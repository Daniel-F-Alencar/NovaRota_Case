"""Identidades, conflitos e intervalos temporais, independentes da chegada."""

from novarota.contracts import SOURCES
from novarota.quality.contracts import ENTITIES, identity_fields
from novarota.quality.rules import add_reason


def canonicalize(frame, source: str):
    from pyspark.sql import functions as F, Window
    keys = identity_fields(source)
    summary = frame.groupBy(*keys).agg(F.countDistinct("hash_conteudo").alias("_payload_count"),
                                      F.min("_first_seen").alias("_identity_first_seen"))
    # Nulls em chaves invalidas continuam avaliaveis, sem desaparecer no join.
    joined = frame.alias("r").join(summary.alias("g"),
        _and([F.col("r." + key).eqNullSafe(F.col("g." + key)) for key in keys]), "left")
    frame = joined.select("r.*", "g._payload_count", "g._identity_first_seen")
    frame = add_reason(frame, F.col("_payload_count") > 1, "IDENTITY_CONFLICT")
    if source in ENTITIES:
        position = [ENTITIES[source], "data_atualizacao", "sequencia_origem"]
        conflicts = (frame.groupBy(*position).agg(F.countDistinct("hash_conteudo").alias("_position_count")))
        joined = frame.alias("r").join(conflicts.alias("g"),
            _and([F.col("r." + key).eqNullSafe(F.col("g." + key)) for key in position]), "left")
        frame = add_reason(joined.select("r.*", "g._position_count"), F.col("_position_count") > 1, "TEMPORAL_POSITION_CONFLICT")
    if source == "transacoes":
        blocked = frame.groupBy("id_transacao").agg(F.max((F.col("_payload_count") > 1).cast("int")).alias("_transaction_conflict"))
        frame = add_reason(frame.join(blocked, "id_transacao", "left"), F.col("_transaction_conflict") > 0, "TRANSACTION_CONFLICT")
    order = Window.partitionBy(*keys).orderBy((F.size("_errors") > 0).asc(), F.col("_first_seen").asc_nulls_last(),
                                              "arquivo_origem", "hash_linha", "_occurrence_id")
    return (frame.withColumn("_identity", F.to_json(F.struct(*[F.col(key) for key in keys]), options={"ignoreNullFields": "false"}))
            .withColumn("_rank", F.row_number().over(order)))


def _and(expressions):
    from functools import reduce
    from operator import and_
    return reduce(and_, expressions)


def approved(frame):
    from pyspark.sql import functions as F
    return frame.where((F.size("_errors") == 0) & (F.col("_rank") == 1))


def events(frame, source: str, extra=()):
    from pyspark.sql import functions as F
    return approved(frame).select(*SOURCES[source].fields, "extras_json", "dispositivo", "hash_conteudo", "hash_linha",
                                  "arquivo_origem", "batch_id", "run_id_bronze", "schema_version",
                                  F.col("_identity_first_seen").alias("primeira_disponibilidade"),
                                  F.sha2("_identity", 256).alias("event_key"), *extra)


def history(frame, source: str):
    """Eventos rejeitados delimitam lacunas; nunca prolongar versao antiga sobre conflito."""
    from pyspark.sql import functions as F, Window
    key = ENTITIES[source]
    known = frame.where(F.col(key).isNotNull() & F.col("data_atualizacao").isNotNull() & F.col("sequencia_origem").isNotNull())
    slots = known.groupBy(key, "data_atualizacao").agg(F.max("sequencia_origem").alias("_last_sequence"))
    order = Window.partitionBy(key).orderBy("data_atualizacao")
    slots = slots.withColumn("valid_to", F.lead("data_atualizacao").over(order))
    rows = events(frame, source).join(slots, [key, "data_atualizacao"], "inner").where(F.col("sequencia_origem") == F.col("_last_sequence")).drop("_last_sequence")
    unknown_order = frame.where(F.col(key).isNotNull() & (F.col("data_atualizacao").isNull() | F.col("sequencia_origem").isNull())).select(key).distinct()
    rows = rows.join(unknown_order, key, "left_anti")
    return (rows.withColumn("valid_from", F.col("data_atualizacao"))
            .withColumn("is_current", F.col("valid_to").isNull())
            .withColumn("is_deleted", F.col("operacao") == "D")
            .withColumn("version_id", F.sha2(F.to_json(F.struct(F.lit(source).alias("source"), F.col(key), F.col("valid_from")),
                                                       options={"timeZone": "UTC"}), 256)))


def temporal_reference(frame, parent, foreign: str, key: str, at: str, prefix: str, attributes=(), tombstone=False):
    from pyspark.sql import functions as F
    joined = frame.alias("r").join(parent.alias("p"),
        (F.col("r." + foreign) == F.col("p." + key)) & (F.col("r." + at) >= F.col("p.valid_from")) &
        (F.col("p.valid_to").isNull() | (F.col("r." + at) < F.col("p.valid_to"))), "left")
    result = joined.select("r.*", F.col("p.version_id").alias(prefix + "version_id"),
                           F.col("p.is_deleted").alias(prefix + "deleted"),
                           *[F.col("p." + field).alias(prefix + field) for field in attributes])
    skip = F.col("operacao") == "D" if tombstone else F.lit(False)
    result = add_reason(result, ~skip & F.col(prefix + "version_id").isNull(), "REFERENCE_NOT_FOUND:" + key)
    return add_reason(result, ~skip & F.coalesce(F.col(prefix + "deleted"), F.lit(False)), "REFERENCE_DELETED:" + key)
