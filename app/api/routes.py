import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent.runner import AgentResult, AgentRunner

logger = logging.getLogger(__name__)
router = APIRouter()


ALLOWED_MODELS = {
    "claude-sonnet-4-6",
    "claude-opus-4-6",
    "claude-haiku-4-5-20251001",
}


class AskRequest(BaseModel):
    question: str
    model: str = "claude-sonnet-4-6"
    session_id: str | None = None


class AskResponse(BaseModel):
    answer: str
    tool_calls: list[dict]
    iterations: int
    error: str | None = None


@router.post("/ask", response_model=AskResponse)
async def ask(body: AskRequest, request: Request) -> AskResponse:
    runner: AgentRunner = request.app.state.agent_runner
    model = body.model if body.model in ALLOWED_MODELS else "claude-sonnet-4-6"
    logger.info("Question received [%s]: %s", model, body.question[:100])
    result: AgentResult = await runner.run(body.question, model=model)
    return AskResponse(
        answer=result.answer,
        tool_calls=result.tool_calls,
        iterations=result.iterations,
        error=result.error,
    )


@router.post("/ask/stream")
async def ask_stream(body: AskRequest, request: Request):
    runner: AgentRunner = request.app.state.agent_runner
    model = body.model if body.model in ALLOWED_MODELS else "claude-sonnet-4-6"
    logger.info("Stream question received [%s]: %s", model, body.question[:100])

    # Session management
    sessions = request.app.state.sessions
    session_id = body.session_id if body.session_id and body.session_id in sessions else str(uuid.uuid4())
    history = list(sessions.get(session_id, []))  # copy existing history (may be empty)

    queue: asyncio.Queue = asyncio.Queue()
    result_holder: dict = {}

    async def run_agent():
        result = await runner.run(
            body.question,
            model=model,
            progress_queue=queue,
            conversation_history=history if history else None,
        )
        result_holder["messages"] = result.messages

    asyncio.create_task(run_agent())

    async def event_generator():
        while True:
            event = await queue.get()
            if event is None:  # sentinel — agent finished
                # Persist updated conversation history
                if "messages" in result_holder:
                    sessions[session_id] = result_holder["messages"]
                break
            if event.get("type") == "done":
                event["session_id"] = session_id
            yield f"data: {json.dumps(event, default=str)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/health")
async def health(request: Request) -> dict:
    cache = request.app.state.collibra_cache
    engine = request.app.state.duckdb_engine
    return {
        "status": "ok",
        "collibra_assets_cached": len(cache.assets),
        "collibra_relations_cached": len(cache.relations),
        "tables_loaded": engine.table_names,
    }
