"""
Pilot eval runner — calls the live Lambda for each golden question, judges
the response, writes per-question results, and aggregates a markdown report.

Usage:
    python3 evals/run_eval.py [--limit N] [--workers 4]

The deployed API uses an async job pattern:
  POST {endpoint}              -> 202 {"job_id": "...", "status": "pending"}
  GET  {endpoint}/status/{id}  -> {"status": "pending|done|failed", "answer": ...}

Set EVAL_API_ENDPOINT to override the default Phase 1 endpoint.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import requests

# Make `from evals.judge import judge` work regardless of CWD.
sys.path.insert(0, str(Path(__file__).parent.parent))

from evals.judge import judge

REPO_ROOT = Path(__file__).parent.parent
GOLDEN_PATH = REPO_ROOT / "evals" / "golden_v1.json"
RESULTS_PATH = REPO_ROOT / "evals" / "results.jsonl"
REPORT_PATH = REPO_ROOT / "evals" / "report_v1.md"

# Pulled from frontend/.env (VITE_API_ENDPOINT). Override via env var if needed.
API_ENDPOINT = os.environ.get(
    "EVAL_API_ENDPOINT",
    "https://<API_ID>.execute-api.us-east-1.amazonaws.com/prod/v2/query",
)

# Polling parameters mirror frontend/src/services/api.ts.
INITIAL_POST_TIMEOUT_S = 30
STATUS_GET_TIMEOUT_S = 10
POLL_INTERVAL_S = 2.0
MAX_POLL_S = 300  # 5 minutes total budget per question


def _status_url(job_id: str) -> str:
    """Build the status poll URL the same way the frontend does."""
    return f"{API_ENDPOINT.rstrip('/')}/status/{job_id}"


def call_lambda(question: str, timeout: int = MAX_POLL_S) -> dict:
    """
    POST the question, then poll the status endpoint until done or timeout.

    Returns the final job dict containing at least `answer` and `citations`.
    Raises on HTTP error, missing job_id, failed job, or total-budget timeout.
    """
    start = time.time()

    # Step 1: kick off the async job.
    resp = requests.post(
        API_ENDPOINT,
        json={"query": question, "mode": "research"},
        timeout=INITIAL_POST_TIMEOUT_S,
    )
    resp.raise_for_status()
    data = resp.json()

    # Backward-compat: server may return a complete answer synchronously
    # (sync=true mode or older deployments). Honor it.
    if data.get("answer"):
        return data

    job_id = data.get("job_id")
    if not job_id:
        raise RuntimeError(f"no job_id in response: {data}")

    # Step 2: poll until done, failed, or budget exhausted.
    status_url = _status_url(job_id)
    while time.time() - start < timeout:
        time.sleep(POLL_INTERVAL_S)
        try:
            s = requests.get(status_url, timeout=STATUS_GET_TIMEOUT_S).json()
        except requests.RequestException as e:
            # Transient network blip — keep polling until budget runs out.
            print(f"  [poll] transient error for {job_id}: {e}")
            continue

        status = s.get("status")
        if status == "done":
            return s
        if status == "failed":
            raise RuntimeError(f"job failed: {s.get('error')}")
        # else: pending — keep polling.

    raise TimeoutError(f"job {job_id} timed out after {timeout}s")


def evaluate_one(q: dict) -> dict:
    """Run one golden question end-to-end. Returns the result dict for results.jsonl."""
    record = {
        "id": q["id"],
        "pattern": q.get("pattern", "unknown"),
        "question": q["question"],
    }
    try:
        api_resp = call_lambda(q["question"])
        record["system_answer"] = api_resp.get("answer", "")
        record["citations"] = api_resp.get("citations", [])
        record["intent"] = api_resp.get("intent")
        scores = judge(q["question"], q["ideal_answer"], record["system_answer"])
        record["scores"] = scores
    except Exception as e:
        # Per-question failure must not crash the whole run.
        record["error"] = str(e)
        record["scores"] = {"primary_score": None, "overall": None}
    return record


def aggregate(results: list[dict]) -> dict:
    """Compute headline stats from per-question results."""
    valid = [r for r in results if r.get("scores", {}).get("overall") is not None]
    by_pattern: dict[str, list[float]] = {}
    by_axis: dict[str, list[float]] = {
        "groundedness": [],
        "inference_honesty": [],
        "correctness": [],
        "jurisdiction": [],
    }
    primaries: list[float] = []
    overalls: list[float] = []
    for r in valid:
        s = r["scores"]
        primaries.append(s["primary_score"])
        overalls.append(s["overall"])
        by_pattern.setdefault(r["pattern"], []).append(s["overall"])
        for axis in by_axis:
            v = s.get(axis, {}).get("score") if isinstance(s.get(axis), dict) else None
            if v is not None:
                by_axis[axis].append(v)
    return {
        "n_total": len(results),
        "n_valid": len(valid),
        "n_failed": len(results) - len(valid),
        "primary_score": statistics.mean(primaries) if primaries else 0.0,
        "overall": statistics.mean(overalls) if overalls else 0.0,
        "axes": {a: (statistics.mean(v) if v else 0.0) for a, v in by_axis.items()},
        "patterns": {p: statistics.mean(v) for p, v in by_pattern.items()},
        "worst5": sorted(valid, key=lambda r: r["scores"]["overall"])[:5],
    }


def write_report(agg: dict, out: Path) -> None:
    lines = [
        "# Pilot Eval Report v1",
        "",
        f"_Generated: {datetime.now().isoformat(timespec='seconds')}_",
        "",
        "## Headline",
        "",
        f"- **Primary score (Groundedness x Inference Honesty):** **{agg['primary_score']:.2f}** across {agg['n_valid']} of {agg['n_total']} questions",
        f"- **Overall (4-axis mean):** {agg['overall']:.2f}",
        f"- **Failed runs:** {agg['n_failed']}",
        "",
        "## Per-axis",
        "",
        "| Axis | Score |",
        "|---|---|",
        f"| Groundedness        | {agg['axes']['groundedness']:.2f} |",
        f"| Inference Honesty   | {agg['axes']['inference_honesty']:.2f} |",
        f"| Correctness         | {agg['axes']['correctness']:.2f} |",
        f"| Jurisdiction        | {agg['axes']['jurisdiction']:.2f} |",
        "",
        "## Per-pattern",
        "",
        "| Pattern | Mean Overall |",
        "|---|---|",
    ]
    for pat, score in sorted(agg["patterns"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| {pat} | {score:.2f} |")
    lines += [
        "",
        "## Worst 5 questions",
        "",
    ]
    for r in agg["worst5"]:
        s = r["scores"]
        lines += [
            f"### {r['id']} ({r['pattern']}) - overall {s['overall']:.2f}",
            "",
            f"**Q:** {r['question']}",
            "",
            f"- Groundedness: {s.get('groundedness', {}).get('score', '-')} - _{s.get('groundedness', {}).get('explanation', '')}_",
            f"- Inference Honesty: {s.get('inference_honesty', {}).get('score', '-')} - _{s.get('inference_honesty', {}).get('explanation', '')}_",
            f"- Correctness: {s.get('correctness', {}).get('score', '-')} - _{s.get('correctness', {}).get('explanation', '')}_",
            f"- Jurisdiction: {s.get('jurisdiction', {}).get('score', '-')} - _{s.get('jurisdiction', {}).get('explanation', '')}_",
            "",
        ]
    lines += [
        "## Limitations",
        "",
        "- N=25, AI-curated golden set, no counsel review (Phase 2: 80-question Colby-validated set)",
        "- Light self-calibration (5 hand-graded), no full LLM-vs-human alignment study",
        "- Single run, no variance analysis",
        "- Inference marking is self-reported by the model (Phase 2: post-hoc verification via reflection_agent.py)",
        "",
    ]
    out.write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None,
                        help="Run only the first N questions (smoke test).")
    parser.add_argument("--workers", type=int, default=4,
                        help="Thread-pool size for parallel question execution.")
    args = parser.parse_args()

    # Fail fast with a friendly message if the golden set isn't there yet.
    if not GOLDEN_PATH.exists():
        print(f"ERROR: golden set not found at {GOLDEN_PATH}", file=sys.stderr)
        print("       (Task 5 may still be running — wait for evals/golden_v1.json.)",
              file=sys.stderr)
        sys.exit(1)

    try:
        golden = json.loads(GOLDEN_PATH.read_text())
    except json.JSONDecodeError as e:
        print(f"ERROR: {GOLDEN_PATH} is not valid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(golden, list):
        print(f"ERROR: {GOLDEN_PATH} must be a JSON list of question dicts", file=sys.stderr)
        sys.exit(1)

    if args.limit:
        golden = golden[: args.limit]

    print(f"Running eval on {len(golden)} questions with {args.workers} workers...")
    print(f"  endpoint: {API_ENDPOINT}")

    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(evaluate_one, q): q for q in golden}
        for fut in as_completed(futures):
            r = fut.result()
            results.append(r)
            ok = r.get("scores", {}).get("overall")
            tag = "OK" if ok is not None else "FAIL"
            err = f" ({r.get('error')})" if r.get("error") else ""
            print(f"  [{r['id']}] {tag} overall={ok}{err}")

    results.sort(key=lambda r: r["id"])
    with RESULTS_PATH.open("w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    agg = aggregate(results)
    write_report(agg, REPORT_PATH)
    print(f"\nResults written to {RESULTS_PATH}")
    print(f"Report  written to {REPORT_PATH}")
    print(f"Primary score: {agg['primary_score']:.2f}  Overall: {agg['overall']:.2f}")


if __name__ == "__main__":
    main()
