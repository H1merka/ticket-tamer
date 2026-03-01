import { useState, useEffect, useMemo } from "react";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { Search, Download, ChevronLeft, ChevronRight, ArrowUpDown } from "lucide-react";
import { fetchTickets, getExportUrl } from "@/api/client";
import type { Ticket } from "@/types/ticket";

const CATEGORIES = [
  "неисправность",
  "калибровка",
  "запрос_документации",
  "запрос_доступа",
  "прочее",
];

const STATUSES = [
  { value: "new", label: "Новый" },
  { value: "processing", label: "В обработке" },
  { value: "responded", label: "Отвечен" },
  { value: "needs_review", label: "Требует проверки" },
  { value: "closed", label: "Закрыт" },
];

const SENTIMENT_MAP: Record<string, { label: string; variant: "success" | "secondary" | "destructive" }> = {
  позитив: { label: "Позитив", variant: "success" },
  нейтраль: { label: "Нейтраль", variant: "secondary" },
  негатив: { label: "Негатив", variant: "destructive" },
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

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: "created_at", label: "Дата" },
  { key: "fio", label: "ФИО" },
  { key: "organization", label: "Объект" },
  { key: "phone", label: "Телефон" },
  { key: "email_from", label: "Email" },
  { key: "serial_numbers", label: "Заводские номера" },
  { key: "device_type", label: "Тип приборов" },
  { key: "sentiment", label: "Тональность" },
  { key: "description", label: "Описание" },
];

const PAGE_SIZES = [25, 50, 100] as const;

/** Format ISO date as dd.mm.yyyy HH:MM in UTC+5 (Perm / ERIS). */
function formatDate(iso: string): string {
  const d = new Date(iso);
  const utc5 = new Date(d.getTime() + 5 * 60 * 60 * 1000);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(utc5.getUTCDate())}.${pad(utc5.getUTCMonth() + 1)}.${utc5.getUTCFullYear()} ${pad(utc5.getUTCHours())}:${pad(utc5.getUTCMinutes())}`;
}

export default function MessagesPage() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("__all__");
  const [categoryFilter, setCategoryFilter] = useState("__all__");
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("created_at");
  const [sortAsc, setSortAsc] = useState(false);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState<number>(25);

  useEffect(() => {
    setLoading(true);
    fetchTickets({
      status: statusFilter === "__all__" ? undefined : statusFilter,
      category: categoryFilter === "__all__" ? undefined : categoryFilter,
      limit: 200,
    })
      .then(setTickets)
      .catch((err) => console.error("Fetch error:", err))
      .finally(() => setLoading(false));
  }, [statusFilter, categoryFilter]);

  // Local search filter
  const filtered = useMemo(() => {
    if (!search.trim()) return tickets;
    const q = search.toLowerCase();
    return tickets.filter(
      (t) =>
        (t.description ?? "").toLowerCase().includes(q) ||
        (t.fio ?? "").toLowerCase().includes(q) ||
        (t.organization ?? "").toLowerCase().includes(q) ||
        (t.subject ?? "").toLowerCase().includes(q),
    );
  }, [tickets, search]);

  // Sort
  const sorted = useMemo(() => {
    const arr = [...filtered];
    arr.sort((a, b) => {
      const av = String(a[sortKey] ?? "");
      const bv = String(b[sortKey] ?? "");
      const cmp = av.localeCompare(bv);
      return sortAsc ? cmp : -cmp;
    });
    return arr;
  }, [filtered, sortKey, sortAsc]);

  // Paginate
  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const paged = sorted.slice(page * pageSize, (page + 1) * pageSize);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(!sortAsc);
    else {
      setSortKey(key);
      setSortAsc(true);
    }
  };

  return (
    <div className="space-y-4">
      {/* Filters bar */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative w-[220px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="Поиск..."
            className="pl-9 h-9"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
          />
        </div>

        <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(0); }}>
          <SelectTrigger className="w-[170px]">
            <SelectValue placeholder="Статус" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__all__">Все статусы</SelectItem>
            {STATUSES.map((s) => (
              <SelectItem key={s.value} value={s.value}>
                {s.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={categoryFilter} onValueChange={(v) => { setCategoryFilter(v); setPage(0); }}>
          <SelectTrigger className="w-[200px]">
            <SelectValue placeholder="Категория" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__all__">Все категории</SelectItem>
            {CATEGORIES.map((c) => (
              <SelectItem key={c} value={c}>
                {c}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <div className="flex-1" />

        <a
          href={getExportUrl("csv", {
            status: statusFilter === "__all__" ? undefined : statusFilter,
            category: categoryFilter === "__all__" ? undefined : categoryFilter,
          })}
          download
        >
          <Button variant="outline" size="sm" className="gap-2">
            <Download className="w-4 h-4" />
            CSV
          </Button>
        </a>
        <a
          href={getExportUrl("xlsx", {
            status: statusFilter === "__all__" ? undefined : statusFilter,
            category: categoryFilter === "__all__" ? undefined : categoryFilter,
          })}
          download
        >
          <Button variant="outline" size="sm" className="gap-2">
            <Download className="w-4 h-4" />
            XLSX
          </Button>
        </a>
      </div>

      {/* Table */}
      <div className="bg-card rounded-xl border border-border overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-40 text-muted-foreground">
            Загрузка...
          </div>
        ) : paged.length === 0 ? (
          <div className="flex items-center justify-center h-40 text-muted-foreground">
            Нет данных
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/30">
                {COLUMNS.map((col) => (
                  <TableHead
                    key={col.key}
                    className="cursor-pointer select-none"
                    onClick={() => handleSort(col.key)}
                  >
                    <span className="inline-flex items-center gap-1">
                      {col.label}
                      {sortKey === col.key ? (
                        <span className="text-primary">
                          {sortAsc ? "▲" : "▼"}
                        </span>
                      ) : (
                        <ArrowUpDown className="w-3 h-3 opacity-30" />
                      )}
                    </span>
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {paged.map((t) => {
                const sentInfo = SENTIMENT_MAP[t.sentiment ?? ""];
                return (
                  <TableRow key={t.id}>
                    <TableCell className="whitespace-nowrap">
                      {formatDate(t.created_at)}
                    </TableCell>
                    <TableCell className="font-medium whitespace-nowrap">
                      {t.fio ?? "—"}
                    </TableCell>
                    <TableCell className="whitespace-nowrap">
                      {t.organization ?? "—"}
                    </TableCell>
                    <TableCell className="whitespace-nowrap">
                      {t.phone ?? "—"}
                    </TableCell>
                    <TableCell className="whitespace-nowrap">
                      {t.email_from}
                    </TableCell>
                    <TableCell className="whitespace-nowrap">
                      {t.serial_numbers?.join(", ") ?? "—"}
                    </TableCell>
                    <TableCell className="whitespace-nowrap">
                      {t.device_type ?? "—"}
                    </TableCell>
                    <TableCell>
                      {sentInfo ? (
                        <Badge variant={sentInfo.variant}>
                          {sentInfo.label}
                          {t.confidence != null && (
                            <span className="ml-1 opacity-70">
                              {(t.confidence * 100).toFixed(0)}%
                            </span>
                          )}
                        </Badge>
                      ) : (
                        "—"
                      )}
                    </TableCell>
                    <TableCell className="max-w-[300px] truncate">
                      {t.description ?? "—"}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </div>

      {/* Pagination */}
      <div className="flex items-center gap-4 text-sm text-muted-foreground">
        <span>Записей: {filtered.length}</span>

        <Select
          value={String(pageSize)}
          onValueChange={(v) => {
            setPageSize(Number(v));
            setPage(0);
          }}
        >
          <SelectTrigger className="w-[100px] h-8">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {PAGE_SIZES.map((s) => (
              <SelectItem key={s} value={String(s)}>
                {s} / стр.
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="icon"
            className="h-8 w-8"
            disabled={page === 0}
            onClick={() => setPage(Math.max(0, page - 1))}
          >
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <span className="px-2">
            {page + 1} / {totalPages}
          </span>
          <Button
            variant="outline"
            size="icon"
            className="h-8 w-8"
            disabled={page >= totalPages - 1}
            onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
          >
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
