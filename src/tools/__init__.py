"""Agent 工具集 — 提供 web_search, web_fetch, file_read 等真实工具"""
from .registry import ToolRegistry, tool_registry
from .web_tools import register_web_tools
from .browser_tools import register_browser_tools
from .scrapling_tools import register_scrapling_tools

# 注册所有工具
register_web_tools(tool_registry)
register_browser_tools(tool_registry)
register_scrapling_tools(tool_registry)
