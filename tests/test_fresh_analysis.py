import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import fresh_analysis as fa  # noqa: E402


def test_kappa_is_one_for_perfect_agreement_and_zero_for_chance():
    assert fa.cohen_kappa(["a", "b", "a", "b"], ["a", "b", "a", "b"]) == 1.0
    assert fa.cohen_kappa(["a", "a", "b", "b"], ["a", "b", "a", "b"]) == 0.0
    assert fa.cohen_kappa([1, 1, 1], [1, 1, 1]) == 1.0


def write_sheet(folder: Path, answers: list[str], parser: list[str]) -> None:
    with (folder / "strata_check.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "id",
                "language",
                "changed (file :: function)",
                "report",
                "your_answer (function / file / trace / none)",
                "notes",
            ]
        )
        for i, a in enumerate(answers):
            w.writerow([f"b{i}", "python", "x.py :: f", "text", a, ""])
    with (folder / "strata_parser.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "parser_says"])
        for i, p in enumerate(parser):
            w.writerow([f"b{i}", p])


def test_strata_agreement_waits_until_every_row_is_filled(tmp_path, monkeypatch):
    monkeypatch.setattr(fa, "FRESH", tmp_path)
    write_sheet(tmp_path, ["function", ""], ["function", "none"])
    assert fa.strata_agreement() == {"filled_in": 1, "rows": 2}


def test_strata_agreement_reports_kappa_and_the_rule(tmp_path, monkeypatch):
    monkeypatch.setattr(fa, "FRESH", tmp_path)
    write_sheet(
        tmp_path, ["function", "file", "trace", "None "], ["function", "file", "trace", "none"]
    )
    out = fa.strata_agreement()
    assert out["kappa"] == 1.0 and out["agreement"] == 1.0 and not out["rq4_indicative_only"]
    write_sheet(
        tmp_path, ["function", "file", "trace", "none"], ["none", "trace", "file", "function"]
    )
    assert fa.strata_agreement()["rq4_indicative_only"]


def test_strata_agreement_refuses_unknown_answers(tmp_path, monkeypatch):
    monkeypatch.setattr(fa, "FRESH", tmp_path)
    write_sheet(tmp_path, ["functon"], ["function"])
    with pytest.raises(SystemExit):
        fa.strata_agreement()


def record(q: str, names: list[str]) -> dict:
    return {"id": q, "answer": {"functions": [{"file": "m.py", "name": n} for n in names]}}


def test_repeatability_compares_the_two_answers(tmp_path, monkeypatch):
    monkeypatch.setattr(fa, "OUT", tmp_path)
    items = {"a": {"repo": "r", "gold": ["m.py::f"]}, "b": {"repo": "r", "gold": ["m.py::g"]}}
    with (tmp_path / "fresh-agents_codex-single-astra.jsonl").open("w", encoding="utf-8") as f:
        f.write(json.dumps(record("a", ["f"])) + "\n" + json.dumps(record("b", ["g"])) + "\n")
    assert fa.repeatability(items) is None
    with (tmp_path / "fresh-repeat50_codex-single-astra-repeat.jsonl").open(
        "w", encoding="utf-8"
    ) as f:
        f.write(json.dumps(record("a", ["f"])) + "\n" + json.dumps(record("b", ["h"])) + "\n")
    out = fa.repeatability(items)
    assert out["issues"] == 2 and out["hit@10_outcome_changed"] == 1
    assert out["same_first_answer"] == 0.5 and out["top10_jaccard_mean"] == 0.5


def test_long_path_list_and_languages_cover_the_sealed_set():
    listed = fa.long_path_bugs("fresh")
    langs = fa.languages("fresh")
    assert len(langs) == 580 and listed <= set(langs)
    assert fa.long_path_bugs("pilot") == set() and fa.languages("pilot") == {}
