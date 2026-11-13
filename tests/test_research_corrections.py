"""Scientific invariants for the audit corrections (ADR 0037)."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from correct_swerank import recover  # noqa: E402
from escalation_headroom import complementarity  # noqa: E402
from fresh_analysis import escalation  # noqa: E402
from frontier import source_files  # noqa: E402
from open_agent import grep  # noqa: E402
from swerank_export import swerank_id  # noqa: E402
from swerank_import import split_id  # noqa: E402

from allfather.eval.metrics import holm, mcnemar_exact, paired_bootstrap  # noqa: E402
from allfather.parsing.symbols import EXTENSIONS  # noqa: E402


@pytest.mark.parametrize("extension", EXTENSIONS)
def test_every_supported_extension_survives_export_import_and_agent_access(tmp_path, extension):
    path = f"src/module{extension}"
    file = tmp_path / path
    file.parent.mkdir()
    file.write_text("needle_for_localization\n", encoding="utf-8")
    assert split_id(swerank_id(path, "Browser.launch")) == {"file": path, "name": "Browser.launch"}
    assert path in source_files(tmp_path).splitlines()
    assert f"{path}:1:" in grep(tmp_path, "needle_for_localization", None)


def test_actual_lost_identifier_is_recovered():
    assert split_id("skills/taste-skill/scripts/lib/cdp.mjs/Browser/launch") == {
        "file": "skills/taste-skill/scripts/lib/cdp.mjs",
        "name": "Browser.launch",
    }


def test_recovery_preserves_original_records_order_and_failed_slots():
    rows = [
        {
            "id": "issue",
            "cost_usd": None,
            "answer": {
                "functions": [
                    {"file": "x.mjs/Browser/launch", "name": ""},
                    {"file": "unsupported.txt/foo", "name": ""},
                    {"file": "x.py", "name": "good"},
                ]
            },
        }
    ]
    after, changes = recover(rows)
    assert rows[0]["answer"]["functions"][0]["name"] == ""
    assert after[0]["answer"]["functions"] == [
        {"file": "x.mjs", "name": "Browser.launch"},
        {"file": "unsupported.txt/foo", "name": ""},
        {"file": "x.py", "name": "good"},
    ]
    assert after[0]["cost_usd"] is None
    assert changes[0]["slot"] == 1 and len(changes) == 1
    assert recover(after) == (after, [])


def test_source_listing_uses_candidate_exclusions_and_ignores_directories(tmp_path):
    for path in ("src/types.d.ts", "src/bundle.min.js", "tests/main.mjs", "src/main.mjs"):
        file = tmp_path / path
        file.parent.mkdir(exist_ok=True)
        file.write_text("", encoding="utf-8")
    (tmp_path / "directory.py").mkdir()
    assert source_files(tmp_path) == "src/main.mjs"


def test_small_p_values_survive_multiple_testing_correction():
    d = paired_bootstrap(np.zeros(30), np.ones(30))
    assert d.p_value == mcnemar_exact(30, 0)
    assert 0 < holm({"small": d.p_value, "large": 0.5})["small"] < 0.0001


def test_headroom_uses_common_instances_and_distinguishes_rescue_from_damage():
    result = complementarity(
        {"a": 0, "b": 0, "c": 1, "not_shared": 1},
        {"a": 1, "b": 0, "c": 0},
        {"a": 0, "b": 1, "c": 0},
    )
    assert result["issues"] == 3 and result["oracle_any_hit"] == 3
    assert result["rerank_only_rescues_cheap"] == ["a"]
    assert result["agent_only_rescues_cheap"] == ["b"]
    assert result["both_damage_cheap"] == ["c"]


def test_gate_evaluates_the_supplied_threshold_without_rounding_confidence():
    ref = {
        "a": {"confidence": 0.78991, "hit@10": 0, "cost": 1},
        "b": {"confidence": 0.9, "hit@10": 1, "cost": 1},
    }
    other = {
        "a": {"hit@10": 1, "cost": 10},
        "b": {"hit@10": 0, "cost": 100},
    }
    chosen = escalation(ref, other, ["a", "b"], 0.78992)["chosen"]
    assert chosen["threshold"] == 0.78992
    assert chosen["escalated"] == 0.5
    assert chosen["hit@10"] == 1
    # Charge only the selected agent call, plus both cheap calls.
    assert chosen["cost"] == 6
    assert escalation(ref, other, ["a", "b"], 0.78991)["chosen"]["escalated"] == 0
