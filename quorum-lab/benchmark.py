#!/usr/bin/env python3
"""Benchmark ERC-721 voting throughput on a GoQuorum network."""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import queue
import statistics
import sys
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from web3 import Web3
from web3.exceptions import TimeExhausted

try:  # web3>=7
    from web3.middleware.proof_of_authority import ExtraDataToPOAMiddleware as _POA_MIDDLEWARE
except ImportError:  # fallback for older web3 releases
    from web3.middleware import geth_poa_middleware as _POA_MIDDLEWARE

DEFAULT_ARTIFACT_PATH = os.path.join(
    os.path.dirname(__file__), "artifacts", "deployment.json"
)
DEFAULT_BENCHMARK_DIR = os.path.join(
    os.path.dirname(__file__), "benchmarks"
)
DEFAULT_REPORT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "test_result"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact",
        default=DEFAULT_ARTIFACT_PATH,
        help="Path to deployment artifact containing contract address and ABI",
    )
    parser.add_argument(
        "--rpc-url",
        default=None,
        help="Override RPC endpoint (defaults to value in artifact if present)",
    )
    parser.add_argument(
        "--consensus",
        default="clique",
        help="Consensus label used when naming output files",
    )
    parser.add_argument(
        "--tx-count",
        type=int,
        default=20,
        help="Number of vote transactions to submit",
    )
    parser.add_argument(
        "--proposal-id",
        type=int,
        default=0,
        help="Proposal identifier that voters will support",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Seconds to wait for each transaction receipt",
    )
    parser.add_argument(
        "--gas-limit",
        type=int,
        default=800000,
        help="Gas limit to use for each vote transaction",
    )
    parser.add_argument(
        "--poa",
        action="store_true",
        help="Inject POA middleware (recommended for Clique/IBFT)",
    )
    parser.add_argument(
        "--unlock", "--unlock-duration",
        type=int,
        default=3600,
        help="Attempt to unlock voter accounts for the specified duration (seconds)",
    )
    parser.add_argument(
        "--skip-unlock",
        action="store_true",
        help="Assume accounts are already unlocked and skip personal_unlockAccount calls",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_BENCHMARK_DIR,
        help="Directory where benchmark CSV and summary JSON will be written",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Skip CSV emission, only print summary statistics",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration without sending transactions",
    )
    parser.add_argument(
        "--accounts",
        help=(
            "Comma-separated list of voter accounts to use; defaults to node accounts "
            "excluding the funder"
        ),
    )
    parser.add_argument(
        "--funder",
        help="Account that funds gas fees (defaults to the first node account)",
    )
    parser.add_argument(
        "--labels",
        help="Optional comma-separated labels to include in CSV rows",
    )
    parser.add_argument(
        "--fresh-accounts",
        action="store_true",
        help="Force creation of new voter accounts instead of reusing existing ones",
    )
    parser.add_argument(
        "--phase",
        dest="phases",
        action="append",
        help=(
            "Define a workload phase as COUNT@RATE where RATE may be specified as "
            "e.g. 2tps or 0.5s. Use multiple --phase flags for multi-phase runs."
        ),
    )
    parser.add_argument(
        "--phase-labels",
        help="Optional comma-separated labels matching the defined phases",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help=(
            "Ensure the required voter accounts exist (creating as needed) and exit "
            "without submitting transactions"
        ),
    )
    parser.add_argument(
        "--report-dir",
        default=DEFAULT_REPORT_DIR,
        help="Directory where markdown benchmark reports will be written",
    )
    parser.add_argument(
        "--execution-log",
        help="Optional path to the benchmark log file to include in the report",
    )
    parser.add_argument(
        "--receipt-workers",
        type=int,
        default=1,
        help="Number of worker threads used to collect transaction receipts",
    )
    return parser.parse_args()


def parse_phase_spec(spec: str) -> Dict[str, Any]:
    if "@" not in spec:
        raise ValueError(
            f"Invalid phase specification '{spec}'. Expected format COUNT@RATE (e.g. 6000@2tps)."
        )

    count_part, rate_part = spec.split("@", 1)
    try:
        count = int(count_part)
    except ValueError as exc:  # noqa: BLE001
        raise ValueError(f"Phase count must be an integer, received '{count_part}'.") from exc

    rate_str = rate_part.strip().lower()
    if rate_str.endswith("tps"):
        try:
            tps = float(rate_str[:-3])
        except ValueError as exc:  # noqa: BLE001
            raise ValueError(f"Unable to parse TPS value from '{rate_part}'.") from exc
        if tps <= 0:
            raise ValueError("Phase TPS must be greater than zero.")
        interval = 1.0 / tps
    elif rate_str.endswith("s"):
        try:
            interval = float(rate_str[:-1])
        except ValueError as exc:  # noqa: BLE001
            raise ValueError(f"Unable to parse interval seconds from '{rate_part}'.") from exc
        if interval <= 0:
            raise ValueError("Phase interval must be greater than zero seconds.")
        tps = 1.0 / interval
    else:
        raise ValueError(
            f"Unknown rate suffix in '{rate_part}'. Use values like '2tps' or '0.5s'."
        )

    return {"count": count, "tps": tps, "interval": interval}


def build_phase_plan(args: argparse.Namespace) -> Optional[List[Dict[str, Any]]]:
    if not args.phases:
        return None

    parsed = [parse_phase_spec(item) for item in args.phases]
    labels: List[str]
    if args.phase_labels:
        labels = [label.strip() for label in args.phase_labels.split(",") if label.strip()]
        if len(labels) != len(parsed):
            raise ValueError(
                "Number of --phase-labels entries must match the number of --phase flags"
            )
    else:
        labels = [f"phase{idx + 1}" for idx in range(len(parsed))]

    for entry, label in zip(parsed, labels):
        entry["label"] = label

    return parsed


def percentile(values: List[float], fraction: float) -> float:
    if not values:
        raise ValueError("Cannot compute percentile of empty list")
    ordered = sorted(values)
    index = max(0, math.ceil(fraction * len(ordered)) - 1)
    return ordered[index]


def calculate_latency_stats(latencies: List[float]) -> Optional[Dict[str, float]]:
    if not latencies:
        return None
    avg_latency = statistics.mean(latencies)
    p95_latency = percentile(latencies, 0.95)
    max_latency = max(latencies)
    return {
        "avg": avg_latency,
        "p95": p95_latency,
        "max": max_latency,
        "count": len(latencies),
    }


def collect_latency_breakdown(
    results: List[Dict[str, Any]],
    phase_plan: Optional[List[Dict[str, Any]]],
) -> tuple[Optional[Dict[str, float]], Dict[str, Dict[str, float]]]:
    overall_latencies: List[float] = []
    phase_latencies: Dict[str, List[float]] = {}

    for row in results:
        latency = row.get("latency_sec")
        if latency is None:
            continue
        latency_val = float(latency)
        overall_latencies.append(latency_val)
        phase_label = row.get("phase")
        if phase_plan and phase_label:
            phase_latencies.setdefault(phase_label, []).append(latency_val)

    overall_stats = calculate_latency_stats(overall_latencies)
    phase_stats: Dict[str, Dict[str, float]] = {}
    if phase_plan:
        for entry in phase_plan:
            label = entry["label"]
            phase_stats[label] = calculate_latency_stats(phase_latencies.get(label, [])) or {
                "count": 0,
                "avg": None,
                "p95": None,
                "max": None,
            }
    return overall_stats, phase_stats


def fetch_block_stats(
    web3: Web3, sample_count: int = 50, consensus_hint: Optional[str] = None
) -> Dict[str, Optional[float]]:
    try:
        latest_block_number = web3.eth.block_number
    except Exception as exc:  # noqa: BLE001
        return {"latest": None, "avg": None, "min": None, "max": None, "error": str(exc)}

    try:
        start_number = max(0, latest_block_number - sample_count + 1)
        timestamps: List[int] = []
        for block_number in range(start_number, latest_block_number + 1):
            block = web3.eth.get_block(block_number)
            if not block:
                continue
            timestamps.append(int(block.get("timestamp", 0)))

        if len(timestamps) < 2:
            return {
                "latest": latest_block_number,
                "avg": None,
                "min": None,
                "max": None,
            }

        scale = 1.0
        if consensus_hint and consensus_hint.lower() == "raft":
            scale = 1e-9

        intervals = [
            (timestamps[index] - timestamps[index - 1]) * scale
            for index in range(1, len(timestamps))
        ]
        if not intervals:
            return {
                "latest": latest_block_number,
                "avg": None,
                "min": None,
                "max": None,
            }

        return {
            "latest": latest_block_number,
            "avg": float(statistics.mean(intervals)),
            "min": float(min(intervals)),
            "max": float(max(intervals)),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "latest": latest_block_number,
            "avg": None,
            "min": None,
            "max": None,
            "error": str(exc),
        }


def format_latency_line(label: str, stats: Optional[Dict[str, float]]) -> str:
    if not stats or stats.get("count", 0) == 0:
        return f"- {label}: no successful receipts"
    avg = stats["avg"]
    p95 = stats["p95"]
    max_latency = stats["max"]
    count = stats["count"]
    return (
        f"- {label}: avg {avg:.2f} s, p95 {p95:.2f} s, max {max_latency:.2f} s "
        f"(n = {count})"
    )


def sanitize_component(value: str) -> str:
    return "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in value)


def generate_report_filename(
    report_dir: str,
    timestamp: str,
    consensus: str,
    phase_plan: Optional[List[Dict[str, Any]]],
) -> str:
    ensure_directory(report_dir)
    date_prefix = timestamp[:8]
    consensus_part = sanitize_component(consensus.lower())
    workload_part = "phase" if phase_plan else "sequential"
    base_name = f"{date_prefix}_{consensus_part}_{workload_part}.md"
    candidate = os.path.join(report_dir, base_name)
    counter = 2
    while os.path.exists(candidate):
        candidate = os.path.join(
            report_dir,
            f"{date_prefix}_{consensus_part}_{workload_part}_run{counter}.md",
        )
        counter += 1
    return candidate


def format_phase_plan(phase_plan: Optional[List[Dict[str, Any]]]) -> str:
    if not phase_plan:
        return "Sequential run"

    def _format_tps(value: float) -> str:
        formatted = f"{value:.2f}"
        return formatted.rstrip("0").rstrip(".")

    formatted = [
        f"{entry['label']} {entry['count']} @ {_format_tps(entry['tps'])} TPS"
        for entry in phase_plan
    ]
    return ", ".join(formatted)


def generate_markdown_report(
    args: argparse.Namespace,
    paths: Dict[str, str],
    summary_payload: Dict[str, Any],
    phase_plan: Optional[List[Dict[str, Any]]],
    block_stats: Dict[str, Optional[float]],
    overall_latency: Optional[Dict[str, float]],
    phase_latency: Dict[str, Dict[str, float]],
) -> Optional[str]:
    try:
        timestamp = summary_payload["timestamp"]
    except KeyError:
        return None

    try:
        header_dt = datetime.strptime(timestamp, "%Y%m%dT%H%M%SZ")
        header_str = header_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        header_str = timestamp

    workload_label = "Phase Workload" if phase_plan else "Sequential Workload"
    report_lines = [
        f"# {summary_payload.get('consensus', '').capitalize()} Benchmark – {workload_label} ({header_str})",
        "",
        "## Throughput",
        f"- Total votes: {summary_payload.get('tx_count', 0)} "
        f"(success {summary_payload.get('success', 0)}, failed {summary_payload.get('failed', 0)})",
        f"- Wall-clock duration: {summary_payload.get('duration_seconds', 0.0):.2f} s",
        f"- Effective TPS: {summary_payload.get('tps_estimate', 0.0):.2f} tx/s",
        f"- Phase plan: {format_phase_plan(phase_plan)}",
        "",
        "## Block Interval",
    ]

    latest_block = block_stats.get("latest")
    latest_block_str = "N/A" if latest_block is None else str(int(latest_block))
    avg_interval = block_stats.get("avg")
    min_interval = block_stats.get("min")
    max_interval = block_stats.get("max")

    if avg_interval is not None:
        report_lines.append(f"- Latest observed block: {latest_block_str}")
        report_lines.append(
            f"- Average interval (last 50 blocks): {avg_interval:.2f} s"
        )
        report_lines.append(
            f"- Min/Max interval: {min_interval:.2f} s / {max_interval:.2f} s"
        )
    else:
        report_lines.append(f"- Latest observed block: {latest_block_str}")
        report_lines.append("- Average interval (last 50 blocks): N/A")
        report_lines.append("- Min/Max interval: N/A / N/A")

    report_lines.append("")
    report_lines.append("## Confirmation Delay (T_confirmed − T_sent)")
    report_lines.append(format_latency_line("Overall", overall_latency))
    for label, stats in phase_latency.items():
        report_lines.append(format_latency_line(f"Phase {label}", stats))

    report_lines.extend(
        [
            "",
            "## Artifacts",
            f"- Summary JSON: `{paths['summary']}`",
            f"- Detailed CSV: `{paths['csv']}`",
        ]
    )
    if args.execution_log:
        report_lines.append(f"- Execution log: `{args.execution_log}`")

    report_path = generate_report_filename(
        os.path.abspath(args.report_dir),
        timestamp=timestamp,
        consensus=summary_payload.get("consensus", "benchmark"),
        phase_plan=phase_plan,
    )
    with open(report_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(report_lines) + "\n")

    print(f"Markdown report written to {report_path}")
    return report_path


def launch_receipt_worker(
    web3: Web3,
    contract: Any,
    args: argparse.Namespace,
    results: List[Dict[str, Any]],
    label_string: str,
    start_overall: float,
    results_lock: threading.Lock,
) -> tuple[queue.Queue, List[threading.Thread]]:
    submission_queue: queue.Queue[Optional[Dict[str, Any]]] = queue.Queue()

    def worker() -> None:
        while True:
            item = submission_queue.get()
            if item is None:
                submission_queue.task_done()
                break

            tx_hash = item["tx_hash"]
            tx_hash_hex = tx_hash.hex()
            phase_suffix = f" during {item['phase']}" if item["phase"] else ""
            try:
                receipt = web3.eth.wait_for_transaction_receipt(
                    tx_hash, timeout=args.timeout
                )
                completion_time = time.perf_counter()

                gas_used = receipt.get("gasUsed")
                status = receipt.get("status", 0)
                token_id: Optional[int] = None
                proposal_id: Optional[int] = None

                try:
                    # VoteCast 이벤트만 필터링하여 경고 방지
                    vote_cast_logs = contract.events.VoteCast().process_receipt(receipt, errors='ignore')
                    if vote_cast_logs:
                        event_args = vote_cast_logs[0]["args"]
                        token_id = int(event_args.get("tokenId"))
                        proposal_id = int(event_args.get("proposalId"))
                except Exception:  # noqa: BLE001 - decode best effort
                    pass

                row = {
                    "index": item["index"],
                    "account": item["account"],
                    "tx_hash": tx_hash_hex,
                    "status": status,
                    "gas_used": gas_used,
                    "latency_sec": completion_time - item["start_time"],
                    "token_id": token_id,
                    "proposal_id": proposal_id,
                    "labels": label_string,
                    "phase": item["phase"],
                    "submitted_sec": item["submission_time"] - start_overall,
                    "completed_sec": completion_time - start_overall,
                }
            except TimeExhausted:
                row = {
                    "index": item["index"],
                    "account": item["account"],
                    "tx_hash": tx_hash_hex,
                    "status": 0,
                    "gas_used": None,
                    "latency_sec": None,
                    "token_id": None,
                    "proposal_id": None,
                    "labels": label_string,
                    "phase": item["phase"],
                    "submitted_sec": item["submission_time"] - start_overall,
                    "completed_sec": None,
                }
                print(
                    f"[ERROR] Receipt timeout for voter {item['account']}{phase_suffix}",
                    file=sys.stderr,
                )
            except Exception as exc:  # noqa: BLE001
                row = {
                    "index": item["index"],
                    "account": item["account"],
                    "tx_hash": tx_hash_hex,
                    "status": 0,
                    "gas_used": None,
                    "latency_sec": None,
                    "token_id": None,
                    "proposal_id": None,
                    "labels": label_string,
                    "phase": item["phase"],
                    "submitted_sec": item["submission_time"] - start_overall,
                    "completed_sec": None,
                    "error": str(exc),
                }
                print(
                    f"[ERROR] Failed while fetching receipt for {item['account']}{phase_suffix}: {exc}",
                    file=sys.stderr,
                )
            finally:
                with results_lock:
                    results.append(row)
                submission_queue.task_done()

    worker_threads: List[threading.Thread] = []
    worker_count = max(1, args.receipt_workers)
    for _ in range(worker_count):
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        worker_threads.append(thread)

    return submission_queue, worker_threads


def execute_sequential_benchmark(
    web3: Web3,
    contract: Any,
    voters: List[str],
    args: argparse.Namespace,
    labels: List[str],
) -> tuple[List[Dict[str, Any]], float]:
    results: List[Dict[str, Any]] = []
    label_string = "|".join(labels) if labels else ""
    results_lock = threading.Lock()
    start_overall = time.perf_counter()
    submission_queue, worker_threads = launch_receipt_worker(
        web3=web3,
        contract=contract,
        args=args,
        results=results,
        label_string=label_string,
        start_overall=start_overall,
        results_lock=results_lock,
    )

    for index, voter in enumerate(voters):
        iteration_start = time.perf_counter()
        try:
            tx_hash = contract.functions.vote(args.proposal_id).transact(
                {
                    "from": voter,
                    "gas": args.gas_limit,
                }
            )
            submission_time = time.perf_counter()
            submission_queue.put(
                {
                    "index": index,
                    "account": voter,
                    "tx_hash": tx_hash,
                    "start_time": iteration_start,
                    "submission_time": submission_time,
                    "phase": None,
                }
            )
        except Exception as exc:  # noqa: BLE001 - capture all submission failures
            submission_time = time.perf_counter()
            with results_lock:
                results.append(
                    {
                        "index": index,
                        "account": voter,
                        "tx_hash": None,
                        "status": 0,
                        "gas_used": None,
                        "latency_sec": None,
                        "token_id": None,
                        "proposal_id": None,
                        "labels": label_string,
                        "phase": None,
                        "submitted_sec": submission_time - start_overall,
                        "completed_sec": None,
                        "error": str(exc),
                    }
                )
            print(f"[ERROR] Failed to submit vote from {voter}: {exc}", file=sys.stderr)

    for _ in worker_threads:
        submission_queue.put(None)
    submission_queue.join()
    for thread in worker_threads:
        thread.join()

    duration = time.perf_counter() - start_overall
    results.sort(key=lambda item: item["index"])
    return results, duration


def execute_phased_benchmark(
    web3: Web3,
    contract: Any,
    voters: List[str],
    args: argparse.Namespace,
    labels: List[str],
    phase_plan: List[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], float]:
    total_required = sum(entry["count"] for entry in phase_plan)
    if total_required > len(voters):
        raise ValueError(
            f"Phase configuration requires {total_required} voters but only {len(voters)} were provided"
        )

    schedule: List[Dict[str, Any]] = []
    voter_index = 0
    for phase_entry in phase_plan:
        for _ in range(phase_entry["count"]):
            schedule.append(
                {
                    "index": voter_index,
                    "account": voters[voter_index],
                    "interval": phase_entry["interval"],
                    "phase": phase_entry["label"],
                }
            )
            voter_index += 1

    results: List[Dict[str, Any]] = []
    label_string = "|".join(labels) if labels else ""
    results_lock = threading.Lock()
    start_overall = time.perf_counter()
    submission_queue, worker_threads = launch_receipt_worker(
        web3=web3,
        contract=contract,
        args=args,
        results=results,
        label_string=label_string,
        start_overall=start_overall,
        results_lock=results_lock,
    )
    next_emit_time = start_overall

    for index, item in enumerate(schedule):
        if index > 0:
            now = time.perf_counter()
            sleep_duration = next_emit_time - now
            if sleep_duration > 0:
                time.sleep(sleep_duration)

        iteration_start = time.perf_counter()
        try:
            tx_hash = contract.functions.vote(args.proposal_id).transact(
                {
                    "from": item["account"],
                    "gas": args.gas_limit,
                }
            )
            submission_time = time.perf_counter()
            submission_queue.put(
                {
                    "index": item["index"],
                    "account": item["account"],
                    "tx_hash": tx_hash,
                    "start_time": iteration_start,
                    "submission_time": submission_time,
                    "phase": item["phase"],
                }
            )
        except Exception as exc:  # noqa: BLE001 - capture all submission failures
            submission_time = time.perf_counter()
            with results_lock:
                results.append(
                    {
                        "index": item["index"],
                        "account": item["account"],
                        "tx_hash": None,
                        "status": 0,
                        "gas_used": None,
                        "latency_sec": None,
                        "token_id": None,
                        "proposal_id": None,
                        "labels": label_string,
                        "phase": item["phase"],
                        "submitted_sec": submission_time - start_overall,
                        "completed_sec": None,
                        "error": str(exc),
                    }
                )
            print(
                f"[ERROR] Failed to submit vote from {item['account']} during {item['phase']}: {exc}",
                file=sys.stderr,
            )
        finally:
            next_emit_time = max(next_emit_time + item["interval"], time.perf_counter())

    for _ in worker_threads:
        submission_queue.put(None)
    submission_queue.join()
    for thread in worker_threads:
        thread.join()

    duration = time.perf_counter() - start_overall
    results.sort(key=lambda item: item["index"])  # Preserve submission order
    return results, duration


def load_artifact(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Deployment artifact not found: {path}. Run Phase 4 deployment first."
        )
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def ensure_directory(path: str) -> None:
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def inject_poa_if_needed(web3: Web3, enabled: bool) -> None:
    if enabled:
        try:
            web3.middleware_onion.inject(_POA_MIDDLEWARE, layer=0)
        except ValueError:
            # Middleware already present
            pass


def personal_new_account(web3: Web3, password: str = "") -> str:
    return web3.manager.request_blocking("personal_newAccount", [password])


def personal_unlock_account(web3: Web3, account: str, password: str, duration: int) -> Any:
    return web3.manager.request_blocking("personal_unlockAccount", [account, password, duration])


def resolve_accounts(
    web3: Web3,
    funder: Optional[str],
    explicit_accounts: Optional[str],
    unlock_duration: int,
    skip_unlock: bool,
    required: int,
    fresh_accounts: bool,
) -> Dict[str, List[str]]:
    chain_accounts = [Web3.to_checksum_address(acc) for acc in web3.eth.accounts]
    if not chain_accounts:
        raise RuntimeError("No accounts available on the connected node")

    funder_account: str
    if funder:
        funder_account = Web3.to_checksum_address(funder)
        if funder_account not in chain_accounts:
            raise ValueError(
                f"Specified funder {funder_account} is not unlocked on the node"
            )
    else:
        funder_account = chain_accounts[0]

    if explicit_accounts:
        voters = [Web3.to_checksum_address(item.strip()) for item in explicit_accounts.split(",") if item.strip()]
    else:
        voters = []
        if not fresh_accounts:
            voters = [acc for acc in chain_accounts if acc.lower() != funder_account.lower()]

    created_accounts: List[str] = []
    if len(voters) < required:
        needed = required - len(voters)
        print(f"[INFO] Creating {needed} new voter accounts...", flush=True)
        creation_start = time.perf_counter()
        for _ in range(needed):
            try:
                new_account = personal_new_account(web3)
            except Exception as exc:  # noqa: BLE001
                raise ValueError(
                    "Insufficient voter accounts and failed to create new ones. Provide --accounts "
                    "or reduce --tx-count."
                ) from exc
            checksum = Web3.to_checksum_address(new_account)
            voters.append(checksum)
            created_accounts.append(checksum)
            created_so_far = len(created_accounts)
            if needed <= 10 or created_so_far == needed or created_so_far % max(1, needed // 10) == 0:
                elapsed = time.perf_counter() - creation_start
                print(
                    f"  [INFO] Created {created_so_far}/{needed} accounts ({elapsed:.1f}s elapsed)",
                    flush=True,
                )
        total_elapsed = time.perf_counter() - creation_start
        print(
            f"[INFO] Finished account provisioning in {total_elapsed:.1f}s (total accounts: {len(voters)})",
            flush=True,
        )

    voters = voters[:required]

    # Attempt to unlock accounts for smoother execution, emitting progress logs
    if skip_unlock:
        print("[INFO] Skipping account unlock as requested", flush=True)
    else:
        addresses_to_unlock = [funder_account] + voters
        total_unlocks = len(addresses_to_unlock)
        if total_unlocks:
            print(
                f"[INFO] Unlocking {total_unlocks} accounts for {unlock_duration}s...",
                flush=True,
            )
            unlock_failures = 0
            unlock_start = time.perf_counter()
            progress_interval = max(1, total_unlocks // 10)
            for index, address in enumerate(addresses_to_unlock, start=1):
                try:
                    personal_unlock_account(web3, address, "", unlock_duration)
                except Exception:  # noqa: BLE001 - best effort unlock, node may not expose personal API
                    unlock_failures += 1
                if (
                    total_unlocks <= 10
                    or index == total_unlocks
                    or index % progress_interval == 0
                ):
                    elapsed = time.perf_counter() - unlock_start
                    print(
                        f"  [INFO] Unlocked {index}/{total_unlocks} accounts ({elapsed:.1f}s elapsed)",
                        flush=True,
                    )
            if unlock_failures:
                print(
                    f"[WARN] Failed to unlock {unlock_failures} account(s); proceeding regardless.",
                    flush=True,
                )

    return {"funder": funder_account, "voters": voters, "created": created_accounts}


def build_output_paths(output_dir: str, consensus: str) -> Dict[str, str]:
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    ensure_directory(output_dir)
    return {
        "csv": os.path.join(output_dir, f"{consensus}.csv"),
        "summary": os.path.join(output_dir, f"{consensus}_summary_{timestamp}.json"),
        "timestamp": timestamp,
    }


def main() -> int:
    args = parse_args()

    try:
        phase_plan = build_phase_plan(args)
    except ValueError as exc:  # noqa: BLE001
        print(f"Fatal error: {exc}", file=sys.stderr)
        return 1

    if phase_plan:
        total_phase_txs = sum(entry["count"] for entry in phase_plan)
        if args.tx_count and args.tx_count != total_phase_txs:
            print(
                f"[INFO] Overriding --tx-count ({args.tx_count}) with phase total {total_phase_txs}",
                file=sys.stderr,
            )
        args.tx_count = total_phase_txs

    artifact = load_artifact(os.path.abspath(args.artifact))
    contract_info = artifact.get("contract", {})
    network_info = artifact.get("network", {})

    abi = contract_info.get("abi")
    address = contract_info.get("address")
    if not abi or not address:
        raise KeyError("Artifact must include contract.abi and contract.address")

    rpc_url = args.rpc_url or network_info.get("rpcUrl") or "http://localhost:8545"

    web3 = Web3(Web3.HTTPProvider(rpc_url))
    inject_poa_if_needed(web3, args.poa)

    if not web3.is_connected():
        raise ConnectionError(f"Unable to reach RPC endpoint: {rpc_url}")

    chain_id = web3.eth.chain_id
    latest_block = web3.eth.block_number

    contract = web3.eth.contract(
        address=Web3.to_checksum_address(address),
        abi=abi,
    )

    proposals: List[str] = contract_info.get("proposals", [])
    if args.proposal_id >= len(proposals):
        print(
            f"[WARN] Proposal id {args.proposal_id} exceeds stored metadata "
            f"(found {len(proposals)} entries). Proceeding regardless.",
            file=sys.stderr,
        )

    accounts = resolve_accounts(
        web3,
        funder=args.funder,
        explicit_accounts=args.accounts,
        unlock_duration=args.unlock,
        skip_unlock=args.skip_unlock,
        required=args.tx_count,
        fresh_accounts=args.fresh_accounts,
    )

    voters = accounts["voters"]
    funder = accounts["funder"]
    created_accounts = accounts.get("created", [])

    print("RPC:", rpc_url)
    print("Chain ID:", chain_id)
    print("Latest block:", latest_block)
    print("Consensus label:", args.consensus)
    print("Funder:", funder)
    print("Total voters:", len(voters))
    if created_accounts:
        print("Newly created accounts:", len(created_accounts))

    if args.prepare_only:
        print("Preparation complete. No transactions submitted.")
        return 0

    if args.dry_run:
        print("Dry run complete. No transactions sent.")
        return 0

    labels = []
    if args.labels:
        labels = [item.strip() for item in args.labels.split(",") if item.strip()]
    if phase_plan:
        results, duration = execute_phased_benchmark(
            web3=web3,
            contract=contract,
            voters=voters,
            args=args,
            labels=labels,
            phase_plan=phase_plan,
        )
    else:
        results, duration = execute_sequential_benchmark(
            web3=web3,
            contract=contract,
            voters=voters,
            args=args,
            labels=labels,
        )

    success_latencies = [row["latency_sec"] for row in results if row["latency_sec"]]
    success_count = sum(1 for row in results if row["status"] == 1)
    failure_count = len(results) - success_count
    tps = success_count / duration if duration > 0 else 0.0

    print("--- Benchmark Summary ---")
    print(f"Transactions attempted: {len(results)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {failure_count}")
    print(f"Elapsed seconds: {duration:.4f}")
    print(f"Approx TPS: {tps:.4f}")

    if success_latencies:
        avg_latency = statistics.mean(success_latencies)
        sorted_latencies = sorted(success_latencies)
        p95_index = max(0, math.ceil(0.95 * len(sorted_latencies)) - 1)
        p95_latency = sorted_latencies[p95_index]
        max_latency = sorted_latencies[-1]
        print(f"Latency avg: {avg_latency:.4f}s")
        print(f"Latency p95: {p95_latency:.4f}s")
        print(f"Latency max: {max_latency:.4f}s")
    else:
        print("No successful receipts to compute latency stats.")

    phase_results: Dict[str, Dict[str, int]] = {}
    if phase_plan:
        for row in results:
            phase_label = row.get("phase") or "unlabeled"
            phase_entry = phase_results.setdefault(
                phase_label, {"total": 0, "success": 0, "failed": 0}
            )
            phase_entry["total"] += 1
            if row.get("status") == 1:
                phase_entry["success"] += 1
            else:
                phase_entry["failed"] += 1

        print("Phase breakdown:")
        for entry in phase_plan:
            label = entry["label"]
            stats = phase_results.get(label, {"total": 0, "success": 0, "failed": 0})
            print(
                f"  {label}: target {entry['count']} | submitted {stats['total']} | "
                f"success {stats['success']} | failed {stats['failed']} | "
                f"target_rate {entry['tps']:.2f} tps"
            )

    paths = build_output_paths(os.path.abspath(args.output_dir), args.consensus)
    block_stats = fetch_block_stats(web3, consensus_hint=args.consensus)
    overall_latency_stats, phase_latency_stats = collect_latency_breakdown(results, phase_plan)

    if not args.summary_only:
        header = [
            "index",
            "account",
            "tx_hash",
            "status",
            "gas_used",
            "latency_sec",
            "token_id",
            "proposal_id",
            "phase",
            "submitted_sec",
            "completed_sec",
            "labels",
        ]
        ensure_directory(os.path.dirname(paths["csv"]))
        write_header = not os.path.exists(paths["csv"])
        with open(paths["csv"], "a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=header)
            if write_header:
                writer.writeheader()
            for row in results:
                writer.writerow({key: row.get(key) for key in header})
        print(f"Detailed results appended to {paths['csv']}")

    summary_payload = {
        "timestamp": paths["timestamp"],
        "consensus": args.consensus,
        "rpc_url": rpc_url,
        "chain_id": chain_id,
        "latest_block": block_stats.get("latest", latest_block),
        "tx_count": len(results),
        "success": success_count,
        "failed": failure_count,
        "duration_seconds": duration,
        "tps_estimate": tps,
        "proposal_id": args.proposal_id,
        "proposals": proposals,
        "labels": labels,
        "new_accounts": created_accounts,
    }

    if success_latencies:
        summary_payload.update(
            {
                "latency_avg_sec": avg_latency,
                "latency_p95_sec": p95_latency,
                "latency_max_sec": max_latency,
            }
        )

    if phase_plan:
        summary_payload["phase_plan"] = [
            {
                "label": entry["label"],
                "count": entry["count"],
                "tps": entry["tps"],
                "interval_sec": entry["interval"],
            }
            for entry in phase_plan
        ]
        summary_payload["phase_results"] = phase_results

    with open(paths["summary"], "w", encoding="utf-8") as handle:
        json.dump(summary_payload, handle, indent=2)
    print(f"Summary written to {paths['summary']}")

    generate_markdown_report(
        args=args,
        paths=paths,
        summary_payload=summary_payload,
        phase_plan=phase_plan,
        block_stats=block_stats,
        overall_latency=overall_latency_stats,
        phase_latency=phase_latency_stats,
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"Fatal error: {exc}", file=sys.stderr)
        raise
