# Databricks notebook source
# MAGIC %md
# MAGIC # NovaRota: fato Gold, comportamento, risco e features
# MAGIC Reutilizar o mesmo workspace e a Silver já concluída. Executar em Serverless.
# MAGIC `feature_date` é o fim do dia de disponibilidade: não pode anteceder a publicação da Silver consumida.
# MAGIC `run_id` vazio cria nova tentativa; após falha, preencher com o ID impresso para retomar.

# COMMAND ----------
import importlib.util
import json
import logging
import sys
from datetime import date, datetime, timezone
from uuid import uuid4

dbutils.widgets.text("catalog", "workspace")
dbutils.widgets.text("dataset_id", "case01")
dbutils.widgets.text("feature_date", datetime.now(timezone.utc).date().isoformat())
dbutils.widgets.text("run_id", "")
dbutils.widgets.text("project_root", "")

project_root = dbutils.widgets.get("project_root").strip()
if project_root:
    if not project_root.startswith("/Workspace/"):
        raise ValueError("project_root deve iniciar em /Workspace/")
    sys.path.insert(0, project_root)
try:
    gold_spec = importlib.util.find_spec("novarota.gold.pipeline")
except ModuleNotFoundError:
    gold_spec = None
if gold_spec is None:
    raise ImportError("Importe o ZIP Gold completo com os modulos atualizados ao lado do notebook.")

from novarota.config import identifier
from novarota.gold.pipeline import GoldConfig, run_gold
from pyspark.sql import functions as F

logging.basicConfig(level=logging.INFO, format="%(message)s")
logging.getLogger("novarota").setLevel(logging.INFO)
dataset_id = identifier(dbutils.widgets.get("dataset_id"))
config = GoldConfig(
    catalog=dbutils.widgets.get("catalog"), bronze_schema=f"novarota_{dataset_id}_bronze",
    silver_schema=f"novarota_{dataset_id}_silver", gold_schema=f"novarota_{dataset_id}_gold",
    ops_schema="novarota_ops", volume=f"{dataset_id}_files",
    feature_date=date.fromisoformat(dbutils.widgets.get("feature_date")),
    run_id=dbutils.widgets.get("run_id").strip() or uuid4().hex,
)
print(json.dumps({"run_id": config.run_id, "dataset": config.dataset_key,
                  "feature_date": config.feature_date.isoformat(),
                  "resume_with_this_run_id_on_failure": config.run_id}))

# COMMAND ----------
result = run_gold(spark, config)
print(json.dumps(result, ensure_ascii=False, default=str))

def gold(name):
    return spark.table(config.gold_table(name)).where(F.col("_dataset_id") == config.dataset_key)

# COMMAND ----------
display(gold("gold_fato_transacao")
        .where("id_transacao IN ('T_PARTIAL','T_FULL','T_CANCELLED','T_FX','T_BEFORE_CANCEL','T_AFTER_CANCEL','T_VERSION')")
        .select("id_transacao", "data_transacao", "id_cliente", "status_transacao", "moeda",
                "elegivel_indicadores", "motivos_exclusao", "valor_bruto_brl",
                "valor_estornado_brl", "valor_liquido_brl").orderBy("id_transacao"))
display(gold("gold_cliente_mes").orderBy("id_cliente", "data_mes"))
display(gold("gold_indicadores_risco").orderBy("id_cliente", "data_mes"))
display(gold("gold_features_cliente").orderBy("id_cliente"))

# COMMAND ----------
display(spark.table(f"{config.catalog}.{config.ops_schema}.pipeline_events")
        .where(F.col("run_id") == config.run_id).orderBy("event_at"))
print(json.dumps(result, ensure_ascii=False, default=str))
