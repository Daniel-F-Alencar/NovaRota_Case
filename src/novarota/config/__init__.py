"""Configuracao reutilizavel, sem dependencia de Spark ou segredos de workspace."""

from dataclasses import dataclass, field, fields
from datetime import date
import json
from pathlib import Path
import re
from uuid import uuid4


def identifier(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"Identificador invalido: {value!r}")
    return value


def logical_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", value):
        raise ValueError(f"Identificacao invalida: {value!r}")
    return value


@dataclass(frozen=True)
class PipelineConfig:
    catalog: str
    reference_date: date
    environment: str = "dev"
    bronze_schema: str = "novarota_bronze"
    ops_schema: str = "novarota_ops"
    volume: str = "case_files"
    seed: int = 42
    mode: str = "incremental"
    batch_id: str = "batch_001_initial"
    run_id: str = field(default_factory=lambda: uuid4().hex)
    date_from: date | None = None
    date_to: date | None = None
    silver_schema: str = "novarota_silver"
    rule_version: str = "silver_v1"

    def __post_init__(self) -> None:
        for name in ("catalog", "bronze_schema", "ops_schema", "volume", "silver_schema"):
            identifier(getattr(self, name))
        logical_id(self.rule_version)
        if self.silver_schema in {self.bronze_schema, self.ops_schema}:
            raise ValueError("silver_schema deve ser separado de bronze_schema e ops_schema")
        if self.environment not in {"dev", "test", "prod"}:
            raise ValueError("environment deve ser dev, test ou prod")
        if self.mode not in {"incremental", "reprocess"}:
            raise ValueError("mode deve ser incremental ou reprocess")
        if type(self.seed) is not int or self.seed < 0:
            raise ValueError("seed deve ser inteiro nao negativo")
        logical_id(self.batch_id)
        logical_id(self.run_id)
        if type(self.reference_date) is not date:
            raise ValueError("reference_date deve ser uma data")
        if (self.date_from is None) != (self.date_to is None):
            raise ValueError("date_from e date_to devem ser informadas juntas")
        if self.date_from is not None:
            if type(self.date_from) is not date or type(self.date_to) is not date:
                raise ValueError("Intervalo deve conter datas")
            if self.date_from > self.date_to:
                raise ValueError("Intervalo de datas invertido")
        if self.mode == "reprocess" and self.date_from is None:
            raise ValueError("reprocess exige intervalo de datas")

    @property
    def volume_path(self) -> str:
        return f"/Volumes/{self.catalog}/{self.ops_schema}/{self.volume}"

    def table(self, source: str) -> str:
        return f"{self.catalog}.{self.bronze_schema}.bronze_{identifier(source)}"

    @property
    def dataset_key(self) -> str:
        return f"{self.catalog}.{self.bronze_schema}.{self.silver_schema}"

    def silver_table(self, name: str) -> str:
        return f"{self.catalog}.{self.silver_schema}.{identifier(name)}"

    @classmethod
    def from_dict(cls, values: dict) -> "PipelineConfig":
        values = dict(values)
        unknown = set(values) - {item.name for item in fields(cls)}
        if unknown:
            raise ValueError(f"Parametros desconhecidos: {sorted(unknown)}")
        for name in ("catalog", "reference_date"):
            if name not in values:
                raise ValueError(f"Parametro obrigatorio ausente: {name}")
        for name in ("reference_date", "date_from", "date_to"):
            if isinstance(values.get(name), str):
                values[name] = date.fromisoformat(values[name])
        return cls(**values)

    @classmethod
    def load(cls, path: str | Path) -> "PipelineConfig":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
