# NovaRota - Data Product Transacional

Case de Engenharia de Dados Sênior em Databricks Free Edition, com dados inteiramente sintéticos.

Estado: fundação e Bronze concluídas. A demonstração registrou BRONZE_DEMO_PASSED em modo FRESH: 111 linhas nas seis fontes, com reconciliação, replay, atraso, evolução de schema e auditoria verificados pelo notebook. Os 34 testes locais passaram antes dessa execução. A primeira execução Silver também concluiu com sucesso; Gold e consultas analíticas estão implementadas e aguardam execução no Databricks.

Na branch `feature/dq-and-scd`, a Silver inclui tipagem, qualidade, quarentena, canonização, SCD2, MERGE e controle de retomada. A execução informada no Databricks reconciliou 111 entradas: 102 aprovadas, 2 duplicatas e 7 em quarentena. A branch `feature/gold-data-products` acrescenta os produtos Gold e SQL analítico; sua execução remota ainda precisa de evidência. Os 34 testes locais citados acima pertencem à revisão Bronze.

- [Acesso ao workspace e primeira amostra](docs/workspace-setup.md)
- [Desenvolvimento local](docs/local-development.md)
- [Notebook para verificar o workspace](notebooks/00_workspace_smoke.ipynb)
- [Executar a Bronze das seis fontes](docs/bronze-runbook.md)
- [Executar a Silver e consultar a quarentena](docs/silver-runbook.md)
- [Contratos tipados e regras Silver](docs/silver-contracts.md)
- [Contratos Gold](docs/gold-contracts.md)
- [Executar a Gold](docs/gold-runbook.md)
- [Contratos e cenários sintéticos](docs/data_contracts.md)
- [Arquitetura](docs/architecture.md)
- [Decisões e trade-offs (ADRs)](docs/decisions.md)
- [Branches e fluxo de commits](docs/git-workflow.md)

- [Exploração e proposta de solução](docs/solution-exploration.md)
O desenvolvimento segue etapas de fundação/Bronze, Silver, Gold e demonstração integrada. O desenho e o estado de cada camada estão em [arquitetura](docs/architecture.md) e [decisões](docs/decisions.md). Testes e documentação acompanham as mudanças.

## Referências

- [Limitações da Free Edition](https://docs.databricks.com/aws/en/getting-started/free-edition-limitations)
- [Streaming em serverless](https://docs.databricks.com/aws/en/compute/serverless/streaming)

## Estrutura do repositório

O código está organizado por responsabilidade dentro do pacote Python `novarota`, em `src/`.

```text
novarota-lakehouse-case/
├── README.md
├── requirements.txt
├── src/novarota/
│   ├── config/          # configuração validada
│   ├── ingestion/       # publicação e Bronze incremental
│   ├── silver/          # canonização, SCD2, MERGE e retomada
│   ├── gold/            # fato, dimensões, comportamento, risco e features
│   ├── quality/         # contratos tipados e regras reutilizáveis
│   ├── observability/   # auditoria e logs
│   └── synthetic/       # geração das fontes fictícias
├── config/              # exemplos de parâmetros de ambiente
├── tests/
├── sql/                 # consultas analíticas versionadas
├── notebooks/
├── scripts/             # empacotamento para Databricks
└── docs/
    ├── architecture.md
    ├── decisions.md
    ├── data_contracts.md
    ├── git-workflow.md
    └── evidence/
```

Configuração de código fica em `src/novarota/config/`; arquivos JSON de ambiente ficam em `config/`. Os imports públicos existentes, como `from novarota.config import PipelineConfig`, permanecem iguais.

A base Bronze e a organização do repositório compõem a entrega inicial em `main`; `develop` integra as próximas etapas. Ver [fluxo Git](docs/git-workflow.md). Os 34 testes aprovados são anteriores à reorganização; a suíte não foi reexecutada nesta etapa.

## Executar

No Databricks, importar o ZIP criado por `python scripts/build_artifacts.py`, abrir `novarota_case/01_bronze_demo` e executar em Serverless com `catalog=workspace`, `dataset_id=case01` e `profile=sample`. O pacote fica ao lado do notebook; regras permanecem em módulos Python. O [runbook](docs/bronze-runbook.md) detalha permissões, retomada e coleta de evidência.

Para continuar a partir da Bronze existente, gerar `python scripts/build_artifacts.py --name novarota_silver_demo.zip`, importar o ZIP e executar **02_silver_demo** no mesmo workspace, com `dataset_id=case01`. O [runbook Silver](docs/silver-runbook.md) orienta configuração, retomada e interpretação dos resultados.

Após Silver SUCCEEDED, gerar `python scripts/build_artifacts.py --name novarota_gold_demo.zip`, importar o ZIP e executar **03_gold_demo** no mesmo workspace. O [runbook Gold](docs/gold-runbook.md) detalha data de corte, produtos, SQL e retomada.

Para geração local, preparar Python e apontar para as fontes:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:PYTHONPATH = (Resolve-Path src).Path
.\.venv\Scripts\python.exe -m novarota generate --output data/generated/sample --profile sample
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Em outra máquina, seguir o [setup local](docs/local-development.md). O pacote não precisa de PySpark para gerar arquivos ou executar os testes puros. Expressões Spark, Auto Loader e Delta são testados no ambiente real pelo notebook; nenhum mock substitui essa evidência.

## Evidências

- [Fundação local](docs/evidence/local-foundation.md)
- [Amostra Databricks aprovada](docs/evidence/workspace-smoke-passed.md)
- [Validação local do gerador e empacotamento](docs/evidence/local-bronze-validation.md)
- [Correção da estrutura de pastas do ZIP](docs/evidence/import-archive-fix.md)
- [Bronze das seis fontes aprovada — resumo da execução](docs/evidence/bronze-demo-passed.md)
- [Silver concluída — resumo da primeira execução](docs/evidence/silver-demo-succeeded.md)
- [Gold — implementação e verificação do pacote](docs/evidence/gold-implementation.md)

O objetivo é entregar os critérios completos do case progressivamente. Os artefatos da primeira mudança não demonstram, por si, conclusão das camadas seguintes.
