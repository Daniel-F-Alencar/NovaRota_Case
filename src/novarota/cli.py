"""Comandos locais do case; comandos novos acompanham a implementacao."""

import argparse
from dataclasses import asdict
from datetime import date
import json

from novarota import __version__
from novarota.config import PipelineConfig
from novarota.ingestion.manifests import read_manifest, verify_files
from novarota.ingestion.publisher import publish_batch
from novarota.synthetic.generator import GeneratorConfig, generate
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(prog="novarota")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    config = commands.add_parser("config", help="Validar e exibir configuracao resolvida")
    config.add_argument("--file", required=True)
    generator = commands.add_parser("generate", help="Gerar quatro lotes fora da landing")
    generator.add_argument("--output", required=True)
    generator.add_argument("--profile", choices=("sample", "demo"), default="sample")
    generator.add_argument("--reference-date", default="2026-06-30")
    generator.add_argument("--seed", type=int, default=42)
    generator.add_argument("--customers", type=int)
    generator.add_argument("--transactions", type=int)
    verify = commands.add_parser("verify", help="Reconciliar arquivos gerados com manifesto")
    verify.add_argument("--manifest", required=True)
    publish = commands.add_parser("publish", help="Publicar lote imutavel (sem ingestao concorrente)")
    publish.add_argument("--manifest", required=True)
    publish.add_argument("--landing", required=True)
    publish.add_argument("--published", required=True)
    args = parser.parse_args()
    try:
        if args.command == "config":
            settings = PipelineConfig.load(args.file)
            result = {**asdict(settings), "volume_path": settings.volume_path}
        elif args.command == "generate":
            customers, transactions = (10, 40) if args.profile == "sample" else (100, 10000)
            settings = GeneratorConfig(seed=args.seed, reference_date=date.fromisoformat(args.reference_date),
                                       customers=customers if args.customers is None else args.customers,
                                       transactions=transactions if args.transactions is None else args.transactions)
            result = {"manifests": [str(path) for path in generate(args.output, settings)]}
        elif args.command == "verify":
            manifest_path = Path(args.manifest)
            manifest = read_manifest(manifest_path)
            verify_files(manifest, manifest_path.parent / "files")
            result = {"batch_id": manifest["batch_id"], "status": "VERIFIED"}
        else:
            result = publish_batch(args.manifest, args.landing, args.published)
    except (ValueError, TypeError, OSError) as error:
        parser.error(str(error))
    print(json.dumps(result, default=str, ensure_ascii=False, indent=2))
