# NovaRota - Data Product Transacional

Case de Engenharia de Dados Sênior em Databricks Free Edition, com dados inteiramente sintéticos.


- [Acesso ao workspace e primeira amostra](docs/workspace-setup.md)
- [Desenvolvimento local](docs/local-development.md)
- [Notebook para verificar o workspace](notebooks/00_workspace_smoke.ipynb)
- [Executar a Bronze das seis fontes](docs/bronze-runbook.md)
- [Contratos e cenários sintéticos](docs/data_contracts.md)

- [Exploração e proposta de solução](docs/solution-exploration.md)

O ciclo é Explore → Propose → Review → Apply → Archive. A primeira mudança cobre a fundação, os dados sintéticos e a Bronze; mudanças seguintes cobrirão Prata, Ouro e demonstração integrada. Testes e documentação acompanham cada mudança.


## Referências

- [Limitações da Free Edition](https://docs.databricks.com/aws/en/getting-started/free-edition-limitations)
- [Streaming em serverless](https://docs.databricks.com/aws/en/compute/serverless/streaming)

## Executar

No Databricks, importar o ZIP criado por `python scripts/build_artifacts.py`, abrir `novarota_case/01_bronze_demo` e executar em Serverless com `catalog=workspace`, `dataset_id=case01` e `profile=sample`. O pacote fica ao lado do notebook; regras permanecem em módulos Python. O [runbook](docs/bronze-runbook.md) detalha permissões, retomada e coleta de evidência.

Para geração local, a venv já preparada nesta sessão permite:

```powershell
.\.venv\Scripts\python.exe -m novarota generate --output data/generated/sample --profile sample
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Em outra máquina, seguir o [setup local](docs/local-development.md). O pacote não precisa de PySpark para gerar arquivos ou executar os testes puros. Expressões Spark, Auto Loader e Delta são testados no ambiente real pelo notebook; nenhum mock substitui essa evidência.

## Evidências

- [Fundação local](docs/evidence/local-foundation.md)
- [Amostra Databricks aprovada](docs/evidence/workspace-smoke-passed.md)
- [Validação local do gerador e empacotamento](docs/evidence/local-bronze-validation.md)
- [Correção da estrutura de pastas do ZIP](docs/evidence/import-archive-fix.md)

O objetivo é entregar os critérios completos do case progressivamente. Os artefatos da primeira mudança não demonstram, por si, conclusão das camadas seguintes.
