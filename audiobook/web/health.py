"""Health strip: network share, disk, GPU, and DB indicators for the dashboard."""

from nicegui import ui, run

# Shared with the SPA server — one implementation for both frontends.
from ..server.health import _exists_with_timeout, check_health  # noqa: F401
from .theme import ERROR, SUCCESS, TEXT_DIM, WARNING


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
