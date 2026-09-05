from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID


@dataclass(frozen=True)
class MeteredProviderResult:
    operation_id: UUID
    provider_request_id: str
    outcome: Literal["success", "partial", "failure", "unknown"]
    requested_units: int
    successful_units: int
    provider_cost_micros: int
    provider_cost_currency: str


class MeteredProvider(Protocol):
    """A provider receives only an already-reserved operation identifier."""

    async def execute(
        self,
        *,
        operation_id: UUID,
        requested_units: int,
        idempotency_key: str,
    ) -> MeteredProviderResult: ...


class DeterministicMeteredProvider:
    """Network-free WO-049 fake. Values are TEST ONLY / NOT CUSTOMER PRICING."""

    def __init__(self) -> None:
        self._outcome: Literal["success", "partial", "failure", "unknown"] = "success"
        self._successful_units: int | None = None
        self._cost_micros = 0
        self._results: dict[str, MeteredProviderResult] = {}
        self.execution_count = 0

    def arrange(
        self,
        outcome: Literal["success", "partial", "failure", "unknown"],
        *,
        successful_units: int | None = None,
        provider_cost_micros: int = 0,
    ) -> None:
        self._outcome = outcome
        self._successful_units = successful_units
        self._cost_micros = provider_cost_micros

    async def execute(
        self,
        *,
        operation_id: UUID,
        requested_units: int,
        idempotency_key: str,
    ) -> MeteredProviderResult:
        existing = self._results.get(idempotency_key)
        if existing is not None:
            if existing.operation_id != operation_id or existing.requested_units != requested_units:
                raise ValueError("Provider idempotency key was reused for different work.")
            return existing
        if requested_units <= 0:
            raise ValueError("Requested units must be positive.")
        successful = self._successful_units
        if successful is None:
            successful = requested_units if self._outcome == "success" else 0
        if successful < 0 or successful > requested_units:
            raise ValueError("Successful units must be within the requested quantity.")
        self.execution_count += 1
        result = MeteredProviderResult(
            operation_id=operation_id,
            provider_request_id=f"deterministic:{idempotency_key}",
            outcome=self._outcome,
            requested_units=requested_units,
            successful_units=successful,
            provider_cost_micros=self._cost_micros,
            provider_cost_currency="AUD",
        )
        self._results[idempotency_key] = result
        return result
