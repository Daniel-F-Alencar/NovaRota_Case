# Databricks notebook source
# MAGIC %md
# MAGIC # NovaRota: demonstracao Bronze das seis fontes
# MAGIC Importar o ZIP gerado com o pacote `novarota` ao lado deste notebook.
# MAGIC Executar em Serverless. `dataset_id` separa schemas, Volume, dados e checkpoints.
# MAGIC `sample` gera 40 transacoes de fundo mais cenarios fixos; `demo` gera 10 mil mais cenarios.
# MAGIC Para evidenciar carga inicial de novo, usar outro dataset_id. Reexecutar o mesmo preserva estado.

# COMMAND ----------
import importlib.util
import json
import logging
import sys
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("dataset_id", "case01")
dbutils.widgets.dropdown("profile", "sample", ["sample", "demo"])
dbutils.widgets.text("seed", "42")
dbutils.widgets.text("reference_date", "2026-06-30")
dbutils.widgets.text("project_root", "")

# Databricks adiciona o diretorio do notebook ao sys.path. O parametro opcional
# permite explicitar a pasta absoluta de workspace sem depender de os.getcwd().
project_root = dbutils.widgets.get("project_root").strip()
if project_root:
    if not project_root.startswith("/Workspace/"):
        raise ValueError("project_root deve ser caminho absoluto iniciado em /Workspace/")
    sys.path.insert(0, project_root)
if importlib.util.find_spec("novarota") is None:
    raise ImportError("Importe o ZIP completo; novarota/ deve ficar ao lado do notebook. Se necessario, informe a pasta absoluta em project_root.")

from novarota.config import PipelineConfig, identifier
from novarota.ingestion.bronze import BatchNotPublishedError, run_bronze, setup_workspace, verify_payload_hashes
from novarota.ingestion.publisher import publish_batch
from novarota.ingestion.runtime_checks import verify_transformations
from novarota.synthetic.generator import GeneratorConfig, generate
from novarota.synthetic.scenarios import BATCH_IDS

logging.basicConfig(level=logging.INFO, format="%(message)s")
logging.getLogger("novarota").setLevel(logging.INFO)
dataset_id = identifier(dbutils.widgets.get("dataset_id"))
profile = dbutils.widgets.get("profile")
config = PipelineConfig(
    catalog=dbutils.widgets.get("catalog"),
    bronze_schema=f"novarota_{dataset_id}_bronze",
    ops_schema="novarota_ops",
    volume=f"{dataset_id}_files",
    reference_date=date.fromisoformat(dbutils.widgets.get("reference_date")),
    seed=int(dbutils.widgets.get("seed")),
)
setup_workspace(spark, config)
print(json.dumps({"started_at": datetime.now(timezone.utc).isoformat(), "catalog": config.catalog,
                  "bronze_schema": config.bronze_schema, "volume": config.volume_path, "profile": profile}))

# COMMAND ----------
# Verificacao real das expressoes Spark e hash contra um oracle Python.
print(json.dumps(verify_transformations(spark, config)))

# COMMAND ----------
customers, transactions = (10, 40) if profile == "sample" else (100, 10000)
generation = GeneratorConfig(seed=config.seed, reference_date=config.reference_date,
                             customers=customers, transactions=transactions)
generation_root = Path(config.volume_path, "generated", f"v1_seed{config.seed}_{profile}_{config.reference_date.isoformat()}")
manifest_paths = generate(generation_root, generation)
print(json.dumps({"generated_manifests": [str(path) for path in manifest_paths]}))

# COMMAND ----------
published_root = Path(config.volume_path, "published")
proof_mode = "RESUME" if list(published_root.glob("*.json")) else "FRESH"
execution_results = []
attempts = []

for index, manifest_path in enumerate(manifest_paths):
    publication = publish_batch(manifest_path, Path(config.volume_path, "landing"), published_root)
    attempt = replace(config, batch_id=publication["batch_id"], run_id=uuid4().hex)
    attempts.append(attempt.run_id)
    results = run_bronze(spark, attempt)
    execution_results.extend({"stage": publication["batch_id"], "run_id": attempt.run_id, **row} for row in results)
    print(json.dumps({"publication": publication, "run_id": attempt.run_id, "source_results": results}))
    if index == 1:
        retry = replace(attempt, run_id=uuid4().hex)
        attempts.append(retry.run_id)
        replay = run_bronze(spark, retry)
        if any(row["rows_added"] != 0 for row in replay):
            raise AssertionError("Replay acrescentou registros")
        print(json.dumps({"stage": "REPLAY_PASSED", "run_id": retry.run_id, "rows_added": 0}))

display(spark.createDataFrame(execution_results))

# COMMAND ----------
# Compara payloads reais de todas as fontes com os arquivos, incluindo duplicates.
# O perfil pequeno e o recomendado para essa verificacao completa no driver.
counts = verify_payload_hashes(spark, config)
tx = spark.table(config.table("transacoes"))
if tx.where("id_transacao = 'T_DUP'").count() != 2:
    raise AssertionError("Bronze removeu duplicata de negocio")
if tx.where("id_transacao = 'T_INVALID_AMOUNT' AND valor = 'abc'").count() != 1:
    raise AssertionError("Valor bruto invalido foi alterado")
if tx.where("id_transacao = 'T_SCHEMA' AND schema_version = '2' AND get_json_object(_rescued_data, '$.dispositivo') = 'mobile-sintetico'").count() != 1:
    raise AssertionError("Coluna nova nao foi preservada")
display(tx.where("id_transacao IN ('T_DUP', 'T_INVALID_AMOUNT', 'T_SCHEMA')"))
print(json.dumps({"payload_hashes": "PASSED", "rows_by_source": counts}))

# COMMAND ----------
# Falha esperada e especifica: comprovar propagacao de erro e auditoria FAILED.
negative = replace(config, batch_id="batch_not_published", run_id=uuid4().hex)
try:
    run_bronze(spark, negative)
except BatchNotPublishedError as error:
    print(json.dumps({"negative_test": "EXPECTED_FAILURE", "run_id": negative.run_id, "message": str(error)}))
else:
    raise AssertionError("Pipeline aceitou lote nao publicado")

events = spark.table(f"{config.catalog}.{config.ops_schema}.pipeline_events")
from pyspark.sql import functions as F
if events.where((F.col("run_id") == negative.run_id) & (F.col("status") == "FAILED")).count() != 1:
    raise AssertionError("Falha esperada nao ficou registrada")
display(events.where(F.col("run_id").isin(attempts + [negative.run_id])).orderBy("event_at"))

# COMMAND ----------
print(json.dumps({
    "status": "BRONZE_DEMO_PASSED", "proof_mode": proof_mode,
    "rows_by_source": counts, "run_ids": attempts, "negative_run_id": negative.run_id,
    "catalog": config.catalog, "bronze_schema": config.bronze_schema,
    "volume": config.volume_path,
    "checks": ["six_sources", "manifest_reconciliation", "initial", "increment", "replay", "late_files", "raw_duplicates", "raw_invalid_value", "schema_rescue", "canonical_hash", "negative_audit"],
    "finished_at": datetime.now(timezone.utc).isoformat(),
}))
