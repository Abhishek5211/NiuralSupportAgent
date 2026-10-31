"""Opt-in benchmark faults; normal conversations have no active fault scope."""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from mock_api import APIError, MockAPI


_active = ContextVar("niural_benchmark_faults", default=None)
_messages = {
    401: "Authentication expired. Reconnect the account before retrying.",
    403: "Access denied for this account resource.",
    503: "Account service temporarily unavailable. No result was produced.",
    504: "Account service timed out. No result was produced.",
}


def validate_faults(rules):
    if not isinstance(rules, list):
        raise ValueError("faults must be a list")
    for rule in rules:
        if (not isinstance(rule, dict) or set(rule) != {"turn", "endpoint", "status"}
                or type(rule["turn"]) is not int or rule["turn"] < 1
                or type(rule["status"]) is not int or rule["status"] not in _messages
                or not isinstance(rule["endpoint"], str)
                or not (rule["endpoint"] in {"*", "RUN"}
                        or rule["endpoint"].startswith("GET /"))):
            raise ValueError("Each fault needs turn >= 1, endpoint (*, RUN or GET /...), and status 401/403/503/504")
        if rule["endpoint"] == "RUN" and rule["status"] != 504:
            raise ValueError("RUN only supports a simulated timeout (504)")


@dataclass
class FailureState:
    rules: list
    turn: int = 0
    events: list = field(default_factory=list)
    exercised: set = field(default_factory=set)

    def apply(self, endpoint):
        for index, rule in enumerate(self.rules):
            if rule["turn"] != self.turn:
                continue
            if rule["endpoint"] != endpoint and not (rule["endpoint"] == "*" and endpoint != "RUN"):
                continue
            self.exercised.add(index)
            self.events.append({"turn": self.turn, "endpoint": endpoint,
                                "status": rule["status"], "rule": index})
            if endpoint == "RUN":
                raise TimeoutError("Simulated benchmark run timeout")
            raise APIError(rule["status"], _messages[rule["status"]])

    def unexercised(self):
        return [index for index in range(len(self.rules)) if index not in self.exercised]


@contextmanager
def failure_scope(rules):
    validate_faults(rules)
    state = FailureState(rules)
    token = _active.set(state)
    try:
        yield state
    finally:
        _active.reset(token)


def raise_run_fault():
    state = _active.get()
    if state is not None:
        state.apply("RUN")


class ScenarioAPI(MockAPI):
    """MockAPI-compatible reads with request-local benchmark fault injection."""

    def _read(self, filename, route, record_type, record_id=None):
        self.auth.authorize()
        state = _active.get()
        if state is not None:
            endpoint = route.format(employer_id=self.auth.employer_id,
                                    employee_id=record_id, invoice_id=record_id,
                                    transaction_id=record_id)
            state.apply(endpoint)
        return super()._read(filename, route, record_type, record_id)
