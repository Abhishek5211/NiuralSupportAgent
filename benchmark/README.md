# Extended account benchmark

- **Cases:** `cases.json` has 33 scenarios and 36 generated user turns. Cases 8, 29 and 30 each contain two live turns.
- **Clock:** Today is the fixture snapshot, **2026-09-28**, not the host clock.
- **Schema:** `id`, final `question`, final `facts`; scripted cases add ordered `turns`, each with `question` and hidden `facts`. The final turn must match the top-level question/facts. Optional `context` remains available for explicit initial history.
- **Live scenarios:**
  - 8: unidentified failed payment -> agent asks for reference -> user supplies `txn-88403` -> agent checks the actual failure.
  - 29: Halberd balance -> user corrects the vendor to Orrery -> agent updates the answer.
  - 30: New York City roster -> user corrects to all New York state -> agent includes Brooklyn.
- **Execution:** Reset once, use a unique session for all turns, and retain actual agent/tool history. No canned assistant answers or case-ID-specific hints. Stop after a runtime/empty-answer failure and clear the session afterward.
- **Scoring:** Judge every turn using its own reference and actual preceding conversation. All turns must pass for the case to pass. Runtime failures fail the case; judge outages are ungraded unless another turn already failed. Earlier assistant claims are not reference truth.
- **Evidence:** `turn_results` retains each question, preceding conversation, answer/error, usage and latency. Top-level usage/latency aggregate the conversation. Existing LangSmith tracing records the tool/model calls.
- **Reported result:** Multi-turn answer accuracy **1.0**, reported by the author. The run export, case denominator and experiment link have not been inspected here; this is not a measured result for the new failure suite.
- **Coverage:** 9-18 cover relative dates; 19-28 cover rankings; 31-32 cover a missing bill and missing transaction reference. Case 28 explicitly includes contractors (Ines); case 33 explicitly excludes them (Freya). Runtime transient-fault injection is in the separate failure suite below.
- **Boundaries:** 15 days ahead = 2026-10-13; three calendar months back = 2026-06-28; the last 30 dates including today start 2026-08-30. Future windows filter current records, not predicted payment outcomes.
- **Label checks:** Date/money/ranking references were checked with raw JSON/Python/Decimal and independent SQLite queries, plus API/contract checks. New conversation setup references were checked against fixtures and authenticated API reads. [Verification evidence](results/cases-extended-verification.json)
- **Dataset:** `--suite standard` uses `niural-account-standard-v3`; earlier datasets stay frozen. The hard suite now uses its own multi-turn snapshot described below; the arithmetic multi-turn snapshot is described below. The common judge rubric now explicitly accepts reference-required clarification; use the same revised rubric for both sides of a new comparison.
- **Run:** `python -m niural_support_agent.run_benchmark --suite standard --name standard-multiturn-baseline`.
- **Comparison:** These are verified labels and a tested harness, not a new agent score. Multi-turn execution changes the scenario; rerun both compared code versions with this same script/rubric before claiming improvement.

# Failure scenarios

- **File:** [fail_scenarios.json](fail_scenarios.json): **7 cases / 11 user turns**, separate from normal accuracy cases.
- **Coverage:** expired authentication (401), permission denial (403), unavailable bill detail (503), transaction timeout (504), employee-detail outage then recovery, vendor correction followed by a run timeout and retry, and a missing transaction (native 404) followed by a corrected ID.
- **Injection:** `faults` contains `{turn, endpoint, status}` rules. `*` affects account reads only; `RUN` simulates an agent-run timeout before a model call. Faults remain active for every matching call on that user turn, then clear on later turns. The model never receives the schedule or hidden expected answers. These simulate API errors locally, not network transport failures.
- **Recovery:** Case 6 sets `continue_on_error: true` and expects a runtime `timeout` on turn 2. Other runtime errors still fail. A failed run preserves the user's correction and a safe error notice, discarding incomplete tool/model items. Case 5 handles an API error as a normal conversational answer and retries on turn 2.
- **Scoring:** Judge every conversational answer against that turn's hidden facts; the expected runtime timeout is checked deterministically. All turns must pass. Required injections must appear in `fault_events`; an unexercised rule leaves the case ungraded. The native 404 case has no synthetic rule.
- **Isolation:** Each case has a fresh session; fault state is scoped to its async execution. Standard, hard and arithmetic datasets keep their current inputs/references.
- **Dataset:** `niural-account-failures-v1`.
- **Run:** `python -m niural_support_agent.run_benchmark --suite failures --name failure-baseline`.
- **Verified locally:** Fault-to-tool error mapping, recovery on later turns, concurrent fault isolation, hidden references and per-turn scoring. The original failed-turn bug loses the Orrery correction; the revised runtime retains it. Existing dataset inputs/references are unchanged. No test files were created.
- **Status:** Failure-suite accuracy is unmeasured; these local checks used deterministic substitutes for model execution. No paid model, embedding or remote LangSmith calls ran.

# Product-guide FAQ baseline

`faq_cases.json` has 34 standalone cases: common tasks (1-10), unusual/keyword-heavy
queries (11-18), missing-information cases (19-20), short queries (21-30), and
cross-section questions (31-34). Each has integer `id`,
`question`, reference `facts`, `expected_behavior`, minimum `required_facts`,
`required_sections`, and optional
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
a focused clarification of i 99 rather than inventing a definition; no source is mandatory.
Each required section is needed; each alternative group needs any one section.
Case 23 has one alternative group. Cases 8/15 omit nonessential source requirements.
Expected behavior is answer, clarify, unavailable, or answer_or_clarify. Judges
receive only the minimum checklist, not the longer reference prose; either allowed
route passes. Cases 23/25/27 accept focused clarification or conditional guidance.
Per-fact evidence decisions determine retrieval sufficiency. Missing values and
rejected premises do not require positive proof when the expected answer says No
or explains a limitation. Case 24 is excluded from retrieval metrics (33 labeled
cases); it is still judged for clarification. No mandatory I-9 lookup is assumed.

Cases 31-34 require all listed sections (3, 2, 3 and 4 respectively). The evaluator
uses one top-3 search, so case 34 has a maximum recall@3 of 0.75. MRR/nDCG can still
be perfect with incomplete evidence; inspect recall and saved missing_sections.
The full chat agent can search again; this single-search baseline cannot. Original
34 questions remain unchanged; reference wording and minimum checklists are revised.
The revised labels/rubric (faq-behavior-v3) create a new dataset
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

- **Scenarios:** `arithmetic_cases.json` has **10 cases / 14 user turns**. Original cases 1-8 are unchanged; cases 9-10 each contain three live turns.
- **Clock and inputs:** Use fixture snapshot 2026-09-28. Budgets, raises, hours, reserves, discounts and fees supplied by the user are hypothetical assumptions; recorded salaries, rates and vendor balances come from authenticated account data.
- **Case 9:** Settle all unpaid bills -> overdue-only plus 5% raises -> replace raises with 3% and reserve with 10% of original cash. Final: USD 49,955 monthly salaries; three complete months; USD 32,365 cash remains; USD 37,590 extra starting cash is needed for four months with the reserve fixed at USD 20,000.
- **Case 10:** Original project quote -> customer discount and processing fee -> correct hours, supplier bill, discount and margin target. Final target quote USD 19,653.26; a mistaken 30% markup quotes USD 16,504.80 but produces only 17.03% margin after fees.
- **Rounding:** Quote upward to cents, then compute receipt/fee/profit from that rounded quote without intermediate rounding. Round displayed amounts/percentages half-up to two decimals. Raises in case 9 replace earlier assumptions and always apply to original recorded salaries.
- **Verification:** Every new turn was checked twice: raw-fixture 50-digit Decimal arithmetic and independent SQLite integer-cent inputs with exact Fraction arithmetic. Recorded inputs were also checked against MockAPI. [Per-turn evidence](results/arithmetic-multiturn-verification.json)
- **Execution/scoring:** Use the existing `turns` format. Preserve actual conversation/tool history; judge each turn against its hidden reference. Every turn must pass. No canned assistant answers or extra test files.
- **Dataset:** `niural-account-arithmetic-v2`; the previous eight-case `niural-account-arithmetic-v1` remains frozen. Compare agent versions only on the same cases, rubric, model settings and turn budgets.
- **Run:** `python -m niural_support_agent.run_benchmark --suite arithmetic --name arithmetic-multiturn-baseline`.
- **Status:** References are verified; no live model, judge, embedding or remote LangSmith calls were made during preparation. No new agent performance score is claimed.

| Original case | Verified reference result |
|---|---|
| 1 | USD 163,270 required; USD 3,270 reserve-preserving shortfall |
| 2 | Four vendor balances; USD 9,872.40 allocated; USD 127.60 remains |
| 3 | Original mean USD 116,400; annual increase USD 68,800; new mean USD 130,160 |
| 4 | Offer A USD 17,553.92; offer B USD 17,805.54; A saves USD 251.62 |
| 5 | Planned cost USD 7,205; USD 295 under budget |
| 6 | Two complete months; cash USD 42,627.60; USD 2,627.60 above reserve |
| 7 | USD 5,000 allocated exactly; overdue debt remaining USD 12,770 |
| 8 | 25% margin quote USD 22,226.67; 25% markup produces 20% margin |

# Initial correctness benchmark

- **Hard suite:** `hard_cases.json` has **10 scenarios / 14 user turns**. Original cases 1-8 are unchanged; cases 9-10 each have three live turns.
- **Case 9:** CA/TX employee roster -> California only -> restore Texas and add a USD 100,000 annual salary floor. Retain manager, status/type and hire-date constraints. Final: Noor, Anouk and Kwame; USD 418,000.00 annually.
- **Case 10:** Unpaid bills due October 5-11 -> extend to October 18, scheduled only -> Vantage, all unpaid, retaining the corrected window. Final: INV-2048, USD 22,000.00, awaiting Rosalind; Beatrix already approved.
- **Format:** Ordered `turns` with a question and hidden reference per turn. Top-level question/facts match the final turn; the evaluator generates actual earlier answers and retains tool history.
- **Scoring:** Every turn must pass. No canned assistant history, case-ID hints or test files are added.
- **Verified:** All six new turn references agree across raw JSON/Decimal, independent SQLite and authenticated API/query reads. [Verification evidence](results/hard-multiturn-verification.json)
- **Dataset:** `niural-account-hard-v2` preserves the frozen eight-case `niural-account-hard-v1`. New results are not directly comparable to the old 7/8 result; rerun both agent versions on the same ten scenarios and rubric.
- **Run:** `python -m niural_support_agent.run_benchmark --suite hard --name hard-multiturn-baseline`.
- **Status:** Labels and evaluator wiring are verified; no new agent, judge, embedding or remote LangSmith calls have run.

Original compound cases 1-8 remain self-contained and explicitly pin 2026-09-28.
The new conversation clock is stated in each first turn and retained thereafter.

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
The default standard suite now selects the 33 examples described above;
use `--suite hard --name hard-multiturn-baseline` for the ten-case hard snapshot.
No remote dataset has been created or overwritten during this extension.

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

All account cases retain top-level integer `id`, final customer-facing `question`,
and natural-language final reference `facts`. Cases 8, 29 and 30 add explicit live
user-turn scripts with a hidden reference for every turn; case 33 adds an explicit
employee-only counterpart to the all-worker ranking in case 28.
The answers are intentionally normal prose. No required tool sequence is scored.

The reference facts were checked against `../mock_api/data/`. Keep them hidden
from the answering agent. Pass them only to the evaluator/judge.

## Conditions

- Treat today as **2026-09-28**, matching the supplied fixtures.
- Start every standalone case in a fresh conversation.
- Historical standard case 8 used an injected transaction reference. The current
  case supplies it through a scripted second user turn after testing clarification.
  It is a new scenario; historical seeded results are not directly comparable.
  Hard cases 1-8 remain self-contained and receive no case-ID-based hints.
  The frozen-dataset guard checks the full turn script and every turn's reference.
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
