"""Validated, local-only runtime configuration."""

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class RuntimeConfig:
    engine: Literal["auto", "native", "langgraph"] = "auto"
    max_writer_passes: int = 5
    min_compliance_score: float = 0.90

    @classmethod
    def from_file(cls, path: str) -> "RuntimeConfig":
        with Path(path).open(encoding="utf-8") as source:
            values = json.load(source)
        if not isinstance(values, dict) or set(values) - {
            "engine", "max_writer_passes", "min_compliance_score"
        }:
            raise ValueError("Runtime config must be an object with supported settings.")
        return cls(**values)

    def __post_init__(self) -> None:
        if self.engine not in ("auto", "native", "langgraph"):
            raise ValueError("Unsupported execution engine.")
        if type(self.max_writer_passes) is not int or self.max_writer_passes < 1:
            raise ValueError("max_writer_passes must be a positive integer.")
        if (
            isinstance(self.min_compliance_score, bool)
            or not isinstance(self.min_compliance_score, (int, float))
            or not math.isfinite(self.min_compliance_score)
            or not 0 < self.min_compliance_score <= 1
        ):
            raise ValueError("min_compliance_score must be finite and in (0, 1].")
