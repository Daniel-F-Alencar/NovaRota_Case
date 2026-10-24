# Decisões de arquitetura

ADRs resumidas em 2026-10-23. Cada decisão indica seu estado e consequências. Requisitos de negócio estão nos contratos de dados e na exploração da solução.

## ADR-001 — Pacote Python e estrutura do case

**Estado:** adotada.

**Contexto:** o briefing sugere src, config, ingestion, silver, gold, quality, observability, tests, sql, notebooks e documentação de arquitetura/decisões. O candidato escolheu requirements.txt para documentar dependências. O projeto já possui módulos importados pelos notebooks.

**Decisão:** usar layout src com namespace `novarota` e módulos irmãos por responsabilidade. Configuração passa a pacote `novarota.config`, preservando o import público. Silver e qualidade já têm implementação; Gold ainda tem diretório reservado. Arquivos de ambiente ficam na pasta config da raiz. A execução local usa PYTHONPATH=src e requirements.txt; Spark/Delta são fornecidos pelo Databricks.

**Alternativas:** módulos genéricos diretamente em src; código de todas as camadas em notebooks; camadas de transformação dentro de ingestion.

**Consequências:** instalação e imports têm um namespace único; notebooks permanecem pontos de entrada; a estrutura acrescenta um nível ao exemplo do briefing. A verificação de empacotamento acompanha a mudança de caminhos. Reexecução dos testes após esta reorganização ainda não foi realizada.

## ADR-002 — Databricks gerenciado e execução finita

**Estado:** adotada e demonstrada no caminho Bronze.

**Contexto:** o candidato usa Free Edition e dados sintéticos, sem armazenamento externo configurado.

**Decisão:** Volume Unity Catalog, tabelas Delta gerenciadas, Serverless e Auto Loader AvailableNow, com fontes sequenciais e uma execução concorrente por dataset.

**Alternativas:** bucket externo e cluster clássico; ingestão batch com descoberta de arquivos desenvolvida no projeto.

**Consequências:** setup pequeno e reproduzível na conta demonstrada. A capacidade/cota da conta limita volume e paralelismo; os resultados da amostra não comprovam desempenho em escala.

## ADR-003 — Bronze lexical e schema rescue

**Estado:** adotada e demonstrada.

**Contexto:** é necessário preservar valores inválidos e evolução das fontes para tratamento posterior.

**Decisão:** contratos explícitos de leitura como strings, metadados de origem, hash lexical canônico e campos extras em rescue. Sem deduplicação ou filtro de elegibilidade na Bronze.

**Alternativas:** inferir tipos automaticamente; descartar linhas inválidas; promover automaticamente toda coluna nova.

**Consequências:** conteúdo abc, duplicatas e dispositivo adicional permanecem auditáveis. Consumidores da Silver precisam tipar e validar deliberadamente. O arquivo original continua preservado no Volume.

## ADR-004 — Idempotência e auditabilidade

**Estado:** adotada na Bronze e implementada na Silver; primeira execução Silver concluída.

**Contexto:** repetição de tentativa e duplicata de negócio são situações distintas.

**Decisão:** publicar arquivos imutáveis com manifesto; checkpoint por fonte; reconciliar antes/depois; distinguir batch_id de run_id. Registrar falha e propagar erro. Silver deduplica identidades, versiona conteúdo e usa MERGE com origem única por chave.

**Alternativas:** sobrescrever arquivos publicados; apagar checkpoints para reprocessar; usar hash como chave única Bronze.

**Consequências:** replay operacional não acrescenta arquivos já reconciliados, mas duplicatas recebidas em arquivos novos continuam na Bronze. Dados e auditoria não formam commit único; recuperação exige reconciliação. A Silver tem implementação e uma primeira execução documentada; recuperação após falha ainda exige evidência própria.

## ADR-005 — Histórico corrigível por eventos atrasados

**Estado:** implementada na Silver; primeira execução concluída, cenário temporal individual ainda sem evidência exportada.

**Contexto:** C001-v2 chega após v3; cancelamento e deleção não podem alterar retroativamente o estado em compras anteriores à sua vigência.

**Decisão:** guardar eventos CDC canônicos e reconstruir intervalos [valid_from, valid_to) das chaves afetadas; usar vigência e sequência da origem e manter deleção lógica. Classificar conflitos sem escolher pela chegada. Preservar primeira disponibilidade para o futuro consumo por data de corte.

**Alternativas:** dimensão somente atual; aplicar SCD2 na ordem de chegada; descartar atraso por watermark de tempo do evento.

**Consequências:** permite corrigir intervalos e relações temporais; aumenta o custo de reavaliar dependentes. Na amostra, varredura completa favorece clareza e correção. A reconstrução de features sem dados futuros ficará na mudança Gold.

## ADR-006 — Histórico Git e branches por mudança

**Estado:** adotada a partir desta organização.

**Contexto:** o avaliador observará o histórico; já existiam oito commits reais antes desta etapa.

**Decisão:** preservar a sequência, autoria, datas e mensagens dos commits. Arquivos internos de planejamento ficam fora das versões publicadas, com backup local do histórico anterior à preparação da entrega. `main` recebe a entrega inicial Bronze e a organização; `develop` integra trabalho em andamento. Usar as três branches feature conforme o escopo, com merges que preservem a evolução.

**Alternativas:** reiniciar Git; reescrever commits antigos para simular branches; usar apenas um commit com a entrega completa.

**Consequências:** evolução anterior continua legível e a exclusão de arquivos de planejamento respeita a orientação do candidato. O backup local preserva os objetos e hashes originais; ele não é publicado. Mensagens Conventional Commits descrevem o diff real: feat para comportamento novo, refactor para organização sem novo comportamento, test para trabalho de testes e docs para documentação. Os exemplos do briefing orientam o formato; não são uma lista de commits a fabricar.
