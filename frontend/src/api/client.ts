import type { Ticket, AnalyticsSummary, TimelinePoint } from "@/types/ticket";

const API = "/api/v1";
const TOKEN_KEY = "tt_access_token";

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem(TOKEN_KEY);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function authFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const res = await fetch(input, {
    ...init,
    headers: { ...authHeaders(), ...init?.headers },
  });
  if (res.status === 401) {
    localStorage.removeItem(TOKEN_KEY);
    window.location.href = "/login";
  }
  return res;
}

export async function fetchTickets(params?: {
  status?: string;
  category?: string;
  skip?: number;
  limit?: number;
}): Promise<Ticket[]> {
  const url = new URL(`${API}/tickets/`, window.location.origin);
  if (params?.status) url.searchParams.set("status", params.status);
  if (params?.category) url.searchParams.set("category", params.category);
  if (params?.skip) url.searchParams.set("skip", String(params.skip));
  if (params?.limit) url.searchParams.set("limit", String(params.limit));
  const res = await authFetch(url.toString());
  if (!res.ok) throw new Error("Failed to fetch tickets");
  return res.json();
}

export function getExportUrl(
  format: "csv" | "xlsx",
  params?: { status?: string; category?: string },
): string {
  const url = new URL(`${API}/export/${format}`, window.location.origin);
  if (params?.status) url.searchParams.set("status", params.status);
  if (params?.category) url.searchParams.set("category", params.category);
  // Append token so download links work (browser can't set Authorization header on <a>)
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) url.searchParams.set("token", token);
  return url.toString();
}

export async function fetchAnalyticsSummary(): Promise<AnalyticsSummary> {
  const res = await authFetch(`${API}/analytics/summary`);
  if (!res.ok) throw new Error("Failed to fetch analytics");
  return res.json();
}

export async function fetchAnalyticsTimeline(
  days = 30,
): Promise<TimelinePoint[]> {
  const res = await authFetch(`${API}/analytics/timeline?days=${days}`);
  if (!res.ok) throw new Error("Failed to fetch timeline");
  return res.json();
}
