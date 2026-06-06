from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config_manager import ConfigManager
from src.model_connectivity import probe_model_connectivity


AGENTS = [
    ("global", "", "zhongshu"),
    ("global", "", "hubu"),
    ("comic", "comic", "hubu"),
    ("comic", "comic", "xingbu"),
    ("comic", "comic", "bingbu"),
    ("comic", "comic", "gongbu"),
]


async def probe(label: str, office_id: str, agent: str) -> dict:
    config = ConfigManager().get_model_config(agent, office_id=office_id)
    result = await probe_model_connectivity(
        agent,
        office_id,
        config,
        output_dir=Path("output/model_tests/quick"),
    )
    result["label"] = label
    return result


async def main() -> None:
    seen = set()
    tasks = []
    for label, office_id, agent in AGENTS:
        key = (label, office_id, agent)
        if key in seen:
            continue
        seen.add(key)
        tasks.append(probe(label, office_id, agent))
    results = await asyncio.gather(*tasks)
    for item in results:
        print(
            "{label}.{agent} | {provider}/{model} | key={key} | kind={kind} | {status} | {detail}".format(
                label=item["label"],
                agent=item["agent"],
                provider=item["provider"],
                model=item["model"],
                key="SET" if item["has_key"] else "EMPTY",
                kind=item["kind"],
                status=item["status"],
                detail=(item["detail"] or "").replace("\n", " ")[:500],
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
