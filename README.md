# Draftly — Gmail AI Reply Agent

An AI-powered Gmail assistant that reads your unread emails, generates smart draft replies using GPT-4, and lets you review, edit, and send them — all from a clean React interface.

Built as a capstone project for **Airtribe's Backend Engineering Launchpad**.

---

## What it does

1. **Login with Gmail** — OAuth2 with PKCE. No passwords stored.
2. **Fetch your inbox** — See unread emails with full content before doing anything.
3. **Select + instruct** — Pick which emails to draft replies for. Add per-email instructions like *"keep it short"* or *"mention I'll follow up Friday"*.
4. **AI generates drafts** — All selected emails are processed concurrently. GPT-4o-mini writes replies matching your tone and writing style.
5. **Review before sending** — Edit, approve, reject, or regenerate with new instructions.
6. **Send** — Reply goes out in the original Gmail thread. Double-sends are blocked by an idempotency guard.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Python 3.11 |
| Database | SQLite via SQLAlchemy |
| AI | OpenRouter → GPT-4o-mini (OpenAI-compatible) |
| Auth | Gmail OAuth2 with PKCE |
| Token Security | Fernet symmetric encryption |
| Frontend | React 19 + Vite |
| Web Server | Nginx (Docker) |
| Container | Docker + Docker Compose |

---

## Project Structure

```
├── app/
│   ├── exceptions.py              # Custom exception hierarchy
│   ├── dependencies.py            # FastAPI DI wiring
│   ├── models.py                  # SQLAlchemy ORM models
│   ├── database.py                # DB engine + session
│   ├── config.py                  # Pydantic settings from .env
│   ├── security.py                # Fernet encrypt/decrypt
│   ├── logger.py                  # RotatingFileHandler logger
│   ├── repositories/
│   │   ├── base.py                # Generic BaseRepository[T]
│   │   ├── user_repository.py     # User CRUD + auth checks
│   │   └── draft_repository.py    # Draft CRUD + state updates
│   ├── services/
│   │   ├── auth_service.py        # OAuth2 flow, token exchange
│   │   ├── gmail_service.py       # Gmail API I/O
│   │   ├── ai_service.py          # OpenAI/OpenRouter calls
│   │   └── draft_service.py       # Draft orchestration + state machine
│   ├── auth/
│   │   └── router.py              # /auth/login, /callback, /logout
│   └── drafts/
│       └── router.py              # /drafts/* endpoints
├── frontend/
│   └── src/
│       ├── pages/Dashboard.jsx    # Tab UI — My Drafts / New Drafts
│       ├── components/
│       │   ├── EmailSelector.jsx  # Inbox list + per-email instructions
│       │   └── DraftCard.jsx      # View / Edit / Regenerate / Send
│       └── api.js                 # Axios API client
├── main.py                        # FastAPI app, middleware, routers
├── Dockerfile.backend
├── Dockerfile.frontend
├── docker-compose.yml
├── nginx.conf
└── requirements.txt
```

---

## Architecture — Design Principles

### 1. Layered Architecture
```
HTTP Request
    ↓
Router (thin — schema validation + HTTP only)
    ↓
Service Layer (business logic)
    ↓
Repository Layer (data access only)
    ↓
Database (SQLite)
```

### 2. Custom Exception Hierarchy
All domain errors extend `DraftlyException`. Each exception knows its own HTTP status. Routers call `.to_http()` to convert — keeping HTTP concerns out of business logic.

```python
DraftlyException
├── AuthenticationError        (401)
├── DraftNotFoundError         (404)
├── DraftAlreadySentError      (400)
├── GmailAPIError              (502)
└── AIGenerationError          (500)
```

### 3. Repository Pattern
`BaseRepository[T]` provides generic typed CRUD. Specific repositories add domain queries. No raw DB calls in routers or services — swap SQLite for PostgreSQL by changing one file.

### 4. Async + Concurrency
- `asyncio.gather()` — all selected emails are drafted **simultaneously**, not one by one
- `asyncio.to_thread()` — blocking Gmail API calls offloaded to thread pool
- Inbox fetch + DB lookup run in **parallel** on every inbox request

### 5. Draft State Machine
```
pending → approved → sent
        ↘ edited  ↗
        → rejected
        → failed (after 3 send retries)
```

### 6. Idempotency Guard
Once a send is queued, an idempotency key is written to the draft. Any duplicate send request is rejected immediately — even while the background task is still in-flight.

---

## Git History

| Commit | Description |
|---|---|
| `d5bb015` | Complete app — sync version (baseline before async) |
| `b5e85e4` | Refactor — convert all I/O to async (before/after comparison) |
| `1d77f29` | Refactor — production-ready layered architecture with classes |
| `c093770` | Docker support + idempotency fix |

---

## Setup — Run Locally

### Prerequisites
- Python 3.11+
- Node.js 18+
- A Google Cloud project with Gmail API enabled
- An OpenRouter API key

### 1. Clone and install backend deps
```bash
git clone https://github.com/muralibalu/Gmail-AI-reply-Agent.git
cd Gmail-AI-reply-Agent
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 2. Create `.env`
```env
OPENAI_API_KEY=sk-or-v1-your-openrouter-key
OPENAI_BASE_URL=https://openrouter.ai/api/v1

GMAIL_CLIENT_ID=your-client-id.apps.googleusercontent.com
GMAIL_CLIENT_SECRET=your-client-secret
GMAIL_REDIRECT_URI=http://localhost:8000/auth/callback

ENCRYPTION_KEY=your-fernet-key   # generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
APP_SECRET_KEY=change-me-in-production
```

### 3. Google Cloud Setup
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project → Enable **Gmail API**
3. OAuth consent screen → add scopes: `gmail.readonly`, `gmail.send`, `gmail.modify`, `userinfo.email`, `openid`
4. Create **OAuth 2.0 Client ID** (Web application)
5. Add `http://localhost:8000/auth/callback` as an authorized redirect URI
6. Copy Client ID and Client Secret into `.env`

### 4. Run backend
```bash
uvicorn main:app --reload
```

### 5. Run frontend
```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**

---

## Setup — Run with Docker

### Prerequisites
- [Rancher Desktop](https://rancherdesktop.io) or Docker Desktop

```bash
docker compose up --build
```

Open **http://localhost**

That's it. Docker runs both backend and frontend, connects them, and persists the database between restarts.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/auth/login` | Redirect to Google OAuth2 |
| GET | `/auth/callback` | Handle OAuth callback |
| POST | `/auth/logout` | Revoke tokens + clear session |
| GET | `/drafts/inbox` | Fetch unread emails as previews |
| POST | `/drafts/generate` | Generate AI drafts for selected emails |
| GET | `/drafts/` | List all drafts for a user |
| PATCH | `/drafts/{id}/edit` | Edit draft body |
| POST | `/drafts/{id}/approve` | Approve a draft |
| POST | `/drafts/{id}/reject` | Reject a draft |
| POST | `/drafts/{id}/regenerate` | Regenerate with new instructions |
| POST | `/drafts/{id}/send` | Send draft as Gmail reply |

---

## Environment Variables

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | OpenRouter or OpenAI API key |
| `OPENAI_BASE_URL` | `https://openrouter.ai/api/v1` for OpenRouter |
| `GMAIL_CLIENT_ID` | Google OAuth2 Client ID |
| `GMAIL_CLIENT_SECRET` | Google OAuth2 Client Secret |
| `GMAIL_REDIRECT_URI` | OAuth callback URL |
| `ENCRYPTION_KEY` | Fernet key for encrypting stored tokens |
| `APP_SECRET_KEY` | App secret (change in production) |
| `DB_PATH` | SQLite file path (default: `./draftly.db`) |
