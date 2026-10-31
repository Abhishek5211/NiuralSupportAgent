# Niural support agent

Use Git branches and commits for iterations. `main` and `v1` preserve
the initial raw-tool agent; `v2` preserves the account baseline; `v3` adds compensation queries, averages and sorting.
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
`--no-judge` to save answers and traces without judge calls. The original arithmetic export scored 4/8: two turn-limit failures and two
compensation-discovery failures. A rerun with the increased limit is a separate experiment. The notebook can select the same suite.

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

## V3 comparison

`query_account` fetches employee details when compensation is requested or used in
filters, aggregates or sorting. Ordinary list queries do not fetch compensation.
Select `compensation` or its dotted amount/currency/frequency fields. Use
`aggregate_field` (replacing v2's `sum_field`) with `sum` or `average`, and
`order_by=[{"field": "compensation.amount", "direction": "desc"}]` for salary
rankings. Filter rankings to one currency and pay frequency. Aggregates keep those
units separate, return their contributing count and include employee detail sources.

The v2 baseline preserves the increased 15-turn limit. V3 commits separately record
the description fix, batched queries, and configurable parallel calls. No calculator
or RAG is included. V3 performance is unmeasured until a manual run:

```powershell
python -m niural_support_agent.run_benchmark --suite arithmetic --name v3-query-tools
python -m niural_support_agent.run_benchmark --suite hard --name v3-query-tools-hard
```

Run with `PARALLEL_TOOL_CALLS=false` first. Then set it to `true` in root `.env`,
restart the CLI/notebook agent, and use a distinct experiment name such as
`v3-query-tools-parallel`. This controls independent model-issued tool calls, not
benchmark case concurrency. The judge keeps parallel calls disabled. Models,
turn limit, timeout and actual parallel setting are experiment metadata. Keep
cases, rubric and models fixed; compare correctness, requests, tokens and latency,
and inspect tool calls in LangSmith. Internal detail reads share one query tool
span; their endpoint references appear in `detail_sources`.

## V4: batched Decimal calculator

V4 adds one `calculate` tool for hypothetical arithmetic. Account lookups and
aggregates still use the existing tools. The calculator accepts named decimal-string
variables and ordered steps; arguments are either `{"value": "12"}` literals or
`{"ref": "salary"}` references to inputs or earlier results. Variables are local
to one invocation. There is no Python execution, expression parser or new dependency.

Supported operations: sum, subtract, multiply, divide, average, min, max, floor,
ceil and round. Subtraction/division evaluate left to right. Division uses 50
significant Decimal digits. Any operation can round its result by supplying both
`places` and `rounding`: half_up, half_even, floor or ceiling. For example, divide
68800 by 12 with places=2 and rounding=half_up to return 5733.33 directly. Leave
both fields null to preserve precision. Standalone round still requires both;
later steps use the rounded result. Results are named decimal strings. Invalid
requests return specific validation messages with step names where available.

Related calculations run inside one tool invocation. Unknown/forward references,
duplicate names, invalid arguments and failed arithmetic return an error, not a
partial answer. This verifies arithmetic only: the agent still has to choose the
right inputs, currency units and formulas. In particular, reserved cash remains
part of total cash; spendable cash is a different quantity.

The shortened v3 prompt is preserved at commit 51f928f. V4 keeps that prompt plus
calculator guidance. Compare with the same eight arithmetic cases, model settings,
15-turn limit, judge rubric and parallel-call setting (currently false):

```powershell
python -m niural_support_agent.run_benchmark --suite arithmetic --name v4-arithmetic-calculator
```

Add `--no-judge` to save answers/traces without judge calls. The notebook defaults
to manual execution. Revised V4 scored 8/8 in run 7afa7ef5, confirmed by manual
review. See [iteration findings](docs/iterations.md#v4-measured-result). Inspect cases 6/7 for formula interpretation and proportional allocation,
and compare model requests, calculator/tool calls, tokens, latency and correctness.
A calculator call may add a model turn and its schema adds input tokens; neither
lower cost nor improved agent correctness is assumed. RAG remains deferred.

## V5: product-guide chunks

```powershell
python -m niural_support_agent.chunking
```

`chunk_product_guide()` returns typed chunks with stable IDs, source, section,
heading path and text. Split at `#`/`##`; keep `###`, tables and numbered steps
together, without size-based splitting or overlap. `embedding_text` includes the
heading path for retrieval context. The cleaned guide produces 17 chunks covering
all 20 FAQ source labels. This command only previews chunks; no API key, embeddings
or vector index is used yet.

## V5: retrieval and evaluation

```powershell
python -m niural_support_agent.retrieval build
python -m niural_support_agent.retrieval search "what are columns of bill?"
python -m niural_support_agent.evaluate_retriever --output benchmark/results/retriever-v5.json
python -m niural_support_agent.evaluate_retriever --generate --judge --output benchmark/results/rag-v5.json
```

Build embeds the 17 sections with root `.env`'s OPENAI_API_KEY and EMBEDDING_MODEL
(default text-embedding-3-small), persisting a cosine index in ignored `.chroma/`.
Unchanged builds make no embedding calls. Rebuild after guide/model changes and
restart chat. Missing/stale indexes return a tool error; account tools still work.
The agent gains search_product_guide as its sixth tool.

Evaluation runs 30 query embeddings and saves matches, distances, source hits/rank/
coverage, tokens and timings. `--judge` adds passage relevance and sufficiency;
`--generate` adds passage-based answers. Together they also judge correctness,
grounding, helpfulness and citations: 30 generation and 60 judge requests for 30
successful cases. Gold facts never reach the generator. This evaluates the RAG
component, not full account conversations. LangSmith follows existing settings.

Verdicts, reasons and usage share one JSON report; existing files are not overwritten.
Judge failures remain ungraded. Source hits and cosine distances do not establish
answer correctness. No live ingestion/eval has run; hybrid search remains deferred.
