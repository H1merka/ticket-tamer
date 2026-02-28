export interface Ticket {
  id: number;
  email_from: string;
  email_to: string | null;
  subject: string;
  body: string;
  // ERIS fields
  fio: string | null;
  organization: string | null;
  phone: string | null;
  serial_numbers: string[] | null;
  device_type: string | null;
  description: string | null;
  // AI results
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
