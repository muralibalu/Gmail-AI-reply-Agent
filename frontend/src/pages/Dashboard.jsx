import { useState, useEffect, useCallback } from "react";
import { getDrafts, getInbox, generateDrafts } from "../api";
import DraftCard from "../components/DraftCard";
import EmailSelector from "../components/EmailSelector";
import Navbar from "../components/Navbar";

const STATUS_FILTERS = ["all", "pending", "approved", "edited", "rejected", "sent", "failed"];

const TAB = {
  base: {
    padding: "8px 20px", borderRadius: "8px", fontSize: "0.9rem",
    fontWeight: 600, border: "none", cursor: "pointer", transition: "all 0.15s",
  },
  active: { background: "var(--primary)", color: "#fff" },
  inactive: { background: "transparent", color: "var(--text-muted)" },
};

export default function Dashboard({ userEmail, onLogout }) {
  const [tab, setTab] = useState("drafts");       // "drafts" | "inbox"
  const [drafts, setDrafts] = useState([]);
  const [inbox, setInbox] = useState([]);          // cached — only cleared on manual refresh
  const [inboxFetched, setInboxFetched] = useState(false);
  const [filter, setFilter] = useState("all");
  const [loadingDrafts, setLoadingDrafts] = useState(false);
  const [loadingInbox, setLoadingInbox] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  const fetchDrafts = useCallback(async () => {
    setLoadingDrafts(true);
    setError("");
    try {
      const res = await getDrafts(userEmail);
      setDrafts(res.data);
    } catch {
      setError("Failed to load drafts.");
    } finally {
      setLoadingDrafts(false);
    }
  }, [userEmail]);

  useEffect(() => { fetchDrafts(); }, [fetchDrafts]);

  // Only hits the API when explicitly called (button click or first switch)
  async function fetchInbox() {
    setLoadingInbox(true);
    setError("");
    try {
      const res = await getInbox(userEmail, 20);
      setInbox(res.data);
      setInboxFetched(true);
    } catch {
      setError("Failed to fetch inbox.");
    } finally {
      setLoadingInbox(false);
    }
  }

  // Switch to inbox tab — fetch only if never fetched before
  async function handleSwitchToInbox() {
    setTab("inbox");
    if (!inboxFetched) await fetchInbox();
  }

  // Manual refresh button inside inbox tab
  async function handleRefreshInbox() {
    await fetchInbox();
  }

  // Generate drafts for selected emails
  async function handleGenerate(selected, tone) {
    setGenerating(true);
    setError("");
    try {
      await generateDrafts(userEmail, tone, selected);
      await fetchDrafts();
      // Mark those emails as "already_drafted" in the cached inbox list
      const draftedIds = new Set(selected.map(s => s.message_id));
      setInbox(prev => prev.map(e =>
        draftedIds.has(e.message_id) ? { ...e, already_drafted: true } : e
      ));
      setTab("drafts");
    } catch (e) {
      setError(e?.response?.data?.detail || "Failed to generate drafts.");
    } finally {
      setGenerating(false);
    }
  }

  const filtered = filter === "all" ? drafts : drafts.filter(d => d.status === filter);
  const counts = STATUS_FILTERS.reduce((acc, s) => {
    acc[s] = s === "all" ? drafts.length : drafts.filter(d => d.status === s).length;
    return acc;
  }, {});

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)" }}>
      <Navbar userEmail={userEmail} onLogout={onLogout} />

      <main style={{ maxWidth: "860px", margin: "0 auto", padding: "28px 16px" }}>

        {/* ── Tab bar ─────────────────────────────────────────────────── */}
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          flexWrap: "wrap", gap: "12px", marginBottom: "24px",
        }}>
          {/* Tabs */}
          <div style={{
            display: "flex", gap: "4px", background: "#fff",
            border: "1px solid var(--border)", borderRadius: "10px", padding: "4px",
            boxShadow: "var(--shadow)",
          }}>
            <button
              style={{ ...TAB.base, ...(tab === "drafts" ? TAB.active : TAB.inactive) }}
              onClick={() => setTab("drafts")}
            >
              My Drafts {drafts.length > 0 && (
                <span style={{
                  marginLeft: "6px", background: tab === "drafts" ? "rgba(255,255,255,0.25)" : "var(--border)",
                  borderRadius: "20px", padding: "1px 7px", fontSize: "0.75rem",
                }}>
                  {drafts.length}
                </span>
              )}
            </button>
            <button
              style={{ ...TAB.base, ...(tab === "inbox" ? TAB.active : TAB.inactive) }}
              onClick={handleSwitchToInbox}
              disabled={loadingInbox}
            >
              {loadingInbox && !inboxFetched ? "Loading…" : "✉ New Drafts"}
            </button>
          </div>

          {/* Right-side actions — change based on active tab */}
          {tab === "drafts" && (
            <button className="btn-ghost" onClick={fetchDrafts} disabled={loadingDrafts} style={{ fontSize: "0.85rem" }}>
              {loadingDrafts ? "Refreshing…" : "↻ Refresh"}
            </button>
          )}
          {tab === "inbox" && inboxFetched && (
            <button className="btn-ghost" onClick={handleRefreshInbox} disabled={loadingInbox} style={{ fontSize: "0.85rem" }}>
              {loadingInbox ? "Fetching…" : "↻ Re-fetch inbox"}
            </button>
          )}
        </div>

        {error && (
          <p style={{ color: "var(--danger)", fontSize: "0.85rem", marginBottom: "16px" }}>{error}</p>
        )}

        {/* ── DRAFTS TAB ──────────────────────────────────────────────── */}
        {tab === "drafts" && (
          <>
            {/* Status filter pills */}
            <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginBottom: "20px" }}>
              {STATUS_FILTERS.map(s => (
                <button
                  key={s}
                  onClick={() => setFilter(s)}
                  style={{
                    padding: "5px 12px", borderRadius: "20px", fontSize: "0.8rem",
                    fontWeight: 500, border: "1px solid var(--border)", cursor: "pointer",
                    background: filter === s ? "var(--primary)" : "#fff",
                    color: filter === s ? "#fff" : "var(--text-muted)",
                  }}
                >
                  {s}{counts[s] > 0 ? ` (${counts[s]})` : ""}
                </button>
              ))}
            </div>

            {loadingDrafts ? (
              <p style={{ textAlign: "center", color: "var(--text-muted)", padding: "40px" }}>Loading drafts…</p>
            ) : filtered.length === 0 ? (
              <div style={{
                textAlign: "center", padding: "60px 20px", background: "#fff",
                borderRadius: "var(--radius)", border: "1px solid var(--border)",
              }}>
                <div style={{ fontSize: "2rem", marginBottom: "8px" }}>📭</div>
                <p style={{ color: "var(--text-muted)", marginBottom: "20px" }}>
                  {filter === "all" ? "No drafts yet. Switch to New Drafts to get started." : `No ${filter} drafts.`}
                </p>
                {filter === "all" && (
                  <button className="btn-primary" onClick={handleSwitchToInbox}>
                    ✉ New Drafts
                  </button>
                )}
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
                {filtered.map(d => (
                  <DraftCard key={d.id} draft={d} onUpdated={fetchDrafts} />
                ))}
              </div>
            )}
          </>
        )}

        {/* ── INBOX TAB ───────────────────────────────────────────────── */}
        {tab === "inbox" && (
          <>
            {loadingInbox ? (
              <div style={{ textAlign: "center", padding: "60px", color: "var(--text-muted)" }}>
                <div style={{ fontSize: "1.5rem", marginBottom: "10px" }}>📬</div>
                Fetching your inbox…
              </div>
            ) : inbox.length === 0 ? (
              <div style={{
                textAlign: "center", padding: "60px", background: "#fff",
                borderRadius: "var(--radius)", border: "1px solid var(--border)",
              }}>
                <div style={{ fontSize: "2rem", marginBottom: "8px" }}>📭</div>
                <p style={{ color: "var(--text-muted)", marginBottom: "16px" }}>No unread emails found.</p>
                <button className="btn-ghost" onClick={handleRefreshInbox}>Re-fetch inbox</button>
              </div>
            ) : (
              <EmailSelector
                emails={inbox}
                generating={generating}
                onGenerate={handleGenerate}
                onCancel={() => setTab("drafts")}
              />
            )}
          </>
        )}

      </main>
    </div>
  );
}
