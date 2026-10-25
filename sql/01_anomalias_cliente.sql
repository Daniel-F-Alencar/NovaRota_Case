-- Substituir __CATALOG__, __GOLD_SCHEMA__ e __DATASET_KEY__ pelos valores do runbook.
-- Grão da saída: cliente, mês, cidade e segmento vigentes nas compras daquele grupo.
WITH compras AS (
    SELECT f.id_cliente, f.data_mes, d.cidade, d.segmento,
           f.id_transacao, f.valor_liquido_brl
    FROM __CATALOG__.__GOLD_SCHEMA__.gold_fato_transacao f
    JOIN __CATALOG__.__GOLD_SCHEMA__.gold_dim_cliente d
      ON f._dataset_id = d._dataset_id AND f.cliente_version_id = d.version_id
    WHERE f._dataset_id = '__DATASET_KEY__'
      AND f.elegivel_indicadores = true
),
mensal AS (
    SELECT id_cliente, data_mes, cidade, segmento,
           COUNT(*) AS qt_compras,
           SUM(valor_liquido_brl) AS gasto_liquido_brl
    FROM compras
    GROUP BY id_cliente, data_mes, cidade, segmento
),
-- Um registro por cliente, mês e grupo; o baseline próprio acompanha períodos observados no mesmo grupo.
historico AS (
    SELECT m.*,
           ROW_NUMBER() OVER (PARTITION BY id_cliente, cidade, segmento ORDER BY data_mes DESC) AS ordem_recente,
           LAG(gasto_liquido_brl) OVER (PARTITION BY id_cliente, cidade, segmento ORDER BY data_mes) AS gasto_anterior_brl,
           AVG(gasto_liquido_brl) OVER (PARTITION BY id_cliente, cidade, segmento ORDER BY data_mes
                ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING) AS baseline_proprio_brl,
           COUNT(*) OVER (PARTITION BY id_cliente, cidade, segmento ORDER BY data_mes
                ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING) AS periodos_baseline,
           FIRST_VALUE(data_mes) OVER (PARTITION BY id_cliente, cidade, segmento ORDER BY data_mes
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS primeiro_mes_observado
    FROM mensal m
),
pares AS (
    SELECT data_mes, cidade, segmento,
           COUNT(DISTINCT id_cliente) AS qt_clientes_pares,
           AVG(gasto_liquido_brl) AS media_pares_brl
    FROM mensal
    GROUP BY data_mes, cidade, segmento
),
comparado AS (
    SELECT h.*, p.qt_clientes_pares, p.media_pares_brl,
           NTILE(4) OVER (PARTITION BY h.data_mes, h.cidade, h.segmento
                          ORDER BY h.gasto_liquido_brl DESC, h.id_cliente) AS quartil_gasto
    FROM historico h
    JOIN pares p ON h.data_mes = p.data_mes AND h.cidade = p.cidade AND h.segmento = p.segmento
)
SELECT id_cliente, data_mes, cidade, segmento, qt_compras, gasto_liquido_brl,
       gasto_anterior_brl, baseline_proprio_brl, media_pares_brl,
       periodos_baseline, qt_clientes_pares, primeiro_mes_observado,
       ordem_recente, quartil_gasto,
       CASE WHEN periodos_baseline < 2 OR qt_clientes_pares < 3 THEN 'BASELINE_INSUFICIENTE'
            WHEN baseline_proprio_brl <= 0 OR media_pares_brl <= 0 THEN 'BASELINE_ZERO'
            WHEN gasto_liquido_brl > 2 * baseline_proprio_brl
             AND gasto_liquido_brl > 2 * media_pares_brl THEN 'ANOMALIA'
            ELSE 'NORMAL' END AS classificacao_comportamento
FROM comparado
ORDER BY data_mes DESC, id_cliente, cidade, segmento;
