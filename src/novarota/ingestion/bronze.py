"""Bronze Databricks: Spark Connect, Delta e Auto Loader AvailableNow.

Imports Spark sao locais para o gerador/testes puros nao dependerem de Spark.
"""

from collections import Counter
from pathlib import Path

from novarota.config import PipelineConfig
from novarota.contracts import SOURCES, SourceContract
from novarota.ingestion.manifests import published_manifests
from novarota.ingestion.reconciliation import (
    check_counts, expected_counts, expected_hashes, relative_origin, verify_landing,
)
from novarota.observability.audit import AUDIT_SCHEMA, DeltaAuditWriter, audited


class BatchNotPublishedError(ValueError):
    """Lote solicitado ainda nao possui manifesto de publicacao concluida."""


def input_schema(contract: SourceContract) -> str:
    return ", ".join(f"{name} STRING" for name in (*contract.fields, "_rescued_data", "_corrupt_record"))


def setup_workspace(spark, config: PipelineConfig) -> None:
    spark.conf.set("spark.sql.session.timeZone", "UTC")
    for schema in (config.bronze_schema, config.ops_schema):
        spark.sql(f"CREATE SCHEMA IF NOT EXISTS {config.catalog}.{schema}")
    spark.sql(f"CREATE VOLUME IF NOT EXISTS {config.catalog}.{config.ops_schema}.{config.volume}")
    for folder in ("landing", "published", "generated", "checkpoints", "schemas"):
        Path(config.volume_path, folder).mkdir(parents=True, exist_ok=True)
    spark.sql(f"CREATE TABLE IF NOT EXISTS {config.catalog}.{config.ops_schema}.pipeline_events ({AUDIT_SCHEMA}) USING DELTA")
    technical = "arquivo_origem STRING, data_ingestao DATE, timestamp_ingestao TIMESTAMP, batch_id STRING, run_id STRING, hash_linha STRING, schema_version STRING"
    for source, contract in SOURCES.items():
        spark.sql(f"CREATE TABLE IF NOT EXISTS {config.table(source)} ({input_schema(contract)}, {technical}) USING DELTA")


def enrich_bronze(frame, contract: SourceContract, config: PipelineConfig):
    """Recebe arquivo_origem extraido de _metadata.file_path pelo leitor."""
    from pyspark.sql import functions as F

    empty_map = F.expr("map()").cast("map<string,string>")
    rescued = F.coalesce(F.from_json(F.col("_rescued_data"), "map<string,string>"), empty_map)
    rescued = F.map_filter(rescued, lambda key, value: key != F.lit("_file_path"))
    known = F.create_map(*[item for name in contract.fields for item in (F.lit(name), F.col(name))])
    payload = F.map_zip_with(known, rescued, lambda key, original, extra: F.coalesce(extra, original))
    corrupt = F.when(F.col("_corrupt_record").isNotNull(), F.create_map(F.lit("_corrupt_record"), F.col("_corrupt_record"))).otherwise(empty_map)
    payload = F.map_concat(payload, corrupt)
    canonical = F.to_json(F.array_sort(F.map_entries(payload)), options={"ignoreNullFields": "false"})
    path_pattern = r"/([A-Za-z0-9][A-Za-z0-9_-]{0,99})/schema_v([1-9][0-9]*)/"
    return (frame
            .withColumn("timestamp_ingestao", F.current_timestamp())
            .withColumn("data_ingestao", F.to_date("timestamp_ingestao"))
            .withColumn("run_id", F.lit(config.run_id))
            .withColumn("batch_id", F.regexp_extract("arquivo_origem", path_pattern, 1))
            .withColumn("schema_version", F.regexp_extract("arquivo_origem", path_pattern, 2))
            .withColumn("hash_linha", F.sha2(canonical, 256)))


def _actual_counts(spark, table: str, expected: dict[str, int]) -> dict[str, int]:
    actual = Counter()
    for row in spark.table(table).groupBy("arquivo_origem").count().collect():
        actual[relative_origin(row["arquivo_origem"], set(expected))] += row["count"]
    return dict(actual)


def _ingest_source(spark, config: PipelineConfig, source: str) -> None:
    from pyspark.sql import functions as F

    contract = SOURCES[source]
    reader = (spark.readStream.format("cloudFiles")
              .schema(input_schema(contract))
              .option("cloudFiles.format", contract.format)
              .option("cloudFiles.schemaLocation", f"{config.volume_path}/schemas/{source}")
              .option("cloudFiles.schemaEvolutionMode", "rescue")
              .option("cloudFiles.partitionColumns", "")
              .option("cloudFiles.allowOverwrites", "false")
              .option("cloudFiles.maxFilesPerTrigger", 100)
              .option("rescuedDataColumn", "_rescued_data")
              .option("columnNameOfCorruptRecord", "_corrupt_record")
              .option("mode", "PERMISSIVE")
              .option("recursiveFileLookup", "true"))
    if contract.format == "csv":
        reader = reader.option("header", "true").option("nullValue", "\\N").option("emptyValue", "")
    raw = reader.load(f"{config.volume_path}/landing/{source}").select("*", F.col("_metadata.file_path").alias("arquivo_origem"))
    query = (enrich_bronze(raw, contract, config).writeStream.format("delta")
             .outputMode("append")
             .option("checkpointLocation", f"{config.volume_path}/checkpoints/{source}")
             .trigger(availableNow=True)
             .toTable(config.table(source)))
    query.awaitTermination()
    if query.exception() is not None:
        raise RuntimeError(str(query.exception()))


def run_bronze(spark, config: PipelineConfig) -> list[dict]:
    """Setup deve ter sido executado; nenhum reset de tabela/checkpoint."""
    if config.mode != "incremental":
        raise ValueError("Bronze aceita apenas incremental; replay de negocio pertence as camadas seguintes")
    writer = DeltaAuditWriter(spark, config)
    results = []
    with audited(writer, "pipeline") as pipeline_metrics:
        manifests = published_manifests(Path(config.volume_path, "published"))
        if config.batch_id not in {manifest["batch_id"] for manifest in manifests}:
            raise BatchNotPublishedError(f"Lote nao publicado: {config.batch_id}")
        verify_landing(manifests, Path(config.volume_path, "landing"))
        for source in SOURCES:
            with audited(writer, source) as metrics:
                expected = expected_counts(manifests, source)
                before = _actual_counts(spark, config.table(source), expected)
                if sum(before.values()) and not Path(config.volume_path, "checkpoints", source).exists():
                    raise ValueError(f"{source}: Bronze possui dados, mas o checkpoint esta ausente; recuperar estado antes de ingerir")
                already_complete = check_counts(before, expected, allow_missing=True)
                metrics.update({"files_expected": len(expected), "empty_files": sum(n == 0 for n in expected.values()),
                                "rows_before": sum(before.values()), "rows_expected": sum(expected.values()), "no_new_rows": already_complete})
                if not already_complete:
                    _ingest_source(spark, config, source)
                after = _actual_counts(spark, config.table(source), expected)
                check_counts(after, expected)
                invalid_metadata = spark.table(config.table(source)).where(
                    "batch_id = '' OR schema_version = '' OR hash_linha IS NULL OR _corrupt_record IS NOT NULL"
                ).count()
                if invalid_metadata:
                    raise ValueError(f"{source}: {invalid_metadata} registros corrompidos ou sem metadados validos; conteudo preservado na Bronze")
                metrics.update({"rows_after": sum(after.values()), "rows_added": sum(after.values()) - sum(before.values())})
                results.append({"source": source, **metrics})
        pipeline_metrics.update({"sources": len(results), "rows_added": sum(r["rows_added"] for r in results)})
    return results


def verify_payload_hashes(spark, config: PipelineConfig) -> dict[str, int]:
    """Oracle Python independente do parser Spark; indicado ao perfil pequeno."""
    manifests = published_manifests(Path(config.volume_path, "published"))
    summary = {}
    for source in SOURCES:
        expected = expected_hashes(manifests, Path(config.volume_path, "landing"), source)
        paths = set(expected_counts(manifests, source))
        actual = Counter()
        for row in spark.table(config.table(source)).groupBy("arquivo_origem", "hash_linha").count().collect():
            actual[(relative_origin(row["arquivo_origem"], paths), row["hash_linha"])] += row["count"]
        if expected != actual:
            raise ValueError(f"Hash/payload diverge do arquivo de origem: {source}")
        summary[source] = sum(actual.values())
    return summary
