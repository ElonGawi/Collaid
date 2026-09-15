import asyncio
import json
import logging
from functools import partial

import anthropic
from pydantic import BaseModel, Field
from typing import Any

from app.agent.tools import TOOL_DEFINITIONS, dispatch_tool
from app.collibra.cache import CollibraCache
from app.data.duckdb_engine import DuckDBEngine

logger = logging.getLogger(__name__)
trace = logging.getLogger("agent.trace")  # writes to dedicated trace file

MAX_ITERATIONS = 20

TOOL_LABELS = {
    "search_business_terms": lambda inp: f"Searching Collibra for '{inp.get('query', '')}'...",
    "get_asset_definition":  lambda inp: "Looking up governed definition...",
    "get_asset_relations":   lambda inp: "Tracing semantic relations...",
    "get_physical_schema":   lambda inp: "Reading physical schema...",
    "execute_sql":           lambda inp: "Running SQL query...",
}


async def _emit(queue, event: dict):
    if queue is not None:
        await queue.put(event)


def _dump(label: str, obj) -> None:
    """Write a labelled JSON dump to the trace log."""
    try:
        text = json.dumps(obj, indent=2, default=str)
    except Exception:
        text = str(obj)
    trace.debug("\n%s\n%s\n%s", "=" * 80, label, text)


class AgentResult(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    answer: str
    tool_calls: list[dict]
    iterations: int
    error: str | None = None
    messages: list[Any] = Field(default_factory=list, exclude=True)


def _summarize_result(result: dict) -> str:
    """Produce a short human-readable summary of a tool result for the trace log."""
    if "error" in result:
        return f"ERROR: {result['error']}"
    if "rows" in result:
        return f"{result['row_count']} rows, columns: {result['columns']}"
    if "results" in result:
        names = [r.get("name", "") for r in result["results"][:5]]
        return f"{result['count']} matches: {names}"
    if "tables" in result:
        tables = list(result["tables"].keys())
        return f"{result['table_count']} tables: {tables}"
    if "definition" in result:
        return result["definition"][:150]
    if "outbound_relations" in result:
        n_out = len(result["outbound_relations"])
        n_in = len(result["inbound_relations"])
        return f"{n_out} outbound, {n_in} inbound relations"
    return str(result)[:200]


class AgentRunner:
    def __init__(
        self,
        anthropic_client: anthropic.Anthropic,
        collibra_cache: CollibraCache,
        duckdb_engine: DuckDBEngine,
        system_prompt: str = "",
    ):
        self.client = anthropic_client
        self.cache = collibra_cache
        self.db = duckdb_engine
        self.system_prompt = system_prompt

    async def run(
        self,
        user_question: str,
        model: str = "claude-sonnet-4-6",
        progress_queue: asyncio.Queue | None = None,
        conversation_history: list[dict] | None = None,
    ) -> AgentResult:
        if conversation_history:
            messages: list[dict] = list(conversation_history)  # shallow copy
            messages.append({"role": "user", "content": user_question})
        else:
            messages: list[dict] = [{"role": "user", "content": user_question}]
        tool_calls_log: list[dict] = []
        final_text = ""
        iterations = 0
        loop = asyncio.get_event_loop()

        trace.debug("\n%s\nNEW QUESTION  model=%s\n%s\nQuestion: %s", "=" * 80, model, "=" * 80, user_question)
        _dump("SYSTEM PROMPT", self.system_prompt)

        try:
            while iterations < MAX_ITERATIONS:
                iterations += 1
                logger.info("Agent iteration %d (model: %s)", iterations, model)

                await _emit(progress_queue, {"type": "thinking", "message": f"Thinking... (step {iterations})"})

                # Serialize messages for the trace (content blocks are SDK objects, not plain dicts)
                serializable_messages = []
                for m in messages:
                    content = m["content"]
                    if isinstance(content, list):
                        serializable_content = []
                        for block in content:
                            if hasattr(block, "model_dump"):
                                serializable_content.append(block.model_dump())
                            elif hasattr(block, "__dict__"):
                                serializable_content.append(vars(block))
                            else:
                                serializable_content.append(block)
                        serializable_messages.append({"role": m["role"], "content": serializable_content})
                    else:
                        serializable_messages.append(m)

                _dump(f"TURN {iterations} — REQUEST (messages sent to Claude)", serializable_messages)

                # Run synchronous Anthropic SDK in thread pool
                create_fn = partial(
                    self.client.messages.create,
                    model=model,
                    max_tokens=4096,
                    system=self.system_prompt,
                    tools=TOOL_DEFINITIONS,
                    messages=messages,
                )
                try:
                    response = await loop.run_in_executor(None, create_fn)
                except Exception as e:
                    logger.error("Anthropic API error: %s", e)
                    trace.debug("API ERROR: %s", e)
                    await _emit(progress_queue, {"type": "error", "message": str(e)})
                    await _emit(progress_queue, None)
                    return AgentResult(
                        answer="",
                        tool_calls=tool_calls_log,
                        iterations=iterations,
                        error=str(e),
                        messages=messages,
                    )

                # Log raw response
                _dump(
                    f"TURN {iterations} — RESPONSE (stop_reason={response.stop_reason})",
                    [b.model_dump() if hasattr(b, "model_dump") else vars(b) for b in response.content],
                )

                # Append assistant turn to conversation
                messages.append({"role": "assistant", "content": response.content})

                if response.stop_reason == "end_turn":
                    for block in response.content:
                        if hasattr(block, "text"):
                            final_text = block.text
                    break

                if response.stop_reason == "tool_use":
                    tool_results = []
                    for block in response.content:
                        if block.type == "tool_use":
                            logger.info("Tool call: %s(%s)", block.name, json.dumps(block.input, default=str)[:200])

                            label_fn = TOOL_LABELS.get(block.name)
                            label = label_fn(block.input) if label_fn else f"Calling {block.name}..."
                            await _emit(progress_queue, {
                                "type": "tool_start",
                                "tool": block.name,
                                "message": label,
                                "input": block.input,
                            })

                            result = await dispatch_tool(
                                block.name,
                                block.input,
                                self.cache,
                                self.db,
                            )
                            summary = _summarize_result(result)
                            logger.info("Tool result: %s", summary)
                            _dump(f"TOOL CALL — {block.name}  input={json.dumps(block.input, default=str)}", result)

                            await _emit(progress_queue, {
                                "type": "tool_done",
                                "tool": block.name,
                                "message": summary,
                                "summary": summary,
                                "input": block.input,
                            })

                            tool_calls_log.append(
                                {
                                    "tool": block.name,
                                    "input": block.input,
                                    "summary": summary,
                                }
                            )
                            tool_results.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": json.dumps(result, default=str),
                                }
                            )
                    messages.append({"role": "user", "content": tool_results})
                else:
                    logger.warning("Unexpected stop_reason: %s", response.stop_reason)
                    break

            if not final_text:
                for block in messages[-1].get("content", []) if messages else []:
                    if hasattr(block, "text"):
                        final_text = block.text
                        break

            trace.debug("\n%s\nFINAL ANSWER (%d iterations)\n%s\n%s", "=" * 80, iterations, "=" * 80, final_text)

            result_obj = AgentResult(
                answer=final_text,
                tool_calls=tool_calls_log,
                iterations=iterations,
                messages=messages,
            )
            await _emit(progress_queue, {
                "type": "done",
                "answer": final_text,
                "tool_calls": tool_calls_log,
                "iterations": iterations,
            })
            await _emit(progress_queue, None)  # sentinel
            return result_obj

        except Exception as e:
            logger.error("Unexpected agent error: %s", e)
            await _emit(progress_queue, {"type": "error", "message": str(e)})
            await _emit(progress_queue, None)
            return AgentResult(
                answer="",
                tool_calls=tool_calls_log,
                iterations=iterations,
                error=str(e),
                messages=messages,
            )
