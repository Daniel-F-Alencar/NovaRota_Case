from datetime import date
import unittest

from novarota.config import PipelineConfig


class ConfigTests(unittest.TestCase):
    def config(self, **updates):
        return PipelineConfig.from_dict({"catalog": "workspace", "reference_date": "2026-06-30", **updates})

    def test_required_and_unknown_parameters(self):
        for values in ({}, {"catalog": "workspace"}):
            with self.assertRaises(ValueError):
                PipelineConfig.from_dict(values)
        with self.assertRaises(ValueError):
            self.config(catlog="typo")

    def test_sql_identifiers_and_paths_reject_injection(self):
        for catalog in ("x; DROP TABLE t", "../escape", "x.y", ""):
            with self.assertRaises(ValueError):
                self.config(catalog=catalog)
        self.assertEqual(self.config().volume_path, "/Volumes/workspace/novarota_ops/case_files")

    def test_date_and_mode_validation(self):
        for updates in ({"reference_date": "2026-02-30"}, {"seed": True}, {"mode": "all"}, {"mode": "reprocess"}, {"date_from": "2026-01-01"}, {"date_from": "2026-05-01", "date_to": "2026-01-01"}, {"batch_id": "../escape"}):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                self.config(**updates)
        cfg = self.config(mode="reprocess", date_from="2026-01-01", date_to="2026-02-01")
        self.assertEqual(cfg.date_from, date(2026, 1, 1))

    def test_attempt_id_changes_without_changing_batch(self):
        first, second = self.config(), self.config()
        self.assertNotEqual(first.run_id, second.run_id)
        self.assertEqual(first.batch_id, second.batch_id)
