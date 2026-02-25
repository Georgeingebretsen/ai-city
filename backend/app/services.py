"""Shared business logic and query functions."""

from fastapi import HTTPException

from .models import ChatMessage, GridResponse, OfferResponse, TileResponse


# --- Validation helpers ---


async def require_running_game(db, game_id: int):
    """Raise 400 if the game is not in 'running' status."""
    cursor = await db.execute(
        "SELECT status FROM games WHERE id = ?", (game_id,)
    )
    game = await cursor.fetchone()
    if dict(game)["status"] != "running":
        raise HTTPException(status_code=400, detail="Game is not running")


async def revoke_done(db, agent: dict):
    """Any action by a 'done' agent revokes their done status."""
    if agent["is_done"]:
        await db.execute(
            "UPDATE agents SET is_done = FALSE WHERE id = ?", (agent["id"],)
        )


async def available_coins(db, agent: dict) -> int:
    """Agent's coins minus coins locked in open buy offers."""
    cursor = await db.execute(
        "SELECT coins FROM agents WHERE id = ?", (agent["id"],)
    )
    coins = (await cursor.fetchone())["coins"]

    cursor = await db.execute(
        """SELECT COALESCE(SUM(price), 0) as locked
           FROM offers
           WHERE agent_id = ? AND game_id = ? AND status = 'open'
           AND offer_type IN ('buy_tile', 'buy_paint')""",
        (agent["id"], agent["game_id"]),
    )
    locked = (await cursor.fetchone())["locked"]
    return coins - locked


async def available_paint(db, agent: dict, color: str) -> int:
    """Agent's paint minus paint locked in open sell_paint offers."""
    cursor = await db.execute(
        "SELECT quantity FROM paint_inventory WHERE agent_id = ? AND color = ?",
        (agent["id"], color),
    )
    row = await cursor.fetchone()
    total = dict(row)["quantity"] if row else 0

    cursor = await db.execute(
        """SELECT COALESCE(SUM(paint_quantity), 0) as locked
           FROM offers
           WHERE agent_id = ? AND game_id = ? AND status = 'open'
           AND offer_type = 'sell_paint' AND paint_color = ?""",
        (agent["id"], agent["game_id"], color),
    )
    locked = (await cursor.fetchone())["locked"]
    return total - locked


async def check_tile_ownership(db, agent: dict, x: int, y: int) -> dict:
    """Fetch tile, verify it exists and is owned by agent. Returns tile dict."""
    cursor = await db.execute(
        "SELECT owner_id, color FROM tiles WHERE x = ? AND y = ? AND game_id = ?",
        (x, y, agent["game_id"]),
    )
    tile = await cursor.fetchone()
    if not tile:
        raise HTTPException(status_code=404, detail="Tile not found")
    tile = dict(tile)
    if tile["owner_id"] != agent["id"]:
        raise HTTPException(status_code=403, detail="You don't own this tile")
    return tile


async def check_tile_not_locked(db, agent: dict, x: int, y: int):
    """Raise 400 if the tile is locked in an open marketplace offer."""
    cursor = await db.execute(
        """SELECT id FROM offers
           WHERE game_id = ? AND status = 'open'
           AND offer_type IN ('sell_tile', 'buy_tile')
           AND tile_x = ? AND tile_y = ? AND agent_id = ?""",
        (agent["game_id"], x, y, agent["id"]),
    )
    if await cursor.fetchone():
        raise HTTPException(
            status_code=400, detail="Tile is locked in a marketplace offer"
        )


def offer_to_response(row: dict) -> OfferResponse:
    """Convert a DB offer row (with agent_name join) to an OfferResponse."""
    return OfferResponse(
        id=row["id"],
        agent=row["agent_name"],
        agent_id=row["agent_id"],
        offer_type=row["offer_type"],
        status=row["status"],
        tile_x=row["tile_x"],
        tile_y=row["tile_y"],
        paint_color=row["paint_color"],
        paint_quantity=row["paint_quantity"],
        price=row["price"],
        accepted_by=row.get("accepted_by_name"),
        created_at=row["created_at"],
    )


# --- Query functions shared between authenticated and public routes ---


async def fetch_grid(db, game_id: int) -> GridResponse:
    """Fetch the full grid state for a game."""
    cursor = await db.execute(
        "SELECT grid_size FROM games WHERE id = ?", (game_id,)
    )
    grid_size = dict(await cursor.fetchone())["grid_size"]

    cursor = await db.execute(
        """SELECT t.x, t.y, t.color, t.owner_id, a.name as owner
           FROM tiles t JOIN agents a ON t.owner_id = a.id
           WHERE t.game_id = ?
           ORDER BY t.y, t.x""",
        (game_id,),
    )
    tiles = [
        TileResponse(x=r["x"], y=r["y"], owner=r["owner"], owner_id=r["owner_id"], color=r["color"])
        for r in await cursor.fetchall()
    ]
    return GridResponse(grid_size=grid_size, tiles=tiles)


async def fetch_offers(db, game_id: int) -> list[OfferResponse]:
    """Fetch all marketplace offers for a game."""
    cursor = await db.execute(
        """SELECT o.*, a.name as agent_name, a2.name as accepted_by_name
           FROM offers o
           JOIN agents a ON o.agent_id = a.id
           LEFT JOIN agents a2 ON o.accepted_by = a2.id
           WHERE o.game_id = ?
           ORDER BY o.created_at DESC""",
        (game_id,),
    )
    return [offer_to_response(dict(r)) for r in await cursor.fetchall()]


async def fetch_chat(db, game_id: int) -> list[ChatMessage]:
    """Fetch all chat messages for a game."""
    cursor = await db.execute(
        """SELECT m.id, m.content, m.created_at, a.name as agent, a.id as agent_id
           FROM messages m JOIN agents a ON m.agent_id = a.id
           WHERE m.game_id = ?
           ORDER BY m.created_at ASC""",
        (game_id,),
    )
    return [
        ChatMessage(
            id=r["id"],
            agent=r["agent"],
            agent_id=r["agent_id"],
            content=r["content"],
            created_at=r["created_at"],
        )
        for r in await cursor.fetchall()
    ]


async def fetch_agent_inventory(db, agent_id: int, game_id: int) -> tuple[dict[str, int], list[dict]]:
    """Fetch an agent's paint inventory and owned tiles."""
    cursor = await db.execute(
        "SELECT color, quantity FROM paint_inventory WHERE agent_id = ?",
        (agent_id,),
    )
    paint = {row["color"]: row["quantity"] for row in await cursor.fetchall()}

    cursor = await db.execute(
        "SELECT x, y, color FROM tiles WHERE owner_id = ? AND game_id = ?",
        (agent_id, game_id),
    )
    tiles = [{"x": r["x"], "y": r["y"], "color": r["color"]} for r in await cursor.fetchall()]

    return paint, tiles
