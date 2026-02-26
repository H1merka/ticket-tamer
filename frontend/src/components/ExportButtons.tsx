import { getExportUrl } from "../api/client";

interface ExportButtonsProps {
  status?: string;
  category?: string;
}

export function ExportButtons({ status, category }: ExportButtonsProps) {
  const params = { status, category };

  return (
    <div style={{ display: "flex", gap: 8 }}>
      <a
        href={getExportUrl("csv", params)}
        download
        style={btnStyle}
      >
        Экспорт CSV
      </a>
      <a
        href={getExportUrl("xlsx", params)}
        download
        style={btnStyle}
      >
        Экспорт XLSX
      </a>
    </div>
  );
}

const btnStyle: React.CSSProperties = {
  padding: "6px 16px",
  background: "#1976d2",
  color: "#fff",
  borderRadius: 4,
  textDecoration: "none",
  fontSize: 14,
  cursor: "pointer",
};
