import json
from pathlib import Path

from allfather.eval.metrics import aggregate, bootstrap_ci, metric_values, score

RUNS = {
    "holdout_function": Path("results/holdout/allfather-fast_function.json"),
    "holdout_file": Path("results/holdout/allfather-fast_file.json"),
    "lite_function": Path("results/frozen/allfather-fast_function_lite.json"),
    "lite_file": Path("results/frozen/allfather-fast_file_lite.json"),
}
KS = [1, 5, 10]
METRICS = ["mrr", *[f"{m}@{k}" for k in KS for m in ("hit", "recall", "all")]]
OUT = Path("results/frozen/report.json")
SITE = Path("web/public/data/holdout.json")
SITE_METRICS = ["hit@1", "hit@5", "hit@10", "all@10", "mrr"]


def main() -> int:
    report = {
        "adr": "docs/decisions/0032-freeze-allfather-fast.md",
        "interval": "95% percentile bootstrap over issues",
        "runs": {},
    }
    for name, path in RUNS.items():
        data = json.loads(path.read_text(encoding="utf-8"))
        scores = [score(i["ranked"], i["gold"], KS) for i in data["per_instance"]]
        point = aggregate(scores, KS)
        stored = data["summary"]
        mismatched = [m for m in METRICS if abs(point[m] - stored[m]) > 1e-4]
        if mismatched:
            raise SystemExit(f"{path}: recomputed {mismatched} differ from the stored summary")
        report["runs"][name] = {
            "file": path.as_posix(),
            "issues": len(scores),
            "metrics": {
                m: {
                    "value": round(float(metric_values(scores, m).mean()), 6),
                    "ci95": bootstrap_ci(scores, m),
                }
                for m in METRICS
            },
        }
    OUT.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    site = {
        "adr": "0032",
        "runs": {
            name: {
                "issues": run["issues"],
                **{m: run["metrics"][m]["value"] for m in SITE_METRICS},
                "hit@10_ci95": run["metrics"]["hit@10"]["ci95"],
            }
            for name, run in report["runs"].items()
        },
    }
    SITE.write_text(json.dumps(site, indent=1) + "\n", encoding="utf-8")
    for name, run in report["runs"].items():
        m = run["metrics"]
        print(
            f"{name:17} n={run['issues']:3}  hit@1 {m['hit@1']['value']:.3f}  hit@5 {m['hit@5']['value']:.3f} {m['hit@5']['ci95']}  hit@10 {m['hit@10']['value']:.3f} {m['hit@10']['ci95']}  MRR {m['mrr']['value']:.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
