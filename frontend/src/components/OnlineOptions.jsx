// import { useState } from "react";
// import { searchOnline } from "../lib/api";

// const clamp2 = {
//   display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical",
//   overflow: "hidden", fontSize: 13, lineHeight: 1.3,
// };

// export default function OnlineOptions({ category, budgetLeft, refPrice }) {
//   const [items, setItems] = useState(null);
//   const [loading, setLoading] = useState(false);
//   const [error, setError] = useState("");

//   async function load() {
//     setLoading(true);
//     setError("");
//     try {
//       setItems(await searchOnline(`${category} furniture`, category, budgetLeft, refPrice));
//     } catch (e) {
//       setError(e.message);
//     } finally {
//       setLoading(false);
//     }
//   }

//   if (items === null) {
//     return (
//       <div>
//         <button type="button" className="ghost" onClick={load} disabled={loading}>
//           {loading ? "Searching…" : "Choose from an online site"}
//         </button>
//         {error && <p className="hint">{error}</p>}
//       </div>
//     );
//   }

//   return (
//     <div>
//       <div className="hint">
//         Top online matches. Price and stock may differ on the site.{" "}
//         <button type="button" className="linkbtn" onClick={() => setItems(null)}>Hide</button>
//       </div>
//       {items.length === 0 && <div className="hint">No relevant online listings within your budget.</div>}
//       {items.map((it) => (
//         <div key={it.id} style={{ display: "flex", gap: 10, margin: "8px 0" }}>
//           {it.image && <img src={it.image} alt="" width={56} height={56} style={{ objectFit: "cover", borderRadius: 6 }} />}
//           <div style={{ minWidth: 0 }}>
//             <div style={clamp2} title={it.name}>{it.name}</div>
//             <div className="muted" style={{ fontSize: 12 }}>
//               ₹{it.price}{it.rating ? ` · ★ ${it.rating}` : ""}
//               {it.dims ? ` · ${it.dims.a_cm}×${it.dims.b_cm}×${it.dims.c_cm} cm` : " · size not listed"}
//             </div>
//             {it.buy_url && <a className="onlinelink" href={it.buy_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 12 }}>View on the site </a>}
//           </div>
//         </div>
//       ))}
//     </div>
//   );
// }

import { useState } from "react";
import { searchOnline } from "../lib/api";

const clamp2 = {
  display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical",
  overflow: "hidden", fontSize: 13, lineHeight: 1.3,
};

export default function OnlineOptions({ category, budgetLeft, refPrice, refName, color, roomType }) {
  const [items, setItems] = useState(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const r = await searchOnline({
        category, refName, refColor: color, roomType,
        maxPrice: budgetLeft, refPrice,
      });
      setItems(r.items);
      setQuery(r.query);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  if (items === null) {
    return (
      <div>
        <button type="button" className="ghost" onClick={load} disabled={loading}>
          {loading ? "Searching…" : "Find similar online"}
        </button>
        {error && <p className="hint">{error}</p>}
      </div>
    );
  }

  return (
    <div>
      <div className="hint">
        Similar online options: Price and stock may differ on the site.{" "}
        <button type="button" className="linkbtn" onClick={() => setItems(null)}>Hide</button>
      </div>
      {items.length === 0 && <div className="hint">No similar listings within your budget.</div>}
      {items.map((it) => (
        <div key={it.id} style={{ display: "flex", gap: 10, margin: "8px 0" }}>
          {it.image && <img src={it.image} alt="" width={56} height={56} style={{ objectFit: "cover", borderRadius: 6 }} />}
          <div style={{ minWidth: 0 }}>
            <div style={clamp2} title={it.name}>{it.name}</div>
            <div className="muted" style={{ fontSize: 12 }}>
              ₹{it.price}{it.rating ? ` · ★ ${it.rating}` : ""}
              {it.dims ? ` · ${it.dims.a_cm}×${it.dims.b_cm}×${it.dims.c_cm} cm` : " · size not listed"}
            </div>
            {it.buy_url && (
              <a className="onlinelink" href={it.buy_url} target="_blank" rel="noopener noreferrer"
                 style={{ color: "#6ee7d0", fontSize: 12, textDecoration: "none" }}>
                View on the site ↗
              </a>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}