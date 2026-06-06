"""三省六部 · Quickstart

用法:
    python examples/quickstart.py

======================================================================
  接入 LLM 的方式
======================================================================

方式一: 环境变量 (推荐)
    export ANTHROPIC_API_KEY="sk-ant-..."
    export OPENAI_API_KEY="sk-..."
    # 然后在 config 中用 ${ANTHROPIC_API_KEY} 引用

方式二: 直接在代码里填
    config = {
        "models": {
            "zhongshu": {"provider": "openai", "model": "gpt-4o", "api_key": "sk-..."},
            ...
        }
    }

方式三: 写 config.yaml 文件 (运行时会自动加载)

======================================================================
  不配任何 Key?
======================================================================
  完全可以。Agent 会使用内置的模拟回应跑完整个流程，
  适合先体验协作机制，再接入 LLM。
"""

import asyncio, sys, io, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Windows UTF-8
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
except Exception:
    pass

from sanshengliubu import CourtSession


def build_config():
    """构建配置——在这里填入你的 API Key"""
    API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    return {
        "models": {
            # 三省 — 用 DeepSeek V3，推理能力最强
            "zhongshu": {"provider": "deepseek", "model": "deepseek-chat", "api_key": API_KEY},
            "menxia":   {"provider": "deepseek", "model": "deepseek-chat", "api_key": API_KEY},
            "shangshu": {"provider": "deepseek", "model": "deepseek-chat", "api_key": API_KEY},
            # 六部
            "libu":     {"provider": "deepseek", "model": "deepseek-chat", "api_key": API_KEY},
            "hubu":     {"provider": "deepseek", "model": "deepseek-chat", "api_key": API_KEY},
            "libu_comm":{"provider": "deepseek", "model": "deepseek-chat", "api_key": API_KEY},
            "bingbu":   {"provider": "deepseek", "model": "deepseek-chat", "api_key": API_KEY},
            "xingbu":   {"provider": "deepseek", "model": "deepseek-chat", "api_key": API_KEY},
            # 工部暂不验证
            "gongbu":   {"provider": "deepseek", "model": "deepseek-chat", "api_key": API_KEY},
        },
        "system": {
            "max_debate_rounds": 5,
            "max_step_retries": 3,
            "vector_db_path": "./data/chroma",
        },
    }


async def main():
    config = build_config()

    # 检查是否有 API Key
    has_key = any(
        cfg.get("api_key", "")
        for cfg in config["models"].values()
    )
    mode = "LLM 驱动模式" if has_key else "模拟模式 (无 API Key)"
    print(f"=== 三省六部 Quickstart [{mode}] ===")
    print()

    async with CourtSession(config_dict=config) as court:
        async for msg in court.submit("修复订单接口超时问题"):
            speaker_label = f"{msg.speaker.emoji} {msg.speaker.display_name}"
            print(f"{speaker_label}: {msg.content[:150]}")
            print()

    print("=== 完成 ===")


if __name__ == "__main__":
    asyncio.run(main())
