"""MERGE escopado por dataset e verificacao operacional dos destinos."""

from uuid import uuid4


def literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def stamp(frame, config):
    from pyspark.sql import functions as F
    frame = frame.withColumn("_dataset_id", F.lit(config.dataset_key)).withColumn("_rule_version", F.lit(config.rule_version))
    stable = [name for name in sorted(frame.columns) if name != "evaluation_run_id"]
    return frame.withColumn("_content_hash", F.sha2(F.to_json(F.struct(*[F.col(name) for name in stable]),
        options={"ignoreNullFields": "false", "timeZone": "UTC"}), 256))


def sync(spark, frame, table: str, keys: tuple, dataset: str, delete_missing=True):
    from pyspark.sql import functions as F
    all_keys = ("_dataset_id", *keys)
    if frame.where(_any([F.col(key).isNull() for key in all_keys])).limit(1).count():
        raise ValueError(f"Chave nula na origem do MERGE de {table}")
    if frame.groupBy(*all_keys).count().where("count > 1").limit(1).count():
        raise ValueError(f"Chave duplicada na origem do MERGE de {table}")
    # mode(ignore) cria somente tabelas ausentes, sem limpar as existentes.
    frame.limit(0).write.format("delta").mode("ignore").saveAsTable(table)
    view = "nr_silver_" + uuid4().hex
    frame.createOrReplaceTempView(view)
    condition = " AND ".join(f"t.`{key}` = s.`{key}`" for key in all_keys)
    cleanup = f"WHEN NOT MATCHED BY SOURCE AND t._dataset_id = {literal(dataset)} THEN DELETE" if delete_missing else ""
    try:
        spark.sql(f"""MERGE INTO {table} t USING {view} s ON {condition}
            WHEN MATCHED AND NOT (t._content_hash <=> s._content_hash) THEN UPDATE SET *
            WHEN NOT MATCHED THEN INSERT *
            {cleanup}""")
    finally:
        spark.catalog.dropTempView(view)


def reconcile(spark, desired, table: str, keys: tuple, config, history=False):
    from pyspark.sql import functions as F
    actual = spark.table(table).where(F.col("_dataset_id") == config.dataset_key)
    if history:
        actual = actual.where(F.col("evaluation_run_id") == config.run_id)
    columns = ["_dataset_id", *keys, "_content_hash"]
    expected = desired.select(*columns)
    observed = actual.select(*columns)
    if expected.exceptAll(observed).limit(1).count() or observed.exceptAll(expected).limit(1).count():
        raise ValueError(f"Reconciliação Silver divergente em {table}; consumo bloqueado pela auditoria")
    return observed.count()


def _any(expressions):
    from functools import reduce
    from operator import or_
    return reduce(or_, expressions)
