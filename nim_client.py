"""
Thin wrapper around the NVIDIA NIM OpenAI-compatible endpoint that runs one
agent's turn to completion: send messages -> if the model calls tools,
execute them locally and feed results back -> repeat until the model
answers with plain text (or we hit max_tool_iters, as a runaway guard).

NIM base URL and auth: https://integrate.api.nvidia.com/v1, key from
NVIDIA_API_KEY. Tool-calling support and quality vary by model — pick one
documented to support function calling well (e.g. meta/llama-3.3-70b-instruct
or meta/llama-3.1-70b-instruct). Verify against the current model catalog
at build.nvidia.com before relying on it; NVIDIA adds/deprecates models
regularly.
"""
from __future__ import annotations

import json
import os

from openai import OpenAI

NIM_BASE_URL = os.environ.get("NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")


def get_client() -> OpenAI:
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Set NVIDIA_API_KEY in your environment (or .env) — get one at "
            "https://build.nvidia.com by opening any model card and clicking "
            "'Get API Key'."
        )
    return OpenAI(base_url=NIM_BASE_URL, api_key=api_key)


def run_agent_turn(
    client: OpenAI,
    model: str,
    system_prompt: str,
    user_message: str,
    tool_schemas: list[dict],
    tool_impls: dict,
    max_tool_iters: int = 12,
    temperature: float = 0.2,
    verbose: bool = True,
) -> tuple[str, list[dict]]:
    """Runs one agent (fresh context) to completion. Returns (final_text,
    full_message_history) — the history is useful for logging/debugging,
    not for continuing the conversation (each spawn is meant to start fresh,
    same as a real Claude Code subagent)."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    for _ in range(max_tool_iters):
        kwargs = dict(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        if tool_schemas:
            kwargs["tools"] = tool_schemas
            kwargs["tool_choice"] = "auto"

        # Retry with exponential backoff on rate-limit (429) errors
        response = None
        for attempt in range(5):
            try:
                response = client.chat.completions.create(**kwargs)
                break
            except Exception as e:
                if "429" in str(e) and attempt < 4:
                    wait = 15 * (attempt + 1)
                    if verbose:
                        print(f"    [rate-limit] 429 — waiting {wait}s before retry {attempt + 1}/5...")
                    import time
                    time.sleep(wait)
                else:
                    raise
        if response is None:
            raise RuntimeError("Failed to get response after 5 retries")
        choice = response.choices[0]
        msg = choice.message

        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                **(
                    {"tool_calls": [tc.model_dump() for tc in msg.tool_calls]}
                    if msg.tool_calls
                    else {}
                ),
            }
        )

        if not msg.tool_calls:
            return msg.content or "", messages

        for tc in msg.tool_calls:
            fn_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            if verbose:
                print(f"    [tool] {fn_name}({args})")

            impl = tool_impls.get(fn_name)
            if impl is None:
                result = f"ERROR: tool '{fn_name}' is not available to this agent"
            else:
                try:
                    result = impl(**args)
                except Exception as e:  # noqa: BLE001 — surface any tool error to the model
                    result = f"ERROR running {fn_name}: {e}"

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": str(result)[:8000],
                }
            )

    return (
        "ERROR: hit max_tool_iters without a final answer — the agent may be "
        "stuck in a tool-call loop.",
        messages,
    )
