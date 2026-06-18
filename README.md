# Origin Medical Meeting Intelligence Pipeline

An AI-powered workflow automation service built for medical teams. It takes raw meeting transcripts, pulls out structured action items using Google Gemini 2.5 Flash, auto-creates Jira tickets for clear tasks, and routes anything ambiguous to Slack for human approval — keeping your project board clean without losing track of anything discussed.

---

## Why This Exists

Medical teams deal with dense, high-stakes meetings where missed action items can delay FDA submissions, client deliverables, or clinical deadlines. Manually reviewing transcripts and creating tickets is slow and error-prone. This pipeline automates the straightforward stuff and escalates only what genuinely needs a human decision.

**Core principle:** Automate what is clear. Escalate what is ambiguous.

---

## How It Works

```
Transcript  -->  Gemini 2.5 Flash  -->  Confidence Evaluation  -->  Jira / Slack
```

1. A user uploads or pastes a meeting transcript through the Next.js frontend.
2. The backend hashes the transcript (SHA-256) and checks for duplicates against SQLite — if it's been processed before, the cached result is returned immediately.
3. The transcript is sent to Gemini 2.5 Flash with a strict Pydantic response schema. Gemini returns structured JSON containing a meeting summary and a list of action items, each with a title, description, assignee, priority, and confidence score.
4. Each action item is passed through the **Review Engine**, which decides whether it can be auto-processed or needs human review. An item is flagged for review if:
   - Confidence is below 80%
   - No specific person is assigned
   - The title or assignee contains vague language ("someone", "the team")
5. Clear, high-confidence tasks get a Jira ticket created automatically via the Jira Cloud REST API.
6. Ambiguous tasks are saved as `PendingReview` records in SQLite and posted to a Slack approval channel as interactive Block Kit cards with Approve/Reject buttons.
7. When a manager clicks Approve in Slack, the webhook hits `/slack/interactions`, the request signature is verified (HMAC-SHA256), and a Jira ticket is created. If they click Reject, the record is marked accordingly and no ticket is created.
8. A final executive summary is posted to a Slack notification channel, breaking down how many tickets were auto-created vs. how many are pending approval.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI, Python 3.11, Uvicorn |
| AI / LLM | Google Gemini 2.5 Flash (structured JSON output) |
| Data Validation | Pydantic, Pydantic Settings |
| Database | SQLite via SQLAlchemy Async ORM + aiosqlite |
| Task Management | Jira Cloud REST API v3 (aiohttp) |
| Notifications | Slack Bot API, Slack Block Kit, Interactive Components |
| Retry Logic | Tenacity (exponential backoff on transient failures) |
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS |
| Containerization | Docker, Docker Compose |
| Testing | pytest, pytest-asyncio, httpx |

---

## Project Structure

```
origin-medical-meeting-intelligence-pipeline/
├── app/
│   ├── main.py               # FastAPI entry point, orchestration endpoints
│   ├── config.py              # Centralized env config (pydantic-settings)
│   ├── database.py            # Async SQLAlchemy engine, session factory
│   ├── models.py              # ORM models: ProcessedMeeting, PendingReview
│   ├── schemas.py             # Pydantic schemas: ActionItem, MeetingExtraction
│   ├── ingestion.py           # Transcript file loading and validation
│   ├── extraction_agent.py    # Gemini API calls with retry logic
│   ├── review_engine.py       # Confidence evaluation and ambiguity detection
│   ├── jira_client.py         # Async Jira ticket creation
│   ├── slack_client.py        # Slack summary + interactive review cards
│   ├── logging_config.py      # Rotating file + stdout logging
│   └── utils.py               # SHA-256 hashing
├── frontend/
│   └── src/app/
│       ├── page.tsx            # Dashboard — drag-and-drop transcript ingestion
│       ├── layout.tsx          # Root layout
│       └── globals.css         # Global styles
├── tests/
│   ├── test_api.py             # API auth and health check tests
│   ├── test_extraction.py      # Pydantic schema validation tests
│   ├── test_review_engine.py   # Confidence and ambiguity logic tests
│   └── test_slack_workflow.py  # Slack signature and payload tests
├── data/
│   ├── transcript.txt          # Sample medical meeting transcript
│   └── pipeline.db             # SQLite database (auto-created)
├── logs/
│   └── pipeline.log            # Rotating application logs
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env
```

---

## Getting Started

### Prerequisites

- **Docker** and **Docker Compose** installed
- **Node.js** v18+ (for the frontend)
- API credentials for Gemini, Jira Cloud, and Slack (see Environment Variables below)

### 1. Set Up Environment Variables

Create a `.env` file in the project root with the following:

```env
# AI
GEMINI_API_KEY=your_gemini_api_key

# Jira Cloud
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=you@example.com
JIRA_API_TOKEN=your_jira_api_token
JIRA_PROJECT_KEY=PROJ

# Slack
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
SLACK_SIGNING_SECRET=your_slack_signing_secret
SLACK_APPROVAL_CHANNEL_ID=C0XXXXXXX
SLACK_NOTIFY_CHANNEL_ID=C0XXXXXXX

# API Security
PIPELINE_API_KEY=your_secret_key

# Pipeline Tuning
CONFIDENCE_THRESHOLD=0.80

# Database (default works out of the box)
DATABASE_URL=sqlite+aiosqlite:///./data/pipeline.db
```

### 2. Start the Backend (Docker)

```bash
docker compose up --build
```

The FastAPI server will be available at `http://localhost:8000`. The SQLite database and log files are persisted via volume mounts to `./data` and `./logs`.

### 3. Set Up Slack Interactivity (ngrok)

For Slack's interactive buttons to reach your local backend:

```bash
ngrok http 8000
```

Copy the HTTPS forwarding URL and go to your Slack App Dashboard:
- Navigate to **Interactivity & Shortcuts**
- Set the Request URL to `https://<your-ngrok-id>.ngrok.io/slack/interactions`
- Save

### 4. Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

The dashboard will be available at `http://localhost:3000`.

### 5. Process a Meeting

1. Open `http://localhost:3000` in your browser.
2. Enter your Pipeline API Key (the `PIPELINE_API_KEY` value from your `.env`) in the header.
3. Drag and drop a `.txt` transcript file into the upload zone, or paste the text directly.
4. Click **Process Meeting**.
5. The dashboard will show how many Jira tickets were auto-created and how many items were sent to Slack for approval. The executive summary appears on the right panel.

A sample transcript is included at `data/transcript.txt` to test with.

---

## API Reference

### `GET /health`
Health check endpoint. Returns `{"status": "ok", "version": "0.1.0"}`.

### `POST /process-meeting`
Main pipeline endpoint. Requires `X-API-Key` header.

**Request body:**
```json
{
  "transcript_text": "Dr. Anand: Rahul, can you own the root cause analysis..."
}
```

**Response:**
```json
{
  "summary": "The team discussed model validation failures, client feedback...",
  "tickets_created": 4,
  "pending_review": 2,
  "status": "processed"
}
```

If the same transcript is submitted again, it returns the cached result with `"status": "already_processed"`.

### `POST /slack/interactions`
Webhook endpoint for Slack interactive components. Handles Approve/Reject button clicks. Verifies request authenticity using HMAC-SHA256 signature validation.

---

## Running Tests

```bash
pytest tests/ -v
```

Tests cover:
- **Schema validation** — verifies Pydantic models reject invalid priorities, out-of-range confidence scores, and empty summaries
- **Review engine logic** — verifies low confidence, missing assignees, and ambiguous ownership all trigger human review
- **API security** — verifies missing/invalid API keys are rejected, health endpoint responds correctly
- **Slack workflow** — verifies invalid signatures are rejected (403), missing payloads return proper errors

---

## Key Design Decisions

**Idempotent processing** — Every transcript is hashed before processing. Duplicate submissions return the cached result immediately, avoiding wasted LLM API calls and duplicate Jira tickets.

**Async everything** — The entire backend is async. Gemini calls, Jira ticket creation, and Slack message posting all use `aiohttp` and `asyncio`, so nothing blocks the event loop during I/O.

**Slack signature verification** — The `/slack/interactions` endpoint verifies every incoming request using Slack's HMAC-SHA256 signing protocol with replay protection (5-minute window). This prevents unauthorized sources from creating Jira tickets through the webhook.

**Retry with backoff** — Both the Gemini extraction and Jira ticket creation use Tenacity with exponential backoff. Gemini retries on 5xx and 429 errors. Jira retries on 429, 500, 502, and 503. Non-retryable errors (auth failures, bad requests) fail immediately.

**Structured LLM output** — Gemini is configured with `response_mime_type="application/json"` and a Pydantic `response_schema`, so the model is constrained to return valid JSON matching the expected structure. The response is then validated again through Pydantic on the application side.

---

## License

This project was built as a demonstration of production-grade AI workflow automation for the medical-tech space.
