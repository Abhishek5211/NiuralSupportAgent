"""A small query language over authenticated, Pydantic-validated API records."""

from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mock_api.models import APIResponse, Source


Resource = Literal["employees", "vendors", "invoices"]
Scalar = str | int | float | bool | None
RecordValue = Scalar | dict[str, Scalar]

# Only fields present in the list endpoints can be queried. Detail fields require
# the corresponding detail tool, not an invented filter on incomplete data.
FIELDS = {
    "employees": {
        "employee_id", "first_name", "last_name", "status", "employment_type",
        "work_email", "job_title", "department", "start_date", "manager_name",
        "work_location", "work_location.city", "work_location.state", "work_location.country_iso2",
    },
    "vendors": {
        "vendor_id", "name", "email", "status", "default_currency", "payment_method",
        "payment_terms_days", "address", "address.city", "address.country_iso2",
    },
    "invoices": {
        "invoice_id", "invoice_number", "vendor_id", "vendor_name", "amount",
        "currency", "status", "issue_date", "due_date", "paid_date",
    },
}
# Generate the schema enum from the catalog so they cannot drift apart.
QueryField = StrEnum("QueryField", {
    field.upper().replace(".", "_"): field
    for field in sorted(set().union(*FIELDS.values()))
})
OBJECT_FIELDS = {"address", "work_location"}
DATE_FIELDS = {"start_date", "issue_date", "due_date", "paid_date"}
NUMBER_FIELDS = {"amount", "payment_terms_days"}
ENUMS = {
    ("employees", "status"): {"ONBOARDED", "PENDING_ONBOARDING", "DISMISSED"},
    ("employees", "employment_type"): {"EMPLOYEE", "US_1099_CONTRACTOR"},
    ("vendors", "status"): {"ACTIVE"},
    ("vendors", "payment_method"): {"ACH", "WIRE"},
    ("invoices", "status"): {"PAID", "OVERDUE", "PENDING_APPROVAL", "SCHEDULED"},
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def typed_value(field: str, value: str | None):
    if value is None:
        return None
    if field in DATE_FIELDS:
        return date.fromisoformat(value)
    if field in NUMBER_FIELDS:
        number = Decimal(value)
        if not number.is_finite():
            raise ValueError("Numeric filters must be finite decimal numbers")
        return number
    return value


class QueryFilter(StrictModel):
    field: QueryField
    operator: Literal["eq", "ne", "in", "lt", "lte", "gt", "gte", "contains"]
    value: str | list[str] | None = Field(
        description="Use exact API strings; dates YYYY-MM-DD, numeric values decimal strings. "
                    "For in use a nonempty list; null is allowed only with eq/ne. "
                    "contains is a case-insensitive substring match."
    )

    @model_validator(mode="after")
    def validate_value(self):
        if self.operator == "in":
            if not isinstance(self.value, list) or not 1 <= len(self.value) <= 50:
                raise ValueError("in requires a list of 1 to 50 strings")
        elif isinstance(self.value, list):
            raise ValueError("Only in accepts a list")
        if self.value is None and self.operator not in {"eq", "ne"}:
            raise ValueError("null supports only eq and ne")
        if self.operator == "contains" and self.field in DATE_FIELDS | NUMBER_FIELDS:
            raise ValueError("contains requires a text field")
        values = self.value if isinstance(self.value, list) else [self.value]
        try:
            for value in values:
                typed_value(self.field, value)
        except (ValueError, InvalidOperation):
            raise ValueError("Use valid YYYY-MM-DD dates or finite numeric values") from None
        return self


class AccountQuery(StrictModel):
    resource: Resource
    operation: Literal["select", "count", "sum"]
    filters: list[QueryFilter] = Field(default_factory=list, max_length=12,
                                      description="All filters are combined with AND. Empty means all records.")
    fields: list[QueryField] = Field(default_factory=list, max_length=18,
                                    description="select only: fields to return. Empty returns all available top-level list fields. "
                                                "Select address/work_location for the whole object, or use dotted paths for specific parts.")
    group_by: list[QueryField] = Field(default_factory=list, max_length=3,
                                      description="count/sum only. Sum always groups by currency as well.")
    sum_field: Literal["amount"] | None = Field(default=None,
                                               description="Required for sum; only invoice amount can be summed.")

    @model_validator(mode="after")
    def validate_query(self):
        requested = set(self.fields + self.group_by + [f.field for f in self.filters])
        if not requested <= FIELDS[self.resource]:
            raise ValueError(f"Available {self.resource} fields: {', '.join(sorted(FIELDS[self.resource]))}")
        scalar_fields = set(self.group_by + [f.field for f in self.filters])
        if scalar_fields & OBJECT_FIELDS:
            raise ValueError("Filters/grouping require scalar fields, such as address.city or work_location.state")
        if self.operation == "sum":
            if self.resource != "invoices" or self.sum_field != "amount":
                raise ValueError("sum requires resource=invoices and sum_field=amount")
        elif self.sum_field is not None:
            raise ValueError("sum_field is only valid for sum")
        if self.operation != "select" and self.fields:
            raise ValueError("fields is only valid for select")
        if self.operation == "select" and self.group_by:
            raise ValueError("group_by is only valid for count or sum")
        if len(set(self.fields)) != len(self.fields) or len(set(self.group_by)) != len(self.group_by):
            raise ValueError("fields and group_by cannot contain duplicates")
        for condition in self.filters:
            choices = ENUMS.get((self.resource, condition.field))
            values = condition.value if isinstance(condition.value, list) else [condition.value]
            if choices and (condition.operator not in {"eq", "ne", "in"} or
                            any(value not in choices for value in values)):
                raise ValueError(f"{condition.field} requires eq/ne/in with: {', '.join(sorted(choices))}")
        return self


class Aggregate(StrictModel):
    group: dict[str, Scalar]
    value: int | str = Field(description="Integer count or exact decimal sum as a string.")


class QueryResponse(StrictModel):
    query: AccountQuery
    matched_count: int = Field(ge=0)
    records: list[dict[str, RecordValue]] = Field(default_factory=list)
    aggregates: list[Aggregate] = Field(default_factory=list)
    source: Source


def field_value(record: dict, field: str):
    value = record
    for part in field.split("."):
        value = value[part]
    return value


def matches(record: dict, condition: QueryFilter) -> bool:
    raw = field_value(record, condition.field)
    actual = typed_value(condition.field, str(raw)) if raw is not None else None
    if condition.operator == "in":
        return actual in [typed_value(condition.field, v) for v in condition.value]
    expected = typed_value(condition.field, condition.value)
    if condition.operator == "eq":
        return actual == expected
    if condition.operator == "ne":
        return actual != expected
    # Missing dates/locations never satisfy ordering or substring conditions.
    if actual is None or expected is None:
        return False
    if condition.operator == "contains":
        return expected.casefold() in actual.casefold()
    if condition.operator == "lt":
        return actual < expected
    if condition.operator == "lte":
        return actual <= expected
    if condition.operator == "gt":
        return actual > expected
    return actual >= expected


def query_records(response: APIResponse, query: AccountQuery) -> QueryResponse:
    """Reusable executor: no model arithmetic, SQL, eval, or fixture-file access."""
    rows = [record.model_dump(mode="json", exclude_unset=True) for record in response.data]
    rows = [row for row in rows if all(matches(row, f) for f in query.filters)]
    if query.operation == "select":
        fields = query.fields or sorted(field for field in FIELDS[query.resource] if "." not in field)
        records = [{field: field_value(row, field) for field in fields} for row in rows]
        return QueryResponse(query=query, matched_count=len(rows), records=records,
                             source=response.source)

    group_by = list(query.group_by)
    if query.operation == "sum" and "currency" not in group_by:
        group_by.append("currency")
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(field_value(row, field) for field in group_by)].append(row)
    # Ungrouped counts return zero on empty results. Empty grouped results/sums
    # remain empty; never invent a currency for an account with no matching bills.
    if not group_by and not rows:
        groups[()] = []
    aggregates = []
    for key, members in groups.items():
        value = (len(members) if query.operation == "count" else
                 format(sum((Decimal(str(row["amount"])) for row in members), Decimal(0)), "f"))
        aggregates.append(Aggregate(group=dict(zip(group_by, key)), value=value))
    return QueryResponse(query=query, matched_count=len(rows), aggregates=aggregates,
                         source=response.source)
