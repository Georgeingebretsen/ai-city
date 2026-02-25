import secrets

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException

from ..auth import get_current_agent
from ..database import get_db
from ..models import InventoryResponse, RegisterRequest, RegisterResponse
from ..services import fetch_agent_inventory, require_running_game
from ..websocket import manager

router = APIRouter()


@router.post("/register", response_model=RegisterResponse)
async def register(req: RegisterRequest, db=Depends(get_db)):
    # Find a waiting game to register into
    cursor = await db.execute(
        "SELECT id FROM games WHERE status = 'waiting' ORDER BY id DESC LIMIT 1"
    )
    game = await cursor.fetchone()
    if not game:
        raise HTTPException(status_code=400, detail="No game waiting for players — create one first with POST /game/create")
    game_id = dict(game)["id"]

    # Check agent limit (max 8)
    cursor = await db.execute(
        "SELECT COUNT(*) as cnt FROM agents WHERE game_id = ?", (game_id,)
    )
    count = (await cursor.fetchone())["cnt"]
    if count >= 8:
        raise HTTPException(status_code=400, detail="Game is full (max 8 agents)")

    token = secrets.token_urlsafe(32)
    try:
        cursor = await db.execute(
            "INSERT INTO agents (game_id, name, token) VALUES (?, ?, ?)",
            (game_id, req.name, token),
        )
        agent_id = cursor.lastrowid
        await db.commit()
    except aiosqlite.IntegrityError:
        raise HTTPException(
            status_code=409, detail=f"Agent name '{req.name}' already taken"
        )

    return RegisterResponse(agent_id=agent_id, name=req.name, token=token)


@router.delete("/admin/agents/{agent_id}")
async def delete_agent(agent_id: int, db=Depends(get_db)):
    """Admin endpoint to remove an agent. Only works before game starts."""
    cursor = await db.execute(
        "SELECT a.id, a.game_id, g.status FROM agents a JOIN games g ON a.game_id = g.id WHERE a.id = ?",
        (agent_id,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Agent not found")
    row = dict(row)
    if row["status"] != "waiting":
        raise HTTPException(status_code=400, detail="Cannot remove agents after game has started")

    await db.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
    await db.commit()
    return {"status": "deleted", "agent_id": agent_id}


@router.get("/inventory", response_model=InventoryResponse)
async def get_inventory(agent: dict = Depends(get_current_agent), db=Depends(get_db)):
    # Re-fetch agent to get fresh coins/is_done (auth snapshot may be stale)
    cursor = await db.execute(
        "SELECT coins, is_done FROM agents WHERE id = ?", (agent["id"],)
    )
    fresh = dict(await cursor.fetchone())
    paint, tiles = await fetch_agent_inventory(db, agent["id"], agent["game_id"])
    return InventoryResponse(
        agent_id=agent["id"],
        name=agent["name"],
        coins=fresh["coins"],
        paint=paint,
        tiles=tiles,
        is_done=fresh["is_done"],
    )


@router.post("/done")
async def declare_done(agent: dict = Depends(get_current_agent), db=Depends(get_db)):
    await require_running_game(db, agent["game_id"])

    await db.execute(
        "UPDATE agents SET is_done = TRUE WHERE id = ?", (agent["id"],)
    )
    await db.commit()

    await manager.broadcast(
        {"type": "agent_done", "agent": agent["name"], "agent_id": agent["id"]}
    )

    # Check if game is finished (all done + all painted)
    cursor = await db.execute(
        "SELECT COUNT(*) as cnt FROM agents WHERE game_id = ? AND is_done = FALSE",
        (agent["game_id"],),
    )
    not_done = (await cursor.fetchone())["cnt"]

    if not_done == 0:
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM tiles WHERE game_id = ? AND color IS NULL",
            (agent["game_id"],),
        )
        unpainted = (await cursor.fetchone())["cnt"]
        if unpainted == 0:
            await db.execute(
                "UPDATE games SET status = 'finished' WHERE id = ?",
                (agent["game_id"],),
            )
            await db.commit()
            await manager.broadcast({"type": "game_finished"})

    return {"status": "done"}
