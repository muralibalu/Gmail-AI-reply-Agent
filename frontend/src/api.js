import axios from "axios";

// In Docker: Nginx serves the frontend on port 80 and proxies /auth/ and /drafts/
// to the backend container. Using relative baseURL means API calls go to the
// same origin — Nginx picks them up and forwards automatically.
// Locally (npm run dev): Vite dev server runs on 5173, so we need the full URL.
const baseURL = import.meta.env.VITE_API_URL || "";
const api = axios.create({ baseURL });

export const getDrafts = (userEmail) =>
  api.get("/drafts/", { params: { user_email: userEmail } });

export const getInbox = (userEmail, maxResults = 20) =>
  api.get("/drafts/inbox", { params: { user_email: userEmail, max_results: maxResults } });

// selected = [{ message_id, instructions }]
export const generateDrafts = (userEmail, tone, selected) =>
  api.post("/drafts/generate", { user_email: userEmail, tone, selected });

export const editDraft = (id, draftBody) =>
  api.patch(`/drafts/${id}/edit`, { draft_body: draftBody });

export const regenerateDraft = (id, instructions) =>
  api.post(`/drafts/${id}/regenerate`, { instructions });

export const approveDraft = (id) => api.post(`/drafts/${id}/approve`);

export const rejectDraft = (id) => api.post(`/drafts/${id}/reject`);

export const sendDraft = (id) => api.post(`/drafts/${id}/send`);

export const logout = (userEmail) =>
  api.post("/auth/logout", null, { params: { user_email: userEmail } });
