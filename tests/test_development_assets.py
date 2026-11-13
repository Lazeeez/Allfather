import hashlib
import json
import sys
from types import SimpleNamespace

import pytest

from scripts import development_assets as assets
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


def test_download_redirects_inherited_caches_and_pins_files(tmp_path, monkeypatch):
    spec, store, repo, _, _, _ = fixture_assets(tmp_path)
    spec["adapter"]["path"] = str(repo / "adapter")
    manifest = tmp_path / "assets.json"
    manifest.write_text(json.dumps(spec), encoding="utf-8")
    monkeypatch.setattr(assets, "MANIFEST", manifest)
    monkeypatch.setattr(sys, "argv", ["assets", "--store", str(store), "--download"])
    for name in (
        "HF_HOME",
        "HF_HUB_CACHE",
        "HUGGINGFACE_HUB_CACHE",
        "HF_XET_CACHE",
        "HF_ASSETS_CACHE",
        "HF_HUB_OFFLINE",
    ):
        monkeypatch.setenv(name, "inherited-value")
    calls = []

    def download(name, **kwargs):
        calls.append((name, kwargs))
        assert assets.os.environ["HF_HUB_OFFLINE"] == "0"
        for key in (
            "HF_HOME",
            "HF_HUB_CACHE",
            "HUGGINGFACE_HUB_CACHE",
            "HF_XET_CACHE",
            "HF_ASSETS_CACHE",
        ):
            assert assets.os.environ[key].startswith(str(store))

    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(snapshot_download=download))
    assert assets.main() == 0
    assert calls == [
        (
            "org/model",
            {
                "revision": "pinned",
                "cache_dir": store / "hub",
                "allow_patterns": ["model.safetensors"],
                "max_workers": 2,
            },
        )
    ]


def test_adapter_only_does_not_require_model_cache(tmp_path, monkeypatch):
    spec, _, repo, model, _, _ = fixture_assets(tmp_path)
    model.unlink()
    spec["adapter"]["path"] = str(repo / "adapter")
    manifest = tmp_path / "assets.json"
    manifest.write_text(json.dumps(spec), encoding="utf-8")
    monkeypatch.setattr(assets, "MANIFEST", manifest)
    monkeypatch.setattr(sys, "argv", ["assets", "--adapter-only"])
    assert assets.main() == 0


def test_download_requires_explicit_store(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["assets", "--download"])
    with pytest.raises(SystemExit) as error:
        assets.main()
    assert error.value.code == 2
