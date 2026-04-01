from fastapi import APIRouter, HTTPException, Query
from api.core.deps import PersonalConn, CurrentUser
from api.models.stats import AddStatsRequest, UpdateStatRequest

router = APIRouter()


@router.post("/add_stats", status_code=201)
async def add_stats(body: AddStatsRequest, conn: PersonalConn, user: CurrentUser):
    # TODO: migrate from flask_app.py /api/add_stats
    # Includes data quality guards and chart generation side-effects
    raise HTTPException(status_code=501, detail="Not yet migrated")


@router.get("/get_recent_stats")
async def get_recent_stats(
    player_id: int = Query(...),
    game_id: int | None = Query(None),
    limit: int = Query(50),
    conn: PersonalConn = None,
):
    # TODO: migrate from flask_app.py /api/get_recent_stats
    raise HTTPException(status_code=501, detail="Not yet migrated")


@router.put("/update_stats/{stat_id}")
async def update_stats(stat_id: int, body: UpdateStatRequest, conn: PersonalConn, user: CurrentUser):
    # TODO: migrate from flask_app.py /api/update_stats
    raise HTTPException(status_code=501, detail="Not yet migrated")


@router.delete("/delete_stats/{stat_id}", status_code=204)
async def delete_stats(stat_id: int, conn: PersonalConn, user: CurrentUser):
    # TODO: migrate from flask_app.py /api/delete_stats
    raise HTTPException(status_code=501, detail="Not yet migrated")


@router.get("/get_summary/{game_id}")
async def get_summary(game_id: int, player_id: int = Query(...), conn: PersonalConn = None):
    # TODO: migrate from flask_app.py /api/get_summary
    raise HTTPException(status_code=501, detail="Not yet migrated")


@router.get("/get_streaks/{game_id}")
async def get_streaks(game_id: int, player_id: int = Query(...), conn: PersonalConn = None):
    # TODO: migrate from flask_app.py /api/get_streaks
    raise HTTPException(status_code=501, detail="Not yet migrated")


@router.get("/get_stat_ticker")
async def get_stat_ticker(player_id: int = Query(...), conn: PersonalConn = None):
    # TODO: migrate from flask_app.py /api/get_stat_ticker
    raise HTTPException(status_code=501, detail="Not yet migrated")


@router.get("/get_ticker_facts/{game_id}")
async def get_ticker_facts(game_id: int, player_id: int = Query(...), conn: PersonalConn = None):
    # TODO: migrate from flask_app.py /api/get_ticker_facts (15-min server cache, tiered facts)
    raise HTTPException(status_code=501, detail="Not yet migrated")
