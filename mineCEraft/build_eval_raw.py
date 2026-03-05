from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from action_processor import read_placed_and_removed_from_action


SENTINEL = "::ACTION_MAX_JS::"  # indicator of the lastly executed JS file names for each prompt.


@dataclass
class FlatTurnMeta:
    run_idx: int
    turn_idx: int
    n_turns: int
    prompt: str
    checks: List[Dict[str, Any]]
    comment: str


def _merge_coords(prev: List[Dict[str, Any]], placed: List[Dict[str, Any]], removed: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return prev with removed positions dropped and placed added (multi-turn cumulative)."""
    rem_set = {(c["x"], c["y"], c["z"]) for c in removed}
    prev_remaining = [c for c in prev if (c["x"], c["y"], c["z"]) not in rem_set]

    by_key: Dict[Tuple[int, int, int], Dict[str, Any]] = {
        (c["x"], c["y"], c["z"]): c for c in prev_remaining
    }
    for c in placed:
        by_key[(c["x"], c["y"], c["z"])] = c
    return list(by_key.values())


def _flatten_runs(runs: Iterable[Tuple[List[str], List[List[Dict[str, Any]]], str]]) -> List[FlatTurnMeta]:
    """Flatten runs into per-turn metadata in the same order as prompts_for_send."""
    flat: List[FlatTurnMeta] = []
    for run_idx, (prompt_sequence, checks_per_turn, comment) in enumerate(runs, start=1):
        n_turns = len(prompt_sequence)
        for turn_idx, prompt_text in enumerate(prompt_sequence, start=1):
            checks_this_turn = checks_per_turn[turn_idx - 1]
            flat.append(
                FlatTurnMeta(
                    run_idx=run_idx,
                    turn_idx=turn_idx,
                    n_turns=n_turns,
                    prompt=prompt_text,
                    checks=checks_this_turn,
                    comment=comment or "",
                )
            )
    return flat


def _load_builder_model() -> Tuple[str, Dict[str, Any]]:
    """Load builder.json and return (model_name, full_cfg)."""
    builder_cfg_path = Path.cwd().parent / "builder.json"
    builder_cfg = json.loads(builder_cfg_path.read_text(encoding="utf-8"))
    model_name = builder_cfg.get("model", "unknown_model")
    return model_name, builder_cfg


def _safe_model_name(raw: str) -> str:
    return raw.replace("/", "-").replace(" ", "_")[:60]


def run_build_and_save_eval_raw(
    runs: Iterable[Tuple[List[str], List[List[Dict[str, Any]]], str]],
    *,
    results_dir: str | Path = "eval_results",
    inter_prompt_command: str = "Come up to the highest block position, and move 20 blocks in the positive z direction.",
    inter_prompt_delay_ms: int = 10000,
    wait_for_agent_ready_seconds: int = 15,
) -> Path:
    """
    Run the builder agent for all prompts in `runs` and append per-prompt evaluation
    inputs to an intermediate JSON-lines file.

    Each JSON line has at least:
      - run_idx, turn_idx, n_turns
      - prompt
      - checks  (list of {fn, args, ...})
      - coords  (cumulative block coordinates after this turn)
      - _comment
      - builder_model, model_safe, ts, action_file

    The returned path has the form:
      results_dir / f"eval_raw_{model_safe}_{ts}.json"
    """
    runs = list(runs)
    if not runs:
        raise ValueError("No runs provided. Make sure the benchmark loading step produced at least one run.")

    flat_meta = _flatten_runs(runs)
    total_turns = len(flat_meta)

    model_name, builder_cfg = _load_builder_model()
    model_safe = _safe_model_name(model_name)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    results_dir_path = Path(results_dir)
    results_dir_path.mkdir(exist_ok=True)
    eval_raw_path = results_dir_path / f"eval_raw_{model_safe}_{ts}.json"

    print(f"[PY] Using builder model: {model_name} (safe='{model_safe}')")
    print(f"[PY] Total turns to send: {total_turns}")
    print(f"[PY] Intermediate eval_raw file: {eval_raw_path}")

    # Start the main agent (Minecraft builder) process.
    parent_dir = Path.cwd().parent
    proc_main_agent = subprocess.Popen(
        ["node", "main.js"],
        cwd=str(parent_dir),
    )
    print(f"[PY] Builder agent started (PID={proc_main_agent.pid})")

    # Give the agent some time to join the world before sending prompts.
    time.sleep(wait_for_agent_ready_seconds)

    # Start the send_prompts.js helper.
    script = (Path.cwd() / "send_prompts.js").resolve()
    node_exec = shutil.which("node") or "node"

    proc_send_prompts = subprocess.Popen(
        [node_exec, str(script)],
        cwd=str(script.parent),  # Node's process.cwd() equals the JS folder
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,  # line-buffered
    )

    # Build payload from runs (Node still expects flat prompts + run_lengths)
    prompts_for_send = [p for (seq, _, _) in runs for p in seq]
    run_lengths_for_send = [len(seq) for (seq, _, _) in runs]

    assert len(prompts_for_send) == total_turns, "prompts_for_send and flat_meta length mismatch."

    payload = {
        "prompts": prompts_for_send,
        "run_lengths": run_lengths_for_send,
        "clear_between": True,
        "inter_prompt_command": inter_prompt_command,
        "inter_prompt_delay": inter_prompt_delay_ms,
    }
    proc_send_prompts.stdin.write(json.dumps(payload) + "\n")
    proc_send_prompts.stdin.close()

    # Track cumulative coords for each run.
    cumulative_by_run: Dict[int, List[Dict[str, Any]]] = {}
    flat_index = 0  # index into flat_meta

    try:
        with eval_raw_path.open("w", encoding="utf-8") as f_raw:
            for line in proc_send_prompts.stdout:
                line = line.rstrip("\n")
                print(line)  # mirror Node logs to notebook/stdout

                # If Node reports the max-numbered file, parse and record it.
                if not line.startswith(SENTINEL):
                    continue

                payload_raw = line[len(SENTINEL) :]
                try:
                    payload_json = json.loads(payload_raw)
                except json.JSONDecodeError:
                    print("[PY] Failed to parse sentinel JSON.")
                    continue

                if not (payload_json.get("ok") and "path" in payload_json):
                    reason = payload_json.get("reason", "unknown")
                    print(f"[PY] No max file reported (reason={reason}).")
                    continue

                file_path = Path(payload_json["path"])
                print(f"\n[PY] Max action file: index={payload_json.get('index')} name={payload_json.get('name')}")
                print(f"[PY] Path: {file_path}")

                try:
                    placed, removed = read_placed_and_removed_from_action(str(file_path))
                    print(f"[PY] placed={len(placed)}, removed={len(removed)}")
                except Exception as e:  # noqa: BLE001
                    print(f"[PY] Failed to convert action to coords: {e}")
                    continue

                if flat_index >= total_turns:
                    print("[PY] Warning: received more action files than expected; skipping extra action.")
                    continue

                meta = flat_meta[flat_index]
                prev_coords = cumulative_by_run.get(meta.run_idx, [])
                coords = _merge_coords(prev_coords, placed, removed)
                cumulative_by_run[meta.run_idx] = coords

                record = {
                    "run_idx": meta.run_idx,
                    "turn_idx": meta.turn_idx,
                    "n_turns": meta.n_turns,
                    "prompt": meta.prompt,
                    "checks": meta.checks,
                    "coords": coords,
                    "_comment": meta.comment,
                    "builder_model": model_name,
                    "model_safe": model_safe,
                    "ts": ts,
                    "action_file": str(file_path),
                }
                f_raw.write(json.dumps(record, ensure_ascii=False) + "\n")
                f_raw.flush()

                flat_index += 1

    finally:
        try:
            if proc_send_prompts.stdout is not None:
                proc_send_prompts.stdout.close()
            proc_send_prompts.wait(timeout=10)
        except Exception:
            pass

        try:
            proc_main_agent.kill()
            print("[PY] Builder agent process terminated.")
        except Exception:
            pass

    if flat_index != total_turns:
        print(f"[PY] Warning: expected {total_turns} turns but recorded {flat_index}. Some prompts may have failed.")

    print(f"[PY] Finished building. eval_raw written to: {eval_raw_path}")
    return eval_raw_path


__all__ = [
    "run_build_and_save_eval_raw",
]

