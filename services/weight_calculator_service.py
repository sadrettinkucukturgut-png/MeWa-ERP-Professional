from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

from models.packing_model import PackingItem, PackingTotals, PalletStats


class WeightCalculatorService:
    @staticmethod
    def item_net_weight(item: PackingItem) -> float:
        return max(0.0, float(item.quantity) * float(item.quantity_weight))

    @staticmethod
    def pallet_stats(pallet_no: str, items: Iterable[PackingItem], pallet_weight: float) -> PalletStats:
        selected = [item for item in items if item.pallet_no == pallet_no]
        qty = sum(float(item.quantity) for item in selected)
        net = sum(WeightCalculatorService.item_net_weight(item) for item in selected)
        gross = net + (float(pallet_weight) if selected else 0.0)
        return PalletStats(
            pallet_no=pallet_no,
            product_count=len(selected),
            total_quantity=qty,
            total_net_weight=net,
            total_gross_weight=gross,
        )

    @staticmethod
    def all_pallet_stats(
        pallet_order: List[str],
        pallet_weights: Dict[str, float],
        items: List[PackingItem],
    ) -> Dict[str, PalletStats]:
        stats: Dict[str, PalletStats] = {}
        for pallet_no in pallet_order:
            stats[pallet_no] = WeightCalculatorService.pallet_stats(
                pallet_no,
                items,
                float(pallet_weights.get(pallet_no, 0.0)),
            )
        return stats

    @staticmethod
    def totals(
        pallet_order: List[str],
        pallet_weights: Dict[str, float],
        items: List[PackingItem],
        visible_pallets: Iterable[str] | None = None,
    ) -> PackingTotals:
        palette = set(visible_pallets or pallet_order)
        stats = WeightCalculatorService.all_pallet_stats(pallet_order, pallet_weights, items)
        selected = [stat for name, stat in stats.items() if name in palette]
        return PackingTotals(
            total_pallets=len(selected),
            total_pieces=sum(stat.total_quantity for stat in selected),
            total_net_weight=sum(stat.total_net_weight for stat in selected),
            total_gross_weight=sum(stat.total_gross_weight for stat in selected),
        )

    @staticmethod
    def item_gross_weights(
        pallet_order: List[str],
        pallet_weights: Dict[str, float],
        items: List[PackingItem],
    ) -> Dict[int, float]:
        gross_by_index: Dict[int, float] = {}
        grouped: Dict[str, List[int]] = {pallet: [] for pallet in pallet_order}
        for index, item in enumerate(items):
            grouped.setdefault(item.pallet_no, []).append(index)

        for pallet, indexes in grouped.items():
            pallet_weight = float(pallet_weights.get(pallet, 0.0))
            for order, item_index in enumerate(indexes):
                net = WeightCalculatorService.item_net_weight(items[item_index])
                gross_by_index[item_index] = net + (pallet_weight if order == 0 else 0.0)
        return gross_by_index
