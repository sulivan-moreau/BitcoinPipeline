"""Schémas Pydantic pour les relevés de prix Bitcoin."""

from pydantic import BaseModel


class PriceItem(BaseModel):
    id: int
    source: str
    price_usd: float
    timestamp: str
    collected_at: str
