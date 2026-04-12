from __future__ import annotations

import httpx
import pytest

from rescontre import Client, Direction, RescontreAPIError


def _mock_client(handler: httpx.MockTransport) -> Client:
    http = httpx.Client(base_url="http://test", transport=handler)
    return Client(base_url="http://test", http_client=http)


def test_end_to_end_happy_path() -> None:
    seen: list[tuple[str, str, dict | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = None
        if request.content:
            import json as _json

            body = _json.loads(request.content)
        seen.append((request.method, request.url.path, body))

        if request.url.path == "/agents":
            return httpx.Response(200, json={"id": body["id"]})
        if request.url.path == "/servers":
            return httpx.Response(200, json={"id": body["id"]})
        if request.url.path == "/agreements":
            return httpx.Response(200, json={"agreement_id": "agr-1"})
        if request.url.path == "/internal/verify":
            return httpx.Response(
                200, json={"valid": True, "reason": None, "remaining_credit": 9_000_000}
            )
        if request.url.path == "/internal/settle":
            return httpx.Response(
                200,
                json={
                    "settled": True,
                    "commitment_id": "cmt-1",
                    "net_position": -1_000_000,
                    "commitments_until_settlement": 99,
                },
            )
        return httpx.Response(404, json={"error": "not found"})

    with _mock_client(httpx.MockTransport(handler)) as c:
        c.register_agent("agent-1", "0xAAA")
        c.register_server("server-1", "0xBBB", ["/api/data"])
        c.create_agreement("agent-1", "server-1", credit_limit=10_000_000)

        v = c.verify("agent-1", "server-1", 1_000_000, "n-1")
        assert v.valid and v.remaining_credit == 9_000_000

        s = c.settle(
            "agent-1",
            "server-1",
            1_000_000,
            "n-1",
            "GET /api/data",
            direction=Direction.AgentToServer,
        )
        assert s.settled
        assert s.commitment_id == "cmt-1"

    paths = [p for _, p, _ in seen]
    assert paths == [
        "/agents",
        "/servers",
        "/agreements",
        "/internal/verify",
        "/internal/settle",
    ]

    settle_body = seen[-1][2]
    assert settle_body["direction"] == "AgentToServer"


def test_api_error_raised() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "insufficient credit"})

    with _mock_client(httpx.MockTransport(handler)) as c:
        with pytest.raises(RescontreAPIError) as ei:
            c.verify("a", "s", 1, "n")
        assert ei.value.status_code == 400
        assert "insufficient credit" in str(ei.value)
