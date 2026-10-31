"""A small query language over authenticated, Pydantic-validated API records."""

from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mock_api import APIError
from mock_api.models import APIResponse, Source


Resource = Literal["employees", "vendors", "invoices"]
Scalar = str | int | float | bool | None
RecordValue = Scalar | dict[str, Scalar]

# Compensation is fetched from employee details only when the query needs it.
COMPENSATION_FIELDS = {
    "compensation", "compensation.amount", "compensation.currency", "compensation.frequency",
}
FIELDS = {
    "employees": {
        "employee_id", "first_name", "last_name", "status", "employment_type",
        "work_email", "job_title", "department", "start_date", "manager_name",
        "work_location", "work_location.city", "work_location.state", "work_location.country_iso2",
    } | COMPENSATION_FIELDS,
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
OBJECT_FIELDS = {"address", "work_location", "compensation"}
DATE_FIELDS = {"start_date", "issue_date", "due_date", "paid_date"}
NUMBER_FIELDS = {"amount", "payment_terms_days", "compensation.amount"}
ENUMS = {
    ("employees", "status"): {"ONBOARDED", "PENDING_ONBOARDING", "DISMISSED"},
    ("employees", "employment_type"): {"EMPLOYEE", "US_1099_CONTRACTOR"},
    ("employees", "compensation.frequency"): {"ANNUAL", "HOURLY"},
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


class QueryOrder(StrictModel):
    field: QueryField | Literal["value"]
    direction: Literal["asc", "desc"] = "asc"


class AccountQuery(StrictModel):
    resource: Resource
    operation: Literal["select", "count", "sum", "average"]
    filters: list[QueryFilter] = Field(default_factory=list, max_length=12,
                                      description="All filters are combined with AND. Empty means all records.")
    fields: list[QueryField] = Field(default_factory=list, max_length=18,
                                    description="select only: fields to return. Empty returns all available top-level list fields. "
                                                "Select address/work_location/compensation for the whole object, or use dotted paths.")
    group_by: list[QueryField] = Field(default_factory=list, max_length=3,
                                      description="count/sum/average only. Monetary aggregates also group by currency and compensation frequency.")
    aggregate_field: Literal["amount", "compensation.amount"] | None = Field(
        default=None, description="sum/average only: invoice amount or employee compensation.amount.")
    order_by: list[QueryOrder] = Field(default_factory=list, max_length=3,
                                     description="Sort select records by scalar fields; aggregates by group fields or value. Nulls last.")

    @property
    def requested_fields(self) -> set[str]:
        return set(self.fields + self.group_by + [f.field for f in self.filters]
                   + [o.field for o in self.order_by if o.field != "value"]
                   + ([self.aggregate_field] if self.aggregate_field else []))

    @model_validator(mode="after")
    def validate_query(self):
        requested = self.requested_fields
        if not requested <= FIELDS[self.resource]:
            raise ValueError(f"Available {self.resource} fields: {', '.join(sorted(FIELDS[self.resource]))}")
        scalar_fields = set(self.group_by + [f.field for f in self.filters] + [o.field for o in self.order_by])
        if scalar_fields & OBJECT_FIELDS:
            raise ValueError("Filters/grouping/sorting require scalar fields, such as address.city")
        if self.operation in {"sum", "average"}:
            expected = {"invoices": "amount", "employees": "compensation.amount"}.get(self.resource)
            if expected is None or self.aggregate_field != expected:
                raise ValueError("sum/average require invoice amount or employee compensation.amount")
        elif self.aggregate_field is not None:
            raise ValueError("aggregate_field is only valid for sum or average")
        if self.operation != "select" and self.fields:
            raise ValueError("fields is only valid for select")
        if self.operation == "select" and self.group_by:
            raise ValueError("group_by is only valid for count, sum or average")
        if len(set(self.fields)) != len(self.fields) or len(set(self.group_by)) != len(self.group_by):
            raise ValueError("fields and group_by cannot contain duplicates")
        sort_fields = [order.field for order in self.order_by]
        if len(set(sort_fields)) != len(sort_fields):
            raise ValueError("order_by cannot contain duplicate fields")
        allowed_sort = FIELDS[self.resource] if self.operation == "select" else set(self.group_by) | {"value"}
        if not set(sort_fields) <= allowed_sort:
            raise ValueError("Sort select records by resource fields; aggregates by group_by fields or value")
        for condition in self.filters:
            choices = ENUMS.get((self.resource, condition.field))
            values = condition.value if isinstance(condition.value, list) else [condition.value]
            if choices and (condition.operator not in {"eq", "ne", "in"} or
                            any(value not in choices for value in values)):
                raise ValueError(f"{condition.field} requires eq/ne/in with: {', '.join(sorted(choices))}")
        return self


class Aggregate(StrictModel):
    group: dict[str, Scalar]
    value: int | str = Field(description="Integer count or decimal sum/average as a string.")
    count: int = Field(ge=0, description="Number of records contributing to this aggregate.")


class QueryResponse(StrictModel):
    query: AccountQuery
    matched_count: int = Field(ge=0)
    records: list[dict[str, RecordValue]] = Field(default_factory=list)
    aggregates: list[Aggregate] = Field(default_factory=list,
        description="Computed aggregates; invoice selects also include sums of all matching bills by currency.")
    source: Source
    detail_sources: list[Source] = Field(default_factory=list)


def field_value(record: dict, field: str):
    if field in record:
        return record[field]
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


def sort_rows(rows: list[dict], orders: list[QueryOrder]) -> list[dict]:
    """Stable multi-column sorting, with nulls last in either direction."""
    for order in reversed(orders):
        present = [row for row in rows if field_value(row, order.field) is not None]
        missing = [row for row in rows if field_value(row, order.field) is None]
        def key(row):
            value = field_value(row, order.field)
            return Decimal(str(value)) if order.field == "value" else typed_value(order.field, str(value))
        rows = sorted(present, key=key, reverse=order.direction == "desc") + missing
    return rows


def invoice_identifier_field(value: str | None) -> str | None:
    if value and value.casefold().startswith("vinv-"):
        return "invoice_id"
    if value and value.casefold().startswith("inv-"):
        return "invoice_number"
    return None


def aggregate_rows(rows, operation, group_by, aggregate_field=None):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(field_value(row, field) for field in group_by)].append(row)
    # Do not invent a currency when grouped monetary results are empty.
    if not group_by and not rows:
        groups[()] = []
    aggregates = []
    for key, members in groups.items():
        value = len(members)
        if operation in {"sum", "average"}:
            total = sum((Decimal(str(field_value(row, aggregate_field))) for row in members), Decimal(0))
            value = format(total / len(members) if operation == "average" else total, "f")
        aggregates.append(Aggregate(group=dict(zip(group_by, key)), value=value, count=len(members)))
    return aggregates


def query_records(response: APIResponse, query: AccountQuery, *, get_employee=None) -> QueryResponse:
    """Filter first, fetch required details, then aggregate or sort in Python."""
    for condition in query.filters:
        if condition.field in {"invoice_id", "invoice_number"}:
            values = condition.value if isinstance(condition.value, list) else [condition.value]
            for value in values:
                expected = invoice_identifier_field(value)
                if expected and expected != condition.field:
                    raise APIError(422, f"Use {expected} for {value}, not {condition.field}. Do not convert identifiers.")
    rows = [record.model_dump(mode="json", exclude_unset=True) for record in response.data]
    list_filters = [f for f in query.filters if f.field not in COMPENSATION_FIELDS]
    rows = [row for row in rows if all(matches(row, f) for f in list_filters)]
    detail_sources = []
    if rows and query.requested_fields & COMPENSATION_FIELDS:
        if get_employee is None:
            raise APIError(422, "Compensation queries require an employee detail reader")
        for row in rows:
            detail = get_employee(row["employee_id"])
            if detail.data.compensation is None:
                raise APIError(502, f"Compensation is missing for {row['employee_id']}; no result was computed")
            row["compensation"] = detail.data.compensation.model_dump(mode="json")
            detail_sources.append(detail.source)
    detail_filters = [f for f in query.filters if f.field in COMPENSATION_FIELDS]
    rows = [row for row in rows if all(matches(row, f) for f in detail_filters)]
    if query.operation == "select":
        if any(o.field == "compensation.amount" for o in query.order_by):
            units = {(row["compensation"]["currency"], row["compensation"]["frequency"]) for row in rows}
            if len(units) > 1:
                raise APIError(422, "Filter compensation to one currency and frequency before ranking amounts")
        rows = sort_rows(rows, query.order_by)
        fields = query.fields or sorted(field for field in FIELDS[query.resource]
                                        if "." not in field and field != "compensation")
        records = [{field: field_value(row, field) for field in fields} for row in rows]
        totals = aggregate_rows(rows, "sum", ["currency"], "amount") if query.resource == "invoices" else []
        return QueryResponse(query=query, matched_count=len(rows), records=records,
                             aggregates=totals,
                             source=response.source, detail_sources=detail_sources)

    group_by = list(query.group_by)
    if query.operation in {"sum", "average"}:
        units = (["compensation.currency", "compensation.frequency"]
                 if query.resource == "employees" else ["currency"])
        group_by.extend(field for field in units if field not in group_by)
    aggregates = aggregate_rows(rows, query.operation, group_by, query.aggregate_field)
    if query.operation in {"sum", "average"} and any(o.field == "value" for o in query.order_by):
        if len({tuple(a.group[field] for field in units) for a in aggregates}) > 1:
            raise APIError(422, "Filter to one currency and pay frequency before ranking monetary aggregates")
    sortable = [dict(a.group, value=a.value, _aggregate=a) for a in aggregates]
    aggregates = [row["_aggregate"] for row in sort_rows(sortable, query.order_by)]
    return QueryResponse(query=query, matched_count=len(rows), aggregates=aggregates,
                         source=response.source, detail_sources=detail_sources)
