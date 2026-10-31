"""Validate account records while preserving all supplied fixture fields."""

from datetime import date
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict

SNAPSHOT_DATE = date(2026, 9, 28)

class Record(BaseModel):
    model_config = ConfigDict(extra="allow")


class WorkLocation(BaseModel):
    city: str
    state: str | None
    country_iso2: str


class OnboardingStep(Record):
    name: str
    status: Literal["COMPLETE", "PENDING"]


class Onboarding(Record):
    complete: bool
    steps: list[OnboardingStep]


class Employee(Record):
    employee_id: str
    first_name: str
    last_name: str
    status: Literal["ONBOARDED", "PENDING_ONBOARDING", "DISMISSED"]
    employment_type: Literal["EMPLOYEE", "US_1099_CONTRACTOR"]
    work_location: WorkLocation
    onboarding: Onboarding | None = None
    payroll_eligible: bool | None = None


class Vendor(Record):
    vendor_id: str
    name: str
    default_currency: str


class Invoice(Record):
    invoice_id: str
    invoice_number: str
    vendor_id: str
    vendor_name: str
    amount: float
    currency: str
    status: Literal["PAID", "OVERDUE", "PENDING_APPROVAL", "SCHEDULED"]
    due_date: date
    paid_date: date | None


class Payment(Record):
    transaction_id: str
    reference: str
    amount: float
    currency: str
    status: Literal["SETTLED", "PENDING", "FAILED"]
    failure_reason: str | None


class Source(BaseModel):
    reference: str
    path: str
    as_of: date = SNAPSHOT_DATE


T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    message: str
    data: T
    source: Source
