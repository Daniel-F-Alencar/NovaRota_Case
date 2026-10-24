# Quality

Contratos tipados e validações de negócio reutilizáveis da Silver, implementados em `contracts.py` e `rules.py`. CPF, campos obrigatórios, enums, datas UTC, decimais e proveniência são avaliados com expressões Spark, sem UDF Python.

As verificações em `novarota.ingestion` tratam integridade de arquivos e fidelidade Bronze. Regras de referência temporal e canonização ficam em `novarota.silver`. Consultar `docs/silver-contracts.md` na raiz para códigos, tipos e identidades. A demonstração real da Silver ainda está pendente.
