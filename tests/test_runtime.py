import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.runtime import RuntimeConfig


class TestRuntimeConfig(unittest.TestCase):
    def test_defaults_and_invalid_settings(self):
        self.assertEqual(RuntimeConfig().max_writer_passes, 5)
        for settings in (
            {"engine": "remote"}, {"max_writer_passes": 0},
            {"max_writer_passes": True}, {"max_writer_passes": 1.5},
            {"min_compliance_score": float("nan")},
            {"min_compliance_score": float("inf")},
            {"min_compliance_score": True}, {"min_compliance_score": "0.9"},
            {"min_compliance_score": 0}, {"min_compliance_score": 1.1},
        ):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                RuntimeConfig(**settings)

    def test_json_config_is_loaded_and_validated(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "runtime.json"
            for value in ([], {"api_key": "unused"}, {"max_writer_passes": 0}):
                path.write_text(json.dumps(value), encoding="utf-8")
                with self.assertRaises(ValueError):
                    RuntimeConfig.from_file(str(path))
            path.write_text('{"engine":"native","max_writer_passes":2}', encoding="utf-8")
            self.assertEqual(RuntimeConfig.from_file(str(path)).max_writer_passes, 2)
