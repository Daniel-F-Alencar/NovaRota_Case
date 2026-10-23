"""Comparacoes puras, usadas antes e depois das escritas distribuidas."""

from collections import Counter
from pathlib import Path

from novarota.ingestion.manifests import decode_records, file_path, validate_manifest, verify_files
from novarota.ingestion.hashing import row_hash
from novarota.contracts import SOURCES


def expected_counts(manifests: list[dict], source: str) -> dict[str, int]:
    return {entry["path"]: entry["rows"] for manifest in manifests for entry in manifest["files"] if entry["source"] == source}


def relative_origin(origin: str, paths: set[str]) -> str:
    matches = [path for path in paths if origin == path or origin.endswith("/" + path)]
    if len(matches) != 1:
        raise ValueError(f"Origem sem correspondencia unica no manifesto: {origin}")
    return matches[0]


def check_counts(actual: dict[str, int], expected: dict[str, int], allow_missing: bool = False) -> bool:
    if set(actual) - set(expected):
        raise ValueError("Bronze possui origens ausentes dos manifestos publicados")
    for path, count in actual.items():
        if count > expected[path]:
            raise ValueError(f"Bronze possui duplicacao/excesso em {path}: {count} > {expected[path]}")
    equal = all(actual.get(path, 0) == count for path, count in expected.items())
    if not equal and not allow_missing:
        raise ValueError("Contagens Bronze divergem dos manifestos publicados")
    return equal


def verify_landing(manifests: list[dict], landing: str | Path) -> None:
    landing = Path(landing)
    seen = set()
    batches = set()
    for manifest in manifests:
        validate_manifest(manifest)
        if manifest["batch_id"] in batches:
            raise ValueError("Manifestos publicados repetem um lote")
        batches.add(manifest["batch_id"])
        verify_files(manifest, landing)
        for entry in manifest["files"]:
            if entry["path"] in seen:
                raise ValueError("Arquivo declarado em mais de um manifesto")
            seen.add(entry["path"])
    found = {path.relative_to(landing).as_posix() for path in landing.rglob("*") if path.is_file()}
    if found != seen:
        raise ValueError("Landing possui arquivos nao publicados ou ausentes; concluir publicacao antes de ingerir")


def expected_hashes(manifests: list[dict], landing: str | Path, source: str) -> Counter:
    result = Counter()
    for manifest in manifests:
        for entry in manifest["files"]:
            if entry["source"] == source:
                content = file_path(Path(landing), entry["path"]).read_bytes()
                for row in decode_records(entry, content):
                    result[(entry["path"], row_hash(row, SOURCES[source]))] += 1
    return result
