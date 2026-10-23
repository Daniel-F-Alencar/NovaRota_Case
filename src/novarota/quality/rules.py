"""Validacoes vetorizadas: sem UDF Python, RDD ou coleta dos registros."""

from novarota.contracts import SOURCES
from novarota.quality.contracts import ENUMS, TYPES


def reasons(*conditions):
    from pyspark.sql import functions as F
    return F.filter(F.array(*[F.when(F.coalesce(condition, F.lit(False)), F.lit(code))
                             for condition, code in conditions]), lambda value: value.isNotNull())


def add_reason(frame, condition, code: str):
    from pyspark.sql import functions as F
    return frame.withColumn("_errors", F.array_sort(F.array_distinct(
        F.concat(F.col("_errors"), reasons((condition, code))))))


def cpf_valid(column="cpf"):
    from pyspark.sql import functions as F
    digits = [F.expr(f"try_cast(substr(`{column}`, {index}, 1) AS INT)") for index in range(1, 12)]
    checks = []
    for length in (9, 10):
        remainder = sum(digits[index] * (length + 1 - index) for index in range(length)) * 10 % 11
        checks.append(digits[length] == F.when(remainder == 10, 0).otherwise(remainder))
    return (F.col(column).rlike(r"^[0-9]{11}$") &
            ~F.col(column).rlike(r"^([0-9])\1{10}$") & checks[0] & checks[1])


def prepare(raw, source: str):
    from pyspark.sql import functions as F

    contract = SOURCES[source]
    raw_payload = F.to_json(F.struct(*[F.col(name) for name in (*contract.fields, "_rescued_data", "_corrupt_record")]),
                            options={"ignoreNullFields": "false"})
    grouped = (raw.withColumn("_raw_payload", raw_payload)
               .groupBy(*contract.fields, "_rescued_data", "_corrupt_record", "arquivo_origem", "hash_linha", "batch_id", "schema_version", "_raw_payload")
               .agg(F.count("*").alias("multiplicidade"), F.min("timestamp_ingestao").alias("_first_seen"),
                    F.min("run_id").alias("run_id_bronze")))
    empty_map = F.expr("map()").cast("map<string,string>")
    rescue = F.from_json("_rescued_data", "map<string,string>")
    extras = F.map_filter(F.coalesce(rescue, empty_map), lambda key, value: key != F.lit("_file_path"))
    checks = [(F.col("_corrupt_record").isNotNull(), "CORRUPT_RECORD"),
              (F.col("_rescued_data").isNotNull() & rescue.isNull(), "INVALID_RESCUE"),
              (F.col("arquivo_origem").isNull() | F.col("hash_linha").isNull() | F.col("_first_seen").isNull(), "MISSING_PROVENANCE")]
    columns = []
    for name in contract.fields:
        original = F.col(name)
        kind = TYPES.get(name, "STRING")
        value = F.trim(original) if kind == "STRING" else F.expr(f"try_cast(`{name}` AS {kind})")
        checks.append((original.isNull() | (F.trim(original) == ""), "REQUIRED:" + name))
        if kind != "STRING":
            checks.append((original.isNotNull() & value.isNull(), "INVALID_TYPE:" + name))
        if kind.startswith("DECIMAL"):
            checks.extend([(original.isNotNull() & ~original.rlike(r"^-?[0-9]+(?:\.[0-9]{1,2})?$"), "INVALID_DECIMAL:" + name),
                           (value < 0 if name in {"renda", "limite"} else value <= 0, "INVALID_RANGE:" + name)])
        elif kind == "BIGINT":
            checks.append((~original.rlike(r"^[0-9]+$") | (value <= 0), "INVALID_SEQUENCE"))
        elif kind == "TIMESTAMP":
            checks.append((~original.rlike(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|\+00:00)$"), "INVALID_UTC:" + name))
        elif kind == "DATE":
            checks.append((~original.rlike(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"), "INVALID_DATE:" + name))
        if name in ENUMS:
            value = F.upper(value)
            checks.append((~value.isin(*ENUMS[name]), "INVALID_ENUM:" + name))
        if name in {"moeda", "pais"}:
            value = F.upper(value)
            checks.append((~value.rlike(r"^[A-Z]{3}$" if name == "moeda" else r"^[A-Z]{2}$"), "INVALID_CODE:" + name))
        if name == "cpf":
            checks.append((~F.coalesce(cpf_valid(), F.lit(False)), "INVALID_CPF"))
        if name == "mcc":
            checks.append((~value.rlike(r"^[0-9]{4}$"), "INVALID_MCC"))
        columns.append(value.alias(name))
    if source == "transacoes":
        checks.append((F.expr("try_cast(data_atualizacao AS TIMESTAMP) < try_cast(data_transacao AS TIMESTAMP)"), "UPDATE_BEFORE_TRANSACTION"))
    if source == "contas_cdc":
        checks.append((F.expr("try_cast(data_abertura AS DATE) > CAST(try_cast(data_atualizacao AS TIMESTAMP) AS DATE)"), "OPENING_AFTER_EVENT"))
    result = grouped.select(*columns, "arquivo_origem", "hash_linha", "batch_id", "schema_version", "run_id_bronze",
                            "_first_seen", "multiplicidade", "_raw_payload", reasons(*checks).alias("_errors"),
                            F.to_json(F.array_sort(F.map_entries(extras)), options={"ignoreNullFields": "false"}).alias("extras_json"),
                            F.element_at(extras, F.lit("dispositivo")).alias("dispositivo"))
    occurrence = F.to_json(F.struct(F.lit(source).alias("source"), F.col("arquivo_origem"), F.col("hash_linha"),
                                   F.col("batch_id"), F.col("schema_version"), F.col("_raw_payload")),
                           options={"ignoreNullFields": "false"})
    normalized = F.to_json(F.struct(*[F.col(name) for name in contract.fields], F.col("extras_json")),
                           options={"ignoreNullFields": "false", "timeZone": "UTC"})
    return (result.withColumn("_occurrence_id", F.sha2(occurrence, 256))
            .withColumn("hash_conteudo", F.sha2(F.concat(F.lit("normalized_v1:"), normalized), 256)))
