from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class Direction(str, Enum):
    AgentToServer = "AgentToServer"
    ServerToAgent = "ServerToAgent"


class Rail(str, Enum):
    X402 = "X402"
    Stripe = "Stripe"
    Crypto = "Crypto"


class CreditTier(str, Enum):
    Minimal = "Minimal"
    Basic = "Basic"
    Established = "Established"
    Trusted = "Trusted"


class VerifyResponse(BaseModel):
    valid: bool
    reason: str | None = None
    remaining_credit: int | None = None


class SettleResponse(BaseModel):
    settled: bool
    commitment_id: str | None = None
    net_position: int | None = None
    commitments_until_settlement: int | None = None


class BilateralSettlementResult(BaseModel):
    agent_id: str
    server_id: str
    gross_volume: int
    net_amount: int
    commitments_netted: int
    compression: float
