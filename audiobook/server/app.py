"""FastAPI app factory for the SPA-serving API server (no NiceGUI)."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .routers import chapters, config, jobs, media, series, speakers, system
from .spa import mount_spa


def create_app(runner):
    """Build the FastAPI app around an existing PipelineRunner."""

    @asynccontextmanager
    async def lifespan(app):
        yield
        # Drain the queue, unload the TTS model, reset stale processing rows.
        runner.shutdown()

    app = FastAPI(title='Audiobook Pipeline', lifespan=lifespan,
                  docs_url='/api/docs', openapi_url='/api/openapi.json')
    app.state.runner = runner

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        # pipeline.py raises ValueError for user-facing errors
        # (e.g. "Cannot rescrape a local series")
        return JSONResponse(status_code=400, content={'detail': str(exc)})

    for r in (system, jobs, series, chapters, speakers, config, media):
        app.include_router(r.router)

    mount_spa(app)  # must be last: catch-all static mount at /
    return app
