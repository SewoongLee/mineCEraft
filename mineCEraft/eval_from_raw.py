from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import importlib


def _resolve_callable(dotted: str) -> Tuple[Any, str]:
    """Resolve e.g. 'size.is_equal' to eval_code.size.is_equal callable."""
    fq = f"eval_code.{dotted}"
    mod_name, func_name = fq.rsplit(".", 1)
    mod = importlib.import_module(mod_name)
    return getattr(mod, func_name), fq


def _run_checks(coords: List[Dict[str, Any]], checks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Run checks on coords; return score, results, and by_category summary.
    Each check must return a value in [0, 1]; we clamp and sum for score.
    """
    results: List[Dict[str, Any]] = []
    score = 0.0
    cat_pass: Dict[str, float] = defaultdict(float)   # category -> sum of scores in [0, 1]
    cat_total: Dict[str, int] = defaultdict(int)      # category -> total count

    for chk in checks:
        fn_name = chk["fn"]          # e.g., 'material.is_all_material_equal_to'
        args = chk.get("args") or {}
        category = fn_name.split(".", 1)[0]  # module name as category (e.g., material)

        fn, fq = _resolve_callable(fn_name)
        try:
            v = fn(coords, **args)
            ok = max(0.0, min(1.0, float(v)))
        except Exception as e:  # noqa: BLE001
            ok, args = 0.0, {**args, "_error": str(e)}  # surface error on this line

        score += ok
        cat_total[category] += 1
        cat_pass[category] += ok

        results.append({"fn": fq, "category": category, "ok": ok, "args": args})

    cat_summary = {
        c: {"pass": cat_pass[c], "total": cat_total[c]}
        for c in sorted(cat_total.keys())
    }
    return {"score": score, "total": len(results), "results": results, "by_category": cat_summary}


def _infer_model_and_ts(paths: List[Path]) -> Tuple[str, str]:
    """
    Infer (model_safe, ts) from eval_raw file name(s).
    If exactly one file matches eval_raw_{model_safe}_{ts}.json, reuse that.
    Otherwise fall back to a generic name and current timestamp.
    """
    now_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not paths:
        return "unknown_model", now_ts

    stem = paths[0].stem  # e.g., "eval_raw_model_ts"
    if stem.startswith("eval_raw_"):
        rest = stem[len("eval_raw_") :]
        parts = rest.rsplit("_", 1)
        if len(parts) == 2:
            return parts[0] or "unknown_model", parts[1] or now_ts
        return rest or "unknown_model", now_ts

    if len(paths) > 1:
        return "multi_raw", now_ts

    return stem or "unknown_model", now_ts


def evaluate_from_raw(
    eval_raw_paths: Iterable[str | Path],
    *,
    results_dir: str | Path = "eval_results",
) -> Tuple[List[List[List[Dict[str, Any]]]], Path, Path]:
    """
    Evaluate one or more eval_raw_*.json files and write:
      - eval_{model_safe}_{ts}.log
      - eval_{model_safe}_{ts}.csv

    The eval_raw files are expected to be JSON-lines, where each line is
    a JSON object with:
      - run_idx, turn_idx, n_turns
      - prompt
      - checks
      - coords
      - _comment

    Returns:
      coords_by_problem, log_path, csv_path
      where coords_by_problem[run_index][turn_index] = coords at that eval.
    """
    paths = [Path(p) for p in eval_raw_paths]
    if not paths:
        raise ValueError("eval_raw_paths must contain at least one path.")

    results_dir_path = Path(results_dir)
    results_dir_path.mkdir(exist_ok=True)

    model_safe, ts = _infer_model_and_ts(paths)
    log_path = results_dir_path / f"eval_{model_safe}_{ts}.log"
    csv_path = results_dir_path / f"eval_{model_safe}_{ts}.csv"

    overall_pass = 0.0
    overall_total = 0
    overall_by_cat_pass: Dict[str, float] = defaultdict(float)
    overall_by_cat_total: Dict[str, int] = defaultdict(int)

    coords_by_problem_dict: Dict[int, List[List[Dict[str, Any]]]] = defaultdict(list)
    csv_rows: List[Dict[str, Any]] = []

    with open(Path("category.json"), encoding="utf-8") as _f:
        categories = json.load(_f)

    with open(log_path, "w", encoding="utf-8") as log_file:

        def print_and_log(msg: str) -> None:
            print(msg)
            log_file.write(msg + "\n")
            log_file.flush()

        for raw_path in paths:
            print_and_log(f"[PY] Reading eval_raw from {raw_path}")
            with raw_path.open(encoding="utf-8") as f_raw:
                for line in f_raw:
                    line = line.strip()
                    if not line:
                        continue

                    record = json.loads(line)
                    run_idx = int(record.get("run_idx", 0))
                    turn_idx = int(record.get("turn_idx", 0))
                    n_turns = int(record.get("n_turns", 1))
                    prompt_text = record.get("prompt", "")
                    checks = record.get("checks") or []
                    coords = record.get("coords") or []
                    run_comment = record.get("_comment", "")

                    report = _run_checks(coords, checks)
                    coords_by_problem_dict[run_idx].append(coords)

                    print_and_log("\n[PY] === Evaluation Result ===")
                    print_and_log(f"[PY] Run #{run_idx}, Turn #{turn_idx}/{n_turns}: {prompt_text}")
                    print_and_log(f"[PY] Score: {report['score']} / {report['total']} (coords={len(coords)})")

                    print_and_log("[PY] Category scores:")
                    for cat, st in report["by_category"].items():
                        print_and_log(f"  - {cat}: {st['pass']} / {st['total']}")

                    for r in report["results"]:
                        ok_val = r["ok"]
                        status = "PASS" if ok_val >= 1.0 else ("FAIL" if ok_val <= 0 else f"{ok_val:.2f}")
                        line_out = f"  · {status} | {r['fn']}({r.get('args', {})})"
                        print_and_log(line_out)
                        csv_rows.append(
                            {
                                "run_idx": run_idx,
                                "turn_idx": turn_idx,
                                "prompt_text": prompt_text,
                                "check_fn": r["fn"],
                                "check_args": str(r.get("args", {})),
                                "passed": ok_val,
                                "_comment": run_comment,
                            }
                        )

                    overall_pass += report["score"]
                    overall_total += report["total"]
                    for cat, st in report["by_category"].items():
                        overall_by_cat_pass[cat] += st["pass"]
                        overall_by_cat_total[cat] += st["total"]

        if overall_total > 0:
            print_and_log("\n[PY] === Overall Summary ===")
            overall_pct = (overall_pass / overall_total * 100.0) if overall_total > 0 else 0.0
            print_and_log(f"[PY] Total PASS: {overall_pass} / {overall_total} ({overall_pct:.1f}%)")

            print_and_log("[PY] By category:")
            for big_cat in categories:
                p = sum(overall_by_cat_pass.get(sub, 0.0) for sub in categories[big_cat])
                t = sum(overall_by_cat_total.get(sub, 0) for sub in categories[big_cat])
                cat_pct = (p / t * 100.0) if t > 0 else 0.0
                print_and_log(f"  - {big_cat}: {p} / {t} ({cat_pct:.1f}%)")

            print_and_log("[PY] By subcategory:")
            for big_cat in categories:
                for sub in categories[big_cat]:
                    p = overall_by_cat_pass.get(sub, 0.0)
                    t = overall_by_cat_total.get(sub, 0)
                    if t > 0:
                        cat_pct = p / t * 100.0
                        print_and_log(f"  - {sub}: {p} / {t} ({cat_pct:.1f}%)")

    with open(csv_path, "w", newline="", encoding="utf-8") as f_csv:
        writer = csv.DictWriter(
            f_csv,
            fieldnames=[
                "run_idx",
                "turn_idx",
                "prompt_text",
                "check_fn",
                "check_args",
                "passed",
                "_comment",
            ],
        )
        writer.writeheader()
        writer.writerows(csv_rows)

    # Build coords_by_problem as a sorted list of runs.
    coords_by_problem: List[List[List[Dict[str, Any]]]] = []
    for run_idx in sorted(coords_by_problem_dict.keys()):
        coords_by_problem.append(coords_by_problem_dict[run_idx])

    print(f"[PY] Results saved: log={log_path}, csv={csv_path}")
    return coords_by_problem, log_path, csv_path


__all__ = [
    "evaluate_from_raw",
]

