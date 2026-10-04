# Rodada 004 — Fase 1: PostgreSQL provisionável

## Identificação

- **Projeto:** DB Operations Lab — Resilient Multi-Database Platform
- **Fase:** 1 — PostgreSQL provisionável
- **Rodada:** 004
- **Agentes:** DBA PostgreSQL, DevOps/Automação e QA/Incidentes
- **Data/hora:** 2026-10-03 19:47:35 -03:00 (America/Sao_Paulo)
- **Status:** concluída e validada contra PostgreSQL 16.4 em Docker

## Objetivo

Implementar o primeiro fluxo operacional real do laboratório: provisionamento idempotente, migrations, roles com permissões separadas, health check, logs JSON, validação de espaço e códigos de saída controlados.

Backup, restore, PITR, tuning, exporters e dashboards ficaram fora desta rodada porque pertencem às fases seguintes.

## Estado antes da rodada

- O Compose possuía somente a fundação do PostgreSQL, sem CLI, migrations ou roles específicas.
- A pasta `automation/` não tinha código executável.
- O banco ainda não possuía o schema do domínio nem tabela de controle de migrations.
- A dependência `psycopg` não estava instalada no Python local.

## Alterações realizadas

### `.env.example`

Adicionadas variáveis para credenciais de aplicação, operador, somente leitura e monitoramento, além do caminho e limite mínimo de espaço usado pelo health check.

Nenhuma senha real foi adicionada. O `.env` local usado durante a validação contém somente credenciais de laboratório e está ignorado pelo Git.

### `automation/requirements.txt`

Adicionada a dependência pinada `psycopg[binary]==3.2.1` para conexão PostgreSQL no Python 3.12/Windows.

### `automation/dbops.py`

Implementada a CLI da Fase 1 com:

- comandos `provision` e `health-check`;
- carregamento simples de `.env` sem sobrescrever variáveis já exportadas;
- validação de variáveis obrigatórias e portas;
- logs JSON no stderr;
- códigos de saída `0`, `2`, `3`, `4` e `5`;
- conexão com timeout de 5 segundos;
- criação ou reconciliação de roles sem superuser, createdb, createrole ou replication;
- concessão do role nativo `pg_monitor` ao usuário de monitoramento;
- aplicação ordenada e idempotente de migrations;
- tabela `public.schema_migrations` para registrar versões aplicadas;
- grants separados para aplicação, operador e somente leitura;
- privilégios padrão para tabelas e sequences futuras;
- health check de versão, banco, usuário, tamanho do banco, tabelas, migrations, roles e espaço em disco.

Durante a validação foi corrigido um erro de DDL: PostgreSQL não aceita `$1` diretamente na cláusula `PASSWORD` de `CREATE ROLE`/`ALTER ROLE`. O código passou a usar `psycopg.sql.Literal` para escapar o valor sem concatenação manual.

### `migrations/001_initial_schema.sql`

Criado o schema inicial de chamados com `customers`, `tickets` e `ticket_events`, incluindo chaves estrangeiras, checks, timestamps e índices compostos preparados para futuras demonstrações de performance.

### `automation/README.md`

Documentados preparação do ambiente virtual, criação do `.env`, subida do PostgreSQL, comandos da CLI e códigos de saída.

### `tests/test_dbops.py`

Criados testes unitários para carregamento de `.env` sem sobrescrever variável de processo e rejeição de configuração sem senha de role.

### `.env` local

Criado apenas para validação local. Como a porta `5432` apresentou autenticação inconsistente no encaminhamento do Docker Desktop neste host, o `.env` local usa `POSTGRES_PORT=15432`. O `.env.example`, o Compose e a documentação continuam com `5432` como padrão do projeto.

## Comandos executados e resultados

### Validação estática

```powershell
python -m py_compile automation/dbops.py tests/test_dbops.py
python -m unittest discover -s tests -v
docker compose --env-file .env.example config --quiet
```

Resultados:

- compilação Python: passou;
- testes unitários: 2 passaram;
- Compose: código `0`;
- aviso do Docker sobre permissão para `C:\Users\Calvo\.docker\config.json`, sem impedir a validação.

### Dependência

```powershell
python -m pip install -r automation/requirements.txt
```

A primeira tentativa foi bloqueada pelo sandbox. A instalação autorizada concluiu com `psycopg`, `psycopg-binary`, `typing-extensions` e `tzdata`.

### Runtime PostgreSQL

```powershell
docker compose up -d postgres
python automation/dbops.py provision
python automation/dbops.py health-check
python automation/dbops.py provision
python automation/dbops.py health-check
```

Resultados observados:

- container `dbops_lab-postgres-1` saudável;
- imagem PostgreSQL `16.4-alpine`;
- primeiro provisionamento: sucesso, uma migration aplicada e quatro roles processadas;
- primeiro health check: sucesso;
- segundo provisionamento: sucesso, zero migrations novas;
- segundo health check: sucesso;
- espaço livre observado: `412288 MB`;
- migrations registradas: `1`;
- tabelas públicas: `4`;
- banco: `dbops`;
- usuário administrativo: `dbops_admin`.

### Permissões

Foi consultado o catálogo do PostgreSQL sem imprimir senhas:

- `dbops_app`: sem superuser/createdb/createrole, com SELECT/INSERT/UPDATE/DELETE;
- `dbops_operator`: sem superuser/createdb/createrole, com privilégios operacionais nas tabelas;
- `dbops_readonly`: sem superuser/createdb/createrole, somente SELECT;
- `dbops_monitor`: sem superuser/createdb/createrole e membro de `pg_monitor`.

## Checks concluídos

- Check 0 — Segurança e reprodutibilidade: concluído na Rodada 001.
- Check 1 — Provisionamento PostgreSQL: concluído nesta rodada.
- Checks 2 a 8: permanecem pendentes.
- Check final de portfólio: permanece pendente.

## Limitações e riscos

- O `.env` local usa uma porta alternativa (`15432`) por causa do comportamento de autenticação observado na porta publicada `5432` deste host. Isso não altera o padrão versionado.
- O volume Docker foi preservado; não foi usado `down -v` nem qualquer exclusão destrutiva.
- O banco foi provisionado com credenciais de laboratório. Elas devem ser trocadas antes de qualquer uso fora da máquina local.
- Ainda não há backup, WAL archiving, PITR, restore, monitoramento do PostgreSQL ou testes de performance.
- `psycopg` foi instalado no ambiente global de usuário usado nesta validação; o fluxo documentado continua recomendando `.venv`.

## Próximo passo

Fase 2 — Backup, restore e recuperação PostgreSQL: implementar `backup`, `verify-backup`, `restore`, backup lógico, backup físico, WAL archiving, PITR e teste automático de restauração.

## Comandos granulares para o usuário salvar e commitar

Estes comandos não foram executados pelo agente. O `.env` não deve ser adicionado:

```powershell
git add .env.example automation migrations tests
git commit -m "feat: add PostgreSQL provisioning CLI"

git add evidence/phase-0/round-004.md
git commit -m "docs: record PostgreSQL provisioning validation"
```

As alterações em `docs/` continuam ignoradas conforme a decisão da Rodada 003.
