"""Coder Agent — step 2 of the pipeline.

Takes the EnvironmentDesign produced by the Designer Agent and generates a
complete, runnable Gymnasium environment file with claude-fable-5. Also
provides the auto-fix call used by the Code Executor when the generated
environment fails its sanity check.

Code generation streams the response (full env files can run long) and the
model is instructed to emit only Python source, which is fence-stripped
defensively before being written to backend/generated_envs/.
"""

import re
from pathlib import Path

from llm import LLMError, generate_text
from schemas import EnvironmentDesign

GENERATED_ENVS_DIR = Path(__file__).resolve().parent.parent / "generated_envs"

SYSTEM_PROMPT = """\
You are an expert Python engineer who writes production-quality Gymnasium \
reinforcement learning environments. You receive a structured environment \
design and emit one complete, self-contained Python file.

Hard requirements for the file you write:

1. Imports: only the Python standard library, `numpy`, and `gymnasium`. The \
file must be runnable as-is with no other dependencies and no network access.

2. Exactly one environment class, named exactly as given in the design's \
environment_name, inheriting from `gymnasium.Env`. Implement `__init__`, \
`reset`, `step`, `render`, and `close`.

3. Spaces must match the design EXACTLY — same Gymnasium space class, same \
variable order, same bounds. For Box spaces use `dtype=np.float32` and make \
sure every observation you return is `np.float32` and lies within the declared \
bounds (clip if simulation dynamics could exceed them), so that \
`observation_space.contains(obs)` is always True.

4. `reset(self, seed=None, options=None)` must call `super().reset(seed=seed)`, \
draw ALL randomness from `self.np_random` (Gymnasium initializes it even when \
no seed is given), and return `(obs, info)`. NEVER create your own RNG that \
only exists when a seed is provided — training libraries call `reset()` with \
no seed, and the environment must work identically in that case.

5. `step(self, action)` must return the 5-tuple \
`(obs, reward, terminated, truncated, info)`. Set `truncated=True` when the \
step counter reaches the design's episode_length; set `terminated=True` only \
for the design's termination_conditions. The info dict must include a \
`"reward_components"` mapping with the value of every reward component for \
that step.

6. The reward must implement EVERY component listed in the design's \
reward_function, each multiplied by its weight and summed. Implement each \
component as a small, clearly named private method or inline block.

7. Simulate the environment dynamics yourself (demand, arrivals, failures, \
prices, ...) using `self.np_random` so episodes are reproducible under a seed.

8. Comments: include inline comments that reference the design rationale — \
explain WHY a dynamic, bound, or reward term is shaped the way it is, not what \
the line does.

9. `render` may simply print a compact human-readable summary of the current \
state; `close` can be a no-op.

Output format: respond with ONLY the Python source code. No markdown fences, \
no prose before or after, no explanations. The first line of your response \
must be valid Python (a docstring or import).
"""

FIX_SYSTEM_PROMPT = """\
You are an expert Python debugger. You receive a Gymnasium environment file \
that failed a runtime check (instantiate -> reset -> random steps, including a \
reset() WITHOUT a seed as training libraries do, with \
observation_space.contains() asserted on every observation — or a crash during \
actual SAC/PPO training), together with the failure output. Return the \
COMPLETE corrected file.

Rules:
- Fix the root cause, not just the symptom; keep the environment's design \
(spaces, reward components, dynamics, comments) intact.
- Keep imports limited to the standard library, numpy, and gymnasium.
- Respond with ONLY the full corrected Python source. No markdown fences, no \
prose. The first line must be valid Python.
"""


class CoderAgentError(Exception):
    """Raised when the Coder Agent cannot produce usable code."""


def _strip_code_fences(text: str) -> str:
    """Defensively remove markdown fences if the model adds them anyway."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", text)
        text = re.sub(r"\n```\s*$", "", text)
    return text.strip() + "\n"


def _snake_case(name: str) -> str:
    name = re.sub(r"[^0-9a-zA-Z]+", "", name)
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


async def _generate(system: str, user_content: str) -> str:
    """Shared LLM call: returns the model's text output as Python source."""
    try:
        code = await generate_text(system, user_content, max_tokens=32000)
    except LLMError as e:
        raise CoderAgentError(str(e)) from e

    code = _strip_code_fences(code)
    if "gymnasium" not in code or "class" not in code:
        raise CoderAgentError("Model output does not look like a Gymnasium environment file.")
    return code


async def generate_environment_code(design: EnvironmentDesign) -> tuple[Path, str]:
    """Generate the Gymnasium env file for a design.

    Saves it to backend/generated_envs/{snake_case_env_name}.py and returns
    (file_path, code).
    """
    user_content = (
        "Write the complete Gymnasium environment file for this design:\n\n"
        f"{design.model_dump_json(indent=2)}"
    )
    code = await _generate(SYSTEM_PROMPT, user_content)

    GENERATED_ENVS_DIR.mkdir(parents=True, exist_ok=True)
    file_path = GENERATED_ENVS_DIR / f"{_snake_case(design.environment_name)}.py"
    file_path.write_text(code, encoding="utf-8")
    return file_path, code


async def fix_environment_code(code: str, error: str) -> str:
    """Ask the model to repair a generated env that failed its sanity check."""
    user_content = (
        "This Gymnasium environment file failed its sanity check.\n\n"
        "=== FILE ===\n"
        f"{code}\n"
        "=== FAILURE OUTPUT ===\n"
        f"{error}\n\n"
        "Return the complete corrected file."
    )
    return await _generate(FIX_SYSTEM_PROMPT, user_content)
