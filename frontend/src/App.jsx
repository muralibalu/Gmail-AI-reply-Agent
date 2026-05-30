import { useState, useEffect } from "react";
import LoginPage from "./pages/LoginPage";
import Dashboard from "./pages/Dashboard";

export default function App() {
  const [userEmail, setUserEmail] = useState(() => localStorage.getItem("draftly_email") || "");

  // Pick up email from OAuth callback redirect (?email=foo@bar.com)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const email = params.get("email");
    if (email) {
      setUserEmail(email);
      localStorage.setItem("draftly_email", email);
      window.history.replaceState({}, "", "/");
    }
  }, []);

  function handleLogout() {
    localStorage.removeItem("draftly_email");
    setUserEmail("");
  }

  if (!userEmail) return <LoginPage />;
  return <Dashboard userEmail={userEmail} onLogout={handleLogout} />;
}
