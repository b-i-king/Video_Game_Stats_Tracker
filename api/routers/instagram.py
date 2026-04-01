from fastapi import APIRouter, HTTPException
from api.core.deps import PersonalConn, CurrentUser

router = APIRouter()


@router.post("/post_instagram")
async def post_instagram(conn: PersonalConn, user: CurrentUser):
    # TODO: migrate from flask_app.py /api/post_instagram
    raise HTTPException(status_code=501, detail="Not yet migrated")


@router.get("/preview_instagram")
async def preview_instagram(conn: PersonalConn):
    # TODO: migrate from flask_app.py /api/preview_instagram
    raise HTTPException(status_code=501, detail="Not yet migrated")
