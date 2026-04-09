from pathlib import Path


def test_bi_guardrail_current_repo_passes():
    from app.guardrails.bi_guardrail import evaluate_guardrail, REPO_ROOT

    report = evaluate_guardrail(REPO_ROOT)

    assert report["ok"], report


def test_bi_guardrail_fails_for_new_unauthorized_reference(tmp_path: Path):
    from app.guardrails.bi_guardrail import evaluate_guardrail, format_report

    repo = tmp_path / "repo"
    target = repo / "backend" / "app"
    target.mkdir(parents=True)
    (target / "foo.py").write_text("SQL = \"SELECT * FROM bi.real_monthly_agg\"\n", encoding="utf-8")

    config = {
        "policy": {
            "official_sources": ["ops.*"],
        },
        "scan": {
            "roots": ["backend/app"],
            "include_suffixes": [".py"],
            "exclude_paths": [],
        },
        "allowed_references": [],
    }

    report = evaluate_guardrail(repo_root=repo, config=config)
    message = format_report(report)

    assert report["ok"] is False
    assert report["violations"]
    assert "bi.real_monthly_agg" in message
    assert "Mover a ops.*" in message
