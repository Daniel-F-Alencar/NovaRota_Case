# Amostra Databricks executada

Data: 2026-10-23. Executada pelo candidato na interface; saídas conferidas por leitura do notebook autenticado.

- [Notebook executado](https://dbc-ba28e3ae-73b2.cloud.databricks.com/editor/notebooks/1109191637403049?o=7474657033449260)
- Ambiente: Free Edition, Python/Spark Connect, Serverless.
- Parâmetros: `catalog=workspace`, `schema=novarota_smoke`.
- Volume: `/Volumes/workspace/novarota_smoke/smoke_files`.
- Tabela: `workspace.novarota_smoke.bronze_probe`.
- Início informado pela primeira célula: `2026-10-23T22:29:02.964099+00:00` (19:29:02 em America/Sao_Paulo).
- Fim informado pela última célula: `2026-10-23T22:29:56.725294+00:00` (19:29:56 em America/Sao_Paulo).

Saída inicial observada: `{'stage': 'initial_or_resume', 'rows': 1}`.

Saída final observada:

```json
{"status": "PASSED", "checks": ["initial", "increment", "rescue_csv", "invalid_lexical_value", "replay", "setup_preserves_state"], "rows": 2, "finished_at": "2026-10-23T22:29:56.725294+00:00"}
```

Tabela exibida:

| id | valor | _rescued_data |
| --- | --- | --- |
| smoke-001 | 100.00 | null |
| smoke-002 | abc | `{"dispositivo":"mobile-sintetico","_file_path":"/Volumes/workspace/novarota_smoke/smoke_files/landing/batch_002.csv"}` |

As três células de código aparecem como concluídas. O código executado verifica a criação de schema/Volume, ingestão inicial e incremental em Delta, preservação da coluna adicional em CSV, valor inválido preservado como string, replay e repetição do setup preservando tabela e checkpoint.

Limite desta evidência: dois registros em uma fonte de teste. Ainda não comprova a ingestão das seis fontes do case, metadados completos, auditoria do pipeline ou cenários de negócio. O notebook local permanece sem outputs; este registro é uma transcrição das saídas observadas na interface, não um export com outputs.
