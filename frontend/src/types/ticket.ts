export interface Ticket {
  id: number;
  email_from: string;
  email_to: string | null;
  subject: string;
  body: string;
  fio: string | null;
  organization: string | null;
  phone: string | null;
  serial_numbers: string[] | null;
  device_type: string | null;
  description: string | null;
  category: string | null;
  priority: string;
  sentiment: string | null;
  confidence: number | null;
  entities: Record<string, string> | null;
  response: string | null;
  kb_article_id: number | null;
  status: string;
  is_auto: boolean;
  created_at: string;
  updated_at: string;
  responded_at: string | null;
}

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
