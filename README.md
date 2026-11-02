# CrewAI Stock Analysis

A small CrewAI project that turns public market data into an evidence-aware daily stock brief. It is designed as a learning project: Python gathers and calculates the data, while the crew explains what it means in clear language.

## Setup

Use Python 3.10 through 3.13.

Create and activate a virtual environment, then install the project with its development dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Copy `.env.example` to `.env` and set the credentials required by your selected CrewAI-supported model provider. For MiniMax, set `MINIMAX_API_KEY` and use a LiteLLM model name such as `minimax/MiniMax-M3` for `OPENAI_MODEL_NAME`. The key is sent in the provider's `Authorization` header.

Optionally copy `knowledge/user_preference.example.txt` to
`knowledge/user_preference.txt` and customize it locally. Without that file,
the project uses generic beginner-friendly preferences. Preferences are sent
to the configured model provider; never put credentials, account identifiers,
or other private information in them.

## Run a report

```powershell
stock-brief NVDA
stock-brief SNDK
```

The final brief is printed to the terminal and saved as a timestamped Markdown file under `reports/`.

## Learn From A Run

This project uses CrewAI's classic Python and YAML layout. Run it with the
default full trace to see CrewAI's live agent/tool messages and save a local
record of the run:

```powershell
stock-brief NVDA --trace full
```

The final brief stays on standard output. Learning logs are written to standard
error and to a timestamped folder under `traces/`. Trace files are intended
for local use and can include preferences, market data, prompts, and model
responses. The supplied ignore rules exclude them, but files already tracked
by Git require a separate index and history review.

```mermaid
flowchart LR
		CLI[stock-brief NVDA] --> Main[main.py]
		Main --> Inputs[ticker and user preferences]
		Inputs --> Crew[ScratchProject crew]
		Crew --> Collect[1. Collector]
		Collect --> Tool[Get Stock Data tool]
		Tool --> Data[Yahoo Finance data and Python metrics]
		Data --> Summary[2. News Summarizer]
		Summary --> Risk[3. Risk Analyst]
		Risk --> Writer[4. Daily Brief Writer]
		Writer --> Output[CrewOutput]
		Output --> Report[reports/TICKER_timestamp.md]
		Output --> Trace[traces/TICKER_timestamp]
```

The crew uses `Process.sequential`, so tasks run in the order shown. In this
mode, CrewAI gives each later task the outputs from earlier tasks as context.
The collector is the only agent with the `Get Stock Data` tool. That tool calls
Yahoo Finance and calculates repeatable metrics in Python; the other agents
interpret only the information handed to them.

### Trace Modes

| Command option | What you see | Files saved |
| --- | --- | --- |
| `--trace full` | CrewAI's complete verbose agent and tool activity, plus application lifecycle logs | `learning.log`, `crewai-events.json`, task outputs, and `run-summary.json` |
| `--trace summary` | Application lifecycle and Yahoo Finance retrieval logs | `learning.log`, task outputs, and `run-summary.json` |
| `--trace off` | Only the final report or an error | No trace files |

Use `--trace-dir path/to/folder` to place artifacts elsewhere. Keep a custom
trace directory outside the repository, or explicitly ignore it and verify
the exclusion before staging. Each trace folder
contains `task-outputs/01-...md` through `04-...md`, in execution order. Read
them side by side to see what the next agent received and how it transformed
that context. `run-summary.json` records metadata, duration, token usage
when the provider returns it, and the final report location, which may be an
absolute local path. Both summary and full modes retain raw task outputs;
neither mode sanitizes files for public sharing.

Full trace mode can be noisy and may include prompts or model output. Do not
share its files publicly without reviewing them, and never place API keys in
agent/task YAML files or the preference file.

## What the report uses

- Latest available close, daily change, and five-session return
- 20-day and 50-day simple moving averages, plus 14-period RSI
- Recent volume relative to its 20-session average
- Available market capitalization, trailing P/E, and 52-week range
- Recent headlines with sources and links when provided by Yahoo Finance
- Company industry/sector classification and industry-related headlines,
  when the Yahoo Finance search API provides usable results

### Industry News And Sentiment

The tool makes one best-effort `yfinance.Search` request using the company's
industry name. It requests up to ten results with a ten-second timeout and
returns at most eight unique headlines. It does not retrieve article bodies
or require another API key. Missing classification, unsupported search,
request failures, or sparse results do not remove the collected stock metrics.

The report includes **Industry news and sentiment**. Existing agents assess
the relevant news as positive, negative, neutral, mixed, or insufficient
evidence. Any assessment other than insufficient evidence requires at least
two unique, source-linked, dated industry-relevant stories from the preceding
seven days in UTC. Company-news duplicates, company-only stories, unrelated
results, stale or future-dated stories, and undated articles cannot support
the assessment. Undated articles may be shown with an explicit warning.

This is AI interpretation of a selective industry-related news sample, not a
yfinance-provided sentiment score or measured sentiment across the entire
industry. Search relevance and coverage vary. Missing evidence is reported
explicitly rather than described as neutral. All original report sections
and the educational disclaimer remain.

`yfinance` is a best-effort public-data source. Data may be delayed, incomplete, or unavailable. Reports are educational summaries, not financial advice or trading recommendations.

## Project structure

- `src/scratch_project/tools/custom_tool.py`: data collection and deterministic calculations
- `src/scratch_project/config/`: CrewAI agent and task instructions
- `src/scratch_project/crew.py`: four-agent sequential crew composition
- `src/scratch_project/main.py`: command-line entry point and Markdown persistence
- `knowledge/user_preference.txt`: preferences passed to the brief writer
- `tests/`: offline tests that mock external services


No scanner can guarantee detection of every secret or personal detail. Review
the exact publication contents before choosing repository visibility. Keep
review snapshots private and remove them when no longer needed. No license is
selected automatically; choose one explicitly before granting reuse rights.
