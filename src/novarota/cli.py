"""Comandos locais do case; comandos novos acompanham a implementacao."""

import argparse
from dataclasses import asdict
import json

from novarota import __version__
from novarota.config import PipelineConfig


def main() -> None:
    parser = argparse.ArgumentParser(prog="novarota")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    config = commands.add_parser("config", help="Validar e exibir configuracao resolvida")
    config.add_argument("--file", required=True)
    args = parser.parse_args()
    try:
        settings = PipelineConfig.load(args.file)
    except (ValueError, TypeError, OSError) as error:
        parser.error(str(error))
    result = {**asdict(settings), "volume_path": settings.volume_path}
    print(json.dumps(result, default=str, ensure_ascii=False, indent=2))
