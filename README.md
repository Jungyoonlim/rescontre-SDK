# rescontre

Python SDK for [Rescontre](https://github.com/Jungyoonlim/Rescontre), an
x402-style clearinghouse for agent-to-agent payments. Agents and resource
servers record commitments against a bilateral ledger and settle in periodic
batches instead of on every request.

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

## Links

- Main repo: <https://github.com/Jungyoonlim/Rescontre>
