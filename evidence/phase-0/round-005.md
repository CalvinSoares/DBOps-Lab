# Rodada 005 — Fase 2: backup lógico, verificação e restore isolado

## Identificação

- **Projeto:** DB Operations Lab — Resilient Multi-Database Platform
- **Fase:** 2 — Backup, restore e recuperação PostgreSQL
- **Rodada:** 005
- **Agentes:** DBA PostgreSQL, DevOps/Automação e QA/Incidentes
- **Data/hora:** 2026-10-03 20:00:00 -03:00 (America/Sao_Paulo)
- **Status:** subetapa lógica concluída; backup físico, WAL archiving e PITR continuam pendentes

## Objetivo

Implementar e validar o primeiro ciclo real de proteção de dados:

1. gerar backup lógico PostgreSQL em formato custom;
2. criar manifesto com tamanho, timestamp e SHA-256;
3. verificar integridade do artefato e listar seu conteúdo com `pg_restore`;
4. restaurar em um banco novo e isolado do banco principal;
5. validar tabelas, migrations e contagens de dados após o restore.

## Estado antes da rodada

- A CLI tinha apenas `provision` e `health-check`.
- O PostgreSQL tinha schema, roles e dados de laboratório, mas nenhum fluxo de backup automatizado.
- O Compose não montava um diretório de artefatos no container.
- O Check 2 estava completamente pendente.

## Alterações realizadas

### `automation/dbops.py`

Adicionados:

- comando `backup`;
- comando `verify-backup <artifact>`;
- comando `restore <artifact> [--target-db]`;
- criação automática de `postgres/backup/artifacts/`;
- execução de `pg_dump` dentro do container quando `pg_dump` não existe no host;
- backup em formato custom com `--no-owner` e `--no-privileges`;
- manifesto JSON ao lado do dump;
- cálculo SHA-256 em streaming, sem carregar o dump inteiro em memória;
- validação de tamanho diferente de zero;
- validação de tamanho e SHA-256 contra o manifesto;
- verificação do formato com `pg_restore --list`;
- criação segura de banco de restore somente com prefixo `dbops_restore_`;
- restore com `pg_restore --exit-on-error`;
- validação pós-restore de tabelas, migrations, clientes e chamados;
- separação explícita entre caminhos locais Windows e caminhos POSIX dentro do container.

O último item corrigiu um bug encontrado durante a rodada: `pathlib.Path("/var/lib/...")` em Windows transformava o caminho interno do container em barras invertidas. O código passou a montar caminhos Docker como strings POSIX.

### `docker-compose.yml`

O serviço PostgreSQL passou a montar:

```text
./postgres/backup/artifacts:/var/lib/postgresql/backups
```

Isso permite que o `pg_dump` seja executado no container e que o artefato fique disponível no host para manifesto, verificação e retenção.

### `.env.example`

Adicionada a variável `POSTGRES_BACKUP_DIR=postgres/backup/artifacts`.

### `automation/README.md`

Documentados os comandos de backup, verificação e restore, incluindo a limitação de que o destino atual é um banco isolado no mesmo servidor.

### `docs/CHECKS.md` e `docs/EVIDENCE_MATRIX.md`

- marcado o subcheck de backup lógico como concluído;
- marcado o subcheck de checksum/tamanho/manifesto como concluído;
- mantidos pendentes backup físico, WAL, PITR, ambiente separado e validação completa de permissões;
- marcada a evidência de backup lógico como `validated`.

## Dados usados no teste

Foram inseridos dados sintéticos e parametrizados:

- 2 clientes;
- 1 chamado;
- 1 evento de chamado.

Nenhum dado pessoal real foi utilizado.

## Comandos executados e resultados

### Preparação e provisionamento

```powershell
docker compose up -d --force-recreate postgres
python automation/dbops.py provision
```

Resultado: container saudável e provisionamento idempotente aprovado.

### Backup lógico

```powershell
python automation/dbops.py backup
```

Resultado observado:

- artefato: `dbops_20261003T225857Z.dump`;
- tamanho: `9140` bytes;
- SHA-256: `322f17e6c0d2498be7466b618511f83b2437a696c941077261212f765e4da68d`;
- manifesto: `dbops_20261003T225857Z.dump.manifest.json`;
- código de saída: `0`.

Um primeiro teste gerou um arquivo de zero bytes por causa do bug de caminho Windows/POSIX. O código foi corrigido para rejeitar dumps vazios e o artefato inválido foi removido. O backup final foi gerado novamente e validado.

### Verificação

```powershell
python automation/dbops.py verify-backup dbops_20261003T225857Z.dump
```

Resultado: manifesto, tamanho, SHA-256 e `pg_restore --list` aprovados; código de saída `0`.

### Restore

```powershell
python automation/dbops.py restore dbops_20261003T225857Z.dump
```

Resultado:

- banco de destino: `dbops_restore_20261003225912`;
- tabelas restauradas: `customers`, `tickets`, `ticket_events`, `schema_migrations`;
- migrations: `1`;
- clientes: `2`;
- chamados: `1`;
- código de saída: `0`.

O banco de restore foi mantido para inspeção e comparação. Ele não substitui ainda um ambiente separado; essa validação ficará para o próximo incremento.

## Checks concluídos

- Check 0: concluído anteriormente.
- Check 1: concluído anteriormente.
- Check 2 — backup lógico e manifesto: subchecks concluídos.
- Check 2 — backup físico, WAL, PITR, ambiente separado, RPO/RTO: pendente.
- Checks 3 a 8: pendentes.

## Limitações e riscos

- O backup físico com `pg_basebackup` ainda não foi implementado.
- WAL archiving ainda não foi configurado nem testado.
- PITR ainda não foi executado.
- O restore atual ocorre em banco isolado dentro do mesmo servidor PostgreSQL.
- O dump e o manifesto permanecem no workspace local; dumps são ignorados pelo Git.
- O banco de restore não deve ser confundido com alta disponibilidade ou ambiente de disaster recovery.

## Próximo passo

Implementar backup físico com `pg_basebackup`, role de replicação dedicada, WAL archiving e restore em um cluster/container PostgreSQL separado. Depois disso, executar o cenário temporal de PITR e medir duração, RPO observado e RTO observado.

## Comandos granulares para o usuário salvar e commitar

Estes comandos não foram executados pelo agente. O `.env`, os dumps e bancos restaurados não devem ser adicionados:

```powershell
git add .env.example docker-compose.yml automation postgres/backup/artifacts/.gitkeep
git commit -m "feat: add logical PostgreSQL backup and restore"

git add evidence/phase-0/round-005.md
git commit -m "docs: record logical backup validation"
```

As alterações em `docs/` continuam ignoradas conforme a decisão da Rodada 003.
