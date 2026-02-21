export const COLORS = {
  indigo: "#264653",
  teal: "#2A9D8F",
  saffron: "#E9C46A",
  coral: "#F4A261",
  vermillion: "#E76F51",
  slate: "#6B7280",
  plum: "#7C3AED",
  cream: "#FEFCE8",
};

export const AGENT_HUES = [210, 0, 120, 45, 270, 330, 160, 30];

export function agentColor(index) {
  return `hsl(${AGENT_HUES[index % AGENT_HUES.length]}, 55%, 55%)`;
}

export const API_BASE = "http://localhost:8000";
export const WS_URL = "ws://localhost:8000/ws";
