# Desenvolvimento local

Python 3.10+ executa o gerador e os testes sem Spark ou dependências externas. Databricks fornece Spark no ambiente remoto. Os testes locais usam `unittest` da biblioteca padrão.

```powershell
cd C:\programming\novarota-lakehouse-case
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Se `python` abrir a Microsoft Store, instale Python ou use o executável que já estiver disponível. Nesta sessão foi usado o Python 3.12.14 do runtime do app; esse caminho não é dependência do projeto. Usar diretamente o executável da venv evita depender da política de scripts do PowerShell.

Nesta sessão uma `.venv` já foi criada e o wheel 0.1.0 foi instalado nela. O comando `.\.venv\Scripts\python.exe -m novarota --version` funciona sem ativar scripts.

Alternativa para rodar fontes sem instalar o pacote: definir `$env:PYTHONPATH = (Resolve-Path src).Path` e executar `python -m unittest discover -s tests -v`.

Copiar `config/dev.example.json` para `config/dev.local.json`, ajustar o catálogo existente e os nomes autorizados. Configurações `.local.json` são ignoradas pelo Git. IDs SQL aceitam apenas letras, dígitos e underscore; paths do Volume são derivados desses IDs para impedir interpolação arbitrária em SQL.

`run_id` é criado a cada tentativa; `batch_id` identifica o lote lógico. `mode=reprocess` e intervalo são validados para as próximas camadas; a ingestão Bronze não deve apagar ou reinicializar checkpoints para reprocessar regras de negócio.

## Gerar e verificar dados

```powershell
.\.venv\Scripts\python.exe -m novarota generate --output data/generated/sample --profile sample
.\.venv\Scripts\python.exe -m novarota verify --manifest data/generated/sample/batch_001_initial/manifest.json
.\.venv\Scripts\python.exe -m novarota publish --manifest data/generated/sample/batch_001_initial/manifest.json --landing data/landing --published data/published
```

Gerar nao publica arquivos na landing. Escolher diretorios separados para seeds, referencias ou perfis diferentes. Publicacao local valida a logica de arquivo; nao substitui ingestao Delta. `data/generated/`, `data/landing/` e manifestos de execucao ficam fora do Git.

## Empacotar

```powershell
.\.venv\Scripts\python.exe scripts/build_artifacts.py
```

O ZIP em `dist/novarota_bronze_demo.zip` contem notebook IPYNB, fontes do pacote e guias, sem dados de pessoas, credenciais, outputs ou PDF do briefing. O build e deterministico para as mesmas fontes. Para reconstruir o wheel: `python -m pip wheel --no-deps -w dist .`. Depois de mudar codigo local, reinstalar o pacote na venv ou usar PYTHONPATH=src durante desenvolvimento para evitar testar versao antiga instalada.
