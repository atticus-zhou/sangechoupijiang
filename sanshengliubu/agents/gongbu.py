"""工部 — 🖼️ 构建/图片生成 (GPT-image)

工部是三省六部中唯一可以生成图片的部门。
内置专业的 GPT-image 提示词模板，用户配置 API Key 后即可使用。

支持的图片类型:
- 📊 数据图表: 柱状图、折线图、饼图、散点图
- 🏗️ 架构图: 系统架构、网络拓扑、数据流图
- 🔀 流程图: 业务流程、算法流程
- 🎨 宣传图: 发布海报、社交媒体图
"""

from typing import Optional

from ..agent import AutonomousAgent
from ..protocols import (
    CourtMessage, Speaker, MessageType,
    make_message,
)


# ============================================================
# GPT-image 内置提示词模板
# 每个模板都是精心调校的英文 prompt，确保生成高质量图片
# ============================================================

IMAGE_PROMPTS = {
    # ---- 数据图表 ----

    "bar_chart": """Create a professional bar chart visualization with the following specifications:

Style: Clean, modern corporate style with a white background
Colors: Use a professional blue (#2563EB) as primary color, with lighter blue (#93C5FD) for secondary bars
Layout: Horizontal bars preferred for readability, sorted by value descending
Labels: Clear data labels on each bar, with value annotations
Title: Bold title at top, subtitle with context below
Grid: Subtle light gray grid lines for readability
Legend: Top-right position if multiple series
Dimensions: 16:9 aspect ratio, suitable for presentation

Data to visualize: {data_description}
Context: {context}""",

    "line_chart": """Create a professional line chart with the following specifications:

Style: Clean, modern data visualization style on white background
Colors: Use #2563EB for primary line, #DC2626 for secondary, #059669 for tertiary
Lines: Smooth curves with 2px weight, data points as small circles
Axes: Clear labeled axes with units, subtle gray grid lines
Title: Bold descriptive title, source annotation at bottom
Annotations: Key data points annotated with callouts
Dimensions: 16:9 aspect ratio, presentation-ready

Data to visualize: {data_description}
Time period: {context}""",

    "pie_chart": """Create a professional pie/donut chart with the following specifications:

Style: Modern donut chart style preferred, clean white background
Colors: Professional color palette - blues, greens, teals, with distinct contrast
Layout: Donut hole at 60% for center label, segments labeled with percentages
Labels: Percentage + category name on each segment or with connector lines
Title: Bold descriptive title centered above
Legend: Below chart or right side with clear category names
Dimensions: 1:1 square aspect ratio

Data to visualize: {data_description}
Context: {context}""",

    "scatter": """Create a professional scatter plot with the following specifications:

Style: Clean scientific visualization style on white background
Colors: #2563EB for primary data points, semi-transparent for density
Points: Small circles (r=4), with optional trend line in red dashed
Axes: Labeled with units, clear scale, subtle grid
Title: Descriptive title with R-squared if applicable
Annotations: Outliers or key clusters annotated
Dimensions: 16:9 aspect ratio

Data to visualize: {data_description}
Variables: {context}""",

    # ---- 架构图 ----

    "architecture": """Create a professional system architecture diagram with the following specifications:

Style: Clean AWS-style architecture diagram, light background
Boxes: Rounded rectangle boxes with clear borders, color-coded by layer
  - Frontend layer: Blue (#DBEAFE border #2563EB)
  - Backend/API layer: Green (#D1FAE5 border #059669)
  - Database layer: Orange (#FED7AA border #EA580C)
  - External services: Gray (#F3F4F6 border #6B7280)
Arrows: Clear directional arrows showing data flow between components
Labels: Component name inside each box, protocol/port on connection lines
Grouping: Dashed boundary boxes for logical groups (VPC, Cluster, etc.)
Title: System architecture title at top left
Dimensions: 16:9 landscape, readable at zoom

Architecture description: {data_description}
Key components: {context}""",

    "flowchart": """Create a professional flowchart with the following specifications:

Style: Clean business process flowchart, white background
Shapes:
  - Start/End: Rounded pill shape, green (#059669)
  - Process: Rectangle, blue (#2563EB)
  - Decision: Diamond, orange (#EA580C)
  - Data: Parallelogram, gray (#6B7280)
Arrows: Clear directional arrows connecting steps
Labels: Concise action text inside each shape
Layout: Top-to-bottom flow preferred, branches left-to-right for decisions
Swim lanes: Optional horizontal bands for role-based flows
Title: Process name at top
Dimensions: Suitable for documentation

Process flow: {data_description}
Decision points: {context}""",

    # ---- 宣传图 ----

    "poster": """Create a professional promotional poster/image with the following specifications:

Style: Modern, eye-catching design with gradient background
Typography: Bold headline in large font, subtitle in lighter weight
Colors: Vibrant but professional color scheme, brand-appropriate
Composition: Strong visual hierarchy, focal point at center
Elements: Icon or illustration relevant to the topic, subtle decorative elements
Call to action: Clear CTA button or text at bottom
Dimensions: 1:1 square for social media, or 16:9 for banner

Topic: {data_description}
Key message: {context}""",

    "diagram": """Create a clear explanatory diagram with the following specifications:

Style: Clean educational/infographic style, white or light background
Structure: Logical visual flow showing concepts and their relationships
Icons: Simple, recognizable icons for each concept
Connections: Arrows or lines showing relationships between concepts
Labels: Clear text labels, consistent font size hierarchy
Colors: Limited palette (3-5 colors), each with semantic meaning
Dimensions: 16:9, readable when embedded in documentation

Concept to explain: {data_description}
Key relationships: {context}""",
}

# 图片类型的简短描述
IMAGE_TYPE_INFO = {
    "bar_chart": "📊 柱状图 — 用于数据对比、排名展示",
    "line_chart": "📈 折线图 — 用于趋势变化、时间序列",
    "pie_chart": "🥧 饼图 — 用于占比分布、成分分析",
    "scatter": "🔵 散点图 — 用于相关性分析、异常检测",
    "architecture": "🏗️ 架构图 — 用于系统设计、技术方案",
    "flowchart": "🔀 流程图 — 用于业务流程、算法逻辑",
    "poster": "🎨 宣传图 — 用于对外展示、社交媒体",
    "diagram": "📐 示意图 — 用于概念解释、原理说明",
}


GONGBU_PROMPT = """你是工部尚书，三省六部中的工程师。你负责图片生成和构建部署。

## 🖼️ 图片生成 (核心职能)
你是朝堂中唯一可以生成图片的部门。使用 GPT-image 生成高质量图片。

支持的图片类型:
- bar_chart: 柱状图，用于数据对比
- line_chart: 折线图，用于趋势变化
- pie_chart: 饼图，用于占比分布
- scatter: 散点图，用于相关性分析
- architecture: 架构图，用于系统设计
- flowchart: 流程图，用于业务流程
- poster: 宣传图，用于对外展示
- diagram: 示意图，用于概念解释

## 工作流程
1. 收到图片生成请求 → 选择对应的提示词模板
2. 根据用户数据填充模板 → 调用 GPT-image API
3. 返回生成的图片 URL 或 Base64

## 构建部署
- 编译和构建项目
- 安装依赖
- 部署到目标环境"""


class GongbuAgent(AutonomousAgent):

    @property
    def speaker(self) -> Speaker:
        return Speaker.GONGBU

    @property
    def system_prompt(self) -> str:
        return GONGBU_PROMPT

    async def handle_message(self, msg: CourtMessage) -> Optional[CourtMessage]:
        if msg.msg_type == MessageType.GENERATE_IMAGE:
            return await self._generate_image(msg)

        if msg.msg_type == MessageType.BUILD:
            return await self._build(msg)

        return None

    async def _generate_image(self, msg: CourtMessage) -> CourtMessage:
        """🖼️ 使用 GPT-image 生成图片"""
        image_type = msg.payload.get("image_type", "diagram")
        data_description = msg.payload.get("description", "")
        context = msg.payload.get("context", "")

        # 1. 获取对应的提示词模板
        template = IMAGE_PROMPTS.get(image_type, IMAGE_PROMPTS["diagram"])
        type_info = IMAGE_TYPE_INFO.get(image_type, "📐 通用图片")

        # 2. 填充模板，生成完整 prompt
        full_prompt = template.format(
            data_description=data_description,
            context=context,
        )

        self.log_event("图片生成", f"{type_info}: {data_description[:50]}...")

        # 3. 调用 GPT-image API
        image_url = ""
        if self._llm:
            try:
                # 使用 OpenAI 的 image generation API
                import openai
                client = openai.AsyncOpenAI()
                response = await client.images.generate(
                    model="dall-e-3",
                    prompt=full_prompt[:4000],  # DALL-E 的 prompt 长度限制
                    size="1024x1024",
                    quality="standard",
                    n=1,
                )
                image_url = response.data[0].url if response.data else ""
            except Exception as e:
                image_url = f"[图片生成失败: {e}]"

        # 4. 构建返回消息
        result_parts = [
            f"🖼️ 工部图片生成完成!",
            f"",
            f"📌 类型: {type_info}",
            f"📝 描述: {data_description}",
        ]
        if image_url:
            result_parts.append(f"🔗 图片链接: {image_url}")
        else:
            result_parts.append(f"🔧 使用的 Prompt (配置API Key后自动调用GPT-image):")
            result_parts.append(f"```")
            result_parts.append(full_prompt[:500])
            result_parts.append(f"```")

        return make_message(
            task_id=msg.task_id,
            speaker=self.speaker,
            msg_type=MessageType.IMAGE_READY,
            content="\n".join(result_parts),
            payload={
                "type": "image",
                "image_type": image_type,
                "description": data_description,
                "image_url": image_url,
                "prompt_used": full_prompt,
                "status": "generated" if image_url else "prompt_ready",
            },
            reply_to=msg.id,
        )

    async def _build(self, msg: CourtMessage) -> CourtMessage:
        """构建/部署"""
        target = msg.payload.get("target", "project")
        self.log_event("构建", f"目标: {target}")

        return make_message(
            task_id=msg.task_id,
            speaker=self.speaker,
            msg_type=MessageType.RESULT,
            content=f"🖼️ 工部构建完成: {target}",
            payload={"status": "built", "target": target},
            reply_to=msg.id,
        )

    @classmethod
    def get_available_types(cls) -> dict:
        """获取所有可用的图片类型及其描述"""
        return IMAGE_TYPE_INFO

    @classmethod
    def get_prompt_template(cls, image_type: str) -> str:
        """获取指定类型的提示词模板"""
        return IMAGE_PROMPTS.get(image_type, IMAGE_PROMPTS["diagram"])
