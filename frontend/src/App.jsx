import { useState, useEffect, useCallback } from "react";
import "./App.css";
import Grid from "./components/Grid";
import Marketplace from "./components/Marketplace";
import Chat from "./components/Chat";
import AgentStats from "./components/AgentStats";
import useWebSocket from "./hooks/useWebSocket";
import { API_BASE, WS_URL } from "./constants";

export default function App() {
  const [gameStatus, setGameStatus] = useState(null);
  const [tiles, setTiles] = useState([]);
  const [offers, setOffers] = useState([]);
  const [messages, setMessages] = useState([]);
  const [agents, setAgents] = useState([]);
  const [inventories, setInventories] = useState({});
  const [gridSize, setGridSize] = useState(32);

  const { connected, addListener } = useWebSocket(WS_URL);

  const fetchGrid = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/grid/public`);
      if (res.ok) {
        const data = await res.json();
        setTiles(data.tiles);
        setGridSize(data.grid_size);
      }
    } catch {}
  }, []);

  const fetchMarketplace = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/marketplace/public`);
      if (res.ok) setOffers(await res.json());
    } catch {}
  }, []);

  const fetchChat = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/chat/public`);
      if (res.ok) setMessages(await res.json());
    } catch {}
  }, []);

  const fetchInventories = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/inventories/public`);
      if (res.ok) {
        const data = await res.json();
        const map = {};
        for (const inv of data) map[inv.agent_id] = inv;
        setInventories(map);
      }
    } catch {}
  }, []);

  const fetchAll = useCallback(async () => {
    try {
      const statusRes = await fetch(`${API_BASE}/game/status`);
      const status = await statusRes.json();
      setGameStatus(status.status);
      setGridSize(status.grid_size);
      setAgents(status.agents || []);

      if (status.status === "running" || status.status === "finished") {
        await Promise.all([
          fetchGrid(),
          fetchMarketplace(),
          fetchChat(),
          fetchInventories(),
        ]);
      }
    } catch (e) {
      console.error("Failed to fetch game state:", e);
    }
  }, [fetchGrid, fetchMarketplace, fetchChat, fetchInventories]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  // Handle WebSocket events
  useEffect(() => {
    return addListener((event) => {
      switch (event.type) {
        case "tile_painted":
          setTiles((prev) =>
            prev.map((t) =>
              t.x === event.x && t.y === event.y
                ? { ...t, color: event.color }
                : t
            )
          );
          break;

        case "tile_unpainted":
          setTiles((prev) =>
            prev.map((t) =>
              t.x === event.x && t.y === event.y
                ? { ...t, color: null }
                : t
            )
          );
          break;

        case "offer_posted":
          setOffers((prev) => [event.offer, ...prev]);
          break;

        case "offer_accepted":
          setOffers((prev) =>
            prev.map((o) =>
              o.id === event.offer_id
                ? { ...o, status: "accepted", accepted_by: event.accepted_by }
                : o
            )
          );
          break;

        case "offer_cancelled":
          setOffers((prev) =>
            prev.map((o) =>
              o.id === event.offer_id ? { ...o, status: "cancelled" } : o
            )
          );
          break;

        case "chat_message":
          setMessages((prev) => {
            if (prev.some((m) => m.id === event.id)) return prev;
            return [
              ...prev,
              {
                id: event.id,
                agent: event.agent,
                agent_id: event.agent_id,
                content: event.content,
                created_at: event.timestamp,
              },
            ];
          });
          break;

        case "agent_done":
          setAgents((prev) =>
            prev.map((a) =>
              a.id === event.agent_id ? { ...a, is_done: true } : a
            )
          );
          break;

        case "game_started":
          setGameStatus("running");
          setAgents(
            event.agents.map((a) => ({ ...a, coins: 1000, is_done: false }))
          );
          setGridSize(event.grid_size);
          setTimeout(fetchAll, 500);
          break;

        case "game_finished":
          setGameStatus("finished");
          break;

        default:
          break;
      }

      // Refresh inventories on state changes
      if (
        [
          "tile_painted",
          "tile_unpainted",
          "offer_accepted",
          "offer_posted",
        ].includes(event.type)
      ) {
        fetchInventories();
      }
    });
  }, [addListener, fetchAll, fetchInventories]);

  return (
    <div className="app">
      <header>
        <h1>AI City</h1>
        <div className="status-bar">
          <span className={`status ${gameStatus}`}>
            {gameStatus || "loading..."}
          </span>
          <span className={`ws-status ${connected ? "on" : "off"}`}>
            {connected ? "LIVE" : "RECONNECTING..."}
          </span>
        </div>
      </header>

      <main>
        <div className="left-column">
          <Grid tiles={tiles} gridSize={gridSize} />
          <Chat messages={messages} agents={agents} />
        </div>
        <div className="right-column">
          <Marketplace offers={offers} />
          <AgentStats
            agents={agents}
            inventories={inventories}
            tiles={tiles}
            gridSize={gridSize}
          />
        </div>
      </main>
    </div>
  );
}
