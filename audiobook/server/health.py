"""Health checks: network share, disk, GPU, and DB indicators.

Pure functions (no UI); the legacy NiceGUI health strip re-imports these
so both frontends share one implementation.
"""

import os
import shutil
import threading


def _exists_with_timeout(path, timeout=3.0):
    """os.path.exists guarded by a thread timeout — a dead UNC path can block
    for tens of seconds; treat a hang as unreachable."""
    result = []
    t = threading.Thread(target=lambda: result.append(os.path.exists(path)), daemon=True)
    t.start()
    t.join(timeout)
    return bool(result and result[0])


def check_health(output_dir, db_path):
    """Gather health indicators. Runs on a threadpool."""
    health = {'share_ok': _exists_with_timeout(output_dir)}

    if health['share_ok']:
        try:
            usage = shutil.disk_usage(output_dir)
            health['disk_free_gb'] = usage.free / 2**30
        except OSError:
            pass
        try:
            health['db_size_mb'] = os.path.getsize(db_path) / 2**20
        except OSError:
            pass

    # GPU — only query if a CUDA context already exists; mem_get_info would
    # otherwise initialize one (and hold VRAM) just for monitoring
    try:
        import torch
        if torch.cuda.is_available() and torch.cuda.is_initialized():
            free, total = torch.cuda.mem_get_info()
            health['vram_used_gb'] = (total - free) / 2**30
            health['vram_total_gb'] = total / 2**30
    except Exception:
        pass

    try:
        from ..processors.tts_qwen import QwenTTSInstance
        health['model_loaded'] = QwenTTSInstance._inst is not None
    except Exception:
        health['model_loaded'] = False

    return health
