"""Dependencias cadastrais, canonizacao financeira e classificacoes reconciliaveis."""

from novarota.contracts import SOURCES
from novarota.quality.contracts import EVENT_TABLES, HISTORY_TABLES
from novarota.quality.rules import prepare, add_reason, reasons
from novarota.silver.temporal import canonicalize, events, history, temporal_reference, approved


def classifications(frame, source: str, config):
    from pyspark.sql import functions as F
    rejected = F.size("_errors") > 0
    accepted = ~rejected & (F.col("_rank") == 1)
    return frame.select(F.lit(source).alias("source"), F.col("_occurrence_id").alias("occurrence_id"),
        F.col("_identity").alias("identity_key"), "arquivo_origem", "batch_id", "run_id_bronze", "hash_linha", "hash_conteudo",
        F.col("_raw_payload").alias("payload_original"), F.col("_first_seen").alias("primeira_disponibilidade"),
        F.col("_errors").alias("motivos"), "multiplicidade",
        F.when(accepted, F.lit(1)).otherwise(F.lit(0)).cast("long").alias("qt_aprovadas"),
        F.when(rejected, F.col("multiplicidade")).otherwise(F.lit(0)).cast("long").alias("qt_quarentena"),
        F.when(rejected, F.lit(0)).otherwise(F.col("multiplicidade") - F.when(accepted, 1).otherwise(0)).cast("long").alias("qt_duplicatas"),
        F.when(rejected, "QUARENTENA").when(accepted, "APROVADA").otherwise("DUPLICATA").alias("classificacao"),
        F.lit(config.run_id).alias("evaluation_run_id"))


def _current_transactions(working, versions):
    from pyspark.sql import functions as F
    latest = working.groupBy("id_transacao").agg(F.max(F.struct("data_atualizacao", "sequencia_origem")).alias("_latest"))
    bad_order = working.where(F.col("data_atualizacao").isNull() | F.col("sequencia_origem").isNull()).select("id_transacao").distinct()
    return (versions.join(latest, "id_transacao").where(
        (F.col("data_atualizacao") == F.col("_latest.data_atualizacao")) &
        (F.col("sequencia_origem") == F.col("_latest.sequencia_origem"))).drop("_latest")
        .join(bad_order, "id_transacao", "left_anti"))


def build_silver(inputs: dict, config, materialize):
    """materialize escreve/relê parquet no staging da tentativa, cortando planos longos."""
    from pyspark.sql import functions as F
    working, outputs = {}, {}
    for source in ("clientes_cdc", "contas_cdc", "cartoes_cdc"):
        frame = canonicalize(prepare(inputs[source], source), source)
        if source == "contas_cdc":
            frame = temporal_reference(frame, outputs["clientes_scd2"], "id_cliente", "id_cliente", "data_atualizacao", "_cliente_", tombstone=True)
        if source == "cartoes_cdc":
            frame = temporal_reference(frame, outputs["contas_scd2"], "id_conta", "id_conta", "data_atualizacao", "_conta_", tombstone=True)
        working[source] = materialize("working_" + source, frame)
        outputs[EVENT_TABLES[source]] = materialize(EVENT_TABLES[source], events(working[source], source))
        outputs[HISTORY_TABLES[source]] = materialize(HISTORY_TABLES[source], history(working[source], source))

    tx = canonicalize(prepare(inputs["transacoes"], "transacoes"), "transacoes")
    tx = temporal_reference(tx, outputs["cartoes_scd2"], "id_cartao", "id_cartao", "data_transacao", "_cartao_", ("id_conta", "status_cartao"))
    tx = temporal_reference(tx, outputs["contas_scd2"], "_cartao_id_conta", "id_conta", "data_transacao", "_conta_", ("id_cliente", "status_conta"))
    tx = temporal_reference(tx, outputs["clientes_scd2"], "_conta_id_cliente", "id_cliente", "data_transacao", "_cliente_")
    eligibility = reasons((F.col("status_transacao") != "APROVADA", "TRANSACTION_NOT_APPROVED"),
                          (F.col("_cartao_status_cartao") != "ATIVO", "CARD_NOT_ACTIVE"),
                          (F.col("_conta_status_conta") != "ATIVA", "ACCOUNT_NOT_ACTIVE"),
                          (F.col("moeda") != "BRL", "NON_BRL"))
    tx = (tx.withColumn("motivos_inelegibilidade", eligibility)
          .withColumn("elegivel_brl", (F.size("_errors") == 0) & (F.size("motivos_inelegibilidade") == 0))
          .withColumn("id_conta", F.col("_cartao_id_conta")).withColumn("id_cliente", F.col("_conta_id_cliente"))
          .withColumn("cartao_version_id", F.col("_cartao_version_id"))
          .withColumn("conta_version_id", F.col("_conta_version_id"))
          .withColumn("cliente_version_id", F.col("_cliente_version_id")))
    working["transacoes"] = materialize("working_transacoes", tx)
    tx_extra = ("id_conta", "id_cliente", "cartao_version_id", "conta_version_id", "cliente_version_id", "motivos_inelegibilidade", "elegivel_brl")
    versions = events(working["transacoes"], "transacoes", tx_extra)
    current = materialize("transacoes_base_atual", _current_transactions(working["transacoes"], versions))

    for source in ("eventos_risco", "estornos"):
        frame = canonicalize(prepare(inputs[source], source), source)
        parent = current.select("id_transacao", F.col("valor").alias("_purchase_amount"),
                                F.col("moeda").alias("_purchase_currency"), F.col("data_transacao").alias("_purchase_at"))
        frame = frame.join(parent, "id_transacao", "left")
        frame = add_reason(frame, F.col("_purchase_amount").isNull(), "REFERENCE_NOT_FOUND:id_transacao")
        event_at = "data_evento" if source == "eventos_risco" else "data_estorno"
        frame = add_reason(frame, F.col(event_at) < F.col("_purchase_at"), "EVENT_BEFORE_TRANSACTION")
        if source == "estornos":
            frame = add_reason(frame, F.col("moeda") != F.col("_purchase_currency"), "REFUND_CURRENCY_MISMATCH")
            totals = approved(frame).groupBy("id_transacao").agg(F.sum("valor_estorno").alias("_refund_sum"))
            frame = frame.join(totals, "id_transacao", "left")
            frame = add_reason(frame, F.col("_refund_sum") > F.col("_purchase_amount"), "REFUND_EXCEEDS_PURCHASE")
        working[source] = materialize("working_" + source, frame)
        outputs[source] = materialize(source, events(working[source], source))

    refunds = outputs["estornos"].groupBy("id_transacao").agg(F.sum("valor_estorno").alias("valor_estornado_validado"))
    blocked_refunds = working["estornos"].where(F.size("_errors") > 0).select("id_transacao").distinct().withColumn("_blocked_refunds", F.lit(True))
    # Conflito de identidade pode ligar um estorno a duas compras; ambas sao sinalizadas.
    for name, frame in (("transacoes_versoes", versions), ("transacoes_atual", current)):
        outputs[name] = (frame.join(refunds, "id_transacao", "left").join(blocked_refunds, "id_transacao", "left")
                         .withColumn("valor_estornado_validado", F.coalesce("valor_estornado_validado", F.lit(0).cast("decimal(28,2)")))
                         .withColumn("estornos_reconciliados", ~F.coalesce("_blocked_refunds", F.lit(False))).drop("_blocked_refunds"))
    evaluated = [classifications(working[source], source, config) for source in SOURCES]
    all_evaluations = evaluated[0]
    for frame in evaluated[1:]:
        all_evaluations = all_evaluations.unionByName(frame)
    outputs["silver_classificacoes"] = all_evaluations
    outputs["silver_avaliacoes"] = all_evaluations
    return outputs
