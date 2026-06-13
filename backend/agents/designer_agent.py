"""Designer Agent — step 1 of the pipeline.

Takes a plain-English description of a real-world optimization problem and
returns a structured EnvironmentDesign (state space, action space, reward
function, episode logic, rationale) ready for the Coder Agent to turn into
a runnable Gymnasium environment.

Uses claude-fable-5 with adaptive thinking and structured outputs, so the
response is guaranteed to parse into the EnvironmentDesign schema.
"""

from llm import LLMError, generate_structured
from schemas import EnvironmentDesign

SYSTEM_PROMPT = """\
You are an expert reinforcement learning environment designer. You translate \
real-world optimization problems described in plain English into precise, \
trainable Gymnasium environment specifications.

Design principles you must follow:

1. State space: include only variables the decision-maker could plausibly \
observe, normalized to sensible bounds. Every variable needs explicit low/high \
bounds when continuous. Keep the observation vector compact — under ~30 \
dimensions unless the problem genuinely demands more.

2. Action space: model the actual decision lever in the problem. Prefer a \
continuous Box action space when the underlying decision is naturally \
continuous (quantities, rates, allocations); use Discrete/MultiDiscrete for \
genuinely categorical choices. Stable Baselines3 constraint: SAC requires a \
continuous Box action space; PPO handles both. Set recommended_algorithm \
accordingly — never recommend SAC for a discrete action space.

3. Reward function: decompose into named additive components, each with a \
formula written over the state/action variable names you defined, a weight, \
and a rationale. Reward scales should keep the per-step total roughly in \
[-10, 10]. Penalize constraint violations rather than hard-blocking them, \
and avoid reward terms that can be trivially gamed.

4. Episode logic: pick an episode_length that matches the natural planning \
horizon of the problem (e.g. a week of shifts, a trading day). List early \
termination_conditions only for genuinely terminal states (catastrophic \
failure, problem solved), not soft constraint violations.

5. Everything must be simulatable: do not reference data sources or real-time \
feeds that a self-contained Python environment cannot generate. Assume the \
environment will synthesize its own dynamics (demand arrivals, failures, \
prices) with randomness seeded via Gymnasium's reset(seed=...).

Be concrete and quantitative. The design will be handed directly to a code \
generator, so vague variables ("various factors") or unspecified bounds are \
design failures.
"""


class DesignerAgentError(Exception):
    """Raised when the Designer Agent cannot produce a valid design."""


async def design_environment(problem_description: str) -> tuple[EnvironmentDesign, dict]:
    """Run the Designer Agent on a problem description.

    Returns the validated EnvironmentDesign plus a usage dict for logging.
    Raises DesignerAgentError on refusal, truncation, or API failure.
    """
    user_content = (
        "Design a Gymnasium reinforcement learning environment for "
        "the following real-world optimization problem:\n\n"
        f"{problem_description}"
    )
    try:
        return await generate_structured(SYSTEM_PROMPT, user_content, EnvironmentDesign)
    except LLMError as e:
        raise DesignerAgentError(str(e)) from e
