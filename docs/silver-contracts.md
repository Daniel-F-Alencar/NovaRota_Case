# Contratos e regras Silver

Estado: código implementado; demonstração no Databricks pendente. A Bronze permanece lexical e preservada. As regras abaixo são executadas como expressões Spark, sem UDF Python ou coleta dos registros no driver.

## Tipos

Todos os campos do [contrato de origem](data_contracts.md) são mantidos com o mesmo nome. Campos não listados abaixo permanecem STRING com trim; enums, país e moeda são normalizados para maiúsculas.

| Campos | Tipo | Regra |
| --- | --- | --- |
| renda, limite | DECIMAL(18,2) | Não negativos; até duas casas; sem arredondamento silencioso |
| valor, valor_estorno | DECIMAL(18,2) | Positivos; até duas casas; overflow rejeitado |
| sequencia_origem | BIGINT | Inteiro positivo |
| data_abertura | DATE | YYYY-MM-DD válida e não posterior ao evento da conta |
| data_atualizacao, data_transacao, data_evento, data_estorno | TIMESTAMP | ISO 8601 UTC, Z ou +00:00, até seis dígitos de fração |
| cpf | STRING | Onze dígitos, verificadores válidos e sem sequência repetida |
| mcc | STRING | Quatro dígitos |
| moeda, pais | STRING | Três e duas letras, respectivamente; sem conversão cambial |
| dispositivo | STRING opcional | Promovido de rescue, preservando extras |

Enums: operações I/U/D; contas ATIVA/ENCERRADA e CORRENTE/POUPANCA/PAGAMENTO; cartões ATIVO/CANCELADO e CREDITO/DEBITO/MULTIPLO; transações APROVADA/PENDENTE/CANCELADA; risco SUSPEITA/FRAUDE/CHARGEBACK, severidades BAIXA/MEDIA/ALTA/CRITICA. Esses domínios são decisões do contrato sintético, não uma classificação externa completa.

Todos os campos mínimos são obrigatórios, inclusive no payload CDC de deleção previsto pelo gerador. Atualização de transação não pode anteceder a compra. Campos adicionais ficam em extras_json, uma lista ordenada de pares chave/valor, excluindo somente o _file_path técnico. Coluna nova por si só não causa rejeição.

## Identidades e hashes

- CDC: id_evento_cdc por fonte; conflito adicional por entidade, timestamp e sequência.
- Transação: id_transacao e sequencia_origem. Conflito em uma versão bloqueia as projeções dessa transação até resolução.
- Risco/estorno: id_evento e id_estorno por fonte.
- hash_linha: hash lexical da Bronze.
- hash_conteudo: SHA-256 de `normalized_v1:` mais JSON dos campos do contrato tipados, em sua ordem declarada, e extras_json; nulls explícitos e timezone UTC. Datas/decimais normalizados permitem canonizar repetições lexicalmente distintas com conteúdo equivalente.
- Para registros já rejeitados pela tipagem, hash_conteudo usa `invalid_v1:` e campos lexicais, corrupção e extras sem caminho técnico. Isso impede que um decimal inválido arredondado pelo cast pareça idêntico à versão válida; esses registros nunca são promovidos.
- occurrence_id: SHA-256 de fonte, arquivo, hash lexical, lote, contrato e payload original. Cópias indistinguíveis dentro do mesmo arquivo são agrupadas com multiplicidade; não é inventado número de linha.
- event_key: SHA-256 da identidade de origem serializada em JSON.
- version_id SCD2: SHA-256 de fonte, chave de entidade e início de vigência.

Primeira disponibilidade é o menor timestamp_ingestao Bronze da identidade. Ela é preservada entre tentativas e não equivale à data do evento. Views SCD2 representam vigência corrigida; uma futura feature por corte deverá usar também histórico de disponibilidade/avaliações.

## Qualidade e quarentena

As avaliações guardam payload original, proveniência, versão de regras e todos os motivos aplicáveis. Códigos principais: REQUIRED, INVALID_TYPE, INVALID_DECIMAL, INVALID_RANGE, INVALID_SEQUENCE, INVALID_UTC, INVALID_DATE, INVALID_ENUM, INVALID_CODE, INVALID_CPF, INVALID_MCC, CORRUPT_RECORD, INVALID_RESCUE, MISSING_PROVENANCE, IDENTITY_CONFLICT, TEMPORAL_POSITION_CONFLICT, TRANSACTION_CONFLICT, REFERENCE_NOT_FOUND, REFERENCE_DELETED, EVENT_BEFORE_TRANSACTION, UPDATE_BEFORE_TRANSACTION, OPENING_AFTER_EVENT, REFUND_CURRENCY_MISMATCH e REFUND_EXCEEDS_PURCHASE. Alguns códigos recebem o nome do campo como sufixo.

Por grupo de ocorrência, qt_aprovadas é 0 ou 1, qt_duplicatas conserva cópias idênticas restantes e qt_quarentena conserva toda a multiplicidade rejeitada. A soma dessas três quantidades precisa coincidir com as linhas Bronze da fonte. Uma ocorrência representante válida recebe APROVADA, mesmo que seu grupo inclua cópias contabilizadas como duplicatas.

`silver_classificacoes` mantém a avaliação atual; a view `silver_quarentena` filtra qt_quarentena>0; `silver_avaliacoes` guarda cada tentativa e permite observar a saída de um registro da quarentena. Reavaliar todo o snapshot permite recuperar referências que chegaram depois e remover projeções que se tornaram conflitantes.

## Temporalidade e valores financeiros

SCD2 usa [valid_from, valid_to), com limite final null no último estado conhecido. Maior sequência vence entre eventos válidos no mesmo instante; eventos intermediários ficam no ledger. Evento rejeitado com posição conhecida encerra a vigência anterior e deixa lacuna até o próximo estado válido. Ordem impossível de determinar bloqueia a projeção da chave. Tombstones preservam o passado, com is_deleted=true.

Transações resolvem cartão, conta e cliente na data da compra. Cancelamento, encerramento e moeda estrangeira são estados válidos; elegivel_brl e motivos_inelegibilidade indicam consumo financeiro permitido. Transação cancelada ou posterior ao cancelamento do cartão permanece consultável. Uma versão mais recente inválida não provoca retorno silencioso à versão atual anterior.

Risco e estornos referenciam a transação atual canônica e não podem anteceder a compra. Estornos devem usar a mesma moeda; a soma é feita após deduplicação. Se o conjunto excede o valor original, todos os estornos desse conjunto são rejeitados e a transação fica não reconciliada. `valor_estornado_validado` soma apenas eventos aceitos; `estornos_reconciliados` precisa ser verdadeiro antes de tratar esse total como completo. Nenhum cálculo de gasto líquido Gold é entregue nesta etapa.
