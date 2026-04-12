"""End-to-end smoke run of the SDK against a live backend on :3000."""
from __future__ import annotations

import uuid

from rescontre import Client, Direction


def main() -> None:
    run = uuid.uuid4().hex[:8]
    agent_id = f"agent-{run}"
    server_id = f"server-{run}"

    with Client("http://localhost:3000") as c:
        print("health:", c.health()["status"])

        print("register_agent:", c.register_agent(agent_id, "0xAAA" + run))
        print("register_server:", c.register_server(server_id, "0xBBB" + run, ["/api/data"]))
        print(
            "create_agreement:",
            c.create_agreement(
                agent_id, server_id,
                credit_limit=10_000_000,
                settlement_frequency=100,
            ),
        )

        check = c.verify(agent_id, server_id, amount=1_000_000, nonce=f"{run}-n1")
        print("verify:", check.model_dump())
        assert check.valid, check.reason

        receipt = c.settle(
            agent_id, server_id,
            amount=1_000_000,
            nonce=f"{run}-n1",
            description="GET /api/data",
            direction=Direction.AgentToServer,
        )
        print("settle:", receipt.model_dump())
        assert receipt.settled
        assert receipt.commitment_id == f"{run}-n1"
        assert receipt.net_position == 1_000_000

    print("\nOK — end-to-end verified.")


if __name__ == "__main__":
    main()
