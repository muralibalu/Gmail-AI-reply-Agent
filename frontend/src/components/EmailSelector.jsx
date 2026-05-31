import { useState } from "react";

const TONES = ["formal", "concise", "friendly"];

export default function EmailSelector({ emails, onGenerate, onCancel, generating }) {
  const [expanded, setExpanded] = useState(null);         // message_id of open email
  const [selected, setSelected] = useState({});           // { message_id: true }
  const [instructions, setInstructions] = useState({});   // { message_id: string }
  const [tone, setTone] = useState("formal");

  const selectable = emails.filter(e => !e.already_drafted);
  const selectedIds = Object.keys(selected).filter(id => selected[id]);
  const allSelected = selectable.length > 0 && selectedIds.length === selectable.length;

  function toggleSelect(id) {
    setSelected(prev => ({ ...prev, [id]: !prev[id] }));
  }

  function toggleAll() {
    if (allSelected) {
      setSelected({});
    } else {
      setSelected(Object.fromEntries(selectable.map(e => [e.message_id, true])));
    }
  }

  function toggleExpand(id) {
    setExpanded(prev => (prev === id ? null : id));
  }

  function handleGenerate() {
    const payload = selectedIds.map(id => ({
      message_id: id,
      instructions: instructions[id] || "",
    }));
    onGenerate(payload, tone);
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>

      {/* ── Toolbar ─────────────────────────────────────────────────── */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        flexWrap: "wrap", gap: "12px",
        background: "#fff", border: "1px solid var(--border)",
        borderRadius: "var(--radius)", padding: "14px 18px", boxShadow: "var(--shadow)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <label style={{ display: "flex", alignItems: "center", gap: "8px", cursor: "pointer", fontSize: "0.9rem", fontWeight: 500 }}>
            <input
              type="checkbox" checked={allSelected} onChange={toggleAll}
              style={{ width: 16, height: 16, cursor: "pointer" }}
            />
            Select all
          </label>
          <span style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
            {selectedIds.length} of {selectable.length} selected
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <label style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Tone</label>
          <select
            value={tone} onChange={e => setTone(e.target.value)}
            style={{ padding: "6px 10px", borderRadius: "6px", border: "1px solid var(--border)", fontSize: "0.85rem" }}
          >
            {TONES.map(t => <option key={t}>{t}</option>)}
          </select>
          <button className="btn-ghost" onClick={onCancel}>Cancel</button>
          <button
            className="btn-primary"
            disabled={selectedIds.length === 0 || generating}
            onClick={handleGenerate}
          >
            {generating ? "Generating…" : `Generate${selectedIds.length > 0 ? ` (${selectedIds.length})` : ""}`}
          </button>
        </div>
      </div>

      {/* ── Email list ──────────────────────────────────────────────── */}
      {emails.map(email => {
        const drafted = email.already_drafted;
        const isSelected = !!selected[email.message_id];
        const isExpanded = expanded === email.message_id;
        const hasInstructions = (instructions[email.message_id] || "").trim().length > 0;

        return (
          <div
            key={email.message_id}
            style={{
              background: "#fff",
              border: `1.5px solid ${isSelected ? "var(--primary)" : "var(--border)"}`,
              borderRadius: "var(--radius)",
              boxShadow: isSelected ? "0 0 0 3px rgba(79,70,229,0.08)" : "var(--shadow)",
              transition: "border-color 0.15s, box-shadow 0.15s",
              overflow: "hidden",
            }}
          >
            {/* ── Email row (always visible) ───────────────────────── */}
            <div style={{
              display: "flex", alignItems: "center", gap: "12px",
              padding: "14px 16px",
              opacity: drafted ? 0.5 : 1,
            }}>
              {/* Checkbox */}
              <input
                type="checkbox"
                checked={isSelected}
                disabled={drafted}
                onChange={() => toggleSelect(email.message_id)}
                onClick={e => e.stopPropagation()}
                style={{ width: 16, height: 16, flexShrink: 0, cursor: drafted ? "default" : "pointer" }}
              />

              {/* Email summary — click to expand */}
              <div
                style={{ flex: 1, minWidth: 0, cursor: drafted ? "default" : "pointer" }}
                onClick={() => !drafted && toggleExpand(email.message_id)}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                  <span style={{ fontWeight: 600, fontSize: "0.9rem" }}>
                    {email.subject}
                  </span>
                  {drafted && (
                    <span style={{ fontSize: "0.72rem", background: "#dbeafe", color: "#1e40af", padding: "2px 8px", borderRadius: "12px", fontWeight: 600 }}>
                      Draft exists
                    </span>
                  )}
                  {hasInstructions && !isExpanded && (
                    <span style={{ fontSize: "0.72rem", background: "#fef9c3", color: "#854d0e", padding: "2px 8px", borderRadius: "12px", fontWeight: 600 }}>
                      Instructions added
                    </span>
                  )}
                </div>
                <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: "2px" }}>
                  {email.sender}
                </div>
                {!isExpanded && (
                  <div style={{ fontSize: "0.82rem", color: "var(--text-muted)", marginTop: "2px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                    {email.snippet || "(no preview)"}
                  </div>
                )}
              </div>

              {/* Expand chevron */}
              {!drafted && (
                <button
                  onClick={() => toggleExpand(email.message_id)}
                  style={{
                    background: "none", border: "none", padding: "4px", cursor: "pointer",
                    color: "var(--text-muted)", fontSize: "1rem", flexShrink: 0,
                    transform: isExpanded ? "rotate(180deg)" : "rotate(0deg)",
                    transition: "transform 0.2s",
                  }}
                  aria-label={isExpanded ? "Collapse" : "Expand"}
                >
                  ▾
                </button>
              )}
            </div>

            {/* ── Expanded panel ───────────────────────────────────── */}
            {isExpanded && (
              <div style={{ borderTop: "1px solid var(--border)", padding: "16px", background: "#fafafa", display: "flex", flexDirection: "column", gap: "14px" }}>

                {/* Full email body */}
                <div>
                  <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-muted)", marginBottom: "6px", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                    Email content
                  </div>
                  <div style={{
                    background: "#fff", border: "1px solid var(--border)", borderRadius: "8px",
                    padding: "12px 14px", fontSize: "0.875rem", lineHeight: 1.7,
                    whiteSpace: "pre-wrap", color: "var(--text)", maxHeight: "260px",
                    overflowY: "auto",
                  }}>
                    {email.body
                      ? email.body
                      : <span style={{ color: "var(--text-muted)" }}>(no content)</span>
                    }
                  </div>
                </div>

                {/* Instructions input */}
                <div>
                  <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "var(--text-muted)", marginBottom: "6px", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                    Instructions for AI <span style={{ fontWeight: 400, textTransform: "none" }}>(optional)</span>
                  </div>
                  <textarea
                    placeholder='e.g. "Decline politely and suggest next week instead" or "Ask for more details about the budget"'
                    value={instructions[email.message_id] || ""}
                    onChange={e => setInstructions(prev => ({ ...prev, [email.message_id]: e.target.value }))}
                    rows={3}
                    style={{
                      width: "100%", padding: "10px 12px", borderRadius: "8px",
                      border: "1px solid var(--border)", fontSize: "0.875rem",
                      fontFamily: "inherit", lineHeight: 1.6, resize: "vertical",
                      background: "#fff", color: "var(--text)",
                    }}
                  />
                </div>

                {/* Quick-select button */}
                <div style={{ display: "flex", gap: "8px" }}>
                  <button
                    className={isSelected ? "btn-danger" : "btn-success"}
                    style={{ fontSize: "0.82rem" }}
                    onClick={() => toggleSelect(email.message_id)}
                  >
                    {isSelected ? "Deselect" : "Select for draft"}
                  </button>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
