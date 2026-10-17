"""LangGraph agent with optional native tool calling and SQLite memory."""

import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.prebuilt import create_react_agent

from . import config
from .llm import get_chat_model
from .tools import ALL_TOOLS

_agent = None


def get_agent():
    """Build the active chat model and expose tools only when configured."""
    global _agent
    if _agent is None:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        # SqliteSaver 直接收 sqlite3 连接；check_same_thread=False 允许跨线程
        conn = sqlite3.connect(str(config.CHECKPOINT_DB_PATH), check_same_thread=False)
        memory = SqliteSaver(conn)
        model = get_chat_model()
        system_prompt = config.load_text("system_prompt.txt")
        tools = ALL_TOOLS if config.TEXT_TOOL_CALLING else []
        if not tools:
            system_prompt += (
                "\n\nThis deployment has native tool calling disabled. "
                "Answer only from user-provided context and the prompt; "
                "do not claim to have queried the product or knowledge database."
            )
        _agent = create_react_agent(model, tools, prompt=system_prompt, checkpointer=memory)
    return _agent
