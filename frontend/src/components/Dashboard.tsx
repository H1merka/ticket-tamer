import { useEffect, useState } from "react";
import {
  fetchAnalyticsSummary,
  fetchAnalyticsTimeline,
  type AnalyticsSummary,
  type TimelinePoint,
} from "../api/client";

// Color palettes
const CATEGORY_COLORS: Record<string, string> = {
  неисправность: "#e74c3c",
  калибровка: "#f39c12",
  запрос_документации: "#3498db",
  запрос_доступа: "#2ecc71",
  прочее: "#95a5a6",
};

const SENTIMENT_COLORS: Record<string, string> = {
  позитив: "#27ae60",
  нейтраль: "#7f8c8d",
  негатив: "#c0392b",
};

const STATUS_COLORS: Record<string, string> = {
  new: "#3498db",
  processing: "#f39c12",
  responded: "#27ae60",
  needs_review: "#e74c3c",
  closed: "#95a5a6",
};

export function Dashboard() {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [timeline, setTimeline] = useState<TimelinePoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([fetchAnalyticsSummary(), fetchAnalyticsTimeline(30)])
      .then(([s, t]) => {
        setSummary(s);
        setTimeline(t);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p style={{ textAlign: "center", padding: 40 }}>Загрузка аналитики...</p>;
  if (!summary) return <p style={{ textAlign: "center", padding: 40 }}>Нет данных</p>;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* KPI Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 16 }}>
        <KpiCard label="Всего тикетов" value={summary.total_tickets} />
        <KpiCard
          label="Среднее SLA (мин)"
          value={summary.avg_response_time_minutes ?? "—"}
        />
        <KpiCard
          label="Авто-ответ"
          value={`${(summary.auto_response_rate * 100).toFixed(0)}%`}
        />
        <KpiCard
          label="Требуют проверки"
          value={summary.by_status["needs_review"] ?? 0}
          color="#e74c3c"
        />
      </div>

      {/* Charts row */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
        <ChartCard title="По категориям">
          <HorizontalBar data={summary.by_category} colors={CATEGORY_COLORS} />
        </ChartCard>
        <ChartCard title="По тональности">
          <HorizontalBar data={summary.by_sentiment} colors={SENTIMENT_COLORS} />
        </ChartCard>
        <ChartCard title="По статусу">
          <HorizontalBar data={summary.by_status} colors={STATUS_COLORS} />
        </ChartCard>
      </div>

      {/* Timeline (simple bar chart) */}
      <ChartCard title="Обращения за 30 дней">
        <TimelineChart data={timeline} />
      </ChartCard>

      {/* Top devices */}
      {summary.top_devices.length > 0 && (
        <ChartCard title="Топ-5 приборов">
          <HorizontalBar
            data={Object.fromEntries(summary.top_devices.map((d) => [d.device, d.count]))}
            colors={{}}
            defaultColor="#3498db"
          />
        </ChartCard>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function KpiCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string | number;
  color?: string;
}) {
  return (
    <div
      style={{
        background: "#fff",
        border: "1px solid #e0e0e0",
        borderRadius: 8,
        padding: "16px 20px",
        textAlign: "center",
      }}
    >
      <div style={{ fontSize: 12, color: "#666", marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 700, color: color || "#333" }}>
        {value}
      </div>
    </div>
  );
}

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        background: "#fff",
        border: "1px solid #e0e0e0",
        borderRadius: 8,
        padding: 16,
      }}
    >
      <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>{title}</div>
      {children}
    </div>
  );
}

function HorizontalBar({
  data,
  colors,
  defaultColor,
}: {
  data: Record<string, number>;
  colors: Record<string, string>;
  defaultColor?: string;
}) {
  const max = Math.max(...Object.values(data), 1);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {Object.entries(data).map(([label, value]) => (
        <div key={label} style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div
            style={{ width: 120, fontSize: 12, color: "#555", textAlign: "right", flexShrink: 0 }}
          >
            {label}
          </div>
          <div style={{ flex: 1, background: "#f0f0f0", borderRadius: 4, height: 20 }}>
            <div
              style={{
                width: `${(value / max) * 100}%`,
                height: "100%",
                background: colors[label] || defaultColor || "#888",
                borderRadius: 4,
                minWidth: value > 0 ? 4 : 0,
              }}
            />
          </div>
          <div style={{ width: 36, fontSize: 12, color: "#333", fontWeight: 600 }}>{value}</div>
        </div>
      ))}
    </div>
  );
}

function TimelineChart({ data }: { data: TimelinePoint[] }) {
  if (data.length === 0) return <p style={{ color: "#999", fontSize: 13 }}>Нет данных за период</p>;

  const maxCount = Math.max(...data.map((d) => d.count), 1);
  const barWidth = Math.max(4, Math.floor(700 / data.length) - 2);

  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 2, height: 120, overflow: "auto" }}>
      {data.map((d) => (
        <div
          key={d.date}
          title={`${d.date}: ${d.count} (авто: ${d.auto}, ручн: ${d.manual})`}
          style={{ display: "flex", flexDirection: "column", alignItems: "center" }}
        >
          <div
            style={{
              width: barWidth,
              height: `${(d.count / maxCount) * 100}px`,
              background: "#3498db",
              borderRadius: "2px 2px 0 0",
              position: "relative",
            }}
          >
            {/* Auto portion */}
            <div
              style={{
                position: "absolute",
                bottom: 0,
                width: "100%",
                height: `${(d.auto / (d.count || 1)) * 100}%`,
                background: "#27ae60",
                borderRadius: "0 0 0 0",
              }}
            />
          </div>
          {data.length <= 15 && (
            <div style={{ fontSize: 9, color: "#999", marginTop: 2, transform: "rotate(-45deg)" }}>
              {d.date.slice(5)}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
