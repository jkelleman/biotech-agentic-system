"""Streaming CSV ingestion with explicit structural errors and identifier preservation."""

import csv
from itertools import islice
from pathlib import Path
from typing import Generator, Iterator


class CSVValidationError(ValueError):
    """A malformed clinical CSV; messages never contain row values."""


class CDISCChunkParser:
    """Stream string-valued records; no coercion of IDs, dates, or missing values."""

    def __init__(self, chunk_size: int = 500):
        if type(chunk_size) is not int or chunk_size < 1:
            raise ValueError("chunk_size must be a positive integer")
        self.chunk_size = chunk_size

    def stream_csv(self, file_path: str | Path) -> Generator[dict[str, str], None, None]:
        with Path(file_path).open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle, strict=True)
            try:
                header = next(reader, None)
                if not header:
                    raise CSVValidationError("CSV requires a header")
                header = [field.strip() for field in header]
                if any(not field for field in header) or len(set(header)) != len(header):
                    raise CSVValidationError("CSV headers must be non-empty and unique")
                if "subject_id" not in header:
                    raise CSVValidationError("CSV requires a subject_id column")
                for row in reader:
                    if not row:
                        continue
                    if len(row) != len(header):
                        raise CSVValidationError(f"CSV column count mismatch at line {reader.line_num}")
                    record = dict(zip(header, row))
                    if not record["subject_id"].strip():
                        raise CSVValidationError(f"Missing subject_id at line {reader.line_num}")
                    yield record
            except csv.Error:
                raise CSVValidationError(f"Malformed CSV near line {reader.line_num}") from None

    def iter_subject_records(self, file_path: str | Path, subject_id: str) -> Iterator[dict[str, str]]:
        if not isinstance(subject_id, str) or not subject_id.strip():
            raise ValueError("subject_id must be a non-empty string")
        return (row for row in self.stream_csv(file_path) if row["subject_id"] == subject_id)

    def stream_chunks(self, file_path: str | Path) -> Iterator[list[dict[str, str]]]:
        rows = self.stream_csv(file_path)
        try:
            while chunk := list(islice(rows, self.chunk_size)):
                yield chunk
        finally:
            rows.close()

    def fetch_subject_records(self, file_path: str | Path, subject_id: str) -> dict:
        """Materialize one subject's rows; use iter_subject_records for bounded memory."""
        return {"subject_id": subject_id, "events": list(self.iter_subject_records(file_path, subject_id))}
