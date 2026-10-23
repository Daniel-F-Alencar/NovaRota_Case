"""Publica um lote completo; executar sem concorrencia com ingestao."""

from pathlib import Path

from novarota.ingestion.manifests import file_path, read_manifest, verify_files
from novarota.synthetic.generator import json_bytes, write_once


def publish_batch(manifest_path: str | Path, landing: str | Path, published: str | Path) -> dict:
    manifest_path, landing, published = Path(manifest_path), Path(landing), Path(published)
    manifest = read_manifest(manifest_path)
    source_root = manifest_path.parent / "files"
    verify_files(manifest, source_root)
    content = json_bytes(manifest)
    marker = published / (manifest["batch_id"] + ".json")
    # Preflight de todos os destinos antes de copiar qualquer arquivo.
    if marker.exists() and marker.read_bytes() != content:
        raise ValueError(f"Lote logico ja publicado com outro manifesto: {marker}")
    for entry in manifest["files"]:
        destination = file_path(landing, entry["path"])
        if destination.exists() and destination.read_bytes() != file_path(source_root, entry["path"]).read_bytes():
            raise ValueError(f"Arquivo publicado e imutavel: {destination}")
    added = 0
    for entry in manifest["files"]:
        destination = file_path(landing, entry["path"])
        existed = destination.exists()
        write_once(destination, file_path(source_root, entry["path"]).read_bytes())
        added += not existed
    # Publicacao logica finalizada somente depois de todos os arquivos verificados.
    verify_files(manifest, landing)
    write_once(marker, content)
    return {"batch_id": manifest["batch_id"], "files_added": added,
            "files_total": len(manifest["files"]), "rows": sum(e["rows"] for e in manifest["files"])}
