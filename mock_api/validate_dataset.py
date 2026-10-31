"""Checks the dataset is internally consistent and that every seeded question is answerable.

A take-home dataset fails in two ways that are invisible by eye: a question with no
defensible answer (wasting the candidate's time), and data that contradicts itself (an
invoice marked OVERDUE with a future due date, an employee reporting to someone who
isn't on the roster). Both are checked here.

Run: python mock_api/validate_dataset.py
"""

import json
import pathlib
import sys

DATA = pathlib.Path(__file__).parent / "data"
TODAY = "2026-09-28"

checks, failures = [], []


def check(label, condition, detail=""):
    checks.append(label)
    if not condition:
        failures.append(f"{label}{' — ' + detail if detail else ''}")


def load(name):
    return json.loads((DATA / name).read_text())


employees = load("employees.json")
vendors = load("vendors.json")
invoices = load("vendor_invoices.json")
payments = load("payments.json")

roster = employees["GET /employer/{employer_id}/employees"]["data"]
details = employees["GET /employer/{employer_id}/employee/{employee_id}"]["_records"]
vendor_rows = vendors["GET /vendors"]["data"]
invoice_rows = invoices["GET /vendor-invoices"]["data"]
invoice_details = invoices["GET /vendor-invoices/{invoice_id}"]["_records"]
txns = [
    v["data"]
    for v in payments["GET /transactions/{transaction_id}"]["_records"].values()
]

by_name = {f"{e['first_name']} {e['last_name']}": e for e in roster}
vendor_ids = {v["vendor_id"] for v in vendor_rows}
vendor_by_name = {v["name"]: v for v in vendor_rows}

# ---------------------------------------------------------------- referential integrity
check(
    "every employee has a detail record",
    {e["employee_id"] for e in roster} == set(details),
)
check(
    "every manager_name is someone on the roster",
    all(e["manager_name"] in by_name for e in roster if e["manager_name"]),
    str(
        [
            e["manager_name"]
            for e in roster
            if e["manager_name"] and e["manager_name"] not in by_name
        ]
    ),
)
check(
    "every invoice points at a known vendor",
    all(i["vendor_id"] in vendor_ids for i in invoice_rows),
)
check(
    "every invoice has a detail record",
    {i["invoice_id"] for i in invoice_rows} == set(invoice_details),
)
check(
    "invoice vendor_name matches the vendor record",
    all(
        i["vendor_name"]
        == next(v["name"] for v in vendor_rows if v["vendor_id"] == i["vendor_id"])
        for i in invoice_rows
    ),
)

# --------------------------------------------------------------------- internal logic
check(
    "PAID invoices have a paid_date, others do not",
    all((i["paid_date"] is not None) == (i["status"] == "PAID") for i in invoice_rows),
    str(
        [
            i["invoice_number"]
            for i in invoice_rows
            if (i["paid_date"] is not None) != (i["status"] == "PAID")
        ]
    ),
)
check(
    "OVERDUE invoices really are past due and unpaid",
    all(
        i["due_date"] < TODAY and i["paid_date"] is None
        for i in invoice_rows
        if i["status"] == "OVERDUE"
    ),
    str(
        [
            i["invoice_number"]
            for i in invoice_rows
            if i["status"] == "OVERDUE"
            and not (i["due_date"] < TODAY and i["paid_date"] is None)
        ]
    ),
)
check(
    "no unpaid invoice is past due without being marked OVERDUE",
    all(
        i["status"] == "OVERDUE"
        for i in invoice_rows
        if i["paid_date"] is None and i["due_date"] < TODAY
    ),
    str(
        [
            i["invoice_number"]
            for i in invoice_rows
            if i["paid_date"] is None
            and i["due_date"] < TODAY
            and i["status"] != "OVERDUE"
        ]
    ),
)
check(
    "only PENDING_APPROVAL invoices await an approver",
    all(
        (d["data"]["awaiting_approval_from"] is not None)
        == (d["data"]["status"] == "PENDING_APPROVAL")
        for d in invoice_details.values()
    ),
)
check(
    "payroll_eligible is true only for ONBOARDED employees",
    all(
        d["data"]["payroll_eligible"] == (d["data"]["status"] == "ONBOARDED")
        for d in details.values()
    ),
)
check(
    "onboarding.complete is false only for PENDING_ONBOARDING",
    all(
        d["data"]["onboarding"]["complete"]
        == (d["data"]["status"] != "PENDING_ONBOARDING")
        for d in details.values()
    ),
)
check(
    "dismissed employees carry dismissal detail, others do not",
    all(
        (d["data"]["dismissal"] is not None) == (d["data"]["status"] == "DISMISSED")
        for d in details.values()
    ),
)

# ------------------------------------------------------- each seeded question resolves
active = [e for e in roster if e["status"] == "ONBOARDED"]
check(
    "Q1 headcount is non-trivial (active < total, so status matters)",
    0 < len(active) < len(roster),
    f"{len(active)} active of {len(roster)}",
)

ny = [e for e in roster if e["work_location"]["state"] == "NY"]
check("Q2 several employees are in New York", len(ny) >= 3, f"{len(ny)} found")

marisol = details.get(by_name["Marisol Okonjo"]["employee_id"], {}).get("data")
pending_steps = (
    [s for s in marisol["onboarding"]["steps"] if s["status"] == "PENDING"]
    if marisol
    else []
)
check(
    "Q3 Marisol has exactly one outstanding onboarding step",
    marisol is not None and len(pending_steps) == 1,
    f"{len(pending_steps)} pending",
)

priya = details.get(by_name["Priya Raghunathan"]["employee_id"], {}).get("data")
check(
    "Q4 Priya is dismissed with a final pay date already passed",
    priya is not None
    and priya["status"] == "DISMISSED"
    and priya["dismissal"]["final_pay_date"] < TODAY,
)

halberd_id = vendor_by_name["Halberd Components Ltd"]["vendor_id"]
halberd_blocked = [
    d["data"]
    for d in invoice_details.values()
    if d["data"]["vendor_id"] == halberd_id
    and d["data"]["status"] == "PENDING_APPROVAL"
]
check(
    "Q5 Halberd has a bill blocked on a named approver",
    len(halberd_blocked) == 1 and halberd_blocked[0]["awaiting_approval_from"],
    str([b["invoice_number"] for b in halberd_blocked]),
)

overdue = [i for i in invoice_rows if i["status"] == "OVERDUE"]
check(
    "Q6 there are overdue bills to report", len(overdue) >= 3, f"{len(overdue)} overdue"
)

orrery_id = vendor_by_name["Orrery Cloud Services"]["vendor_id"]
orrery_unpaid = [
    i for i in invoice_rows if i["vendor_id"] == orrery_id and i["paid_date"] is None
]
check(
    "Q7 Orrery has multiple unpaid bills, so the answer requires summing",
    len(orrery_unpaid) >= 2,
    f"{len(orrery_unpaid)} unpaid, total {sum(i['amount'] for i in orrery_unpaid)}",
)

failed = [t for t in txns if t["status"] == "FAILED"]
check(
    "Q8 a failed payment exists and says why",
    len(failed) >= 1 and all(t.get("failure_reason") for t in failed),
)

# ----------------------------------------------------------------------------- report
for label in checks:
    mark = "FAIL" if any(f.startswith(label) for f in failures) else "ok  "
    print(f"  {mark} {label}")

print(f"\n{len(checks) - len(failures)}/{len(checks)} checks passed")
if failures:
    print("\nProblems:")
    for f in failures:
        print(f"  - {f}")
sys.exit(1 if failures else 0)
