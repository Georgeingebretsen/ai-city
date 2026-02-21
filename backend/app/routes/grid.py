from fastapi import APIRouter, Depends, HTTPException

from ..auth import get_current_agent
from ..database import get_db
from ..models import GridResponse, PaintRequest, UnpaintRequest
from ..services import (
    check_tile_not_locked,
    check_tile_ownership,
    fetch_grid,
    require_running_game,
    revoke_done,
)
from ..websocket import manager

router = APIRouter()


@router.get("/grid", response_model=GridResponse)
async def get_grid(agent: dict = Depends(get_current_agent), db=Depends(get_db)):
    return await fetch_grid(db, agent["game_id"])


@router.post("/paint")
async def paint_tile(req: PaintRequest, agent: dict = Depends(get_current_agent), db=Depends(get_db)):
    await require_running_game(db, agent["game_id"])
    tile = await check_tile_ownership(db, agent, req.x, req.y)
    await check_tile_not_locked(db, agent, req.x, req.y)

    # Check paint availability
    cursor = await db.execute(
        "SELECT quantity FROM paint_inventory WHERE agent_id = ? AND color = ?",
        (agent["id"], req.color),
    )
    paint = await cursor.fetchone()
    if not paint or dict(paint)["quantity"] < 1:
        raise HTTPException(status_code=400, detail=f"No {req.color} paint available")

    # If tile already painted, return old paint
    if tile["color"]:
        await db.execute(
            """INSERT INTO paint_inventory (agent_id, color, quantity) VALUES (?, ?, 1)
               ON CONFLICT(agent_id, color) DO UPDATE SET quantity = quantity + 1""",
            (agent["id"], tile["color"]),
        )

    # Paint the tile and deduct paint
    await db.execute(
        "UPDATE tiles SET color = ? WHERE x = ? AND y = ? AND game_id = ?",
        (req.color, req.x, req.y, agent["game_id"]),
    )
    await db.execute(
        "UPDATE paint_inventory SET quantity = quantity - 1 WHERE agent_id = ? AND color = ?",
        (agent["id"], req.color),
    )

    await revoke_done(db, agent)
    await db.commit()

    await manager.broadcast(
        {"type": "tile_painted", "x": req.x, "y": req.y, "color": req.color, "agent": agent["name"], "agent_id": agent["id"]}
    )

    return {"status": "painted", "x": req.x, "y": req.y, "color": req.color}


@router.post("/unpaint")
async def unpaint_tile(req: UnpaintRequest, agent: dict = Depends(get_current_agent), db=Depends(get_db)):
    await require_running_game(db, agent["game_id"])
    tile = await check_tile_ownership(db, agent, req.x, req.y)
    if not tile["color"]:
        raise HTTPException(status_code=400, detail="Tile is not painted")
    await check_tile_not_locked(db, agent, req.x, req.y)

    # Return paint and clear tile
    old_color = tile["color"]
    await db.execute(
        """INSERT INTO paint_inventory (agent_id, color, quantity) VALUES (?, ?, 1)
           ON CONFLICT(agent_id, color) DO UPDATE SET quantity = quantity + 1""",
        (agent["id"], old_color),
    )
    await db.execute(
        "UPDATE tiles SET color = NULL WHERE x = ? AND y = ? AND game_id = ?",
        (req.x, req.y, agent["game_id"]),
    )

    await revoke_done(db, agent)
    await db.commit()

    await manager.broadcast(
        {"type": "tile_unpainted", "x": req.x, "y": req.y, "agent": agent["name"], "agent_id": agent["id"]}
    )

    return {"status": "unpainted", "x": req.x, "y": req.y, "color_returned": old_color}
