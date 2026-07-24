"""Server entry point: PipelineRunner + FastAPI + uvicorn on port 8080."""

import os
import threading
import webbrowser


def serve(dev_mode=False, open_browser=True, port=8080):
    """Launch the API/SPA server (the default GUI mode)."""
    os.environ['AUDIOBOOK_GUI'] = '1'

    import uvicorn
    from ..web.runner import PipelineRunner
    from .app import create_app

    runner = PipelineRunner(dev_mode=dev_mode)
    app = create_app(runner)

    if open_browser:
        threading.Timer(1.0, webbrowser.open, [f'http://127.0.0.1:{port}']).start()

    uvicorn.run(app, host='0.0.0.0', port=port, log_level='warning')
