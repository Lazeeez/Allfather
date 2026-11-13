import hashlib
import json

from scripts.development_assets import check_assets


def fixture_assets(tmp_path):
    store, repo = tmp_path / "store", tmp_path / "repo"
    model = store / "hub/models--org--model/snapshots/pinned/model.safetensors"
    weights = repo / "adapter/adapter_model.safetensors"
    for path in (model, weights):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"expected")
    config = weights.with_name("adapter_config.json")
    config.write_text('{"r": 16}\n', encoding="utf-8")
    digest = hashlib.sha256(b"expected").hexdigest()
    spec = {
        "models": {"org/model": {"revision": "pinned", "files_sha256": {model.name: digest}}},
        "adapter": {"path": "adapter", "weights_sha256": digest, "config": {"r": 16}},
    }
    return spec, store, repo, model, weights, config


def test_assets_require_exact_revision_and_file_contents(tmp_path):
    spec, store, repo, model, _, _ = fixture_assets(tmp_path)
    assert check_assets(spec, store, repo) == []
    model.write_bytes(b"corrupt")
    assert any("SHA256 mismatch" in error for error in check_assets(spec, store, repo))
    spec["models"]["org/model"]["revision"] = "another-revision"
    assert any("Missing:" in error for error in check_assets(spec, store, repo))


def test_adapter_identity_and_cross_platform_config(tmp_path):
    spec, store, repo, _, weights, config = fixture_assets(tmp_path)
    config.write_bytes(b'{\r\n  "r": 16\r\n}\r\n')
    assert check_assets(spec, store, repo) == []
    weights.write_bytes(b"different adapter")
    assert any("adapter SHA256 mismatch" in error for error in check_assets(spec, store, repo))
    weights.unlink()
    config.write_text(json.dumps({"r": 32}), encoding="utf-8")
    errors = check_assets(spec, store, repo)
    assert any("Missing trained weights" in error for error in errors)
    assert any("Adapter config mismatch" in error for error in errors)
