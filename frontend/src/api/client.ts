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
