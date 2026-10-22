# AI Detective Live Gateway

This is a separate optional service. It is deliberately outside the core
`src/ai_detective` CLI package and exists only to detect an already-running
backend and connect the independent React frontend to a log source.

## Install

From the repository root:

```powershell
& .\.venv\Scripts\python.exe -m pip install -e .
& .\.venv\Scripts\python.exe -m pip install -e .\services\live_gateway
Copy-Item .\services\live_gateway\.env.example .\services\live_gateway\.env
```

The gateway does not start, stop or inspect the terminal of another process.
It probes `localhost:5000` and `localhost:3000` automatically. You can also
enter a backend URL and a log-source URL in the dashboard:

```dotenv
AI_DETECTIVE_ALLOW_REMOTE_SOURCE=false
```

The log-source URL can be any HTTP endpoint returning plain text, JSON records,
NDJSON, or a stream snapshot. It does not have to be named `/logs`. A backend
base URL alone is enough to verify that the service is alive, but an accessible
log source is required before AI Detective can analyse errors. The frontend can
also analyse a local `.json` or `.jsonl` file; the file is read in memory and is
never copied into the Python project.

When an incident is found, the dashboard can ask the configured Groq model to
generate one professional, structured prompt that can be copied into another
LLM. This is an explicit button action, not an automatic request.

When `Analyse IA + Stack Overflow` is enabled, the investigation performs one
bounded Stack Overflow/Stack Exchange lookup for the leading error. The
dashboard labels those recommendations and displays their source links. In
deterministic mode, recommendations are derived only from the logs and are not
presented as Stack Overflow advice.

## Run

```powershell
& .\.venv\Scripts\python.exe -m uvicorn live_gateway.api:app --app-dir services/live_gateway/src --port 8000
```

The independent frontend can then use `http://127.0.0.1:8000` through
`VITE_API_BASE_URL`. The gateway exposes discovery, connection and analysis
routes; it never controls the backend process.

## Request protection

The frontend does not re-analyse the source during backend discovery. Discovery
runs every 15 seconds only while no report exists, and analysis is started by
the user or by the initial connection. The gateway also caches an identical
analysis for 10 seconds and caches an identical generated prompt for 5 minutes.
Prompt generation has a five-second per-client cooldown to avoid accidental
double clicks and Groq `429 Too Many Requests` responses.
