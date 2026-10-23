# Fluxo Git do case

O repositório fica em `C:\programming\novarota-lakehouse-case`. Os commits anteriores à organização de branches foram preservados com suas datas e conteúdo reais.

## Branches

| Branch | Uso |
| --- | --- |
| main | Base Bronze demonstrada e evidência registrada |
| develop | Integração da organização e propostas em andamento |
| feature/ingestion-framework | Organização modular da fundação/ingestão |
| feature/dq-and-scd | Proposta e implementação futura de qualidade e histórico |
| feature/gold-data-products | Reservada para o trabalho Gold |

Branches feature são locais. Gold ainda não tem implementação. Uma branch existir não significa que sua capacidade esteja concluída. Atualmente não há remoto Git configurado; commits e merges desta sessão são locais.

## Inspecionar o estado

```powershell
cd C:\programming\novarota-lakehouse-case
git status
git branch -vv
git log --graph --oneline --decorate --all
```

## Próximo trabalho Silver

Começar com diretório de trabalho limpo e atualizar a branch com o estado integrado:

```powershell
git switch feature/dq-and-scd
git merge --ff-only develop
```


- `feat: implementa canonização de eventos CDC`
- `refactor: separa regras de qualidade em módulo reutilizável`
- `test: cobre conflitos e eventos CDC atrasados`
- `docs: registra evidências da demonstração Silver`

Registrar a revisão, os comandos executados e seus resultados antes de afirmar que uma entrega está validada. Os 34 testes locais aprovados atualmente documentados pertencem à revisão anterior à reorganização.

Depois da implementação e revisão, integrar a feature em develop com merge que preserve seus commits. A promoção de develop para main acompanha uma entrega demonstrada e revisada. Nenhum commit de implementação Silver/Gold deve ser criado enquanto só existirem propostas e diretórios reservados.
