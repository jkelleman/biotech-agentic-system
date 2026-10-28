import importlib.util
import io
import unittest
from copy import deepcopy
from dataclasses import replace
from unittest.mock import patch

from src.agents.graph import AegisStateGraphOrchestrator
from src.runtime.config import RuntimeConfig
from src.utils.mock_generator import generate_mock_cases
from tests.benchmark import (
    BenchmarkAssertionError, BenchmarkConfig, BenchmarkResult, PerformanceLimits,
    assert_results, format_summary, main, run_benchmarks, validate_case,
)


class TestBenchmark(unittest.TestCase):
    def setUp(self):
        self.native = BenchmarkResult(
            engine="native", samples=10, execution_seconds=0.01,
            mean_ms=1, p50_ms=0.9, p95_ms=1.5, throughput_rps=1000,
            peak_python_bytes=1024**2, output_digest="a" * 64,
        )
        self.graph = replace(
            self.native, engine="langgraph", execution_seconds=0.02,
            mean_ms=2, p50_ms=1.8, p95_ms=3, throughput_rps=500,
            peak_python_bytes=2 * 1024**2,
        )

    def test_delta_summary_and_configured_budgets(self):
        results = [self.native, self.graph]
        assert_results(results, PerformanceLimits(2, 2, 500))
        summary = format_summary(results, BenchmarkConfig(records=10, repeats=1))
        self.assertIn("mean latency +100.0%", summary)
        self.assertIn("throughput -50.0%", summary)
        self.assertIn("peak Python memory +100.0%", summary)
        for limits in (PerformanceLimits(max_latency_ratio=1.9),
                       PerformanceLimits(max_memory_ratio=1.9),
                       PerformanceLimits(min_throughput_rps=501)):
            with self.subTest(limits=limits), self.assertRaises(BenchmarkAssertionError):
                assert_results(results, limits)

    def test_parity_and_invalid_measurements_fail_explicitly(self):
        for result in (replace(self.graph, output_digest="b" * 64),
                       replace(self.graph, samples=9),
                       replace(self.graph, mean_ms=float("nan")),
                       replace(self.graph, peak_python_bytes=0),
                       replace(self.graph, throughput_rps=42)):
            with self.subTest(result=result), self.assertRaises(BenchmarkAssertionError):
                assert_results([self.native, result])
        with self.assertRaises(BenchmarkAssertionError):
            assert_results([self.native], PerformanceLimits(max_latency_ratio=2))

    def test_privacy_oracle_rejects_leaked_identifiers(self):
        case = next(generate_mock_cases(1))
        state = AegisStateGraphOrchestrator(RuntimeConfig(engine="native")).run_record(case.record)
        validate_case(case, state)
        leaked = deepcopy(state)
        leaked["raw_data"]["clinical_notes"] += " " + case.record["email"]
        with self.assertRaises(BenchmarkAssertionError) as error:
            validate_case(case, leaked)
        self.assertNotIn(case.record["email"], str(error.exception))
        incorrect = deepcopy(state)
        incorrect["coded_terms"].append("Unsupported finding")
        with self.assertRaises(BenchmarkAssertionError):
            validate_case(case, incorrect)

    def test_cli_always_prints_summary_before_budget_failure(self):
        with patch("tests.benchmark.run_benchmarks", return_value=[self.native, self.graph]):
            with patch("sys.stdout", new_callable=io.StringIO) as output:
                status = main(["--records", "10", "--repeats", "1", "--max-latency-ratio", "1"])
        self.assertEqual(status, 1)
        self.assertIn("LangGraph vs native delta", output.getvalue())
        self.assertIn("Assertions: FAIL", output.getvalue())

    def test_fresh_process_smoke_benchmark(self):
        engines = ("native", "langgraph") if importlib.util.find_spec("langgraph") else ("native",)
        results = run_benchmarks(BenchmarkConfig(records=3, repeats=1, warmup=1, note_repetitions=2), engines)
        assert_results(results)
        self.assertEqual(len(results), len(engines))
        self.assertTrue(all(result.samples == 3 and result.peak_python_bytes > 0 for result in results))

    def test_invalid_configuration(self):
        for kwargs in ({"records": 0}, {"repeats": True}, {"warmup": -1},
                       {"note_repetitions": 0}, {"seed": "42"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                BenchmarkConfig(**kwargs)
        for value in (0, -1, True, float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                PerformanceLimits(max_latency_ratio=value)
