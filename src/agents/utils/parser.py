"""Strict, constant-row-memory CSV ingestion preserving clinical identifiers."""

import csv
from itertools import islice
from pathlib import Path
from typing import Dict, Iterator, List, Sequence, Union


class ClinicalCSVError(ValueError):
    """Malformed clinical CSV; messages never include source row values."""


CSVValidationError = ClinicalCSVError


class CDISCChunkParser:
    """Stream strings without numeric/NA coercion or silent row skipping.

    ``chunk_size`` remains a validated compatibility argument. The stdlib reader
    streams one record at a time; collecting all subject events is opt-in.
    """

    def __init__(self, chunk_size: int = 500) -> None:
        if type(chunk_size) is not int or chunk_size < 1:
            raise ValueError("chunk_size must be a positive integer.")
        self.chunk_size = chunk_size

    def stream_csv(
        self, file_path: Union[str, Path], *, required_columns: Sequence[str] = ()
    ) -> Iterator[Dict[str, str]]:
        with open(file_path, newline="", encoding="utf-8-sig") as source:
            reader = csv.reader(source, strict=True)
            try:
                headers = next(reader, None)
                if not headers:
                    raise ClinicalCSVError("CSV requires a non-empty header.")
                headers = [header.strip() for header in headers]
                if any(not header for header in headers) or len(set(headers)) != len(headers):
                    raise ClinicalCSVError("CSV header names must be non-empty and unique.")
                if set(required_columns) - set(headers):
                    raise ClinicalCSVError("CSV is missing required columns.")
                for row in reader:
                    if len(row) != len(headers):
                        raise ClinicalCSVError(f"CSV column count mismatch at line {reader.line_num}.")
                    record = dict(zip(headers, row))
                    if "subject_id" in record and not record["subject_id"].strip():
                        raise ClinicalCSVError(f"Missing subject_id at line {reader.line_num}.")
                    yield record
            except csv.Error:
                raise ClinicalCSVError(f"Malformed CSV near line {reader.line_num}.") from None
            except UnicodeError:
                raise ClinicalCSVError("CSV must be UTF-8 encoded.") from None

    def stream_chunks(self, file_path: Union[str, Path]) -> Iterator[List[Dict[str, str]]]:
        records = self.stream_csv(file_path)
        try:
            while chunk := list(islice(records, self.chunk_size)):
                yield chunk
        finally:
            records.close()

    def iter_subject_records(self, file_path: Union[str, Path], subject_id: str) -> Iterator[Dict[str, str]]:
        if not isinstance(subject_id, str) or not subject_id:
            raise ValueError("subject_id must be a non-empty string.")
        for record in self.stream_csv(file_path, required_columns=("subject_id",)):
            if record["subject_id"] == subject_id:
                yield record

    def fetch_subject_records(self, file_path: Union[str, Path], subject_id: str) -> Dict[str, object]:
        events: List[Dict[str, str]] = list(self.iter_subject_records(file_path, subject_id))
        return {"subject_id": subject_id, "events": events}
