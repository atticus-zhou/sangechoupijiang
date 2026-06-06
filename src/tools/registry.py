"""工具注册表 — 管理 agent 可用的工具"""

from typing import Callable, Optional


class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        self._tools: dict[str, dict] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: dict,
        handler: Callable,
    ):
        """注册一个工具"""
        self._tools[name] = {
            "name": name,
            "description": description,
            "parameters": parameters,
            "handler": handler,
        }

    def get_definitions(self, names: list[str] = None) -> list[dict]:
        """获取工具的 OpenAI function calling 定义"""
        tools = []
        target = names or list(self._tools.keys())
        for name in target:
            if name in self._tools:
                t = self._tools[name]
                tools.append({
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t["parameters"],
                    },
                })
        return tools

    async def execute(self, name: str, arguments: dict) -> dict:
        """执行一个工具调用"""
        if name not in self._tools:
            return {"error": f"未知工具: {name}"}
        handler = self._tools[name]["handler"]
        try:
            result = await handler(**arguments)
            return {"tool": name, "result": result}
        except Exception as e:
            return {"tool": name, "error": str(e)}


tool_registry = ToolRegistry()
