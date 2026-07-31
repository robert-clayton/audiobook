"""Static serving for the built React SPA with client-route fallback."""

import os
from pathlib import Path

from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

# repo-root/frontend/dist (paths in this project are repo-cwd relative)
DIST_DIR = Path(__file__).resolve().parents[2] / 'frontend' / 'dist'


class SPAStaticFiles(StaticFiles):
    """Serve the SPA bundle; unknown non-API paths fall back to index.html
    so client-side routes like /series/Some%20Name deep-link correctly.

    index.html is served no-cache so an updated dist shows up on a plain
    reload; the hashed assets it references stay cacheable."""

    async def get_response(self, path, scope):
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            response = await super().get_response('index.html', scope)
            path = 'index.html'
        if path in ('', '.', 'index.html'):
            response.headers['Cache-Control'] = 'no-cache'
        return response


def mount_spa(app):
    """Mount the built SPA at / (after all API routes), or a hint page if absent."""
    if (DIST_DIR / 'index.html').is_file():
        app.mount('/', SPAStaticFiles(directory=str(DIST_DIR), html=True), name='spa')
    else:
        @app.get('/')
        def missing_dist():
            return PlainTextResponse(
                'SPA build not found.\n\n'
                f'Expected: {DIST_DIR}{os.sep}index.html\n'
                'Build it with:  cd frontend && npm install && npm run build\n'
                'Or run the legacy UI:  uv run audiobook --legacy\n',
                status_code=503,
            )
