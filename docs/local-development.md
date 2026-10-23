# Desenvolvimento local

Python 3.10+ executa o gerador e os testes sem Spark ou dependências externas. Databricks fornece Spark no ambiente remoto. Os testes locais usam `unittest` da biblioteca padrão.

```powershell
cd C:\programming\novarota-lakehouse-case
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Se `python` abrir a Microsoft Store, instale Python ou use o executável que já estiver disponível. Nesta sessão foi usado o Python 3.12.14 do runtime do app; esse caminho não é dependência do projeto. Usar diretamente o executável da venv evita depender da política de scripts do PowerShell.

Alternativa para rodar fontes sem instalar o pacote: definir `$env:PYTHONPATH = (Resolve-Path src).Path` e executar `python -m unittest discover -s tests -v`.

Copiar `config/dev.example.json` para `config/dev.local.json`, ajustar o catálogo existente e os nomes autorizados. Configurações `.local.json` são ignoradas pelo Git. IDs SQL aceitam apenas letras, dígitos e underscore; paths do Volume são derivados desses IDs para impedir interpolação arbitrária em SQL.

`run_id` é criado a cada tentativa; `batch_id` identifica o lote lógico. `mode=reprocess` e intervalo são validados para as próximas camadas; a ingestão Bronze não deve apagar ou reinicializar checkpoints para reprocessar regras de negócio.
