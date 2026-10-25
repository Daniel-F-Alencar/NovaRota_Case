# Contratos Gold

Estado: código implementado na branch `feature/gold-data-products`; a primeira execução informou sucesso e reconciliou os oito destinos. O resumo está em [evidence/gold-demo-succeeded.md](evidence/gold-demo-succeeded.md). Os produtos leem somente versões Delta de uma Silver com `silver_execution_state.status=SUCCEEDED` para o dataset exato. Os oito destinos possuem `_dataset_id`, `_rule_version=gold_v1` e `_content_hash`.

| Produto | Grão/chave | Regra |
| --- | --- | --- |
| `gold_fato_transacao` | `id_transacao` atual canônico | Uma linha por `transacoes_atual`, inclusive cancelada, USD ou não elegível. Guarda chaves de versões temporais, status, moeda, valores, motivos e primeira disponibilidade. |
| `gold_dim_cliente` | `version_id` | SCD2 Silver, inclusive intervalos históricos e deleção lógica. |
| `gold_dim_conta` | `version_id` | SCD2 Silver, inclusive conta encerrada. |
| `gold_dim_cartao` | `version_id` | SCD2 Silver, inclusive cartão cancelado/tombstone. |
| `gold_dim_estabelecimento` | `id_estabelecimento` | Representação da transação mais recente, com desempate por ID; conta variantes distintas de nome/MCC. |
| `gold_cliente_mes` | `id_cliente`, `data_mes` | Somente compras elegíveis; soma BRL bruto, estornado e líquido, quantidade, ticket líquido, diversidade e diferença para mês anterior observado. |
| `gold_indicadores_risco` | `id_cliente`, `data_mes` | Risco e estorno agregados por transação antes do cliente/mês; eventos atribuídos ao mês da compra. Conta chargebacks, risco alto, estornos e transações canônicas. |
| `gold_features_cliente` | `id_cliente`, `data_referencia` | Uma fotografia da Silver atual conhecida ao fim do dia escolhido; janelas 30/90/365 dias e contagens de risco. Mantém somente clientes atuais não deletados. |

`elegivel_indicadores = elegivel_brl AND estornos_reconciliados`. Para essa condição, `valor_bruto_brl=valor`, `valor_estornado_brl=valor_estornado_validado` e `valor_liquido_brl=valor-valor_estornado_validado`. Para os demais casos, esses três valores são nulos; a linha permanece na fato e `motivos_exclusao` explica o motivo. Não há conversão de USD para BRL. `T_PARTIAL` deve produzir 100/30/70; `T_FULL`, 80/80/0. Chargeback é evento de risco e nunca subtração adicional.

`gold_cliente_mes` usa o mês da compra, não da chegada do arquivo ou do estorno. `gold_indicadores_risco` também atribui risco e estorno ao mês da compra para permitir comparação; uma visão de fluxo de caixa pelo mês do estorno seria outro produto. O risco inclui eventos de transações canônicas mesmo quando a compra é inelegível para gasto BRL. Seu valor estornado BRL soma apenas compras elegíveis.

O corte de `gold_features_cliente` é de **fim de dia UTC**. A execução recusa `feature_date` anterior à data UTC de conclusão da Silver atual. Eventos da fato só entram se `data_transacao` e `primeira_disponibilidade` forem anteriores ao dia seguinte. Como a fonte é um snapshot Silver corrigido, não se oferecem cortes anteriores à sua publicação nem se afirma haver uma série histórica de treino. O produto contém somente a data de corte desta execução; uma nova execução substitui o snapshot lógico do dataset. Reconstituir múltiplas datas de treinamento exigiria snapshots Silver históricos e reavaliação de dependências como eram conhecidas em cada corte.
