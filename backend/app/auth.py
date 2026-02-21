from fastapi import Depends, Header, HTTPException

from .database import get_db


async def get_current_agent(authorization: str = Header(), db=Depends(get_db)):
    """Extract and validate agent from Bearer token.

    Uses the same db connection as the route handler (FastAPI caches
    the get_db dependency within a single request).
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization[7:]
    cursor = await db.execute(
        "SELECT id, game_id, name, coins, is_done FROM agents WHERE token = ?",
        (token,),
    )
    agent = await cursor.fetchone()
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid token")
    return dict(agent)
