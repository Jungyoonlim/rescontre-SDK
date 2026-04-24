from __future__ import annotations

from types import TracebackType
from typing import Any

import httpx

from .errors import RescontreAPIError
from .models import (
    BilateralSettlementResult,
    Direction,
    SettleResponse,
    VerifyResponse,
)

DEFAULT_TIMEOUT = 10.0


class Client:
    """Synchronous HTTP client for the Rescontre facilitator."""

    def __init__(
        self,
        base_url: str = "http://localhost:3000",
        *,
        timeout: float = DEFAULT_TIMEOUT,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._owns_client = http_client is None
        self._http = http_client or httpx.Client(
            base_url=self.base_url, timeout=timeout
        )

    def __enter__(self) -> "Client":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def _request(self, method: str, path: str, *, json: Any = None) -> Any:
        response = self._http.request(method, path, json=json)
        if response.status_code >= 400:
            try:
                body = response.json()
                message = body.get("error") or body.get("message") or response.text
            except ValueError:
                body = response.text
                message = response.text or response.reason_phrase
            raise RescontreAPIError(
                message, status_code=response.status_code, response_body=body
            )
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def register_agent(self, agent_id: str, wallet_address: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/agents",
            json={"id": agent_id, "wallet_address": wallet_address},
        )

    def register_server(
        self,
        server_id: str,
        wallet_address: str,
        endpoints: list[str],
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/servers",
            json={
                "id": server_id,
                "wallet_address": wallet_address,
                "endpoints": endpoints,
            },
        )

    def create_agreement(
        self,
        agent_id: str,
        server_id: str,
        *,
        credit_limit: int | None = None,
        settlement_frequency: int | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/agreements",
            json={
                "agent_id": agent_id,
                "server_id": server_id,
                "credit_limit": credit_limit,
                "settlement_frequency": settlement_frequency,
            },
        )

    def verify(
        self,
        agent_id: str,
        server_id: str,
        amount: int,
        nonce: str,
    ) -> VerifyResponse:
        data = self._request(
            "POST",
            "/internal/verify",
            json={
                "agent_id": agent_id,
                "server_id": server_id,
                "amount": amount,
                "nonce": nonce,
            },
        )
        return VerifyResponse.model_validate(data)

    def settle(
        self,
        agent_id: str,
        server_id: str,
        amount: int,
        nonce: str,
        description: str,
        *,
        direction: Direction | None = None,
    ) -> SettleResponse:
        data = self._request(
            "POST",
            "/internal/settle",
            json={
                "agent_id": agent_id,
                "server_id": server_id,
                "amount": amount,
                "nonce": nonce,
                "description": description,
                "direction": direction.value if direction else None,
            },
        )
        return SettleResponse.model_validate(data)

    def bilateral_settlement(
        self,
        agent_id: str,
        server_id: str,
    ) -> BilateralSettlementResult:
        data = self._request(
            "POST",
            "/settlement",
            json={"agent_id": agent_id, "server_id": server_id},
        )
        return BilateralSettlementResult.model_validate(data)
