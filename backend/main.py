"""FastAPI backend for the RL Environment Auto-Designer.

Run from the backend/ directory:
    uvicorn main:app --reload
"""

import asyncio
import json
import os

from dotenv import load_dotenv

load_dotenv()  # must run before agent modules read env vars

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

import llm
from agents.coder_agent import (
    CoderAgentError,
    fix_environment_code,
    generate_environment_code,
)
from agents.trainer_agent import TRAINING_DIR
from agents.designer_agent import DesignerAgentError, design_environment
from agents.reporter_agent import ReporterAgentError, generate_report
from agents.trainer_agent import TrainerAgentError, train_agent
from schemas import (
    CodeResponse,
    DesignRequest,
    DesignResponse,
    EnvironmentDesign,
    ExecuteRequest,
    ExecuteResponse,
    PipelineRequest,
    ReportRequest,
    ReportResponse,
    TrainingResult,
    TrainRequest,
)
from tools.code_executor import execute_with_autofix, validate_generated_path

app = FastAPI(
    title="RL Environment Auto-Designer",
    description="Agentic pipeline that turns plain-English optimization problems "
    "into trained RL environments.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")],
    # Next.js dev auto-increments its port when 3000 is busy, so also allow
    # any localhost origin during local development.
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Serve training artifacts (reward_curve.png etc.) to the frontend:
#   GET /artifacts/{env_dir}/reward_curve.png
TRAINING_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/artifacts", StaticFiles(directory=TRAINING_DIR), name="artifacts")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


def _refresh_env() -> None:
    """Re-read .env before agent calls so an API key pasted after server
    startup is picked up without a restart (the SDK reads the key from the
    environment when each client is constructed)."""
    load_dotenv(override=True)


@app.post("/design", response_model=DesignResponse)
async def create_design(request: DesignRequest) -> DesignResponse:
    _refresh_env()
    """Step 1 of the pipeline: turn a plain-English problem into a structured
    Gymnasium environment design."""
    if not request.problem_description.strip():
        raise HTTPException(status_code=422, detail="problem_description must not be empty")

    try:
        design, usage = await design_environment(request.problem_description)
    except DesignerAgentError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return DesignResponse(design=design, model=llm.active_model(), usage=usage)


@app.post("/code", response_model=CodeResponse)
async def create_code(design: EnvironmentDesign) -> CodeResponse:
    """Step 2 of the pipeline: turn an EnvironmentDesign into a runnable
    Gymnasium environment file under backend/generated_envs/."""
    _refresh_env()
    try:
        file_path, code = await generate_environment_code(design)
    except CoderAgentError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return CodeResponse(file_path=str(file_path), code=code)


@app.post("/execute", response_model=ExecuteResponse)
async def execute_code(request: ExecuteRequest) -> ExecuteResponse:
    """Step 3 of the pipeline: sanity-check a generated env (reset + 3 random
    steps in a subprocess), auto-fixing failures with the model up to 2 times."""
    _refresh_env()
    try:
        file_path = validate_generated_path(request.file_path)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    try:
        result, fix_attempts = await execute_with_autofix(file_path)
    except CoderAgentError as e:
        raise HTTPException(status_code=502, detail=f"Auto-fix failed: {e}") from e

    return ExecuteResponse(
        success=result.success,
        error=result.error,
        output=result.output,
        fix_attempts=fix_attempts,
        file_path=str(file_path),
        code=file_path.read_text(encoding="utf-8"),
    )


@app.post("/train", response_model=TrainingResult)
async def train(request: TrainRequest) -> TrainingResult:
    """Step 4 of the pipeline: train SAC/PPO on the generated env with SB3
    and save model + reward curve + results CSV under backend/training/."""
    try:
        file_path = validate_generated_path(request.file_path)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    try:
        # Blocking, CPU-bound — keep the event loop free.
        return await asyncio.to_thread(
            train_agent, file_path, request.design, request.n_timesteps
        )
    except TrainerAgentError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/report", response_model=ReportResponse)
async def report(request: ReportRequest) -> ReportResponse:
    """Step 5 of the pipeline: write the markdown training report."""
    _refresh_env()
    try:
        report_md, report_path = await generate_report(
            request.design, request.training_result
        )
    except ReporterAgentError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return ReportResponse(report_md=report_md, report_path=str(report_path))


@app.post("/run-pipeline")
async def run_pipeline(request: PipelineRequest) -> StreamingResponse:
    """Run all 5 stages sequentially, streaming NDJSON progress events:

        {"stage": "designing", "status": "in_progress", "message": "..."}
        {"stage": "designing", "status": "complete", "data": {...}}
        ...
        {"stage": "pipeline", "status": "complete"}
    """

    def event(stage: str, status: str, message: str | None = None, data=None) -> str:
        payload: dict = {"stage": stage, "status": status}
        if message is not None:
            payload["message"] = message
        if data is not None:
            payload["data"] = data
        return json.dumps(payload) + "\n"

    _refresh_env()

    async def stream():
        stage = "designing"
        try:
            yield event(stage, "in_progress", "Analyzing the problem and designing the environment...")
            design, _usage = await design_environment(request.problem_description)
            yield event(stage, "complete", data=design.model_dump())

            stage = "coding"
            yield event(stage, "in_progress", "Generating the Gymnasium environment file...")
            file_path, code = await generate_environment_code(design)
            yield event(stage, "complete", data={"file_path": str(file_path), "code": code})

            stage = "executing"
            yield event(stage, "in_progress", "Sanity-checking the environment (auto-fix enabled)...")
            result, fix_attempts = await execute_with_autofix(file_path)
            if not result.success:
                yield event(
                    stage,
                    "error",
                    message=f"Environment failed its sanity check after "
                    f"{fix_attempts} fix attempt(s): {result.error}",
                    data={"fix_attempts": fix_attempts, "output": result.output},
                )
                return
            yield event(stage, "complete", data={"output": result.output, "fix_attempts": fix_attempts})

            stage = "training"
            yield event(
                stage,
                "in_progress",
                f"Training with Stable Baselines3 for {request.n_timesteps} timesteps "
                "(this is the slow part)...",
            )
            try:
                training_result = await asyncio.to_thread(
                    train_agent, file_path, design, request.n_timesteps
                )
            except TrainerAgentError as first_error:
                # The env can crash under real training in ways the sanity
                # check can't fully cover — give the model one shot at fixing
                # it, re-validate, and retrain.
                yield event(
                    stage,
                    "in_progress",
                    f"Training crashed ({first_error}) — asking the model to fix "
                    "the environment and retrying...",
                )
                code = file_path.read_text(encoding="utf-8")
                fixed = await fix_environment_code(code, str(first_error))
                file_path.write_text(fixed, encoding="utf-8")
                recheck, _ = await execute_with_autofix(file_path)
                if not recheck.success:
                    raise TrainerAgentError(
                        f"Training failed ({first_error}) and the fixed environment "
                        f"did not pass re-validation: {recheck.error}"
                    ) from first_error
                training_result = await asyncio.to_thread(
                    train_agent, file_path, design, request.n_timesteps
                )
            yield event(stage, "complete", data=training_result.model_dump())

            stage = "reporting"
            yield event(stage, "in_progress", "Writing the training report...")
            report_md, report_path = await generate_report(design, training_result)
            yield event(stage, "complete", data={"report_md": report_md, "report_path": str(report_path)})

            yield event("pipeline", "complete", message="All 5 stages finished.")
        except (DesignerAgentError, CoderAgentError, TrainerAgentError, ReporterAgentError) as e:
            yield event(stage, "error", message=str(e))
        except Exception as e:  # never let the stream die silently
            yield event(stage, "error", message=f"Unexpected error: {e}")

    return StreamingResponse(stream(), media_type="application/x-ndjson")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=os.getenv("BACKEND_HOST", "127.0.0.1"),
        port=int(os.getenv("BACKEND_PORT", "8000")),
        reload=True,
    )
