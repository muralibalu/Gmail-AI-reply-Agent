import { logout } from "../api";

const styles = {
  nav: {
    background: "#fff",
    borderBottom: "1px solid var(--border)",
    padding: "0 24px",
    height: "60px",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    boxShadow: "var(--shadow)",
    position: "sticky",
    top: 0,
    zIndex: 100,
  },
  logo: { fontWeight: 700, fontSize: "1.25rem", color: "var(--primary)" },
  right: { display: "flex", alignItems: "center", gap: "12px" },
  email: { fontSize: "0.85rem", color: "var(--text-muted)" },
};

export default function Navbar({ userEmail, onLogout }) {
  async function handleLogout() {
    try {
      await logout(userEmail);
    } catch (_) {}
    onLogout();
  }

  return (
    <nav style={styles.nav}>
      <span style={styles.logo}>✉️ Draftly</span>
      <div style={styles.right}>
        <span style={styles.email}>{userEmail}</span>
        <button className="btn-ghost" onClick={handleLogout}>Logout</button>
      </div>
    </nav>
  );
}
