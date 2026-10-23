# Demonstração Bronze aprovada

Fonte: saída da última célula de `01_bronze_demo`, copiada pelo candidato nesta conversa em 2026-10-23, após confirmar importação e execução bem-sucedidas. O JSON está preservado em [bronze-demo-passed.json](bronze-demo-passed.json). Esta é uma transcrição fornecida pelo usuário; não é uma consulta independente das tabelas nem um notebook exportado com outputs.

Resultado informado: **BRONZE_DEMO_PASSED**, modo **FRESH**, concluído em 2026-10-23 às 23:06:43 UTC (20:06:43 em São Paulo). O modo indica ausência de manifestos publicados no início da demonstração, conforme o código versionado do notebook.

| Fonte | Linhas Bronze |
| --- | ---: |
| clientes_cdc | 14 |
| contas_cdc | 16 |
| cartoes_cdc | 21 |
| transacoes | 54 |
| eventos_risco | 3 |
| estornos | 3 |
| **Total** | **111** |

Recursos: catálogo `workspace`, schema `novarota_case01_bronze`, Volume `/Volumes/workspace/novarota_ops/case01_files`. Cinco tentativas cobrem quatro lotes e o replay. Na ordem do laço do notebook:

| Etapa | run_id |
| --- | --- |
| Inicial | `58198cd0b51e4ef1b9263d3c424f4256` |
| Incremental | `df8d7a3461da48ba987052c65200f1f2` |
| Replay do incremental | `0b4a5648b158472cb2e24b690e3feccc` |
| Atraso | `abdc49c35cff434bbe55618634447baa` |
| Evolução de schema | `759db7db5b154051a50d0c730d769b73` |

A tentativa negativa `a0eadd6a8fb94273bbaa5a2ac4c6e9ec` exercita lote não publicado e exige um evento FAILED na auditoria; essa falha esperada faz parte do sucesso da demonstração.

O resumo confirma reconciliação das seis fontes com manifestos, carga inicial, incremento, replay, arquivos atrasados, duplicatas preservadas, valor inválido bruto, coluna resgatada, hash canônico e auditoria negativa. O código só emite o resumo depois das asserções correspondentes. As 111 linhas coincidem com o total dos quatro lotes sample registrado na validação local (79 + 21 + 10 + 1).

A publicação imutável possui testes locais específicos; o resumo remoto comprova publicação/ingestão sequencial em Volume, mas não relata uma tentativa de adulterar arquivos nesse Volume. Replay sem novas linhas também pode usar a reconciliação NOOP; o comportamento do checkpoint já foi exercitado na amostra inicial.

Os 34 testes locais constam da [correção do ZIP](import-archive-fix.md); não foram executados novamente nesta atualização documental. Nenhum resultado Silver, SCD2 ou Gold foi produzido por esta demonstração.

Para a entrega final, complementar com export IPYNB/HTML incluindo outputs e link do notebook executado, permitindo inspeção das consultas e da auditoria. Esses arquivos ainda não foram recebidos; a evidência disponível agora é o resumo acima e a amostra anterior conferida no navegador.
