"""Validated, local-only workflow settings."""

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Engine = Literal["auto", "native", "langgraph"]


@dataclass(frozen=True)
class RuntimeConfig:
    engine: Engine = "auto"
    max_writer_passes: int = 5
    min_compliance_score: float = 0.90

    def __post_init__(self) -> None:
        if self.engine not in ("auto", "native", "langgraph"):
            raise ValueError("Unsupported execution engine")
        if type(self.max_writer_passes) is not int or self.max_writer_passes < 1:
            raise ValueError("max_writer_passes must be a positive integer")
        score = self.min_compliance_score
        if (
            isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not math.isfinite(score)
            or not 0 < score <= 1
        ):
            raise ValueError("min_compliance_score must be in (0, 1]")

    @classmethod
    def from_file(cls, path: str | Path) -> "RuntimeConfig":
        with Path(path).open(encoding="utf-8") as handle:
            settings = json.load(handle)
        if not isinstance(settings, dict):
            raise ValueError("Runtime configuration must be an object")
        try:
            return cls(**settings)
        except TypeError:
            raise ValueError("Runtime configuration contains unsupported settings") from None
