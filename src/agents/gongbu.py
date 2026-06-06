"""工部 — Builder Agent: 项目搭建、文档生成、报告产出"""

import json
import os
import re
from pathlib import Path

from src.agents.base import BaseAgent
from src.data.schemas import (
    AgentId,
    AgentMessage,
    MessageType,
)
from src.data.prompts import GONGBU_SYSTEM_PROMPT

OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"


class GongbuAgent(BaseAgent):
    agent_id = AgentId.GONGBU

    @property
    def system_prompt(self) -> str:
        return GONGBU_SYSTEM_PROMPT

    def _write_file(self, task_id: str, filename: str, content: str) -> str:
        """将内容写入磁盘文件, 返回文件路径"""
        task_dir = OUTPUT_DIR / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        filepath = task_dir / filename
        filepath.write_text(content, encoding="utf-8")
        return str(filepath)

    async def scaffold_project(self, spec: str, output_dir: str, task_id: str = "") -> dict:
        """从零搭建项目骨架"""
        prompt = f"""## 项目搭建任务
需求规格:
{spec}

输出目录: {output_dir}

请设计项目结构并生成所有必要的文件:
1. 目录结构
2. 入口文件
3. 配置文件
4. 基础的模块骨架
5. README 和说明文档

请输出实质性内容，不要留空。"""

        result = await self.call_llm(prompt=prompt, max_tokens=8192)
        content = result.get("content", "")
        files = []
        if content and task_id:
            self._write_file(task_id, "project_scaffold.md", content)
            files = [f"output/{task_id}/project_scaffold.md"]
        return {
            "task_type": "scaffold",
            "files_created": files,
            "summary": f"已设计项目骨架: {output_dir}",
            "content": content or "(LLM 返回空)",
        }

    async def generate_document(self, doc_type: str, context: str, task_id: str = "") -> dict:
        """生成文档"""
        type_names = {
            "readme": "README 项目说明",
            "api": "API 接口文档",
            "architecture": "架构设计文档",
            "guide": "使用指南",
            "changelog": "变更日志",
        }

        prompt = f"""## 文档生成任务
文档类型: {type_names.get(doc_type, doc_type)}
参考上下文:
{context}

请生成完整的文档内容，必须输出实质性文本。"""

        result = await self.call_llm(prompt=prompt, max_tokens=8192)
        content = result.get("content", "")
        files = []
        if content and task_id:
            self._write_file(task_id, f"{doc_type}.md", content)
            files = [f"output/{task_id}/{doc_type}.md"]
        return {
            "task_type": "document",
            "files_created": files,
            "summary": f"已生成 {type_names.get(doc_type, doc_type)}",
            "content": content or "(LLM 返回空)",
        }

    async def generate_report(self, title: str, data: str, task_id: str = "") -> dict:
        """生成综合分析报告, 写入磁盘文件"""
        prompt = f"""## 报告生成任务
报告标题: {title}

原始数据/素材:
{data}

请生成一份可以提交给老板的研究报告。

硬性要求:
1. 不要写“X百万台”“Y亿元”等占位符。
2. 没有来源支撑的具体数字必须写“待核验”，不能编造。
3. 报告必须包含: 执行摘要、关键结论、市场/行业现状、竞争格局、趋势判断、风险与不确定性、图表建议、来源与待核验清单。
4. 图表建议要说明图表类型、用途、需要的数据字段。
5. 如果原始材料不足，要明确列出缺口，而不是假装完整。
6. 输出 Markdown 正文，不要输出调度决策 JSON。"""

        result = await self.call_llm(prompt=prompt, max_tokens=8192)
        content = result.get("content", "")
        files = []
        if content and task_id:
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)[:40]
            self._write_file(task_id, f"{safe_title}.md", content)
            files = [f"output/{task_id}/{safe_title}.md"]
        return {
            "task_type": "report",
            "files_created": files,
            "summary": f"已生成报告: {title}",
            "content": content or "(LLM 返回空)",
        }

    async def render_template(self, template: str, variables: dict, task_id: str = "") -> dict:
        """根据模板渲染内容"""
        prompt = f"""## 模板渲染任务
模板:
{template}

变量:
{variables}

请根据模板和变量渲染输出，必须输出实质性内容。"""

        result = await self.call_llm(prompt=prompt, max_tokens=8192)
        content = result.get("content", "")
        return {
            "task_type": "template",
            "files_created": [],
            "summary": "模板渲染完成",
            "content": content or "(LLM 返回空)",
        }

    async def handle(self, msg: AgentMessage) -> AgentMessage:
        """处理建造相关请求"""
        action = msg.payload.get("action", "")

        if action == "scaffold":
            result = await self.scaffold_project(
                spec=msg.payload.get("spec", ""),
                output_dir=msg.payload.get("output_dir", "."),
                task_id=msg.task_id,
            )
            return AgentMessage(
                id="", task_id=msg.task_id,
                from_agent=self.agent_id, to_agent=msg.from_agent,
                msg_type=MessageType.RESPONSE,
                payload={"action": "scaffold_result", "result": result},
            )

        elif action == "generate_doc":
            result = await self.generate_document(
                doc_type=msg.payload.get("doc_type", "readme"),
                context=msg.payload.get("context", ""),
                task_id=msg.task_id,
            )
            return AgentMessage(
                id="", task_id=msg.task_id,
                from_agent=self.agent_id, to_agent=msg.from_agent,
                msg_type=MessageType.RESPONSE,
                payload={"action": "doc_result", "result": result},
            )

        elif action == "generate_report":
            result = await self.generate_report(
                title=msg.payload.get("title", "报告"),
                data=msg.payload.get("data", ""),
                task_id=msg.task_id,
            )
            return AgentMessage(
                id="", task_id=msg.task_id,
                from_agent=self.agent_id, to_agent=msg.from_agent,
                msg_type=MessageType.RESPONSE,
                payload={"action": "report_result", "result": result},
            )

        elif action == "render_template":
            result = await self.render_template(
                template=msg.payload.get("template", ""),
                variables=msg.payload.get("variables", {}),
                task_id=msg.task_id,
            )
            return AgentMessage(
                id="", task_id=msg.task_id,
                from_agent=self.agent_id, to_agent=msg.from_agent,
                msg_type=MessageType.RESPONSE,
                payload={"action": "render_result", "result": result},
            )

        return AgentMessage(
            id="", task_id=msg.task_id,
            from_agent=self.agent_id, to_agent=msg.from_agent,
            msg_type=MessageType.RESPONSE, payload={"status": "ack"},
        )
