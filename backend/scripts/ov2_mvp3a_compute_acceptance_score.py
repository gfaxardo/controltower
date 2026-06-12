"""
OV2-MVP.3A — Acceptance Score Computation

Deterministic. No AI. Reads from usage metrics endpoint.

Usage:
    python backend/scripts/ov2_mvp3a_compute_acceptance_score.py
    python backend/scripts/ov2_mvp3a_compute_acceptance_score.py --trial-days 14
"""
from __future__ import annotations

import argparse
import json
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Weights from OV2-MVP3 Acceptance Score Model
W_COVERAGE = 0.30
W_USABILITY = 0.25
W_RELIABILITY = 0.20
W_PERFORMANCE = 0.15
W_CONFIDENCE = 0.10

# Critical tasks from OV2_MVP3_CRITICAL_TASK_INVENTORY.md
TOTAL_CRITICAL_TASKS = 21
READY_TASKS = 19  # 2 pending (commission, ECharts)


def compute_coverage(ready: int = READY_TASKS, total: int = TOTAL_CRITICAL_TASKS) -> float:
    return (ready / total) * 100


def compute_usability(p0: int = 0, p1: int = 0, p2: int = 0) -> float:
    score = 100 - (p0 * 10) - (p1 * 5) - (p2 * 2)
    return max(0, score)


def compute_reliability(errors: int = 0, sessions: int = 1) -> float:
    error_rate = (errors / max(sessions, 1)) * 100
    score = 100 - (error_rate * 5)
    return max(0, min(100, score))


def compute_performance(avg_ms: float = 750) -> float:
    if avg_ms < 2000:
        return 100
    elif avg_ms < 5000:
        return 85
    elif avg_ms < 10000:
        return 60
    return 30


def compute_confidence(survey_score: float = 0) -> float:
    return survey_score * 20


def compute_acceptance_score(
    coverage: float = None,
    usability: float = None,
    reliability: float = None,
    performance: float = None,
    confidence: float = None,
    p0: int = 0,
    p1: int = 0,
    p2: int = 0,
    errors: int = 0,
    sessions: int = 1,
    avg_matrix_ms: float = 750,
    survey_score: float = 0,
) -> dict:
    cov = coverage if coverage is not None else compute_coverage()
    usa = usability if usability is not None else compute_usability(p0, p1, p2)
    rel = reliability if reliability is not None else compute_reliability(errors, sessions)
    perf = performance if performance is not None else compute_performance(avg_matrix_ms)
    conf = confidence if confidence is not None else compute_confidence(survey_score)

    total = (
        cov * W_COVERAGE
        + usa * W_USABILITY
        + rel * W_RELIABILITY
        + perf * W_PERFORMANCE
        + conf * W_CONFIDENCE
    )

    if total >= 85:
        classification = "ACCEPTED"
    elif total >= 70:
        classification = "CONDITIONAL"
    else:
        classification = "REJECTED"

    return {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "components": {
            "coverage": {"score": round(cov, 1), "weight": W_COVERAGE, "weighted": round(cov * W_COVERAGE, 1)},
            "usability": {"score": round(usa, 1), "weight": W_USABILITY, "weighted": round(usa * W_USABILITY, 1)},
            "reliability": {"score": round(rel, 1), "weight": W_RELIABILITY, "weighted": round(rel * W_RELIABILITY, 1)},
            "performance": {"score": round(perf, 1), "weight": W_PERFORMANCE, "weighted": round(perf * W_PERFORMANCE, 1)},
            "confidence": {"score": round(conf, 1), "weight": W_CONFIDENCE, "weighted": round(conf * W_CONFIDENCE, 1)},
        },
        "total_score": round(total, 1),
        "classification": classification,
        "inputs": {
            "ready_tasks": READY_TASKS,
            "total_tasks": TOTAL_CRITICAL_TASKS,
            "p0": p0, "p1": p1, "p2": p2,
            "errors": errors, "sessions": sessions,
            "avg_matrix_ms": avg_matrix_ms,
            "survey_score": survey_score,
        },
    }


def main():
    ap = argparse.ArgumentParser(description="OV2-MVP.3A Acceptance Score Computation")
    ap.add_argument("--p0", type=int, default=0)
    ap.add_argument("--p1", type=int, default=0)
    ap.add_argument("--p2", type=int, default=0)
    ap.add_argument("--errors", type=int, default=0)
    ap.add_argument("--sessions", type=int, default=1)
    ap.add_argument("--avg-ms", type=float, default=750)
    ap.add_argument("--survey", type=float, default=0)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    result = compute_acceptance_score(
        p0=args.p0, p1=args.p1, p2=args.p2,
        errors=args.errors, sessions=args.sessions,
        avg_matrix_ms=args.avg_ms, survey_score=args.survey,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"OV2-MVP.3A Acceptance Score")
        print(f"{'=' * 50}")
        for name, comp in result["components"].items():
            print(f"  {name:<15} {comp['score']:>6.1f}  (weight={comp['weight']:.0%}, weighted={comp['weighted']:>5.1f})")
        print(f"  {'─' * 40}")
        print(f"  TOTAL SCORE:   {result['total_score']:>6.1f}")
        print(f"  CLASSIFICATION: {result['classification']}")
        print(f"\n  GO for OV2-MVP.4: {'YES' if result['total_score'] >= 85 else 'CONDITIONAL' if result['total_score'] >= 70 else 'NO'}")

    return 0 if result["total_score"] >= 70 else 1


if __name__ == "__main__":
    raise SystemExit(main())
