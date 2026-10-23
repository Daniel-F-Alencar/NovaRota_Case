# Correção do empacotamento ZIP

Data: 2026-10-23. Erro de importação informado pelo candidato:

```json
{"error_code":"RESOURCE_DOES_NOT_EXIST","message":"The parent folder (/Workspace/Users/<conta>/novarota_bronze_demo <timestamp>/novarota) does not exist."}
```

O ZIP original declarava 20 arquivos e nenhuma entrada de diretório. A checagem anterior de CRC/sintaxe passou, mas não validava a existência das pastas antes dos arquivos na ordem do archive. A mensagem retornada é consistente com essa falha de empacotamento; a aceitação pelo serviço ainda depende da nova tentativa.

Correção: `write_archive` declara primeiro os cinco diretórios, em ordem de profundidade, e depois os arquivos. Os metadados distinguem diretórios e arquivos regulares. Há validação de caminhos e colisão arquivo/pasta. O parâmetro `--name` permite produzir `novarota_bronze_demo_v2.zip` sem ambiguidade com a primeira tentativa.

Verificações executadas:

- 34 testes locais passaram, incluindo cinco testes de empacotamento.
- Extração sequencial estrita, que não cria pais automaticamente, concluiu com os conteúdos preservados.
- Build determinístico confirmado e células Python do notebook analisadas por AST.
- ZIP v2: 25 entradas, sendo 5 diretórios e 20 arquivos; CRC sem erro.
- SHA-256: `f44e7d9dbf3d42ba6d9c115b0eba56bfb5c29ac630b6f0934acf9ecc82dd163d`.

O arquivo canônico `dist/novarota_bronze_demo.zip` também foi regenerado com o mesmo conteúdo. O nome da pasta externa sugerido pelo Databricks pode ser o nome do ZIP mais timestamp; a instrução de importação foi ajustada para não depender de um nome externo fixo.

Status: correção local verificada; reimportação no Databricks e execução das seis fontes continuam pendentes. Nenhuma pasta ou recurso remoto da tentativa anterior foi apagado.
