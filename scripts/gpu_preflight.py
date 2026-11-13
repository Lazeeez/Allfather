"""Check the existing GPU environment without downloading or loading model weights."""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    # Refuse to overwrite an earlier diagnostic, including a failed one.
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as output:
        report = {
            "created_at": datetime.now(UTC).isoformat(),
            "python": sys.version,
            "executable": sys.executable,
            "platform": platform.platform(),
            "slurm": {
                key: os.environ.get(key)
                for key in ("SLURM_JOB_ID", "SLURM_JOB_PARTITION", "SLURM_CPUS_PER_TASK")
            },
            "packages": {},
            "checks": [],
            "ok": False,
        }
        try:
            report["commit"] = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True
            ).strip()
            report["nvidia_smi"] = subprocess.check_output(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total,driver_version",
                    "--format=csv",
                ],
                text=True,
            ).strip()
            for package, module in (
                ("torch", "torch"),
                ("transformers", "transformers"),
                ("sentence-transformers", "sentence_transformers"),
                ("peft", "peft"),
                ("safetensors", "safetensors"),
            ):
                report["packages"][package] = importlib.metadata.version(package)
                importlib.import_module(module)

            import torch

            report["torch_cuda_version"] = torch.version.cuda
            if not torch.cuda.is_available():
                raise RuntimeError("PyTorch cannot use CUDA in this allocation")
            report["visible_device_count"] = torch.cuda.device_count()
            report["device"] = torch.cuda.get_device_name(0)
            report["device_memory_bytes"] = torch.cuda.get_device_properties(0).total_memory
            report["compute_capability"] = list(torch.cuda.get_device_capability(0))
            # Exercise the dtypes used by dense retrieval and the cross encoder.
            # This is a correctness smoke check, not a throughput benchmark.
            for dtype in (torch.float32, torch.float16, torch.bfloat16):
                tensor = torch.eye(256, dtype=dtype, device="cuda:0")
                actual = tensor @ tensor
                torch.cuda.synchronize()
                if not torch.equal(actual, tensor):
                    raise RuntimeError(f"CUDA matrix multiplication failed for {dtype}")
                report["checks"].append({"dtype": str(dtype), "matmul": "passed"})
            report["ok"] = True
        except Exception:
            report["error"] = traceback.format_exc()
        output.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
