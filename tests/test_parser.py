import tempfile
import unittest
from pathlib import Path

from src.agents.utils.parser import CDISCChunkParser, CSVValidationError


class TestCSVParser(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "clinical.csv"
        self.parser = CDISCChunkParser(chunk_size=1)

    def write(self, text):
        self.path.write_text(text, encoding="utf-8")

    def test_preserves_identifiers_quoted_notes_and_missing_values(self):
        self.write('\ufeffsubject_id,clinical_notes,lab\n001,"nausea,\nresolved",\nNA,normal,3\n')
        rows = list(self.parser.stream_csv(self.path))
        self.assertEqual(rows[0], {"subject_id": "001", "clinical_notes": "nausea,\nresolved", "lab": ""})
        self.assertEqual(rows[1]["subject_id"], "NA")
        self.assertEqual(self.parser.fetch_subject_records(self.path, "001")["events"], rows[:1])
        self.assertEqual(list(self.parser.stream_chunks(self.path)), [[rows[0]], [rows[1]]])

    def test_malformed_input_fails_without_exposing_values(self):
        for text in ("", "subject_id,subject_id\n1,1", "subject_id,\n1,2",
                     "notes\nsecret", "subject_id,notes\n1,secret,extra",
                     "subject_id,notes\n1", 'subject_id,notes\n1,"secret', "subject_id,notes\n,secret"):
            with self.subTest(text=text):
                self.write(text)
                with self.assertRaises(CSVValidationError) as raised:
                    list(self.parser.stream_csv(self.path))
                self.assertNotIn("secret", str(raised.exception))

    def test_missing_file_is_not_a_success_shaped_record(self):
        with self.assertRaises(FileNotFoundError):
            list(self.parser.stream_csv(self.path))
        with self.assertRaises(FileNotFoundError):
            self.parser.fetch_subject_records(self.path, "001")

    def test_invalid_chunk_size(self):
        for value in (0, -1, True, 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                CDISCChunkParser(value)
