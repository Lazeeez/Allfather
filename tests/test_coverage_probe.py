import json

import numpy as np
import pytest

from scripts.coverage_probe import (
    PROTOCOL,
    inject,
    lexical_index,
    positive_order,
    query_fields,
    reference_neighbors,
    validate_protocol,
)


def test_query_fields_preserve_late_report_evidence_and_deduplicate_quotes():
    text = (
        "Title\n"
        + "template " * 600
        + '\n{"message":"pricing is disabled"}\n`api/pricing`\n"pricing is disabled"'
    )
    fields = query_fields(text)
    assert fields["full"] == text
    assert fields["title"] == "Title"
    assert fields["code"] == "`api/pricing`"
    assert fields["quoted"].splitlines() == ["message", "pricing is disabled"]
    assert query_fields("Title\n'failure text'")["quoted"] == "failure text"


@pytest.mark.parametrize("budget", [0, 1, 5, 50, 200])
def test_injection_obeys_capacity_retains_head_and_handles_duplicate_proposals(budget):
    base = list(range(101))
    original = base[:budget]
    result = inject(base, [0, 1, 900, 900, 901, 902], budget)
    head = (len(original) + 1) // 2
    assert len(result) == len(set(result)) == len(original)
    assert result[:head] == original[:head]
    assert len(set(result) - set(original)) <= len(original) - head
    assert inject(base, base[:budget], budget) == original


def test_reference_expansion_scopes_names_and_rejects_high_fanout():
    universe = [
        {"id": f"{p}::{q}"}
        for p, q in [
            ("a.py", "seed"),
            ("a.py", "Helper.work"),
            ("b.py", "work"),
            *[(f"lib{i}.py", "ambiguous") for i in range(9)],
        ]
    ]
    # A comment is deliberately eligible: this baseline is lexical, not a call graph.
    texts = ["seed\n# work ambiguous", *[""] * (len(universe) - 1)]
    rows, counts = reference_neighbors(texts, universe, [0])
    assert rows == [1]
    assert counts["references_skipped_for_ambiguity"] == 1


def test_lexical_index_includes_path_terms_and_ties_use_original_rows():
    index, vocab = lexical_index(
        ["same", "same", "same"],
        [
            {"id": "billing/payment.go::A"},
            {"id": "billing/payment.go::B"},
            {"id": "render/view.ts::C"},
        ],
    )
    scores = index.scores(vocab.lookup({"payment": 1}))
    assert positive_order(scores) == [0, 1]
    assert scores[0] == scores[1] > scores[2] == 0
    assert positive_order(np.zeros(3)) == []


def test_control_drift_rejected_before_capture():
    protocol = json.loads(PROTOCOL.read_bytes())
    validate_protocol(protocol)
    protocol["fusion"]["constant"] = 10
    with pytest.raises(ValueError, match="protocol changed"):
        validate_protocol(protocol)
