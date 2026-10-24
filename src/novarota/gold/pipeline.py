"""Snapshot Gold fixado por versões Silver, com MERGE e estado auditável."""

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
import json
import logging
from pathlib import Path
from uuid import uuid4

from novarota.config import identifier, logical_id
from novarota.observability.audit import AUDIT_SCHEMA, DeltaAuditWriter, audited
from novarota.silver.persistence import stamp, sync, reconcile
from novarota.gold.transformations import build_gold

LOGGER = logging.getLogger("novarota")
IMPLEMENTATION_VERSION = "gold_1"
STATE_SCHEMA = "_dataset_id STRING, run_id STRING, signature STRING, status STRING, started_at TIMESTAMP, finished_at TIMESTAMP, metrics_json STRING"
INPUTS = ("clientes_scd2", "contas_scd2", "cartoes_scd2", "transacoes_atual", "eventos_risco", "estornos")
KEYS = {
    "gold_fato_transacao": ("id_transacao",),
    "gold_dim_cliente": ("version_id",),
    "gold_dim_conta": ("version_id",),
    "gold_dim_cartao": ("version_id",),
    "gold_dim_estabelecimento": ("id_estabelecimento",),
    "gold_cliente_mes": ("id_cliente", "data_mes"),
    "gold_indicadores_risco": ("id_cliente", "data_mes"),
    "gold_features_cliente": ("id_cliente", "data_referencia"),
}


@dataclass(frozen=True)
class GoldConfig:
    catalog: str
    bronze_schema: str
    silver_schema: str
    gold_schema: str
    ops_schema: str
    volume: str
    feature_date: date
    run_id: str
    rule_version: str = "gold_v1"
    batch_id: str = "gold_snapshot"

    def __post_init__(self):
        for value in (self.catalog, self.bronze_schema, self.silver_schema, self.gold_schema, self.ops_schema, self.volume):
            identifier(value)
        if len({self.bronze_schema, self.silver_schema, self.gold_schema, self.ops_schema}) != 4:
            raise ValueError("Schemas Bronze, Silver, Gold e ops devem ser distintos")
        logical_id(self.run_id)
        logical_id(self.rule_version)
        logical_id(self.batch_id)
        if type(self.feature_date) is not date:
            raise ValueError("feature_date deve ser uma data")
        if self.feature_date > datetime.now(timezone.utc).date():
            raise ValueError("feature_date nao pode estar no futuro UTC")

    @property
    def dataset_key(self):
        return f"{self.catalog}.{self.bronze_schema}.{self.silver_schema}"

    @property
    def volume_path(self):
        return f"/Volumes/{self.catalog}/{self.ops_schema}/{self.volume}"

    def silver_table(self, name):
        return f"{self.catalog}.{self.silver_schema}.{identifier(name)}"

    def gold_table(self, name):
        return f"{self.catalog}.{self.gold_schema}.{identifier(name)}"


def _write_once_json(path, value):
    content = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=str)
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise ValueError(f"Inventario Gold imutavel divergente: {path}")
    else:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(content)


def setup_gold(spark, config):
    spark.conf.set("spark.sql.session.timeZone", "UTC")
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {config.catalog}.{config.gold_schema}")
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {config.catalog}.{config.ops_schema}")
    spark.sql(f"CREATE VOLUME IF NOT EXISTS {config.catalog}.{config.ops_schema}.{config.volume}")
    spark.sql(f"CREATE TABLE IF NOT EXISTS {config.catalog}.{config.ops_schema}.pipeline_events ({AUDIT_SCHEMA}) USING DELTA")
    spark.sql(f"CREATE TABLE IF NOT EXISTS {config.catalog}.{config.ops_schema}.gold_execution_state ({STATE_SCHEMA}) USING DELTA")


def _one_state(spark, config, name):
    from pyspark.sql import functions as F

    rows = (spark.table(f"{config.catalog}.{config.ops_schema}.{name}")
            .where(F.col("_dataset_id") == config.dataset_key).limit(2).collect())
    if len(rows) > 1:
        raise ValueError(f"Estado duplicado em {name}; interromper e reconciliar")
    return rows[0].asDict() if rows else None


def _write_state(spark, config, signature, status, started_at, result=None):
    view = "nr_gold_state_" + uuid4().hex
    now = datetime.now(timezone.utc)
    payload = (config.dataset_key, config.run_id, signature, status, started_at,
               now if status != "STARTED" else None, json.dumps(result or {}, default=str, sort_keys=True))
    spark.createDataFrame([payload], STATE_SCHEMA).createOrReplaceTempView(view)
    try:
        spark.sql(f"""MERGE INTO {config.catalog}.{config.ops_schema}.gold_execution_state t
            USING {view} s ON t._dataset_id = s._dataset_id
            WHEN MATCHED THEN UPDATE SET * WHEN NOT MATCHED THEN INSERT *""")
    finally:
        spark.catalog.dropTempView(view)


def _silver_succeeded(spark, config):
    state = _one_state(spark, config, "silver_execution_state")
    if not state or state["status"] != "SUCCEEDED":
        raise ValueError("Silver deve estar SUCCEEDED antes da Gold")
    finished_at = state["finished_at"]
    if finished_at is None or finished_at.date() > config.feature_date:
        raise ValueError("data de corte anterior a publicacao do snapshot Silver")
    return state


def _snapshot(spark, config, root, signature):
    path = root / "input.json"
    if path.exists():
        metadata = json.loads(path.read_text(encoding="utf-8"))
        if metadata["signature"] != signature:
            raise ValueError("run_id Gold reutilizado com parametros ou implementacao diferentes")
        return metadata
    silver = _silver_succeeded(spark, config)
    versions = {}
    for name in INPUTS:
        table = config.silver_table(name)
        detail = spark.sql(f"DESCRIBE DETAIL {table}").first().asDict()
        version = spark.sql(f"DESCRIBE HISTORY {table} LIMIT 1").first()["version"]
        versions[name] = {"table": table, "table_id": detail["id"], "version": int(version)}
    again = _silver_succeeded(spark, config)
    if again["run_id"] != silver["run_id"]:
        raise ValueError("Silver mudou durante a captura Gold; repetir com novo run_id")
    metadata = {"signature": signature, "run_id": config.run_id, "dataset": config.dataset_key,
                "implementation": IMPLEMENTATION_VERSION, "silver_run_id": silver["run_id"],
                "silver_finished_at": silver["finished_at"].isoformat(), "feature_date": config.feature_date.isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat(), "inputs": versions}
    _write_once_json(path, metadata)
    return metadata


def _read_inputs(spark, config, metadata):
    from pyspark.sql import functions as F

    if set(metadata["inputs"]) != set(INPUTS) or metadata["dataset"] != config.dataset_key:
        raise ValueError("Inventario Gold incompleto ou de outro dataset")
    frames = {}
    for name in INPUTS:
        item = metadata["inputs"][name]
        table = config.silver_table(name)
        if item["table"] != table or type(item["version"]) is not int or item["version"] < 0:
            raise ValueError("Tabela/versao Silver invalida no inventario Gold")
        if spark.sql(f"DESCRIBE DETAIL {table}").first()["id"] != item["table_id"]:
            raise ValueError(f"Tabela Silver recriada apos snapshot Gold: {name}")
        frames[name] = spark.sql(f"SELECT * FROM {table} VERSION AS OF {item['version']}").where(
            F.col("_dataset_id") == config.dataset_key)
    return frames


def _stage_outputs(spark, config, root, metadata):
    from pyspark.sql import functions as F

    inputs = _read_inputs(spark, config, metadata)
    outputs = build_gold(inputs, config.feature_date)
    fact = outputs["gold_fato_transacao"]
    if fact.count() != inputs["transacoes_atual"].count():
        raise ValueError("Fato Gold nao reconcilia com transacoes atuais Silver")
    if fact.where((F.col("elegivel_indicadores") & (F.col("valor_liquido_brl") < 0)) |
                  (~F.col("elegivel_indicadores") & F.col("valor_liquido_brl").isNotNull())).limit(1).count():
        raise ValueError("Valor liquido Gold invalido ou publicado para transacao inelegivel")
    for name, frame in outputs.items():
        stamp(frame, config).write.mode("overwrite").parquet(str(root / "output" / name))
    _write_once_json(root / "ready.json", {"signature": metadata["signature"], "tables": list(outputs)})


def run_gold(spark, config: GoldConfig):
    """Uma tentativa concorrente por dataset; retry reutiliza run_id e versões Silver."""
    if config.rule_version != "gold_v1":
        raise ValueError("Esta implementacao suporta somente rule_version=gold_v1")
    setup_gold(spark, config)
    signature = sha256(json.dumps({**asdict(config), "implementation": IMPLEMENTATION_VERSION},
                                  default=str, sort_keys=True).encode()).hexdigest()
    previous = _one_state(spark, config, "gold_execution_state")
    if previous and previous["run_id"] == config.run_id:
        if previous["signature"] != signature:
            raise ValueError("run_id Gold registrado com outros parametros")
        if previous["status"] == "SUCCEEDED":
            return json.loads(previous["metrics_json"])
    elif previous and previous["status"] != "SUCCEEDED":
        raise ValueError(f"Tentativa Gold incompleta {previous['run_id']}; retomar esse run_id")
    root = Path(config.volume_path, "gold_staging", config.gold_schema, config.run_id)
    root.mkdir(parents=True, exist_ok=True)
    if previous and previous["run_id"] != config.run_id and (root / "input.json").exists():
        raise ValueError("Tentativa Gold antiga substituida; usar novo run_id")
    started_at = previous["started_at"] if previous and previous["run_id"] == config.run_id else datetime.now(timezone.utc)
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    _write_state(spark, config, signature, "STARTED", started_at)
    writer = DeltaAuditWriter(spark, config)
    try:
        with audited(writer, "gold_pipeline") as audit_metrics:
            metadata = _snapshot(spark, config, root, signature)
            silver = _silver_succeeded(spark, config)
            if silver["run_id"] != metadata["silver_run_id"]:
                raise ValueError("Silver atual difere do snapshot Gold fixado")
            ready = root / "ready.json"
            if not ready.exists():
                _stage_outputs(spark, config, root, metadata)
            staged = json.loads(ready.read_text(encoding="utf-8"))
            if staged["signature"] != signature or set(staged["tables"]) != set(KEYS):
                raise ValueError("Staging Gold nao corresponde ao contrato da tentativa")
            audit_metrics.update({"stage": "gold", "dataset": config.dataset_key,
                                  "silver_run_id": metadata["silver_run_id"],
                                  "feature_date": config.feature_date.isoformat(), "inputs": metadata["inputs"]})
            rows_by_table = {}
            for name in staged["tables"]:
                frame = spark.read.parquet(str(root / "output" / name))
                table = config.gold_table(name)
                with audited(writer, "gold:" + name) as table_metrics:
                    sync(spark, frame, table, KEYS[name], config.dataset_key)
                    count = reconcile(spark, frame, table, KEYS[name], config)
                    rows_by_table[name] = count
                    table_metrics.update({"table": table, "rows": count, "dataset": config.dataset_key})
            silver = _silver_succeeded(spark, config)
            if silver["run_id"] != metadata["silver_run_id"]:
                raise ValueError("Silver mudou durante a publicacao Gold")
            result = {"status": "GOLD_PIPELINE_SUCCEEDED", "run_id": config.run_id,
                      "silver_run_id": metadata["silver_run_id"], "catalog": config.catalog,
                      "silver_schema": config.silver_schema, "gold_schema": config.gold_schema,
                      "rule_version": config.rule_version, "feature_date": config.feature_date.isoformat(),
                      "rows_by_table": rows_by_table, "input_versions": metadata["inputs"],
                      "finished_at": datetime.now(timezone.utc).isoformat()}
            audit_metrics["rows_by_table"] = rows_by_table
        _write_state(spark, config, signature, "SUCCEEDED", started_at, result)
        return result
    except Exception as error:
        try:
            _write_state(spark, config, signature, "FAILED", started_at, {"error": f"{type(error).__name__}: {error}"[:4000]})
        except Exception:
            LOGGER.exception("Nao foi possivel atualizar estado Gold FAILED; preservar excecao original")
        raise
