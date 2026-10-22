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
6. optionally let an AI investigator query three read-only tools;
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

The AI investigator will have access to three bounded tools:

- `get_error_summary`: inspect recurring errors and their frequencies;
- `get_events_around`: inspect events near a line number or timestamp;
- `search_similar_lines`: find related log messages.

No arbitrary shell command, production connection or automatic remediation is exposed to the agent.

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
- Secrets and tokens should be masked before external model calls.
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

The repository is intentionally built in increments. Only the foundation is currently implemented; parser, analysis, evidence, orchestration and reporting components are added and tested as separate milestones.

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
- automated tests and Ruff validation.

The next milestone is validated report models and JSON/Markdown output. The AI investigation layer will only be added after the non-AI analysis path is reliable and tested.

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

1. Define validated report models and the `--no-ai` export path.
2. Add the evidence store and read-only investigation tools.
3. Integrate a configurable LLM provider and bounded orchestration.
4. Add incident datasets, security tests and evaluation metrics.
5. Complete JSON/Markdown reporting, Docker and continuous integration.

