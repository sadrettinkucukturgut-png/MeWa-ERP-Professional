from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PackingItem:
    stock_id: int
    stock_code: str
    description: str
    hs_code: str
    quantity: float
    unit: str
    quantity_weight: float
    pallet_no: str
    remarks: str = ""


@dataclass
class PalletStats:
    pallet_no: str
    product_count: int
    total_quantity: float
    total_net_weight: float
    total_gross_weight: float


@dataclass
class PackingTotals:
    total_pallets: int
    total_pieces: float
    total_net_weight: float
    total_gross_weight: float
