"""Walkthrough of the Rescontre SDK against a facilitator on :3000.

Shows bidirectional commitments accumulating on a bilateral ledger, then
bilateral settlement that nets them into a single transfer.

Run the facilitator first, then: `python demo.py`
"""
from __future__ import annotations

import uuid

import httpx

from rescontre import Client, Direction, RescontreAPIError


def dollars(microdollars: int) -> str:
    return f"${microdollars / 1_000_000:.2f}"


def main() -> None:
    run = uuid.uuid4().hex[:8]
    agent_id = f"agent-{run}"
    server_id = f"server-{run}"

    with Client("http://localhost:3000") as c:
        print(f"[health]  {c.health()['status']}")

        c.register_agent(agent_id, wallet_address="0xAAA" + run)
        c.register_server(
            server_id,
            wallet_address="0xBBB" + run,
            endpoints=["/api/data"],
        )
        c.create_agreement(
            agent_id,
            server_id,
            credit_limit=10_000_000,
            settlement_frequency=100,
        )
        print(f"[setup]   agent={agent_id}  server={server_id}\n")

        # Agent calls server's API three times (agent owes server).
        flow = [
            (1_000_000, Direction.AgentToServer, "GET /api/data"),
            (1_000_000, Direction.AgentToServer, "GET /api/data"),
            (1_000_000, Direction.AgentToServer, "GET /api/data"),
            # Server pays agent back (refund / revenue share).
            (500_000, Direction.ServerToAgent, "refund"),
            (500_000, Direction.ServerToAgent, "revenue share"),
        ]

        for i, (amount, direction, description) in enumerate(flow, start=1):
            nonce = f"{run}-n{i}"

            check = c.verify(agent_id, server_id, amount=amount, nonce=nonce)
            if not check.valid:
                raise SystemExit(f"verify failed: {check.reason}")

            receipt = c.settle(
                agent_id,
                server_id,
                amount=amount,
                nonce=nonce,
                description=description,
                direction=direction,
            )
            arrow = "→" if direction == Direction.AgentToServer else "←"
            print(
                f"[commit]  #{i} {dollars(amount)} {arrow}  "
                f"net={dollars(receipt.net_position or 0)}  "
                f"({description})"
            )

        # The payoff: net everything into a single transfer.
        result = c.bilateral_settlement(agent_id, server_id)
        print()
        print(f"[settle]  commitments netted:  {result.commitments_netted}")
        print(f"[settle]  gross volume:        {dollars(result.gross_volume)}")
        print(f"[settle]  net amount:          {dollars(result.net_amount)}")
        print(f"[settle]  compression:         {result.compression:.0%}")

    print("\nOK")


if __name__ == "__main__":
    try:
        main()
    except httpx.ConnectError:
        raise SystemExit(
            "Could not reach the facilitator at http://localhost:3000.\n"
            "Start it first:  (cd ~/Projects/work/clearinghouse/Rescontre && cargo run)"
        )
    except RescontreAPIError as e:
        raise SystemExit(f"API error {e.status_code}: {e}")
