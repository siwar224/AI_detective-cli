# AI Detective CLI

AI Detective is a Python incident-investigation platform that transforms application logs into evidence-based diagnostic reports and practical developer actions.

This repository contains two independently installable Python responsibilities:

- the core CLI and analysis engine in `src/ai_detective`;
- the optional Live Gateway in `services/live_gateway`, which connects the separate React dashboard to an already-running backend.

The dedicated frontend is maintained in a separate repository: [AI Detective Frontend](https://github.com/siwar224/AI-detecitve-frontend). The separation keeps backend analysis, HTTP integration and user-interface concerns independent.

## The developer story

Imagine that you are working on a backend project and a request suddenly fails. Your terminal contains database errors, authentication failures, timeouts and warnings from dependent services. Reading the raw output line by line takes time, while sending everything directly to an LLM can produce vague or unsupported answers.

AI Detective creates a controlled investigation path:

1. Analyze a local log file from the CLI, or connect the dashboard to a running backend.
2. Parse and preserve the original evidence, including source line numbers.
3. Calculate deterministic statistics, recurring error groups and useful timeline information.
4. Separate observable facts from probable causes and hypotheses.
5. Optionally ask Groq for a bounded investigation grounded in the available evidence.
6. Optionally enrich recommendations with one bounded Stack Overflow search.
7. Review the proposed actions and copy a professional prompt for one selected error or the complete incident.

The system helps the developer understand what happened and what to verify next. It does not silently change source code, execute arbitrary commands or apply an automatic fix.

## Current architecture

```text
Local log file or already-running backend
                  |
                  v
        Live Gateway (optional FastAPI service)
        - discovers ports 5000/3000
        - accepts a user-provided backend URL
        - connects to an explicit log source
        - protects analysis and prompt requests
                  |
                  v
          Python analysis engine
        - text and JSON parsing
        - deterministic statistics
        - evidence store
        - bounded Groq investigation
        - optional Stack Overflow enrichment
                  |
                  +--------------------+
                  v                    v
         JSON/Markdown report    Separate React dashboard
```

### Core CLI

The core `ai_detective` package remains usable without a browser, HTTP server or LLM provider. Deterministic analysis is the fallback and the source of truth for parsed facts.

### Live Gateway

The gateway is deliberately outside the core CLI package. It does not start, stop or inspect the terminal of another process. It probes `localhost:5000` and `localhost:3000` after the user chooses live mode, or accepts a backend URL entered by the user.

The gateway can:

- verify that an existing backend is reachable;
- connect to an explicit log-source URL;
- read plain text, JSON records, NDJSON or a stream snapshot;
- analyze local JSON/JSONL content sent by the frontend without copying the file into this repository;
- work without requiring the source endpoint to be named `/logs`;
- generate one bounded, copyable resolution prompt;
- return clear errors for unavailable sources, invalid content and rate limits.

The frontend sends no request before the user chooses an input mode. In JSON mode, no backend discovery is performed.

## Main gateway endpoints

The Live Gateway runs on port `8000` by default:

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Verify that the gateway is available. |
| `GET /api/backends/discover` | Check supported local backend candidates. |
| `POST /api/backends/connect` | Validate the selected backend and log source. |
| `POST /api/analyze/source` | Fetch and analyze an HTTP log source. |
| `POST /api/analyze/content` | Analyze JSON or text content provided by the frontend. |
| `POST /api/prompt/generate` | Generate a professional prompt from bounded context. |

The gateway caches identical analyses for a short period and caches generated prompts for a longer period. Prompt generation also has a per-client cooldown to prevent accidental double-clicks and Groq `429 Too Many Requests` responses.

## CLI usage

Analyze a local incident without an LLM:

```powershell
python -m ai_detective analyze .\datasets\incidents\mongodb.log --no-ai
```

Analyze with the optional AI investigation enabled:

```powershell
python -m ai_detective analyze .\datasets\incidents\mongodb.log
```

Export reports to a directory:

```powershell
python -m ai_detective analyze .\datasets\incidents\mongodb.log --output .\reports\
```

The deterministic path remains useful when Groq is unavailable or no API key is configured.

## Installation

Requirements:

- Python 3.11 or newer;
- PowerShell on Windows, or an equivalent shell;
- Node.js 18 or newer only when the separate frontend is used.

Create a virtual environment and install the core project:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Install the optional gateway package:

```powershell
python -m pip install -e ".\services\live_gateway"
Copy-Item .\services\live_gateway\.env.example .\services\live_gateway\.env
```

## Groq and external recommendations

The AI investigation uses Groq for tool-calling and final report generation. The model never receives direct shell access; it can only request the bounded read-only tools described below.

Configure the gateway or CLI environment locally:

```dotenv
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b
AI_DETECTIVE_MAX_ITERATIONS=5
AI_DETECTIVE_MAX_TOOL_CALLS=8
AI_DETECTIVE_MAX_EXTERNAL_CALLS=1
# Optional: STACKEXCHANGE_API_KEY=...
```

Run AI analysis with:

```powershell
python -m ai_detective analyze .\datasets\incidents\mongodb.log
```

Use `--no-ai` for deterministic analysis only. If the key is missing or the provider is unavailable, the report records the limitation and continues with deterministic results.

When **AI + Stack Overflow** is enabled in the dashboard, the investigation performs one bounded Stack Overflow/Stack Exchange lookup for the leading error. The dashboard labels those recommendations and displays their source links. In deterministic mode, recommendations come only from the logs and are not presented as Stack Overflow advice.

## Investigation tools and evidence

The investigator has access to bounded read-only tools:

- `get_error_summary`: inspect recurring errors and their frequencies;
- `get_events_around`: inspect events near a line number or timestamp;
- `search_similar_lines`: find related log messages;
- `search_external_solutions`: search Stack Overflow through the official Stack Exchange API for resolution suggestions related to an existing deterministic error group.

External search results are suggestions, not incident evidence. The final report preserves their URLs and only accepts resolution steps that cite URLs returned by the controlled external tool. No arbitrary shell command, production connection or automatic remediation is exposed to the agent.

The final report can include:

- incident summary;
- parsed event and level statistics;
- repeated error groups and source lines;
- timeline information;
- probable causes with confidence levels;
- supporting and contradicting evidence;
- recommended checks and resolution steps;
- external recommendations clearly separated from incident evidence;
- limitations and unavailable data.

Every evidence reference contains a source line, quote and reason. References are validated against the evidence store before they are accepted in the report.

## Run the Live Gateway

Start the gateway from this repository:

```powershell
python -m uvicorn live_gateway.api:app --app-dir services/live_gateway/src --port 8000
```

The backend being inspected must be started separately on its own port, commonly `5000` or `3000`. The gateway does not launch that backend and does not require it to expose a new `/logs` route.

## Connect the separate frontend

```powershell
git clone https://github.com/siwar224/AI-detecitve-frontend.git
cd AI-detecitve-frontend
npm install
npm run dev
```

The frontend uses `http://127.0.0.1:8000` for the gateway by default. To change it, create `.env.local` in the frontend repository:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000
```

The dashboard supports two explicit input modes:

- **Live backend URL**: discover or enter a backend and analyze its log source;
- **JSON log file**: choose a local JSON/JSONL file and analyze it without backend discovery.

The dashboard displays every detected error occurrence, multiple resolution steps, optional Stack Overflow references and a prompt scoped either to selected errors or to the complete incident.

## Supported log input

The documented text format is available in [`docs/log-format.md`](docs/log-format.md):

```text
TIMESTAMP LEVEL SERVICE [COMPONENT] MESSAGE
```

Example:

```text
2026-10-21T10:15:04Z ERROR api [database] MongoDB connection refused
```

The parser preserves the original line, line number, timestamp when valid, level, service, normalized message and parsing status. JSON logs are supported through the gateway content-analysis path.

## Project structure

```text
AI_detective-cli/
├── src/ai_detective/
│   ├── cli.py                   # command-line interface
│   ├── parser/                  # text and JSON log parsing
│   ├── analyzer/                # deterministic analysis
│   ├── evidence/                # evidence storage and lookup
│   ├── agent/                   # bounded investigation orchestration
│   ├── external/                # optional Stack Exchange lookup
│   ├── llm/                     # provider abstraction and Groq adapter
│   └── models/                  # validated report models
├── services/live_gateway/
│   ├── src/live_gateway/        # optional FastAPI gateway
│   ├── tests/                   # gateway tests
│   └── README.md                # gateway-specific instructions
├── tests/                       # core tests
├── datasets/incidents/          # reproducible sample incidents
├── docs/                        # technical documentation
├── pyproject.toml
├── .env                         # local only, ignored by Git
└── README.md
```

The React frontend is intentionally not part of this Python repository. Keep frontend changes in the dedicated frontend repository and backend/gateway changes here.

## Configuration and security

Keep secrets in local environment files and never commit them:

```dotenv
GROQ_API_KEY=your_key_here
AI_DETECTIVE_ALLOW_REMOTE_SOURCE=false
```

`GROQ_API_KEY` is optional. Remote-source access should stay disabled unless the deployment explicitly requires it and its network policy has been reviewed.

The project follows these principles:

- logs are untrusted data, never instructions for the agent;
- source files are read only and are never modified by analysis;
- the agent has no arbitrary shell, production or remediation access;
- model calls, source fetches, prompt size and investigation iterations are bounded;
- external recommendations are labeled separately from incident evidence;
- secrets are loaded from environment variables and masked before model calls;
- deterministic analysis remains available when the LLM provider is unavailable;
- the local gateway must not be exposed publicly without authentication and network restrictions.

## Testing

Run the core tests:

```powershell
python -m pytest -q
```

Run lint checks when Ruff is installed:

```powershell
ruff check .
```

Run gateway tests when the gateway extras are installed:

```powershell
python -m pytest services/live_gateway/tests -q
```

## Current status

The current version includes:

- deterministic text and JSON-oriented log analysis;
- recurring error and warning statistics;
- evidence-grounded investigation models;
- optional Groq analysis with bounded external enrichment;
- an independently installable Live Gateway for backend discovery and log sources;
- prompt generation with rate protection and short-lived caching;
- a separate React dashboard for live backend and JSON-file workflows;
- reproducible tests for the core and gateway behavior.

## Scope boundaries

AI Detective is a read-only investigation and recommendation tool. It does not:

- apply fixes automatically;
- execute arbitrary commands suggested by an LLM;
- connect directly to production databases;
- replace application monitoring, alerting or incident-management systems;
- guarantee that an external recommendation is correct for every environment.
