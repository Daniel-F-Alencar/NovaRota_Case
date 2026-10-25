# Suíte local aprovada

Data: 2026-10-25. Branch: feature/gold-data-products. Python virtual environment do projeto, PYTHONPATH apontado para src.

Comando executado:

```powershell
New-Item -ItemType Directory -Force .test-tmp | Out-Null
$env:PYTHONPATH = (Resolve-Path src).Path
$env:TMP = (Resolve-Path .test-tmp).Path
$env:TEMP = $env:TMP
$env:TMPDIR = $env:TMP
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Resultado nesta revisão: 40 testes executados, todos aprovados. A primeira tentativa desta revisão usou a pasta temporária padrão isolada do Windows e falhou por permissão ao criar arquivos ZIP e fixtures. A repetição direcionou TMP, TEMP e TMPDIR para a pasta ignorada .test-tmp dentro do repositório; assim os testes de publicação e geração também passaram.

A suíte cobre gerador sintético, manifests/publicação, reconciliação, configuração, auditoria, hashing, empacotamento e, agora, as evidências HTML executadas da Bronze/Silver/Gold, a saída CSV/perfil da consulta SQL e as janelas da versão atual do SQL. As novas asserções de Databricks estão em [test_databricks_evidence.py](../../tests/test_databricks_evidence.py). Elas fazem parse dos exports e conferem os outputs registrados. Não executam DataFrames Spark nem substituem testes locais de transformação Spark; a evidência de transformação continua sendo a execução real no Databricks.

Os módulos estão organizados em `tests/`: `test_synthetic.py` valida dados e cenários; `test_publication.py` e `test_reconciliation.py` cobrem publicação e reconciliação; `test_config.py`, `test_audit.py`, `test_hashing.py` e `test_artifacts.py` cobrem configuração, auditoria, hashes e empacotamento. A suíte pode ser repetida na raiz do repositório:

```powershell
New-Item -ItemType Directory -Force .test-tmp | Out-Null
$env:PYTHONPATH = (Resolve-Path src).Path
$env:TMP = (Resolve-Path .test-tmp).Path
$env:TEMP = $env:TMP
$env:TMPDIR = $env:TMP
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```
