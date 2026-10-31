# Niural support agent

Use Git branches and commits for iterations. `main` and `v1` preserve
the initial raw-tool agent; `v2` contains the current implementation.
There are no version folders. See `docs/iterations.md` for observations and limits.

## Setup

Use the existing Conda base Python. No virtual environment is needed.

```powershell
python -m pip install --no-cache-dir -r requirements.txt
```

Put credentials and model settings in the repository-root `.env`; `.env.example`
is the template. Only that file is loaded. It is ignored by Git. Existing local
settings were migrated without changing model choices or LangSmith project names.
The current code uses OpenAI; GPT-4.1 and reasoning-model settings are supported.

## Chat

```powershell
python -m niural_support_agent
```

Answer text and tool events stream in the terminal. `/reset` clears the conversation;
`/quit`, Ctrl+C or EOF exits. The CLI does not run a judge. Notebook cells in
`notebooks/evaluation.ipynb` are for inspection and explicitly requested evaluations.

## Evaluate

Enable `LANGSMITH_TRACING=true` and set `LANGSMITH_API_KEY` in `.env` to record
model/tool traces. Use the matching LANGSMITH_ENDPOINT and, if needed, workspace ID.

```powershell
python -m niural_support_agent.run_benchmark --suite hard --name account-tools-hard
```

This manually runs the eight self-contained hard cases as a separate LangSmith
experiment. Add `--no-judge` to skip judge calls or `--concurrency 2` for parallel
cases. Model/judge choices, Git branch and commit are experiment metadata.
No evaluation or uploads run on import. Keys are never committed.

The `arithmetic` suite contains eight hypothetical budgeting, salary, contractor,
allocation and pricing cases. Establish its baseline on unchanged `v2` before
adding arithmetic/sorting tools on `v3`:

```powershell
python -m niural_support_agent.run_benchmark --suite arithmetic --name v2-arithmetic-baseline --description "Baseline: existing v2 account tools"
```

This runs eight answers and optional correctness judging in LangSmith. Add
`--no-judge` to save answers and traces without judge calls. No arithmetic-suite
agent results have been recorded yet. The notebook can select the same suite.

The `standard` suite preserves legacy questions; its original payment case relied
on an injected ID. That shortcut is removed from current code. Revise/rebaseline
that scenario explicitly rather than overwriting a frozen LangSmith dataset.

## Layout

```text
niural_support_agent/   Agent, typed query tools, CLI and evaluation runner
mock_api/              Authenticated file-backed API, Pydantic models and fixtures
benchmark/             Questions, reference facts, rubric and historical export
notebooks/             Evaluation notebook
docs/                  Iteration observations and supplied assignment materials
```

Tools perform deterministic filtering/counting/summing over supplied account data.
The snapshot date is 2026-09-28. Vendor addresses contain city/country only. Help
articles and API-reference documents are not loaded into the agent prompt; RAG is
deferred. See the trace and reference facts when reviewing a judge decision.
