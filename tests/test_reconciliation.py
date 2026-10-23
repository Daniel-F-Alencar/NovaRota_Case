import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from novarota.ingestion.reconciliation import check_counts, relative_origin, verify_landing
from novarota.ingestion.publisher import publish_batch
from novarota.ingestion.manifests import published_manifests
from novarota.synthetic.generator import GeneratorConfig, generate


class ReconciliationTests(unittest.TestCase):
    def test_empty_file_counts_as_zero_and_missing_rows_fail(self):
        expected = {"one.csv": 2, "empty.csv": 0}
        self.assertTrue(check_counts({"one.csv": 2}, expected))
        self.assertFalse(check_counts({"one.csv": 1}, expected, allow_missing=True))
        with self.assertRaises(ValueError):
            check_counts({"one.csv": 1}, expected)

    def test_extra_rows_or_origins_cannot_be_hidden_by_matching_total(self):
        for actual in ({"one": 3}, {"one": 1, "unknown": 1}):
            with self.subTest(actual=actual), self.assertRaises(ValueError):
                check_counts(actual, {"one": 2}, allow_missing=True)

    def test_uri_prefix_does_not_change_manifest_identity(self):
        relative = "transacoes/batch_001_initial/schema_v1/event_date=2026-01-01/part_0001.csv"
        self.assertEqual(relative_origin("dbfs:/Volumes/a/b/c/landing/" + relative, {relative}), relative)
        self.assertEqual(relative_origin("/Volumes/a/b/c/landing/" + relative, {relative}), relative)
        with self.assertRaises(ValueError):
            relative_origin("/Volumes/a/b/c/other.csv", {relative})

    def test_incomplete_publication_cannot_be_ingested(self):
        with TemporaryDirectory() as root:
            root = Path(root)
            manifests = generate(root / "generated", GeneratorConfig(transactions=0))
            landing, published = root / "landing", root / "published"
            publish_batch(manifests[0], landing, published)
            verify_landing(published_manifests(published), landing)
            extra = landing / "unpublished.csv"
            extra.write_text("id\n1\n")
            with self.assertRaisesRegex(ValueError, "nao publicados"):
                verify_landing(published_manifests(published), landing)
