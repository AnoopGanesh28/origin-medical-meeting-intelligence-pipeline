"""
Origin Medical Meeting Intelligence Pipeline
FastAPI application entry point.
"""
from fastapi import FastAPI

app = FastAPI(
    title="Origin Medical Meeting Intelligence Pipeline",
    description="AI-powered meeting transcript processor that extracts action items, creates Jira tickets, and routes ambiguous tasks to Slack for human approval.",
    version="0.1.0",
)


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}
