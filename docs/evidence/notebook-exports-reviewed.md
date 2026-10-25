# Exports executados dos notebooks revisados

Os exports HTML recebidos em 2026-10-25 foram abertos e os outputs embutidos foram conferidos. Todas as células estão marcadas como `finished`; as últimas células registram os status abaixo. Os arquivos preservam código, resultados tabulares, auditoria e JSON final.

| Notebook | Status e execução | Verificações observadas |
| --- | --- | --- |
| `notebooks/01_bronze_demo.html` | `BRONZE_DEMO_PASSED`, `proof_mode=FRESH` | 14 clientes, 16 contas, 21 cartões, 54 transações, 3 eventos de risco e 3 estornos. Checks incluem replay, arquivos atrasados, schema rescue e auditoria negativa. |
| `notebooks/02_silver_demo.html` | `SILVER_PIPELINE_SUCCEEDED`, run `5e3210757d82445cad0bfa0cbe38e9c2` | 111 entradas reconciliadas: 102 aprovadas, 2 duplicatas e 7 em quarentena. Outputs exibem histórico SCD2 de C001 e K001, transações antes/depois do cancelamento, estorno parcial/integral e moeda estrangeira. |
| `notebooks/03_gold_demo.html` | `GOLD_PIPELINE_SUCCEEDED`, run `ddb1e31e37d3426e8b1d97550cfe576f` | Oito produtos reconciliados: fato 50, dimensões cliente/conta/cartão/estabelecimento 12/15/20/1, cliente-mês 27, risco 27 e features 10. |

Na fato Gold, os outputs mostram `T_PARTIAL` com 100,00 bruto, 30,00 estornado e 70,00 líquido; `T_FULL` com 80,00/80,00/0,00; `T_BEFORE_CANCEL` elegível; `T_AFTER_CANCEL` não elegível por `CARD_NOT_ACTIVE`; `T_CANCELLED` não elegível por `TRANSACTION_NOT_APPROVED`; e `T_FX` não elegível por `NON_BRL`, sem métricas BRL.

O resultado informado pelo candidato para a consulta `COUNT(*)` sobre `gold_fato_transacao` foi 50, consistente com a reconciliação Gold e com o output tabular da fato. As asserções locais em `tests/test_databricks_evidence.py` verificam esses outputs exportados. Elas validam a evidência capturada; não executam Spark localmente nem substituem a execução remota.
