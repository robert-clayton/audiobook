"""Job queue: submit whole-pipeline jobs, cancel, inspect."""

from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_runner

router = APIRouter(prefix='/api/jobs', tags=['jobs'])


def submit_response(result):
    """Uniform response for every job-submit endpoint."""
    job, created = result
    return {'job': job.snapshot(), 'created': created}


@router.post('/full')
async def start_full(runner=Depends(get_runner)):
    return submit_response(runner.start_full())


@router.post('/scrape-all')
async def start_scrape_all(runner=Depends(get_runner)):
    return submit_response(runner.start_scrape_only())


@router.delete('/{job_id}')
async def cancel_job(job_id: str, runner=Depends(get_runner)):
    if not runner.cancel(job_id):
        raise HTTPException(status_code=404, detail='Job not found')
    return {'cancelled': True}
