// Pure utility functions used across the app.

export function hashColor(name) {
  let h = 0;
  for (let i = 0; i < name.length; i++) {
    h = (Math.imul(31, h) + name.charCodeAt(i)) | 0;
  }
  const hue = Math.abs(h) % 360;
  return `hsl(${hue},65%,48%)`;
}

export function initials(name) {
  const words = name.trim().split(/\s+/);
  if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
}

export function fmtListeners(n) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M listeners`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K listeners`;
  return `${n} listeners`;
}

export function escHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;");
}

export function linkKey(a, b) {
  return a < b ? `${a}|||${b}` : `${b}|||${a}`;
}

// Shared fetch wrapper. Never throws on a bad status or a non-JSON body;
// resolves to { ok, status, data, error }. AbortError is rethrown.

function statusMessage(status) {
  if (status === 429) return "Too many requests. Wait a minute and try again.";
  if (status === 504) return "That took too long. Try again.";
  if (status >= 500) return "Rex is having trouble. Try again shortly.";
  return "Request failed.";
}

export async function fetchJSON(url, opts) {
  let res;
  try {
    res = await fetch(url, opts);
  } catch (e) {
    if (e && e.name === "AbortError") throw e;
    return { ok: false, status: 0, data: null, error: "Could not reach Rex. Check your connection." };
  }
  let data = null;
  let parsed = false;
  try {
    data = await res.json();
    parsed = true;
  } catch (e) {
    if (e && e.name === "AbortError") throw e;
  }
  const serverError = data && typeof data === "object" && typeof data.error === "string" && data.error
    ? data.error
    : null;
  const ok = res.ok && parsed && !serverError;
  return {
    ok,
    status: res.status,
    data,
    error: ok ? null : (serverError || statusMessage(res.status)),
  };
}
