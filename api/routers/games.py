from fastapi import APIRouter, HTTPException
from api.core.deps import PersonalConn, CurrentUser
from api.models.games import UpdateGameRequest

router = APIRouter()


@router.get("/get_games")
async def get_games(conn: PersonalConn):
    rows = await conn.fetch(
        "SELECT game_id, game_name, platform, franchise, installment, genre, is_active FROM dim.dim_games ORDER BY game_name"
    )
    return [dict(r) for r in rows]


@router.get("/get_game_details/{game_id}")
async def get_game_details(game_id: int, conn: PersonalConn):
    # TODO: migrate from flask_app.py /api/get_game_details
    raise HTTPException(status_code=501, detail="Not yet migrated")


@router.put("/update_game/{game_id}")
async def update_game(game_id: int, body: UpdateGameRequest, conn: PersonalConn, user: CurrentUser):
    # TODO: migrate from flask_app.py /api/update_game
    raise HTTPException(status_code=501, detail="Not yet migrated")


@router.delete("/delete_game/{game_id}", status_code=204)
async def delete_game(game_id: int, conn: PersonalConn, user: CurrentUser):
    # TODO: migrate from flask_app.py /api/delete_game
    raise HTTPException(status_code=501, detail="Not yet migrated")


@router.get("/get_game_ranks/{game_id}")
async def get_game_ranks(game_id: int, conn: PersonalConn):
    # TODO: migrate from flask_app.py /api/get_game_ranks
    raise HTTPException(status_code=501, detail="Not yet migrated")


@router.get("/get_game_modes/{game_id}")
async def get_game_modes(game_id: int, conn: PersonalConn):
    # TODO: migrate from flask_app.py /api/get_game_modes
    raise HTTPException(status_code=501, detail="Not yet migrated")


@router.get("/get_game_stat_types/{game_id}")
async def get_game_stat_types(game_id: int, conn: PersonalConn):
    # TODO: migrate from flask_app.py /api/get_game_stat_types
    raise HTTPException(status_code=501, detail="Not yet migrated")


@router.get("/get_game_context/{game_id}")
async def get_game_context(game_id: int, conn: PersonalConn):
    # TODO: migrate from flask_app.py /api/get_game_context
    raise HTTPException(status_code=501, detail="Not yet migrated")


@router.get("/get_game_franchises")
async def get_game_franchises(conn: PersonalConn):
    # TODO: migrate from flask_app.py /api/get_game_franchises
    raise HTTPException(status_code=501, detail="Not yet migrated")


@router.get("/get_game_installments/{franchise_name:path}")
async def get_game_installments(franchise_name: str, conn: PersonalConn):
    # TODO: migrate from flask_app.py /api/get_game_installments
    raise HTTPException(status_code=501, detail="Not yet migrated")
