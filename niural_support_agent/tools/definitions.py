"""Account queries, detail lookups and one batched Decimal calculator."""

import json

from agents import function_tool
from agents.exceptions import ModelBehaviorError
from pydantic import ValidationError

from mock_api import APIError, MockAPI
from .calculator import Calculation, calculate as run_calculation
from .query import AccountQuery, StrictModel, invoice_identifier_field, query_records
from ..retrieval import GuideRetriever, IndexNotReadyError


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
        status, message = 500, "Tool failed. No result was produced."
    return ErrorResponse(error=ToolError(status=status, message=message)).model_dump_json()


def calculator_error(context, error):
    # The SDK may redact the original ValidationError; recover safe field messages.
    try:
        payload = json.loads(context.tool_arguments)["calculation"]
        Calculation.model_validate(payload)
    except ValidationError as validation:
        messages = []
        for issue in validation.errors(include_input=False, include_url=False, include_context=False):
            message = issue["msg"].removeprefix("Value error, ")
            location = issue["loc"]
            if len(location) > 1 and location[0] in {"steps", "variables"}:
                item = payload[location[0]][location[1]]
                name = item.get("name") if isinstance(item, dict) else None
                label = "Step" if location[0] == "steps" else "Variable"
                if not message.startswith(f"{label} "):
                    message = f"{label} {name or '#' + str(location[1] + 1)}: {message}"
            messages.append(message)
        message = "; ".join(dict.fromkeys(messages))
    except (json.JSONDecodeError, KeyError, TypeError):
        message = "Supply a valid JSON object with a calculation containing variables and steps"
    else:
        return api_error(context, error)
    return ErrorResponse(error=ToolError(status=422, message=message)).model_dump_json()


def build_tools(account: MockAPI, guide: GuideRetriever | None = None):
    @function_tool(failure_error_function=api_error)
    def query_account(query: AccountQuery) -> str:
        """Filter, select, count, sum, average and sort authenticated account data.

        Use this for every account list, name lookup, headcount and balance.
        employees fields: employee_id, first_name, last_name, work_email,
        job_title, department, status, employment_type, start_date, manager_name,
        work_location (city, state, country_iso2).
        State values are abbreviations (NY, CA); city values are stored names
        (New York, Brooklyn). Always state city/state scope; clarify ambiguity.
        Employee compensation (amount, currency, frequency) is available: this
        tool fetches matching employee details internally when needed. Select
        compensation or its dotted fields. ANNUAL is salary; HOURLY is a rate.
        Use aggregate_field=compensation.amount for employee sum/average;
        currency and frequency are automatically kept in separate groups.
        Active means status=ONBOARDED; EMPLOYEE excludes US_1099_CONTRACTOR.
        vendors fields: vendor_id, name, email, status, default_currency,
        payment_method, payment_terms_days, address (city, country_iso2).
        Select the whole address/work_location object or its dotted fields;
        filtering/grouping requires dotted scalar fields, such as address.city.
        Vendor address contains city/country only, not a street/postal address.
        invoices fields: invoice_id, invoice_number, vendor_id, vendor_name,
        amount, currency, status, issue_date, due_date, paid_date.
        invoice_id is the internal vinv-... ID; invoice_number is the printed INV-... number.
        They are different fields, not interchangeable or convertible identifiers.
        A previous select may return only requested fields. Query other available
        fields when asked; an omitted field is not missing from the dataset.
        Statuses and worker types use exact uppercase API values. Text contains
        is case-insensitive; other comparisons are exact. Filters use AND.
        For outstanding balance exclude PAID, including pending/scheduled bills.
        Use aggregate_field=amount for invoice sum/average, grouped by currency.
        Invoice selects also return aggregates: Python sums for ALL matching
        records by currency, even if amount/currency were not selected. Use these
        totals when listing bills plus a balance. They are outstanding balances
        only when PAID is excluded. Never add row amounts yourself.
        order_by sorts records by scalar fields, or aggregates by group_by fields
        and value. For salary rankings filter to one currency and frequency.
        Sums and averages use Decimal; aggregate count is its contributing rows.
        Empty select/groups means no matches, not a tool failure. No pagination.
        Return IDs in selected fields when a follow-up detail lookup is needed.
        Onboarding, dismissal and approval detail require the detail tools.
        """
        readers = {"employees": account.list_employees, "vendors": account.list_vendors,
                   "invoices": account.list_vendor_invoices}
        # Ordinary SDK tools stringify BaseModel objects as Python repr, so
        # explicitly serialize the validated QueryResponse to JSON.
        return query_records(readers[query.resource](), query,
                             get_employee=account.get_employee).model_dump_json()

    @function_tool(failure_error_function=api_error)
    def get_employee(employee_id: str) -> str:
        """Get compensation (salary or hourly amount, currency and ANNUAL/HOURLY frequency), onboarding blockers, payroll eligibility and dismissal details. Resolve names with query_account first unless an ID is already in context."""
        return account.get_employee(employee_id).model_dump_json(exclude_unset=True)

    @function_tool(failure_error_function=api_error)
    def get_vendor_invoice(invoice_id: str) -> str:
        """Get invoice approvals and the pending approver using invoice_id (vinv-...).

        For a printed invoice_number (INV-...), first select its invoice_id with
        query_account. Never convert one identifier into the other.
        """
        if invoice_identifier_field(invoice_id) == "invoice_number":
            raise APIError(422, "Use an internal invoice_id (vinv-...). Resolve the printed invoice_number with query_account first.")
        return account.get_vendor_invoice(invoice_id).model_dump_json(exclude_unset=True)

    @function_tool(failure_error_function=api_error)
    def get_payment_status(transaction_id: str) -> str:
        """Get payment status and failure detail using a transaction ID supplied in conversation. There is no payment list or invoice-to-transaction lookup; never guess an ID."""
        return account.get_payment_status(transaction_id).model_dump_json(exclude_unset=True)

    @function_tool(failure_error_function=calculator_error)
    def calculate(calculation: Calculation) -> str:
        """Compute a complete hypothetical scenario in one batch using Decimal.

        Supply named variables from tool evidence or explicit user assumptions.
        Each step has a unique name, operation and arguments: {value: "12"} for
        a decimal literal, or {ref: "salary"} for a variable or earlier result.
        subtract/divide evaluate left to right. Any operation can round its result:
        supply both places and rounding (half_up, half_even, floor, ceiling), or
        leave both null. USD uses 2 places. Standalone round requires both fields.
        Later steps use the rounded result. Do not round intermediates unless
        required by the request. Keep quantities with different meanings or
        units separate; choose formulas from the request, not from examples.
        All steps run locally in one call. Results are decimal strings. This tool
        verifies arithmetic, not input provenance, currency compatibility or the
        business meaning of your formulas. It never changes accounts or payments.
        """
        try:
            return run_calculation(calculation).model_dump_json()
        except ValueError as error:
            return ErrorResponse(error=ToolError(status=422, message=str(error))).model_dump_json()

    tools = [query_account, get_employee, get_vendor_invoice, get_payment_status, calculate]
    if guide is not None:
        @function_tool(failure_error_function=api_error)
        async def search_product_guide(query: str) -> str:
            """Find product instructions, UI labels and explanations in Niural's guide.

            Use for how-to and product questions; include the subject in follow-ups.
            Account-specific facts require account tools. Results include section IDs,
            headings and excerpts for citations, ordered by hybrid keyword/vector rank.
            Distance is vector-only; scores are not confidence. Missing evidence
            requires clarification or support.
            """
            try:
                return (await guide.search(query)).model_dump_json()
            except IndexNotReadyError as error:
                return ErrorResponse(error=ToolError(status=503, message=str(error))).model_dump_json()
            except ValueError as error:
                return ErrorResponse(error=ToolError(status=422, message=str(error))).model_dump_json()
        tools.append(search_product_guide)
    return tools
