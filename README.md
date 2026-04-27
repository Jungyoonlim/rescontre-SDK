# rescontre

Python SDK for Rescontre, a clearinghouse for agent-to-agent payments. Agents and resource
servers record commitments against a bilateral ledger and settle in periodic
batches instead of on every request.

## Why?

Instead of settling every API call on-chain, Rescontre nets obligations and settles the differences. Up to ~90% fewer settlement transactions. 

## Install

```bash
pip install rescontre
```

## Quickstart

```python
from rescontre import Client, Direction

with Client("http://localhost:3000") as c:
    c.register_agent("agent-1", wallet_address="0xAAA...")
    c.register_server("server-1", wallet_address="0xBBB...", endpoints=["/api/data"])
    c.create_agreement("agent-1", "server-1", credit_limit=10_000_000, settlement_frequency=100)

    check = c.verify("agent-1", "server-1", amount=1_000_000, nonce="n-1")
    assert check.valid, check.reason

    receipt = c.settle(
        "agent-1", "server-1",
        amount=1_000_000, nonce="n-1",
        description="GET /api/data",
        direction=Direction.AgentToServer,
    )
    print(receipt.commitment_id, receipt.net_position)
```

Amounts are integers in microdollars (`$1 == 1_000_000`).

## Connect

```python
# Local development
with Client("http://localhost:3000") as c:

# Production
with Client("https://rescontre-production.up.railway.app") as c:
```

```python
    # After multiple settle calls in both directions...
    result = c.bilateral_settlement("agent-1", "server-1")
    print(f"Gross: ${result.gross_volume / 1_000_000:.2f}")
    print(f"Net:   ${result.net_amount / 1_000_000:.2f}")
    print(f"Compression: {result.compression:.0%}")
```

## Examples

End-to-end demo of the x402 → verify → settle → net flow lives in [`examples/`](./examples). The example server uses FastAPI, which is *not* a dependency of the SDK itself. Install it separately:

```bash
pip install fastapi uvicorn

# Terminal 1
python examples/demo_server.py

# Terminal 2
python examples/demo_client.py
```
