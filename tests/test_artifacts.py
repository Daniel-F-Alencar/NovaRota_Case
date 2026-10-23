import ast
import json
from pathlib import Path
import stat
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from scripts.build_artifacts import collect_members, write_archive


class ArtifactTests(unittest.TestCase):
    def test_all_parents_exist_before_their_children(self):
        # Importador sequencial estrito: nunca cria pais implicitamente.
        with TemporaryDirectory() as temp:
            temp = Path(temp)
            archive = temp / "test.zip"
            members = {"project/a.py": b"pass\n", "project/lib/deep/__init__.py": b""}
            write_archive(archive, members)
            destination = temp / "unpacked"
            destination.mkdir()
            with ZipFile(archive) as bundle:
                self.assertIsNone(bundle.testzip())
                for entry in bundle.infolist():
                    target = destination / entry.filename
                    self.assertTrue(target.parent.is_dir(), f"Pai ausente antes de {entry.filename}")
                    if entry.is_dir():
                        self.assertTrue(stat.S_ISDIR(entry.external_attr >> 16))
                        target.mkdir()  # Sem parents=True.
                    else:
                        self.assertTrue(stat.S_ISREG(entry.external_attr >> 16))
                        target.write_bytes(bundle.read(entry))
            for name, content in members.items():
                self.assertEqual((destination / name).read_bytes(), content)

    def test_archive_is_deterministic(self):
        with TemporaryDirectory() as temp:
            first, second = Path(temp) / "first.zip", Path(temp) / "second.zip"
            members = {"root/lib/a.py": b"x = 1\n", "root/notebook.ipynb": b"{}"}
            write_archive(first, members)
            write_archive(second, dict(reversed(list(members.items()))))
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_unsafe_names_and_file_folder_collisions_are_rejected(self):
        with TemporaryDirectory() as temp:
            archive = Path(temp) / "bad.zip"
            for name in ("../bad.py", "/bad.py", "C:/bad.py", "root\\bad.py", "root//bad.py"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    write_archive(archive, {name: b""})
            with self.assertRaises(ValueError):
                write_archive(archive, {"root/lib": b"file", "root/lib/a.py": b"pass"})

    def test_distribution_contains_package_and_executable_notebook_together(self):
        members = collect_members()
        self.assertIn("novarota_case/novarota/__init__.py", members)
        self.assertIn("novarota_case/novarota/ingestion/bronze.py", members)
        notebook = json.loads(members["novarota_case/01_bronze_demo.ipynb"])
        for cell in notebook["cells"]:
            if cell["cell_type"] == "code":
                ast.parse("".join(cell["source"]))
                self.assertEqual(cell["outputs"], [])
        self.assertEqual(notebook["nbformat"], 4)

    def test_actual_distribution_has_explicit_parent_folders(self):
        with TemporaryDirectory() as temp:
            archive = Path(temp) / "actual.zip"
            directories = write_archive(archive, collect_members())
            with ZipFile(archive) as bundle:
                self.assertEqual(directories, 5)
                self.assertEqual(len(bundle.infolist()), 25)
                seen = {"."}
                for entry in bundle.infolist():
                    self.assertIn(Path(entry.filename).parent.as_posix(), seen)
                    if entry.is_dir():
                        seen.add(entry.filename.rstrip("/"))
