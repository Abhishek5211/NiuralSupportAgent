# Initial correctness benchmark

`hard_cases.json` is a separate eight-question compound benchmark. It leaves the
original eight cases unchanged. Each record has integer `id`, `question`, and
customer-facing reference `facts`; every question is self-contained and pins
2026-09-28. No hidden messages or transaction IDs are required.

The first four cases cover vendor/invoice joins plus contacts and totals; employee
filters plus five individual compensation lookups; paid/unpaid lookalikes plus
current approval-chain state; and a corrected state/city filter plus onboarding
and an unusual recorded contractor location. One correct exclusion reason is
sufficient for each excluded employee. Do not infer that similar bills are
duplicate charges or silently correct fixture geography using outside knowledge.

Reference calculations were independently verified three ways: direct JSON with
Decimal arithmetic; SQLite joins/predicates with integer-cent aggregation; and
the authenticated MockAPI with Pydantic query execution and detail lookups. All
three produced matching record identities, contact fields, salaries, approval
states and totals. Key checks: four qualifying vendors, USD 15,792.40 unpaid and
USD 15,270.00 overdue; five qualifying employees; only USD 8,400.00 awaiting
Beatrix; six NY-state workers and one active US contractor recorded in CA.

These are verified reference labels, not agent scores. No agent/judge inference
was run. The salary/approval cases need several detail lookups and may expose a
model-turn budget that is too small. Keep budgets fixed when comparing versions.
The existing LangSmith batch command still selects the original eight cases;
use `--suite hard --name v2-hard` to select this separate dataset. It has not been
uploaded or substituted into the original dataset by the assistant.

Cases 5-8 add direct/indirect manager relationships, a teammate's manager plus
onboarding/dismissal details, null-manager records with direct-report counts,
and upcoming bills with contact details, approval owners and status totals.
These additional references were also independently verified with raw JSON,
SQLite self-joins and integer-cent totals, and authenticated API/Pydantic queries.
All three agree: Rosalind has nine direct and one one-level-indirect report;
Lucas is Desmond's only onboarded direct report; three onboarded employees have
no assigned manager; and the October 5-11 window has four unpaid bills totaling
USD 20,080.00 (USD 9,380.00 pending approval; USD 10,700.00 scheduled).

Benchmark version: **account-v1** (draft; freeze before the first live comparison).

`cases.json` contains eight cases with exactly three fields: integer `id`,
customer-facing `question`, and natural-language reference `facts`.
The answers are intentionally normal prose. No required tool sequence is scored.

The reference facts were checked against `../../mock_api/data/`. Keep them hidden
from the answering agent. Pass them only to the evaluator/judge.

## Conditions

- Treat today as **2026-09-28**, matching the supplied fixtures.
- Start every standalone case in a fresh conversation.
- Legacy standard case 8 was previously evaluated with an injected transaction
  reference. That shortcut has been removed. The original file is preserved, but
  its payment reference answer needs a clarification-aware revision before reuse
  without an explicit transaction reference. Old seeded LangSmith results are a
  different scenario; do not silently overwrite or compare them with an unseeded
  run. The frozen-dataset guard will reject changed context. Hard cases 1-8 are
  self-contained and receive no injected messages, regardless of case ID.
- Case 1's reference distinguishes 14 employees from 16 workers including contractors.
  Accept 14 when explicitly counting employees, or 16 when explicitly including
  contractors. Do not treat contractors as employee-type records.
- Case 2's reference covers New York state. Accept the four New York City names if
  the answer explicitly limits its scope to that city. The six state names include
  the two Brooklyn employees. A clarification is reasonable conversation behavior,
  but record it as unresolved rather than a correct factual answer in this initial
  standalone correctness benchmark.

## Scoring

Use `judge_prompt.txt` with the question, actual conversation context, reference
facts and candidate answer. The answering agent receives only the question, context
and its normal documentation/tools, never the reference facts.

The judge returns `correct` and a short `reason`. Accept equivalent wording and
reasonable formatting. Reference facts are not an exact output template; require
the information needed to answer the question, not every optional explanatory phrase.
An incorrect material extra claim makes an otherwise correct answer fail.

Report correct/8 and preserve per-case decisions. An unresolved clarification is not
a successful answer to an answerable case. Keep that distinct from whether asking
the clarification was appropriate. Tool use, citation quality and tone are not scored
in this first benchmark. Inspect saved answers and judge decisions; tracing is deferred to LangSmith.

The judge is not deterministic. Manually review the first run, use the same judge
model/settings/rubric across compared versions, and inspect disputed verdicts.
No live results or judge agreement have been established yet.

## Changing the benchmark

Keep questions, facts and rubric unchanged within a comparison. If labels need a
correction or new conversation/error cases are added, create a new named benchmark
snapshot and rerun both compared versions. Do not compare scores with different
case sets as if they were the same experiment. Record benchmark and rubric hashes
in each run's manifest.
