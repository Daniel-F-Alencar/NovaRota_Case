# Arquitetura NovaRota


## Fluxo de dados

```mermaid
flowchart LR
    G[Gerador com seed] --> M[Arquivos e manifestos]
    M --> V[Landing imutável em Volume UC]
    V --> A[Auto Loader AvailableNow por fonte]
    A --> B[Bronze Delta lexical e metadados]
    A --> O[Auditoria de execução]
    B -. proposta .-> Q[Tipagem e qualidade]
    Q -. proposta .-> X[Quarentena e avaliações]
    Q -. proposta .-> S[Silver canônica e SCD2]
    S -. futuro .-> F[Gold: fato e indicadores]
    F -. futuro .-> D[Features por data de corte e SQL]
```

Linhas contínuas representam o caminho Bronze implementado. Linhas pontilhadas representam capacidades propostas ou futuras.

## Organização do código

O layout sugerido no briefing é mantido dentro de `src/novarota/`, um namespace próprio para instalação, imports de notebooks e empacotamento. A estrutura local `novarota-lakehouse-case/` corresponde à raiz de exemplo `case-senior/`.

| Diretório | Responsabilidade | Estado |
| --- | --- | --- |
| src/novarota/config/ | Parâmetros, identificadores e caminhos derivados | Implementado |
| src/novarota/synthetic/ | Contratos materializados e massa determinística | Implementado |
| src/novarota/ingestion/ | Manifestos, publicação, Auto Loader, hash e reconciliação | Implementado |
| src/novarota/observability/ | Auditoria e logs por tentativa | Implementado |
| src/novarota/quality/ | Regras reutilizáveis e classificação de qualidade | Reservado para a Silver |
| src/novarota/silver/ | Canonização financeira e histórico SCD2 | Proposta preparada |
| src/novarota/gold/ | Produtos de consumo e features | Futuro |
| config/ | JSON de exemplo por ambiente, sem credenciais | Implementado |
| tests/ | Verificações locais e fixtures independentes | 34 testes na última execução anterior à reorganização |
| sql/ | Consultas analíticas versionadas | Futuro |
| notebooks/ | Entradas de execução e demonstração | Smoke e Bronze implementados |
| scripts/ | Build determinístico do pacote para importação | Implementado |
| docs/ | Arquitetura, decisões, contratos, guias e evidências | Mantido com cada mudança |

Os diretórios futuros têm README de escopo. A verificação de integridade de arquivos permanece em ingestion; as regras de qualidade de negócio serão adicionadas ao módulo quality na mudança correspondente.

## Recursos da execução demonstrada

- Compute: Databricks Free Edition, Serverless.
- Catálogo: `workspace`.
- Bronze: `workspace.novarota_case01_bronze`, uma tabela por fonte com prefixo `bronze_`.
- Operação: `workspace.novarota_ops.pipeline_events`.
- Volume: `/Volumes/workspace/novarota_ops/case01_files`.
- Fontes: clientes/contas/cartões CDC em JSONL; transações, eventos de risco e estornos em CSV.

Catálogo, schema, dataset, seed e referência temporal são parâmetros. O setup usa recursos gerenciados e preserva dados e checkpoints existentes. A publicação ocorre fora da ingestão e conclui com manifesto; arquivos publicados são imutáveis.

## Incrementalidade e recuperação

Cada fonte possui checkpoint e schemaLocation independentes. A execução AvailableNow termina após processar o inventário disponível. A reconciliação de manifestos compara os arquivos/linhas e permite NOOP quando tudo já está persistido. Duplicatas de negócio e valores inválidos permanecem na Bronze. CSV adicional fica recuperável em rescue.

Dados e auditoria não são uma transação única. Uma tentativa é identificada por run_id; lote lógico usa batch_id. Erros são registrados e propagados. Recuperação deve reconciliar o estado; não excluir checkpoint para corrigir regra de negócio. [Runbook Bronze](bronze-runbook.md).

## Evolução Silver


Gold calculará o produto financeiro e as features depois da Silver. A SCD2 de vigência não basta, sozinha, para reconstruir o conhecimento disponível no corte de um modelo; essa semântica será especificada na mudança Gold.

## Evidência e limites

[Resumo Bronze](evidence/bronze-demo-passed.md): transcrição fornecida pelo candidato. A amostra anterior foi conferida no navegador. Export do notebook com outputs ainda complementará a entrega final. O perfil sample demonstra correção funcional; não mede escala de produção.

A reorganização moveu config.py para config/__init__.py com imports públicos preservados e ajustou as expectativas do teste de empacotamento. A suíte não foi reexecutada nessa etapa; os 34 testes aprovados são evidência anterior à reorganização.
