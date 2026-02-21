from typing import Literal

from pydantic import BaseModel, Field

# --- Color palette (Japanese woodblock-inspired) ---

COLORS = {
    "indigo": "#264653",
    "teal": "#2A9D8F",
    "saffron": "#E9C46A",
    "coral": "#F4A261",
    "vermillion": "#E76F51",
    "slate": "#6B7280",
    "plum": "#7C3AED",
    "cream": "#FEFCE8",
}

COLOR_NAMES = list(COLORS.keys())

# --- Request models ---


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=32)


class PaintRequest(BaseModel):
    x: int
    y: int
    color: Literal[
        "indigo", "teal", "saffron", "coral", "vermillion", "slate", "plum", "cream"
    ]


class UnpaintRequest(BaseModel):
    x: int
    y: int


class OfferRequest(BaseModel):
    offer_type: Literal["sell_tile", "buy_tile", "sell_paint", "buy_paint"]
    tile_x: int | None = None
    tile_y: int | None = None
    paint_color: str | None = None
    paint_quantity: int | None = None
    price: int = Field(gt=0)


class ChatRequest(BaseModel):
    content: str = Field(min_length=1, max_length=500)


# --- Response models ---


class RegisterResponse(BaseModel):
    agent_id: int
    name: str
    token: str


class TileResponse(BaseModel):
    x: int
    y: int
    owner: str
    owner_id: int
    color: str | None


class GridResponse(BaseModel):
    grid_size: int
    tiles: list[TileResponse]


class InventoryResponse(BaseModel):
    agent_id: int
    name: str
    coins: int
    paint: dict[str, int]
    tiles: list[dict]
    is_done: bool


class OfferResponse(BaseModel):
    id: int
    agent: str
    agent_id: int
    offer_type: str
    status: str
    tile_x: int | None = None
    tile_y: int | None = None
    paint_color: str | None = None
    paint_quantity: int | None = None
    price: int
    accepted_by: str | None = None
    created_at: str


class ChatMessage(BaseModel):
    id: int
    agent: str
    agent_id: int
    content: str
    created_at: str


class GameStatusResponse(BaseModel):
    status: str
    grid_size: int
    agents: list[dict]
    total_painted: int
    total_tiles: int
    all_done: bool
