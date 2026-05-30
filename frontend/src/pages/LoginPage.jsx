const s = {
  page: {
    minHeight: "100vh", display: "flex", alignItems: "center",
    justifyContent: "center", background: "var(--bg)",
  },
  card: {
    background: "#fff", padding: "48px 40px", borderRadius: "16px",
    boxShadow: "var(--shadow-md)", textAlign: "center", maxWidth: "400px", width: "100%",
    border: "1px solid var(--border)",
  },
  logo: { fontSize: "2.5rem", marginBottom: "8px" },
  title: { fontSize: "1.6rem", fontWeight: 700, color: "var(--text)", marginBottom: "6px" },
  sub: { color: "var(--text-muted)", fontSize: "0.9rem", marginBottom: "32px" },
  btn: {
    display: "flex", alignItems: "center", justifyContent: "center", gap: "10px",
    width: "100%", padding: "12px", borderRadius: "8px", fontSize: "0.95rem",
    fontWeight: 600, background: "var(--primary)", color: "#fff",
    border: "none", cursor: "pointer",
  },
  hint: { marginTop: "16px", fontSize: "0.78rem", color: "var(--text-muted)" },
};

export default function LoginPage() {
  function handleLogin() {
    window.location.href = "http://localhost:8000/auth/login";
  }

  return (
    <div style={s.page}>
      <div style={s.card}>
        <div style={s.logo}>✉️</div>
        <div style={s.title}>Draftly</div>
        <p style={s.sub}>AI-powered Gmail reply drafting.<br />Review and approve before anything is sent.</p>
        <button style={s.btn} onClick={handleLogin}>
          <svg width="18" height="18" viewBox="0 0 48 48" fill="none">
            <path d="M44.5 20H24v8.5h11.8C34.7 33.9 30.1 37 24 37c-7.2 0-13-5.8-13-13s5.8-13 13-13c3.1 0 5.9 1.1 8.1 2.9l6.4-6.4C34.6 4.1 29.6 2 24 2 11.8 2 2 11.8 2 24s9.8 22 22 22c11 0 21-8 21-22 0-1.3-.2-2.7-.5-4z" fill="#FFC107"/>
            <path d="M6.3 14.7l7.4 5.4C15.5 17 19.5 14 24 14c3.1 0 5.9 1.1 8.1 2.9l6.4-6.4C34.6 4.1 29.6 2 24 2 16.3 2 9.7 7.4 6.3 14.7z" fill="#FF3D00"/>
            <path d="M24 46c5.5 0 10.4-1.9 14.2-5.1l-6.6-5.6C29.6 37 26.9 38 24 38c-6 0-10.6-3-11.8-8.4L4.7 35c3.3 7.1 10.1 11 19.3 11z" fill="#4CAF50"/>
            <path d="M44.5 20H24v8.5h11.8c-1 3-3.2 5.3-6 6.8l6.6 5.6C40.4 37.4 45 31.4 45 24c0-1.3-.2-2.7-.5-4z" fill="#1976D2"/>
          </svg>
          Sign in with Google
        </button>
        <p style={s.hint}>Only Gmail read &amp; send permissions are requested.</p>
      </div>
    </div>
  );
}
