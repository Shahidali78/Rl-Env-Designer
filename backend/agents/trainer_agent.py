"""Trainer Agent — step 4 of the pipeline.

Loads a generated (and already sanity-checked) Gymnasium environment file,
picks SAC or PPO based on the design's action space, trains it with
Stable Baselines3, and produces:

    backend/training/{env_name}/model.zip          trained policy
    backend/training/{env_name}/reward_curve.png   episode reward plot
    backend/training/{env_name}/results.csv        raw Monitor episode data

train_agent() is synchronous and CPU-bound — call it via asyncio.to_thread
from async endpoints. SB3/torch/matplotlib are imported lazily so the rest
of the backend works before the heavy RL stack is installed.
"""

import importlib.util
import inspect
import re
import time
from pathlib import Path

import gymnasium as gym

from schemas import EnvironmentDesign, TrainingResult

TRAINING_DIR = Path(__file__).resolve().parent.parent / "training"

SB3_INSTALL_HINT = (
    "Stable Baselines3 / PyTorch / matplotlib are not installed yet. "
    "From the project root run:  .venv\\Scripts\\pip install -r requirements.txt  "
    "(this downloads PyTorch, which is large — allow a few minutes)."
)


class TrainerAgentError(Exception):
    """Raised when training cannot run or produces no usable results."""


def snake_case(name: str) -> str:
    name = re.sub(r"[^0-9a-zA-Z]+", "", name)
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _load_env_class(file_path: Path) -> type:
    """Import the generated file and return its gymnasium.Env subclass."""
    spec = importlib.util.spec_from_file_location("generated_env", file_path)
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
        raise TrainerAgentError(f"No gymnasium.Env subclass found in {file_path.name}")
    return env_classes[0]


def _plot_reward_curve(df, plot_path: Path, env_name: str, algorithm: str) -> None:
    import matplotlib

    matplotlib.use("Agg")  # headless server — no display
    import matplotlib.pyplot as plt

    steps = df["l"].cumsum()
    window = max(1, min(10, len(df) // 5))
    rolling = df["r"].rolling(window).mean()

    plt.figure(figsize=(8, 4.5))
    plt.plot(steps, df["r"], alpha=0.3, label="episode reward")
    plt.plot(steps, rolling, linewidth=2, label=f"rolling mean (window={window})")
    plt.xlabel("timesteps")
    plt.ylabel("episode reward")
    plt.title(f"{env_name} — {algorithm} training reward")
    plt.legend()
    plt.tight_layout()
    plt.savefig(plot_path, dpi=120)
    plt.close()


def train_agent(
    file_path: Path,
    design: EnvironmentDesign,
    n_timesteps: int = 50_000,
) -> TrainingResult:
    """Train SAC/PPO on the generated env and return metrics + artifact paths."""
    try:
        from stable_baselines3 import PPO, SAC
        from stable_baselines3.common.monitor import Monitor, load_results
    except ImportError as e:
        raise TrainerAgentError(SB3_INSTALL_HINT) from e

    # SAC needs a continuous Box action space; everything else trains with PPO.
    algorithm = "SAC" if design.action_space.gym_space_type == "Box" else "PPO"
    algo_cls = SAC if algorithm == "SAC" else PPO

    env_name = snake_case(design.environment_name)
    run_dir = TRAINING_DIR / env_name
    run_dir.mkdir(parents=True, exist_ok=True)

    env_class = _load_env_class(file_path)
    env = Monitor(env_class(), filename=str(run_dir / "monitor"))

    start = time.monotonic()
    try:
        model = algo_cls("MlpPolicy", env, verbose=0)
        model.learn(total_timesteps=n_timesteps)
    except Exception as e:
        raise TrainerAgentError(f"{algorithm} training failed: {e}") from e
    finally:
        env.close()
    training_time = time.monotonic() - start

    model_path = run_dir / "model.zip"
    model.save(str(model_path))

    df = load_results(str(run_dir))
    if len(df) < 2:
        raise TrainerAgentError(
            f"Only {len(df)} episode(s) completed in {n_timesteps} timesteps — "
            "episode_length is too large to measure learning; raise n_timesteps."
        )

    csv_path = run_dir / "results.csv"
    df.to_csv(csv_path, index=False)

    plot_path = run_dir / "reward_curve.png"
    _plot_reward_curve(df, plot_path, design.environment_name, algorithm)

    # First/last episode windows: early episodes ≈ random-policy baseline.
    rewards = df["r"].to_numpy()
    k = max(1, min(20, len(rewards) // 5))
    mean_initial = float(rewards[:k].mean())
    mean_final = float(rewards[-k:].mean())
    std_final = float(rewards[-k:].std())
    improvement_pct = (
        (mean_final - mean_initial) / abs(mean_initial) * 100.0
        if abs(mean_initial) > 1e-9
        else 0.0
    )

    return TrainingResult(
        env_name=design.environment_name,
        algorithm=algorithm,
        total_timesteps=n_timesteps,
        mean_reward_final=mean_final,
        std_reward_final=std_final,
        mean_reward_initial=mean_initial,
        improvement_pct=improvement_pct,
        model_path=str(model_path),
        plot_path=str(plot_path),
        csv_path=str(csv_path),
        training_time_seconds=training_time,
    )
