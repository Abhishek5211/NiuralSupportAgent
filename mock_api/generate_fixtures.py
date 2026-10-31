"""Generates the candidate-exercise dataset in ./data.

Scope is deliberately small: six endpoints across the Employees tab and Niural Pay,
enough to build a customer support agent against without drowning the candidate.

Every record is invented. Shapes follow the conventions of the real API (the
``{"message", "data"}`` envelope, snake_case fields, summary-in-list /
detail-by-id) but no real employer, person, vendor or amount appears here.

The dataset is seeded so each question in README.md has exactly one defensible
answer — ``validate_dataset.py`` enforces that.

Run: python mock_api/generate_fixtures.py
"""

import json
import pathlib

OUT = pathlib.Path(__file__).parent / "data"

TODAY = "2026-09-28"
EMPLOYER_ID = "emplr-4f2a91c8"


def ok(data):
    return {"message": "Success", "data": data}


# --------------------------------------------------------------------------------------
# Employees
# --------------------------------------------------------------------------------------
# status drives most of the interesting questions:
#   ONBOARDED           - active, payable
#   PENDING_ONBOARDING  - hired, not yet payable (paperwork outstanding)
#   DISMISSED           - offboarded, excluded from payroll after final_pay_date
#
# (first, last, title, department, type, status, start, city, state, manager)
_ROSTER = [
    (
        "Marisol",
        "Okonjo",
        "Senior Controls Engineer",
        "Engineering",
        "EMPLOYEE",
        "PENDING_ONBOARDING",
        "2026-09-21",
        "Brooklyn",
        "NY",
        "Rosalind Vane",
    ),
    (
        "Teodor",
        "Lindqvist",
        "Firmware Technician",
        "Engineering",
        "EMPLOYEE",
        "ONBOARDED",
        "2025-03-10",
        "Austin",
        "TX",
        "Rosalind Vane",
    ),
    (
        "Priya",
        "Raghunathan",
        "Account Manager",
        "Sales",
        "EMPLOYEE",
        "DISMISSED",
        "2024-01-15",
        "Chicago",
        "IL",
        "Desmond Achebe",
    ),
    (
        "Rosalind",
        "Vane",
        "VP Engineering",
        "Engineering",
        "EMPLOYEE",
        "ONBOARDED",
        "2023-02-01",
        "New York",
        "NY",
        None,
    ),
    (
        "Desmond",
        "Achebe",
        "Head of Sales",
        "Sales",
        "EMPLOYEE",
        "ONBOARDED",
        "2023-05-22",
        "New York",
        "NY",
        None,
    ),
    (
        "Ines",
        "Bramante",
        "Industrial Designer",
        "Design",
        "US_1099_CONTRACTOR",
        "ONBOARDED",
        "2026-06-01",
        "Milan",
        None,
        "Rosalind Vane",
    ),
    (
        "Kwame",
        "Boateng",
        "Mechanical Engineer",
        "Engineering",
        "EMPLOYEE",
        "ONBOARDED",
        "2025-08-04",
        "Austin",
        "TX",
        "Rosalind Vane",
    ),
    (
        "Saoirse",
        "Kavanagh",
        "Payroll Specialist",
        "Finance",
        "EMPLOYEE",
        "ONBOARDED",
        "2024-11-12",
        "New York",
        "NY",
        "Beatrix Nolan",
    ),
    (
        "Beatrix",
        "Nolan",
        "Controller",
        "Finance",
        "EMPLOYEE",
        "ONBOARDED",
        "2023-09-18",
        "New York",
        "NY",
        None,
    ),
    (
        "Hiroshi",
        "Tanabe",
        "QA Engineer",
        "Engineering",
        "EMPLOYEE",
        "ONBOARDED",
        "2025-01-07",
        "Seattle",
        "WA",
        "Rosalind Vane",
    ),
    (
        "Amara",
        "Diallo",
        "Recruiter",
        "People",
        "EMPLOYEE",
        "ONBOARDED",
        "2025-06-16",
        "Chicago",
        "IL",
        "Beatrix Nolan",
    ),
    (
        "Lucas",
        "Ferreira",
        "Support Engineer",
        "Support",
        "EMPLOYEE",
        "ONBOARDED",
        "2024-07-29",
        "Austin",
        "TX",
        "Desmond Achebe",
    ),
    (
        "Noor",
        "Al-Sabah",
        "Product Manager",
        "Product",
        "EMPLOYEE",
        "ONBOARDED",
        "2024-04-08",
        "San Francisco",
        "CA",
        "Rosalind Vane",
    ),
    (
        "Elias",
        "Thorne",
        "Technical Writer",
        "Product",
        "US_1099_CONTRACTOR",
        "ONBOARDED",
        "2026-02-02",
        "Portland",
        "CA",
        "Noor Al-Sabah",
    ),
    (
        "Freya",
        "Ostergaard",
        "Data Analyst",
        "Finance",
        "EMPLOYEE",
        "ONBOARDED",
        "2025-10-20",
        "Boston",
        "MA",
        "Beatrix Nolan",
    ),
    (
        "Mateo",
        "Villalobos",
        "Field Technician",
        "Operations",
        "EMPLOYEE",
        "ONBOARDED",
        "2025-05-05",
        "San Diego",
        "CA",
        "Rosalind Vane",
    ),
    (
        "Anouk",
        "Visser",
        "Operations Lead",
        "Operations",
        "EMPLOYEE",
        "ONBOARDED",
        "2024-02-26",
        "San Jose",
        "CA",
        "Rosalind Vane",
    ),
    (
        "Tobias",
        "Werner",
        "Sales Engineer",
        "Sales",
        "EMPLOYEE",
        "PENDING_ONBOARDING",
        "2026-09-29",
        "Seattle",
        "WA",
        "Desmond Achebe",
    ),
    (
        "Chiara",
        "Rossi",
        "Office Manager",
        "People",
        "EMPLOYEE",
        "ONBOARDED",
        "2023-11-06",
        "Brooklyn",
        "NY",
        "Beatrix Nolan",
    ),
    (
        "Oluwafemi",
        "Adeyemi",
        "Junior Engineer",
        "Engineering",
        "EMPLOYEE",
        "PENDING_ONBOARDING",
        "2026-10-05",
        "Austin",
        "TX",
        "Rosalind Vane",
    ),
    (
        "Greta",
        "Lindholm",
        "Marketing Lead",
        "Marketing",
        "EMPLOYEE",
        "DISMISSED",
        "2023-07-17",
        "Boston",
        "MA",
        "Desmond Achebe",
    ),
]

_SALARY = {
    "VP Engineering": 218000,
    "Head of Sales": 205000,
    "Controller": 186000,
    "Senior Controls Engineer": 164000,
    "Product Manager": 158000,
    "Operations Lead": 132000,
    "Mechanical Engineer": 128000,
    "QA Engineer": 118000,
    "Data Analyst": 112000,
    "Sales Engineer": 126000,
    "Payroll Specialist": 96000,
    "Support Engineer": 94000,
    "Recruiter": 92000,
    "Marketing Lead": 142000,
    "Firmware Technician": 88000,
    "Field Technician": 76000,
    "Office Manager": 72000,
    "Junior Engineer": 82000,
    "Account Manager": 104000,
    "Industrial Designer": 95,
    "Technical Writer": 78,  # contractors: hourly
}


def _employee_id(index):
    return f"emp-{3100 + index * 7:05d}"


def _summary(index, row):
    first, last, title, dept, etype, status, start, city, state, manager = row
    return {
        "employee_id": _employee_id(index),
        "first_name": first,
        "last_name": last,
        "work_email": f"{first.lower()}.{last.lower().replace(' ', '')}@bramblewood.example",
        "job_title": title,
        "department": dept,
        "employment_type": etype,
        "status": status,
        "start_date": start,
        "work_location": {
            "city": city,
            "state": state,
            "country_iso2": "US" if state else ("IT" if city == "Milan" else "US"),
        },
        "manager_name": manager,
    }


SUMMARIES = [_summary(i, row) for i, row in enumerate(_ROSTER)]
BY_NAME = {f"{s['first_name']} {s['last_name']}": s for s in SUMMARIES}


def _onboarding(status, start_date):
    """Checklist. Complete for ONBOARDED/DISMISSED; partial for PENDING_ONBOARDING."""
    steps = [
        "Personal details",
        "Tax withholding (W-4)",
        "Direct deposit",
        "I-9 Section 1",
        "I-9 Section 2",
    ]
    if status != "PENDING_ONBOARDING":
        return {
            "complete": True,
            "completed_steps": len(steps),
            "total_steps": len(steps),
            "steps": [
                {"name": s, "status": "COMPLETE", "completed_date": start_date}
                for s in steps
            ],
        }
    # Partial: everything the employee controls is done; the employer-side step is not.
    done = steps[:4]
    return {
        "complete": False,
        "completed_steps": len(done),
        "total_steps": len(steps),
        "steps": [
            {"name": s, "status": "COMPLETE", "completed_date": start_date}
            for s in done
        ]
        + [
            {
                "name": "I-9 Section 2",
                "status": "PENDING",
                "completed_date": None,
                "blocked_on": "EMPLOYER",
                "note": "Employer must verify original documents within 3 business days of the start date.",
            }
        ],
    }


def _detail(summary, row):
    first, last, title, dept, etype, status, start, city, state, manager = row
    contractor = etype == "US_1099_CONTRACTOR"
    detail = dict(summary)
    detail["compensation"] = {
        "amount": _SALARY[title],
        "currency": "USD",
        "frequency": "HOURLY" if contractor else "ANNUAL",
    }
    detail["onboarding"] = _onboarding(status, start)
    detail["manager"] = (
        {
            "employee_id": BY_NAME[manager]["employee_id"],
            "name": manager,
            "job_title": BY_NAME[manager]["job_title"],
        }
        if manager
        else None
    )
    detail["payroll_eligible"] = status == "ONBOARDED"
    if status == "DISMISSED":
        dismissal = {
            "Priya Raghunathan": {
                "dismissal_date": "2026-08-31",
                "final_pay_date": "2026-08-31",
                "reason": "VOLUNTARY_RESIGNATION",
            },
            "Greta Lindholm": {
                "dismissal_date": "2026-05-15",
                "final_pay_date": "2026-05-30",
                "reason": "ROLE_ELIMINATED",
            },
        }[f"{first} {last}"]
        detail["dismissal"] = dismissal
        detail["payroll_eligible"] = False
    else:
        detail["dismissal"] = None
    return detail


EMPLOYEES = {
    "GET /employer/{employer_id}/employees": ok(SUMMARIES),
    "GET /employer/{employer_id}/employee/{employee_id}": {
        "_note": "Keyed by employee_id. A mock server returns the matching object.",
        "_records": {
            s["employee_id"]: ok(_detail(s, row)) for s, row in zip(SUMMARIES, _ROSTER)
        },
    },
}

# --------------------------------------------------------------------------------------
# Vendors
# --------------------------------------------------------------------------------------
_VENDORS = [
    (
        "ven-6201",
        "Halberd Components Ltd",
        "ap@halberd-components.example",
        "ACH",
        30,
        "Sheffield",
        "GB",
    ),
    (
        "ven-6202",
        "Orrery Cloud Services",
        "billing@orrery.example",
        "WIRE",
        15,
        "Dublin",
        "IE",
    ),
    (
        "ven-6203",
        "Kestrel Freight",
        "invoices@kestrel-freight.example",
        "ACH",
        45,
        "Newark",
        "US",
    ),
    (
        "ven-6204",
        "Pallas Metalworks",
        "accounts@pallas-metal.example",
        "ACH",
        30,
        "Cleveland",
        "US",
    ),
    (
        "ven-6205",
        "Juniper Office Supply",
        "ar@juniper-office.example",
        "ACH",
        30,
        "Austin",
        "US",
    ),
    (
        "ven-6206",
        "Vantage Legal LLP",
        "billing@vantagelegal.example",
        "WIRE",
        30,
        "New York",
        "US",
    ),
    (
        "ven-6207",
        "Sable Facilities",
        "invoices@sablefacilities.example",
        "ACH",
        30,
        "Brooklyn",
        "US",
    ),
    (
        "ven-6208",
        "Thicket Design Studio",
        "hello@thicketdesign.example",
        "ACH",
        14,
        "Lisbon",
        "PT",
    ),
]

VENDOR_RECORDS = [
    {
        "vendor_id": vid,
        "name": name,
        "email": email,
        "status": "ACTIVE",
        "default_currency": "USD",
        "payment_method": method,
        "payment_terms_days": terms,
        "address": {"city": city, "country_iso2": country},
    }
    for vid, name, email, method, terms, city, country in _VENDORS
]
VENDOR_NAME = {v["vendor_id"]: v["name"] for v in VENDOR_RECORDS}

VENDORS = {"GET /vendors": ok(VENDOR_RECORDS)}

# --------------------------------------------------------------------------------------
# Vendor invoices
# --------------------------------------------------------------------------------------
# status: PAID | OVERDUE | PENDING_APPROVAL | SCHEDULED
# "overdue" means due_date is before TODAY (2026-09-28) and nothing has been paid.
#
# (number, vendor, amount, status, issue, due, paid)
_INVOICES = [
    (
        "INV-2041",
        "ven-6201",
        8400.00,
        "PENDING_APPROVAL",
        "2026-09-05",
        "2026-10-05",
        None,
    ),
    ("INV-2042", "ven-6202", 1250.00, "OVERDUE", "2026-08-10", "2026-08-25", None),
    ("INV-2043", "ven-6202", 1250.00, "OVERDUE", "2026-09-01", "2026-09-16", None),
    (
        "INV-2044",
        "ven-6202",
        980.00,
        "PENDING_APPROVAL",
        "2026-09-20",
        "2026-10-05",
        None,
    ),
    ("INV-2045", "ven-6203", 3120.00, "OVERDUE", "2026-07-30", "2026-09-13", None),
    (
        "INV-2046",
        "ven-6204",
        15600.00,
        "PAID",
        "2026-08-01",
        "2026-08-31",
        "2026-08-28",
    ),
    ("INV-2047", "ven-6205", 410.55, "PAID", "2026-08-05", "2026-09-04", "2026-09-02"),
    (
        "INV-2048",
        "ven-6206",
        22000.00,
        "PENDING_APPROVAL",
        "2026-09-18",
        "2026-10-18",
        None,
    ),
    ("INV-2049", "ven-6207", 2750.00, "PAID", "2026-08-12", "2026-09-11", "2026-09-09"),
    ("INV-2050", "ven-6208", 6400.00, "SCHEDULED", "2026-09-22", "2026-10-06", None),
    ("INV-2051", "ven-6201", 7900.00, "PAID", "2026-07-06", "2026-08-05", "2026-08-01"),
    (
        "INV-2052",
        "ven-6204",
        14250.00,
        "PAID",
        "2026-07-01",
        "2026-07-31",
        "2026-07-30",
    ),
    ("INV-2053", "ven-6205", 388.20, "PAID", "2026-07-05", "2026-08-04", "2026-08-03"),
    ("INV-2054", "ven-6203", 2980.00, "PAID", "2026-06-28", "2026-08-12", "2026-08-10"),
    ("INV-2055", "ven-6207", 2750.00, "OVERDUE", "2026-08-12", "2026-09-11", None),
    (
        "INV-2056",
        "ven-6206",
        18500.00,
        "PAID",
        "2026-06-15",
        "2026-07-15",
        "2026-07-14",
    ),
    ("INV-2057", "ven-6208", 5900.00, "PAID", "2026-06-20", "2026-07-04", "2026-07-02"),
    ("INV-2058", "ven-6201", 8100.00, "PAID", "2026-05-08", "2026-06-07", "2026-06-05"),
    ("INV-2059", "ven-6204", 9400.00, "OVERDUE", "2026-08-18", "2026-09-17", None),
    ("INV-2060", "ven-6205", 522.40, "SCHEDULED", "2026-09-24", "2026-10-24", None),
    ("INV-2061", "ven-6203", 3410.00, "PAID", "2026-05-30", "2026-07-14", "2026-07-11"),
    (
        "INV-2062",
        "ven-6206",
        16750.00,
        "PAID",
        "2026-05-12",
        "2026-06-11",
        "2026-06-10",
    ),
    ("INV-2063", "ven-6207", 2750.00, "PAID", "2026-07-12", "2026-08-11", "2026-08-08"),
    ("INV-2064", "ven-6208", 4300.00, "SCHEDULED", "2026-09-26", "2026-10-10", None),
    ("INV-2065", "ven-6202", 1250.00, "PAID", "2026-07-01", "2026-07-16", "2026-07-15"),
]


def _invoice_id(number):
    return f"vinv-{number.split('-')[1]}"


INVOICE_SUMMARIES = [
    {
        "invoice_id": _invoice_id(number),
        "invoice_number": number,
        "vendor_id": vendor,
        "vendor_name": VENDOR_NAME[vendor],
        "amount": amount,
        "currency": "USD",
        "status": status,
        "issue_date": issue,
        "due_date": due,
        "paid_date": paid,
    }
    for number, vendor, amount, status, issue, due, paid in _INVOICES
]

# Approval chains. Only PENDING_APPROVAL invoices are actually waiting on someone;
# this is what answers "why hasn't <vendor> been paid yet".
_APPROVALS = {
    "INV-2041": [
        {
            "step": 1,
            "approver_name": "Saoirse Kavanagh",
            "role": "Payroll Specialist",
            "status": "APPROVED",
            "acted_date": "2026-09-06",
        },
        {
            "step": 2,
            "approver_name": "Beatrix Nolan",
            "role": "Controller",
            "status": "PENDING",
            "acted_date": None,
        },
    ],
    "INV-2044": [
        {
            "step": 1,
            "approver_name": "Saoirse Kavanagh",
            "role": "Payroll Specialist",
            "status": "PENDING",
            "acted_date": None,
        },
    ],
    "INV-2048": [
        {
            "step": 1,
            "approver_name": "Beatrix Nolan",
            "role": "Controller",
            "status": "APPROVED",
            "acted_date": "2026-09-19",
        },
        {
            "step": 2,
            "approver_name": "Rosalind Vane",
            "role": "VP Engineering",
            "status": "PENDING",
            "acted_date": None,
        },
    ],
}

_LINE_ITEMS = {
    "INV-2041": [
        {"description": "Actuator housings (x120)", "amount": 7200.00},
        {"description": "Freight", "amount": 1200.00},
    ],
    "INV-2042": [{"description": "Hosting — August", "amount": 1250.00}],
    "INV-2043": [{"description": "Hosting — September", "amount": 1250.00}],
    "INV-2044": [{"description": "Additional storage tier", "amount": 980.00}],
}


def _invoice_detail(summary):
    number = summary["invoice_number"]
    detail = dict(summary)
    detail["line_items"] = _LINE_ITEMS.get(
        number, [{"description": "Services rendered", "amount": summary["amount"]}]
    )
    approvals = _APPROVALS.get(number)
    if approvals is None:
        approvals = [
            {
                "step": 1,
                "approver_name": "Beatrix Nolan",
                "role": "Controller",
                "status": "APPROVED",
                "acted_date": summary["issue_date"],
            }
        ]
    detail["approvals"] = approvals
    pending = [a for a in approvals if a["status"] == "PENDING"]
    detail["awaiting_approval_from"] = pending[0]["approver_name"] if pending else None
    detail["payment_terms_days"] = next(
        v["payment_terms_days"]
        for v in VENDOR_RECORDS
        if v["vendor_id"] == summary["vendor_id"]
    )
    return detail


VENDOR_INVOICES = {
    "GET /vendor-invoices": ok(INVOICE_SUMMARIES),
    "GET /vendor-invoices/{invoice_id}": {
        "_note": "Keyed by invoice_id. A mock server returns the matching object.",
        "_records": {
            s["invoice_id"]: ok(_invoice_detail(s)) for s in INVOICE_SUMMARIES
        },
    },
}

# --------------------------------------------------------------------------------------
# Payments / transactions
# --------------------------------------------------------------------------------------
_TRANSACTIONS = [
    {
        "transaction_id": "txn-88401",
        "reference": "INV-2046",
        "transaction_type": "ACH",
        "amount": 15600.00,
        "currency": "USD",
        "status": "SETTLED",
        "created_date": "2026-08-27T10:14:00Z",
        "settlement_date": "2026-08-28",
        "failure_reason": None,
        "payment_method": {
            "institution_name": "Meridian Trust Bank",
            "account_last_4": "4417",
        },
    },
    {
        "transaction_id": "txn-88402",
        "reference": "INV-2049",
        "transaction_type": "ACH",
        "amount": 2750.00,
        "currency": "USD",
        "status": "SETTLED",
        "created_date": "2026-09-08T09:02:00Z",
        "settlement_date": "2026-09-09",
        "failure_reason": None,
        "payment_method": {
            "institution_name": "Meridian Trust Bank",
            "account_last_4": "4417",
        },
    },
    {
        "transaction_id": "txn-88403",
        "reference": "INV-2045",
        "transaction_type": "ACH",
        "amount": 3120.00,
        "currency": "USD",
        "status": "FAILED",
        "created_date": "2026-09-12T14:31:00Z",
        "settlement_date": None,
        "failure_reason": "INSUFFICIENT_FUNDS",
        "failure_detail": "The funding account did not have sufficient balance on the settlement date.",
        "payment_method": {
            "institution_name": "Meridian Trust Bank",
            "account_last_4": "4417",
        },
    },
    {
        "transaction_id": "txn-88404",
        "reference": "PAYROLL-2026-09-15",
        "transaction_type": "ACH",
        "amount": 48250.00,
        "currency": "USD",
        "status": "PENDING",
        "created_date": "2026-09-26T16:45:00Z",
        "settlement_date": None,
        "expected_settlement_date": "2026-09-30",
        "failure_reason": None,
        "payment_method": {
            "institution_name": "Meridian Trust Bank",
            "account_last_4": "4417",
        },
    },
]

PAYMENTS = {
    "GET /transactions/{transaction_id}": {
        "_note": "Keyed by transaction_id. A mock server returns the matching object.",
        "_records": {t["transaction_id"]: ok(t) for t in _TRANSACTIONS},
    }
}

FILES = {
    "employees.json": EMPLOYEES,
    "vendors.json": VENDORS,
    "vendor_invoices.json": VENDOR_INVOICES,
    "payments.json": PAYMENTS,
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("*.json"):
        if stale.name not in FILES:
            stale.unlink()
            print(f"  removed {stale.name}")
    for name, payload in FILES.items():
        (OUT / name).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        )
        print(f"  wrote   {name}")
    print(
        f"\n{len(SUMMARIES)} employees · {len(VENDOR_RECORDS)} vendors · "
        f"{len(INVOICE_SUMMARIES)} invoices · {len(_TRANSACTIONS)} transactions"
    )


if __name__ == "__main__":
    main()
