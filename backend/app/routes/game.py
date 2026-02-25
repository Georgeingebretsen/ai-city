from fastapi import APIRouter, Depends, HTTPException

from ..database import get_db
from ..game import distribute_paint, distribute_tiles
from ..models import AgentStatusResponse, GameStatusResponse
from ..websocket import manager

router = APIRouter()


@router.post("/game/create")
async def create_game(db=Depends(get_db)):
    """Create a new game in waiting state so agents can register."""
    cursor = await db.execute(
        "SELECT id FROM games WHERE status = 'waiting' ORDER BY id DESC LIMIT 1"
    )
    if await cursor.fetchone():
        raise HTTPException(status_code=400, detail="A game is already waiting for players")

    cursor = await db.execute("INSERT INTO games (status) VALUES ('waiting')")
    game_id = cursor.lastrowid
    await db.commit()

    return {"status": "waiting", "game_id": game_id}


@router.get("/game/status", response_model=GameStatusResponse)
async def game_status(db=Depends(get_db)):
    cursor = await db.execute(
        "SELECT id, status, grid_size FROM games ORDER BY id DESC LIMIT 1"
    )
    game = await cursor.fetchone()
    if not game:
        return GameStatusResponse(
            status="no_game",
            grid_size=32,
            agents=[],
            total_painted=0,
            total_tiles=0,
            all_done=False,
        )

    game = dict(game)
    cursor = await db.execute(
        "SELECT id, name, coins, is_done FROM agents WHERE game_id = ?",
        (game["id"],),
    )
    agents = [dict(a) for a in await cursor.fetchall()]

    cursor = await db.execute(
        "SELECT COUNT(*) as cnt FROM tiles WHERE game_id = ? AND color IS NOT NULL",
        (game["id"],),
    )
    painted = (await cursor.fetchone())["cnt"]

    total_tiles = game["grid_size"] ** 2
    all_done = len(agents) > 0 and all(a["is_done"] for a in agents)

    return GameStatusResponse(
        status=game["status"],
        grid_size=game["grid_size"],
        agents=[AgentStatusResponse(id=a["id"], name=a["name"], coins=a["coins"], is_done=a["is_done"]) for a in agents],
        total_painted=painted,
        total_tiles=total_tiles,
        all_done=all_done and painted == total_tiles,
    )


@router.post("/game/reset")
async def reset_game(db=Depends(get_db)):
    """Wipe the current game so a new one can start fresh."""
    cursor = await db.execute(
        "SELECT id FROM games ORDER BY id DESC LIMIT 1"
    )
    game = await cursor.fetchone()
    if not game:
        return {"status": "nothing_to_reset"}

    game_id = dict(game)["id"]

    await db.execute("DELETE FROM messages WHERE game_id = ?", (game_id,))
    await db.execute("DELETE FROM offers WHERE game_id = ?", (game_id,))
    await db.execute("DELETE FROM tiles WHERE game_id = ?", (game_id,))
    await db.execute(
        "DELETE FROM paint_inventory WHERE agent_id IN (SELECT id FROM agents WHERE game_id = ?)",
        (game_id,),
    )
    await db.execute("DELETE FROM agents WHERE game_id = ?", (game_id,))
    await db.execute("DELETE FROM games WHERE id = ?", (game_id,))
    await db.commit()

    await manager.broadcast({"type": "game_reset"})

    return {"status": "reset"}


@router.post("/game/start")
async def start_game(db=Depends(get_db)):
    # Check if there's already a running game
    cursor = await db.execute(
        "SELECT id, status, grid_size FROM games ORDER BY id DESC LIMIT 1"
    )
    game = await cursor.fetchone()
    if game and dict(game)["status"] == "running":
        raise HTTPException(status_code=400, detail="Game already running")

    if not game or dict(game)["status"] != "waiting":
        raise HTTPException(status_code=400, detail="No game in waiting state")

    game = dict(game)
    game_id = game["id"]

    # Need at least 2 agents
    cursor = await db.execute(
        "SELECT id FROM agents WHERE game_id = ?", (game_id,)
    )
    agents = [dict(a) for a in await cursor.fetchall()]
    if len(agents) < 2:
        raise HTTPException(
            status_code=400, detail="Need at least 2 agents to start"
        )

    agent_ids = [a["id"] for a in agents]
    grid_size = game["grid_size"]

    # Distribute tiles
    tiles = distribute_tiles(grid_size, agent_ids)
    await db.executemany(
        "INSERT INTO tiles (x, y, game_id, owner_id) VALUES (?, ?, ?, ?)",
        [(x, y, game_id, owner) for x, y, owner in tiles],
    )

    # Distribute paint
    paint = distribute_paint(agent_ids, grid_size)
    await db.executemany(
        "INSERT INTO paint_inventory (agent_id, color, quantity) VALUES (?, ?, ?)",
        paint,
    )

    # Start the game
    await db.execute(
        "UPDATE games SET status = 'running' WHERE id = ?", (game_id,)
    )
    await db.commit()

    # Broadcast
    cursor = await db.execute(
        "SELECT id, name FROM agents WHERE game_id = ?", (game_id,)
    )
    agent_names = [dict(a) for a in await cursor.fetchall()]
    await manager.broadcast(
        {
            "type": "game_started",
            "agents": [{"id": a["id"], "name": a["name"]} for a in agent_names],
            "grid_size": grid_size,
        }
    )

    return {"status": "running", "agents": len(agent_ids), "grid_size": grid_size}
