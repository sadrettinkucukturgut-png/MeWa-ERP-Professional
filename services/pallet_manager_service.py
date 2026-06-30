from __future__ import annotations

from typing import Dict, List, Tuple

from models.packing_model import PackingItem


class PalletManagerService:
    @staticmethod
    def ensure_pallet(pallet_order: List[str], pallet_weights: Dict[str, float], pallet_no: str, default_weight: float = 25.0) -> None:
        name = str(pallet_no or "").strip()
        if not name:
            return
        if name not in pallet_order:
            pallet_order.append(name)
        if name not in pallet_weights:
            pallet_weights[name] = float(default_weight)

    @staticmethod
    def next_auto_name(pallet_order: List[str], prefix: str = "Pallet") -> str:
        index = 1
        known = {str(name).strip().lower() for name in pallet_order}
        while True:
            candidate = f"{prefix} {index}"
            if candidate.lower() not in known:
                return candidate
            index += 1

    @staticmethod
    def rename_pallet(
        pallet_order: List[str],
        pallet_weights: Dict[str, float],
        items: List[PackingItem],
        current_name: str,
        new_name: str,
    ) -> Tuple[bool, str]:
        current = str(current_name or "").strip()
        target = str(new_name or "").strip()
        if not current or not target:
            return False, "Pallet name is required."
        if current not in pallet_order:
            return False, "Pallet not found."
        if target != current and target in pallet_order:
            return False, "This pallet name already exists."

        for i, pallet in enumerate(pallet_order):
            if pallet == current:
                pallet_order[i] = target

        pallet_weights[target] = float(pallet_weights.get(current, 0.0))
        if target != current:
            pallet_weights.pop(current, None)

        for item in items:
            if item.pallet_no == current:
                item.pallet_no = target
        return True, ""

    @staticmethod
    def delete_empty_pallet(
        pallet_order: List[str],
        pallet_weights: Dict[str, float],
        items: List[PackingItem],
        pallet_name: str,
    ) -> Tuple[bool, str]:
        pallet = str(pallet_name or "").strip()
        if not pallet:
            return False, "Select a pallet first."
        if any(item.pallet_no == pallet for item in items):
            return False, "This pallet contains products.\n\nMove them before deleting."

        pallet_order[:] = [name for name in pallet_order if name != pallet]
        pallet_weights.pop(pallet, None)
        return True, ""
