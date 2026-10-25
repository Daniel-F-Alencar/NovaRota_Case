# Suíte local aprovada

Data: 2026-10-25. Branch: feature/gold-data-products. Python virtual environment do projeto, PYTHONPATH apontado para src.

Comando executado:

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
..venv\Scripts\python.exe -m unittest discover -s tests -v
```

Resultado: 34 testes executados, todos aprovados. A primeira tentativa usou a pasta temporária padrão isolada do Windows e falhou por permissão ao criar arquivos ZIP e fixtures. A repetição direcionou TMP, TEMP e TMPDIR para a pasta ignorada .test-tmp dentro do repositório; assim os testes de publicação e geração também passaram.

A suíte cobre gerador sintético, manifests/publicação, reconciliação, configuração, auditoria, hashing e empacotamento. Ela não executa DataFrames Spark nem testes diretos das transformações Silver/Gold; os cenários dessas camadas ainda precisam de evidência do notebook Databricks ou de testes de transformação apropriados.
