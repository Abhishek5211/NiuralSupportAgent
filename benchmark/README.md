# Product-guide FAQ baseline

`faq_cases.json` has 34 standalone cases: common tasks (1-10), unusual/keyword-heavy
queries (11-18), missing-information cases (19-20), short queries (21-30), and
cross-section questions (31-34). Each has integer `id`,
`question`, customer-facing `facts`, `required_sections`, and optional
`alternative_sections` groups from
[`PRODUCT_GUIDE.md`](../mock_api/PRODUCT_GUIDE.md). These are source headings,
not chunk IDs; map them after chunking. Cases 19-20 cite sections that establish
the limitation, not a benefits procedure or fee rate.

Keywords include KYB, I-9 Section 2, Re-analyze, Unlinked, MM-DD-YYYY, Add exemption,
BRW-XFEWYVQU, HAL-2026-0101, AED/USD and UI placeholders. Keep the same questions
for semantic and later hybrid search. Reference facts/sections stay hidden from
the answering agent. Score source-section coverage separately from answer
correctness, grounding and citations. Accept equivalent wording and optional detail.

Short queries preserve informal wording, exact UI terms and typos. Case 24 requires
clarifying i 99 rather than inventing a definition; its I-9 section is only a candidate.
Each required section is needed; each alternative group needs any one section.
Case 23 has one alternative group. Cases 15/27 omit nonessential source requirements.

Cases 31-34 require all listed sections (3, 2, 3 and 4 respectively). The evaluator
uses one top-3 search, so case 34 has a maximum recall@3 of 0.75. MRR/nDCG can still
be perfect with incomplete evidence; inspect recall and saved missing_sections.
The full chat agent can search again; this single-search baseline cannot. Original
30 questions/facts remain unchanged. The revised labels/rubric create a new dataset
snapshot; rerun comparisons under the same rules rather than compare old scores directly.

Read the full guide and verified the original 20 cases twice: first against source sections
and factual anchors, then for exceptions, examples versus actual account records,
currency/status distinctions and unsupported answers. This is document verification,
not an agent score. Retrieval is now available through evaluate_retriever; no
model, embedding or judge calls ran during implementation. Freeze these labels for the first comparison.

The retriever evaluator scores section requirements: recall@3 is the fraction
covered; MRR@3 rewards the first match; nDCG@3 rewards earlier matches. Alternative
sections earn one credit per group, without double-counting. Retrieval errors score zero.
These measure label coverage, not sufficient answer evidence. The judge must support
every requested part from passages; reference facts cannot fill gaps. Reports list
missing required sections and missing alternative groups separately.
Alternative sections (case 23), scope limitations (19-20) and candidate evidence for
an ambiguous typo (24) need interpretation. Optional passage judges assess actual
relevance/sufficiency; optional answer judges assess correctness, grounding,
helpfulness and citations. Grades can be wrong: inspect reasons and traces. No
hard similarity threshold is assumed. Judge failures are unavailable, not failures
of the answer. Results go to one explicitly named JSON file, with no manifest.
When LangSmith tracing is enabled, runs also appear as experiments with metric and
optional judge feedback. FAQ content determines the dataset snapshot; compare runs
on the same snapshot. `--name` labels the experiment; JSON keeps its link.

# Arithmetic baseline

`arithmetic_cases.json` contains eight self-contained hypothetical scenarios with
integer `id`, `question` and natural-language `facts`. Questions use the snapshot
date already supplied by the system prompt. User-supplied budgets, hours, reserve
rules, discounts and pricing targets are assumptions, not account facts.

| Case | Coverage | Reference result |
|---|---|---|
| 1 | Percentage reserve, quarterly salaries and overdue bills | $163,270 required; $3,270 shortfall against the reserve |
| 2 | Vendor totals, ascending order and whole-balance allocation | Four vendors; $9,872.40 allocated; $127.60 remaining |
| 3 | Mean salary, conditional raises and new mean | $116,400 original mean; $68,800 annual increase; $130,160 new mean |
| 4 | Sequential discount and fees with cent rounding | A $17,553.92 versus B $17,805.54; A saves $251.62 |
| 5 | Hourly contractor costs and contingency | $7,205 planned cost; $295 under budget |
| 6 | Vendor settlement, reserve and complete-month runway | Two months; $42,627.60 cash remains, $2,627.60 above reserve |
| 7 | Proportional vendor allocation and rounding remainder | $5,000 allocated exactly; $12,770 remains overdue |
| 8 | Contractor/vendor costs, margin versus markup | $22,226.67 for 25% margin; 25% markup gives $20,837.50 and 20% margin |

Reference inputs and calculations were checked locally using raw fixture data,
Decimal arithmetic, SQLite integer-cent totals and authenticated API reads. These
are reference labels, not measured agent performance. No agent or judge calls
were made while preparing this suite. No hidden context or required tool sequence
is supplied. The agent sees only each question; reference facts go to the judge.

Run manually with `--suite arithmetic --name v2-arithmetic-baseline`; the runner
uses the separate LangSmith dataset `niural-account-arithmetic-v1`. The existing
dataset guard rejects changed questions or facts. Keep this dataset, shared judge
rubric, answering/judge models, model-turn limits and concurrency fixed when
comparing unchanged v2 against v3. Preserve runtime failures and unresolved answers
as baseline findings rather than fixing the agent during measurement. Review
disputed judge verdicts against the stated hypothetical assumptions and arithmetic.
The existing evaluator records answers, usage, latency, errors and correctness;
LangSmith records model/tool traces. The score remains unmeasured until a run.

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
