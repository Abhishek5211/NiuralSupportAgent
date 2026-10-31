"""Six read-only methods over the supplied JSON fixtures."""

import json
from pathlib import Path

from .auth import AuthContext, EMPLOYER_ID
from .errors import APIError
from .models import APIResponse, Employee, Invoice, Payment, SNAPSHOT_DATE, Source, Vendor

DATA_DIR = Path(__file__).resolve().parent / "data"


class MockAPI:
    def __init__(self, token="local-admin", *, employer_id=EMPLOYER_ID, data_dir=DATA_DIR):
        self.auth = AuthContext(token=token, employer_id=employer_id)
        self.data_dir = Path(data_dir)

    def list_employees(self) -> APIResponse[list[Employee]]:
        return self._read("employees.json", "GET /employer/{employer_id}/employees", list[Employee])

    def get_employee(self, employee_id: str) -> APIResponse[Employee]:
        return self._read("employees.json", "GET /employer/{employer_id}/employee/{employee_id}", Employee, employee_id)

    def list_vendors(self) -> APIResponse[list[Vendor]]:
        return self._read("vendors.json", "GET /vendors", list[Vendor])

    def list_vendor_invoices(self) -> APIResponse[list[Invoice]]:
        return self._read("vendor_invoices.json", "GET /vendor-invoices", list[Invoice])

    def get_vendor_invoice(self, invoice_id: str) -> APIResponse[Invoice]:
        return self._read("vendor_invoices.json", "GET /vendor-invoices/{invoice_id}", Invoice, invoice_id)

    def get_payment_status(self, transaction_id: str) -> APIResponse[Payment]:
        return self._read("payments.json", "GET /transactions/{transaction_id}", Payment, transaction_id)

    def _read(self, filename, route, record_type, record_id=None):
        self.auth.authorize()
        fixtures = json.loads((self.data_dir / filename).read_text(encoding="utf-8"))
        body = fixtures[route]
        if record_id is not None:
            body = body["_records"].get(record_id)
        if body is None:
            raise APIError(404, "Record not found.")

        endpoint = route.format(employer_id=self.auth.employer_id, employee_id=record_id,
                                invoice_id=record_id, transaction_id=record_id)
        label = {"employees.json": "Employee list", "vendors.json": "Vendor list",
                 "vendor_invoices.json": "Vendor bills", "payments.json": "Payment status"}[filename]
        if record_id is not None:
            data = body["data"]
            if filename == "employees.json":
                label = f"{data['first_name']} {data['last_name']} — employee record"
            elif filename == "vendor_invoices.json":
                label = f"{data['vendor_name']} — {data['invoice_number']}, bill details"
            elif filename == "payments.json":
                label = f"Payment — {data['reference']}"
        return APIResponse[record_type](
            message=body["message"],
            data=body["data"],
            source=Source(reference=endpoint, citation_label=label,
                          path=f"mock_api/data/{filename}", as_of=SNAPSHOT_DATE),
        )
