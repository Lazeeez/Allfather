import hashlib
import zlib

import pytest

from scripts.prepare_patch_audit import changed_files, symbols, verified_object


def test_raw_diff_handles_spaces_and_added_files_without_name_heuristics():
    old, new = "0" * 40, "a" * 40
    result = changed_files(f":000000 100644 {old} {new} A\0folder/space name.py\0".encode())
    assert result[0]["path"] == "folder/space name.py"
    assert result[0]["old_blob"] == old
    with pytest.raises(ValueError, match="malformed raw diff"):
        changed_files(f":100644 100644 {new} {new} R100\0a\0b\0".encode())


def test_download_bytes_must_match_git_tree_not_only_http_success():
    data = b"print('example')\n"
    raw = b"blob " + str(len(data)).encode() + b"\0" + data
    oid = hashlib.sha1(raw).hexdigest()
    assert zlib.decompress(verified_object(data, oid)) == raw
    with pytest.raises(ValueError, match="pinned tree"):
        verified_object(data + b"\n", oid)


def test_unknown_files_are_not_parsed_as_python():
    source = b"def plausible_name():\n    return 1\n"
    assert symbols(source, "archive.zip") == []
    assert symbols(source, "config.yml") == []
    assert [c.qualname for c in symbols(source, "source.py")] == ["plausible_name"]
