# Fluxo Git do case

O histórico registra a evolução do projeto, com autoria, datas, mensagens e merges. Os arquivos internos de planejamento ficam fora da publicação. O histórico anterior à preparação da publicação permanece em backup local.

## Branches

| Branch | Uso |
| --- | --- |
| main | Entrega inicial Bronze; Gold ainda não integrada |
| develop | Integração anterior à Gold; Gold ainda não integrada |
| feature/ingestion-framework | Organização modular da fundação/ingestão |
| feature/dq-and-scd | Silver implementada, com primeira execução demonstrada |
| feature/gold-data-products | Gold implementada; primeira execução remota informada; SQL e cenários detalhados pendentes |

O estado Gold está registrado em [evidence/gold-demo-succeeded.md](evidence/gold-demo-succeeded.md). A branch ainda não foi integrada a develop ou main. Destino da publicação privada: [Daniel-F-Alencar/NovaRota_Case](https://github.com/Daniel-F-Alencar/NovaRota_Case). As cinco branches fazem parte da publicação inicial.

## Inspecionar o estado

```powershell
cd C:\programming\novarota-lakehouse-case
git status
git branch -vv
git log --graph --oneline --decorate --all
```

## Próximos passos para fechar a entrega

1. Preservar os exports executados dos notebooks Bronze, Silver e Gold, incluindo as saídas das consultas de cenários.
2. Executar a consulta SQL de anomalias no workspace e guardar resultado e Query Profile/plano.
3. Revisar e executar a suíte local na revisão final. Ela não foi executada após a reorganização e a implementação Gold; também não há testes locais de transformação Gold registrados.
4. Depois da revisão, integrar feature/gold-data-products em develop e promover develop para main, preservando os commits existentes.
5. Confirmar o formato final combinado com o avaliador: repositório Git privado ou pacote com o histórico e as evidências.

Os resumos JSON de Bronze, Silver e Gold demonstram execuções informadas, mas não substituem os exports com células e consultas visíveis. Registrar os comandos executados e seus resultados ao atualizar este checklist.
