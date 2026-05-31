const colors = {
  pending:  { bg: "#fef9c3", color: "#854d0e" },
  approved: { bg: "#dcfce7", color: "#166534" },
  edited:   { bg: "#dbeafe", color: "#1e40af" },
  rejected: { bg: "#fee2e2", color: "#991b1b" },
  sent:     { bg: "#f0fdf4", color: "#15803d" },
  failed:   { bg: "#fce7f3", color: "#9d174d" },
};

export default function StatusBadge({ status }) {
  const s = colors[status] || { bg: "#f1f5f9", color: "#475569" };
  return (
    <span style={{
      ...s,
      padding: "2px 10px",
      borderRadius: "20px",
      fontSize: "0.75rem",
      fontWeight: 600,
      textTransform: "uppercase",
      letterSpacing: "0.04em",
    }}>
      {status}
    </span>
  );
}
