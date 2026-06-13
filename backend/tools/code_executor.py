"""Code Executor — step 3 of the pipeline.

Runs a generated Gymnasium environment file in an isolated subprocess and
sanity-checks it: import the module, find the gymnasium.Env subclass,
reset(seed=42), take 3 random steps, and assert the step contract
(5-tuple, observations inside the declared observation space).

If the check fails, the failure output is sent back to claude-fable-5
(via the Coder Agent's fix call) and the file is rewritten — up to
MAX_FIX_ATTEMPTS times.
"""

import asyncio
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from agents.coder_agent import GENERATED_ENVS_DIR, fix_environment_code

MAX_FIX_ATTEMPTS = 2
SANITY_CHECK_TIMEOUT_SECONDS = 120

# Runs inside the subprocess. Plain string — no f-string, so braces are safe.
_DRIVER = """
import importlib.util
import inspect
import sys

import gymnasium as gym

path = sys.argv[1]
spec = importlib.util.spec_from_file_location("generated_env", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

env_classes = [
    obj
    for obj in vars(module).values()
    if inspect.isclass(obj)
    and issubclass(obj, gym.Env)
    and obj.__module__ == "generated_env"
]
if not env_classes:
    raise RuntimeError("No gymnasium.Env subclass found in the file")

env = env_classes[0]()
print(f"instantiated {env_classes[0].__name__}")

obs, info = env.reset(seed=42)
assert env.observation_space.contains(obs), (
    f"reset() returned an observation outside observation_space: {obs!r}"
)
print(f"reset OK: obs={obs!r}")

for i in range(3):
    action = env.action_space.sample()
    result = env.step(action)
    assert isinstance(result, tuple) and len(result) == 5, (
        f"step() must return a 5-tuple (obs, reward, terminated, truncated, info), got {result!r}"
    )
    obs, reward, terminated, truncated, step_info = result
    assert env.observation_space.contains(obs), (
        f"step() returned an observation outside observation_space: {obs!r}"
    )
    reward = float(reward)
    print(f"step {i}: reward={reward:.4f} terminated={terminated} truncated={truncated}")
    if terminated or truncated:
        obs, info = env.reset()

env.render()
env.close()

# Stable Baselines3 resets WITHOUT a seed — a fresh instance must work that way
# too (catches envs whose RNG only exists when a seed is provided).
env2 = env_classes[0]()
obs, info = env2.reset()
assert env2.observation_space.contains(obs), (
    f"reset() WITHOUT a seed returned an observation outside observation_space: {obs!r}"
)
result = env2.step(env2.action_space.sample())
assert isinstance(result, tuple) and len(result) == 5, (
    "step() after an unseeded reset() must still return a 5-tuple"
)
assert env2.observation_space.contains(result[0]), (
    "step() after an unseeded reset() returned an observation outside observation_space"
)
env2.close()
print("unseeded reset/step OK")
print("SANITY CHECK PASSED")
"""


@dataclass
class ExecutionResult:
    success: bool
    error: Optional[str]
    output: str


def run_sanity_check(file_path: Path) -> ExecutionResult:
    """Run the generated env file's sanity check in a subprocess (blocking)."""
    try:
        proc = subprocess.run(
            [sys.executable, "-c", _DRIVER, str(file_path)],
            capture_output=True,
            text=True,
            timeout=SANITY_CHECK_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return ExecutionResult(
            success=False,
            error=f"Sanity check timed out after {SANITY_CHECK_TIMEOUT_SECONDS}s "
            "(likely an infinite loop in reset() or step()).",
            output="",
        )

    if proc.returncode == 0:
        return ExecutionResult(success=True, error=None, output=proc.stdout)

    error = proc.stderr.strip() or proc.stdout.strip() or f"exit code {proc.returncode}"
    return ExecutionResult(success=False, error=error, output=proc.stdout)


def validate_generated_path(file_path: str) -> Path:
    """Resolve a user-supplied path and require it to be a .py file inside
    backend/generated_envs (rejects path traversal and arbitrary execution)."""
    path = Path(file_path)
    if not path.is_absolute():
        path = GENERATED_ENVS_DIR / path.name
    path = path.resolve()
    if path.parent != GENERATED_ENVS_DIR.resolve() or path.suffix != ".py":
        raise ValueError("file_path must point to a .py file inside backend/generated_envs")
    if not path.exists():
        raise FileNotFoundError(f"No such generated env file: {path.name}")
    return path


async def execute_with_autofix(file_path: Path) -> tuple[ExecutionResult, int]:
    """Sanity-check the env; on failure, ask the model to fix it (max 2 rounds).

    Each fix overwrites the file in place. Returns (final result, fix rounds used).
    """
    result = await asyncio.to_thread(run_sanity_check, file_path)

    attempts = 0
    while not result.success and attempts < MAX_FIX_ATTEMPTS:
        attempts += 1
        code = file_path.read_text(encoding="utf-8")
        fixed_code = await fix_environment_code(code, result.error or "unknown failure")
        file_path.write_text(fixed_code, encoding="utf-8")
        result = await asyncio.to_thread(run_sanity_check, file_path)

    return result, attempts
