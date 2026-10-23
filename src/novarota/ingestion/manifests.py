"""Validacao estrutural; regras de negocio permanecem fora da Bronze."""

import csv
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path, PurePosixPath
import re

from novarota.config import logical_id
from novarota.contracts import SOURCES


def _relative_path(relative: str) -> PurePosixPath:
    if not isinstance(relative, str) or not re.fullmatch(r"[A-Za-z0-9_./=-]+", relative):
        raise ValueError(f"Caminho de manifesto invalido: {relative!r}")
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or pure.as_posix() != relative:
        raise ValueError(f"Caminho fora do contrato: {relative}")
    return pure


def file_path(root: Path, relative: str) -> Path:
    """Rejeita traversal, caminhos absolutos, links para fora e ambiguidades."""
    pure = _relative_path(relative)
    result = root.joinpath(*pure.parts)
    if not result.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Caminho escapa da raiz: {relative}")
    return result


def validate_manifest(manifest: dict) -> dict:
    if not isinstance(manifest, dict) or manifest.get("manifest_version") != 1:
        raise ValueError("Versao de manifesto nao suportada")
    batch_id = logical_id(manifest.get("batch_id"))
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Manifesto deve declarar arquivos")
    paths = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Entrada de manifesto deve ser um objeto")
        source = entry.get("source")
        if not isinstance(source, str) or source not in SOURCES:
            raise ValueError(f"Fonte desconhecida: {source}")
        version = entry.get("schema_version")
        if not isinstance(version, str) or not re.fullmatch(r"[1-9][0-9]*", version):
            raise ValueError("schema_version deve ser uma string numerica positiva")
        path = entry.get("path")
        if not isinstance(path, str):
            raise ValueError("path deve ser string")
        _relative_path(path)
        parts = PurePosixPath(path).parts
        if len(parts) < 4 or parts[:3] != (source, batch_id, f"schema_v{version}"):
            raise ValueError(f"Caminho nao corresponde a fonte/lote/versao: {path}")
        expected_format = SOURCES[source].format
        if entry.get("format") != expected_format or not path.endswith("." + expected_format):
            raise ValueError(f"Formato inconsistente: {path}")
        if path in paths:
            raise ValueError(f"Arquivo repetido no manifesto: {path}")
        paths.add(path)
        for name in ("rows", "bytes"):
            if type(entry.get(name)) is not int or entry[name] < 0:
                raise ValueError(f"{name} deve ser inteiro nao negativo")
        if not isinstance(entry.get("sha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", entry["sha256"]):
            raise ValueError("Hash de arquivo invalido")
    return manifest


def read_manifest(path: str | Path) -> dict:
    return validate_manifest(json.loads(Path(path).read_text(encoding="utf-8")))


def decode_records(entry: dict, content: bytes) -> list[dict]:
    text = content.decode("utf-8")
    if entry["format"] == "json":
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        reader = csv.DictReader(StringIO(text, newline=""))
        headers = reader.fieldnames
        if headers is None or len(headers) != len(set(headers)):
            raise ValueError("CSV sem cabecalho ou com colunas repetidas")
        rows = list(reader)
    for row in rows:
        if not isinstance(row, dict) or None in row or any(not isinstance(k, str) or (v is not None and not isinstance(v, str)) for k, v in row.items()):
            raise ValueError("O contrato sintetico exige objetos planos com valores lexicais")
    return rows


def verify_files(manifest: dict, root: Path) -> None:
    validate_manifest(manifest)
    for entry in manifest["files"]:
        content = file_path(root, entry["path"]).read_bytes()
        if len(content) != entry["bytes"] or sha256(content).hexdigest() != entry["sha256"]:
            raise ValueError(f"Hash/tamanho divergente: {entry['path']}")
        if len(decode_records(entry, content)) != entry["rows"]:
            raise ValueError(f"Contagem divergente: {entry['path']}")


def published_manifests(root: str | Path) -> list[dict]:
    return [read_manifest(path) for path in sorted(Path(root).glob("*.json"))]
