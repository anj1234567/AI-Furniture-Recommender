export const API_URL = 'http://localhost:8000'
export const inr = (n) => '₹' + Number(n).toLocaleString('en-IN')

// export async function searchOnline(q, category, maxPrice, refPrice) {
//   const params = new URLSearchParams({ q, category, limit: "4" });
//   if (maxPrice) params.set("max_price", String(Math.round(maxPrice)));
//   if (refPrice) params.set("ref_price", String(Math.round(refPrice)));
//   const res = await fetch(`${API_URL}/online/search?${params}`);
//   if (!res.ok) {
//     let detail = "Online search failed";
//     try { detail = (await res.json()).detail || detail; } catch {}
//     throw new Error(detail);
//   }
//   return (await res.json()).items;
// }

export async function searchOnline({ category, refName, refColor, roomType, maxPrice, refPrice }) {
  const params = new URLSearchParams({ category, limit: "4" });
  if (refName) params.set("ref_name", refName);
  if (refColor) params.set("ref_color", refColor);
  if (roomType) params.set("room_type", roomType);
  if (maxPrice) params.set("max_price", String(Math.round(maxPrice)));
  if (refPrice) params.set("ref_price", String(Math.round(refPrice)));
  const res = await fetch(`${API_URL}/online/search?${params}`);
  if (!res.ok) {
    let detail = "Online search failed";
    try { detail = (await res.json()).detail || detail; } catch {}
    throw new Error(detail);
  }
  return await res.json();
}