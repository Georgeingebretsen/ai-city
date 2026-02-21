export default function Marketplace({ offers }) {
  if (!offers.length) {
    return (
      <div className="panel">
        <h2>Marketplace</h2>
        <p className="empty">No offers yet</p>
      </div>
    );
  }

  return (
    <div className="panel">
      <h2>Marketplace</h2>
      <div className="offer-list">
        {offers.map((o) => (
          <div
            key={o.id}
            className={`offer ${o.status}`}
          >
            <div className="offer-header">
              <span className="offer-agent">{o.agent}</span>
              <span className="offer-price">{o.price} coins</span>
            </div>
            <div className="offer-body">
              {formatOffer(o)}
            </div>
            {o.status === "accepted" && (
              <div className="offer-accepted">
                Accepted by {o.accepted_by}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function formatOffer(o) {
  switch (o.offer_type) {
    case "sell_tile":
      return `Selling tile (${o.tile_x}, ${o.tile_y})`;
    case "buy_tile":
      return `Buying tile (${o.tile_x}, ${o.tile_y})`;
    case "sell_paint":
      return `Selling ${o.paint_quantity}× ${o.paint_color}`;
    case "buy_paint":
      return `Buying ${o.paint_quantity}× ${o.paint_color}`;
    default:
      return o.offer_type;
  }
}
