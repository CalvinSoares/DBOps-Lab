# Rodada 006 — Fase 2: backup físico e arquivamento de WAL

## Identificação

- **Projeto:** DB Operations Lab — Resilient Multi-Database Platform
- **Fase:** 2 — Backup, restore e recuperação PostgreSQL
- **Rodada:** 006
- **Agentes:** DBA PostgreSQL, DevOps/Automação, QA/Incidentes e orquestrador
- **Data/hora:** 2026-10-03 20:08:30 -03:00 (America/Sao_Paulo)
- **Status:** backup físico e WAL validados; PITR continua pendente

## Objetivo e escopo

Adicionar uma camada física de proteção ao PostgreSQL e provar que o servidor arquiva WAL de forma observável. O escopo desta rodada foi limitado a:

1. criar uma role de replicação dedicada para `pg_basebackup`;
2. executar backup físico com `pg_basebackup` e `--wal-method=stream`;
3. gerar manifesto de diretório com contagem, tamanho e SHA-256;
4. validar o backup com `pg_verifybackup`;
5. configurar e exercitar o arquivamento de WAL;
6. deixar PITR para uma rodada separada, com cluster de recuperação isolado.

Não foi declarado sucesso de PITR, RPO ou RTO nesta rodada.

## Estado antes da rodada

- O backup lógico e o restore para um banco isolado já estavam validados na Rodada 005.
- O Compose ainda não configurava `wal_level`, `archive_mode` ou `archive_command`.
- Não havia role de replicação dedicada.
- Os subchecks de backup físico e WAL estavam pendentes.

## Alterações realizadas

### `docker-compose.yml`

- adicionadas as variáveis `POSTGRES_BACKUP_USER` e `POSTGRES_BACKUP_PASSWORD` ao serviço PostgreSQL;
- montado `postgres/backup/physical/` em `/var/lib/postgresql/physical_backups`;
- montado `postgres/backup/wal/` em `/var/lib/postgresql/wal_archive`;
- configurado `wal_level=replica`;
- configurado `archive_mode=on`;
- configurado `archive_command` idempotente, que copia cada segmento apenas se ele ainda não existir;
- configurado `archive_timeout=5s` para tornar o teste do laboratório determinístico.

### `.env.example`

Documentadas as variáveis locais para a role de backup e para o diretório do backup físico. O `.env` real continua local e ignorado pelo Git.

### `automation/dbops.py`

- a configuração passou a conhecer uma role dedicada de backup;
- a role é criada com atributo `REPLICATION`, enquanto as demais recebem `NOREPLICATION`;
- adicionado `backup --type physical`;
- adicionado `backup --type both`;
- implementado fallback para executar `pg_basebackup` dentro do container quando o binário não está disponível no host;
- criado manifesto para árvore de backup física, com contagem de arquivos, tamanho total e SHA-256 calculado em streaming;
- adicionado `pg_verifybackup` ao fluxo de `verify-backup`;
- adicionado `wal-status`, que força uma troca controlada de WAL e verifica `pg_stat_archiver`, configuração do servidor e arquivos arquivados no host;
- mantidos logs JSON sem senha ou token.

### Estrutura de armazenamento

- `postgres/backup/physical/.gitkeep`: diretório reservado para backups físicos locais;
- `postgres/backup/wal/.gitkeep`: diretório reservado para segmentos WAL locais;
- os artefatos gerados permanecem fora do Git; manifestos e evidências não contêm credenciais.

## Comandos executados e resultados

### Validação de configuração e reinício

```powershell
docker compose config --quiet
docker compose up -d --force-recreate postgres
python automation/dbops.py provision
python automation/dbops.py health-check
```

Resultado: configuração válida, container saudável, provisionamento idempotente e health check aprovados. A role de backup foi criada e consultada com `rolreplication=true`.

### Backup físico

```powershell
python automation/dbops.py backup --type physical
```

Resultado observado:

- artefato: `dbops_20261003T230613Z`;
- formato: diretório físico do cluster;
- método de WAL: `stream`;
- arquivos: `1613`;
- tamanho total: `72796313` bytes;
- SHA-256 do conteúdo: `2247c189f3b3dd108b2dfc20e3433adbfff81116dd3c306860717fdac3d2365d`;
- manifesto: `postgres/backup/physical/dbops_20261003T230613Z.manifest.json`;
- código de saída: `0`.

### Verificação do backup físico

```powershell
python automation/dbops.py verify-backup dbops_20261003T230613Z
```

Resultado: manifesto, contagem de arquivos, tamanho, SHA-256 e `pg_verifybackup` aprovados; código de saída `0`.

### Arquivamento de WAL

```powershell
python automation/dbops.py wal-status
```

Resultado observado:

- `wal_level`: `replica`;
- `archive_command_configured`: `true`;
- WAL trocado: `0/5000000`;
- segmentos arquivados contabilizados pelo PostgreSQL: `5`;
- falhas de arquivamento: `0`;
- último WAL arquivado: `000000010000000000000004`;
- arquivos encontrados no diretório montado: `6`;
- código de saída: `0`.

### Checks técnicos finais

```powershell
python -m py_compile automation/dbops.py
python -m unittest discover -s tests -v
python automation/dbops.py health-check
```

Resultado: compilação sem erro, `2` testes unitários aprovados e health check aprovado. O health check registrou PostgreSQL 16.4, `4` tabelas, `1` migration e aproximadamente `7.7 MB` de banco de laboratório.

## Checks concluídos nesta rodada

- Check 2 — backup físico com `pg_basebackup`: concluído.
- Check 2 — WAL arquivado e verificável: concluído.
- Check 2 — checksum/tamanho/manifesto: reforçado também para o backup físico.
- Check 0 e Check 1: permanecem aprovados pelas rodadas anteriores e foram reexercitados.
- Check 2 — PITR, restore em cluster separado, idade/falha em métrica e RPO/RTO observado: pendentes.
- Checks 3 a 8: pendentes.

## Limitações, riscos e decisões

- O arquivamento atual usa diretório local montado no host; não é armazenamento remoto, imutável ou off-site.
- `archive_timeout=5s` é uma configuração didática para o laboratório e não deve ser copiada para produção sem análise de volume de WAL e custo de I/O.
- A role e a senha são adequadas apenas para o ambiente local de estudo; não são segredo de produção.
- `pg_verifybackup` valida a consistência do backup físico, mas não prova que o procedimento de recuperação operacional atende um RTO.
- O backup físico ainda não foi iniciado como um novo cluster e não foi usado para PITR.
- O diretório de WAL contém artefatos locais; não adicionar esses arquivos ao Git.

## Próximo passo

Construir o fluxo de PITR: gerar um marcador temporal, produzir atividade após o backup base, simular perda lógica, iniciar um container de recuperação com o `pg_basebackup`, configurar `restore_command` e `recovery_target_time`, validar que o dado pós-incidente não reaparece e medir duração. Só então registrar RPO/RTO observados.

## Comandos granulares para o usuário salvar e commitar

Estes comandos não foram executados pelo agente. Eles não adicionam `.env`, dumps, diretórios físicos ou segmentos WAL:

```powershell
git add .env.example docker-compose.yml automation/dbops.py automation/README.md postgres/backup/physical/.gitkeep postgres/backup/wal/.gitkeep
git commit -m "feat: add physical PostgreSQL backups and WAL archiving"

git add evidence/phase-0/round-006.md
git commit -m "docs: record physical backup and WAL validation"
```

As alterações em `docs/` e `AGENTS.md` continuam ignoradas conforme a decisão registrada na Rodada 003.
