"""Named Decimal calculations, executed in one tool call."""

from decimal import (
    Context, Decimal, DecimalException, Underflow, ROUND_CEILING, ROUND_FLOOR,
    ROUND_HALF_EVEN, ROUND_HALF_UP, localcontext,
)
from functools import reduce
from math import prod
from operator import sub, truediv
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ROUNDING = {
    "half_up": ROUND_HALF_UP,
    "half_even": ROUND_HALF_EVEN,
    "floor": ROUND_FLOOR,
    "ceiling": ROUND_CEILING,
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Number(StrictModel):
    value: str = Field(max_length=256, description="Finite decimal string, e.g. 5000 or 0.02.")

    @field_validator("value")
    @classmethod
    def finite_number(cls, value):
        try:
            if not Decimal(value).is_finite():
                raise ValueError("Numbers must be finite")
        except DecimalException:
            raise ValueError("Use a finite decimal string") from None
        return value


class Variable(Number):
    name: str = Field(min_length=1, max_length=64)


class Reference(StrictModel):
    ref: str = Field(min_length=1, max_length=64,
                     description="Name of an input variable or an earlier step.")


class Step(StrictModel):
    name: str = Field(min_length=1, max_length=64)
    operation: Literal["sum", "subtract", "multiply", "divide", "average",
                       "min", "max", "floor", "ceil", "round"]
    arguments: list[Number | Reference] = Field(min_length=1, max_length=100)
    places: int | None = Field(default=None, ge=0, le=12,
                               description="Optional result rounding for any operation; e.g. 2 for USD cents.")
    rounding: Literal["half_up", "half_even", "floor", "ceiling"] | None = Field(
        default=None, description="Supply with places; required for round. Floor/ceiling mean toward negative/positive infinity.")

    @model_validator(mode="after")
    def validate_operation(self):
        if self.operation in {"round", "floor", "ceil"} and len(self.arguments) != 1:
            raise ValueError(f"Step {self.name}: {self.operation} requires one argument")
        if self.operation in {"subtract", "divide"} and len(self.arguments) < 2:
            raise ValueError(f"Step {self.name}: {self.operation} requires at least two arguments")
        if (self.places is None) != (self.rounding is None):
            raise ValueError(f"Step {self.name}: supply both places and rounding, or neither")
        if self.operation == "round" and self.places is None:
            raise ValueError(f"Step {self.name}: round requires places and rounding")
        return self


class Calculation(StrictModel):
    variables: list[Variable] = Field(default_factory=list, max_length=100)
    steps: list[Step] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def validate_names(self):
        names = {variable.name for variable in self.variables}
        if len(names) != len(self.variables):
            raise ValueError("Variable names must be unique")
        for step in self.steps:
            if step.name in names:
                raise ValueError(f"Step {step.name}: name duplicates an input or earlier step")
            for argument in step.arguments:
                if isinstance(argument, Reference) and argument.ref not in names:
                    raise ValueError(f"Step {step.name}: unknown or forward reference {argument.ref}")
            names.add(step.name)
        return self


class CalculationResult(StrictModel):
    results: list[Variable]


def calculate(calculation: Calculation) -> CalculationResult:
    values = {variable.name: Decimal(variable.value) for variable in calculation.variables}
    results = []
    # Compute at full context precision, then apply any explicitly requested rounding.
    with localcontext(Context(prec=50, rounding=ROUND_HALF_EVEN, Emax=100, Emin=-100)) as context:
        context.traps[Underflow] = True
        for step in calculation.steps:
            args = [values[arg.ref] if isinstance(arg, Reference) else Decimal(arg.value)
                    for arg in step.arguments]
            try:
                match step.operation:
                    case "sum": result = sum(args, Decimal(0))
                    case "subtract": result = reduce(sub, args)
                    case "multiply": result = prod(args, start=Decimal(1))
                    case "divide": result = reduce(truediv, args)
                    case "average": result = sum(args, Decimal(0)) / len(args)
                    case "min": result = min(args)
                    case "max": result = max(args)
                    case "floor": result = args[0].to_integral_value(rounding=ROUND_FLOOR)
                    case "ceil": result = args[0].to_integral_value(rounding=ROUND_CEILING)
                    case "round": result = args[0]
                if step.places is not None:
                    result = result.quantize(Decimal(1).scaleb(-step.places),
                                             rounding=ROUNDING[step.rounding])
                result = +result  # Apply the bounded Decimal context before formatting.
            except DecimalException as error:
                raise ValueError(f"Step {step.name} failed: {type(error).__name__}") from None
            if not result.is_finite():
                raise ValueError(f"Step {step.name} did not produce a finite number")
            values[step.name] = result
            results.append(Variable(name=step.name, value=format(result, "f")))
    return CalculationResult(results=results)
