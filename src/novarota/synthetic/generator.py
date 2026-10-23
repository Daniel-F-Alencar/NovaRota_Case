"""Arquivos e manifestos deterministas, sem Spark ou rede."""

from collections import defaultdict
import csv
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import random

from novarota import __version__
from novarota.contracts import SOURCES
from novarota.synthetic.scenarios import (
    BATCH_IDS, SCENARIOS, account, card, cdc, customer, fixed_scenarios, timestamp, transaction,
)


@dataclass(frozen=True)
class GeneratorConfig:
    seed: int = 42
    reference_date: date = date(2026, 6, 30)
    customers: int = 10
    transactions: int = 40

    def __post_init__(self) -> None:
        if type(self.seed) is not int or self.seed < 0:
            raise ValueError("seed deve ser inteiro nao negativo")
        if type(self.reference_date) is not date:
            raise ValueError("reference_date deve ser date")
        if type(self.customers) is not int or not 4 <= self.customers <= 100_000:
            raise ValueError("customers deve estar entre 4 e 100000")
        if type(self.transactions) is not int or not 0 <= self.transactions <= 1_000_000:
            raise ValueError("transactions deve estar entre 0 e 1000000")


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def write_once(path: Path, content: bytes) -> None:
    """Rerun identico e permitido; alteracoes exigem outro diretorio/lote."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError(f"Conteudo imutavel divergente: {path}")
        return
    with path.open("xb") as stream:
        stream.write(content)


def build_records(config: GeneratorConfig) -> dict:
    batches = fixed_scenarios(config.reference_date)
    initial, incremental = (batches[batch] for batch in BATCH_IDS[:2])
    rng = random.Random(config.seed)
    cards = []
    at = timestamp(config.reference_date, 180)
    for index in range(config.customers - 3):
        client_id = f"C{100000 + index}"
        row = customer(client_id, 100000 + index)
        income_cents = rng.randrange(180000, 1500000)
        row["renda"] = f"{income_cents // 100}.{income_cents % 100:02d}"
        initial["clientes_cdc"].append(cdc(row, client_id, at))
        for position in range(1 + (index % 2)):
            account_id = f"A{100000 + index * 2 + position}"
            initial["contas_cdc"].append(cdc(account(account_id, client_id, at), account_id, at))
            for card_position in range(1 + (index % 3 == 0 and position == 0)):
                card_id = f"K{100000 + index * 4 + position * 2 + card_position}"
                initial["cartoes_cdc"].append(cdc(card(card_id, account_id), card_id, at))
                cards.append(card_id)
    initial_count = config.transactions * 7 // 10
    for index in range(config.transactions):
        is_initial = index < initial_count
        days_ago = rng.randint(31, 179) if is_initial else rng.randint(0, 29)
        amount_cents = rng.randrange(100, 100000)
        amount = f"{amount_cents // 100}.{amount_cents % 100:02d}"
        row = transaction(f"T{1000000 + index}", rng.choice(cards), timestamp(config.reference_date, days_ago), amount,
                          canal=rng.choice(("PRESENCIAL", "APP", "WEB")))
        target = initial if is_initial else incremental
        target["transacoes"].append(row)
    return batches


def encode_records(source: str, rows: list[dict[str, str]]) -> bytes:
    contract = SOURCES[source]
    if contract.format == "json":
        return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows).encode("utf-8")
    extra = sorted({field for row in rows for field in row} - set(contract.fields))
    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=[*contract.fields, *extra], lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def generate(output: str | Path, config: GeneratorConfig) -> list[Path]:
    """Retorna os manifestos; nenhum arquivo e publicado na landing aqui."""
    output = Path(output)
    records = build_records(config)
    manifests = []
    for batch_id, sources in records.items():
        manifest = {
            "manifest_version": 1, "generator_version": __version__, "batch_id": batch_id,
            "seed": config.seed, "reference_date": config.reference_date.isoformat(),
            "parameters": {"customers": config.customers, "background_transactions": config.transactions},
            "scenarios": SCENARIOS[batch_id], "files": [],
        }
        batch_root = output / batch_id
        for source, rows in sources.items():
            version = "2" if batch_id == BATCH_IDS[3] and source == "transacoes" else "1"
            groups = defaultdict(list)
            if source == "transacoes":
                for row in rows:
                    groups[row["data_transacao"][:10]].append(row)
                if not rows:
                    groups["empty"] = []
            else:
                groups[None] = rows
            for partition, group in sorted(groups.items(), key=lambda item: str(item[0])):
                parts = [source, batch_id, f"schema_v{version}"]
                if partition is not None:
                    parts.append(f"event_date={partition}")
                extension = "json" if SOURCES[source].format == "json" else "csv"
                relative = "/".join([*parts, f"part_0001.{extension}"])
                content = encode_records(source, group)
                write_once(batch_root / "files" / relative, content)
                manifest["files"].append({"path": relative, "source": source, "schema_version": version,
                                          "format": SOURCES[source].format, "rows": len(group),
                                          "bytes": len(content), "sha256": sha256(content).hexdigest()})
        manifest_path = batch_root / "manifest.json"
        write_once(manifest_path, json_bytes(manifest))
        manifests.append(manifest_path)
    return manifests
