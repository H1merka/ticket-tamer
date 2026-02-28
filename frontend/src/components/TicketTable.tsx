import { useState, useMemo } from "react";
import type { Ticket } from "../types/ticket";

interface TicketTableProps {
  tickets: Ticket[];
  loading: boolean;
}

const STATUS_COLORS: Record<string, string> = {
  new: "#e3f2fd",
  processing: "#fff3e0",
  responded: "#e8f5e9",
  needs_review: "#fff8e1",
  closed: "#f5f5f5",
};

const SENTIMENT_BADGE: Record<string, { bg: string; label: string }> = {
  позитив: { bg: "#c8e6c9", label: "позитив" },
  нейтраль: { bg: "#e0e0e0", label: "нейтраль" },
  негатив: { bg: "#ffcdd2", label: "негатив" },
};

type SortKey =
  | "created_at"
  | "fio"
  | "organization"
  | "phone"
  | "email_from"
  | "serial_numbers"
  | "device_type"
  | "sentiment"
  | "description";

const PAGE_SIZES = [25, 50, 100] as const;

function formatDate(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function TicketTable({ tickets, loading }: TicketTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("created_at");
  const [sortAsc, setSortAsc] = useState(false);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState<number>(25);
  const [search, setSearch] = useState("");

  // filter by search
  const filtered = useMemo(() => {
    if (!search.trim()) return tickets;
    const q = search.toLowerCase();
    return tickets.filter(
      (t) =>
        (t.description ?? "").toLowerCase().includes(q) ||
        (t.fio ?? "").toLowerCase().includes(q) ||
        (t.organization ?? "").toLowerCase().includes(q) ||
        (t.subject ?? "").toLowerCase().includes(q)
    );
  }, [tickets, search]);

  // sort
  const sorted = useMemo(() => {
    const arr = [...filtered];
    arr.sort((a, b) => {
      const av = (a[sortKey] ?? "") as string;
      const bv = (b[sortKey] ?? "") as string;
      const cmp = typeof av === "string" ? av.localeCompare(bv) : 0;
      return sortAsc ? cmp : -cmp;
    });
    return arr;
  }, [filtered, sortKey, sortAsc]);

  // paginate
  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const paged = sorted.slice(page * pageSize, (page + 1) * pageSize);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(true);
    }
  };

  const arrow = (key: SortKey) =>
    sortKey === key ? (sortAsc ? " ▲" : " ▼") : "";

  if (loading) return <p>Загрузка...</p>;
  if (tickets.length === 0) return <p>Нет тикетов</p>;

  return (
    <div>
      {/* Search */}
      <input
        type="text"
        placeholder="Поиск по описанию, ФИО, организации..."
        value={search}
        onChange={(e) => {
          setSearch(e.target.value);
          setPage(0);
        }}
        style={{ ...inputStyle, marginBottom: 12 }}
      />

      {/* Table */}
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, minWidth: 1100 }}>
          <thead>
            <tr>
              {(
                [
                  ["created_at", "Дата"],
                  ["fio", "ФИО"],
                  ["organization", "Объект"],
                  ["phone", "Телефон"],
                  ["email_from", "Email"],
                  ["serial_numbers", "Заводские номера"],
                  ["device_type", "Тип приборов"],
                  ["sentiment", "Эмоц. окрас"],
                  ["description", "Описание"],
                ] as [SortKey, string][]
              ).map(([key, label]) => (
                <th
                  key={key}
                  onClick={() => handleSort(key)}
                  style={{ ...thStyle, cursor: "pointer", userSelect: "none" }}
                >
                  {label}
                  {arrow(key)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paged.map((t) => {
              const sentimentInfo = SENTIMENT_BADGE[t.sentiment ?? ""];
              return (
                <tr key={t.id} style={{ background: STATUS_COLORS[t.status] ?? "#fff" }}>
                  <td style={{ ...tdStyle, whiteSpace: "nowrap" }}>{formatDate(t.created_at)}</td>
                  <td style={tdStyle}>{t.fio ?? "—"}</td>
                  <td style={tdStyle}>{t.organization ?? "—"}</td>
                  <td style={{ ...tdStyle, whiteSpace: "nowrap" }}>{t.phone ?? "—"}</td>
                  <td style={tdStyle}>{t.email_from}</td>
                  <td style={tdStyle}>
                    {t.serial_numbers && t.serial_numbers.length > 0
                      ? t.serial_numbers.join(", ")
                      : "—"}
                  </td>
                  <td style={tdStyle}>{t.device_type ?? "—"}</td>
                  <td style={tdStyle}>
                    {sentimentInfo ? (
                      <span style={{ ...badgeStyle, background: sentimentInfo.bg }}>
                        {sentimentInfo.label}
                        {t.confidence != null && (
                          <span style={{ marginLeft: 4, fontSize: 11, opacity: 0.7 }}>
                            {(t.confidence * 100).toFixed(0)}%
                          </span>
                        )}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td style={{ ...tdStyle, maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis" }}>
                    {t.description ?? "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 12, fontSize: 13 }}>
        <span>Записей: {filtered.length}</span>
        <select
          value={pageSize}
          onChange={(e) => {
            setPageSize(Number(e.target.value));
            setPage(0);
          }}
          style={inputStyle}
        >
          {PAGE_SIZES.map((s) => (
            <option key={s} value={s}>
              {s} / стр.
            </option>
          ))}
        </select>
        <button onClick={() => setPage(Math.max(0, page - 1))} disabled={page === 0} style={btnStyle}>
          ◀
        </button>
        <span>
          {page + 1} / {totalPages}
        </span>
        <button
          onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
          disabled={page >= totalPages - 1}
          style={btnStyle}
        >
          ▶
        </button>
      </div>
    </div>
  );
}

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "10px 8px",
  borderBottom: "2px solid #ccc",
  whiteSpace: "nowrap",
  position: "sticky",
  top: 0,
  background: "#fafafa",
  zIndex: 1,
};

const tdStyle: React.CSSProperties = {
  padding: "7px 8px",
  borderBottom: "1px solid #eee",
  verticalAlign: "top",
};

const badgeStyle: React.CSSProperties = {
  padding: "2px 8px",
  borderRadius: 4,
  fontSize: 12,
  fontWeight: 600,
  display: "inline-flex",
  alignItems: "center",
};

const inputStyle: React.CSSProperties = {
  padding: "6px 12px",
  border: "1px solid #ccc",
  borderRadius: 4,
  fontSize: 13,
};

const btnStyle: React.CSSProperties = {
  padding: "4px 12px",
  border: "1px solid #ccc",
  borderRadius: 4,
  background: "#fff",
  cursor: "pointer",
  fontSize: 13,
};
