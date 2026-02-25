from fastapi import APIRouter, Depends, HTTPException

from ..auth import get_current_agent
from ..database import get_db
from ..models import OfferRequest, OfferResponse
from ..services import (
    available_coins,
    available_paint,
    fetch_offers,
    offer_to_response,
    require_running_game,
    revoke_done,
)
from ..websocket import manager

router = APIRouter()


@router.get("/marketplace", response_model=list[OfferResponse])
async def get_marketplace(agent: dict = Depends(get_current_agent), db=Depends(get_db)):
    return await fetch_offers(db, agent["game_id"])


@router.post("/marketplace", response_model=OfferResponse)
async def post_offer(req: OfferRequest, agent: dict = Depends(get_current_agent), db=Depends(get_db)):
    await require_running_game(db, agent["game_id"])

    # Validate and lock resources based on offer type
    if req.offer_type == "sell_tile":
        if req.tile_x is None or req.tile_y is None:
            raise HTTPException(status_code=400, detail="tile_x and tile_y required for sell_tile")
        # Must own the tile
        cursor = await db.execute(
            "SELECT owner_id FROM tiles WHERE x = ? AND y = ? AND game_id = ?",
            (req.tile_x, req.tile_y, agent["game_id"]),
        )
        tile = await cursor.fetchone()
        if not tile or dict(tile)["owner_id"] != agent["id"]:
            raise HTTPException(status_code=403, detail="You don't own this tile")
        # Check not already locked
        cursor = await db.execute(
            """SELECT id FROM offers WHERE game_id = ? AND status = 'open'
               AND tile_x = ? AND tile_y = ? AND agent_id = ?
               AND offer_type = 'sell_tile'""",
            (agent["game_id"], req.tile_x, req.tile_y, agent["id"]),
        )
        if await cursor.fetchone():
            raise HTTPException(status_code=400, detail="Tile already listed for sale")

    elif req.offer_type == "buy_tile":
        if req.tile_x is None or req.tile_y is None:
            raise HTTPException(status_code=400, detail="tile_x and tile_y required for buy_tile")
        # Tile must exist and be owned by someone else
        cursor = await db.execute(
            "SELECT owner_id FROM tiles WHERE x = ? AND y = ? AND game_id = ?",
            (req.tile_x, req.tile_y, agent["game_id"]),
        )
        tile = await cursor.fetchone()
        if not tile:
            raise HTTPException(status_code=404, detail="Tile not found")
        if dict(tile)["owner_id"] == agent["id"]:
            raise HTTPException(status_code=400, detail="You already own this tile")
        # Lock coins
        avail = await available_coins(db, agent)
        if avail < req.price:
            raise HTTPException(status_code=400, detail=f"Insufficient coins (available: {avail})")

    elif req.offer_type == "sell_paint":
        if not req.paint_color or not req.paint_quantity:
            raise HTTPException(status_code=400, detail="paint_color and paint_quantity required")
        if req.paint_quantity < 1:
            raise HTTPException(status_code=400, detail="paint_quantity must be positive")
        # Check available paint (minus locked)
        avail = await available_paint(db, agent, req.paint_color)
        if avail < req.paint_quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient {req.paint_color} paint (available: {avail})")

    elif req.offer_type == "buy_paint":
        if not req.paint_color or not req.paint_quantity:
            raise HTTPException(status_code=400, detail="paint_color and paint_quantity required")
        if req.paint_quantity < 1:
            raise HTTPException(status_code=400, detail="paint_quantity must be positive")
        # Lock coins
        avail = await available_coins(db, agent)
        if avail < req.price:
            raise HTTPException(status_code=400, detail=f"Insufficient coins (available: {avail})")

    # Create the offer
    cursor = await db.execute(
        """INSERT INTO offers (game_id, agent_id, offer_type, tile_x, tile_y,
           paint_color, paint_quantity, price)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            agent["game_id"], agent["id"], req.offer_type,
            req.tile_x, req.tile_y,
            req.paint_color, req.paint_quantity, req.price,
        ),
    )
    offer_id = cursor.lastrowid

    await revoke_done(db, agent)
    await db.commit()

    # Fetch the created offer for response
    cursor = await db.execute(
        """SELECT o.*, a.name as agent_name, NULL as accepted_by_name
           FROM offers o JOIN agents a ON o.agent_id = a.id
           WHERE o.id = ?""",
        (offer_id,),
    )
    row = dict(await cursor.fetchone())
    response = offer_to_response(row)

    await manager.broadcast(
        {"type": "offer_posted", "offer": response.model_dump()}
    )

    return response


@router.post("/marketplace/{offer_id}/accept")
async def accept_offer(offer_id: int, agent: dict = Depends(get_current_agent), db=Depends(get_db)):
    await require_running_game(db, agent["game_id"])

    # Fetch the offer
    cursor = await db.execute(
        "SELECT * FROM offers WHERE id = ? AND game_id = ?",
        (offer_id, agent["game_id"]),
    )
    offer = await cursor.fetchone()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    offer = dict(offer)

    if offer["status"] != "open":
        raise HTTPException(status_code=400, detail="Offer is no longer open")
    if offer["agent_id"] == agent["id"]:
        raise HTTPException(status_code=400, detail="Cannot accept your own offer")

    # Execute trade based on type
    poster_id = offer["agent_id"]
    accepter_id = agent["id"]

    if offer["offer_type"] == "sell_tile":
        # Poster sells tile to accepter: accepter pays coins, gets tile
        avail = await available_coins(db, agent)
        if avail < offer["price"]:
            raise HTTPException(status_code=400, detail="Insufficient coins")
        await db.execute("UPDATE agents SET coins = coins - ? WHERE id = ?", (offer["price"], accepter_id))
        await db.execute("UPDATE agents SET coins = coins + ? WHERE id = ?", (offer["price"], poster_id))
        await db.execute(
            "UPDATE tiles SET owner_id = ? WHERE x = ? AND y = ? AND game_id = ?",
            (accepter_id, offer["tile_x"], offer["tile_y"], agent["game_id"]),
        )

    elif offer["offer_type"] == "buy_tile":
        # Poster wants to buy tile from accepter: accepter must own the tile
        cursor = await db.execute(
            "SELECT owner_id FROM tiles WHERE x = ? AND y = ? AND game_id = ?",
            (offer["tile_x"], offer["tile_y"], agent["game_id"]),
        )
        tile = await cursor.fetchone()
        if not tile or dict(tile)["owner_id"] != accepter_id:
            raise HTTPException(status_code=403, detail="You don't own this tile")
        # Check tile not locked by accepter
        cursor = await db.execute(
            """SELECT id FROM offers WHERE game_id = ? AND status = 'open'
               AND tile_x = ? AND tile_y = ? AND agent_id = ?
               AND offer_type = 'sell_tile'""",
            (agent["game_id"], offer["tile_x"], offer["tile_y"], accepter_id),
        )
        if await cursor.fetchone():
            raise HTTPException(status_code=400, detail="Tile is locked in your own offer")

        await db.execute("UPDATE agents SET coins = coins - ? WHERE id = ?", (offer["price"], poster_id))
        await db.execute("UPDATE agents SET coins = coins + ? WHERE id = ?", (offer["price"], accepter_id))
        await db.execute(
            "UPDATE tiles SET owner_id = ? WHERE x = ? AND y = ? AND game_id = ?",
            (poster_id, offer["tile_x"], offer["tile_y"], agent["game_id"]),
        )

    elif offer["offer_type"] == "sell_paint":
        # Poster sells paint to accepter
        avail = await available_coins(db, agent)
        if avail < offer["price"]:
            raise HTTPException(status_code=400, detail="Insufficient coins")
        await db.execute("UPDATE agents SET coins = coins - ? WHERE id = ?", (offer["price"], accepter_id))
        await db.execute("UPDATE agents SET coins = coins + ? WHERE id = ?", (offer["price"], poster_id))
        # Transfer paint
        await db.execute(
            "UPDATE paint_inventory SET quantity = quantity - ? WHERE agent_id = ? AND color = ?",
            (offer["paint_quantity"], poster_id, offer["paint_color"]),
        )
        await db.execute(
            """INSERT INTO paint_inventory (agent_id, color, quantity) VALUES (?, ?, ?)
               ON CONFLICT(agent_id, color) DO UPDATE SET quantity = quantity + ?""",
            (accepter_id, offer["paint_color"], offer["paint_quantity"], offer["paint_quantity"]),
        )

    elif offer["offer_type"] == "buy_paint":
        # Poster wants to buy paint from accepter
        avail = await available_paint(db, agent, offer["paint_color"])
        if avail < offer["paint_quantity"]:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient {offer['paint_color']} paint (available: {avail})",
            )
        await db.execute("UPDATE agents SET coins = coins - ? WHERE id = ?", (offer["price"], poster_id))
        await db.execute("UPDATE agents SET coins = coins + ? WHERE id = ?", (offer["price"], accepter_id))
        await db.execute(
            "UPDATE paint_inventory SET quantity = quantity - ? WHERE agent_id = ? AND color = ?",
            (offer["paint_quantity"], accepter_id, offer["paint_color"]),
        )
        await db.execute(
            """INSERT INTO paint_inventory (agent_id, color, quantity) VALUES (?, ?, ?)
               ON CONFLICT(agent_id, color) DO UPDATE SET quantity = quantity + ?""",
            (poster_id, offer["paint_color"], offer["paint_quantity"], offer["paint_quantity"]),
        )

    # Mark offer as accepted
    await db.execute(
        "UPDATE offers SET status = 'accepted', accepted_by = ? WHERE id = ?",
        (accepter_id, offer_id),
    )

    await revoke_done(db, agent)
    await db.commit()

    await manager.broadcast(
        {"type": "offer_accepted", "offer_id": offer_id, "accepted_by": agent["name"], "accepted_by_id": agent["id"]}
    )

    return {"status": "accepted", "offer_id": offer_id}


@router.delete("/marketplace/{offer_id}")
async def cancel_offer(offer_id: int, agent: dict = Depends(get_current_agent), db=Depends(get_db)):
    cursor = await db.execute(
        "SELECT * FROM offers WHERE id = ? AND game_id = ?",
        (offer_id, agent["game_id"]),
    )
    offer = await cursor.fetchone()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    offer = dict(offer)

    if offer["agent_id"] != agent["id"]:
        raise HTTPException(status_code=403, detail="Not your offer")
    if offer["status"] != "open":
        raise HTTPException(status_code=400, detail="Offer is not open")

    await db.execute(
        "UPDATE offers SET status = 'cancelled' WHERE id = ?", (offer_id,)
    )
    await db.commit()

    await manager.broadcast(
        {"type": "offer_cancelled", "offer_id": offer_id}
    )

    return {"status": "cancelled", "offer_id": offer_id}
