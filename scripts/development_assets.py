"""Check replay assets without loading models; optionally fetch pinned public weights."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/research/development-assets-v1.json"


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def check_assets(spec: dict, store: Path, repo: Path = ROOT) -> list[str]:
    errors = []
    for name, model in spec["models"].items():
        snapshot = store / "hub" / ("models--" + name.replace("/", "--"))
        snapshot = snapshot / "snapshots" / model["revision"]
        for relative, expected in model["files_sha256"].items():
            path = snapshot / relative
            if not path.is_file():
                errors.append(f"Missing: {path}")
            elif digest(path) != expected:
                errors.append(f"SHA256 mismatch: {path}")
    adapter = repo / spec["adapter"]["path"]
    weights = adapter / "adapter_model.safetensors"
    if not weights.is_file():
        errors.append(f"Missing trained weights (transfer from the local project): {weights}")
    elif digest(weights) != spec["adapter"]["weights_sha256"]:
        errors.append(f"Trained adapter SHA256 mismatch: {weights}")
    config = adapter / "adapter_config.json"
    try:
        if json.loads(config.read_bytes()) != spec["adapter"]["config"]:
            errors.append(f"Adapter config mismatch: {config}")
    except (OSError, ValueError) as exc:
        errors.append(f"Cannot read adapter config: {config}: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--store",
        type=Path,
        default=Path(os.environ.get("HF_STORE", Path.home() / "scratch/odin-cache/huggingface")),
        help="Hugging Face root containing hub/ (same meaning as HF_STORE)",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Fetch pinned base-model files; never train or replace the adapter",
    )
    args = parser.parse_args()
    spec = json.loads(MANIFEST.read_bytes())
    failures = []
    if args.download:
        # Set before importing huggingface_hub, whose settings are read at import.
        os.environ["HF_HUB_OFFLINE"] = "0"
        from huggingface_hub import snapshot_download

        for name, model in spec["models"].items():
            print(f"Preparing {name}@{model['revision']}", flush=True)
            try:
                snapshot_download(
                    name,
                    revision=model["revision"],
                    cache_dir=args.store / "hub",
                    allow_patterns=list(model["files_sha256"]),
                    max_workers=2,
                )
            except Exception as exc:
                failures.append(f"Download failed for {name}: {type(exc).__name__}: {exc}")
    failures.extend(check_assets(spec, args.store))
    print(
        json.dumps({"ok": not failures, "store": str(args.store), "failures": failures}, indent=2)
    )
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
