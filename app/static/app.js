// ===== Utilities =====
const $ = s => document.querySelector(s);
function esc(s){ return (s ?? '').toString().replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function copy(key, fallback=''){ return (meta.copy && meta.copy[key]) || fallback; }
function attrValue(record, key){
  if(record?.attributes && record.attributes[key] != null) return record.attributes[key];
  return record?.[key] ?? '';
}
function attributeField(key){ return (meta.customer_fields || []).find(f => f.key === key); }
function filterField(){
  return (meta.customer_fields || []).find(f => f.filterable) || meta.customer_fields?.[0];
}
function itemLabel(key){ return meta.item_labels?.[key] || key; }
function scoreColor(score){
  if(score==null || Number.isNaN(Number(score))) return '#5b6478';
  const value = params_meta().higher_is_better ? Number(score) : 100 - Number(score);
  if(value>=80) return 'var(--good)';
  if(value>=60) return '#a3e635';
  if(value>=40) return 'var(--mid)';
  return 'var(--bad)';
}
function params_meta(){ return meta || {}; }
function weightedAverage(values){
  const usable = values.filter(([value,weight]) => value!=null && Number(weight)>0);
  const totalWeight = usable.reduce((sum,[,weight]) => sum + Number(weight), 0);
  return usable.length && totalWeight ? usable.reduce((sum,[value,weight]) => sum + Number(value)*Number(weight), 0) / totalWeight : null;
}

async function api(path, opts={}){
  opts.credentials = 'same-origin';
  const response = await fetch(path, opts);
  if(!response.ok){
    let message; try{ message = (await response.json()).detail || response.statusText; }catch(e){ message = response.statusText; }
    throw new Error(message);
  }
  return response.json();
}
function post(path, body){ return api(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)}); }
function newThreadId(){
  return crypto.randomUUID ? crypto.randomUUID() : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = crypto.getRandomValues(new Uint8Array(1))[0] % 16;
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });
}

// ===== State =====
let meta = {
  branding: {}, copy: {}, dimensions: [], customer_fields: [],
  recommendation: {top_dimensions: 3}, categories: [], item_labels: {}, alerts: []
};
let customersCache = [];
let productsCache = [];
let currentSegment = '';
let allSegments = [];
let currentThread = newThreadId();
let sending = false;
let currentCustomer = null;
let editingProductId = null;
let vlmImageB64 = null;
let lastAnalysis = '';
let isAdmin = false;
let privacyMode = 'local_llm';

// ===== Profile-driven copy =====
function setText(id, text){
  const element = document.getElementById(id);
  if(element && text != null) element.textContent = text;
}
function applyProfile(profile){
  meta = profile || meta;
  const brand = meta.branding?.name || 'Consultation Assistant';
  const tagline = meta.branding?.tagline || '';
  document.title = tagline ? `${brand} · ${tagline}` : brand;
  setText('brandName', brand);
  setText('serviceGroup', copy('service_group', '顾问服务'));
  setText('adminGroup', copy('admin_group', '管理'));
  setText('chatNav', copy('chat_nav', '智能顾问'));
  setText('assessmentNav', copy('assessment_nav', '照片分析'));
  setText('customerNav', copy('customer_nav', '客户管理'));
  setText('productNav', copy('product_nav', '产品库'));
  setText('chatTitle', copy('chat_title', '智能顾问'));
  setText('chatSub', copy('chat_subtitle', '多轮对话 · 自动查库'));
  setText('newChatBtn', copy('new_chat', '＋ 新对话'));
  setText('customersTitle', copy('customers_title', '客户管理'));
  setText('addCustomerBtn', copy('add_customer', '＋ 新增客户'));
  setText('assessmentTitle', copy('assessment_title', '照片分析'));
  setText('assessmentSub', copy('assessment_subtitle', '一般性外观观察'));
  setText('assessmentUpload', copy('assessment_upload', '选择照片 / 拍照'));
  setText('assessmentHint', copy('assessment_hint', '照片会发送到所配置的视觉模型服务。'));
  setText('productsTitle', copy('products_title', '产品库'));
  setText('addProductBtn', copy('add_product', '＋ 新增产品'));
  setText('logoutBtn', copy('logout', '退出登录'));
  setText('vlmBtn', copy('assessment_start', '开始分析'));
  $('#chatInput').placeholder = copy('chat_placeholder', '输入你的问题…');
  $('#searchBox').placeholder = copy('customer_search_placeholder', '搜索客户…');
  $('#productSearch').placeholder = copy('product_search_placeholder', '搜索产品…');
  const assessmentEnabled = meta.assessment?.enabled !== false;
  document.querySelector('.nav-item[data-view="camera"]').style.display = assessmentEnabled ? '' : 'none';
  renderChatWelcome();
}
function renderChatWelcome(){
  const examples = (meta.copy?.chat_examples || []).map(example => `· ${esc(example)}`).join('<br>');
  const assistant = esc(copy('assistant_name', '顾问'));
  $('#chatBox').innerHTML = `<div class="msg ai"><div class="avatar-sm">${esc(copy('assistant_name', '顾问').charAt(0))}</div><div class="bubble">你好，我是 ${assistant}。<br>你可以问我：<br>${examples}<br><br><small>${esc(copy('disclaimer'))}</small></div></div>`;
}

// ===== Views and auth =====
function switchView(view){
  document.querySelectorAll('.nav-item').forEach(button => button.classList.remove('active'));
  const target = document.querySelector('.nav-item[data-view="'+view+'"]');
  if(target) target.classList.add('active');
  document.querySelectorAll('.view').forEach(element => element.style.display='none');
  $('#view-' + view).style.display = 'block';
  if(view === 'customers') loadCustomers();
  if(view === 'products') loadProducts();
}
document.querySelectorAll('.nav-item').forEach(button => {
  button.addEventListener('click', () => {
    const view = button.dataset.view;
    if(view === 'customers' || view === 'products'){
      requireLogin(() => switchView(view));
    }else{
      switchView(view);
    }
  });
});
function requireLogin(callback){
  if(isAdmin){ callback(); return; }
  openAdminLogin(callback);
}
function openAdminLogin(callback){
  const modal = $('#adminModal');
  modal.innerHTML = `<div class="modal-card" style="max-width:420px">
    <div class="modal-head"><h3>${esc(copy('login_title', '管理登录'))}</h3><button class="modal-close" onclick="closeModal('adminModal')">✕</button></div>
    <div class="form-field"><label>${esc(copy('login_title', '管理登录'))}</label><input id="admin-pass" type="password" placeholder="请输入管理口令" onkeydown="if(event.key==='Enter')doLogin()"></div>
    <div class="hint" id="adminErr" style="color:var(--bad);min-height:18px"></div>
    <div class="form-actions">
      <button class="ghost-btn" onclick="closeModal('adminModal')">取消</button>
      <button class="primary-btn" onclick="doLogin()">登录</button>
    </div>
  </div>`;
  modal.classList.add('open');
  window._adminCb = callback;
  setTimeout(() => $('#admin-pass')?.focus(), 50);
}
async function doLogin(){
  const password = $('#admin-pass').value.trim();
  if(!password) return;
  try{
    await post('/api/login', { password });
    isAdmin = true;
    $('#logoutBtn').style.display = 'block';
    closeModal('adminModal');
    const callback = window._adminCb;
    window._adminCb = null;
    if(callback) callback();
  }catch(e){
    $('#adminErr').textContent = '口令错误，请重试';
  }
}
async function logoutAdmin(){
  try{ await post('/api/logout', {}); }catch(e){}
  isAdmin = false;
  $('#logoutBtn').style.display = 'none';
  switchView('chat');
  alert('已退出管理账号');
}

// ===== Chat =====
function addMsg(role, text){
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  if(role === 'ai') div.innerHTML = `<div class="avatar-sm">${esc(copy('assistant_name', '顾问').charAt(0))}</div>`;
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = text;
  div.appendChild(bubble);
  $('#chatBox').appendChild(div);
  scrollChat();
  return bubble;
}
function scrollChat(){ const box = $('#chatBox'); box.scrollTop = box.scrollHeight; }
function newChat(){
  currentThread = newThreadId();
  renderChatWelcome();
  $('#chatInput').value = '';
  $('#chatInput').focus();
}
async function sendChat(){
  const input = $('#chatInput');
  const message = input.value.trim();
  if(!message || sending) return;
  input.value = '';
  addMsg('user', message);
  const bubble = addMsg('ai', '');
  bubble.innerHTML = '<span class="spinner"></span> 思考中…';
  sending = true;
  $('#chatBtn').disabled = true;
  let first = true;
  try{
    const response = await fetch('/api/chat', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ thread_id: currentThread, message })
    });
    if(!response.ok) throw new Error((await response.json()).detail || response.statusText);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while(true){
      const { done, value } = await reader.read();
      if(done) break;
      buffer += decoder.decode(value, {stream:true});
      let index;
      while((index = buffer.indexOf('\n\n')) >= 0){
        const line = buffer.slice(0, index);
        buffer = buffer.slice(index+2);
        if(!line.startsWith('data: ')) continue;
        const payload = line.slice(6).trim();
        if(payload === '[DONE]') continue;
        let data; try{ data = JSON.parse(payload); }catch(e){ continue; }
        if(data.error){
          bubble.innerHTML = `<span style="color:var(--bad)">出错：${esc(data.error)}</span>`;
          first = false;
        }else if(data.token){
          if(first){ bubble.innerHTML = ''; first = false; }
          bubble.innerHTML += esc(data.token);
        }
        scrollChat();
      }
    }
    if(first) bubble.innerHTML = '（无回复）';
  }catch(e){
    bubble.innerHTML = `<span style="color:var(--bad)">出错：${esc(e.message)}</span>`;
  }finally{
    sending = false;
    $('#chatBtn').disabled = false;
    scrollChat();
  }
}

// ===== Customers =====
async function loadCustomers(){
  const keyword = $('#searchBox').value.trim();
  customersCache = await api(`/api/customers?keyword=${encodeURIComponent(keyword)}&segment=${encodeURIComponent(currentSegment)}`);
  $('#customerCount').textContent = `共 ${customersCache.length} 条`;
  renderGrid();
  if(!allSegments.length){
    const all = await api('/api/customers');
    const field = filterField();
    allSegments = [...new Set(all.map(customer => attrValue(customer, field?.key)).filter(Boolean))];
    renderChips();
  }
}
function renderChips(){
  const element = $('#chips');
  element.innerHTML = '<div class="chip active" data-f="">全部</div>' +
    allSegments.map(value => `<div class="chip" data-f="${esc(value)}">${esc(value)}</div>`).join('');
  element.querySelectorAll('.chip').forEach(chip => chip.addEventListener('click', () => {
    element.querySelectorAll('.chip').forEach(item => item.classList.remove('active'));
    chip.classList.add('active');
    currentSegment = chip.dataset.f;
    loadCustomers();
  }));
}
function renderGrid(){
  const grid = $('#grid');
  if(!customersCache.length){ grid.innerHTML = '<div class="empty">没有匹配的记录</div>'; return; }
  const field = filterField();
  grid.innerHTML = customersCache.map(customer => {
    const segment = attrValue(customer, field?.key);
    const details = (meta.customer_fields || [])
      .filter(item => !item.filterable)
      .map(item => attrValue(customer, item.key))
      .filter(Boolean)
      .slice(0, 2)
      .map(esc)
      .join(' · ');
    return `<div class="card" onclick="openDetail('${esc(customer.id)}')">
      <div class="top"><span class="name">${esc(customer.name||'未命名')}</span><span class="age">${details}</span></div>
      <div><span class="nature">${esc(segment||'—')}</span></div>
      <div class="meta"><span>${esc(field?.label||'')}</span><span class="score">${customer.score?`评分 ${esc(customer.score)}`:'—'}</span></div>
    </div>`;
  }).join('');
}
function computeDimensions(items){
  return (meta.dimensions || []).map(dimension => {
    const detail = {};
    const values = [];
    for(const item of dimension.items){
      if(items[item.key] == null) continue;
      detail[item.key] = items[item.key];
      values.push([items[item.key], item.weight || 1]);
    }
    return {...dimension, detail, score: weightedAverage(values)};
  }).filter(dimension => dimension.score != null);
}
function rankDimensions(items){
  const dimensions = computeDimensions(items);
  const higherIsBetter = meta.higher_is_better !== false;
  dimensions.sort((a,b) => higherIsBetter ? a.score-b.score : b.score-a.score);
  return dimensions;
}
async function openDetail(id){
  currentCustomer = await api('/api/customers/' + id);
  const modal = $('#detailModal');
  modal.innerHTML = `<div class="modal-card">
    <div class="modal-head"><h3>${esc(copy('customer_detail_title', '客户记录'))}</h3><button class="modal-close" onclick="closeModal('detailModal')">✕</button></div>
    <div id="detailBody"></div>
  </div>`;
  modal.classList.add('open');
  renderDetailBody(currentCustomer);
  loadRecommend(currentCustomer);
}
function renderDetailBody(customer){
  const items = customer.items || {};
  const dimensions = rankDimensions(items);
  const focusCount = Number(meta.recommendation?.top_dimensions || 3);
  const focused = dimensions.slice(0, focusCount);
  const itemEntries = Object.entries(items).filter(([,value]) => value!=null)
    .sort((a,b) => meta.higher_is_better === false ? b[1]-a[1] : a[1]-b[1]);
  const tags = [];
  if(customer.age) tags.push(`${customer.age}岁`);
  if(customer.sex) tags.push(customer.sex);
  for(const field of meta.customer_fields || []){
    const value = attrValue(customer, field.key);
    if(value) tags.push(`${field.label} ${value}${field.unit||''}`);
  }
  const alerts = activeAlerts(items);
  $('#detailBody').innerHTML = `
    <div class="hero">
      <div class="avatar">${esc((customer.name||'?').charAt(0))}</div>
      <div class="info">
        <h2>${esc(customer.name||'—')}</h2>
        <div class="tags">${tags.map(tag => `<span class="tag">${esc(tag)}</span>`).join('')}</div>
        ${customer.score?`<div class="metrics"><div class="metric"><div class="num">${esc(customer.score)}</div><div class="lbl">评分</div></div></div>`:''}
      </div>
    </div>

    <div class="panel" style="background:linear-gradient(135deg,rgba(34,211,238,.06),rgba(129,140,248,.06));border:1px solid rgba(34,211,238,.2)">
      <h3>AI 建议</h3>
      <button class="primary-btn" id="aiBtn" onclick="aiAnalyze()">${esc(copy('report_button', '生成 AI 建议'))}</button>
      <div class="hint">${privacyMode === 'local_llm' ? '当前使用已配置的本地模型；请确认模型地址受信任。' : '当前使用外部模型，记录内容会发送到所配置的 API。'}</div>
      <div id="aiResult"></div>
    </div>

    ${itemEntries.length ? `
    <div class="panel">
      <h3>${esc(copy('dimension_heading', '关注维度'))}</h3>
      <div class="dims">
        ${dimensions.map(dimension => { const isFocus = focused.includes(dimension); return `<div class="dim ${isFocus?'weak':''}">
          <div class="dl"><b>${esc(dimension.label)}${isFocus?'<span class="badge-focus">重点</span>':''}</b><span>${Math.round(dimension.score)}分</span></div>
          <div class="bar"><i style="width:${dimension.score}%;background:${scoreColor(dimension.score)}"></i></div>
        </div>`; }).join('')}
      </div>
      ${alerts.map(alert => `<div class="warn">⚠ ${esc(alert.message)}</div>`).join('')}
    </div>
    <div class="panel">
      <h3>${esc(copy('item_heading', '指标'))}</h3>
      ${itemEntries.map(([key,value]) => `<div class="itemrow">
        <div class="in">${esc(itemLabel(key))}</div>
        <div class="track"><i style="width:${value}%;background:${scoreColor(value)}"></i></div>
        <div class="val" style="color:${scoreColor(value)}">${value}</div>
      </div>`).join('')}
    </div>` : ''}

    ${customer.analysis?`<div class="panel"><h3>${esc(copy('analysis_title', '记录摘要'))}</h3><div class="analysis">${esc(customer.analysis)}</div>
      <div style="margin-top:12px"><button class="ghost-btn" onclick="askAdvisorForCustomer()">${esc(copy('send_to_advisor', '发给智能顾问'))}</button></div></div>`:''}
    ${customer.advice?.length?`<div class="panel"><h3>${esc(copy('advice_title', '建议'))}</h3><ul class="advice">${customer.advice.map(item => `<li>${esc(item)}</li>`).join('')}</ul></div>`:''}
    ${itemEntries.length ? `<div class="panel"><h3>${esc(copy('recommendation_heading', '匹配产品'))}</h3><div id="recoBox"><div class="empty">加载中…</div></div></div>`:''}
  `;
}
function activeAlerts(items){
  return (meta.alerts || []).filter(alert => {
    const value = items[alert.item];
    if(value == null) return false;
    const threshold = Number(alert.threshold || 0);
    const check = {
      lt: Number(value) < threshold, lte: Number(value) <= threshold,
      gt: Number(value) > threshold, gte: Number(value) >= threshold,
      eq: Number(value) === threshold
    };
    return check[alert.operator] || false;
  });
}
function askAdvisorForCustomer(){
  if(!currentCustomer) return;
  const details = [];
  for(const field of meta.customer_fields || []){
    const value = attrValue(currentCustomer, field.key);
    if(value) details.push(`${field.label} ${value}`);
  }
  document.querySelector('.nav-item[data-view="chat"]').click();
  $('#chatInput').value = `以下是我已获授权使用的${copy('customer_detail_title', '记录')}，未包含姓名：${details.join('，')}。\n${currentCustomer.analysis||'暂无摘要'}\n请给出产品匹配与一般建议。`;
  closeModal('detailModal');
  sendChat();
}
async function loadRecommend(customer){
  const box = $('#recoBox');
  if(!box) return;
  try{
    const recommendations = await post('/api/recommend', { items: customer.items || {} });
    if(!recommendations.length){ box.innerHTML = '<div class="empty">暂无推荐</div>'; return; }
    box.innerHTML = recommendations.map(recommendation => `
      <div class="reco-group">
        <div class="rg-title">${esc(recommendation.label)} <span class="why">（${Math.round(recommendation.score)} 分）</span></div>
        <div class="prods">${recommendation.products.map(product => `<div class="prod">
          ${product.image ? `<img class="prod-img" src="${esc(product.image)}" loading="lazy">` : ''}
          <div class="brand">${esc(product.brand)}</div>
          <div class="pname">${esc(product.name)}</div>
          <div class="desc">${esc(product.description)}</div>
          <div class="ing">${esc(copy('product_features_label'))}: ${esc(product.features)}</div>
          <div class="foot"><span class="price">${esc(product.price)}</span><span>${esc(product.target)}</span></div>
        </div>`).join('')}</div>
      </div>`).join('');
  }catch(e){
    box.innerHTML = `<div class="warn">推荐加载失败：${esc(e.message)}</div>`;
  }
}
async function aiAnalyze(){
  if(!currentCustomer) return;
  const button = $('#aiBtn'), box = $('#aiResult');
  button.disabled = true;
  button.innerHTML = '<span class="spinner"></span> 生成中…';
  box.innerHTML = '';
  try{
    const data = await post('/api/ai-report', { customer_id: currentCustomer.id });
    const tags = (data.weak_dims||[]).map(item => `<span class="ai-tag">${esc(item.label)} ${item.score}分</span>`).join('');
    box.innerHTML = `<div class="ai-result">${esc(data.report)}</div><div class="ai-tags">${tags}</div>`;
  }catch(e){
    box.innerHTML = `<div class="warn">生成失败：${esc(e.message)}</div>`;
  }finally{
    button.disabled = false;
    button.textContent = copy('report_button', '生成 AI 建议');
  }
}

// ===== Customer forms =====
function attributeInputHtml(prefix, field, value=''){
  const id = `${prefix}-${field.key}`;
  if(field.type === 'select'){
    const options = (field.options || []).map(option => `<option ${String(option)===String(value)?'selected':''}>${esc(option)}</option>`).join('');
    return `<div class="form-field"><label>${esc(field.label)}</label><select id="${esc(id)}"><option value="">未填写</option>${options}</select></div>`;
  }
  const type = field.type === 'number' ? 'number' : 'text';
  return `<div class="form-field"><label>${esc(field.label)}</label><input id="${esc(id)}" type="${type}" value="${esc(value)}" placeholder="${esc(field.placeholder||'')}"></div>`;
}
function readAttributes(prefix){
  const attributes = {};
  for(const field of meta.customer_fields || []){
    const value = document.getElementById(`${prefix}-${field.key}`)?.value.trim();
    if(value) attributes[field.key] = value;
  }
  return attributes;
}
function openCustomerForm(){
  const modal = $('#detailModal');
  modal.innerHTML = `<div class="modal-card">
    <div class="modal-head"><h3>${esc(copy('add_customer', '新增客户'))}</h3><button class="modal-close" onclick="closeModal('detailModal')">✕</button></div>
    <div class="form-grid">
      <div class="form-field"><label>姓名 *</label><input id="customer-name" placeholder="姓名"></div>
      ${(meta.customer_fields||[]).map(field => attributeInputHtml('customer', field)).join('')}
      <div class="form-field full"><label>${esc(copy('analysis_title', '备注'))}</label><textarea id="customer-analysis" rows="3"></textarea></div>
    </div>
    <div class="form-actions">
      <button class="ghost-btn" onclick="closeModal('detailModal')">取消</button>
      <button class="primary-btn" onclick="saveNewCustomer()">保存</button>
    </div>
  </div>`;
  modal.classList.add('open');
}
async function saveNewCustomer(){
  const name = $('#customer-name').value.trim();
  if(!name){ alert('请填写姓名'); return; }
  try{
    await post('/api/customers', {
      name,
      attributes: readAttributes('customer'),
      analysis: $('#customer-analysis').value.trim()
    });
    closeModal('detailModal');
    currentSegment = '';
    allSegments = [];
    loadCustomers();
  }catch(e){
    alert('保存失败：' + e.message);
  }
}

// ===== Visual assessment =====
document.getElementById('vlmFile').addEventListener('change', function(){
  const file = this.files && this.files[0];
  if(!file) return;
  const reader = new FileReader();
  reader.onload = event => {
    const image = new Image();
    image.onload = () => {
      const max = 1280;
      const scale = Math.min(1, max/Math.max(image.width, image.height));
      const canvas = document.createElement('canvas');
      canvas.width = Math.round(image.width*scale);
      canvas.height = Math.round(image.height*scale);
      canvas.getContext('2d').drawImage(image, 0, 0, canvas.width, canvas.height);
      vlmImageB64 = canvas.toDataURL('image/jpeg', 0.85);
      $('#vlmPreview').src = vlmImageB64;
      $('#vlmPreview').style.display = 'block';
      $('#vlmBtn').disabled = false;
      $('#vlmResult').innerHTML = '';
    };
    image.src = event.target.result;
  };
  reader.readAsDataURL(file);
});
async function vlmAnalyze(){
  if(!vlmImageB64) return;
  const button = $('#vlmBtn'), box = $('#vlmResult');
  button.disabled = true;
  button.innerHTML = '<span class="spinner"></span> 分析中…';
  box.innerHTML = `<div class="vlm-thinking-box"><div class="vlm-thinking-label">正在观察照片…</div><div class="vlm-thinking" id="vlmThinking"></div></div>
    <div class="vlm-result" id="vlmContent" style="display:none"></div>`;
  const thinking = $('#vlmThinking'), content = $('#vlmContent');
  try{
    const response = await fetch('/api/vlm-analyze', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ image: vlmImageB64 })
    });
    if(!response.ok) throw new Error((await response.json()).detail || response.statusText);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '', analysis = '';
    while(true){
      const { done, value } = await reader.read();
      if(done) break;
      buffer += decoder.decode(value, {stream:true});
      let index;
      while((index = buffer.indexOf('\n\n')) >= 0){
        const line = buffer.slice(0, index);
        buffer = buffer.slice(index+2);
        if(!line.startsWith('data: ')) continue;
        const payload = line.slice(6).trim();
        if(payload === '[DONE]') continue;
        let data; try{ data = JSON.parse(payload); }catch(e){ continue; }
        if(data.error) throw new Error(data.error);
        if(data.type === 'thinking'){
          thinking.textContent += data.text;
        }else if(data.type === 'content'){
          if(content.style.display === 'none'){ thinking.parentElement.querySelector('.vlm-thinking-label').textContent = '分析完成'; content.style.display = 'block'; }
          analysis += data.text;
          content.textContent = analysis;
        }
      }
    }
    lastAnalysis = analysis || thinking.textContent || '（无结果）';
    content.insertAdjacentHTML('afterend', `
      <div class="vlm-actions">
        <button class="primary-btn" onclick="saveAssessmentAsCustomer()">${esc(copy('save_customer', '保存为客户'))}</button>
        <button class="ghost-btn" onclick="askAdvisorAboutAssessment()">${esc(copy('send_to_advisor', '发给智能顾问'))}</button>
      </div>
      <div class="vlm-save-form" id="vlmSaveForm" style="display:none">
        <div class="form-grid">
          <div class="form-field"><label>姓名 *</label><input id="vlm-name" placeholder="姓名"></div>
          ${(meta.customer_fields||[]).map(field => attributeInputHtml('vlm', field)).join('')}
        </div>
        <button class="primary-btn" onclick="confirmSaveAssessmentCustomer()">保存</button>
      </div>`);
  }catch(e){
    box.innerHTML = `<div class="warn">分析失败：${esc(e.message)}</div>`;
  }finally{
    button.disabled = false;
    button.textContent = copy('assessment_start', '开始分析');
  }
}
function saveAssessmentAsCustomer(){
  if(!isAdmin){ requireLogin(saveAssessmentAsCustomer); return; }
  $('#vlmSaveForm').style.display = 'block';
}
async function confirmSaveAssessmentCustomer(){
  const name = $('#vlm-name').value.trim();
  if(!name){ alert('请填写姓名'); return; }
  try{
    await post('/api/customers', {
      name,
      attributes: readAttributes('vlm'),
      analysis: lastAnalysis
    });
    $('#vlmSaveForm').style.display = 'none';
    alert('已保存到本地数据库');
  }catch(e){
    alert('保存失败：' + e.message);
  }
}
function askAdvisorAboutAssessment(){
  if(!lastAnalysis) return;
  document.querySelector('.nav-item[data-view="chat"]').click();
  $('#chatInput').value = `我刚完成一次${copy('assessment_title', '照片分析')}，结果如下：\n${lastAnalysis}\n请给出一般建议并说明如何理解结果。`;
  sendChat();
}

// ===== Products =====
async function loadProducts(){
  const keyword = $('#productSearch').value.trim();
  productsCache = await api('/api/products?keyword=' + encodeURIComponent(keyword));
  $('#productCount').textContent = `共 ${productsCache.length} 款`;
  renderProductTable();
}
function renderProductTable(){
  const element = $('#productTable');
  if(!productsCache.length){ element.innerHTML = '<div class="empty">暂无产品</div>'; return; }
  element.innerHTML = `<thead><tr>
    <th>图片</th><th>品牌</th><th>名称</th><th>${esc(copy('product_category_label', '分类'))}</th><th>${esc(copy('product_target_label', '适用对象'))}</th><th>${esc(copy('product_features_label', '特点'))}</th><th>价格</th><th>操作</th>
  </tr></thead><tbody>` + productsCache.map(product => `<tr>
    <td>${product.image ? `<img class="prod-thumb" src="${esc(product.image)}" loading="lazy">` : '<span class="prod-thumb none">—</span>'}</td>
    <td><span class="brand">${esc(product.brand)}</span></td>
    <td>${esc(product.name)}</td>
    <td><span class="cat-badge">${esc(product.category)}</span></td>
    <td>${esc(product.target)}</td>
    <td>${esc(product.features)}</td>
    <td>${esc(product.price)}</td>
    <td style="white-space:nowrap">
      <button class="edit-btn" onclick="openProductFormById(${product.id})">编辑</button>
      <button class="danger-btn" onclick="deleteProduct(${product.id})">删除</button>
    </td>
  </tr>`).join('') + '</tbody>';
}
function openProductFormById(id){ openProductForm(productsCache.find(product => product.id === id)); }
function openProductForm(product){
  editingProductId = product ? product.id : null;
  const categories = meta.categories || [];
  const modal = $('#productModal');
  modal.innerHTML = `<div class="modal-card">
    <div class="modal-head"><h3>${product?'编辑':'新增'}${esc(copy('product_nav', '产品'))}</h3><button class="modal-close" onclick="closeModal('productModal')">✕</button></div>
    <div class="form-grid">
      <div class="form-field"><label>品牌</label><input id="product-brand" value="${esc(product?product.brand:'')}"></div>
      <div class="form-field"><label>名称</label><input id="product-name" value="${esc(product?product.name:'')}"></div>
      <div class="form-field"><label>${esc(copy('product_category_label', '分类'))}</label><select id="product-category">${categories.map(category => `<option ${product&&product.category===category?'selected':''}>${esc(category)}</option>`).join('')}</select></div>
      <div class="form-field"><label>${esc(copy('product_target_label', '适用对象'))}</label><input id="product-target" value="${esc(product?product.target:'')}"></div>
      <div class="form-field"><label>价格</label><input id="product-price" value="${esc(product?product.price:'')}"></div>
      <div class="form-field"><label>${esc(copy('product_features_label', '特点'))}</label><input id="product-features" value="${esc(product?product.features:'')}"></div>
      <div class="form-field full"><label>说明</label><textarea id="product-description" rows="2">${esc(product?product.description:'')}</textarea></div>
    </div>
    <div class="form-actions">
      <button class="ghost-btn" onclick="closeModal('productModal')">取消</button>
      <button class="primary-btn" onclick="saveProduct()">保存</button>
    </div>
  </div>`;
  modal.classList.add('open');
}
async function saveProduct(){
  const body = {
    brand: $('#product-brand').value.trim(),
    name: $('#product-name').value.trim(),
    category: $('#product-category').value,
    target: $('#product-target').value.trim(),
    features: $('#product-features').value.trim(),
    price: $('#product-price').value.trim(),
    description: $('#product-description').value.trim()
  };
  if(!body.name){ alert('请填写产品名称'); return; }
  if(editingProductId){
    await api('/api/products/'+editingProductId, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  }else{
    await post('/api/products', body);
  }
  closeModal('productModal');
  loadProducts();
}
async function deleteProduct(id){
  if(!confirm('确定删除该产品？')) return;
  await api('/api/products/'+id, {method:'DELETE'});
  loadProducts();
}
function closeModal(id){ $('#'+id).classList.remove('open'); }

// ===== Initialize =====
async function init(){
  let health = null;
  try{
    health = await api('/api/health');
    privacyMode = health.privacy || 'local_llm';
  }catch(e){
    $('#sideStatus').textContent = '连接失败';
  }
  try{ meta = await api('/api/meta'); }catch(e){}
  applyProfile(meta);
  if(health){
    const status = $('#sideStatus');
    status.textContent = '在线 · ' + copy(privacyMode === 'local_llm' ? 'privacy_local' : 'privacy_external');
    status.classList.add('ok');
  }
  try{ await api('/api/session'); }catch(e){}
  try{
    await api('/api/admin/session');
    isAdmin = true;
    $('#logoutBtn').style.display = 'block';
  }catch(e){
    isAdmin = false;
  }
  if(isAdmin){ loadCustomers(); loadProducts(); }
}
init();
