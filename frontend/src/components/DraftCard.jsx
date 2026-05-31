import { useState } from "react";
import StatusBadge from "./StatusBadge";
import { approveDraft, rejectDraft, editDraft, sendDraft, regenerateDraft } from "../api";

const card = {
  background: "var(--surface)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius)",
  boxShadow: "var(--shadow)",
  overflow: "hidden",
};

// mode: "view" | "edit" | "regenerate"
export default function DraftCard({ draft, onUpdated }) {
  const [mode, setMode] = useState("view");
  const [body, setBody] = useState(draft.draft_body);
  const [instructions, setInstructions] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const actionable = ["pending", "edited", "approved"].includes(draft.status);
  const canSend    = ["approved", "edited"].includes(draft.status);
  const canRegen   = draft.status !== "sent";

  async function handle(fn) {
    setLoading(true);
    setError("");
    try {
      await fn();
      onUpdated();
    } catch (e) {
      setError(e?.response?.data?.detail || "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  async function saveEdit() {
    await handle(async () => {
      await editDraft(draft.id, body);
      setMode("view");
    });
  }

  async function submitRegenerate() {
    if (!instructions.trim()) return;
    await handle(async () => {
      await regenerateDraft(draft.id, instructions.trim());
      setInstructions("");
      setMode("view");
    });
  }

  function cancelMode() {
    setMode("view");
    setBody(draft.draft_body);
    setInstructions("");
    setError("");
  }

  return (
    <div style={card}>

      {/* ── Header ──────────────────────────────────────────────────── */}
      <div style={{ padding: "16px 20px 0", display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 8 }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: "0.95rem" }}>{draft.subject || "(no subject)"}</div>
          <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: 2 }}>From: {draft.sender}</div>
        </div>
        <StatusBadge status={draft.status} />
      </div>

      {/* ── Draft body ──────────────────────────────────────────────── */}
      <div style={{ padding: "12px 20px" }}>
        {mode === "edit" ? (
          <textarea
            value={body}
            onChange={e => setBody(e.target.value)}
            rows={6}
            style={{
              width: "100%", resize: "vertical", padding: "10px 12px",
              border: "1px solid var(--primary)", borderRadius: "6px",
              fontSize: "0.9rem", fontFamily: "inherit", lineHeight: 1.6, outline: "none",
            }}
          />
        ) : (
          <p style={{
            background: "var(--bg)", borderRadius: "6px", padding: "12px 14px",
            fontSize: "0.9rem", whiteSpace: "pre-wrap", color: "var(--text)",
            border: "1px solid var(--border)", margin: 0,
          }}>
            {draft.draft_body}
          </p>
        )}
      </div>

      {/* ── Regenerate panel (slides in below body) ─────────────────── */}
      {mode === "regenerate" && (
        <div style={{
          margin: "0 20px 12px", padding: "14px 16px",
          background: "#fefce8", border: "1px solid #fde68a",
          borderRadius: "8px", display: "flex", flexDirection: "column", gap: "10px",
        }}>
          <div style={{ fontSize: "0.8rem", fontWeight: 600, color: "#92400e" }}>
            🤖 Tell AI what to change
          </div>
          <textarea
            autoFocus
            placeholder='e.g. "Make it shorter and more direct" or "Add an apology for the delay" or "Ask for a call instead"'
            value={instructions}
            onChange={e => setInstructions(e.target.value)}
            rows={3}
            style={{
              width: "100%", resize: "vertical", padding: "9px 12px",
              border: "1px solid #fcd34d", borderRadius: "6px",
              fontSize: "0.875rem", fontFamily: "inherit", lineHeight: 1.6,
              background: "#fff", outline: "none",
            }}
            onKeyDown={e => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submitRegenerate();
            }}
          />
          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            <button
              className="btn-primary"
              onClick={submitRegenerate}
              disabled={loading || !instructions.trim()}
            >
              {loading ? "Regenerating…" : "Regenerate"}
            </button>
            <button className="btn-ghost" onClick={cancelMode} disabled={loading}>Cancel</button>
            <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginLeft: "auto" }}>
              ⌘↵ to submit
            </span>
          </div>
        </div>
      )}

      {/* ── Footer: tone + actions ───────────────────────────────────── */}
      <div style={{
        padding: "10px 20px 16px",
        display: "flex", justifyContent: "space-between",
        alignItems: "center", flexWrap: "wrap", gap: "8px",
      }}>
        <span style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
          Tone: <strong>{draft.tone}</strong>
        </span>

        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          {error && (
            <span style={{ fontSize: "0.8rem", color: "var(--danger)", alignSelf: "center" }}>{error}</span>
          )}

          {/* Edit mode buttons */}
          {mode === "edit" && (
            <>
              <button className="btn-primary" onClick={saveEdit} disabled={loading}>Save</button>
              <button className="btn-ghost" onClick={cancelMode}>Cancel</button>
            </>
          )}

          {/* View mode buttons */}
          {mode === "view" && (
            <>
              {canRegen && (
                <button
                  className="btn-ghost"
                  onClick={() => setMode("regenerate")}
                  style={{ color: "#d97706", borderColor: "#fcd34d" }}
                >
                  🔄 Regenerate
                </button>
              )}
              {actionable && mode !== "regenerate" && (
                <button className="btn-ghost" onClick={() => setMode("edit")}>Edit</button>
              )}
              {actionable && (
                <>
                  <button className="btn-success" onClick={() => handle(() => approveDraft(draft.id))} disabled={loading}>Approve</button>
                  <button className="btn-danger"  onClick={() => handle(() => rejectDraft(draft.id))}  disabled={loading}>Reject</button>
                </>
              )}
              {canSend && (
                <button className="btn-primary" onClick={() => handle(() => sendDraft(draft.id))} disabled={loading}>
                  {loading ? "Sending…" : "Send"}
                </button>
              )}
              {draft.status === "sent"   && <span style={{ color: "var(--success)", fontWeight: 600, fontSize: "0.85rem" }}>✓ Sent</span>}
              {draft.status === "failed" && <span style={{ color: "var(--danger)",  fontWeight: 600, fontSize: "0.85rem" }}>✗ Failed — check logs</span>}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
