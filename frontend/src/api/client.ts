import type { Ticket, AnalyticsSummary, TimelinePoint } from "@/types/ticket";

const API = "/api/v1";

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
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error("Failed to fetch tickets");
  return res.json();
}

export async function fetchTicketById(id: number): Promise<Ticket> {
  const res = await fetch(`${API}/tickets/${id}`);
  if (!res.ok) throw new Error("Ticket not found");
  return res.json();
}

export function getExportUrl(
  format: "csv" | "xlsx",
  params?: { status?: string; category?: string },
): string {
  const url = new URL(`${API}/export/${format}`, window.location.origin);
  if (params?.status) url.searchParams.set("status", params.status);
  if (params?.category) url.searchParams.set("category", params.category);
  return url.toString();
}

export async function fetchAnalyticsSummary(): Promise<AnalyticsSummary> {
  const res = await fetch(`${API}/analytics/summary`);
  if (!res.ok) throw new Error("Failed to fetch analytics");
  return res.json();
}

export async function fetchAnalyticsTimeline(
  days = 30,
): Promise<TimelinePoint[]> {
  const res = await fetch(`${API}/analytics/timeline?days=${days}`);
  if (!res.ok) throw new Error("Failed to fetch timeline");
  return res.json();
}
