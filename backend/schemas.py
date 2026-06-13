"""Pydantic models shared across the agent pipeline.

EnvironmentDesign is the structured-output contract for the Designer Agent:
the Anthropic API constrains the model's response to this schema, so the
Coder Agent downstream can rely on every field being present and typed.

Note: structured outputs reject numeric constraints (ge/le/min_length etc.),
so validation here is type-and-enum only.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Environment design (Designer Agent output)
# ---------------------------------------------------------------------------

class StateVariable(BaseModel):
    name: str = Field(description="Identifier for this observation variable, snake_case")
    description: str = Field(description="What this variable represents in the real-world problem")
    type: Literal["continuous", "discrete", "binary"] = Field(
        description="continuous -> Box dimension, discrete -> integer-valued, binary -> 0/1"
    )
    low: Optional[float] = Field(default=None, description="Lower bound (continuous/discrete)")
    high: Optional[float] = Field(default=None, description="Upper bound (continuous/discrete)")


class StateSpace(BaseModel):
    gym_space_type: Literal["Box", "Discrete", "MultiDiscrete", "MultiBinary"] = Field(
        description="Gymnasium space class for the observation space"
    )
    variables: list[StateVariable] = Field(
        description="Every variable in the observation vector, in order"
    )
    description: str = Field(description="One-paragraph summary of what the agent observes")


class ActionVariable(BaseModel):
    name: str = Field(description="Identifier for this action dimension, snake_case")
    description: str = Field(description="What taking this action means in the real-world problem")
    type: Literal["continuous", "discrete", "binary"] = Field(
        description="continuous -> Box dimension, discrete -> integer choice, binary -> 0/1"
    )
    low: Optional[float] = Field(default=None, description="Lower bound (continuous)")
    high: Optional[float] = Field(default=None, description="Upper bound (continuous)")
    num_options: Optional[int] = Field(
        default=None, description="Number of choices when type is discrete"
    )


class ActionSpace(BaseModel):
    gym_space_type: Literal["Box", "Discrete", "MultiDiscrete", "MultiBinary"] = Field(
        description="Gymnasium space class for the action space"
    )
    variables: list[ActionVariable] = Field(
        description="Every dimension of the action, in order"
    )
    description: str = Field(description="One-paragraph summary of what the agent controls")


class RewardComponent(BaseModel):
    name: str = Field(description="Identifier for this reward term, snake_case")
    formula: str = Field(
        description="How this term is computed, as a short Python-like expression "
        "over state/action variable names, e.g. '-0.1 * abs(staffing_gap)'"
    )
    weight: float = Field(description="Multiplier applied to this term in the total reward")
    rationale: str = Field(description="Why this term exists and what behavior it incentivizes")


class RewardFunction(BaseModel):
    components: list[RewardComponent] = Field(
        description="Additive terms; total reward is the weighted sum of all components"
    )
    description: str = Field(description="Plain-English summary of the overall reward signal")


class EnvironmentDesign(BaseModel):
    environment_name: str = Field(
        description="PascalCase class name for the env, ending in 'Env', e.g. 'HospitalShiftEnv'"
    )
    problem_summary: str = Field(
        description="Restatement of the user's problem as an RL task in 2-3 sentences"
    )
    state_space: StateSpace
    action_space: ActionSpace
    reward_function: RewardFunction
    episode_length: int = Field(
        description="Maximum number of steps per episode before truncation"
    )
    termination_conditions: list[str] = Field(
        description="Conditions (beyond max steps) under which an episode ends early"
    )
    recommended_algorithm: Literal["SAC", "PPO"] = Field(
        description="SAC only if the action space is a continuous Box; otherwise PPO"
    )
    design_rationale: str = Field(
        description="Explanation of the key design decisions: why this state/action "
        "factorization, why this reward shaping, expected failure modes"
    )


# ---------------------------------------------------------------------------
# API request/response models
# ---------------------------------------------------------------------------

class DesignRequest(BaseModel):
    problem_description: str = Field(
        description="Plain-English description of the real-world optimization problem"
    )


class DesignResponse(BaseModel):
    design: EnvironmentDesign
    model: str
    usage: dict


class CodeResponse(BaseModel):
    file_path: str
    code: str


class ExecuteRequest(BaseModel):
    file_path: str = Field(
        description="Path to a generated env file (must live in backend/generated_envs)"
    )


class TrainingResult(BaseModel):
    env_name: str
    algorithm: Literal["SAC", "PPO"]
    total_timesteps: int
    mean_reward_final: float = Field(description="Mean episode reward over the last episodes")
    std_reward_final: float
    mean_reward_initial: float = Field(
        description="Mean episode reward over the first episodes (≈ random-policy baseline)"
    )
    improvement_pct: float = Field(
        description="Percent improvement of final mean reward over the initial baseline"
    )
    model_path: str
    plot_path: str
    csv_path: str
    training_time_seconds: float


class TrainRequest(BaseModel):
    file_path: str
    design: EnvironmentDesign
    n_timesteps: int = Field(default=50_000, description="Training budget in env steps")


class ReportRequest(BaseModel):
    design: EnvironmentDesign
    training_result: TrainingResult


class ReportResponse(BaseModel):
    report_md: str
    report_path: str


class PipelineRequest(BaseModel):
    problem_description: str
    n_timesteps: int = Field(default=50_000, description="Training budget in env steps")


class ExecuteResponse(BaseModel):
    success: bool
    error: Optional[str] = None
    output: str
    fix_attempts: int = Field(description="How many auto-fix rounds were used (0-2)")
    file_path: str
    code: str = Field(description="Final file contents (may differ from input after auto-fix)")
