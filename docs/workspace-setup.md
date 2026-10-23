# Acesso ao workspace e primeira amostra

Na Free Edition, concluir o cadastro cria um workspace com compute serverless e armazenamento. Acesse o [cadastro/login oficial da Free Edition](https://login.databricks.com/?dbx_source=docs&intent=CE_SIGN_UP) com a conta existente. Fonte: [documentacao Databricks](https://docs.databricks.com/aws/en/getting-started/free-edition).

Quando o workspace abrir, copie o endereco da barra do navegador. Esse endereco permite identificar a conta; nao compartilhe senhas, tokens ou codigos de login.

## Verificar recursos

1. Abra o Catalog Explorer e identifique um catalogo existente com permissao para criar schema. O valor `workspace` nos exemplos e apenas um valor inicial editavel.
2. Importe `notebooks/00_workspace_smoke.ipynb` no workspace. Use Python e o compute serverless disponivel.
3. Preencha o parametro `catalog` com o catalogo identificado. O schema isolado padrao e `novarota_smoke`.
4. Execute as celulas na ordem. O notebook cria schema/Volume dedicados, publica um CSV com um registro, ingere via Auto Loader e publica um segundo CSV com coluna nova.
5. Confira a saida final `status: PASSED`, duas linhas e o campo adicional em `_rescued_data`. O notebook testa tambem replay e preservacao do estado ao repetir setup.

Essa amostra ainda precisa ser executada na conta do candidato. Sua existencia no repositorio ou validacao de sintaxe local nao demonstra suporte real do workspace.

Nao apagar tabelas nem checkpoints para repetir o teste. Um novo schema permite uma demonstracao independente. A limpeza dos recursos e uma operacao separada.
