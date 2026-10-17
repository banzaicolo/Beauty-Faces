// ===== 基础工具 =====
const $ = s => document.querySelector(s);
function esc(s){ return (s ?? '').toString().replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function scoreColor(s){
  if(s==null) return '#5b6478';
  if(s>=80) return 'var(--good)';
  if(s>=60) return '#a3e635';
  if(s>=40) return 'var(--mid)';
  return 'var(--bad)';
}
function avg(a){ a = a.filter(v=>v!=null); return a.length ? a.reduce((x,y)=>x+y,0)/a.length : null; }

async function api(path, opts={}){
  opts.credentials = 'same-origin';
  const r = await fetch(path, opts);
  if(!r.ok){
    let m; try{ m = (await r.json()).detail || r.statusText; }catch(e){ m = r.statusText; }
    throw new Error(m);
  }
  return r.json();
}
function post(path, body){ return api(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)}); }

// ===== 全局状态 =====
let meta = { dims: [], categories: [] };
let customersCache = [];
let productsCache = [];
let currentNature = '';
let allNatures = [];
let currentThread = newThreadId();
let sending = false;
let currentCustomer = null;
let editingProductId = null;
let vlmImageB64 = null;
let lastSkinAnalysis = '';
let isAdmin = false;
let privacyMode = 'local_llm';

function newThreadId(){
  return crypto.randomUUID ? crypto.randomUUID() : 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = crypto.getRandomValues(new Uint8Array(1))[0] % 16;
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });
}

// ===== 视图切换 =====
function switchView(v){
  document.querySelectorAll('.nav-item').forEach(b=>b.classList.remove('active'));
  const target = document.querySelector('.nav-item[data-view="'+v+'"]');
  if(target) target.classList.add('active');
  document.querySelectorAll('.view').forEach(x=>x.style.display='none');
  $('#view-' + v).style.display = 'block';
  if(v === 'customers') loadCustomers();
  if(v === 'products') loadProducts();
}
document.querySelectorAll('.nav-item').forEach(btn=>{
  btn.addEventListener('click', ()=>{
    const v = btn.dataset.view;
    if(v === 'customers' || v === 'products'){
      requireLogin(()=>switchView(v));
    } else {
      switchView(v);
    }
  });
});

// ===== 门店登录 =====
function requireLogin(cb){
  if(isAdmin){ cb(); return; }
  openAdminLogin(cb);
}
function openAdminLogin(cb){
  const modal = $('#adminModal');
  modal.innerHTML = `<div class="modal-card" style="max-width:420px">
    <div class="modal-head"><h3>门店登录</h3><button class="modal-close" onclick="closeModal('adminModal')">✕</button></div>
    <div class="form-field"><label>管理口令</label><input id="admin-pass" type="password" placeholder="请输入门店管理口令" onkeydown="if(event.key==='Enter')doLogin()"></div>
    <div class="hint" id="adminErr" style="color:var(--bad);min-height:18px"></div>
    <div class="form-actions">
      <button class="ghost-btn" onclick="closeModal('adminModal')">取消</button>
      <button class="primary-btn" onclick="doLogin()">登录</button>
    </div>
  </div>`;
  modal.classList.add('open');
  window._adminCb = cb;
  setTimeout(()=>{ const i = $('#admin-pass'); if(i) i.focus(); }, 50);
}
async function doLogin(){
  const pass = $('#admin-pass').value.trim();
  if(!pass) return;
  try{
    await post('/api/login', { password: pass });
    isAdmin = true;
    $('#logoutBtn').style.display = 'block';
    closeModal('adminModal');
    const cb = window._adminCb; window._adminCb = null;
    if(cb) cb();
  }catch(e){
    $('#adminErr').textContent = '口令错误，请重试';
  }
}
async function logoutAdmin(){
  try{ await post('/api/logout', {}); }catch(e){}
  isAdmin = false;
  $('#logoutBtn').style.display = 'none';
  switchView('chat');
  alert('已退出门店账号');
}

// ===== 智能顾问（聊天） =====
function addMsg(role, text){
  const box = $('#chatBox');
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  if(role === 'ai') div.innerHTML = '<div class="avatar-sm">小肤</div>';
  const b = document.createElement('div');
  b.className = 'bubble';
  b.textContent = text;
  div.appendChild(b);
  box.appendChild(div);
  scrollChat();
  return b;
}
function scrollChat(){ const box = $('#chatBox'); box.scrollTop = box.scrollHeight; }
function newChat(){
  currentThread = newThreadId();
  $('#chatBox').innerHTML = '';
  $('#chatInput').value = '';
  $('#chatInput').focus();
}

async function sendChat(){
  const input = $('#chatInput');
  const msg = input.value.trim();
  if(!msg || sending) return;
  input.value = '';
  addMsg('user', msg);
  const bubble = addMsg('ai', '');
  bubble.innerHTML = '<span class="spinner"></span> 思考中…';
  sending = true;
  $('#chatBtn').disabled = true;
  let first = true;
  try{
    const resp = await fetch('/api/chat', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ thread_id: currentThread, message: msg })
    });
    if(!resp.ok) throw new Error((await resp.json()).detail || resp.statusText);
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';
    while(true){
      const { done, value } = await reader.read();
      if(done) break;
      buf += decoder.decode(value, { stream:true });
      let idx;
      while((idx = buf.indexOf('\n\n')) >= 0){
        const line = buf.slice(0, idx); buf = buf.slice(idx+2);
        if(!line.startsWith('data: ')) continue;
        const payload = line.slice(6).trim();
        if(payload === '[DONE]') continue;
        let j; try{ j = JSON.parse(payload); }catch(e){ continue; }
        if(j.error){ bubble.innerHTML = `<span style="color:var(--bad)">出错：${esc(j.error)}</span>`; first = false; }
        else if(j.token){ if(first){ bubble.innerHTML=''; first=false; } bubble.innerHTML += esc(j.token); }
        scrollChat();
      }
    }
    if(first) bubble.innerHTML = '（无回复）';
  }catch(e){
    bubble.innerHTML = `<span style="color:var(--bad)">出错：${esc(e.message)}</span>`;
  }finally{
    sending = false; $('#chatBtn').disabled = false; scrollChat();
  }
}

// ===== 客户管理 =====
async function loadCustomers(){
  const kw = $('#searchBox').value.trim();
  customersCache = await api(`/api/customers?keyword=${encodeURIComponent(kw)}&nature=${encodeURIComponent(currentNature)}`);
  $('#customerCount').textContent = `共 ${customersCache.length} 位客户`;
  renderGrid();
  if(!allNatures.length){
    const all = await api('/api/customers');
    allNatures = [...new Set(all.map(c=>c.nature).filter(Boolean))];
    renderChips();
  }
}

function renderChips(){
  const el = $('#chips');
  el.innerHTML = '<div class="chip active" data-f="">全部</div>' +
    allNatures.map(n=>`<div class="chip" data-f="${esc(n)}">${esc(n)}</div>`).join('');
  el.querySelectorAll('.chip').forEach(c=>c.addEventListener('click', ()=>{
    el.querySelectorAll('.chip').forEach(x=>x.classList.remove('active'));
    c.classList.add('active');
    currentNature = c.dataset.f;
    loadCustomers();
  }));
}

function renderGrid(){
  const grid = $('#grid');
  if(!customersCache.length){ grid.innerHTML = '<div class="empty">没有匹配的客户</div>'; return; }
  grid.innerHTML = customersCache.map(d=>`
    <div class="card" onclick="openDetail('${esc(d.id)}')">
      <div class="top"><span class="name">${esc(d.name||'未知')}</span><span class="age">${esc(d.age)}岁 · ${esc(d.sex)}</span></div>
      <div><span class="nature">${esc(d.nature||'—')}</span></div>
      <div class="meta"><span>肤龄 ${esc(d.skin_age)}岁</span><span class="score">综合 ${esc(d.score)}分</span></div>
    </div>`).join('');
}

function computeDims(items){
  return meta.dims.map(d => {
    const vals = d.items.map(n => items[n]).filter(v=>v!=null);
    return { cat:d.cat, label:d.label, items:d.items, score: vals.length ? avg(vals) : null };
  });
}

async function openDetail(id){
  const d = await api('/api/customers/' + id);
  currentCustomer = d;
  const modal = $('#detailModal');
  modal.innerHTML = `<div class="modal-card">
    <div class="modal-head"><h3>客户检测报告</h3><button class="modal-close" onclick="closeModal('detailModal')">✕</button></div>
    <div id="detailBody"></div>
  </div>`;
  modal.classList.add('open');
  renderDetailBody(d);
  loadRecommend(d);
}

function renderDetailBody(d){
  const items = d.items || {};
  const dims = computeDims(items).filter(x=>x.score!=null).sort((a,b)=>a.score-b.score);
  const weak = dims.slice(0,3);
  const itemEntries = Object.entries(items).filter(([k,v])=>v!=null).sort((a,b)=>a[1]-b[1]);
  const fluor = items['荧光剂'];
  $('#detailBody').innerHTML = `
    <div class="hero">
      <div class="avatar">${esc((d.name||'?').charAt(0))}</div>
      <div class="info">
        <h2>${esc(d.name||'—')}</h2>
        <div class="tags">
          <span class="tag">${esc(d.age)}岁 · ${esc(d.sex)}</span>
          <span class="tag">${esc(d.nature||'—')}</span>
          ${d.ph?`<span class="tag">pH ${esc(d.ph)}</span>`:''}
          ${d.water?`<span class="tag">水分 ${parseFloat(d.water).toFixed(0)}%</span>`:''}
        </div>
        <div class="metrics">
          ${d.score?`<div class="metric"><div class="num">${esc(d.score)}</div><div class="lbl">综合分</div></div>`:''}
          ${d.skin_age?`<div class="metric"><div class="num">${esc(d.skin_age)}</div><div class="lbl">肤龄(岁)</div></div>`:''}
          <div class="metric"><div class="num">${esc(d.age||'—')}</div><div class="lbl">实际年龄</div></div>
        </div>
      </div>
    </div>

    <div class="panel" style="background:linear-gradient(135deg,rgba(34,211,238,.06),rgba(129,140,248,.06));border:1px solid rgba(34,211,238,.2)">
      <h3>AI 智能分析</h3>
      <button class="primary-btn" id="aiBtn" onclick="aiAnalyze()">生成 AI 护肤报告</button>
      <div class="hint">${privacyMode === 'local_llm' ? '当前使用已配置的本地模型；请确认 OLLAMA_URL 确实指向受信任的本机或内网服务。' : '当前已启用外部模型：客户检测数据会发送到所配置的 DeepSeek API。'}</div>
      <div id="aiResult"></div>
    </div>

    ${itemEntries.length ? `
    <div class="panel">
      <h3>四维皮肤状态（分越低越需关注）</h3>
      <div class="dims">
        ${dims.map(w=>{ const isWeak = weak.includes(w); return `<div class="dim ${isWeak?'weak':''}">
          <div class="dl"><b>${esc(w.label)}${isWeak?'<span class="badge-focus">重点</span>':''}</b><span>${Math.round(w.score)}分</span></div>
          <div class="bar"><i style="width:${w.score}%;background:${scoreColor(w.score)}"></i></div>
        </div>`; }).join('')}
      </div>
      ${fluor!=null && fluor<40 ? `<div class="warn">⚠ 检测到荧光剂残留风险（评分 ${fluor}），建议加强清洁。</div>` : ''}
    </div>

    <div class="panel">
      <h3>检测项目评分（正脸 · 共 ${itemEntries.length} 项）</h3>
      ${itemEntries.map(([k,v])=>`<div class="itemrow">
        <div class="in">${esc(k)}</div>
        <div class="track"><i style="width:${v}%;background:${scoreColor(v)}"></i></div>
        <div class="val" style="color:${scoreColor(v)}">${v}</div>
      </div>`).join('')}
    </div>` : ''}

    ${d.analysis?`<div class="panel"><h3>问题分析</h3><div class="analysis">${esc(d.analysis)}</div>
      <div style="margin-top:12px"><button class="ghost-btn" onclick="askAdvisorForCustomer()">发给智能顾问深入分析</button></div></div>`:''}
    ${d.advice&&d.advice.length?`<div class="panel"><h3>护理建议</h3><ul class="advice">${d.advice.map(a=>`<li>${esc(a)}</li>`).join('')}</ul></div>`:''}

    ${itemEntries.length ? `<div class="panel"><h3>为你推荐（按皮肤短板匹配）</h3><div id="recoBox"><div class="empty">加载中…</div></div></div>`
      : `<div class="panel"><h3>产品推荐</h3><div class="empty">该客户暂无检测数据，点上方「发给智能顾问深入分析」，AI 会基于问题分析从商品库挑合适的产品</div></div>`}
  `;
}

function askAdvisorForCustomer(){
  if(!currentCustomer) return;
  const d = currentCustomer;
  const parts = [d.age?`${d.age}岁`:'', d.sex||'', d.nature||''];
  document.querySelector('.nav-item[data-view="chat"]').click();
  $('#chatInput').value = `以下是我已获授权使用的护肤检测记录，未包含姓名：${parts.filter(Boolean).join('，')}。\n结果：\n${d.analysis||'暂无'}\n请从商品库里挑合适的产品推荐，并给护理建议。`;
  closeModal('detailModal');
  sendChat();
}

async function loadRecommend(d){
  const box = $('#recoBox');
  if(!box) return;
  try{
    const recos = await post('/api/recommend', { items: d.items||{} });
    if(!recos.length){ box.innerHTML = '<div class="empty">暂无推荐</div>'; return; }
    box.innerHTML = recos.map(r=>`
      <div class="reco-group">
        <div class="rg-title">${esc(r.label)}护理 · ${esc(r.cat)} <span class="why">（该维度 ${Math.round(r.score)} 分）</span></div>
        <div class="prods">
          ${r.products.map(p=>`<div class="prod">
            ${p.image ? `<img class="prod-img" src="${esc(p.image)}" loading="lazy">` : ''}
            <div class="brand">${esc(p.brand)}</div>
            <div class="pname">${esc(p.name)}</div>
            <div class="desc">${esc(p.description)}</div>
            <div class="ing">成分：${esc(p.ingredients)}</div>
            <div class="foot"><span class="price">${esc(p.price)}</span><span>${esc(p.skin_type)}</span></div>
          </div>`).join('')}
        </div>
      </div>`).join('');
  }catch(e){
    $('#recoBox').innerHTML = `<div class="warn">推荐加载失败：${esc(e.message)}</div>`;
  }
}

async function aiAnalyze(){
  if(!currentCustomer) return;
  const btn = $('#aiBtn'), box = $('#aiResult');
  btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> 生成中…';
  box.innerHTML = '';
  try{
    const data = await post('/api/ai-report', { customer_id: currentCustomer.id });
    const tags = (data.weak_dims||[]).map(w=>`<span class="ai-tag">${esc(w.cat)} ${w.score}分</span>`).join('');
    box.innerHTML = `<div class="ai-result">${esc(data.report)}</div><div class="ai-tags">${tags}</div>`;
  }catch(e){
    box.innerHTML = `<div class="warn">生成失败：${esc(e.message)}</div>`;
  }finally{
    btn.disabled = false; btn.innerHTML = '生成 AI 护肤报告';
  }
}

function closeModal(id){ $('#'+id).classList.remove('open'); }

// ===== 拍照测肤 =====
document.getElementById('vlmFile').addEventListener('change', function(){
  const file = this.files && this.files[0];
  if(!file) return;
  const reader = new FileReader();
  reader.onload = e=>{
    const img = new Image();
    img.onload = ()=>{
      const MAX = 1280; let w = img.width, h = img.height;
      const scale = Math.min(1, MAX/Math.max(w,h));
      w = Math.round(w*scale); h = Math.round(h*scale);
      const c = document.createElement('canvas'); c.width=w; c.height=h;
      c.getContext('2d').drawImage(img, 0, 0, w, h);
      vlmImageB64 = c.toDataURL('image/jpeg', 0.85);
      const pv = $('#vlmPreview'); pv.src = vlmImageB64; pv.style.display = 'block';
      $('#vlmBtn').disabled = false; $('#vlmResult').innerHTML = '';
    };
    img.src = e.target.result;
  };
  reader.readAsDataURL(file);
});

async function vlmAnalyze(){
  if(!vlmImageB64) return;
  const btn = $('#vlmBtn'), box = $('#vlmResult');
  btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> 分析中…';
  // 流式：思考过程灰字实时滚动，正文逐字打出，进度一目了然
  box.innerHTML = `<div class="vlm-thinking-box"><div class="vlm-thinking-label">AI 正在观察照片…</div><div class="vlm-thinking" id="vlmThinking"></div></div>
    <div class="vlm-result" id="vlmContent" style="display:none"></div>`;
  const thEl = $('#vlmThinking'), ctEl = $('#vlmContent');
  const thBox = thEl.parentElement;
  try{
    const resp = await fetch('/api/vlm-analyze', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ image: vlmImageB64 })
    });
    if(!resp.ok) throw new Error((await resp.json()).detail || resp.statusText);
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = '', analysis = '';
    while(true){
      const { done, value } = await reader.read();
      if(done) break;
      buf += decoder.decode(value, { stream:true });
      let idx;
      while((idx = buf.indexOf('\n\n')) >= 0){
        const line = buf.slice(0, idx); buf = buf.slice(idx+2);
        if(!line.startsWith('data: ')) continue;
        const payload = line.slice(6).trim();
        if(payload === '[DONE]') continue;
        let j; try{ j = JSON.parse(payload); }catch(e){ continue; }
        if(j.error) throw new Error(j.error);
        if(j.type === 'thinking'){
          thEl.textContent += j.text;
          thBox.scrollTop = thBox.scrollHeight;
        }else if(j.type === 'content'){
          if(ctEl.style.display === 'none'){ thBox.querySelector('.vlm-thinking-label').textContent = '分析完成'; ctEl.style.display = 'block'; }
          analysis += j.text;
          ctEl.textContent = analysis;
        }
      }
    }
    if(!analysis) analysis = thEl.textContent || '（无结果）';
    lastSkinAnalysis = analysis;
    ctEl.insertAdjacentHTML('afterend', `
      <div class="vlm-actions">
        <button class="primary-btn" onclick="saveVlmAsCustomer()">存为客户</button>
        <button class="ghost-btn" onclick="askAdvisorAboutSkin()">发给智能顾问分析</button>
      </div>
      <div class="vlm-save-form" id="vlmSaveForm" style="display:none">
        <div class="svf-row">
          <input id="vlm-c-name" placeholder="姓名（必填）">
          <input id="vlm-c-age" placeholder="年龄" type="number" min="1" max="120">
          <select id="vlm-c-sex"><option>女</option><option>男</option></select>
          <select id="vlm-c-nature">
            <option value="">肤质…</option><option>中性皮肤</option><option>干性皮肤</option>
            <option>油性皮肤</option><option>混合型皮肤</option><option>敏感肌</option>
          </select>
          <button class="primary-btn" onclick="confirmSaveVlmCustomer()">保存</button>
        </div>
      </div>`);
  }catch(e){
    box.innerHTML = `<div class="warn">分析失败：${esc(e.message)}</div>`;
  }finally{
    btn.disabled = false; btn.innerHTML = '开始分析';
  }
}

// ===== 测肤结果联动 =====
function saveVlmAsCustomer(){
  if(!isAdmin){ requireLogin(saveVlmAsCustomer); return; }
  $('#vlmSaveForm').style.display = 'block';
}
async function confirmSaveVlmCustomer(){
  const name = $('#vlm-c-name').value.trim();
  if(!name){ alert('请填写姓名'); return; }
  try{
    await post('/api/customers', {
      name,
      age: $('#vlm-c-age').value,
      sex: $('#vlm-c-sex').value,
      nature: $('#vlm-c-nature').value,
      analysis: lastSkinAnalysis
    });
    $('#vlmSaveForm').style.display = 'none';
    alert('已保存到客户管理，数据持久化在本地数据库');
  }catch(e){
    alert('保存失败：' + e.message);
  }
}
function askAdvisorAboutSkin(){
  if(!lastSkinAnalysis) return;
  document.querySelector('.nav-item[data-view="chat"]').click();
  $('#chatInput').value = `我刚做了拍照测肤，AI 视觉分析结果如下：\n${lastSkinAnalysis}\n请根据我的皮肤状况，从商品库里挑合适的产品推荐，并给护理建议。`;
  sendChat();
}

// ===== 新增客户 =====
function openCustomerForm(){
  const modal = $('#detailModal');
  modal.innerHTML = `<div class="modal-card">
    <div class="modal-head"><h3>新增客户</h3><button class="modal-close" onclick="closeModal('detailModal')">✕</button></div>
    <div class="form-grid">
      <div class="form-field"><label>姓名 *</label><input id="c-name" placeholder="客户姓名"></div>
      <div class="form-field"><label>年龄</label><input id="c-age" type="number" min="1" max="120"></div>
      <div class="form-field"><label>性别</label><select id="c-sex"><option>女</option><option>男</option></select></div>
      <div class="form-field"><label>肤质</label><select id="c-nature">
        <option value="">未测</option><option>中性皮肤</option><option>干性皮肤</option>
        <option>油性皮肤</option><option>混合型皮肤</option><option>敏感肌</option>
      </select></div>
      <div class="form-field full"><label>备注 / 皮肤情况</label><textarea id="c-analysis" rows="3" placeholder="可选，如：两颊干燥，T区偏油"></textarea></div>
    </div>
    <div class="form-actions">
      <button class="ghost-btn" onclick="closeModal('detailModal')">取消</button>
      <button class="primary-btn" onclick="saveNewCustomer()">保存</button>
    </div>
  </div>`;
  modal.classList.add('open');
}

async function saveNewCustomer(){
  const name = $('#c-name').value.trim();
  if(!name){ alert('请填写姓名'); return; }
  try{
    await post('/api/customers', {
      name,
      age: $('#c-age').value,
      sex: $('#c-sex').value,
      nature: $('#c-nature').value,
      analysis: $('#c-analysis').value.trim()
    });
    closeModal('detailModal');
    currentNature = '';
    loadCustomers();
  }catch(e){
    alert('保存失败：' + e.message);
  }
}

// ===== 商品库 =====
async function loadProducts(){
  const kw = $('#productSearch').value.trim();
  productsCache = await api('/api/products?keyword=' + encodeURIComponent(kw));
  $('#productCount').textContent = `共 ${productsCache.length} 款`;
  renderProductTable();
}

function renderProductTable(){
  const el = $('#productTable');
  if(!productsCache.length){ el.innerHTML = '<div class="empty">暂无商品，点右上角「新增商品」添加</div>'; return; }
  el.innerHTML = `<thead><tr>
    <th>图片</th><th>品牌</th><th>名称</th><th>功效</th><th>适用肤质</th><th>成分</th><th>价格</th><th>操作</th>
  </tr></thead><tbody>` + productsCache.map(p=>`<tr>
    <td>${p.image ? `<img class="prod-thumb" src="${esc(p.image)}" loading="lazy">` : '<span class="prod-thumb none">—</span>'}</td>
    <td><span class="brand">${esc(p.brand)}</span></td>
    <td>${esc(p.name)}</td>
    <td><span class="cat-badge">${esc(p.category)}</span></td>
    <td>${esc(p.skin_type)}</td>
    <td>${esc(p.ingredients)}</td>
    <td>${esc(p.price)}</td>
    <td style="white-space:nowrap">
      <button class="edit-btn" onclick="openProductFormById(${p.id})">编辑</button>
      <button class="danger-btn" onclick="deleteProduct(${p.id})">删除</button>
    </td>
  </tr>`).join('') + '</tbody>';
}

function openProductFormById(id){
  const p = productsCache.find(x=>x.id===id);
  openProductForm(p);
}

function openProductForm(p){
  editingProductId = p ? p.id : null;
  const cats = meta.categories || [];
  const modal = $('#productModal');
  modal.innerHTML = `<div class="modal-card">
    <div class="modal-head"><h3>${p?'编辑商品':'新增商品'}</h3><button class="modal-close" onclick="closeModal('productModal')">✕</button></div>
    <div class="form-grid">
      <div class="form-field"><label>品牌</label><input id="f-brand" value="${esc(p?p.brand:'')}"></div>
      <div class="form-field"><label>名称</label><input id="f-name" value="${esc(p?p.name:'')}"></div>
      <div class="form-field"><label>功效分类</label><select id="f-category">${cats.map(c=>`<option ${p&&p.category===c?'selected':''}>${esc(c)}</option>`).join('')}</select></div>
      <div class="form-field"><label>适用肤质</label><input id="f-skin" value="${esc(p?p.skin_type:'')}" placeholder="如 油性/混合"></div>
      <div class="form-field"><label>价格</label><input id="f-price" value="${esc(p?p.price:'')}" placeholder="如 ¥ 239"></div>
      <div class="form-field"><label>成分</label><input id="f-ing" value="${esc(p?p.ingredients:'')}" placeholder="逗号分隔"></div>
      <div class="form-field full"><label>说明</label><textarea id="f-desc" rows="2">${esc(p?p.description:'')}</textarea></div>
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
    brand: $('#f-brand').value.trim(),
    name: $('#f-name').value.trim(),
    category: $('#f-category').value,
    skin_type: $('#f-skin').value.trim(),
    ingredients: $('#f-ing').value.trim(),
    price: $('#f-price').value.trim(),
    description: $('#f-desc').value.trim(),
  };
  if(!body.name){ alert('请填写商品名称'); return; }
  if(editingProductId){
    await api('/api/products/'+editingProductId, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  }else{
    await post('/api/products', body);
  }
  closeModal('productModal');
  loadProducts();
}

async function deleteProduct(id){
  if(!confirm('确定删除该商品？')) return;
  await api('/api/products/'+id, {method:'DELETE'});
  loadProducts();
}

// ===== 初始化 =====
async function init(){
  try{
    const h = await api('/api/health');
    const st = $('#sideStatus');
    privacyMode = h.privacy || 'local_llm';
    st.textContent = privacyMode === 'local_llm' ? '在线 · 本地模型模式' : '在线 · 外部模型模式';
    st.classList.add('ok');
  }catch(e){
    $('#sideStatus').textContent = '连接失败';
  }
  try{ await api('/api/session'); }catch(e){}
  try{
    await api('/api/admin/session');
    isAdmin = true;
    $('#logoutBtn').style.display = 'block';
  }catch(e){
    isAdmin = false;
  }
  try{ meta = await api('/api/meta'); }catch(e){}
  if(isAdmin){ loadCustomers(); loadProducts(); }
  $('#chatBox').innerHTML = `<div class="msg ai"><div class="avatar-sm">小肤</div><div class="bubble">你好，我是 AI 护肤内容助手「小肤」。<br>你可以问我：<br>· 推荐一款祛痘产品<br>· 烟酰胺有什么作用？<br>· 如何看懂检测分数？<br><br><small>本工具提供一般护肤信息，不提供医疗诊断，也不能替代医生。</small></div></div>`;
}
init();
