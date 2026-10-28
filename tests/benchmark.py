"""Isolated native/LangGraph benchmarks using fictional local clinical records.

Run: python -m tests.benchmark --records 2000 --repeats 3 --note-repetitions 4
Latency is measured without tracemalloc. A separate streaming pass measures peak
Python allocations, not total process RSS or native cryptography allocations.
Imports, graph compilation, warm-up, data generation, and assertions are excluded
from latency. Generation is included in the memory pass. No clinical text is printed.
"""

import argparse
import gc
import hashlib
import importlib.util
import json
import math
import statistics
import subprocess
import sys
import time
import tracemalloc
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, Sequence

from src.agents.graph import AegisStateGraphOrchestrator
from src.agents.state import AgentState
from src.runtime.config import RuntimeConfig
from src.utils.mock_generator import SyntheticCase, generate_mock_cases

BenchmarkEngine = Literal["native", "langgraph"]


class BenchmarkAssertionError(AssertionError):
    """A correctness, parity, measurement, or performance-budget failure."""


@dataclass(frozen=True)
class BenchmarkConfig:
    records: int = 1000
    repeats: int = 3
    seed: int = 42
    note_repetitions: int = 4
    warmup: int = 5

    def __post_init__(self) -> None:
        for field in ("records", "repeats", "note_repetitions"):
            value = getattr(self, field)
            if type(value) is not int or value < 1:
                raise ValueError(f"{field} must be a positive integer")
        if type(self.warmup) is not int or self.warmup < 0:
            raise ValueError("warmup must be a non-negative integer")
        if type(self.seed) is not int:
            raise ValueError("seed must be an integer")


@dataclass(frozen=True)
class BenchmarkResult:
    engine: BenchmarkEngine
    samples: int
    execution_seconds: float
    mean_ms: float
    p50_ms: float
    p95_ms: float
    throughput_rps: float
    peak_python_bytes: int
    output_digest: str


@dataclass(frozen=True)
class PerformanceLimits:
    max_latency_ratio: float | None = None
    max_memory_ratio: float | None = None
    min_throughput_rps: float | None = None

    def __post_init__(self) -> None:
        for field in ("max_latency_ratio", "max_memory_ratio", "min_throughput_rps"):
            value = getattr(self, field)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value <= 0
            ):
                raise ValueError(f"{field} must be finite and positive")


def _require(condition: bool, message: str) -> None:
    # Unlike a bare assert, these checks also run under python -O.
    if not condition:
        raise BenchmarkAssertionError(message)


def validate_case(case: SyntheticCase, state: AgentState) -> bytes:
    """Check independent clinical/PHI expectations; return a token-normalized state."""
    _require(state["is_approved"] and state["status"] == "approved", "Synthetic record failed QC")
    _require(state["compliance_score"] == 1 and not state["errors"], "Unexpected QC findings")
    _require(tuple(state["coded_terms"]) == case.expected_terms, "Clinical findings differ from synthetic oracle")
    _require(state["node_history"] == [
        "extractor", "writer", "qc_checker", "finalize", "restore_output",
    ], "Unexpected workflow transitions")
    _require(state["loop_count"] == 1, "Unexpected writer revision")
    subject_id = case.record["subject_id"]
    token = state["raw_data"]["subject_id"]
    _require(token != subject_id, "Subject ID was not tokenized")
    _require(subject_id not in state["draft_narrative"], "Subject ID leaked into draft")
    _require(subject_id not in json.dumps(state["raw_data"]), "Subject ID leaked into processing state")
    _require(subject_id in state["output_narrative"], "Subject ID was not restored")
    _require("SUBJ-ANON-" not in state["output_narrative"], "Output still contains a temporary token")
    rendered = json.dumps(state, sort_keys=True, separators=(",", ":"))
    _require(not any(value in rendered for value in case.forbidden_identifiers),
             "Synthetic selected identifier was not fully redacted")
    return rendered.replace(token, "<SUBJECT_TOKEN>").encode("utf-8")


def measure_engine(engine: BenchmarkEngine, settings: BenchmarkConfig) -> BenchmarkResult:
    """Measure one engine; run_benchmarks provides fresh-process isolation."""
    if tracemalloc.is_tracing():
        raise RuntimeError("Benchmark memory measurement requires an untraced process")
    orchestrator = AegisStateGraphOrchestrator(RuntimeConfig(engine=engine))
    for case in generate_mock_cases(
        settings.warmup, seed=settings.seed, note_repetitions=settings.note_repetitions,
    ):
        validate_case(case, orchestrator.run_record(case.record))
    gc.collect()
    latencies: list[float] = []
    digest = hashlib.sha256()
    for _ in range(settings.repeats):
        for case in generate_mock_cases(
            settings.records, seed=settings.seed, note_repetitions=settings.note_repetitions,
        ):
            start = time.perf_counter()
            result = orchestrator.run_record(case.record)
            latencies.append(time.perf_counter() - start)
            canonical = validate_case(case, result)
            digest.update(len(canonical).to_bytes(8, "big"))
            digest.update(canonical)
            del result, canonical
    seconds = math.fsum(latencies)
    samples = len(latencies)
    _require(samples == settings.records * settings.repeats, "Incomplete benchmark workload")
    _require(all(math.isfinite(value) and value > 0 for value in latencies), "Invalid latency sample")
    ordered = sorted(latencies)
    mean_ms = seconds / samples * 1000
    p50_ms = statistics.median(ordered) * 1000
    p95_ms = ordered[math.ceil(samples * 0.95) - 1] * 1000
    del latencies, ordered, case
    gc.collect()
    tracemalloc.start()
    try:
        for case in generate_mock_cases(
            settings.records, seed=settings.seed, note_repetitions=settings.note_repetitions,
        ):
            result = orchestrator.run_record(case.record)
            del result
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    _require(peak > 0, "Invalid peak allocation measurement")
    return BenchmarkResult(
        engine=engine, samples=samples, execution_seconds=seconds,
        mean_ms=mean_ms, p50_ms=p50_ms, p95_ms=p95_ms,
        throughput_rps=samples / seconds, peak_python_bytes=peak,
        output_digest=digest.hexdigest(),
    )


def run_benchmarks(
    settings: BenchmarkConfig, engines: Sequence[BenchmarkEngine] = ("native", "langgraph"),
) -> list[BenchmarkResult]:
    """Run each engine in a fresh interpreter, avoiding cross-engine cache/memory bias."""
    if not engines or len(set(engines)) != len(engines) or any(
        engine not in ("native", "langgraph") for engine in engines
    ):
        raise ValueError("Choose distinct native and/or langgraph engines")
    if "langgraph" in engines and importlib.util.find_spec("langgraph") is None:
        raise RuntimeError("Install requirements-langgraph.txt to compare both engines")
    results = []
    for engine in engines:
        command = [sys.executable, "-m", "tests.benchmark", "--worker-engine", engine]
        for key, value in asdict(settings).items():
            command.extend(("--" + key.replace("_", "-"), str(value)))
        worker = subprocess.run(
            command, cwd=Path(__file__).resolve().parents[1],
            capture_output=True, text=True, check=False,
        )
        if worker.returncode:
            raise RuntimeError(f"{engine} benchmark worker failed:\n{worker.stderr.strip()}")
        results.append(BenchmarkResult(**json.loads(worker.stdout)))
    return results


def assert_results(
    results: Sequence[BenchmarkResult], limits: PerformanceLimits | None = None,
) -> None:
    limits = limits or PerformanceLimits()
    _require(bool(results), "No benchmark results")
    _require(len({result.engine for result in results}) == len(results), "Duplicate engine results")
    for result in results:
        metrics = (result.execution_seconds, result.mean_ms, result.p50_ms,
                   result.p95_ms, result.throughput_rps, result.peak_python_bytes)
        _require(result.samples > 0 and all(math.isfinite(value) and value > 0 for value in metrics),
                 "Invalid benchmark measurements")
        _require(math.isclose(result.throughput_rps, result.samples / result.execution_seconds),
                 "Inconsistent throughput measurement")
        _require(math.isclose(result.mean_ms, result.execution_seconds / result.samples * 1000),
                 "Inconsistent mean latency")
        _require(result.p50_ms <= result.p95_ms, "Invalid latency percentile ordering")
        if limits.min_throughput_rps is not None:
            _require(result.throughput_rps >= limits.min_throughput_rps,
                     f"{result.engine} throughput is below the configured minimum")
    _require(len({result.samples for result in results}) == 1, "Engine sample counts differ")
    _require(len({result.output_digest for result in results}) == 1,
             "Native and LangGraph states differ on the same clinical workload")
    by_engine = {result.engine: result for result in results}
    if limits.max_latency_ratio is not None or limits.max_memory_ratio is not None:
        _require(set(by_engine) == {"native", "langgraph"}, "Ratio budgets require both engines")
    if set(by_engine) == {"native", "langgraph"}:
        native, graph = by_engine["native"], by_engine["langgraph"]
        if limits.max_latency_ratio is not None:
            _require(graph.mean_ms / native.mean_ms <= limits.max_latency_ratio,
                     "LangGraph/native mean-latency ratio exceeds the configured budget")
        if limits.max_memory_ratio is not None:
            _require(graph.peak_python_bytes / native.peak_python_bytes <= limits.max_memory_ratio,
                     "LangGraph/native peak-memory ratio exceeds the configured budget")


def format_summary(results: Sequence[BenchmarkResult], settings: BenchmarkConfig) -> str:
    lines = [
        f"Workload: {settings.records} records x {settings.repeats} timing repeats; "
        f"{settings.note_repetitions} note blocks; seed {settings.seed}",
        "Engine      Mean ms     P50 ms     P95 ms      Records/s    Peak Python MiB",
    ]
    for result in results:
        lines.append(
            f"{result.engine:10} {result.mean_ms:9.3f} {result.p50_ms:10.3f} "
            f"{result.p95_ms:10.3f} {result.throughput_rps:14.2f} "
            f"{result.peak_python_bytes / 1024**2:18.3f}"
        )
    by_engine = {result.engine: result for result in results}
    if set(by_engine) == {"native", "langgraph"}:
        native, graph = by_engine["native"], by_engine["langgraph"]
        lines.append(
            "LangGraph vs native delta: "
            f"mean latency {(graph.mean_ms / native.mean_ms - 1) * 100:+.1f}%; "
            f"P95 {(graph.p95_ms / native.p95_ms - 1) * 100:+.1f}%; "
            f"throughput {(graph.throughput_rps / native.throughput_rps - 1) * 100:+.1f}%; "
            f"peak Python memory {(graph.peak_python_bytes / native.peak_python_bytes - 1) * 100:+.1f}%"
        )
    else:
        lines.append("Engine delta unavailable: only one engine was requested.")
    lines.append("Timing excludes startup/generation/assertions. Memory uses a separate traced streaming pass; not RSS.")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=int, default=1000)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--note-repetitions", type=int, default=4)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--engine", choices=("both", "native", "langgraph"), default="both")
    parser.add_argument("--max-latency-ratio", type=float)
    parser.add_argument("--max-memory-ratio", type=float)
    parser.add_argument("--min-throughput-rps", type=float)
    parser.add_argument("--worker-engine", choices=("native", "langgraph"), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    settings = BenchmarkConfig(args.records, args.repeats, args.seed, args.note_repetitions, args.warmup)
    limits = PerformanceLimits(args.max_latency_ratio, args.max_memory_ratio, args.min_throughput_rps)
    if args.worker_engine:
        print(json.dumps(asdict(measure_engine(args.worker_engine, settings))))
        return 0
    engines: tuple[BenchmarkEngine, ...]
    if args.engine == "both":
        engines = ("native", "langgraph")
    else:
        engines = (args.engine,)
    results = run_benchmarks(settings, engines)
    print(format_summary(results, settings), flush=True)
    try:
        assert_results(results, limits)
    except BenchmarkAssertionError as exc:
        print(f"Assertions: FAIL - {exc}")
        return 1
    print("Assertions: PASS - clinical oracle, redaction, restoration, transitions, state parity, metrics and configured budgets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
