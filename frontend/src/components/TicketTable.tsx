import type { Ticket } from "../types/ticket";

interface TicketTableProps {
  tickets: Ticket[];
  loading: boolean;
}

const STATUS_COLORS: Record<string, string> = {
  new: "#e3f2fd",
  processing: "#fff3e0",
  responded: "#e8f5e9",
  closed: "#f5f5f5",
};

const PRIORITY_COLORS: Record<string, string> = {
  low: "#a5d6a7",
  medium: "#fff176",
  high: "#ffab91",
  critical: "#ef9a9a",
};

export function TicketTable({ tickets, loading }: TicketTableProps) {
  if (loading) {
    return <p>Загрузка...</p>;
  }

  if (tickets.length === 0) {
    return <p>Нет тикетов</p>;
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
        <thead>
          <tr>
            {["ID", "От", "Тема", "Категория", "Приоритет", "Статус", "Дата"].map(
              (h) => (
                <th key={h} style={thStyle}>
                  {h}
                </th>
              )
            )}
          </tr>
        </thead>
        <tbody>
          {tickets.map((t) => (
            <tr key={t.id} style={{ background: STATUS_COLORS[t.status] ?? "#fff" }}>
              <td style={tdStyle}>{t.id}</td>
              <td style={tdStyle}>{t.email_from}</td>
              <td style={tdStyle}>{t.subject}</td>
              <td style={tdStyle}>{t.category ?? "—"}</td>
              <td style={tdStyle}>
                <span
                  style={{
                    ...badgeStyle,
                    background: PRIORITY_COLORS[t.priority] ?? "#eee",
                  }}
                >
                  {t.priority}
                </span>
              </td>
              <td style={tdStyle}>{t.status}</td>
              <td style={tdStyle}>
                {new Date(t.created_at).toLocaleString("ru-RU")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "10px 12px",
  borderBottom: "2px solid #ccc",
  whiteSpace: "nowrap",
};

const tdStyle: React.CSSProperties = {
  padding: "8px 12px",
  borderBottom: "1px solid #eee",
};

const badgeStyle: React.CSSProperties = {
  padding: "2px 8px",
  borderRadius: 4,
  fontSize: 12,
  fontWeight: 600,
};
