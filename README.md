# Origin Medical Meeting Intelligence Pipeline

An AI-powered workflow automation service that ingests medical meeting transcripts, extracts structured action items using Gemini 2.5 Flash, automatically creates Jira tickets for high-confidence tasks, and routes ambiguous tasks to Slack for human approval.

## Quick Start

```bash
cp .env.example .env
# Fill in your API keys in .env
docker-compose up --build
```

## Usage

Submit a transcript for processing:

```bash
curl -X POST http://localhost:8000/process-meeting \
  -H "X-API-Key: your-pipeline-api-key" \
  -H "Content-Type: application/json" \
  -d '{"transcript_path": "data/transcript.txt"}'
```

## Architecture

See [implementation.md](implementation.md) for the full phase-by-phase implementation plan.
