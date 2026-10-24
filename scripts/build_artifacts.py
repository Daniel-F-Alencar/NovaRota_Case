"""Empacota fontes para importacao pela UI, sem APIs ou credenciais Databricks."""

import argparse
import ast
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re
import stat
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]


def notebook_from_source(path: Path) -> dict:
    blocks = path.read_text(encoding="utf-8").replace("# Databricks notebook source\n", "", 1).split("# COMMAND ----------")
    cells = []
    for index, block in enumerate(blocks):
        block = block.strip() + "\n"
        if block.startswith("# MAGIC %md"):
            lines = block.splitlines()[1:]
            source = "\n".join(line.removeprefix("# MAGIC ").removeprefix("# MAGIC") for line in lines) + "\n"
            cells.append({"cell_type": "markdown", "id": f"{path.stem}-{index}", "metadata": {}, "source": source.splitlines(keepends=True)})
        else:
            ast.parse(block)
            cells.append({"cell_type": "code", "id": f"{path.stem}-{index}", "metadata": {}, "source": block.splitlines(keepends=True), "outputs": [], "execution_count": None})
    return {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}


def collect_members() -> dict[str, bytes]:
    members = {}
    for name in ("01_bronze_demo", "02_silver_demo"):
        notebook = json.dumps(notebook_from_source(ROOT / f"notebooks/{name}.py"), ensure_ascii=False, indent=1).encode("utf-8")
        members[f"novarota_case/{name}.ipynb"] = notebook
    for file in sorted((ROOT / "src/novarota").rglob("*.py")):
        members["novarota_case/novarota/" + file.relative_to(ROOT / "src/novarota").as_posix()] = file.read_bytes()
    for name in ("data_contracts.md", "bronze-runbook.md", "silver-contracts.md", "silver-runbook.md"):
        members["novarota_case/" + name] = (ROOT / "docs" / name).read_bytes()
    return members


def write_archive(archive: Path, members: dict[str, bytes]) -> int:
    """Declara pais antes dos filhos para importadores sequenciais."""
    directories = set()
    for name in members:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or path.as_posix() != name or "\\" in name or name.endswith("/") or ":" in name:
            raise ValueError(f"Nome de arquivo invalido no ZIP: {name}")
        directories.update(parent.as_posix() + "/" for parent in path.parents if parent.as_posix() != ".")
    if any(directory[:-1] in members for directory in directories):
        raise ValueError("ZIP nao pode ter um arquivo com o mesmo caminho de uma pasta")
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as bundle:
        for directory in sorted(directories, key=lambda name: (name.count("/"), name)):
            info = ZipInfo(directory, date_time=(2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.compress_type = ZIP_STORED
            info.external_attr = ((stat.S_IFDIR | 0o755) << 16) | 0x10
            bundle.writestr(info, b"")
        for name, content in sorted(members.items()):
            info = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.compress_type = ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            bundle.writestr(info, content)
    return len(directories)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="novarota_bronze_demo.zip")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+\.zip", args.name):
        parser.error("--name deve ser um nome simples terminado em .zip")
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    archive = output / args.name
    members = collect_members()
    directories = write_archive(archive, members)
    (output / "01_bronze_demo.ipynb").write_bytes(members["novarota_case/01_bronze_demo.ipynb"])
    (output / "02_silver_demo.ipynb").write_bytes(members["novarota_case/02_silver_demo.ipynb"])
    print(json.dumps({"zip": str(archive), "sha256": sha256(archive.read_bytes()).hexdigest(),
                      "files": len(members), "directories": directories, "entries": len(members) + directories}, indent=2))


if __name__ == "__main__":
    main()
