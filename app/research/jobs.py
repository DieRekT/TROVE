"""Background job execution for research tasks."""

import asyncio
import logging
import threading
from typing import List

from app.research import engine, store
from app.research.planner import make_plan
from app.research.renderer import render_markdown
from app.research.schemas import Evidence, Findings, PlanStep, ResearchStart
from app.trove.client import search_trove

logger = logging.getLogger(__name__)

# Rate limiting: max concurrent web requests
MAX_CONCURRENT_WEB = 3
_semaphore = threading.Semaphore(MAX_CONCURRENT_WEB)


def run_in_background(job_id: str, plan: List[PlanStep], params: ResearchStart):
    """
    Execute research plan in background thread.

    Iterates through plan steps, collects evidence, synthesizes findings,
    and generates report.
    """
    try:
        store.update_job_status(job_id, status="running", progress_pct=0)

        total_steps = len(plan)
        all_evidence: List[Evidence] = []

        # Execute plan steps
        for idx, step in enumerate(plan):
            try:
                progress = int((idx / total_steps) * 80)  # 0-80% for collection
                store.update_job_status(job_id, progress_pct=progress)

                logger.info(f"Job {job_id}: Executing step {idx+1}/{total_steps}: {step.query} ({step.scope})")

                if step.scope == "web":
                    evidence = _execute_web_step(step, params.question)
                elif step.scope == "trove":
                    evidence = _execute_trove_step(step)
                else:
                    evidence = []

                # Store evidence
                for ev in evidence:
                    store.append_evidence(job_id, ev)
                    all_evidence.append(ev)

                logger.info(f"Job {job_id}: Collected {len(evidence)} evidence items from {step.scope}")

            except Exception as e:
                logger.error(f"Job {job_id}: Error in step {idx+1}: {e}")
                continue

        # Synthesize findings
        store.update_job_status(job_id, progress_pct=85)
        logger.info(f"Job {job_id}: Synthesizing findings from {len(all_evidence)} evidence items")

        findings = engine.synthesize_findings(all_evidence, params.question)

        # Generate report
        store.update_job_status(job_id, progress_pct=90)
        logger.info(f"Job {job_id}: Generating report")

        markdown = render_markdown(findings, all_evidence)
        report_path = store.persist_report(job_id, markdown)

        # Save evidence as JSONL
        evidence_path = _save_evidence_jsonl(job_id, all_evidence)

        # Update job status
        store.update_job_status(
            job_id,
            status="done",
            progress_pct=100,
            summary_path=report_path,
            evidence_path=evidence_path,
        )

        logger.info(f"Job {job_id}: Completed successfully")

    except Exception as e:
        logger.error(f"Job {job_id}: Fatal error: {e}", exc_info=True)
        store.update_job_status(job_id, status="error", error_message=str(e))


def _execute_web_step(step: PlanStep, question: str) -> List[Evidence]:
    """Execute a web search step with rate limiting."""
    with _semaphore:
        try:
            return engine.call_openai_web(step.query, context_hints=step.rationale)
        except Exception as e:
            logger.error(f"Web step error: {e}")
            return []


def _execute_trove_step(step: PlanStep) -> List[Evidence]:
    """Execute a Trove search step."""
    try:
        return search_trove(step.query, n=20, include_article_text=True)
    except Exception as e:
        logger.error(f"Trove step error: {e}")
        return []


def _save_evidence_jsonl(job_id: str, evidence_list: List[Evidence]) -> str:
    """Save evidence as JSONL file."""
    import json
    from pathlib import Path

    job_dir = Path("outputs/research") / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = job_dir / "evidence.jsonl"

    with open(evidence_path, "w", encoding="utf-8") as f:
        for ev in evidence_list:
            f.write(json.dumps(ev.model_dump(), ensure_ascii=False) + "\n")

    return str(evidence_path)

