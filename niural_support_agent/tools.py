"""Six thin tools; no hidden payment lookup, filtering or aggregation helpers."""

import json

from agents import function_tool

from mock_api import APIError, MockAPI


def api_error(context, error):
    if isinstance(error, APIError):
        return json.dumps(error.as_dict())
    return json.dumps({"error": {"status": 500, "message": "Mock API request failed."}})


def build_tools(account: MockAPI):
    @function_tool(failure_error_function=api_error)
    def list_employees() -> dict:
        """List the complete employer roster, including statuses, worker types, locations and employee IDs. Use to resolve names before fetching individual detail."""
        return account.list_employees().model_dump(mode="json", exclude_unset=True)

    @function_tool(failure_error_function=api_error)
    def get_employee(employee_id: str) -> dict:
        """Get an employee's onboarding checklist, blockers, payroll eligibility and dismissal details using an employee ID obtained from context or the roster."""
        return account.get_employee(employee_id).model_dump(mode="json", exclude_unset=True)

    @function_tool(failure_error_function=api_error)
    def list_vendors() -> dict:
        """List the employer's vendors and their IDs. Use to resolve a vendor name before relating it to bills."""
        return account.list_vendors().model_dump(mode="json", exclude_unset=True)

    @function_tool(failure_error_function=api_error)
    def list_vendor_invoices() -> dict:
        """List all vendor bills with IDs, vendor names/IDs, amounts, currencies, statuses and dates. This returns summaries, not approval chains or transaction IDs."""
        return account.list_vendor_invoices().model_dump(mode="json", exclude_unset=True)

    @function_tool(failure_error_function=api_error)
    def get_vendor_invoice(invoice_id: str) -> dict:
        """Get one vendor bill's detail, including the approval chain and the named pending approver, using its internal invoice ID."""
        return account.get_vendor_invoice(invoice_id).model_dump(mode="json", exclude_unset=True)

    @function_tool(failure_error_function=api_error)
    def get_payment_status(transaction_id: str) -> dict:
        """Get payment status and failure detail using a transaction ID from the conversation. No payment-list or invoice-to-transaction lookup exists. Never guess an ID."""
        return account.get_payment_status(transaction_id).model_dump(mode="json", exclude_unset=True)

    tools = [list_employees, get_employee, list_vendors, list_vendor_invoices,
             get_vendor_invoice, get_payment_status]
    for tool in tools:
        # Groq requires properties even for functions with no arguments.
        tool.params_json_schema.setdefault("properties", {})
        if not tool.params_json_schema["properties"]:
            tool.params_json_schema.pop("required", None)
    return tools
