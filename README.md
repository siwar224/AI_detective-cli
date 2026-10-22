# AI Detective CLI

AI Detective CLI is a Python command-line agent that investigates technical incidents from application logs and produces structured, evidence-based diagnostic reports.

The project combines deterministic log analysis with a constrained AI investigation layer. Python extracts and verifies observable facts first. The AI can then formulate and compare possible causes, but every important conclusion must be linked to real log evidence.

## Why this project exists

Incident investigation often requires manually searching large log files, identifying repeated failures, reconstructing a timeline and distinguishing symptoms from probable causes. LLMs can accelerate this work, but their answers may contain unsupported assumptions or inaccurate references.

AI Detective CLI is designed to address both problems:

- deterministic analysis provides reproducible facts;
- a read-only investigation agent explores the available evidence;
- structured reports make hypotheses, contradictions and limitations explicit;
- backend validation prevents the model from citing non-existent log lines;
- a `--no-ai` mode makes the deterministic engine usable without an API key.

## Target MVP

The MVP is a standalone terminal application. It does not require a web server, browser interface or production access.

The application will:

1. accept a `.log` or `.txt` file from the command line;
2. validate that the file exists, is readable, non-empty and within the configured size limit;
3. parse each line into a structured `LogEvent` while preserving its original line number;
4. calculate deterministic statistics, repeated errors and an exploitable timeline;
5. store the original evidence for later verification;
6. optionally let an AI investigator query bounded read-only tools;
7. generate up to three ranked hypotheses with supporting and contradicting evidence;
8. validate the final report with Pydantic;
9. export the result as JSON and Markdown.

## Target usage

Once the MVP workflow is implemented, the application will be used as follows:

```bash
python -m ai_detective analyze ./datasets/incidents/mongodb.log
python -m ai_detective analyze ./datasets/incidents/mongodb.log --no-ai
python -m ai_detective analyze ./datasets/incidents/mongodb.log --output ./reports/
```

The deterministic mode is intended to work without an LLM provider or API key.

## Groq configuration

The AI investigation mode uses Groq for tool-calling and final report generation. The model never
receives direct shell access: it can only request the bounded local and external read-only tools
described below.

Create a local environment file from the template and add the API key obtained from the Groq console:

```powershell
Copy-Item .env.example .env
```

Then edit `.env`:

```dotenv
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b
AI_DETECTIVE_MAX_ITERATIONS=5
AI_DETECTIVE_MAX_TOOL_CALLS=8
AI_DETECTIVE_MAX_EXTERNAL_CALLS=1
# Optional: STACKEXCHANGE_API_KEY=...
```

Run the AI investigation with:

```bash
python -m ai_detective analyze ./datasets/incidents/mongodb.log
```

Use `--no-ai` to run only the deterministic pipeline. If the key is missing or the provider is
unavailable, the CLI returns a deterministic report with the reason recorded in `limitations`.

## How the investigation works

```text
Log file
   |
   v
File validation
   |
   v
Log parser -------------> Structured LogEvent objects
   |                                      |
   v                                      v
Deterministic analyzer              Evidence store
   |                                      |
   +------------------+-------------------+
                      v
              Investigation orchestrator
                 |                 |
                 v                 v
          Read-only tools       LLM provider
                 \                 /
                  v               v
                 Validated investigation report
                              |
                    +---------+---------+
                    v                   v
                  JSON              Markdown
```

The LLM is not the source of truth. It receives bounded information, uses explicitly allowed tools and proposes hypotheses. Python remains responsible for parsing, evidence lookup, schema validation and reference verification.

## Read-only investigation tools

The AI investigator will have access to four bounded tools:

- `get_error_summary`: inspect recurring errors and their frequencies;
- `get_events_around`: inspect events near a line number or timestamp;
- `search_similar_lines`: find related log messages.
- `search_external_solutions`: search Stack Overflow through the official Stack Exchange API for
  resolution suggestions related to an existing deterministic error group.

External search results are suggestions, not evidence. The final report preserves their URLs and
only accepts resolution steps that cite URLs returned by the controlled external tool. No arbitrary
shell command, production connection or automatic remediation is exposed to the agent.

The Stack Exchange lookup works without an API key for small tests. An optional request key can be
configured as `STACKEXCHANGE_API_KEY` when a separate API quota is needed.

## Log format

The initial format is intentionally simple and documented in [`docs/log-format.md`](docs/log-format.md):

```text
TIMESTAMP LEVEL SERVICE [COMPONENT] MESSAGE
```

Example:

```text
2026-10-21T10:15:04Z ERROR api [database] MongoDB connection refused
```

Each parsed event preserves:

- the original line number;
- the complete raw line;
- the timestamp when it is valid;
- the log level;
- the service;
- the normalized message;
- available metadata;
- a parsing status: `valid`, `partial` or `invalid`.

Missing information is represented as missing data. The parser never invents values.

## Report design

The final report is structured around a clear distinction between observations and hypotheses.

It includes:

- incident summary;
- deterministic statistics;
- significant timeline events;
- up to three possible causes;
- confidence level: `low`, `medium` or `high`;
- supporting evidence;
- contradicting evidence;
- recommended checks;
- analysis limitations.

Every evidence reference contains a line number, a quoted excerpt and a reason. References are checked against the original evidence store before the report is exported.

## Reliability and security principles

- Log content is treated as untrusted data, never as an instruction to the agent.
- The agent is restricted to explicitly approved read-only tools.
- Source log files are never modified.
- API keys are read from environment variables and must not be committed.
- Production deployments should redact secrets and tokens before external model calls.
- File size, prompt size, model calls and investigation iterations are bounded.
- Invalid model responses are rejected or reported clearly.
- The deterministic mode remains available when the model provider is unavailable.

## Incident scenarios

The evaluation dataset will contain at least six reproducible scenarios:

- MongoDB connection refused;
- expired authentication token;
- port already in use;
- external API timeout;
- permission denied;
- simulated increase in error frequency.

Each scenario will include logs and a reference description of the known facts and relevant lines.

## Project structure

```text
ai-detective/
├── src/ai_detective/
│   ├── __main__.py              # python -m ai_detective
│   ├── cli.py                   # command-line interface
│   ├── parser/                  # log parsing
│   ├── analyzer/                # deterministic analysis
│   ├── evidence/                # evidence storage and lookup
│   ├── agent/                   # orchestration and read-only tools
│   ├── llm/                     # provider abstraction
│   ├── models/                  # Pydantic models
│   └── reporting/               # JSON and Markdown exporters
├── tests/
│   ├── unit/
│   ├── integration/
│   └── evaluation/
├── datasets/incidents/          # reproducible incident logs
├── reports/                     # generated reports
├── docs/                        # technical documentation
├── pyproject.toml
├── Dockerfile
└── README.md
```

The repository is intentionally built in increments. The parser, deterministic analysis, evidence
tools and bounded AI investigation are implemented as separate, tested milestones.

## Installation

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the project and development dependencies:

```bash
python -m pip install -e ".[dev]"
```

## Current status

The project foundation is available:

- Python package configuration;
- isolated virtual environment;
- initial CLI entry point;
- documented primary log format;
- sample incident logs;
- text, JSON and raw-line parsing;
- structured `LogEvent` models;
- deterministic error classification;
- deterministic statistics, repeated-error grouping and timelines;
- simple time-window error peak detection;
- input validation with configurable size, line-count and encoding limits;
- bounded read-only evidence tools (`get_error_summary`, `get_events_around`, `search_similar_lines`);
- controlled Stack Overflow solution retrieval with a one-call default limit;
- Groq tool-calling orchestration with iteration and tool-call limits;
- validated investigation reports with exact source-line evidence checks;
- automated tests and Ruff validation.

The next milestone is Markdown/report-file export, incident evaluation datasets and automated quality/security checks.

## Testing

Run the test suite with:

```bash
python -m pytest -q
```

The test strategy separates deterministic unit and integration tests from evaluations that require an LLM. This keeps the core behavior reproducible and testable without external services.

## Out of scope for the MVP

- web or graphical user interface;
- direct production access;
- arbitrary shell execution;
- automatic incident remediation;
- real-time monitoring and alerting;
- Kubernetes integration;
- vector database or advanced RAG pipeline;
- complex agent framework without a demonstrated need.

## Roadmap

1. Complete JSON/Markdown report-file export.
2. Add incident datasets, security tests and evaluation metrics.
3. Add provider-independent evaluation and optional model comparison.
4. Complete Docker and continuous integration.

