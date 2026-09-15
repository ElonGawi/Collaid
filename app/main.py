import io
import logging
import logging.handlers
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime

import anthropic
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.agent.runner import AgentRunner
from app.api.routes import router
from app.collibra.cache import CollibraCache
from app.collibra.client import CollibraClient
from app.config import settings
from app.data.delta_loader import load_all_tables
from app.data.duckdb_engine import DuckDBEngine


def _setup_logging():
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    # Console handler — UTF-8 safe for Windows
    utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    console_handler = logging.StreamHandler(utf8_stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(fmt))

    # File handler — rotating, 10 MB per file, keep last 5
    os.makedirs("logs", exist_ok=True)
    log_path = os.path.join("logs", "app.log")
    file_handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)  # always capture DEBUG to file
    file_handler.setFormatter(logging.Formatter(fmt))

    # Dedicated agent trace file — one file per server run, full prompt/response dumps
    session_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    trace_path = os.path.join("logs", f"agent_trace_{session_ts}.log")
    trace_handler = logging.FileHandler(trace_path, encoding="utf-8")
    trace_handler.setLevel(logging.DEBUG)
    trace_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))

    # Root logger
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(console_handler)
    root.addHandler(file_handler)

    # Agent trace logger — only used in runner.py for full prompt dumps
    trace_logger = logging.getLogger("agent.trace")
    trace_logger.addHandler(trace_handler)
    trace_logger.propagate = False  # don't also write trace dumps to console/app.log

    # Silence noisy third-party loggers on console (still captured in file)
    for noisy in ("httpx", "httpcore", "urllib3", "delta_sharing"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    print(f"Logging to: {os.path.abspath(log_path)}", flush=True)
    print(f"Agent trace: {os.path.abspath(trace_path)}", flush=True)


_setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── STARTUP ──────────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("Starting Ask Your Data Product")
    logger.info("=" * 60)

    # 1. Build Collibra cache
    logger.info("Step 1/3: Building Collibra semantic cache (this takes ~60-90s)...")
    collibra_client = CollibraClient()
    cache = CollibraCache()
    try:
        await cache.build(collibra_client)
    finally:
        await collibra_client.close()
    logger.info(
        "Collibra cache ready: %d assets, %d relations, %d tables in physical schema",
        len(cache.assets),
        len(cache.relations),
        len(cache.physical_schema),
    )

    # 2. Load Delta Sharing tables
    logger.info("Step 2/3: Loading Delta Sharing tables from Databricks...")
    tables = await load_all_tables(settings.delta_sharing_config_path, settings.delta_sharing_limit)
    engine = DuckDBEngine()
    engine.setup(tables)
    logger.info("DuckDB ready with %d tables", len(engine.table_names))

    # 3. Initialize Claude agent
    logger.info("Step 3/3: Initializing Claude agent...")
    from app.agent.system_prompt import build_system_prompt
    system_prompt = build_system_prompt(cache)
    logger.info("System prompt built: %d characters", len(system_prompt))
    anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    runner = AgentRunner(anthropic_client, cache, engine, system_prompt=system_prompt)

    # Attach to app state
    app.state.collibra_cache = cache
    app.state.duckdb_engine = engine
    app.state.agent_runner = runner
    app.state.sessions = {}   # session_id -> list[dict]  (in-memory chat history)

    logger.info("=" * 60)
    logger.info("Ready! Open http://localhost:8000")
    logger.info("=" * 60)

    yield

    # ── SHUTDOWN ─────────────────────────────────────────────────────────────
    logger.info("Shutting down.")


app = FastAPI(title="Ask Your Data", version="1.0.0", lifespan=lifespan)
app.include_router(router, prefix="/api")

# Serve the single-page frontend at /
app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
