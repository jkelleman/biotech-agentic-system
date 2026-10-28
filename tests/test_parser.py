from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.agents.utils.parser import CDISCChunkParser, ClinicalCSVError


class TestClinicalCSV(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "records.csv"
        self.parser = CDISCChunkParser(chunk_size=1)

    def write(self, content):
        self.path.write_text(content, encoding="utf-8")
        return self.path

    def test_preserves_identifiers_missing_values_and_quoted_notes(self):
        path = self.write('\ufeffsubject_id,notes,value\n001,"denies nausea,\nreports vomiting",NA\n002,,\n001,followup,3.0\n')
        records = list(self.parser.stream_csv(path))
        self.assertEqual(records[0]["subject_id"], "001")
        self.assertEqual(records[0]["value"], "NA")
        self.assertEqual(records[1]["value"], "")
        self.assertIn("\n", records[0]["notes"])
        self.assertEqual(len(self.parser.fetch_subject_records(path, "001")["events"]), 2)
        self.assertEqual(list(self.parser.iter_subject_records(path, "1")), [])

    def test_malformed_inputs_are_not_silently_skipped(self):
        for content in (
            "", "subject_id,subject_id\n1,1\n", "subject_id, \n1,2\n",
            "subject_id,value\n1\n", "subject_id\n1,2\n",
            'subject_id,notes\n1,"unterminated\n', 'subject_id\n\n',
        ):
            with self.subTest(content=content), self.assertRaises(ClinicalCSVError):
                list(self.parser.stream_csv(self.write(content)))

    def test_invalid_encoding_is_explicit(self):
        self.path.write_bytes(b"subject_id\n\xff\n")
        with self.assertRaises(ClinicalCSVError):
            list(self.parser.stream_csv(self.path))

    def test_missing_files_and_subject_column_raise(self):
        with self.assertRaises(FileNotFoundError):
            list(self.parser.stream_csv(self.path))
        with self.assertRaises(ClinicalCSVError):
            self.parser.fetch_subject_records(self.write("wrong\n1\n"), "001")
        with self.assertRaises(ClinicalCSVError):
            self.parser.fetch_subject_records(self.write("wrong\n"), "001")

    def test_empty_valid_dataset(self):
        self.assertEqual(list(self.parser.stream_csv(self.write("subject_id,value\n"))), [])

    def test_invalid_chunk_size(self):
        for size in (0, -1, True, 1.5):
            with self.subTest(size=size), self.assertRaises(ValueError):
                CDISCChunkParser(size)

    def test_stream_is_lazy(self):
        records = self.parser.stream_csv(self.write("subject_id\n001\n002,broken\n"))
        self.assertEqual(next(records), {"subject_id": "001"})
        with self.assertRaises(ClinicalCSVError):
            next(records)

    def test_stream_chunks_respects_chunk_size(self):
        path = self.write("subject_id\n001\n002\n")
        self.assertEqual(
            list(self.parser.stream_chunks(path)),
            [[{"subject_id": "001"}], [{"subject_id": "002"}]],
        )
