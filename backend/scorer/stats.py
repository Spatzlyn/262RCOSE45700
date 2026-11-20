"""Confidence intervals and Base-vs-Target comparison (Role_Backend §7).

- Wilson: per-request / per-scene ratios (V1, V2, V10, V12, A2) — computed in score.aggregate.
- Group bootstrap: metrics that average F1s or count several units per scene
  (V3, V4, V5, V6–V9, V11, A1). Source Groups are resampled with replacement, B times.
- Paired group bootstrap: the same resampled groups are applied to both runs; the 2.5/97.5
  percentiles of the per-replicate difference give the difference interval.

A replicate in which a metric is undefined (denominator 0, V5 cell empty) is counted; if any
replicate is undefined the interval is N/A and the undefined rate is reported (spec §7).
"""
from __future__ import annotations

import os

import numpy as np

DEFAULT_B = int(os.environ.get("BOOTSTRAP_B", "2000"))
DEFAULT_SEED = 20261116


def _val(name):
    return lambda m: m[name]["value"] if m[name].get("status") == "computed" else None


def _v3(m):
    v = m["v3_grounding"]
    return v["by_iou"]["0.5"].get("f1") if v.get("status") == "computed" else None


BOOTSTRAP_METRICS = {
    "v3_grounding": _v3, "v4_evidence": _val("v4_evidence"), "v5_relation_macro_f1": _val("v5_relation_macro_f1"),
    "v6_present_recall": _val("v6_present_recall"), "v7_false_positive_rate": _val("v7_false_positive_rate"),
    "v8_unknown_recall": _val("v8_unknown_recall"), "v9_over_abstention": _val("v9_over_abstention"),
    "v11_required_group_recall": _val("v11_required_group_recall"), "a1_attribute_f1": _val("a1_attribute_f1"),
}
COMPARE_METRICS = {**BOOTSTRAP_METRICS, "v1_valid": _val("v1_valid"), "v10_action_pass_rate": _val("v10_action_pass_rate"),
                   "v12_forbidden_rate": _val("v12_forbidden_rate"),
                   "a2_direction_na_violation": _val("a2_direction_na_violation")}
LOWER_IS_BETTER = {"v2_invalid", "v7_false_positive_rate", "v9_over_abstention", "v12_forbidden_rate",
                   "a2_direction_na_violation"}


def _groups(requests, group_of):
    missing = [q["item_id"] for q in requests if not group_of.get(q["item_id"])]
    if missing:
        return None, f"source_group_id missing for {len(missing)} item(s)"
    order = sorted({group_of[q["item_id"]] for q in requests})
    if len(order) < 2:
        return None, "only one Source Group: interval is N/A"
    return order, None


def _na(reason, extra=None):
    return {"ci95": None, "ci_status": "not_applicable", "ci_reason": reason, **(extra or {})}


def _subset(rows, requests, group_of, sample):
    by_group = {}
    for r, q in zip(rows, requests):
        by_group.setdefault(group_of[q["item_id"]], []).append((r, q))
    sub_r, sub_q = [], []
    for g in sample:
        for r, q in by_group[g]:
            sub_r.append(r)
            sub_q.append(q)
    return sub_r, sub_q


def _percentiles(values):
    lo, hi = np.percentile(np.asarray(values, dtype=float), [2.5, 97.5])
    return [round(float(lo), 6), round(float(hi), 6)]


def group_bootstrap(rows, requests, group_of, aggregate, B=DEFAULT_B, seed=DEFAULT_SEED, metrics=None):
    """Per-metric 95% intervals for one run. rows align with requests (same order)."""
    metrics = metrics or BOOTSTRAP_METRICS
    order, reason = _groups(requests, group_of)
    if order is None:
        return {k: _na(reason) for k in metrics}
    rng = np.random.default_rng(seed)
    draws = {k: [] for k in metrics}
    for _ in range(B):
        sample = [order[i] for i in rng.integers(0, len(order), len(order))]
        m = aggregate(*_subset(rows, requests, group_of, sample))["metrics"]
        for k, fn in metrics.items():
            draws[k].append(fn(m))
    out = {}
    for k, vals in draws.items():
        undefined = sum(v is None for v in vals) / B
        meta = {"B": B, "seed": seed, "n_groups": len(order), "undefined_rate": round(undefined, 6)}
        out[k] = (_na("metric undefined in some replicates", meta) if undefined
                  else {"ci95": _percentiles(vals), "ci_status": "group_bootstrap", "ci_reason": None, **meta})
    return out


def paired_comparison(base_rows, base_reqs, tgt_rows, tgt_reqs, group_of, aggregate, B=DEFAULT_B,
                      seed=DEFAULT_SEED, metrics=None):
    """Target − Base on the same resampled groups. judgement: improved / not_confirmed."""
    metrics = metrics or COMPARE_METRICS
    if [q["item_id"] for q in base_reqs] != [q["item_id"] for q in tgt_reqs]:
        return {"status": "not_applicable", "reason": "runs do not share the same fixed request list", "metrics": {}}
    full_b = aggregate(base_rows, base_reqs)["metrics"]
    full_t = aggregate(tgt_rows, tgt_reqs)["metrics"]
    order, reason = _groups(base_reqs, group_of)
    rng = np.random.default_rng(seed)
    deltas = {k: [] for k in metrics}
    if order is not None:
        for _ in range(B):
            sample = [order[i] for i in rng.integers(0, len(order), len(order))]
            mb = aggregate(*_subset(base_rows, base_reqs, group_of, sample))["metrics"]
            mt = aggregate(*_subset(tgt_rows, tgt_reqs, group_of, sample))["metrics"]
            for k, fn in metrics.items():
                a, b = fn(mb), fn(mt)
                deltas[k].append(None if a is None or b is None else b - a)
    out = {}
    for k, fn in metrics.items():
        a, b = fn(full_b), fn(full_t)
        row = {"base": a, "target": b, "delta": None if a is None or b is None else round(b - a, 6),
               "lower_is_better": k in LOWER_IS_BETTER}
        if row["delta"] is None:
            row.update(_na("metric not computed for one of the runs"), judgement="not_applicable")
        elif order is None:
            row.update(_na(reason), judgement="not_applicable")
        else:
            undefined = sum(d is None for d in deltas[k]) / B
            if undefined:
                row.update(_na("difference undefined in some replicates", {"undefined_rate": round(undefined, 6)}),
                           judgement="not_applicable")
            else:
                lo, hi = _percentiles(deltas[k])
                better = hi < 0 if k in LOWER_IS_BETTER else lo > 0
                row.update({"delta_ci95": [lo, hi], "ci_status": "paired_group_bootstrap", "B": B, "seed": seed,
                            "n_groups": len(order), "judgement": "improved" if better else "not_confirmed"})
        out[k] = row
    return {"status": "computed", "reason": None, "metrics": out,
            "judgement_rule": "improved only if the 95% difference interval excludes 0 in the better direction"}
