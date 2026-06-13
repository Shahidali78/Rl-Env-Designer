"""Reporter Agent — step 5 of the pipeline.

Takes the EnvironmentDesign and the TrainingResult and asks claude-fable-5
to write a human-readable markdown report covering the problem, the design
decisions, training performance, and suggestions for improvement.

Saves the report to backend/training/{env_name}/report.md.
"""

import re
from pathlib import Path

from agents.trainer_agent import TRAINING_DIR, snake_case
from llm import LLMError, generate_text
from schemas import EnvironmentDesign, TrainingResult

SYSTEM_PROMPT = """\
You are a technical writer specializing in reinforcement learning. You receive \
the JSON design of an auto-generated Gymnasium environment and the metrics from \
its training run, and you write a clear markdown report for a reader who knows \
software but not RL.

Structure the report with these sections:

# <Environment name>: RL Training Report
## Problem
## Environment Design
   Explain WHY the state space, action space, and each reward component were \
chosen the way they were — translate the design rationale into plain language, \
and connect every reward component back to a real-world objective.
## Training Performance
   Report the algorithm, timesteps, training time, and the reward metrics. \
Include a small markdown table. Interpret the improvement percentage over the \
initial (≈ random-policy) baseline honestly: say clearly whether the agent \
actually learned, plateaued, or regressed.
## Suggestions for Improvement
   3-5 concrete, actionable suggestions for improving the environment design \
or training setup (reward shaping, observation features, episode structure, \
algorithm/hyperparameters, longer training).

Rules:
- Use ONLY the numbers provided — never invent metrics, baselines, or results.
- Be honest about weak results; do not spin a flat or negative improvement as \
success.
- Respond with ONLY the markdown document. No code fences around the whole \
document, no preamble.
"""


class ReporterAgentError(Exception):
    """Raised when the Reporter Agent cannot produce a report."""


def _strip_outer_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", text)
        text = re.sub(r"\n```\s*$", "", text)
    return text.strip() + "\n"


async def generate_report(
    design: EnvironmentDesign, training_result: TrainingResult
) -> tuple[str, Path]:
    """Write the markdown report and save it next to the training artifacts.

    Returns (report_markdown, report_path).
    """
    user_content = (
        "Write the training report for this environment.\n\n"
        "=== ENVIRONMENT DESIGN ===\n"
        f"{design.model_dump_json(indent=2)}\n\n"
        "=== TRAINING RESULT ===\n"
        f"{training_result.model_dump_json(indent=2)}"
    )

    try:
        report_md = await generate_text(SYSTEM_PROMPT, user_content, max_tokens=16000)
    except LLMError as e:
        raise ReporterAgentError(str(e)) from e

    report_md = _strip_outer_fences(report_md)
    if not report_md.strip():
        raise ReporterAgentError("The model returned an empty report.")

    run_dir = TRAINING_DIR / snake_case(design.environment_name)
    run_dir.mkdir(parents=True, exist_ok=True)
    report_path = run_dir / "report.md"
    report_path.write_text(report_md, encoding="utf-8")

    return report_md, report_path
