"""NiceGUI app setup and launch."""

import os
from nicegui import ui, app as nicegui_app
from fastapi.responses import FileResponse
from fastapi import HTTPException
from ..speakers import list_speakers, speaker_wav_path
from .runner import PipelineRunner
from .dashboard import create_dashboard
from .series_page import create_series_page
from .failed_page import create_failed_page
from .speakers_page import create_speakers_page


def launch(dev_mode=False):
    """Create the PipelineRunner and start the NiceGUI server."""
    os.environ['AUDIOBOOK_GUI'] = '1'
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

    @nicegui_app.get('/api/speaker_audio/{name}')
    def serve_speaker_audio(name: str):
        # Validate against the actual speaker list — no path traversal
        if name not in list_speakers():
            raise HTTPException(status_code=404, detail='Speaker not found')
        return FileResponse(speaker_wav_path(name), media_type='audio/wav')

    @ui.page('/')
    def index():
        create_dashboard(runner)

    @ui.page('/series/{name}')
    def series_detail(name: str):
        create_series_page(runner, name)

    @ui.page('/failed')
    def failed(series: str = None):
        create_failed_page(runner, series_filter=series)

    @ui.page('/speakers')
    def speakers():
        create_speakers_page(runner)

    try:
        ui.run(title='Audiobook Pipeline', port=8080, reload=False, show=True)
    except KeyboardInterrupt:
        runner.shutdown()
