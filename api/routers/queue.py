from fastapi import APIRouter, HTTPException
from api.core.deps import PersonalConn, CurrentUser

router = APIRouter()


@router.post("/process_queue")
async def process_queue(conn: PersonalConn, user: CurrentUser):
    # TODO: migrate from flask_app.py /api/process_queue
    raise HTTPException(status_code=501, detail="Not yet migrated")


@router.get("/queue_status")
async def queue_status(conn: PersonalConn):
    # TODO: migrate from flask_app.py /api/queue_status
    raise HTTPException(status_code=501, detail="Not yet migrated")


@router.post("/retry_failed")
async def retry_failed(conn: PersonalConn, user: CurrentUser):
    # TODO: migrate from flask_app.py /api/retry_failed
    raise HTTPException(status_code=501, detail="Not yet migrated")
