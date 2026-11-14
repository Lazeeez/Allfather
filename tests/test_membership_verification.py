import copy
import io
import tarfile

import pytest

from scripts.verify_swerank_membership import digest, read_archive, verify_line_endings, verify_rows


def fixture():
    predictions = [
        {"id": "org/repo#1", "answer": {"functions": [{"file": "a.cjs", "name": "run"}]}}
    ]
    corpus = {("full", "org/repo#1"): {"requested_counts": {"a.cjs/run": 4}}}
    changes = [{"id": "org/repo#1", "slot": 1}]
    rows = [
        {
            "id": "org/repo#1",
            "condition": "full",
            "slots": [
                {
                    "slot": 1,
                    "document_id": "a.cjs/run",
                    "recovered": True,
                    "occurrences": 4,
                    "membership": "ambiguous",
                }
            ],
        }
    ]
    return rows, predictions, corpus, changes


def test_recovered_membership_is_not_mistaken_for_unique_identity():
    rows, predictions, corpus, changes = fixture()
    counts, ambiguous = verify_rows(rows, predictions, corpus, changes, "full")
    assert counts["recovered_ambiguous"] == counts["ambiguous"] == counts["slots"] == 1
    assert not counts["unique"]
    assert ambiguous[0]["occurrences"] == 4


@pytest.mark.parametrize(
    "field,value",
    [
        ("slot", 2),
        ("document_id", "another.cjs/run"),
        ("recovered", False),
        ("occurrences", 1),
        ("membership", "unique"),
    ],
)
def test_rehashed_slot_tampering_still_fails_semantic_join(field, value):
    rows, predictions, corpus, changes = fixture()
    rows[0]["slots"][0][field] = value
    with pytest.raises(ValueError, match="slot disagrees"):
        verify_rows(rows, predictions, corpus, changes, "full")


def test_omitted_rank_slot_and_duplicate_rows_are_rejected():
    rows, predictions, corpus, changes = fixture()
    with pytest.raises(ValueError, match="IDs/order"):
        verify_rows(rows + copy.deepcopy(rows), predictions, corpus, changes, "full")
    rows[0]["slots"] = []
    with pytest.raises(ValueError, match="rank slots"):
        verify_rows(rows, predictions, corpus, changes, "full")


def test_line_ending_exception_requires_exact_trusted_git_bytes():
    committed = b'{"x": 1}\n'
    assert (
        verify_line_endings(committed.replace(b"\n", b"\r\n"), committed, digest(committed))
        == committed
    )
    with pytest.raises(ValueError, match="differs beyond"):
        verify_line_endings(b'{"x": 2}\r\n', committed, digest(committed))
    with pytest.raises(ValueError, match="differs beyond"):
        verify_line_endings(committed, committed, "untrusted-hash")


@pytest.mark.parametrize(
    "name,link", [("root/../summary.json", False), ("root/summary.json", True)]
)
def test_archive_path_traversal_and_links_are_rejected(tmp_path, name, link):
    path = tmp_path / "audit.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        item = tarfile.TarInfo(name)
        if link:
            item.type = tarfile.SYMTYPE
            item.linkname = "outside.json"
            archive.addfile(item)
        else:
            item.size = 2
            archive.addfile(item, io.BytesIO(b"{}"))
    with pytest.raises(ValueError):
        read_archive(path)
