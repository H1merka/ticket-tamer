import { useEffect, useState } from "react";
import type { Ticket } from "./types/ticket";
import { fetchTickets } from "./api/client";
import { TicketTable } from "./components/TicketTable";
import { ExportButtons } from "./components/ExportButtons";

const CATEGORIES = [
  "неисправность",
  "калибровка",
  "запрос_документации",
  "запрос_доступа",
  "прочее",
];

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");

  useEffect(() => {
    setLoading(true);
    fetchTickets({
      status: statusFilter || undefined,
      category: categoryFilter || undefined,
    })
      .then((res) => res.json())
      .then((data) => setTickets(data))
      .catch((err) => console.error("Failed to fetch tickets:", err))
      .finally(() => setLoading(false));
  }, [statusFilter, categoryFilter]);

  return (
    <div style={{ maxWidth: 1400, margin: "0 auto", padding: 24 }}>
      <h1 style={{ fontSize: 24, marginBottom: 16 }}>Ticket Tamer — ЭРИС</h1>

      {/* Filters */}
      <div style={{ display: "flex", gap: 12, marginBottom: 16, flexWrap: "wrap", alignItems: "center" }}>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          style={selectStyle}
        >
          <option value="">Все статусы</option>
          <option value="new">Новый</option>
          <option value="processing">В обработке</option>
          <option value="responded">Отвечен</option>
          <option value="needs_review">Требует проверки</option>
          <option value="closed">Закрыт</option>
        </select>

        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          style={selectStyle}
        >
          <option value="">Все категории</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>

        <ExportButtons status={statusFilter} category={categoryFilter} />
      </div>

      <TicketTable tickets={tickets} loading={loading} />
    </div>
  );
}

const selectStyle: React.CSSProperties = {
  padding: "6px 12px",
  border: "1px solid #ccc",
  borderRadius: 4,
  fontSize: 14,
};
