"""Transformações Gold distribuídas sobre um snapshot Silver concluído."""


def _source(frame):
    return frame.drop("_dataset_id", "_rule_version", "_content_hash")


def transaction_fact(transactions):
    from pyspark.sql import functions as F

    eligible = F.col("elegivel_brl") & F.col("estornos_reconciliados")
    return (_source(transactions)
        .withColumn("data_mes", F.trunc(F.to_date("data_transacao"), "MM"))
        .withColumn("elegivel_indicadores", eligible)
        .withColumn("valor_bruto_brl", F.when(eligible, F.col("valor")).cast("decimal(28,2)"))
        .withColumn("valor_estornado_brl", F.when(eligible, F.col("valor_estornado_validado")).cast("decimal(28,2)"))
        .withColumn("valor_liquido_brl", F.when(eligible, F.col("valor") - F.col("valor_estornado_validado")).cast("decimal(28,2)"))
        .withColumn("motivos_exclusao", F.array_union(
            F.col("motivos_inelegibilidade"),
            F.when(~F.col("estornos_reconciliados"), F.array(F.lit("REFUNDS_NOT_RECONCILED")))
             .otherwise(F.array().cast("array<string>")))))


def establishment_dimension(fact):
    from pyspark.sql import functions as F, Window

    key = "id_estabelecimento"
    ranked = (fact.withColumn("_rank", F.row_number().over(
        Window.partitionBy(key).orderBy(F.col("data_transacao").desc(), F.col("id_transacao").desc())))
        .where(F.col("_rank") == 1)
        .select(key, "estabelecimento", "mcc", F.col("id_transacao").alias("transacao_representante")))
    variants = fact.groupBy(key).agg(F.countDistinct("estabelecimento").alias("nomes_distintos"),
                                     F.countDistinct("mcc").alias("mcc_distintos"))
    return ranked.join(variants, key)


def _risk_by_transaction(events, refunds):
    from pyspark.sql import functions as F

    risk = (events.groupBy("id_transacao").agg(
        F.count("id_evento").alias("qt_eventos_risco"),
        F.sum(F.when(F.col("tipo_evento") == "CHARGEBACK", 1).otherwise(0)).alias("qt_chargebacks"),
        F.sum(F.when(F.col("severidade").isin("ALTA", "CRITICA"), 1).otherwise(0)).alias("qt_risco_alto")))
    refund = (refunds.groupBy("id_transacao").agg(F.count("id_estorno").alias("qt_estornos")))
    return risk, refund


def _fact_with_risk(fact, events, refunds):
    from pyspark.sql import functions as F

    risk, refund = _risk_by_transaction(events, refunds)
    joined = fact.join(risk, "id_transacao", "left").join(refund, "id_transacao", "left")
    for name in ("qt_eventos_risco", "qt_chargebacks", "qt_risco_alto", "qt_estornos"):
        joined = joined.withColumn(name, F.coalesce(F.col(name), F.lit(0)).cast("long"))
    return joined


def customer_month(fact):
    from pyspark.sql import functions as F, Window

    monthly = (fact.where(F.col("elegivel_indicadores") & F.col("id_cliente").isNotNull())
        .groupBy("id_cliente", "data_mes").agg(
            F.count("id_transacao").alias("qt_compras"),
            F.sum("valor_bruto_brl").cast("decimal(28,2)").alias("valor_bruto_brl"),
            F.sum("valor_estornado_brl").cast("decimal(28,2)").alias("valor_estornado_brl"),
            F.sum("valor_liquido_brl").cast("decimal(28,2)").alias("valor_liquido_brl"),
            F.countDistinct("id_estabelecimento").alias("qt_estabelecimentos")))
    order = Window.partitionBy("id_cliente").orderBy("data_mes")
    monthly = monthly.withColumn("ticket_medio_liquido_brl", (F.col("valor_liquido_brl") / F.col("qt_compras")).cast("decimal(28,2)"))
    monthly = monthly.withColumn("valor_mes_anterior_brl", F.lag("valor_liquido_brl").over(order))
    return monthly.withColumn("variacao_mensal_brl", (F.col("valor_liquido_brl") - F.col("valor_mes_anterior_brl")).cast("decimal(28,2)"))


def customer_risk(fact_with_risk):
    from pyspark.sql import functions as F

    return (fact_with_risk.where(F.col("id_cliente").isNotNull())
        .groupBy("id_cliente", "data_mes").agg(
            F.count("id_transacao").alias("qt_transacoes_canonicas"),
            F.sum("qt_eventos_risco").alias("qt_eventos_risco"),
            F.sum("qt_chargebacks").alias("qt_chargebacks"),
            F.sum("qt_risco_alto").alias("qt_risco_alto"),
            F.sum("qt_estornos").alias("qt_estornos"),
            F.sum(F.when(F.col("elegivel_indicadores"), F.col("valor_estornado_brl"))
                  .otherwise(F.lit(0))).cast("decimal(28,2)").alias("valor_estornado_elegivel_brl")))


def customer_features(fact_with_risk, customer_history, cutoff):
    from pyspark.sql import functions as F

    cutoff_date = F.lit(cutoff.isoformat()).cast("date")
    end = F.date_add(cutoff_date, 1).cast("timestamp")
    known = fact_with_risk.where((F.col("data_transacao") < end) & (F.col("primeira_disponibilidade") < end))
    known = known.withColumn("_age", F.datediff(cutoff_date, F.to_date("data_transacao")))
    eligible = F.col("elegivel_indicadores")
    aggregates = known.groupBy("id_cliente").agg(
        F.sum(F.when(eligible & F.col("_age").between(0, 29), F.col("valor_liquido_brl")).otherwise(0)).cast("decimal(28,2)").alias("gasto_liquido_30d_brl"),
        F.sum(F.when(eligible & F.col("_age").between(0, 89), F.col("valor_liquido_brl")).otherwise(0)).cast("decimal(28,2)").alias("gasto_liquido_90d_brl"),
        F.sum(F.when(eligible & F.col("_age").between(0, 364), F.col("valor_liquido_brl")).otherwise(0)).cast("decimal(28,2)").alias("gasto_liquido_365d_brl"),
        F.sum(F.when(eligible & F.col("_age").between(0, 89), 1).otherwise(0)).cast("long").alias("qt_compras_90d"),
        F.sum(F.when(F.col("_age").between(0, 364), F.col("qt_eventos_risco")).otherwise(0)).cast("long").alias("qt_eventos_risco_365d"),
        F.sum(F.when(F.col("_age").between(0, 364), F.col("qt_chargebacks")).otherwise(0)).cast("long").alias("qt_chargebacks_365d"))
    customers = (_source(customer_history).where(F.col("is_current") & ~F.col("is_deleted"))
        .select("id_cliente", "version_id", "cidade", "estado", "segmento"))
    result = customers.join(aggregates, "id_cliente", "left")
    for name in ("gasto_liquido_30d_brl", "gasto_liquido_90d_brl", "gasto_liquido_365d_brl"):
        result = result.withColumn(name, F.coalesce(F.col(name), F.lit(0).cast("decimal(28,2)")))
    for name in ("qt_compras_90d", "qt_eventos_risco_365d", "qt_chargebacks_365d"):
        result = result.withColumn(name, F.coalesce(F.col(name), F.lit(0)).cast("long"))
    return result.withColumn("data_referencia", cutoff_date).withColumnRenamed("version_id", "cliente_version_id")


def build_gold(inputs: dict, cutoff):
    fact = transaction_fact(inputs["transacoes_atual"])
    with_risk = _fact_with_risk(fact, inputs["eventos_risco"], inputs["estornos"])
    return {
        "gold_fato_transacao": fact,
        "gold_dim_cliente": _source(inputs["clientes_scd2"]),
        "gold_dim_conta": _source(inputs["contas_scd2"]),
        "gold_dim_cartao": _source(inputs["cartoes_scd2"]),
        "gold_dim_estabelecimento": establishment_dimension(fact),
        "gold_cliente_mes": customer_month(fact),
        "gold_indicadores_risco": customer_risk(with_risk),
        "gold_features_cliente": customer_features(with_risk, inputs["clientes_scd2"], cutoff),
    }
