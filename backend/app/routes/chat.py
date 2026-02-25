from fastapi import APIRouter, Depends

from ..auth import get_current_agent
from ..database import get_db
from ..models import ChatMessage, ChatRequest
from ..services import fetch_chat, require_running_game
from ..websocket import manager

router = APIRouter()


@router.get("/chat", response_model=list[ChatMessage])
async def get_chat(agent: dict = Depends(get_current_agent), db=Depends(get_db)):
    return await fetch_chat(db, agent["game_id"])


@router.post("/chat", response_model=ChatMessage)
async def post_chat(req: ChatRequest, agent: dict = Depends(get_current_agent), db=Depends(get_db)):
    await require_running_game(db, agent["game_id"])

    cursor = await db.execute(
        "INSERT INTO messages (game_id, agent_id, content) VALUES (?, ?, ?)",
        (agent["game_id"], agent["id"], req.content),
    )
    msg_id = cursor.lastrowid
    await db.commit()

    # Fetch back to get timestamp
    cursor = await db.execute(
        "SELECT created_at FROM messages WHERE id = ?", (msg_id,)
    )
    row = await cursor.fetchone()

    msg = ChatMessage(
        id=msg_id,
        agent=agent["name"],
        agent_id=agent["id"],
        content=req.content,
        created_at=dict(row)["created_at"],
    )

    await manager.broadcast(
        {
            "type": "chat_message",
            "id": msg_id,
            "agent": agent["name"],
            "agent_id": agent["id"],
            "content": req.content,
            "created_at": msg.created_at,
        }
    )

    return msg
