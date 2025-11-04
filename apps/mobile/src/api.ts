const API_BASE = (global as any).expo?.expoConfig?.extra?.apiBase || process.env.EXPO_PUBLIC_API_BASE || "http://127.0.0.1:8001";


export async function searchTrove(q: string, sensitive: boolean) {
  const r = await fetch(`${API_BASE}/api/trove/search`, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ q, sensitive_mode: sensitive, n: 20 })
  });
  const j = await r.json();
  if (!j.ok) throw new Error(j.error || "search failed");
  return j;
}


export async function fetchArticle(idOrUrl: string) {
  const r = await fetch(`${API_BASE}/api/trove/article?id_or_url=${encodeURIComponent(idOrUrl)}`);
  const j = await r.json();
  if (!j.ok) throw new Error(j.error || "article failed");
  return j.article;
}


export async function summarize(text: string) {
  const r = await fetch(`${API_BASE}/api/summarize`, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ text, max_words: 180 })
  });
  if (r.status === 503) return { summary: "(Summaries disabled – OPENAI_API_KEY missing on server.)" };
  const j = await r.json();
  if (!j.ok) throw new Error(j.error || "summarize failed");
  return j;
}


export async function startTunnel() {
  const r = await fetch(`${API_BASE}/api/tunnel/start`, { method: "POST" });
  const j = await r.json();
  return j;
}


export async function getTunnelStatus() {
  const r = await fetch(`${API_BASE}/api/tunnel/status`);
  const j = await r.json();
  return j;
}


export function getQrCodeUrl(url?: string): string {
  const params = url ? `?url=${encodeURIComponent(url)}` : "";
  return `${API_BASE}/api/qrcode${params}`;
}

