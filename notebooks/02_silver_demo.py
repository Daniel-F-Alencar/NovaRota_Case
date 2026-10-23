# Databricks notebook source
# MAGIC %md
# MAGIC # NovaRota: Silver, qualidade e historico temporal
# MAGIC Usar o mesmo workspace e a Bronze de `01_bronze_demo`. Executar em Serverless.
# MAGIC Este notebook chama o pipeline e exibe os produtos e a quarentena; o status final indica conclusao e reconciliacao operacional.
# MAGIC `run_id` vazio inicia nova tentativa. Depois de falha, preencher com o ID exibido para retomar o mesmo snapshot.

# COMMAND ----------
import importlib.util
import json
import logging
import sys
from datetime import date
from uuid import uuid4

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("dataset_id", "case01")
dbutils.widgets.text("rule_version", "silver_v1")
dbutils.widgets.text("run_id", "")
dbutils.widgets.text("project_root", "")
dbutils.widgets.dropdown("mode", "incremental", ["incremental", "reprocess"])
dbutils.widgets.text("date_from", "")
dbutils.widgets.text("date_to", "")
dbutils.widgets.text("reference_date", "2026-06-30")

project_root = dbutils.widgets.get("project_root").strip()
if project_root:
    if not project_root.startswith("/Workspace/"):
        raise ValueError("project_root deve iniciar em /Workspace/")
    sys.path.insert(0, project_root)
try:
    silver_spec = importlib.util.find_spec("novarota.silver.pipeline")
except ModuleNotFoundError:
    silver_spec = None
if silver_spec is None:
    raise ImportError("Importe o ZIP Silver completo com os modulos atualizados ao lado do notebook.")

from novarota.config import PipelineConfig, identifier
from novarota.silver.pipeline import run_silver
from pyspark.sql import functions as F

logging.basicConfig(level=logging.INFO, format="%(message)s")
logging.getLogger("novarota").setLevel(logging.INFO)
dataset_id = identifier(dbutils.widgets.get("dataset_id"))
parse_date = lambda name: date.fromisoformat(dbutils.widgets.get(name)) if dbutils.widgets.get(name).strip() else None
config = PipelineConfig(
    catalog=dbutils.widgets.get("catalog"), reference_date=parse_date("reference_date"),
    bronze_schema=f"novarota_{dataset_id}_bronze", silver_schema=f"novarota_{dataset_id}_silver",
    ops_schema="novarota_ops", volume=f"{dataset_id}_files", batch_id="silver_snapshot",
    run_id=dbutils.widgets.get("run_id").strip() or uuid4().hex,
    rule_version=dbutils.widgets.get("rule_version"), mode=dbutils.widgets.get("mode"),
    date_from=parse_date("date_from"), date_to=parse_date("date_to"),
)
print(json.dumps({"run_id": config.run_id, "dataset": config.dataset_key, "mode": config.mode,
                  "rule_version": config.rule_version, "resume_with_this_run_id_on_failure": config.run_id}))

# COMMAND ----------
result = run_silver(spark, config)
print(json.dumps(result, ensure_ascii=False, default=str))

def silver(name):
    return spark.table(config.silver_table(name)).where(F.col("_dataset_id") == config.dataset_key)

# COMMAND ----------
evaluations = spark.table(f"{config.catalog}.{config.ops_schema}.silver_classificacoes").where(F.col("_dataset_id") == config.dataset_key)
display(evaluations.groupBy("source").agg(
    F.sum("multiplicidade").alias("linhas_bronze"), F.sum("qt_aprovadas").alias("aprovadas"),
    F.sum("qt_duplicatas").alias("duplicatas"), F.sum("qt_quarentena").alias("quarentena")).orderBy("source"))
display(spark.table(f"{config.catalog}.{config.ops_schema}.silver_quarentena")
        .where(F.col("_dataset_id") == config.dataset_key)
        .select("source", "identity_key", "motivos", "payload_original", "arquivo_origem", "qt_quarentena"))

# COMMAND ----------
display(silver("clientes_scd2").where("id_cliente = 'C001'")
        .select("id_cliente", "id_evento_cdc", "renda", "cidade", "valid_from", "valid_to", "is_current", "is_deleted").orderBy("valid_from"))
display(silver("cartoes_scd2").where("id_cartao IN ('K001', 'K004')")
        .select("id_cartao", "status_cartao", "operacao", "valid_from", "valid_to", "is_current", "is_deleted").orderBy("id_cartao", "valid_from"))
display(silver("transacoes_atual")
        .where("id_transacao IN ('T_PARTIAL', 'T_FULL', 'T_DUP', 'T_FX', 'T_CANCELLED', 'T_BEFORE_CANCEL', 'T_AFTER_CANCEL', 'T_VERSION', 'T_SCHEMA')")
        .select("id_transacao", "valor", "moeda", "status_transacao", "elegivel_brl", "motivos_inelegibilidade",
                "valor_estornado_validado", "estornos_reconciliados", "id_cliente", "dispositivo").orderBy("id_transacao"))

# COMMAND ----------
display(spark.table(f"{config.catalog}.{config.ops_schema}.pipeline_events")
        .where(F.col("run_id") == config.run_id).orderBy("event_at"))
print(json.dumps(result, ensure_ascii=False, default=str))
