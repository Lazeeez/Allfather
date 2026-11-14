import hashlib

import pytest

from scripts.prepare_task_audit import packet


def test_packet_exports_only_original_report_fields_not_gold_or_predictions():
    text = "Feature request: add support for another model."
    item = {
        "id": "a/b#123",
        "repo": "a/b",
        "base_commit": "abc",
        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
    }
    record = {
        **item,
        "text": text,
        "gold_functions": ["hidden"],
        "patch": "secret patch",
        "predictions": ["secret prediction"],
    }
    result = packet(item, record)
    assert set(result) == {"case", "repo", "base_commit", "text_sha256", "text"}
    assert result["text"] == text
    assert result["case"] != item["id"]


def test_packet_rejects_edited_reports():
    item = {"id": "a/b#123", "repo": "a/b", "base_commit": "abc", "text_sha256": "incorrect"}
    with pytest.raises(ValueError, match="report changed"):
        packet(item, {**item, "text": "changed"})
