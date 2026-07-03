# AI Interview Agent

AI Interview Agent is an MVP for running structured, resume-aware technical interviews. It accepts a candidate resume, extracts text, generates a role-specific interview flow, runs a chat-style interview, evaluates answers, and stores a final report for admin review.

The implementation follows the design in `docs/DESIGN.md`: a React/Vite frontend, a FastAPI backend, SQLite persistence, PDF/DOCX/TXT resume parsing, and an optional provider-neutral LLM layer with deterministic fallback behavior for demos.

## Features

- Candidate resume upload for PDF, DOCX, and TXT files
- Resume text extraction and structured candidate profile storage
- Candidate profile fields for name, email, skills, projects, experience, education, and technologies
- Role and difficulty-aware interview plan generation
- Chat-based interview flow with one question shown at a time
- Follow-up prompts for short or vague answers
- Answer scoring on a 1 to 5 scale with short feedback
- Final report generation with recommendation, strengths, weaknesses, and skill scores
- Candidate-facing report page for completed interviews
- Admin dashboard for completed interviews
- SQLite-backed persistence for candidates, interviews, answers, reports, and access tokens

## Project Structure

```text
backend/
  app/
    api/          FastAPI routers and auth dependencies
    core/         Runtime configuration and security helpers
    db/           SQLAlchemy engine/session setup
    models/       SQLAlchemy models
    services/     Resume parsing, LLM calls, interview logic, reports
frontend/
  src/            React application
docs/
  DESIGN.md      Product and architecture design document
```

## Backend Setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item ..\.env.example .env
```

Edit `backend/.env` before starting the API. Admin login is disabled until `ADMIN_PASSWORD` or `ADMIN_PASSWORD_HASH` and `AUTH_SECRET_KEY` are configured.

```powershell
uvicorn app.main:app --reload --port 8001
```

The health check is available at `http://127.0.0.1:8001/health`.

## Frontend Setup

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Open the Vite URL, usually `http://localhost:5173`.

## Environment Variables

Backend variables are documented in `.env.example`. The most important security settings are:

- `ADMIN_PASSWORD` or `ADMIN_PASSWORD_HASH`: admin login credential
- `AUTH_SECRET_KEY`: signing key for admin bearer tokens
- `BACKEND_CORS_ORIGINS`: comma-separated list of allowed frontend origins
- `CANDIDATE_TOKEN_HOURS`: candidate interview token lifetime
- `MAX_RESUME_UPLOAD_BYTES`: upload size cap
- `LLM_PROVIDER`: `mock`, `openai`, `azure_openai`, or `claude`
- `OPENAI_API_KEY` / `OPENAI_MODEL`: OpenAI chat-completions configuration
- `AZURE_OPENAI_API_URL` / `AZURE_OPENAI_API_KEY` / `AZURE_OPENAI_DEPLOYMENT`: Azure OpenAI configuration
- `CLAUDE_API_URL` / `CLAUDE_API_KEY`: legacy Claude-compatible endpoint configuration

Frontend variables are documented in `frontend/.env.example`.

## API Overview

- `POST /api/resume/upload`: upload and parse a PDF, DOCX, or TXT resume; returns a structured candidate profile
- `POST /api/interview/plan`: generate a private interview plan
- `POST /api/interview/start`: create an interview session and return the first question
- `POST /api/interview/answer`: submit an answer, evaluate it, and receive the next question or follow-up
- `POST /api/interview/end`: explicitly end an interview, compute scores, persist a report, and return the report payload
- `GET /api/reports/{report_id}`: return a saved report by `reports.id` for candidate display
- `GET /api/admin/interviews`: list completed interviews for admins
- `GET /api/admin/interviews/{interview_id}`: view report and answer details
- `POST /api/auth/admin/login`: issue an admin bearer token

The candidate report page is available at `/reports/:reportId` after an interview completes. The admin dashboard remains available at `/admin`.

## Security Notes

- No default admin password or signing secret is accepted.
- Candidate access tokens are random, hashed in the database, and expire.
- Resume uploads are size-limited, parsed from a temporary file, then removed from disk.
- Admin tokens are stored in browser session storage by the frontend.
- CORS origins are configurable and should be restricted in deployed environments.
- LLM integration is optional; if it is not configured or `LLM_PROVIDER=mock`, the app uses fallback profile extraction, interview generation, scoring, and report logic.

## SQLite Schema Notes

The backend uses `Base.metadata.create_all()` plus a small SQLite-only column sync for the MVP candidate profile fields. Existing local databases keep their data and receive nullable/default columns for `email`, `projects`, `experience`, `education`, and `technologies` on startup. For broader schema changes, replace this with Alembic migrations.

## Development Checks

```powershell
cd frontend
npm run build
```

```powershell
cd backend
python -m compileall app
```

## Current Scope

This is a proof-of-concept MVP for early technical screening. Future extensions from the design doc include recruiter analytics, role-specific rubrics, PostgreSQL migration, voice/video interviews, proctoring, and multi-round workflows.
