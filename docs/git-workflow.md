# Fluxo Git do case

O histórico registra a evolução do projeto, com autoria, datas, mensagens e merges. Os arquivos internos de planejamento ficam fora da publicação. O histórico anterior à preparação da publicação permanece em backup local.

## Branches

| Branch | Uso |
| --- | --- |
| main | Entrega Bronze, Silver e Gold; branch de entrega |
| develop | Integração Bronze, Silver e Gold; promovida para main |
| feature/ingestion-framework | Organização modular da fundação/ingestão |
| feature/dq-and-scd | Silver implementada, com primeira execução demonstrada |
| feature/gold-data-products | Gold implementada e integrada a develop; contém evidências HTML, CSV e Query Profile |

O estado de execução Gold está em [evidence/gold-demo-succeeded.md](evidence/gold-demo-succeeded.md), e os exports dos notebooks estão em [evidence/notebook-exports-reviewed.md](evidence/notebook-exports-reviewed.md). A feature Gold foi integrada a develop e develop foi promovida a main, preservando o merge remoto anterior da Silver. Destino da publicação privada: [Daniel-F-Alencar/NovaRota_Case](https://github.com/Daniel-F-Alencar/NovaRota_Case). As cinco branches fazem parte da publicação.

## Inspecionar o estado

```powershell
cd C:\programming\novarota-lakehouse-case
git status
git branch -vv
git log --graph --oneline --decorate --all
```

## Próximos passos para fechar a entrega

1. Exports dos notebooks Bronze, Silver e Gold preservados e revisados, incluindo as saídas dos cenários.
2. CSV e Query Profile da consulta SQL preservados. Reexecutar `sql/01_anomalias_cliente.sql`, porque o perfil atual registra a versão anterior das janelas analíticas; veja [instruções e detalhe da evidência](evidence/anomalias-sql-execution.md).
3. Suíte local: 40 testes aprovados; ver [evidência](evidence/local-test-suite-passed.md). As transformações Spark foram executadas nos notebooks Databricks, enquanto as novas asserções locais conferem os outputs exportados e a estrutura SQL.
4. Feature Gold integrada em develop; develop promovida para main, mantendo os commits e o histórico de merges.
5. Confirmar o formato final combinado com o avaliador: repositório Git privado ou pacote com o histórico e as evidências.

Os exports HTML preservam células e consultas visíveis; os resumos JSON ajudam a localizar os run IDs e as volumetrias. Ao reexecutar o SQL atualizado, substituir a evidência anterior e registrar o novo ID do perfil.
