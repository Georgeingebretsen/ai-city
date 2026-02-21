#!/usr/bin/env python3
"""
AI City Game Runner

Registers agents, starts the game, and spawns Claude CLI processes — all in one command.

Usage:
    python run_game.py                    # 4 agents, default names
    python run_game.py --agents 2         # 2 agents
    python run_game.py --names Ada,Grace  # custom names
"""

import argparse
import asyncio
import json
import signal
import sys
import urllib.error
import urllib.request
from pathlib import Path

CONFIG = {"base_url": "http://localhost:8000"}

DEFAULT_NAMES = ["Ada", "Grace", "Rosalind", "Marie", "Emmy", "Sophie", "Hypatia", "Maryam"]

# ANSI color codes for distinguishing agents in terminal output
COLORS = [
    "\033[36m",  # cyan
    "\033[33m",  # yellow
    "\033[35m",  # magenta
    "\033[32m",  # green
    "\033[91m",  # bright red
    "\033[94m",  # bright blue
    "\033[93m",  # bright yellow
    "\033[95m",  # bright magenta
]
RESET = "\033[0m"
BOLD = "\033[1m"


def api_request(path: str, data: dict | None = None, method: str | None = None) -> dict:
    """Make a JSON request to the backend. Defaults to POST if data is provided, else GET."""
    url = f"{CONFIG['base_url']}{path}"
    headers = {"Content-Type": "application/json"}
    body = json.dumps(data).encode() if data is not None else None
    if method is None:
        method = "POST" if data is not None else "GET"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def check_backend() -> bool:
    """Check if the backend is reachable."""
    try:
        api_request("/game/status")
        return True
    except (urllib.error.URLError, ConnectionRefusedError, OSError):
        return False


def register_agents(names: list[str]) -> list[dict]:
    """Register agents and return list of {name, token, agent_id}."""
    agents = []
    for name in names:
        resp = api_request("/register", {"name": name})
        agents.append(resp)
        print(f"  Registered {BOLD}{name}{RESET} (id={resp['agent_id']})")
    return agents


def start_game():
    """Start the game via the backend API."""
    api_request("/game/start", method="POST")


def build_prompt(template: str, agent: dict) -> str:
    """Fill in the agent-instructions template with the agent's token."""
    prompt = template.replace("<YOUR_TOKEN_HERE>", agent["token"])
    return prompt


async def stream_output(stream, prefix: str):
    """Read lines from a stream and print with a colored prefix."""
    while True:
        line = await stream.readline()
        if not line:
            break
        text = line.decode("utf-8", errors="replace").rstrip()
        if text:
            print(f"{prefix} {text}")


async def run_agent(name: str, prompt: str, color: str, semaphore: asyncio.Semaphore):
    """Spawn a claude CLI process for one agent."""
    prefix = f"{color}{BOLD}[{name}]{RESET}"

    # Stagger agent launches slightly to avoid overwhelming the API
    async with semaphore:
        print(f"{prefix} Starting claude process...")
        proc = await asyncio.create_subprocess_exec(
            "claude", "-p", prompt, "--verbose", "--dangerously-skip-permissions",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    # Stream both stdout and stderr with the colored prefix
    await asyncio.gather(
        stream_output(proc.stdout, prefix),
        stream_output(proc.stderr, f"{prefix}{color}(err){RESET}"),
    )

    code = await proc.wait()
    print(f"{prefix} Process exited with code {code}")
    return code


async def main():
    parser = argparse.ArgumentParser(description="AI City Game Runner")
    parser.add_argument("--agents", "-n", type=int, default=4, help="Number of agents (default: 4, max: 8)")
    parser.add_argument("--names", type=str, default=None, help="Comma-separated agent names (e.g. Ada,Grace)")
    parser.add_argument("--base-url", type=str, default=CONFIG["base_url"], help="Backend URL (default: http://localhost:8000)")
    args = parser.parse_args()

    CONFIG["base_url"] = args.base_url

    # Determine agent names
    if args.names:
        names = [n.strip() for n in args.names.split(",")]
    else:
        names = DEFAULT_NAMES[: args.agents]

    if len(names) > 8:
        print("Error: Maximum 8 agents allowed", file=sys.stderr)
        sys.exit(1)

    # Load agent instructions template
    script_dir = Path(__file__).parent
    instructions_path = script_dir / "agent-instructions.md"
    if not instructions_path.exists():
        print(f"Error: {instructions_path} not found", file=sys.stderr)
        sys.exit(1)
    template = instructions_path.read_text()

    # Step 1: Check backend
    print(f"\n{BOLD}[1/4] Checking backend at {CONFIG['base_url']}...{RESET}", flush=True)
    if not check_backend():
        print(f"Error: Backend not reachable at {CONFIG['base_url']}", file=sys.stderr)
        print("  Start it with: cd backend && uv run uvicorn app.main:app --reload --port 8000", file=sys.stderr)
        sys.exit(1)
    print("  Backend is up!")

    # Step 2: Reset any previous game
    print(f"\n{BOLD}[2/4] Resetting previous game...{RESET}")
    api_request("/game/reset", method="POST")
    print("  Clean slate!")

    # Step 3: Register agents
    print(f"\n{BOLD}[3/4] Registering {len(names)} agents...{RESET}")
    try:
        agents = register_agents(names)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"Error registering agents: {e.code} {body}", file=sys.stderr)
        sys.exit(1)

    # Step 4: Start the game
    print(f"\n{BOLD}[4/4] Starting the game...{RESET}")
    try:
        start_game()
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"Error starting game: {e.code} {body}", file=sys.stderr)
        sys.exit(1)
    print("  Game started!")

    # Build prompts
    prompts = [build_prompt(template, agent) for agent in agents]

    # Launch agents
    print(f"\n{BOLD}Launching {len(agents)} Claude agents...{RESET}")
    print(f"  Watch the game at http://localhost:5173")
    print(f"  Press Ctrl+C to stop all agents\n")

    # Use a semaphore to stagger launches (2 at a time)
    semaphore = asyncio.Semaphore(2)
    tasks = []
    for i, (agent, prompt) in enumerate(zip(agents, prompts)):
        color = COLORS[i % len(COLORS)]
        task = asyncio.create_task(run_agent(agent["name"], prompt, color, semaphore))
        tasks.append(task)

    # Handle graceful shutdown
    loop = asyncio.get_event_loop()
    shutdown_event = asyncio.Event()

    def handle_signal():
        print(f"\n{BOLD}Shutting down agents...{RESET}")
        shutdown_event.set()
        for task in tasks:
            task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)

    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        print(f"\n{BOLD}All agents finished.{RESET}")
        for agent, result in zip(agents, results):
            if isinstance(result, Exception):
                print(f"  {agent['name']}: error — {result}")
            else:
                print(f"  {agent['name']}: exit code {result}")
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{BOLD}Stopped.{RESET}")
