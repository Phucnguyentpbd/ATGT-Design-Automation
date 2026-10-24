"""Classifier reused from the user-provided ve-vach-son-mac-vong-4-4-qcvn41-2024 skill.

Source script SHA-256: c5df1f9255e29a530cb164c561b9c1217b97292bab2cfb065b0d9187614e842a
Only the pure classification function is retained. The guarded adapter passes
default_lane_w=0 to avoid widening measured geometry. No transport or CAD writer.
The 5 m / 30 m thresholds are project practice, not mandatory QCVN limits.
"""
from typing import Any, Dict, List

def classify_intersections(branches: List[Dict[str, Any]], delta_threshold: float = 5.0, max_pair_dist: float = 30.0, default_lane_w: float = 3.7) -> List[Dict[str, Any]]:
    """
    Phân loại các nút giao theo 3 trường hợp quy chuẩn:
    1. Ngã tư trực diện hoặc lệch ít (delta <= 5m) -> 1 ô to chung bao cả 2 làn
    2. Ngã tư lệch nhiều (5m < delta <= 30m) -> 2 ô riêng so le, phía nào kẻ phía đó
    3. Ngã 3 (không có nhánh đối diện) -> 1 ô cho phía có nhánh
    """
    tim_groups: Dict[str, List[Dict[str, Any]]] = {}
    for b in branches:
        tim_groups.setdefault(b["timHandle"], []).append(b)

    classified_boxes = []

    for th, blist in tim_groups.items():
        blist.sort(key=lambda x: x["midS"])
        paired_handles = set()
        n = len(blist)

        for i in range(n):
            b1 = blist[i]
            if b1["handle"] in paired_handles:
                continue

            best_opp = None
            best_delta = float('inf')
            for j in range(n):
                if i == j:
                    continue
                b2 = blist[j]
                if b2["handle"] in paired_handles:
                    continue
                if b1["side"] != b2["side"]:
                    delta = abs(b1["midS"] - b2["midS"])
                    if delta < best_delta:
                        best_delta = delta
                        best_opp = b2

            # Trường hợp 1: Ngã tư trực diện hoặc lệch ít
            if best_opp is not None and best_delta <= delta_threshold:
                paired_handles.add(b1["handle"])
                paired_handles.add(best_opp["handle"])

                left_b = b1 if b1["side"] == "LEFT" else best_opp
                right_b = b1 if b1["side"] == "RIGHT" else best_opp

                box_min_s = min(left_b["minS"], right_b["minS"])
                box_max_s = max(left_b["maxS"], right_b["maxS"])

                classified_boxes.append({
                    "type": "NGA_TU_TRUC_DIEN",
                    "timHandle": th,
                    "handles": [left_b["handle"], right_b["handle"]],
                    "minS": box_min_s,
                    "maxS": box_max_s,
                    "wLeft": max(left_b["avgW"], default_lane_w),
                    "wRight": max(right_b["avgW"], default_lane_w),
                    "deltaS": best_delta,
                    "description": f"Ngã tư trực diện/lệch ít (lệch {best_delta:.2f}m)"
                })

            # Trường hợp 2: Ngã tư lệch nhiều
            elif best_opp is not None and delta_threshold < best_delta <= max_pair_dist:
                paired_handles.add(b1["handle"])
                paired_handles.add(best_opp["handle"])

                left_b = b1 if b1["side"] == "LEFT" else best_opp
                right_b = b1 if b1["side"] == "RIGHT" else best_opp

                classified_boxes.append({
                    "type": "NGA_TU_LECH_NHIEU_LEFT",
                    "timHandle": th,
                    "handles": [left_b["handle"]],
                    "side": "LEFT",
                    "minS": left_b["minS"],
                    "maxS": left_b["maxS"],
                    "w": max(left_b["avgW"], default_lane_w),
                    "deltaS": best_delta,
                    "description": f"Ngã tư lệch nhiều - nhánh TRÁI (lệch {best_delta:.2f}m)"
                })
                classified_boxes.append({
                    "type": "NGA_TU_LECH_NHIEU_RIGHT",
                    "timHandle": th,
                    "handles": [right_b["handle"]],
                    "side": "RIGHT",
                    "minS": right_b["minS"],
                    "maxS": right_b["maxS"],
                    "w": max(right_b["avgW"], default_lane_w),
                    "deltaS": best_delta,
                    "description": f"Ngã tư lệch nhiều - nhánh PHẢI (lệch {best_delta:.2f}m)"
                })

            # Trường hợp 3: Ngã 3 đơn lẻ
            else:
                paired_handles.add(b1["handle"])
                classified_boxes.append({
                    "type": f"NGA_3_{b1['side']}",
                    "timHandle": th,
                    "handles": [b1["handle"]],
                    "side": b1["side"],
                    "minS": b1["minS"],
                    "maxS": b1["maxS"],
                    "w": max(b1["avgW"], default_lane_w),
                    "deltaS": None,
                    "description": f"Ngã 3 - nhánh {b1['side']}"
                })

    return classified_boxes
