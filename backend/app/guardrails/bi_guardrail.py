from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
ALLOWLIST_PATH = REPO_ROOT / "backend" / "config" / "bi_guardrail_allowlist.json"

DETECTORS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("bi_reference", re.compile(r"bi\.[A-Za-z0-9_*]+")),
    (
        "legacy_symbol",
        re.compile(r"\b(get_revenue_column_name|get_real_column_name|inspect_revenue_column)\b"),
    ),
)


@dataclass(frozen=True)
class Hit:
    path: str
    detector: str
    match: str
    line_no: int
    line_text: str


def load_allowlist(path: Path | None = None) -> dict[str, Any]:
    target = path or ALLOWLIST_PATH
    with target.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _should_scan(path: Path, repo_root: Path, config: dict[str, Any]) -> bool:
    rel = path.relative_to(repo_root).as_posix()
    exclude_paths = config.get("scan", {}).get("exclude_paths", [])
    if any(rel.startswith(prefix) for prefix in exclude_paths):
        return False
    suffixes = set(config.get("scan", {}).get("include_suffixes", []))
    return path.suffix in suffixes


def iter_scan_files(repo_root: Path, config: dict[str, Any]) -> list[Path]:
    out: set[Path] = set()
    for root in config.get("scan", {}).get("roots", []):
        base = repo_root / root
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and _should_scan(path, repo_root, config):
                out.add(path)
    return sorted(out)


def collect_hits(repo_root: Path, config: dict[str, Any]) -> list[Hit]:
    hits: list[Hit] = []
    for path in iter_scan_files(repo_root, config):
        rel = path.relative_to(repo_root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="replace")
        for idx, line in enumerate(text.splitlines(), start=1):
            for detector_name, pattern in DETECTORS:
                for m in pattern.finditer(line):
                    hits.append(
                        Hit(
                            path=rel,
                            detector=detector_name,
                            match=m.group(0),
                            line_no=idx,
                            line_text=line.strip(),
                        )
                    )
    return hits


def build_observed_counts(hits: list[Hit]) -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for hit in hits:
        counts[(hit.path, hit.match)] += 1
    return dict(counts)


def evaluate_guardrail(
    repo_root: Path | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = repo_root or REPO_ROOT
    cfg = config or load_allowlist()
    hits = collect_hits(root, cfg)
    observed_counts = build_observed_counts(hits)

    allowed_entries = {
        (str(entry["path"]), str(entry["match"])): entry
        for entry in cfg.get("allowed_references", [])
    }

    violations: list[dict[str, Any]] = []

    for hit in hits:
        key = (hit.path, hit.match)
        if key not in allowed_entries:
            violations.append(
                {
                    "path": hit.path,
                    "line_no": hit.line_no,
                    "match": hit.match,
                    "line_text": hit.line_text,
                    "reason": "Referencia a bi.* o símbolo legacy no autorizada por allowlist.",
                    "suggestion": "Mover a ops.* o justificar explícitamente en backend/config/bi_guardrail_allowlist.json.",
                }
            )

    stale_allowlist: list[dict[str, Any]] = []
    for key, entry in allowed_entries.items():
        observed = observed_counts.get(key, 0)
        expected = int(entry.get("count", 0))
        if observed != expected:
            stale_allowlist.append(
                {
                    "path": entry["path"],
                    "match": entry["match"],
                    "expected": expected,
                    "observed": observed,
                    "reason": entry.get("reason", ""),
                }
            )

    return {
        "ok": not violations and not stale_allowlist,
        "violations": violations,
        "stale_allowlist": stale_allowlist,
        "observed_counts": observed_counts,
        "policy": cfg.get("policy", {}),
    }


def format_report(report: dict[str, Any]) -> str:
    if report["ok"]:
        return "BI guardrail OK: no se detectaron referencias nuevas no autorizadas a bi.*."

    parts: list[str] = []
    parts.append("BI guardrail FAILED")
    parts.append("Fuente oficial: trips_2025, trips_2026, ops.*, dims canónicas.")

    if report["violations"]:
        parts.append("")
        parts.append("Referencias no autorizadas:")
        for item in report["violations"]:
            parts.append(
                f"- {item['path']}:{item['line_no']} -> {item['match']}\n"
                f"  Motivo: {item['reason']}\n"
                f"  Línea: {item['line_text']}\n"
                f"  Sugerencia: {item['suggestion']}"
            )

    if report["stale_allowlist"]:
        parts.append("")
        parts.append("Allowlist desalineada:")
        for item in report["stale_allowlist"]:
            parts.append(
                f"- {item['path']} -> {item['match']} (esperado={item['expected']}, observado={item['observed']})\n"
                f"  Motivo permitido actual: {item['reason']}\n"
                f"  Acción: actualizar allowlist solo si la excepción sigue siendo legítima."
            )

    return "\n".join(parts)


def main() -> int:
    report = evaluate_guardrail()
    print(format_report(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
