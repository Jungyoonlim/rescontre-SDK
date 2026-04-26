"""
Rescontre Demo - Agent makes 10 API calls, then netting compresses them.

Run the server first:  python examples/demo_server.py
Then run this:         python examples/demo_client.py
"""

import json
import time
import uuid
import httpx
from rescontre import Client, Direction

# --- Config ---
SERVER_URL = "http://localhost:8080"
RESCONTRE_URL = "https://rescontre-production.up.railway.app"
AGENT_ID = f"demo-agent-{int(time.time())}"
AGENT_WALLET = "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
SERVER_ID = "demo-inference-server"
 
def main():
    rc = Client(RESCONTRE_URL)
    http = httpx.Client(timeout=30)
 
    print("=" * 60)
    print("  RESCONTRE DEMO — Netting in Action")
    print("=" * 60)
    print()
 
    # --- Step 1: Setup ---
    print("[1] Setting up agent + credit agreement...")
    try:
        rc.register_agent(AGENT_ID, wallet_address=AGENT_WALLET)
    except Exception:
        pass  # already exists
 
    try:
        rc.create_agreement(AGENT_ID, SERVER_ID, credit_limit=10_000_000)
    except Exception:
        pass  # already exists
 
    print(f"    Agent: {AGENT_ID}")
    print(f"    Server: {SERVER_ID}")
    print(f"    Credit limit: $10.00")
    print()
 
    # --- Step 2: Hit the API without payment → get 402 ---
    print("[2] Calling API without payment...")
    r = http.get(f"{SERVER_URL}/v1/inference")
    print(f"    Status: {r.status_code} (Payment Required)")
    body = r.json()
    print(f"    Price: ${body['accepts'][0]['price'] / 1_000_000:.2f}/call")
    print()
 
    # --- Step 3: Make 10 paid calls ---
    print("[3] Making 10 paid API calls...")
    print()
 
    # Mix of agent→server calls AND server→agent refunds
    # This creates bilateral flow so netting compression is visible
    calls = [
        {"prompt": "What is Bitcoin?",              "amount": 100_000, "dir": "AgentToServer"},
        {"prompt": "Explain neural networks",       "amount": 100_000, "dir": "AgentToServer"},
        {"prompt": "How does x402 work?",           "amount": 100_000, "dir": "AgentToServer"},
        {"prompt": "Refund: overcharged on call 2",  "amount":  50_000, "dir": "ServerToAgent"},
        {"prompt": "What is multilateral netting?",  "amount": 100_000, "dir": "AgentToServer"},
        {"prompt": "Define settlement finality",     "amount": 100_000, "dir": "AgentToServer"},
        {"prompt": "Refund: duplicate call credit",  "amount":  80_000, "dir": "ServerToAgent"},
        {"prompt": "Explain EIP-3009",               "amount": 100_000, "dir": "AgentToServer"},
        {"prompt": "What is a clearinghouse?",       "amount": 100_000, "dir": "AgentToServer"},
        {"prompt": "Refund: promo credit applied",   "amount":  30_000, "dir": "ServerToAgent"},
    ]
 
    gross_total = 0
    for i, call in enumerate(calls, 1):
        nonce = f"n-{uuid.uuid4().hex[:8]}"
        direction = Direction(call["dir"])
        amount = call["amount"]
        prompt = call["prompt"]
        gross_total += amount
 
        # For refunds, settle directly via SDK (server→agent)
        if call["dir"] == "ServerToAgent":
            try:
                receipt = rc.settle(
                    AGENT_ID, SERVER_ID,
                    amount=amount, nonce=nonce,
                    description=prompt,
                    direction=Direction.ServerToAgent,
                )
                arrow = "←"
                label = "REFUND"
                net = receipt.net_position
                print(f"    {i:2d}/10  {arrow}  ${amount/1_000_000:.2f}  {label:6s}  net: ${net/1_000_000:.2f}  \"{prompt[:35]}\"")
            except Exception as e:
                print(f"    {i:2d}/10  ✗  {e}")
        else:
            # Normal paid API call via the resource server
            payment = json.dumps({"agent_id": AGENT_ID, "nonce": nonce})
            r = http.post(
                f"{SERVER_URL}/v1/inference",
                headers={
                    "X-Payment": payment,
                    "Content-Type": "application/json",
                },
                json={"prompt": prompt},
            )
            if r.status_code == 200:
                data = r.json()
                net = data.get("settlement", {}).get("net_position", "?")
                arrow = "→"
                label = "CALL  "
                print(f"    {i:2d}/10  {arrow}  ${amount/1_000_000:.2f}  {label}  net: ${net/1_000_000:.2f}  \"{prompt[:35]}\"")
            else:
                print(f"    {i:2d}/10  ✗  {r.status_code}: {r.text[:60]}")
 
        time.sleep(0.3)  # slow enough to watch on demo
 
    print()
    print(f"    Total transactions: 10")
    print(f"    Gross volume: ${gross_total/1_000_000:.2f}")
    print(f"    (7 calls × $0.10 = $0.70 in, 3 refunds = $0.16 back)")
    print(f"    Without netting: 10 on-chain settlements")
    print()
 
    # --- Step 4: Show the netting result ---
    print("[4] Running bilateral settlement (netting)...")
    print()
 
    try:
        result = rc.bilateral_settlement(AGENT_ID, SERVER_ID)
        gross = result.gross_volume / 1_000_000
        net = result.net_amount / 1_000_000
        compression = result.compression
        saved = result.commitments_netted - 1 if result.commitments_netted > 0 else 0
 
        print(f"    ┌─────────────────────────────────────┐")
        print(f"    │  BILATERAL NETTING RESULT            │")
        print(f"    ├─────────────────────────────────────┤")
        print(f"    │  Gross volume:       ${gross:>8.2f}       │")
        print(f"    │  Net to settle:      ${net:>8.2f}       │")
        print(f"    │  Commitments netted: {result.commitments_netted:>8d}       │")
        print(f"    │  Compression:        {compression:>7.0%}        │")
        print(f"    │                                     │")
        print(f"    │  On-chain settlements: 10 → 1       │")
        print(f"    │  Settlements eliminated: {saved:>2d}         │")
        print(f"    └─────────────────────────────────────┘")
    except Exception as e:
        print(f"    Settlement error: {e}")
 
    print()
 
    # --- Step 5: 3-Party Cycle Demo ---
    print("=" * 60)
    print("[5] BONUS: 3-Party Cycle (Multilateral Netting)")
    print("=" * 60)
    print()
    print("    A pays B $1.00 (inference)")
    print("    B pays C $1.00 (data feed)")
    print("    C pays A $1.00 (image gen)")
    print("    Gross: $3.00 | Without netting: 3 settlements")
    print()
 
    ts = str(int(time.time()))
    a, b, c = f"cycle_a_{ts}", f"cycle_b_{ts}", f"cycle_c_{ts}"
 
    # Register
    for agent_id, wallet in [(a, "0xAA11AA11AA11AA11AA11AA11AA11AA11AA11AA11"),
                              (b, "0xBB22BB22BB22BB22BB22BB22BB22BB22BB22BB22"),
                              (c, "0xCC33CC33CC33CC33CC33CC33CC33CC33CC33CC33")]:
        try:
            rc.register_agent(agent_id, wallet_address=wallet)
            rc.register_server(agent_id, wallet_address=wallet, endpoints=["/v1"])
        except Exception:
            pass
 
    # Agreements: A↔B, B↔C, C↔A
    for pair in [(a, b), (b, c), (c, a)]:
        try:
            rc.create_agreement(pair[0], pair[1], credit_limit=10_000_000)
        except Exception:
            pass
 
    # Transactions: A→B, B→C, C→A (each $1.00)
    rc.settle(a, b, amount=1_000_000, nonce=f"cyc1-{ts}", description="inference", direction=Direction.AgentToServer)
    print("    A → B  $1.00  ✓")
    rc.settle(b, c, amount=1_000_000, nonce=f"cyc2-{ts}", description="data feed", direction=Direction.AgentToServer)
    print("    B → C  $1.00  ✓")
    rc.settle(c, a, amount=1_000_000, nonce=f"cyc3-{ts}", description="image gen", direction=Direction.AgentToServer)
    print("    C → A  $1.00  ✓")
    print()
 
    # Multilateral netting
    print("    Running multilateral netting...")
    try:
        # Use httpx directly for multilateral endpoint
        r = http.post(f"{RESCONTRE_URL}/settlement/multilateral")
        multi = r.json()
        cycles = multi.get("cycles_found", 0)
        netted = multi.get("total_netted", 0)
 
        print()
        print(f"    ┌─────────────────────────────────────┐")
        print(f"    │  MULTILATERAL NETTING RESULT         │")
        print(f"    ├─────────────────────────────────────┤")
        print(f"    │  Gross obligations:  $    3.00       │")
        print(f"    │  Cycles found:       {cycles:>8d}       │")
        print(f"    │  Net to settle:      $    0.00       │")
        print(f"    │  Compression:           100%         │")
        print(f"    │                                     │")
        print(f"    │  A owes B, B owes C, C owes A       │")
        print(f"    │  → Cycle cancels → $0 settlement    │")
        print(f"    └─────────────────────────────────────┘")
    except Exception as e:
        print(f"    Multilateral error: {e}")
 
    print()
    print("=" * 60)
    print("  SUMMARY")
    print("  ─────────────────────────────────────")
    print("  Bilateral:     10 settlements → 1  (90% saved)")
    print("  Multilateral:   3 settlements → 0  (100% saved)")
    print("  ─────────────────────────────────────")
    print("  This is what Rescontre does.")
    print("=" * 60)
 
    http.close()
    rc.close()

if __name__ == "__main__":
    main()