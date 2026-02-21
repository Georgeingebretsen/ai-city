import { COLORS } from "../constants";

export default function Grid({ tiles, gridSize }) {
  const tileMap = {};
  for (const t of tiles) {
    tileMap[`${t.x},${t.y}`] = t;
  }

  const cells = [];
  for (let y = 0; y < gridSize; y++) {
    for (let x = 0; x < gridSize; x++) {
      const key = `${x},${y}`;
      const tile = tileMap[key];
      const painted = tile?.color;

      cells.push(
        <div
          key={key}
          title={`(${x},${y}) ${painted ? tile.color : "unpainted"}`}
          style={{
            backgroundColor: painted ? COLORS[tile.color] : "#1e293b",
            aspectRatio: "1",
          }}
        />
      );
    }
  }

  return (
    <div
      className="grid-container"
      style={{
        display: "grid",
        gridTemplateColumns: `repeat(${gridSize}, 1fr)`,
        gap: "1px",
        backgroundColor: "#0f172a",
        borderRadius: "8px",
        overflow: "hidden",
        aspectRatio: "1",
      }}
    >
      {cells}
    </div>
  );
}
