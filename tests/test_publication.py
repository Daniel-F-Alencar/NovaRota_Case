from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from novarota.ingestion.manifests import read_manifest, validate_manifest, verify_files
from novarota.ingestion.publisher import publish_batch
from novarota.synthetic.generator import GeneratorConfig, generate, json_bytes


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifests = generate(self.root / "generated", GeneratorConfig(transactions=0))
        self.landing = self.root / "landing"
        self.published = self.root / "published"

    def test_only_selected_batch_is_published_and_retry_is_noop(self):
        first = publish_batch(self.manifests[0], self.landing, self.published)
        second = publish_batch(self.manifests[0], self.landing, self.published)
        self.assertGreater(first["files_added"], 0)
        self.assertEqual(second["files_added"], 0)
        self.assertEqual(len(list(self.published.glob("*.json"))), 1)
        self.assertFalse(any("batch_002" in str(path) for path in self.landing.rglob("*")))

    def test_published_file_is_immutable(self):
        publish_batch(self.manifests[0], self.landing, self.published)
        entry = read_manifest(self.manifests[0])["files"][0]
        destination = self.landing / entry["path"]
        destination.write_text("tampered")
        with self.assertRaisesRegex(ValueError, "imutavel"):
            publish_batch(self.manifests[0], self.landing, self.published)
        self.assertEqual(destination.read_text(), "tampered")

    def test_invalid_input_does_not_publish_any_file(self):
        manifest = read_manifest(self.manifests[0])
        source = self.manifests[0].parent / "files" / manifest["files"][-1]["path"]
        source.write_text("tampered")
        with self.assertRaises(ValueError):
            publish_batch(self.manifests[0], self.landing, self.published)
        self.assertFalse(self.landing.exists())
        self.assertFalse(self.published.exists())

    def test_manifest_rejects_traversal_types_and_duplicate_entries(self):
        manifest = read_manifest(self.manifests[0])
        for path in ("../escape.json", "/absolute.json", "C:/escape.json", "source//file.json", "a/../../escape.json", "a\\escape.json"):
            changed = deepcopy(manifest)
            changed["files"][0]["path"] = path
            with self.subTest(path=path), self.assertRaises(ValueError):
                validate_manifest(changed)
        for name, value in (("rows", True), ("bytes", -1), ("schema_version", 1), ("sha256", "bad")):
            changed = deepcopy(manifest)
            changed["files"][0][name] = value
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_manifest(changed)
        changed = deepcopy(manifest)
        changed["files"].append(changed["files"][0])
        with self.assertRaises(ValueError):
            validate_manifest(changed)

    def test_manifest_rows_are_independently_reconciled(self):
        manifest = read_manifest(self.manifests[0])
        manifest["files"][0]["rows"] += 1
        with self.assertRaisesRegex(ValueError, "Contagem"):
            verify_files(manifest, self.manifests[0].parent / "files")

    def test_logical_batch_cannot_change_manifest(self):
        publish_batch(self.manifests[0], self.landing, self.published)
        manifest = read_manifest(self.manifests[0])
        manifest["seed"] = 9876
        self.manifests[0].write_bytes(json_bytes(manifest))
        with self.assertRaisesRegex(ValueError, "outro manifesto"):
            publish_batch(self.manifests[0], self.landing, self.published)
