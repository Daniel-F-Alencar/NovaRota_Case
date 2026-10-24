"""Tentativas com snapshot fixo, staging e retomada sem transacao multitabular."""

from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import logging
from pathlib import Path
from uuid import uuid4

from novarota.config import PipelineConfig
from novarota.contracts import SOURCES
from novarota.observability.audit import AUDIT_SCHEMA, DeltaAuditWriter, audited
from novarota.quality.contracts import TIMESTAMPS
from novarota.silver.persistence import literal, stamp, sync, reconcile
from novarota.silver.transformations import build_silver

LOGGER = logging.getLogger("novarota")
IMPLEMENTATION_VERSION = "silver_1"
STATE_SCHEMA = "_dataset_id STRING, run_id STRING, signature STRING, status STRING, started_at TIMESTAMP, finished_at TIMESTAMP, metrics_json STRING"
KEYS = {
    "clientes_eventos": ("event_key",), "contas_eventos": ("event_key",), "cartoes_eventos": ("event_key",),
    "clientes_scd2": ("version_id",), "contas_scd2": ("version_id",), "cartoes_scd2": ("version_id",),
    "transacoes_versoes": ("event_key",), "transacoes_atual": ("id_transacao",),
    "eventos_risco": ("event_key",), "estornos": ("event_key",),
    "silver_classificacoes": ("source", "occurrence_id"),
    "silver_avaliacoes": ("evaluation_run_id", "source", "occurrence_id"),
}


def setup_silver(spark, config: PipelineConfig):
    spark.conf.set("spark.sql.session.timeZone", "UTC")
    for schema in (config.silver_schema, config.ops_schema):
        spark.sql(f"CREATE SCHEMA IF NOT EXISTS {config.catalog}.{schema}")
    spark.sql(f"CREATE VOLUME IF NOT EXISTS {config.catalog}.{config.ops_schema}.{config.volume}")
    spark.sql(f"CREATE TABLE IF NOT EXISTS {config.catalog}.{config.ops_schema}.pipeline_events ({AUDIT_SCHEMA}) USING DELTA")
    spark.sql(f"CREATE TABLE IF NOT EXISTS {config.catalog}.{config.ops_schema}.silver_execution_state ({STATE_SCHEMA}) USING DELTA")


def _state(spark, config):
    from pyspark.sql import functions as F
    rows = spark.table(f"{config.catalog}.{config.ops_schema}.silver_execution_state").where(F.col("_dataset_id") == config.dataset_key).limit(2).collect()
    if len(rows) > 1:
        raise ValueError("Estado operacional Silver duplicado; interromper e reconciliar")
    return rows[0].asDict() if rows else None


def _write_state(spark, config, signature, status, started_at, result=None):
    view = "nr_silver_state_" + uuid4().hex
    now = datetime.now(timezone.utc)
    payload = (config.dataset_key, config.run_id, signature, status, started_at,
               now if status != "STARTED" else None, json.dumps(result or {}, default=str, sort_keys=True))
    spark.createDataFrame([payload], STATE_SCHEMA).createOrReplaceTempView(view)
    try:
        spark.sql(f"""MERGE INTO {config.catalog}.{config.ops_schema}.silver_execution_state t
            USING {view} s ON t._dataset_id = s._dataset_id
            WHEN MATCHED THEN UPDATE SET * WHEN NOT MATCHED THEN INSERT *""")
    finally:
        spark.catalog.dropTempView(view)


def _write_once_json(path, value):
    content = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=str)
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise ValueError(f"Manifesto de tentativa imutavel divergente: {path}")
    else:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(content)


def _destination(config, name):
    return f"{config.catalog}.{config.ops_schema}.{name}" if name.startswith("silver_") else config.silver_table(name)


def _snapshot(spark, config, root, signature):
    path = root / "input.json"
    if path.exists():
        metadata = json.loads(path.read_text(encoding="utf-8"))
        if metadata["signature"] != signature:
            raise ValueError("run_id reutilizado com parametros ou implementacao diferentes")
        return metadata
    versions = {}
    for source in SOURCES:
        table = config.table(source)
        detail = spark.sql(f"DESCRIBE DETAIL {table}").first().asDict()
        version = spark.sql(f"DESCRIBE HISTORY {table} LIMIT 1").first()["version"]
        versions[source] = {"table": table, "table_id": detail["id"], "version": int(version)}
    metadata = {"signature": signature, "run_id": config.run_id, "dataset": config.dataset_key,
                "implementation": IMPLEMENTATION_VERSION, "created_at": datetime.now(timezone.utc).isoformat(), "inputs": versions}
    _write_once_json(path, metadata)
    return metadata


def _read_inputs(spark, metadata, config):
    frames = {}
    if set(metadata["inputs"]) != set(SOURCES):
        raise ValueError("Inventario da tentativa deve conter as seis fontes")
    for source in SOURCES:
        item = metadata["inputs"][source]
        table = config.table(source)
        if item["table"] != table or type(item["version"]) is not int or item["version"] < 0:
            raise ValueError("Tabela/versao invalida no inventario da tentativa")
        if spark.sql(f"DESCRIBE DETAIL {table}").first()["id"] != item["table_id"]:
            raise ValueError(f"Tabela Bronze recriada desde o inicio da tentativa: {source}")
        frames[source] = spark.sql(f"SELECT * FROM {table} VERSION AS OF {item['version']}")
    return frames


def _metrics(evaluations, inputs, config):
    from pyspark.sql import functions as F
    summary = evaluations.groupBy("source").agg(F.sum("multiplicidade").alias("input_rows"),
        F.sum("qt_aprovadas").alias("approved"), F.sum("qt_duplicatas").alias("duplicates"), F.sum("qt_quarentena").alias("quarantine"))
    result = {row["source"]: row.asDict() for row in summary.collect()}
    for source, frame in inputs.items():
        count = frame.count()
        item = result.setdefault(source, {"source": source, "input_rows": 0, "approved": 0, "duplicates": 0, "quarantine": 0})
        if count != item["input_rows"] or count != item["approved"] + item["duplicates"] + item["quarantine"]:
            raise ValueError(f"Classificacoes nao reconciliam com a Bronze: {source}")
        if config.mode == "reprocess":
            at = TIMESTAMPS[source]
            item["rows_in_requested_dates"] = frame.where(
                F.expr(f"try_cast(substr({at}, 1, 10) AS DATE)").between(config.date_from, config.date_to)).count()
    if not sum(item["input_rows"] for item in result.values()):
        raise ValueError("Bronze vazia: nao sincronizar destinos Silver sem dados")
    return result


def run_silver(spark, config: PipelineConfig):
    """Uma tentativa concorrente por dataset. Retry deve reutilizar o mesmo run_id."""
    if config.rule_version != "silver_v1":
        raise ValueError("Esta implementacao suporta somente rule_version=silver_v1")
    setup_silver(spark, config)
    parameters = {**asdict(config), "implementation": IMPLEMENTATION_VERSION}
    signature = sha256(json.dumps(parameters, default=str, sort_keys=True).encode()).hexdigest()
    previous = _state(spark, config)
    if previous and previous["run_id"] == config.run_id:
        if previous["signature"] != signature:
            raise ValueError("run_id ja registrado com outros parametros")
        if previous["status"] == "SUCCEEDED":
            return json.loads(previous["metrics_json"])
    elif previous and previous["status"] != "SUCCEEDED":
        raise ValueError(f"Tentativa incompleta {previous['run_id']}; retomar esse run_id antes de iniciar outra")
    root = Path(config.volume_path, "silver_staging", config.silver_schema, config.run_id)
    root.mkdir(parents=True, exist_ok=True)
    # Impede que um run_id antigo volte a aplicar snapshot sobre um resultado posterior.
    if previous and previous["run_id"] != config.run_id and (root / "input.json").exists():
        raise ValueError("Tentativa antiga substituida por outra execucao; use novo run_id")
    started_at = previous["started_at"] if previous and previous["run_id"] == config.run_id else datetime.now(timezone.utc)
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    _write_state(spark, config, signature, "STARTED", started_at)
    writer = DeltaAuditWriter(spark, config)
    try:
        with audited(writer, "silver_pipeline") as audit_metrics:
            metadata = _snapshot(spark, config, root, signature)
            inputs = _read_inputs(spark, metadata, config)
            binding_name = sha256(config.dataset_key.encode()).hexdigest() + "_binding.json"
            _write_once_json(root.parent / binding_name, {
                source: {"table": item["table"], "table_id": item["table_id"]}
                for source, item in metadata["inputs"].items()
            })
            ready = root / "ready.json"
            if not ready.exists():
                def materialize(name, frame):
                    path = str(root / "work" / name)
                    frame.write.mode("overwrite").parquet(path)
                    return spark.read.parquet(path)
                outputs = build_silver(inputs, config, materialize)
                quality = _metrics(outputs["silver_classificacoes"], inputs, config)
                for name, frame in outputs.items():
                    stamp(frame, config).write.mode("overwrite").parquet(str(root / "output" / name))
                _write_once_json(ready, {"signature": signature, "tables": list(outputs), "quality": quality})
            staged = json.loads(ready.read_text(encoding="utf-8"))
            if staged["signature"] != signature or set(staged["tables"]) != set(KEYS):
                raise ValueError("Staging nao corresponde ao contrato desta tentativa")
            audit_metrics.update({"stage": "silver", "dataset": config.dataset_key, "scope": "FULL_DATASET",
                                  "mode": config.mode, "date_from": str(config.date_from), "date_to": str(config.date_to),
                                  "rule_version": config.rule_version, "quality": staged["quality"], "inputs": metadata["inputs"]})
            rows_by_table = {}
            for name in staged["tables"]:
                frame = spark.read.parquet(str(root / "output" / name))
                table = _destination(config, name)
                with audited(writer, "silver:" + name) as table_metrics:
                    sync(spark, frame, table, KEYS[name], config.dataset_key, delete_missing=name != "silver_avaliacoes")
                    count = reconcile(spark, frame, table, KEYS[name], config, history=name == "silver_avaliacoes")
                    rows_by_table[name] = count
                    table_metrics.update({"table": table, "rows": count, "rule_version": config.rule_version, "dataset": config.dataset_key})
            spark.sql(f"""CREATE OR REPLACE VIEW {config.catalog}.{config.ops_schema}.silver_quarentena AS
                SELECT * FROM {config.catalog}.{config.ops_schema}.silver_classificacoes WHERE qt_quarentena > 0""")
            result = {"status": "SILVER_PIPELINE_SUCCEEDED", "run_id": config.run_id, "catalog": config.catalog,
                      "bronze_schema": config.bronze_schema, "silver_schema": config.silver_schema,
                      "rule_version": config.rule_version, "scope": "FULL_DATASET", "mode": config.mode,
                      "quality_by_source": staged["quality"], "rows_by_table": rows_by_table,
                      "input_versions": metadata["inputs"], "finished_at": datetime.now(timezone.utc).isoformat()}
            audit_metrics["rows_by_table"] = rows_by_table
        _write_state(spark, config, signature, "SUCCEEDED", started_at, result)
        return result
    except Exception as error:
        try:
            _write_state(spark, config, signature, "FAILED", started_at, {"error": f"{type(error).__name__}: {error}"[:4000]})
        except Exception:
            LOGGER.exception("Nao foi possivel atualizar estado FAILED; preservar excecao original")
        raise
