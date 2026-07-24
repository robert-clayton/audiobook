"""Status bundle, health, log, and filesystem-sync endpoints."""

from fastapi import APIRouter, Depends

from ..deps import get_runner, require_idle
from ..health import check_health

router = APIRouter(prefix='/api', tags=['system'])


@router.get('/status')
async def get_status(log_since: int = 0, runner=Depends(get_runner)):
    """The single 2s poll: state badge + queue + incremental log lines.

    All reads are in-memory (queue snapshot, log ring buffer) — safe on the
    event loop.
    """
    lines, seq = runner.get_log_since(log_since)
    state = runner.state
    return {
        'state': state.value,
        'error': runner.error_msg,
        'busy': runner.is_busy,
        'dev_mode': runner.dev_mode,
        'queue': runner.queue_snapshot(),
        'log': {'lines': lines, 'seq': seq},
    }


@router.get('/health')
def get_health(runner=Depends(get_runner)):
    # Sync def → threadpool: probes the SMB share (has its own UNC timeout guard).
    output_dir = runner.get_config()['config']['output_dir']
    return check_health(output_dir, runner._db_path)


@router.post('/log/clear')
async def clear_log(runner=Depends(get_runner)):
    runner.clear_log()
    return {'ok': True}


@router.post('/sync')
def sync_filesystem(runner=Depends(get_runner)):
    # Sync def → threadpool: walks the share and writes to the DB.
    require_idle(runner)
    runner.sync_all()
    return {'ok': True}
