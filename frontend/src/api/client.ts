const API_BASE = "/api/v1";

export async function fetchTickets(params?: {
  status?: string;
  category?: string;
}): Promise<Response> {
  const url = new URL(`${API_BASE}/tickets/`, window.location.origin);
  if (params?.status) url.searchParams.set("status", params.status);
  if (params?.category) url.searchParams.set("category", params.category);
  return fetch(url.toString());
}

export function getExportUrl(
  format: "csv" | "xlsx",
  params?: { status?: string; category?: string }
): string {
  const url = new URL(`${API_BASE}/export/${format}`, window.location.origin);
  if (params?.status) url.searchParams.set("status", params.status);
  if (params?.category) url.searchParams.set("category", params.category);
  return url.toString();
}

export async function fetchAnalyticsSummary(): Promise<AnalyticsSummary> {
  const res = await fetch(`${API_BASE}/analytics/summary`);
  if (!res.ok) throw new Error("Failed to fetch analytics summary");
  return res.json();
}

export async function fetchAnalyticsTimeline(days = 30): Promise<TimelinePoint[]> {
  const res = await fetch(`${API_BASE}/analytics/timeline?days=${days}`);
  if (!res.ok) throw new Error("Failed to fetch analytics timeline");
  return res.json();
}

// Analytics types
export interface DeviceCount {
  device: string;
  count: number;
}

export interface AnalyticsSummary {
  total_tickets: number;
  by_category: Record<string, number>;
  by_sentiment: Record<string, number>;
  by_status: Record<string, number>;
  avg_response_time_minutes: number | null;
  auto_response_rate: number;
  top_devices: DeviceCount[];
}

export interface TimelinePoint {
  date: string;
  count: number;
  auto: number;
  manual: number;
}
