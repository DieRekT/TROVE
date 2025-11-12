"""Research plan generator."""

from typing import List, Optional

from app.research.schemas import PlanStep


def make_plan(
    question: str,
    region: Optional[str] = None,
    time_window: Optional[str] = None,
    depth: str = "standard",
) -> List[PlanStep]:
    """
    Generate a research plan with 8-15 targeted steps.

    Mixes web and trove scopes, with bias toward Trove for AU history/culture
    and web for government/academic sources.
    """
    steps = []

    # Determine step count based on depth
    base_steps = {"brief": 6, "standard": 10, "deep": 15}
    target_count = base_steps.get(depth, 10)

    # Build query modifiers
    region_mod = f" {region}" if region else ""
    time_mod = f" {time_window}" if time_window else ""

    # Core question variations
    core_queries = [
        (question, "Direct search for the main research question"),
        (f"{question}{region_mod}", "Question with regional context"),
        (f"{question}{time_mod}", "Question with temporal context"),
    ]

    # Angle variations
    angle_queries = [
        (f"history {question}{region_mod}{time_mod}", "Historical perspective"),
        (f"impact {question}{region_mod}", "Impact analysis"),
        (f"controversy {question}{region_mod}{time_mod}", "Controversial aspects"),
        (f"policy {question}{region_mod}", "Policy and regulation angle"),
        (f"community {question}{region_mod}{time_mod}", "Community response"),
        (f"origins {question}{region_mod}", "Origins and background"),
    ]

    # Trove-specific queries (AU archival focus)
    trove_queries = [
        (f"{question}{region_mod}{time_mod}", "Newspaper archives search"),
        (f"newspaper {question}{region_mod}", "Newspaper coverage"),
        (f"archive {question}{region_mod}{time_mod}", "Archival records"),
    ]

    # Web-specific queries (government/academic)
    web_queries = [
        (f"{question} site:gov.au", "Government sources"),
        (f"{question} site:edu.au", "Academic sources"),
        (f"{question} research paper", "Research papers"),
        (f"{question} report analysis", "Reports and analysis"),
    ]

    # Build plan: mix core, angles, trove, and web
    step_idx = 0

    # Add core queries (mix web/trove)
    for query, rationale in core_queries[:2]:
        if step_idx >= target_count:
            break
        scope = "trove" if step_idx % 2 == 0 else "web"
        steps.append(PlanStep(query=query, rationale=rationale, scope=scope))
        step_idx += 1

    # Add Trove queries (bias for AU history)
    trove_count = target_count // 2 if depth == "deep" else target_count // 3
    for query, rationale in trove_queries[:trove_count]:
        if step_idx >= target_count:
            break
        steps.append(PlanStep(query=query, rationale=rationale, scope="trove"))
        step_idx += 1

    # Add web queries (government/academic)
    for query, rationale in web_queries:
        if step_idx >= target_count:
            break
        steps.append(PlanStep(query=query, rationale=rationale, scope="web"))
        step_idx += 1

    # Fill remaining with angle queries
    for query, rationale in angle_queries:
        if step_idx >= target_count:
            break
        scope = "trove" if "history" in query.lower() or "archive" in query.lower() else "web"
        steps.append(PlanStep(query=query, rationale=rationale, scope=scope))
        step_idx += 1

    return steps[:target_count]

