"""Office profiles for project-oriented multi-agent workflows.

An office is a product/workflow context. It reuses the same agents, but gives
them office-specific duties, expected artifacts, and acceptance standards.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass(frozen=True)
class OfficeProfile:
    id: str
    name: str
    description: str
    agent_duties: dict[str, str] = field(default_factory=dict)
    artifact_types: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    default_template: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


RESEARCH_OFFICE = OfficeProfile(
    id="research",
    name="Research Office",
    description=(
        "A project office for product research, e-commerce platform analysis, "
        "competitor tables, evidence-backed reports, and launch decisions."
    ),
    agent_duties={
        "zhongshu": "Turn the request into a product-research plan covering industry, platform data, competitors, reviews, opportunities, and launch decisions.",
        "menxia": "Review whether the plan misses platform data, competitor tables, pain-point analysis, opportunity mapping, or boss-ready outputs.",
        "shangshu": "Coordinate collection, verification, table-building, writing, and package export steps.",
        "libu": "Retrieve and archive project context, prior research, and source notes.",
        "hubu": "Structure data tables, competitor matrices, price bands, sales fields, and review-pain-point summaries.",
        "libu_comm": "Format updates for the user and prepare handoff summaries.",
        "bingbu": "Collect market data, platform/e-commerce information, competitor evidence, sources, and screenshot targets.",
        "xingbu": "Verify source quality, data years, placeholder numbers, unsupported claims, and package completeness.",
        "gongbu": "Produce the final report package: report, briefing, tables, opportunity map, screenshot plan, and exportable materials.",
    },
    artifact_types=[
        "report",
        "briefing",
        "data_table",
        "competitor_table",
        "review_pain_points",
        "opportunity_map",
        "chart",
        "chart_plan",
        "source_list",
        "screenshot_plan",
        "quality_report",
    ],
    acceptance_criteria=[
        "The final report has a clear executive summary.",
        "Recent data points include dates and sources where possible.",
        "Important claims are traceable to source notes or evidence artifacts.",
        "Top competitor products are summarized in a comparable table or explicitly marked unavailable.",
        "Review pain points and differentiated opportunities are separated as artifacts.",
        "Charts or tables are separated as artifacts instead of buried only in prose.",
        "Screenshot targets are listed for platform evidence pages.",
        "The final package is useful for a workplace handoff.",
    ],
    default_template=(
        "Research the following product/category and prepare a workplace-ready product research package. "
        "Follow the research office playbook: industry overview, platform/channel data, top competitors, "
        "sales and price-band fields, title/selling-point keywords, user profile, review pain points, "
        "common success factors, differentiation opportunities, chart/table opportunities, screenshot/evidence "
        "needs, and launch/development recommendations. User request: {user_input}"
    ),
)


COMIC_OFFICE = OfficeProfile(
    id="comic",
    name="AI Comic Office",
    description=(
        "A pre-production office for AI comic dramas: script development, "
        "character/prop/scene breakdown, style bible, storyboard, camera "
        "movement plan, prompts, and consistency checks."
    ),
    agent_duties={
        "zhongshu": "Turn the user's idea into a short-drama script direction, conflict structure, episode beats, and human checkpoint plan.",
        "menxia": "Review whether the script direction has a hook, clear stakes, coherent motivation, and reusable production standards.",
        "shangshu": "Coordinate script, asset breakdown, style lock, storyboard, camera plan, prompt package, and consistency checks.",
        "libu": "Archive story bible, style bible, character locks, prop rules, scene rules, and prior generated batches.",
        "hubu": "Maintain structured asset sheets for characters, props, scenes, buildings, and their continuity rules.",
        "libu_comm": "Package outputs for handoff to image, video, and editing platforms.",
        "bingbu": "Prepare storyboard rows, shot prompts, camera movement instructions, and downstream generation tasks.",
        "xingbu": "Check character, prop, scene, style, and shot continuity before assets are accepted.",
        "gongbu": "Produce the pre-production asset package: style bible, prompt package, storyboard, camera plan, and delivery manifest.",
    },
    artifact_types=[
        "script",
        "style_bible",
        "character_sheet",
        "prop_sheet",
        "scene_sheet",
        "storyboard_table",
        "storyboard_handoff",
        "camera_plan",
        "prompt_package",
        "consistency_checklist",
        "delivery_manifest",
    ],
    acceptance_criteria=[
        "The package improves a raw idea into a usable script direction.",
        "Characters, props, and scenes have separate locked asset sheets.",
        "The style bible defines visual consistency and regeneration rules.",
        "Storyboard rows specify scene, characters, props, framing, and prompt.",
        "Camera movement is described separately from the storyboard image prompt.",
        "The package is suitable for downstream image/video/editing tools.",
        "The office does not claim to produce the final edited short drama.",
    ],
    default_template=(
        "Create an AI comic-drama pre-production package from this idea. "
        "Do not produce the final edited video. Produce script direction, "
        "character sheets, prop sheets, scene sheets, style bible, storyboard, "
        "camera movement plan, image prompts, negative prompts, consistency "
        "checklist, and delivery manifest. User idea: {user_input}"
    ),
)


COMIC_PRODUCTION_OFFICE = OfficeProfile(
    id="comic_production",
    name="AI Comic Production Office",
    description=(
        "An isolated production office for AI comic dramas. It turns a confirmed "
        "story into a structured production chain: story contract, department "
        "handoff, asset registry, storyboard/camera plan, prompts, QA, and Word canvas."
    ),
    agent_duties={
        "neige": "Align with the human creator and freeze the story contract before any production work starts.",
        "zhongshu": "Convert the confirmed story into a production brief with required slots, acceptance rules, and department handoff instructions.",
        "menxia": "Audit the production brief for missing characters, props, scenes, continuity rules, storyboard coverage, and delivery requirements.",
        "shangshu": "Dispatch the approved blank production template to departments and track which slots are filled or blocked.",
        "libu": "Maintain continuity memory: story bible, character locks, scene rules, prop rules, and version changes.",
        "hubu": "Maintain the asset registry and resource ledger for characters, props, scenes, generated images, and prompt ownership.",
        "libu_comm": "Adapt the package for downstream platforms and prepare handoff notes for image/video/editing tools.",
        "bingbu": "Build storyboard rows and camera-movement rows from the approved production brief.",
        "xingbu": "Run acceptance checks against story, continuity, image prompt, storyboard, camera plan, and Word canvas completeness.",
        "gongbu": "Generate and assemble assets into the delivery package, including image specs and the Word production canvas.",
    },
    artifact_types=[
        "story_contract",
        "production_brief",
        "production_review",
        "asset_review_package",
        "production_chain_state",
        "dispatch_plan",
        "asset_registry",
        "continuity_bible",
        "platform_delivery_spec",
        "script",
        "character_sheet",
        "prop_sheet",
        "scene_sheet",
        "style_bible",
        "storyboard_table",
        "camera_plan",
        "prompt_package",
        "generated_image",
        "image_quality_report",
        "quality_report",
        "word_canvas",
    ],
    acceptance_criteria=[
        "This office uses a separate office_id from the older AI comic office.",
        "The cabinet story contract is frozen before production starts.",
        "Zhongshu and Menxia only create and review the production specification; execution is dispatched later.",
        "Shangshu receives a blank production template with explicit slots to fill.",
        "Hubu manages the asset registry instead of decomposing the story task.",
        "Libu preserves continuity decisions and version changes.",
        "Bingbu produces storyboard and camera rows that downstream platforms can execute.",
        "Gongbu assembles generated assets and the Word canvas without changing the story contract.",
        "Xingbu marks missing images, generic prompts, broken bindings, and incomplete delivery rows before handoff.",
    ],
    default_template=(
        "Create an isolated AI comic-drama production package from the confirmed story. "
        "Follow the production office chain: story contract, Zhongshu production brief, "
        "Menxia review, Shangshu dispatch plan, Libu continuity bible, Hubu asset registry, "
        "Bingbu storyboard/camera plan, Gongbu assembly, Xingbu QA, and final Word canvas. "
        "User idea or confirmed story: {user_input}"
    ),
)


OFFICE_PROFILES = {
    RESEARCH_OFFICE.id: RESEARCH_OFFICE,
    COMIC_OFFICE.id: COMIC_OFFICE,
    COMIC_PRODUCTION_OFFICE.id: COMIC_PRODUCTION_OFFICE,
}


def list_offices() -> list[dict]:
    return [office.to_dict() for office in OFFICE_PROFILES.values()]


def get_office(office_id: str) -> OfficeProfile:
    return OFFICE_PROFILES.get(office_id, RESEARCH_OFFICE)
