# Quiet Call AI — Backend

FastAPI async backend for **Quiet Call AI**, a voice assistant SaaS that automates repetitive phone calls using AI (
OpenAI Realtime for end-to-end audio, OpenAI Chat/STT/TTS for fallback, Twilio for VoIP).

Repositories:

- Backend (this repo) —
  GitHub: [Gojinevschi04/quiet-call-ai-backend](https://github.com/Gojinevschi04/quiet-call-ai-backend) · UTM DISA
  mirror: [ana.gojinevschi/quiet-call-ai](https://disa.codestorage.space/ana.gojinevschi/quiet-call-ai)
- Frontend — GitHub: [Gojinevschi04/quiet-call-ai-frontend](https://github.com/Gojinevschi04/quiet-call-ai-frontend) ·
  UTM DISA
  mirror: [ana.gojinevschi/quiet-call-ai-frontend](https://disa.codestorage.space/ana.gojinevschi/quiet-call-ai-frontend)

---

## Tech Stack

| Technology                | Purpose                                                                    |
|---------------------------|----------------------------------------------------------------------------|
| **Python 3.13**           | Language                                                                   |
| **FastAPI**               | Async web framework                                                        |
| **SQLModel + SQLAlchemy** | ORM (async, with asyncpg driver)                                           |
| **PostgreSQL 17**         | Database (via Docker)                                                      |
| **Alembic**               | Database migrations                                                        |
| **Poetry**                | Dependency management                                                      |
| **PyJWT**                 | JWT authentication (HS256)                                                 |
| **Twilio**                | VoIP — outbound calls + Media Streams (bidirectional audio over WebSocket) |
| **OpenAI Realtime API**   | End-to-end voice agent (`gpt-realtime`, μ-law 8kHz, semantic VAD)          |
| **OpenAI Chat/STT/TTS**   | Legacy dialog path, summaries, outcome classification                      |
| **aiosmtplib**            | Async email notifications (branded templates, en/ru/ro)                    |
| **httpx**                 | Outbound webhook dispatcher                                                |
| **WebSockets**            | Twilio Media Streams + real-time call events to the UI                     |
| **Black + Ruff + MyPy**   | Formatting, linting, type checking                                         |

---

## Features

- **End-to-end voice agent via OpenAI Realtime + Twilio Media Streams** — bidirectional audio streaming,
  semantic VAD, sub-second latency, natural barge-in. Toggleable via `USE_REALTIME_API` flag.
- **Legacy `<Gather>`/`<Say>` webhook path** — preserved as a fallback for environments that cannot terminate
  WebSockets; auto-selected on retry when Realtime init fails (error tagged `[REALTIME_INIT_FAILED]`).
- **Voicemail detection (AMD)** — Twilio Answering Machine Detection hangs up automatically when
  `AnsweredBy=machine_*` arrives on the status webhook.
- **Concurrency cap** — process-local semaphore gates outbound calls (`MAX_CONCURRENT_CALLS`).
- **Exponential backoff retry** — failed tasks with retryable errors retry after 1 → 5 → 30 → 120 minutes,
  max 4 attempts. `retry_count` + `next_retry_at` columns on `Task`.
- **Prior-attempt context on retry** — the system prompt includes the previous transcript so the agent
  resumes rather than re-introducing itself.
- **Compliance guards** — AI disclosure baked into the prompt, max call duration watchdog,
  business-hours window (09:00–20:00 by default).
- **Dual-channel recording** — agent on the left channel, caller on the right.
- **Per-phone + per-user rate limits** — `MAX_CALLS_PER_PHONE_PER_DAY`, `MAX_CALLS_PER_USER_PER_DAY`
  (admins exempt).
- **Token tracking** — per-call input/output audio + text token columns on `CallSession`, surfaced in the
  admin extended-stats chart and in `GET /users/me/usage` with estimated USD cost.
- **Task duplication** — clone a task's template + slot data to a new phone number.
- **User feedback** — 1-5 rating + optional comment on completed/failed tasks.
- **Admin listen-in** — admins can subscribe to any in-progress call's transcript WebSocket.
- **Audit log** — every task create/edit/cancel/execute/retry/rate/duplicate is recorded and viewable by admins.
- **Outbound webhooks** — users configure `webhook_url` on their profile; JSON payload POSTed on every
  terminal task status (fire-and-forget, 10 s timeout).
- **Multi-language** — English, Russian, Romanian for templates, Twilio TTS/STT voices, and emails.
- **Real-time UI updates** — WebSocket stream of call events (dialing, answered, each turn, call ended).
- **CSV export** — users export their tasks as CSV.
- **Notification preferences** — users toggle email notifications on/off.
- **Post-call processing** — summary generation, email notification, local recording archival (parallel).
- **Admin panel** — system stats, extended analytics (success rate per template), user / task management,
  audit log.
- **Rate limiting** — per-IP request throttling middleware.
- **726 tests** — unit + integration, 83% coverage.

---

## Getting Started

### Prerequisites

- **Python 3.13**
- **Poetry** (`pip install poetry`)
- **Docker** (for PostgreSQL)
- **ngrok** (for receiving Twilio webhooks / Media Streams during local development)

### Installation

```bash
# Clone the repo (GitHub)
git clone https://github.com/Gojinevschi04/quiet-call-ai-backend.git
cd quiet-call-ai-backend

# Or clone from the UTM DISA mirror
# git clone https://disa.codestorage.space/ana.gojinevschi/quiet-call-ai.git
# cd quiet-call-ai

# Install dependencies
poetry install

# Create environment file and fill in your credentials
cp .env.example .env
```

### Start with Docker (recommended)

```bash
# Start everything (Postgres + API + Worker). Migrations run automatically on API startup.
make app.start

# Seed templates (first time only)
make db.seed

# (Optional) Seed demo users + tasks for testing
make db.seed.demo
```

This starts 3 containers:

- **quiet_call_api** — FastAPI server at `http://localhost:8000`
- **quiet_call_worker** — Background task scheduler
- **quiet_call_db** — PostgreSQL database

API docs: `http://localhost:8000/docs`

> **Note:** For real outbound calls, `BASE_URL` must be a publicly reachable URL (Twilio needs to open
> HTTP callbacks and WebSocket Media Streams back to the backend). Run `ngrok http 8000` and point
> `BASE_URL` at the ngrok URL before kicking off a call.

### Start locally (without Docker)

```bash
# Start PostgreSQL container only
docker compose up quiet_call_db -d

# Run migrations
make db.up

# Start the server
poetry run python -m app.main

# (In another terminal) Start the worker
poetry run python -m app.worker
```

### Common Commands

```bash
# Docker
make app.start              # Build and start all containers
make app.stop               # Stop all containers
make app.logs               # Follow logs from all containers
make app.logs.api           # Follow API logs only
make app.logs.worker        # Follow worker logs only
make app.test               # Run tests in Docker container

# Database
make db.up                              # Run migrations
make db.down                            # Rollback all migrations
make db.make_migrations m='description' # Generate new Alembic migration
make db.seed                            # Seed dialog templates
make db.seed.demo                       # Seed demo users + tasks

# Code quality
make black.run    # Format code with Black
make ruff.run     # Lint + format with Ruff
make mypy.run     # Type checking

# Tests
poetry run pytest                      # Run all 726 tests
poetry run pytest tests/unit/          # Unit tests only
poetry run pytest tests/integration/   # Integration tests only
```

---

## Project Structure

```
app/
├── core/                     # Shared infrastructure
│   ├── config.py             # Pydantic BaseSettings (loads .env)
│   ├── constants.py          # Shared constants (timeouts, limits, headers)
│   ├── concurrency.py        # Process-local semaphore (MAX_CONCURRENT_CALLS)
│   ├── database.py           # Async SQLAlchemy engine & session
│   ├── models.py             # BaseModel (id, created_at, updated_at)
│   ├── repositories.py       # Base repository class
│   ├── exceptions.py         # BaseServiceError
│   ├── health.py             # /health endpoint
│   ├── ws_manager.py         # WebSocket event broadcaster (call events pub/sub)
│   ├── audio.py              # Demo audio helpers
│   ├── retry.py              # @async_retry decorator (exponential backoff)
│   ├── logging.py            # Logger setup
│   ├── middleware.py         # Request logging middleware
│   └── rate_limit.py         # Per-IP rate limiting middleware
│
├── modules/                  # Feature modules (Views → Service → Repository)
│   ├── auth/                 # JWT auth (login, register, refresh, password reset)
│   ├── users/                # Profile, notification prefs, webhook URL, usage endpoint
│   ├── files/                # Generic file upload/download (utility module)
│   ├── tasks/                # Task CRUD + lifecycle + rate + duplicate + CSV export
│   ├── templates/            # Dialog templates (admin CRUD, multi-language)
│   ├── calls/                # Call sessions, transcripts, recordings, pricing, WebSocket
│   ├── admin/                # System stats, extended analytics, user/task management
│   ├── audit/                # Audit log (every task action recorded, admin-only read)
│   ├── scheduler/            # Worker scheduler (due tasks, retry, stuck-in-progress cleanup)
│   ├── notifications/        # Email service + post-call processor + webhook dispatcher
│   ├── feedback/             # Contact form → email forwarding
│   └── webhooks/             # Twilio HTTP callbacks + Media Streams WebSocket handler
│
├── integrations/             # External service adapters
│   ├── interfaces.py         # IVoiceProvider, ILLMProvider (abstract)
│   ├── twilio_adapter.py     # Twilio VoIP (call, gather, hangup, recording, language config)
│   ├── openai_adapter.py     # OpenAI STT/TTS/Chat (Whisper, nova, GPT-4o-mini)
│   ├── realtime_call_manager.py  # Kicks off realtime calls via <Connect><Stream> TwiML
│   ├── realtime_bridge.py    # Bidirectional audio pump Twilio ⇄ OpenAI Realtime WebSocket
│   ├── prompt_builder.py     # System prompt construction (AI disclosure, prior context, guards)
│   ├── call_manager.py       # Legacy webhook-driven dialog loop (Gather/Say)
│   └── conversation.py       # Dialog state (turns, intents, history) for the legacy path
│
├── scripts/
│   ├── seed_templates.py     # Seed 20+ dialog templates (en/ru/ro)
│   ├── seed_demo.py          # Seed demo users + tasks
│   └── constants.py          # Seed data constants
│
├── worker.py                 # Background scheduler process entrypoint
└── main.py                   # FastAPI app factory + router registration

migrations/                   # Alembic migrations
tests/
├── unit/                     # Unit tests (mocked DB sessions)
└── integration/              # Integration tests (HTTP client, patched services)
```

---

## Architecture

```
Client (FE) → FastAPI Router (views.py)
                   ↓
              Service (service.py) — business logic
                   ↓
              Repository (repository.py) — data access
                   ↓
              SQLModel / PostgreSQL
```

### Call Execution Flow — Realtime path (default)

```
User clicks Execute → POST /tasks/{id}/execute (returns immediately)
  ↓ (background, gated by MAX_CONCURRENT_CALLS semaphore)
RealtimeCallManager.execute_task()
  → Set status IN_PROGRESS + emit WS "status_change" / "dialing"
  → Create CallSession row
  → TwilioAdapter.create_call(to=phone, twiml=<Connect><Stream url="wss://.../ws/media-stream">)
    (TwiML passes only task_id/user_id/language — prompt is too long for Twilio's 4000-char limit)
  ↓
Twilio opens Media Stream WebSocket at /ws/media-stream
  ↓
media_stream handler:
  - Waits for "start" event, extracts task_id/user_id/language
  - Rebuilds system prompt server-side from DB (template + slot_data + prior-attempt transcript)
  - Starts RealtimeBridge:
      • Opens WebSocket to OpenAI Realtime API (gpt-realtime, semantic_vad)
      • Pipes μ-law 8 kHz audio both ways (no DSP)
      • Tracks token usage per response.done event
      • Enforces max duration watchdog + idle nudges + barge-in (truncate + clear)
  - Agent calls report_outcome(status, reason) tool when the objective is settled
  - Bridge fires farewell, drains audio, calls TwilioAdapter.hangup()
  ↓
Twilio closes the stream → _finalize_call():
  - Persist LogLine rows from the transcript buffer
  - Fetch Twilio recording URL (dual-channel) + store token counts
  - If outcome missing → LLM classifies from transcript
  - Generate LLM summary in the call's language
  - Tag [REALTIME_INIT_FAILED] if init step failed (triggers legacy-path retry next time)
  - Emit "call_ended" on UI WebSocket
  - PostCallProcessor: email notification + outbound webhook (if user configured one) + local recording archival
```

### Legacy path (`USE_REALTIME_API=false`)

Uses Twilio `<Gather>`/`<Say>` + HTTP webhook callbacks + separate OpenAI chat completions per turn.
Higher latency (~3 s per turn) but doesn't require inbound WebSocket connectivity. Automatically used
for retries after `[REALTIME_INIT_FAILED]`.

### WebSocket Events (`/ws/calls/{task_id}`)

Connect: `ws://host/ws/calls/{task_id}?token=JWT`

| Event                | Data                              | When                       |
|----------------------|-----------------------------------|----------------------------|
| `status_change`      | `{status}`                        | Task moves to IN_PROGRESS  |
| `dialing`            | `{phone}`                         | Call initiated             |
| `call_answered`      | —                                 | Interlocutor picks up      |
| `message`            | `{speaker, text, intent?}`        | Each transcript delta      |
| `generating_summary` | —                                 | Call ended, AI summarizing |
| `call_ended`         | `{status, summary, error_reason}` | Final result               |

Owners see only their own tasks. Admins can subscribe to any task.

---

## API Endpoints (53 total)

### Auth (`/auth`) — Public

| Method | Endpoint                       | Description                                       |
|--------|--------------------------------|---------------------------------------------------|
| POST   | `/auth/register`               | Create account, send welcome email, return tokens |
| POST   | `/auth/login`                  | Get JWT access + refresh tokens                   |
| POST   | `/auth/refresh`                | Refresh access token                              |
| POST   | `/auth/reset-password`         | Request password reset email                      |
| POST   | `/auth/reset-password/confirm` | Confirm password reset                            |

### Users (`/users`) — Authenticated

| Method | Endpoint                    | Description                                                  |
|--------|-----------------------------|--------------------------------------------------------------|
| GET    | `/users/me`                 | Get profile (email, phone, notification pref, `webhook_url`) |
| GET    | `/users/me/usage`           | Aggregate token counts + estimated USD cost for current user |
| PUT    | `/users/me`                 | Update email / phone / notification toggle / webhook URL     |
| POST   | `/users/me/change-password` | Change password (requires reauth)                            |

### Users admin (`/users`) — Admin only

| Method | Endpoint      | Description                |
|--------|---------------|----------------------------|
| POST   | `/users/`     | Create user                |
| GET    | `/users/`     | List all users (paginated) |
| GET    | `/users/{id}` | User detail                |
| PUT    | `/users/{id}` | Update user                |
| DELETE | `/users/{id}` | Delete user (cascade)      |

### Tasks (`/tasks`) — Authenticated

| Method | Endpoint                | Description                                                     |
|--------|-------------------------|-----------------------------------------------------------------|
| POST   | `/tasks/`               | Create a new call task                                          |
| GET    | `/tasks/`               | List tasks (status filter, pagination)                          |
| GET    | `/tasks/export`         | Export tasks as CSV download                                    |
| GET    | `/tasks/stats`          | Task counts by status                                           |
| GET    | `/tasks/{id}`           | Task detail (includes `template_name`, retry info, user rating) |
| PUT    | `/tasks/{id}`           | Edit pending/scheduled task                                     |
| POST   | `/tasks/{id}/cancel`    | Cancel task (admin can cancel any)                              |
| POST   | `/tasks/{id}/rate`      | Rate a completed/failed task (1-5 + comment)                    |
| POST   | `/tasks/{id}/duplicate` | Clone task's template + slot_data for a new phone number        |
| POST   | `/tasks/{id}/retry`     | Retry a failed task manually                                    |
| POST   | `/tasks/{id}/execute`   | Execute task (non-blocking, admin can execute any)              |

### Calls (`/tasks`) — Authenticated

| Method | Endpoint                          | Description                                              |
|--------|-----------------------------------|----------------------------------------------------------|
| GET    | `/tasks/{id}/transcript`          | Structured transcript (session + log lines)              |
| GET    | `/tasks/{id}/transcript/download` | Download transcript as .txt                              |
| GET    | `/tasks/{id}/session`             | Call session metadata (duration, recording URI, tokens)  |
| GET    | `/tasks/{id}/recording`           | Stream/download call recording (local MP3 or Twilio URL) |

### Templates (`/templates`) — Mixed

| Method | Endpoint          | Description                  |
|--------|-------------------|------------------------------|
| GET    | `/templates/`     | List templates (user)        |
| GET    | `/templates/{id}` | Template detail (user)       |
| POST   | `/templates/`     | Create template (admin)      |
| PUT    | `/templates/{id}` | Update template (admin)      |
| DELETE | `/templates/{id}` | Soft-delete template (admin) |

### Admin (`/admin`) — Admin only

| Method | Endpoint                | Description                                          |
|--------|-------------------------|------------------------------------------------------|
| GET    | `/admin/stats`          | System stats (users, tasks, calls)                   |
| GET    | `/admin/stats/extended` | Extended analytics (success rate per template, etc.) |
| GET    | `/admin/users`          | List users (paginated)                               |
| GET    | `/admin/tasks`          | List all tasks (paginated, status filter)            |
| PUT    | `/admin/users/{id}`     | Update user role                                     |
| DELETE | `/admin/users/{id}`     | Delete user (cascade)                                |
| GET    | `/admin/audit/`         | List audit log entries (paginated)                   |

### Files (`/files`) — Authenticated (utility module)

| Method | Endpoint               | Description   |
|--------|------------------------|---------------|
| POST   | `/files/upload`        | Upload a file |
| GET    | `/files/`              | List files    |
| GET    | `/files/{id}`          | File metadata |
| GET    | `/files/{id}/download` | Download file |
| DELETE | `/files/{id}`          | Delete file   |

### WebSocket

| Endpoint                           | Description                                                                 |
|------------------------------------|-----------------------------------------------------------------------------|
| `ws /ws/calls/{task_id}?token=JWT` | Real-time call event stream (owner + admins)                                |
| `ws /ws/media-stream`              | Twilio Media Stream — bidirectional audio bridge (Twilio ⇄ OpenAI Realtime) |

### Other — Public

| Method | Endpoint                         | Description                                        |
|--------|----------------------------------|----------------------------------------------------|
| POST   | `/feedback/`                     | Submit feedback (emailed to admins)                |
| GET    | `/health`                        | Health check (DB connectivity + version)           |
| POST   | `/webhooks/calls/{id}`           | Twilio initial callback                            |
| POST   | `/webhooks/calls/{id}/gather`    | Twilio speech result (legacy path)                 |
| POST   | `/webhooks/calls/{id}/status`    | Twilio call status (voicemail detection, duration) |
| POST   | `/webhooks/calls/{id}/recording` | Twilio recording URL                               |

---

## Database Models (at a glance)

| Model              | Table           | Key fields                                                                                                                                                                 |
|--------------------|-----------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **User**           | user            | email, role, hashed_password, phone_number, email_notifications, **webhook_url**                                                                                           |
| **Task**           | task            | target_phone, status, template_id, user_id, slot_data, scheduled_time, summary, error_reason, **retry_count**, **next_retry_at**, **user_rating**, **user_rating_comment** |
| **DialogTemplate** | dialog_template | name, base_script, required_slots, language (en/ru/ro), is_active                                                                                                          |
| **CallSession**    | call_session    | task_id, start_time, duration, recording_uri, local_recording_path, **input_audio_tokens**, **output_audio_tokens**, **input_text_tokens**, **output_text_tokens**         |
| **LogLine**        | log_line        | session_id, timestamp, speaker, text, detected_intent                                                                                                                      |
| **AuditLog**       | audit_log       | user_id, action, target_type, target_id, details                                                                                                                           |
| **File**           | file            | filename, file_path, file_size, file_type, user_id                                                                                                                         |

All models inherit `BaseModel` (provides `id`, `created_at`, `updated_at`). Bold fields were added
post-v1 as features shipped.

---

## Environment Variables

| Variable                                                                                              | Description                                                                                       |
|-------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------|
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASS`                                                 | PostgreSQL connection                                                                             |
| `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | JWT auth config                                                                                   |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`                                      | Twilio VoIP                                                                                       |
| `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_TTS_MODEL`, `OPENAI_TTS_VOICE`, `OPENAI_STT_MODEL`          | OpenAI (legacy path + summaries)                                                                  |
| `USE_REALTIME_API`                                                                                    | `true` to use OpenAI Realtime + Twilio Media Streams; `false` for legacy `<Gather>`/`<Say>`       |
| `OPENAI_REALTIME_MODEL`, `OPENAI_REALTIME_VOICE`                                                      | Realtime agent model + voice                                                                      |
| `REALTIME_VAD_MODE`, `REALTIME_VAD_EAGERNESS`                                                         | Voice activity detection settings (`semantic_vad`, eagerness `low`/`medium`/`high`)               |
| `MAX_CONCURRENT_CALLS`                                                                                | Process-local semaphore capping simultaneous outbound calls (default 10)                          |
| `AI_DISCLOSURE_REQUIRED`                                                                              | Require agent to disclose itself as automated in its opening line (EU AI Act / CA SB-1001 / TCPA) |
| `MAX_CALL_DURATION_SECONDS`                                                                           | Watchdog timer before graceful hangup (default 300)                                               |
| `CALL_WINDOW_START_HOUR`, `CALL_WINDOW_END_HOUR`                                                      | Permitted scheduling window, local time (default 9–20)                                            |
| `MAX_CALLS_PER_PHONE_PER_DAY`                                                                         | Anti-spam per target number (default 3)                                                           |
| `MAX_CALLS_PER_USER_PER_DAY`                                                                          | Per-user quota (admins exempt, default 20)                                                        |
| `TEST_PHONE_OVERRIDE`                                                                                 | When set, every call is redirected to this number (demos/testing)                                 |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`                                                | Email (SMTP)                                                                                      |
| `EMAIL_FROM`, `EMAIL_FROM_NAME`, `EMAIL_ENABLED`                                                      | Email sender config                                                                               |
| `FEEDBACK_EMAILS`                                                                                     | Comma-separated emails for feedback forwarding                                                    |
| `BASE_URL`                                                                                            | Backend base URL (used for Twilio callbacks + Media Stream WebSocket URL)                         |
| `CORS_ORIGINS`                                                                                        | Allowed CORS origins (comma-separated)                                                            |
| `RATE_LIMIT_PER_MINUTE`                                                                               | API rate limit per IP (default 60)                                                                |
| `LOG_LEVEL`                                                                                           | Logging level (default INFO)                                                                      |

See `.env.example` for defaults and annotations.

---

## Safety & Reliability

| Guard                          | Setting                                          | Purpose                                                                                              |
|--------------------------------|--------------------------------------------------|------------------------------------------------------------------------------------------------------|
| **AI disclosure**              | `AI_DISCLOSURE_REQUIRED=true`                    | Agent identifies as automated in its first sentence                                                  |
| **Max call duration**          | `MAX_CALL_DURATION_SECONDS`                      | Watchdog triggers graceful farewell + hangup                                                         |
| **Business hours**             | `CALL_WINDOW_START_HOUR`, `CALL_WINDOW_END_HOUR` | Rejects scheduling calls outside the window                                                          |
| **Per-phone rate limit**       | `MAX_CALLS_PER_PHONE_PER_DAY`                    | Blocks excess tasks to the same number in 24 h                                                       |
| **Per-user quota**             | `MAX_CALLS_PER_USER_PER_DAY`                     | Stops a single user from draining credits                                                            |
| **Concurrency cap**            | `MAX_CONCURRENT_CALLS`                           | Process-local semaphore                                                                              |
| **Voicemail detection**        | Twilio AMD                                       | Hangs up automatically when an answering machine is detected                                         |
| **Exponential backoff retry**  | 1 → 5 → 30 → 120 min, max 4 attempts             | Only for errors containing connection / timeout / network / refused / retries / realtime_init_failed |
| **Stuck-in-progress cleanup**  | 10 min                                           | Scheduler flips to FAILED if a call never finalized                                                  |
| **Realtime → legacy fallback** | on `[REALTIME_INIT_FAILED]`                      | Next retry automatically uses the legacy path                                                        |
| **Test phone override**        | `TEST_PHONE_OVERRIDE`                            | Redirects every call to a sandbox number                                                             |

---

## Docker Architecture

```
┌────────────────────┐  ┌────────────────────┐  ┌────────────────────┐
│ quiet_call_frontend│  │  quiet_call_api    │  │ quiet_call_worker  │
│    (nginx:80)      │  │   (uvicorn:8K)     │  │    (scheduler)     │
│    port 3000       │  │    port 8000       │  │    background      │
└─────────┬──────────┘  └─────────┬──────────┘  └─────────┬──────────┘
          │                       │                       │
          └──────────┬────────────┴───────────────────────┘
                     │
              ┌──────▼───────┐
              │ quiet_call_db│
              │  (port 5432) │
              └──────────────┘
```

The API container runs `alembic upgrade head` on startup, so new migrations apply automatically.

---

## Connecting with the Frontend

**With Docker:**

```bash
# Backend (this repo)
make app.start

# Frontend (quiet-call-ai-frontend repo)
make docker.start    # runs at http://localhost:3000
```

**Local development:**

```bash
# Backend
make app.start       # or: poetry run python -m app.main

# Frontend
npm run dev          # runs at http://localhost:5173
```

Demo accounts (after `make db.seed.demo`):

- Admin: `ana.gojinevschi@isa.utm.md` / `admin1234`
- Admin: `annagojinevschi@gmail.com` / `admin1234`
