"""
Mock x402 Resource Server — powered by Rescontre clearing

Demonstrates the full flow:
  Agent hits API → 402 Payment Required → Agent pays → Rescontre verify → serve resource → Rescontre settle

Requires (example only, not part of the SDK):
  pip install fastapi uvicorn

Run:   python examples/demo_server.py
Test:  python examples/demo_client.py
"""

import os
import json
import uuid
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from rescontre import Client, Direction

# --- Config ---
RESCONTRE_URL = os.getenv("RESCONTRE_URL", "https://rescontre-production.up.railway.app")
SERVER_ID = os.getenv("SERVER_ID", "demo-inference-server")
SERVER_WALLET = "0x2222222222222222222222222222222222222222"
PRICE_PER_CALL = 100_000  # $0.10 in microdollars

app = FastAPI(title="Demo Inference Server (x402 + Rescontre)")

# --- Rescontre client (shared) ---
rescontre = Client(RESCONTRE_URL)


@app.on_event("startup")
def setup():
    """Register this server with Rescontre on startup."""
    try:
        rescontre.register_server(
            SERVER_ID,
            wallet_address=SERVER_WALLET,
            endpoints=["/v1/inference"],
        )
        print(f"✓ Registered server '{SERVER_ID}' with Rescontre")
    except Exception as e:
        # Already registered — that's fine
        print(f"  Server registration: {e}")


@app.get("/health")
def health():
    return {"status": "ok", "server_id": SERVER_ID, "price_per_call": PRICE_PER_CALL}


@app.api_route("/v1/inference", methods=["GET", "POST"])
async def inference(request: Request):
    """
    x402-style flow:
      1. No payment header → return 402
      2. Payment header → verify with Rescontre → serve → settle
    """
    # --- Check for payment header ---
    payment_header = request.headers.get("X-Payment")

    if not payment_header:
        # Return 402 Payment Required
        return JSONResponse(
            status_code=402,
            content={
                "x402Version": 2,
                "error": "payment_required",
                "resource": {
                    "url": "/v1/inference",
                    "description": "LLM inference endpoint — pay per request",
                },
                "accepts": [{
                    "scheme": "rescontre",
                    "price": PRICE_PER_CALL,
                    "currency": "microdollars",
                    "clearinghouse": RESCONTRE_URL,
                    "server_id": SERVER_ID,
                }],
            },
        )

    # --- Parse payment ---
    try:
        payment = json.loads(payment_header)
        agent_id = payment["agent_id"]
        nonce = payment.get("nonce", str(uuid.uuid4()))
    except (json.JSONDecodeError, KeyError):
        return JSONResponse(status_code=400, content={"error": "invalid payment header"})

    # --- Verify with Rescontre ---
    try:
        check = rescontre.verify(agent_id, SERVER_ID, amount=PRICE_PER_CALL, nonce=nonce)
        if not check.valid:
            return JSONResponse(status_code=402, content={
                "error": "payment_rejected",
                "reason": check.reason,
            })
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"verify failed: {e}"})

    # --- Serve the resource ---
    body = {}
    if request.method == "POST":
        try:
            body = await request.json()
        except Exception:
            pass

    prompt = body.get("prompt", "What is the capital of France?")
    result = {
        "model": "demo-llm-v1",
        "prompt": prompt,
        "response": f"[Mock inference result for: {prompt}]",
        "tokens_used": 42,
    }

    # --- Settle with Rescontre ---
    try:
        receipt = rescontre.settle(
            agent_id, SERVER_ID,
            amount=PRICE_PER_CALL,
            nonce=nonce,
            description=f"inference: {prompt[:50]}",
            direction=Direction.AgentToServer,
        )
        result["settlement"] = {
            "commitment_id": receipt.commitment_id,
            "net_position": receipt.net_position,
            "nonce": nonce,
        }
    except Exception as e:
        result["settlement_error"] = str(e)

    return JSONResponse(status_code=200, content=result)


@app.get("/v1/stats")
def stats():
    """Show current clearing stats from Rescontre."""
    try:
        h = rescontre.health()
        return h
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)