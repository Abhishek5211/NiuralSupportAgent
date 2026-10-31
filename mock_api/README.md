# Niural support agent exercise — dataset

A small mock of the Niural platform: one employer's **Employees** tab and their **Niural
Pay** vendors, bills and payments. Paired with a set of help articles (supplied
separately), it is enough to build and evaluate a customer support agent.

```
mock_api/
  API_DOCUMENTATION.md   the six endpoints, their fields and their enums
  data/                  the dataset, one file per domain
  generate_fixtures.py   regenerates data/
  validate_dataset.py    checks the data holds together and every question is answerable
```

## The exercise

Build an agent that answers an employer admin's support questions. Two kinds arrive, and
part of the exercise is that the agent has to tell them apart:

**Answered from the help articles** — how the product works, no customer data needed.

- "How do I add a new employee?"
- "What does 'Pending onboarding' mean?"
- "How do I approve a bill in Niural Pay?"

**Answered from this dataset** — specific to one employer, requires calling a tool.

| # | Question | Endpoints |
|---|---|---|
| 1 | How many active employees do we have? | list employees |
| 2 | Which of our employees are based in New York? | list employees |
| 3 | Is Marisol Okonjo's onboarding finished, or is something outstanding? | list → get employee |
| 4 | Why isn't Priya showing up in this payroll run? | list → get employee |
| 5 | Why hasn't Halberd Components been paid yet? | list invoices → get invoice |
| 6 | Which bills are overdue right now? | list invoices |
| 7 | How much do we owe Orrery Cloud in total? | list vendors → list invoices |
| 8 | The payment for that freight invoice failed — why? | get payment status |

None of these is answerable by a lookup alone. Q1 turns on status rather than row count,
Q3 and Q4 need the detail endpoint after resolving a name, Q5 needs the approval chain,
and Q7 requires summing several bills.

The dataset is seeded so each has exactly one defensible answer. `validate_dataset.py`
enforces that, so if you change the data, run it.

## Using it

Serve `data/` behind whatever mock you like. Files are keyed by `"METHOD /path"`; a detail
endpoint stores its records under `_records`, keyed by the path parameter:

```json
{
  "GET /vendor-invoices/{invoice_id}": {
    "_records": { "vinv-2041": { "message": "Success", "data": { } } }
  }
}
```

Keys beginning with `_` are fixture scaffolding, not part of the API. See
`API_DOCUMENTATION.md` for every field and enum.

The dataset is built as though today is **2026-09-28** — that is what makes a bill overdue
and a start date still in the future. Pin your clock or keep it in mind.

## Scope

Six endpoints only: list/get employees, list vendors, list/get vendor invoices, and get
payment status. There is deliberately no payroll, wallet, contract, timesheet or time-off
data — questions in those areas belong to the articles, or should be declined.

## Regenerating

```
python mock_api/generate_fixtures.py
python mock_api/validate_dataset.py
```
