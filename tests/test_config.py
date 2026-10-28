import json
import tempfile
import unittest
from pathlib import Path

from src.runtime.config import RuntimeConfig


class TestRuntimeConfig(unittest.TestCase):
    def test_invalid_settings(self):
        for settings in ({"engine": "remote"}, {"max_writer_passes": 0}, {"max_writer_passes": True},
                         {"min_compliance_score": float("nan")}, {"min_compliance_score": 0},
                         {"min_compliance_score": 1.1}, {"min_compliance_score": True}):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                RuntimeConfig(**settings)

    def test_load_local_configuration_and_reject_unknown_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"engine": "native", "max_writer_passes": 2}))
            self.assertEqual(RuntimeConfig.from_file(path), RuntimeConfig(engine="native", max_writer_passes=2))
            path.write_text('{"external_model": "not-supported"}')
            with self.assertRaises(TypeError):
                RuntimeConfig.from_file(path)
