import aiosqlite
import os

DB_PATH = os.environ.get("AI_CITY_DB", "ai_city.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT NOT NULL DEFAULT 'waiting',
    grid_size INTEGER NOT NULL DEFAULT 32,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL REFERENCES games(id),
    name TEXT NOT NULL,
    token TEXT NOT NULL UNIQUE,
    coins INTEGER NOT NULL DEFAULT 1000,
    is_done BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(game_id, name)
);

CREATE TABLE IF NOT EXISTS paint_inventory (
    agent_id INTEGER NOT NULL REFERENCES agents(id),
    color TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (agent_id, color)
);

CREATE TABLE IF NOT EXISTS tiles (
    x INTEGER NOT NULL,
    y INTEGER NOT NULL,
    game_id INTEGER NOT NULL REFERENCES games(id),
    owner_id INTEGER NOT NULL REFERENCES agents(id),
    color TEXT,
    PRIMARY KEY (x, y, game_id)
);

CREATE TABLE IF NOT EXISTS offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL REFERENCES games(id),
    agent_id INTEGER NOT NULL REFERENCES agents(id),
    offer_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    tile_x INTEGER,
    tile_y INTEGER,
    paint_color TEXT,
    paint_quantity INTEGER,
    price INTEGER NOT NULL,
    accepted_by INTEGER REFERENCES agents(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL REFERENCES games(id),
    agent_id INTEGER NOT NULL REFERENCES agents(id),
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agents_token ON agents(token);
CREATE INDEX IF NOT EXISTS idx_agents_game ON agents(game_id);
CREATE INDEX IF NOT EXISTS idx_tiles_owner ON tiles(owner_id, game_id);
CREATE INDEX IF NOT EXISTS idx_offers_game_status ON offers(game_id, status);
CREATE INDEX IF NOT EXISTS idx_messages_game ON messages(game_id);
"""


async def _connect() -> aiosqlite.Connection:
    """Open a new database connection with standard pragmas."""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def get_db():
    """FastAPI dependency — yields one connection per request, auto-closes."""
    db = await _connect()
    try:
        yield db
    finally:
        await db.close()


async def init_db():
    db = await _connect()
    try:
        await db.executescript(SCHEMA)
        await db.commit()
    finally:
        await db.close()
