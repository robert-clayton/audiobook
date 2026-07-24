"""FastAPI dependencies and shared request-scope helpers."""

from contextlib import contextmanager

from fastapi import HTTPException, Request


def get_runner(request: Request):
    """Return the PipelineRunner attached to the app at startup."""
    return request.app.state.runner


@contextmanager
def open_db(runner):
    """Yield a fresh ChapterDB, closing it afterwards.

    The DB is SQLite on an SMB share — constructor failure (share down)
    surfaces as 503 so the SPA can show the health state instead of a
    silent empty table.
    """
    try:
        db = runner.get_db()
    except Exception:
        raise HTTPException(status_code=503, detail='share unreachable')
    try:
        yield db
    finally:
        db.close()


def require_idle(runner):
    """409 for interactive flows that bypass the job queue while it's busy."""
    if runner.is_busy:
        raise HTTPException(status_code=409, detail='Pipeline is busy')
