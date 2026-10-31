"""One reusable query tool and three typed detail tools."""

from agents import function_tool
from agents.exceptions import ModelBehaviorError
from pydantic import ValidationError

from mock_api import APIError, MockAPI
from .query import AccountQuery, StrictModel, query_records


class ToolError(StrictModel):
    status: int
    message: str


class ErrorResponse(StrictModel):
    error: ToolError


def api_error(context, error):
    if isinstance(error, APIError):
        status, message = error.status_code, str(error)
    elif isinstance(error, ModelBehaviorError):
        status = 422
        cause = error.__cause__
        message = ("; ".join(item["msg"] for item in cause.errors(include_input=False, include_url=False))
                   if isinstance(cause, ValidationError) else
                   "Invalid arguments. Use the fields, operators and values permitted by the tool schema.")
    else:
        status, message = 500, "Account tool failed. No result was produced."
    return ErrorResponse(error=ToolError(status=status, message=message)).model_dump_json()


def build_tools(account: MockAPI):
    @function_tool(failure_error_function=api_error)
    def query_account(query: AccountQuery) -> str:
        """Filter, select, count or sum authenticated account data using Python.

        Use this for every account list, name lookup, headcount and balance.
        employees fields: employee_id, first_name, last_name, work_email,
        job_title, department, status, employment_type, start_date, manager_name,
        work_location (city, state, country_iso2).
        Active means status=ONBOARDED; EMPLOYEE excludes US_1099_CONTRACTOR.
        vendors fields: vendor_id, name, email, status, default_currency,
        payment_method, payment_terms_days, address (city, country_iso2).
        Select the whole address/work_location object or its dotted fields;
        filtering/grouping requires dotted scalar fields, such as address.city.
        Vendor address contains city/country only, not a street/postal address.
        invoices fields: invoice_id, invoice_number, vendor_id, vendor_name,
        amount, currency, status, issue_date, due_date, paid_date.
        A previous select may return only requested fields. Query other available
        fields when asked; an omitted field is not missing from the dataset.
        Statuses and worker types use exact uppercase API values. Text contains
        is case-insensitive; other comparisons are exact. Filters use AND.
        For outstanding balance exclude PAID, including pending/scheduled bills.
        Sum invoice amount with Decimal; currencies are always kept separate.
        Empty select/groups means no matches, not a tool failure. No pagination.
        Return IDs in selected fields when a follow-up detail lookup is needed.
        Onboarding, dismissal and approval detail require the detail tools.
        """
        readers = {"employees": account.list_employees, "vendors": account.list_vendors,
                   "invoices": account.list_vendor_invoices}
        # Ordinary SDK tools stringify BaseModel objects as Python repr, so
        # explicitly serialize the validated QueryResponse to JSON.
        return query_records(readers[query.resource](), query).model_dump_json()

    @function_tool(failure_error_function=api_error)
    def get_employee(employee_id: str) -> str:
        """Get compensation (salary or hourly amount, currency and ANNUAL/HOURLY frequency), onboarding blockers, payroll eligibility and dismissal details. Resolve names with query_account first unless an ID is already in context."""
        return account.get_employee(employee_id).model_dump_json(exclude_unset=True)

    @function_tool(failure_error_function=api_error)
    def get_vendor_invoice(invoice_id: str) -> str:
        """Get invoice approval details and the pending approver. Resolve the invoice with query_account first unless its internal ID is already in context."""
        return account.get_vendor_invoice(invoice_id).model_dump_json(exclude_unset=True)

    @function_tool(failure_error_function=api_error)
    def get_payment_status(transaction_id: str) -> str:
        """Get payment status and failure detail using a transaction ID supplied in conversation. There is no payment list or invoice-to-transaction lookup; never guess an ID."""
        return account.get_payment_status(transaction_id).model_dump_json(exclude_unset=True)

    return [query_account, get_employee, get_vendor_invoice, get_payment_status]
