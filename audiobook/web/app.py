"""NiceGUI app setup and launch."""

import os
from nicegui import ui, app as nicegui_app
from fastapi.responses import FileResponse
from fastapi import HTTPException
from .runner import PipelineRunner
from .dashboard import create_dashboard
from .series_page import create_series_page


def launch(dev_mode=False):
    """Create the PipelineRunner and start the NiceGUI server."""
    runner = PipelineRunner(dev_mode=dev_mode)

    @nicegui_app.get('/api/audio/{chapter_id}')
    def serve_audio(chapter_id: int):
        db = runner.get_db()
        try:
            chapter = db.get_chapter_by_id(chapter_id)
        finally:
            db.close()
        if not chapter or not chapter.get('output_path'):
            raise HTTPException(status_code=404, detail='Audio not found')
        path = chapter['output_path']
        if not os.path.exists(path):
            alt = os.path.splitext(path)[0] + ('.mp3' if path.endswith('.wav') else '.wav')
            if os.path.exists(alt):
                path = alt
            else:
                raise HTTPException(status_code=404, detail='Audio file not found')
        media_type = 'audio/mpeg' if path.endswith('.mp3') else 'audio/wav'
        return FileResponse(path, media_type=media_type)

    @ui.page('/')
    def index():
        create_dashboard(runner)

    @ui.page('/series/{name}')
    def series_detail(name: str):
        create_series_page(runner, name)

    try:
        ui.run(title='Audiobook Pipeline', port=8080, reload=False, show=True)
    except KeyboardInterrupt:
        runner.shutdown()
