"""Typed, fixture-backed account API shared by agent versions."""

from .client import MockAPI
from .errors import APIError

__all__ = ["MockAPI", "APIError"]
