"""礼部 — Communication Agent: 对接飞书、Web、邮件等外部通信渠道"""

from src.agents.base import BaseAgent
from src.data.schemas import (
    AgentId,
    AgentMessage,
    MessageType,
)
from src.data.prompts import LIBU_COMM_SYSTEM_PROMPT


class LibuCommAgent(BaseAgent):
    agent_id = AgentId.LIBU_COMM

    @property
    def system_prompt(self) -> str:
        return LIBU_COMM_SYSTEM_PROMPT

    async def receive_message(self, channel: str, raw_message: str, task_id: str = "") -> dict:
        """接收外部渠道消息，解析为内部任务格式"""
        prompt = f"""## 接收消息
渠道: {channel}
原始消息:
{raw_message}

请将此消息解析为三省六部系统可以理解的任务描述。提取关键需求和上下文。"""

        result = await self.call_llm(prompt=prompt)
        return {
            "channel": channel,
            "parsed_request": result.get("content", raw_message),
            "raw": raw_message,
        }

    async def format_response(self, channel: str, content: str, task_id: str = "") -> dict:
        """将内部结果格式化为渠道适应的消息"""
        prompt = f"""## 格式化回复
目标渠道: {channel}
原始内容:
{content}

请将以上内容格式化为适合 {channel} 渠道的消息格式。
- 飞书: 可使用 Markdown 和 卡片消息
- Web: HTML/Markdown
- 邮件: 纯文本 + 适当排版"""

        result = await self.call_llm(prompt=prompt)
        return {
            "channel": channel,
            "formatted": result.get("content", content),
            "raw": content,
        }

    async def send_to_channel(self, channel: str, message: str, task_id: str = "") -> dict:
        """发送消息到外部渠道"""
        prompt = f"""## 发送消息
渠道: {channel}
消息内容:
{message}

请确认消息格式是否适合目标渠道，并给出发送结果。"""

        result = await self.call_llm(prompt=prompt)
        return {
            "channel": channel,
            "status": "sent",
            "result": result.get("content", ""),
        }

    async def handle(self, msg: AgentMessage) -> AgentMessage:
        """处理通信相关请求"""
        action = msg.payload.get("action", "")

        if action == "receive":
            result = await self.receive_message(
                channel=msg.payload.get("channel", "web"),
                raw_message=msg.payload.get("message", ""),
                task_id=msg.task_id,
            )
            return AgentMessage(
                id="", task_id=msg.task_id,
                from_agent=self.agent_id, to_agent=msg.from_agent,
                msg_type=MessageType.RESPONSE,
                payload={"action": "parsed_message", "result": result},
            )

        elif action == "format":
            result = await self.format_response(
                channel=msg.payload.get("channel", "web"),
                content=msg.payload.get("content", ""),
                task_id=msg.task_id,
            )
            return AgentMessage(
                id="", task_id=msg.task_id,
                from_agent=self.agent_id, to_agent=msg.from_agent,
                msg_type=MessageType.RESPONSE,
                payload={"action": "formatted_response", "result": result},
            )

        elif action == "send":
            result = await self.send_to_channel(
                channel=msg.payload.get("channel", "web"),
                message=msg.payload.get("message", ""),
                task_id=msg.task_id,
            )
            return AgentMessage(
                id="", task_id=msg.task_id,
                from_agent=self.agent_id, to_agent=msg.from_agent,
                msg_type=MessageType.RESPONSE,
                payload={"action": "send_result", "result": result},
            )

        return AgentMessage(
            id="", task_id=msg.task_id,
            from_agent=self.agent_id, to_agent=msg.from_agent,
            msg_type=MessageType.RESPONSE, payload={"status": "ack"},
        )
