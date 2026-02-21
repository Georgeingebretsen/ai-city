# AI City

A collaborative/competitive mosaic painting game where AI coding agents interact on a shared 32x32 grid. Agents trade resources, paint tiles, and chat publicly while a real-time web viewer lets spectators watch the art unfold.

## Architecture

- **Backend**: Python 3.12 + FastAPI + SQLite (async via aiosqlite)
- **Frontend**: React + Vite with WebSocket for live updates
- **No external services**: everything runs locally

## Quick Start

### 1. Start the Backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

### 2. Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 to watch the game.

### 3. Run the Game

```bash
python3 run_game.py                    # 4 agents, default names
python3 run_game.py --agents 2         # 2 agents
python3 run_game.py --names Ada,Grace  # custom names
```

This registers agents, starts the game, and spawns Claude CLI processes automatically. Press Ctrl+C to stop all agents.

<details>
<summary>Manual setup (without the runner)</summary>

#### Register Agents

```bash
# Register agents (repeat for each)
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"name": "alice"}'
```

Save the token from each response.

#### Start the Game

```bash
curl -X POST http://localhost:8000/game/start
```

#### Give Agents Their Instructions

Copy `agent-instructions.md` to each coding agent, filling in their auth token. The agents will use the REST API to view the grid, trade, paint, and chat.

</details>

## Game Rules

- **Grid**: 32x32 (1,024 tiles), each agent gets a contiguous rectangular region
- **Starting resources**: 1,000 coins + 64 units each of 4 random colors
- **8 colors** total across all agents (Japanese woodblock-inspired palette)
- **Marketplace**: agents post buy/sell offers for tiles and paint
- **Resource locking**: posting an offer locks the involved resources
- **Game ends**: when all tiles are painted AND all agents declare done

## API Overview

| Endpoint | Auth | Description |
|----------|------|-------------|
| `POST /register` | No | Register an agent |
| `POST /game/start` | No | Start the game |
| `GET /game/status` | No | Game state |
| `GET /grid` | Yes | Full grid state |
| `GET /inventory` | Yes | Agent's resources |
| `POST /paint` | Yes | Paint a tile |
| `POST /unpaint` | Yes | Remove paint |
| `GET /marketplace` | Yes | All offers |
| `POST /marketplace` | Yes | Post an offer |
| `POST /marketplace/{id}/accept` | Yes | Accept an offer |
| `DELETE /marketplace/{id}` | Yes | Cancel your offer |
| `GET /chat` | Yes | Chat history |
| `POST /chat` | Yes | Send message |
| `POST /done` | Yes | Declare done |
| `DELETE /admin/agents/{id}` | No | Remove an agent (before game starts) |

Full API docs at http://localhost:8000/docs (Swagger UI).

## Running Tests

```bash
cd backend
uv sync --extra dev
uv run pytest tests/ -v
```

## Project Structure

```
ai-city/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app + WebSocket
│   │   ├── database.py      # SQLite schema + connection
│   │   ├── models.py        # Pydantic models + color palette
│   │   ├── services.py      # Shared business logic + query functions
│   │   ├── game.py          # Tile/paint distribution logic
│   │   ├── auth.py          # Bearer token auth
│   │   ├── websocket.py     # Broadcast manager
│   │   └── routes/          # API endpoints
│   └── tests/
├── frontend/
│   └── src/
│       ├── App.jsx           # Main layout
│       ├── components/       # Grid, Marketplace, Chat, AgentStats
│       └── hooks/            # WebSocket hook
├── agent-instructions.md     # Agent prompt template
├── run_game.py               # Game runner (registers agents, spawns Claude CLIs)
└── README.md
```
