"""Health strip: network share, disk, GPU, and DB indicators for the dashboard."""

import os
import shutil
import threading

from nicegui import ui, run

from .theme import ERROR, SUCCESS, TEXT_DIM, WARNING


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


def _chip(label, color):
    return (
        f'<span style="display: inline-flex; align-items: center; gap: 5px;'
        f' font-size: 11px; color: {TEXT_DIM}; border: 1px solid {color};'
        f' padding: 1px 8px; border-radius: 2px; white-space: nowrap;">'
        f'<span style="display: inline-block; width: 6px; height: 6px;'
        f' border-radius: 50%; background: {color};"></span>{label}</span>'
    )


def render_health_html(health):
    chips = []
    if health.get('share_ok'):
        chips.append(_chip('share ok', SUCCESS))
        if 'disk_free_gb' in health:
            free = health['disk_free_gb']
            color = SUCCESS if free > 50 else (WARNING if free > 10 else ERROR)
            chips.append(_chip(f'{free:.0f} GB free', color))
        if 'db_size_mb' in health:
            chips.append(_chip(f'db {health["db_size_mb"]:.1f} MB', TEXT_DIM))
    else:
        chips.append(_chip('share unreachable', ERROR))

    if health.get('model_loaded'):
        vram = ''
        if 'vram_used_gb' in health:
            vram = f' {health["vram_used_gb"]:.1f}/{health["vram_total_gb"]:.0f} GB'
        chips.append(_chip(f'model loaded{vram}', WARNING))
    elif 'vram_used_gb' in health:
        chips.append(_chip(
            f'vram {health["vram_used_gb"]:.1f}/{health["vram_total_gb"]:.0f} GB',
            TEXT_DIM))
    else:
        chips.append(_chip('gpu idle', TEXT_DIM))

    return ('<span style="display: inline-flex; gap: 8px; align-items: center;">'
            + ''.join(chips) + '</span>')


def create_health_strip(runner):
    """Mount the health strip; refreshes on its own slow timer."""
    holder = ui.html(_chip('checking...', TEXT_DIM))

    output_dir = runner.get_config()['config']['output_dir']
    db_path = runner._db_path

    async def refresh():
        health = await run.io_bound(check_health, output_dir, db_path)
        holder.set_content(render_health_html(health))

    ui.timer(10.0, refresh)
    ui.timer(0.1, refresh, once=True)
    return holder
