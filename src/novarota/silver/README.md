# Silver

Eventos canônicos, resolução temporal e dimensões SCD2 implementados com DataFrames e Delta MERGE. `temporal.py` resolve identidades, conflitos e intervalos; `transformations.py` processa as seis fontes na ordem de dependência.

As transformações usam `novarota.quality`, configuração de `novarota.config` e auditoria de `novarota.observability`. A Bronze permanece em `novarota.ingestion`. `pipeline.py` gerencia snapshot, staging, tentativa e retomada; `persistence.py` sincroniza destinos e reconcilia o conteúdo. Ver os guias Silver em `docs/` na raiz. A primeira execução foi informada como concluída; casos individuais e recuperação após falha continuam sem evidência específica.
