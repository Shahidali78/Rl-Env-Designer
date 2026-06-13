"""Provider layer for the LLM agents.

All three model-calling agents (Designer, Coder, Reporter) go through the two
functions here. The provider is chosen per call from the environment:

    LLM_PROVIDER=anthropic | openai      explicit override, else auto-detect:
    ANTHROPIC_API_KEY set (and not the placeholder) -> anthropic (claude-fable-5)
    OPENAI_API_KEY set                              -> openai    (gpt-5)

Keys/models are read at call time (not import time) so a key pasted into .env
after server startup is picked up by the next run.
"""

import os
from typing import TypeVar

from pydantic import BaseModel

_PLACEHOLDER = "PASTE-YOUR-KEY-HERE"

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Provider-agnostic failure raised toward the agent layer."""


def provider() -> str:
    explicit = os.getenv("LLM_PROVIDER", "").strip().lower()
    if explicit in ("anthropic", "openai"):
        return explicit
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    if anthropic_key and anthropic_key != _PLACEHOLDER:
        return "anthropic"
    if os.getenv("OPENAI_API_KEY", ""):
        return "openai"
    return "anthropic"  # default — produces a clear auth error if no key at all


def active_model() -> str:
    if provider() == "openai":
        return os.getenv("OPENAI_MODEL", "gpt-5")
    return os.getenv("ANTHROPIC_MODEL", "claude-fable-5")


# ---------------------------------------------------------------------------
# Structured output (Designer Agent)
# ---------------------------------------------------------------------------

async def generate_structured(system: str, user: str, schema: type[T]) -> tuple[T, dict]:
    """One model call constrained to `schema`. Returns (parsed, usage)."""
    if provider() == "openai":
        return await _openai_structured(system, user, schema)
    return await _anthropic_structured(system, user, schema)


async def _anthropic_structured(system: str, user: str, schema: type[T]) -> tuple[T, dict]:
    import anthropic
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic()
    try:
        response = await client.messages.parse(
            model=active_model(),
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=schema,
        )
    except anthropic.RateLimitError as e:
        raise LLMError(f"Rate limited by the Anthropic API: {e.message}") from e
    except anthropic.APIStatusError as e:
        raise LLMError(f"Anthropic API error ({e.status_code}): {e.message}") from e

    if response.stop_reason == "refusal":
        raise LLMError("The model refused this request.")
    if response.stop_reason == "max_tokens":
        raise LLMError("Output was truncated (max_tokens reached).")
    if response.parsed_output is None:
        raise LLMError("The model response did not match the expected schema.")
    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }
    return response.parsed_output, usage


async def _openai_structured(system: str, user: str, schema: type[T]) -> tuple[T, dict]:
    import openai
    from openai import AsyncOpenAI

    client = AsyncOpenAI()
    try:
        response = await client.responses.parse(
            model=active_model(),
            instructions=system,
            input=user,
            text_format=schema,
            max_output_tokens=16000,
        )
    except openai.RateLimitError as e:
        raise LLMError(f"Rate limited by the OpenAI API: {e}") from e
    except openai.APIStatusError as e:
        raise LLMError(f"OpenAI API error ({e.status_code}): {e.message}") from e

    if response.output_parsed is None:
        raise LLMError(
            "The model response did not match the expected schema"
            + (f" (status: {response.status})" if response.status != "completed" else "")
            + "."
        )
    usage = {
        "input_tokens": response.usage.input_tokens if response.usage else 0,
        "output_tokens": response.usage.output_tokens if response.usage else 0,
    }
    return response.output_parsed, usage


# ---------------------------------------------------------------------------
# Plain text output (Coder + Reporter Agents)
# ---------------------------------------------------------------------------

async def generate_text(system: str, user: str, max_tokens: int = 32000) -> str:
    """One model call returning plain text (code or markdown)."""
    if provider() == "openai":
        return await _openai_text(system, user, max_tokens)
    return await _anthropic_text(system, user, max_tokens)


async def _anthropic_text(system: str, user: str, max_tokens: int) -> str:
    import anthropic
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic()
    try:
        # Stream to avoid HTTP timeouts on long generations.
        async with client.messages.stream(
            model=active_model(),
            max_tokens=max_tokens,
            thinking={"type": "adaptive"},
            system=system,
            messages=[{"role": "user", "content": user}],
        ) as stream:
            message = await stream.get_final_message()
    except anthropic.RateLimitError as e:
        raise LLMError(f"Rate limited by the Anthropic API: {e.message}") from e
    except anthropic.APIStatusError as e:
        raise LLMError(f"Anthropic API error ({e.status_code}): {e.message}") from e

    if message.stop_reason == "refusal":
        raise LLMError("The model refused this request.")
    if message.stop_reason == "max_tokens":
        raise LLMError("Output was truncated (max_tokens reached).")
    return "".join(block.text for block in message.content if block.type == "text")


async def _openai_text(system: str, user: str, max_tokens: int) -> str:
    import openai
    from openai import AsyncOpenAI

    client = AsyncOpenAI()
    try:
        response = await client.responses.create(
            model=active_model(),
            instructions=system,
            input=user,
            max_output_tokens=max_tokens,
        )
    except openai.RateLimitError as e:
        raise LLMError(f"Rate limited by the OpenAI API: {e}") from e
    except openai.APIStatusError as e:
        raise LLMError(f"OpenAI API error ({e.status_code}): {e.message}") from e

    if response.status == "incomplete":
        raise LLMError("Output was truncated (max_output_tokens reached).")
    if not response.output_text:
        raise LLMError("The model returned no text.")
    return response.output_text
