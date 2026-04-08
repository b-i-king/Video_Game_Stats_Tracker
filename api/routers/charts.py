from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, Response
from api.core.deps import DynamicConn

router = APIRouter()


@router.get("/get_interactive_chart/{game_id}")
async def get_interactive_chart(
    game_id: int,
    player_id: int = Query(...),
    tz: str | None = Query(None),
    conn: DynamicConn = None,
):
    # TODO: migrate from flask_app.py /api/get_interactive_chart
    # Uses chart_utils.generate_interactive_chart with sustainable x-axis (dtick="M1", tickformat="%b '%y")
    raise HTTPException(status_code=501, detail="Not yet migrated")


@router.post("/download_chart")
async def download_chart(conn: DynamicConn):
    # TODO: migrate from flask_app.py /api/download_chart
    raise HTTPException(status_code=501, detail="Not yet migrated")


@router.get("/get_heatmap/{game_id}")
async def get_heatmap(game_id: int, player_id: int = Query(...), tz: str | None = Query(None), conn: DynamicConn = None):
    # TODO: migrate from flask_app.py /api/get_heatmap
    raise HTTPException(status_code=501, detail="Not yet migrated")
