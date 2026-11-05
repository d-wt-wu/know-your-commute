from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from commute.api import models
from commute.db.connection import database_engine
from commute.db import explorer
from commute.query import InvalidRange, MissingSnapshot, NoData

logger = logging.getLogger(__name__)


def error(status, code, message, details=None):
    body = {"code": code, "message": message}
    if details:
        body["details"] = details
    return JSONResponse(status_code=status, content={"error": body}, headers={"Cache-Control": "no-store"})


def get_engine(request: Request):
    engine = request.app.state.engine
    if engine is None:
        raise HTTPException(503, {"code": "database_unavailable", "message": "Historical data is temporarily unavailable. Try again later."})
    return engine


def create_app(engine=None, web_dir: Path | None = None):
    @asynccontextmanager
    async def lifespan(app):
        owned = engine is None and bool(os.environ.get("DATABASE_URL"))
        app.state.engine = database_engine() if owned else engine
        try:
            yield
        finally:
            if owned:
                app.state.engine.dispose()

    app = FastAPI(title="Know Your Commute API", version="0.2.0",
                  description="Historical reported TTC bus delay records. Counts are not trip-level delay probabilities.", lifespan=lifespan)
    app.state.engine = engine

    @app.middleware("http")
    async def reject_ambiguous_queries(request, call_next):
        if request.url.path.startswith("/api/"):
            keys = [key for key, value in request.query_params.multi_items()]
            if len(keys) != len(set(keys)):
                return error(422, "invalid_filters", "Each query parameter may appear only once.")
        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        details = [{"field": ".".join(str(part) for part in issue["loc"]), "message": issue["msg"]} for issue in exc.errors()]
        return error(422, "invalid_filters", "Check the route, dates and pagination values.", details)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        if isinstance(exc.detail, dict):
            return error(exc.status_code, exc.detail["code"], exc.detail["message"])
        return error(exc.status_code, "not_found" if exc.status_code == 404 else "http_error", str(exc.detail))

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        logger.error("Database query failed (%s)", type(exc).__name__)
        return error(503, "database_unavailable", "Historical data is temporarily unavailable. Try again later.")

    @app.exception_handler(NoData)
    async def no_data(request, exc):
        return error(503, "data_not_loaded", str(exc))

    @app.exception_handler(MissingSnapshot)
    async def missing_snapshot(request, exc):
        return error(404, "snapshot_unavailable", str(exc))

    @app.exception_handler(InvalidRange)
    async def invalid_range(request, exc):
        return error(422, "invalid_filters", str(exc))

    @app.get("/api/v1/health")
    def process_health():
        return {"status": "ok", "service": "Know Your Commute"}

    @app.get("/api/v1/ready")
    def database_ready(db=Depends(get_engine)):
        with db.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ready"}

    @app.get("/api/v1/routes", response_model=models.RoutesResponse)
    def route_list(query: Annotated[models.RoutesQuery, Query()], db=Depends(get_engine)):
        return explorer.routes(db, query.selection(), query.q)

    @app.get("/api/v1/summary", response_model=models.SummaryResponse)
    def summary(query: Annotated[models.FilterQuery, Query()], db=Depends(get_engine)):
        return explorer.summary(db, query.selection())

    @app.get("/api/v1/patterns", response_model=models.PatternsResponse)
    def patterns(query: Annotated[models.FilterQuery, Query()], db=Depends(get_engine)):
        return explorer.patterns(db, query.selection())

    @app.get("/api/v1/records", response_model=models.RecordsResponse)
    def records(query: Annotated[models.RecordsQuery, Query()], db=Depends(get_engine)):
        return explorer.records(db, query.selection(), query.page, query.page_size, query.sort)

    @app.get("/api/v1/data-health", response_model=models.DataHealthResponse)
    def health(db=Depends(get_engine)):
        return explorer.health(db)

    # Optional production build. Vite proxies /api during development. Unknown
    # API/asset paths keep their JSON/404 status, rather than receiving SPA HTML.
    directory = web_dir or Path(os.environ.get("COMMUTE_WEB_DIR", Path(__file__).resolve().parents[3] / "web/dist"))
    if (directory / "index.html").is_file():
        if (directory / "assets").is_dir():
            app.mount("/assets", StaticFiles(directory=directory / "assets"), name="assets")

        @app.get("/favicon.svg", include_in_schema=False)
        def favicon():
            return FileResponse(directory / "favicon.svg")

        @app.get("/", include_in_schema=False)
        @app.get("/data-health", include_in_schema=False)
        @app.get("/about", include_in_schema=False)
        def index():
            return FileResponse(directory / "index.html", headers={"Cache-Control": "no-cache"})

    return app


app = create_app()
