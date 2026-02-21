import { COLORS, agentColor } from "../constants";

function OwnershipMap({ tiles, gridSize, agents }) {
  const agentColors = {};
  agents.forEach((a, i) => {
    agentColors[a.id] = agentColor(i);
  });

  const tileMap = {};
  for (const t of tiles) {
    tileMap[`${t.x},${t.y}`] = t;
  }

  const cells = [];
  for (let y = 0; y < gridSize; y++) {
    for (let x = 0; x < gridSize; x++) {
      const key = `${x},${y}`;
      const tile = tileMap[key];
      cells.push(
        <div
          key={key}
          style={{
            backgroundColor: tile ? agentColors[tile.owner_id] || "#334155" : "#334155",
          }}
        />
      );
    }
  }

  return (
    <div
      className="ownership-map"
      style={{
        display: "grid",
        gridTemplateColumns: `repeat(${gridSize}, 1fr)`,
        gap: 0,
        borderRadius: "6px",
        overflow: "hidden",
        aspectRatio: "1",
        width: "100%",
      }}
    >
      {cells}
    </div>
  );
}

export default function AgentStats({ agents, inventories, tiles, gridSize }) {
  if (!agents.length) {
    return (
      <div className="panel">
        <h2>Agents</h2>
        <p className="empty">No agents registered</p>
      </div>
    );
  }

  return (
    <div className="panel">
      <h2>Agents</h2>
      <div className="agent-list">
        {agents.map((a, i) => {
          const inv = inventories[a.id];
          const color = agentColor(i);
          return (
            <div
              key={a.id}
              className={`agent-card ${a.is_done ? "done" : ""}`}
              style={{ borderLeftColor: color }}
            >
              <div className="agent-header">
                <span className="agent-name">{a.name}</span>
                {a.is_done && <span className="done-badge">DONE</span>}
              </div>
              <div className="agent-coins">{a.coins} coins</div>
              {inv && (
                <div className="agent-paint">
                  {Object.entries(inv.paint)
                    .filter(([, q]) => q > 0)
                    .map(([color, qty]) => (
                      <span
                        key={color}
                        className="paint-chip"
                        style={{ backgroundColor: COLORS[color] }}
                        title={`${color}: ${qty}`}
                      >
                        {qty}
                      </span>
                    ))}
                </div>
              )}
              <div className="agent-tiles">
                {inv ? inv.tiles.length : "?"} tiles
              </div>
            </div>
          );
        })}
      </div>

      <h2 style={{ marginTop: "0.75rem" }}>Ownership</h2>
      <OwnershipMap tiles={tiles} gridSize={gridSize} agents={agents} />
    </div>
  );
}
