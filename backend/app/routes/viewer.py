"""Public endpoints for the web viewer (no auth required)."""

from fastapi import APIRouter, Depends, HTTPException

from ..database import get_db
from ..models import ChatMessage, GridResponse, InventoryResponse, OfferResponse
from ..services import fetch_agent_inventory, fetch_chat, fetch_grid, fetch_offers

router = APIRouter()


async def _get_latest_game(db) -> dict:
    cursor = await db.execute(
        "SELECT id, status, grid_size FROM games ORDER BY id DESC LIMIT 1"
    )
    game = await cursor.fetchone()
    if not game:
        raise HTTPException(status_code=404, detail="No game found")
    return dict(game)


@router.get("/grid/public", response_model=GridResponse)
async def public_grid(db=Depends(get_db)):
    game = await _get_latest_game(db)
    return await fetch_grid(db, game["id"])


@router.get("/marketplace/public", response_model=list[OfferResponse])
async def public_marketplace(db=Depends(get_db)):
    game = await _get_latest_game(db)
    return await fetch_offers(db, game["id"])


@router.get("/chat/public", response_model=list[ChatMessage])
async def public_chat(db=Depends(get_db)):
    game = await _get_latest_game(db)
    return await fetch_chat(db, game["id"])


@router.get("/inventories/public", response_model=list[InventoryResponse])
async def public_inventories(db=Depends(get_db)):
    game = await _get_latest_game(db)
    cursor = await db.execute(
        "SELECT id, name, coins, is_done FROM agents WHERE game_id = ?",
        (game["id"],),
    )
    agents = [dict(a) for a in await cursor.fetchall()]

    result = []
    for agent in agents:
        paint, tiles = await fetch_agent_inventory(db, agent["id"], game["id"])
        result.append(
            InventoryResponse(
                agent_id=agent["id"],
                name=agent["name"],
                coins=agent["coins"],
                paint=paint,
                tiles=tiles,
                is_done=agent["is_done"],
            )
        )
    return result
