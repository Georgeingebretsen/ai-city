import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Use temp DB for tests
os.environ["AI_CITY_DB"] = ":memory:"

from app.main import app
from app.database import init_db


@pytest_asyncio.fixture
async def client():
    """Fresh client with clean DB for each test."""
    # Re-init DB
    import app.database as db_mod
    db_mod.DB_PATH = ":memory:"

    # We need to use a file-based DB since multiple connections are used
    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_mod.DB_PATH = tmp.name
    await init_db()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    os.unlink(tmp.name)


async def _setup_game(client):
    """Create a waiting game so agents can register."""
    resp = await client.post("/game/create")
    assert resp.status_code == 200


async def _register(client, name):
    resp = await client.post("/register", json={"name": name})
    assert resp.status_code == 200
    return resp.json()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_register_and_start(client):
    await _setup_game(client)
    a1 = await _register(client, "alice")
    a2 = await _register(client, "bob")

    assert a1["name"] == "alice"
    assert "token" in a1

    # Start game
    resp = await client.post("/game/start")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "running"
    assert data["agents"] == 2

    # Check status
    resp = await client.get("/game/status")
    assert resp.json()["status"] == "running"
    assert resp.json()["total_tiles"] == 1024


@pytest.mark.asyncio
async def test_paint_and_unpaint(client):
    await _setup_game(client)
    a1 = await _register(client, "alice")
    a2 = await _register(client, "bob")
    await client.post("/game/start")

    headers = _auth(a1["token"])

    # Get inventory to find owned tiles and paint
    resp = await client.get("/inventory", headers=headers)
    inv = resp.json()
    assert len(inv["tiles"]) == 512  # Half of 1024
    assert inv["coins"] == 1000

    # Find a color we have and record starting quantity
    colors_with_paint = [c for c, q in inv["paint"].items() if q > 0]
    color = colors_with_paint[0]
    starting_quantity = inv["paint"][color]
    tile = inv["tiles"][0]

    # Paint
    resp = await client.post("/paint", json={"x": tile["x"], "y": tile["y"], "color": color}, headers=headers)
    assert resp.status_code == 200

    # Check inventory paint decreased by 1
    resp = await client.get("/inventory", headers=headers)
    assert resp.json()["paint"][color] == starting_quantity - 1

    # Unpaint
    resp = await client.post("/unpaint", json={"x": tile["x"], "y": tile["y"]}, headers=headers)
    assert resp.status_code == 200

    # Paint restored
    resp = await client.get("/inventory", headers=headers)
    assert resp.json()["paint"][color] == starting_quantity


@pytest.mark.asyncio
async def test_marketplace_sell_paint(client):
    await _setup_game(client)
    a1 = await _register(client, "alice")
    a2 = await _register(client, "bob")
    await client.post("/game/start")

    h1 = _auth(a1["token"])
    h2 = _auth(a2["token"])

    # Get alice's paint
    resp = await client.get("/inventory", headers=h1)
    alice_paint = {c: q for c, q in resp.json()["paint"].items() if q > 0}
    color = list(alice_paint.keys())[0]
    starting_quantity = alice_paint[color]

    # Alice sells 10 units of her first color
    resp = await client.post("/marketplace", json={
        "offer_type": "sell_paint",
        "paint_color": color,
        "paint_quantity": 10,
        "price": 50,
    }, headers=h1)
    assert resp.status_code == 200
    offer_id = resp.json()["id"]

    # Bob accepts
    resp = await client.post(f"/marketplace/{offer_id}/accept", headers=h2)
    assert resp.status_code == 200

    # Verify balances
    resp = await client.get("/inventory", headers=h1)
    assert resp.json()["coins"] == 1050
    assert resp.json()["paint"][color] == starting_quantity - 10

    resp = await client.get("/inventory", headers=h2)
    assert resp.json()["coins"] == 950


@pytest.mark.asyncio
async def test_chat(client):
    await _setup_game(client)
    a1 = await _register(client, "alice")
    a2 = await _register(client, "bob")
    await client.post("/game/start")

    h1 = _auth(a1["token"])

    resp = await client.post("/chat", json={"content": "Hello world!"}, headers=h1)
    assert resp.status_code == 200

    resp = await client.get("/chat", headers=h1)
    messages = resp.json()
    assert len(messages) == 1
    assert messages[0]["content"] == "Hello world!"
    assert messages[0]["agent"] == "alice"


@pytest.mark.asyncio
async def test_cannot_paint_unowned_tile(client):
    await _setup_game(client)
    a1 = await _register(client, "alice")
    a2 = await _register(client, "bob")
    await client.post("/game/start")

    h1 = _auth(a1["token"])
    h2 = _auth(a2["token"])

    # Get bob's tile
    resp = await client.get("/inventory", headers=h2)
    bob_tile = resp.json()["tiles"][0]

    # Alice tries to paint bob's tile
    resp = await client.get("/inventory", headers=h1)
    color = [c for c, q in resp.json()["paint"].items() if q > 0][0]

    resp = await client.post("/paint", json={
        "x": bob_tile["x"], "y": bob_tile["y"], "color": color,
    }, headers=h1)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_resource_locking(client):
    await _setup_game(client)
    a1 = await _register(client, "alice")
    a2 = await _register(client, "bob")
    await client.post("/game/start")

    h1 = _auth(a1["token"])

    # Get alice's paint
    resp = await client.get("/inventory", headers=h1)
    alice_paint = {c: q for c, q in resp.json()["paint"].items() if q > 0}
    color = list(alice_paint.keys())[0]
    full_quantity = alice_paint[color]

    # Sell all units of that color
    resp = await client.post("/marketplace", json={
        "offer_type": "sell_paint",
        "paint_color": color,
        "paint_quantity": full_quantity,
        "price": 100,
    }, headers=h1)
    assert resp.status_code == 200

    # Try to sell again — should fail (paint is locked)
    resp = await client.post("/marketplace", json={
        "offer_type": "sell_paint",
        "paint_color": color,
        "paint_quantity": 1,
        "price": 10,
    }, headers=h1)
    assert resp.status_code == 400
    assert "Insufficient" in resp.json()["detail"]
