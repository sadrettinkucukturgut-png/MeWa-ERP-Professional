from __future__ import annotations

from dataclasses import replace
from typing import Iterable, List

from models.packing_model import PackingItem


class PalletAssignmentService:
    @staticmethod
    def move_items_to_pallet(items: List[PackingItem], indexes: Iterable[int], destination_pallet: str) -> None:
        target = str(destination_pallet or "").strip()
        if not target:
            return
        for index in sorted(set(indexes)):
            if 0 <= index < len(items):
                items[index].pallet_no = target

    @staticmethod
    def duplicate_items(items: List[PackingItem], indexes: Iterable[int]) -> List[PackingItem]:
        duplicates: List[PackingItem] = []
        for index in sorted(set(indexes)):
            if 0 <= index < len(items):
                duplicates.append(replace(items[index]))
        return duplicates

    @staticmethod
    def delete_items(items: List[PackingItem], indexes: Iterable[int]) -> None:
        for index in sorted(set(indexes), reverse=True):
            if 0 <= index < len(items):
                del items[index]

    @staticmethod
    def split_item_to_pallet(
        items: List[PackingItem],
        index: int,
        move_quantity: float,
        destination_pallet: str,
    ) -> tuple[bool, str]:
        if index < 0 or index >= len(items):
            return False, "Selected product row is invalid."

        destination = str(destination_pallet or "").strip()
        if not destination:
            return False, "Destination pallet is required."

        qty = float(move_quantity or 0)
        if qty <= 0:
            return False, "Move quantity must be greater than 0."

        source_item = items[index]
        source_qty = float(source_item.quantity or 0)
        if qty >= source_qty:
            return False, "Move quantity must be less than available quantity."

        source_item.quantity = source_qty - qty
        moved_item = replace(source_item)
        moved_item.quantity = qty
        moved_item.pallet_no = destination
        items.insert(index + 1, moved_item)
        return True, ""
