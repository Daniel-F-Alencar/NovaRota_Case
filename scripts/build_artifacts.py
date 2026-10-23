"""Empacota fontes para importacao pela UI, sem APIs ou credenciais Databricks."""

import ast
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]


def notebook_from_source(path: Path) -> dict:
    blocks = path.read_text(encoding="utf-8").replace("# Databricks notebook source\n", "", 1).split("# COMMAND ----------")
    cells = []
    for index, block in enumerate(blocks):
        block = block.strip() + "\n"
        if block.startswith("# MAGIC %md"):
            lines = block.splitlines()[1:]
            source = "\n".join(line.removeprefix("# MAGIC ").removeprefix("# MAGIC") for line in lines) + "\n"
            cells.append({"cell_type": "markdown", "id": f"novarota-bronze-{index}", "metadata": {}, "source": source.splitlines(keepends=True)})
        else:
            ast.parse(block)
            cells.append({"cell_type": "code", "id": f"novarota-bronze-{index}", "metadata": {}, "source": block.splitlines(keepends=True), "outputs": [], "execution_count": None})
    return {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}


def main() -> None:
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    notebook = json.dumps(notebook_from_source(ROOT / "notebooks/01_bronze_demo.py"), ensure_ascii=False, indent=1).encode("utf-8")
    archive = output / "novarota_bronze_demo.zip"
    members = {"novarota_case/01_bronze_demo.ipynb": notebook}
    for file in sorted((ROOT / "src/novarota").rglob("*.py")):
        members["novarota_case/novarota/" + file.relative_to(ROOT / "src/novarota").as_posix()] = file.read_bytes()
    for name in ("data_contracts.md", "bronze-runbook.md"):
        members["novarota_case/" + name] = (ROOT / "docs" / name).read_bytes()
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as bundle:
        for name, content in sorted(members.items()):
            info = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            bundle.writestr(info, content)
    (output / "01_bronze_demo.ipynb").write_bytes(notebook)
    print(json.dumps({"zip": str(archive), "sha256": sha256(archive.read_bytes()).hexdigest(), "members": len(members)}, indent=2))


if __name__ == "__main__":
    main()
