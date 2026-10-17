"""LangGraph 智能体：ReAct 循环 + 工具调用 + SqliteSaver 多轮记忆（按 thread_id 隔离会话）"""

import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.prebuilt import create_react_agent

from . import config
from .llm import get_chat_model
from .tools import ALL_TOOLS

_agent = None


def get_agent():
    """懒加载单例 agent：模型可插拔（ollama/DeepSeek），工具从 tools.py 挂载"""
    global _agent
    if _agent is None:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        # SqliteSaver 直接收 sqlite3 连接；check_same_thread=False 允许跨线程
        conn = sqlite3.connect(str(config.DATA_DIR / "checkpoints.db"), check_same_thread=False)
        memory = SqliteSaver(conn)
        model = get_chat_model()
        system_prompt = config.load_text("system_prompt.txt")
        _agent = create_react_agent(model, ALL_TOOLS, prompt=system_prompt, checkpointer=memory)
    return _agent
