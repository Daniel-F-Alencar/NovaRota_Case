# Fundação local: evidência executada

Data da sessão: 2026-10-23. Ambiente: Windows, Python 3.12.14 do runtime local. Esta evidência não representa execução Databricks.

Verificações realizadas:

- `python -m unittest discover -s tests -v`: quatro testes executados, todos passaram. Cobertura: parâmetros obrigatórios/desconhecidos, IDs SQL, datas/modo, seed, intervalo e distinção entre batch_id e run_id.
- `python -m novarota config --file config/dev.example.json`: configuração validada, catálogo de exemplo e caminho de Volume resolvidos. Imports locais usaram `PYTHONPATH=src`.
- `git check-ignore .venv/example data/generated/example.json config/dev.local.json .env`: todos ignorados.
- Notebook `00_workspace_smoke.ipynb`: JSON carregado e sintaxe de cada célula Python compilada. Não executado contra Spark; saídas do notebook continuam vazias.

A instalação do pacote em ambiente independente e as verificações de Delta/Auto Loader, replay e campos resgatados dependem das próximas execuções. Não confundir o teste da configuração com um teste da ingestão.
