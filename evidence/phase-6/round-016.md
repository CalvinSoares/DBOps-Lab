# Rodada 016 — primeiro ciclo operacional do MariaDB

## Identificação

- Fase: 6 — MySQL/MariaDB secundário
- Data/hora: 2026-10-08 19:45:45 -03:00
- Agente responsável: orquestrador / DevOps / DBA secundário
- Status: provisionamento, backup, verificação, restore e consistência validados

## Objetivo e escopo

Esta rodada iniciou o banco secundário MariaDB no Docker Compose e implementou um caminho operacional reproduzível para provisionar, verificar, popular com dados sintéticos, fazer backup lógico, validar o artefato e restaurar em um banco separado.

Ficaram deliberadamente fora desta rodada o Performance Schema, exporter dedicado, dashboard específico, simulação de falha e estratégia de alta disponibilidade. Esses itens continuam pendentes para não declarar uma cobertura maior do que a evidência produzida.

## Estado observado antes

O repositório possuía a pasta `mysql/` planejada, mas não havia serviço MariaDB ativo, schema secundário, CLI de operação ou ciclo de backup/restore validado. O PostgreSQL permaneceu como caminho crítico existente e não foi alterado operacionalmente nesta execução.

## Alterações realizadas

- `.env.example`: adicionadas imagem, banco, usuário, senhas de laboratório, porta e diretório de backup do MariaDB.
- `docker-compose.yml`: adicionado serviço `mariadb` no profile `secondary`, volume persistente, diretório de init/backup e health check nativo.
- `mysql/init/001_schema.sql`: criado schema sintético com `customers`, `tickets` e `ticket_events`, chaves, índices e InnoDB.
- `mysql/README.md`: documentado o ciclo de uso do banco secundário.
- `automation/mysqlops.py`: criada CLI com `provision`, `health-check`, `seed`, `backup`, `verify-backup` e `restore`, códigos de saída, logs JSON e validações.
- `tests/test_mysqlops.py`: adicionados testes estáticos da resolução segura de artefatos e constantes operacionais.
- `automation/README.md` e `README.md`: documentado o primeiro ciclo MariaDB e seus limites.
- `docs/CHECKS.md` e `docs/EVIDENCE_MATRIX.md`: atualizados apenas os itens comprovados nesta rodada.

## Conceitos demonstrados

O profile secundário mantém o MariaDB opcional e evita acoplar sua inicialização ao caminho PostgreSQL. O schema usa InnoDB para transações e chaves estrangeiras. O backup usa `mariadb-dump --single-transaction --routines --triggers`, reduzindo impacto para tabelas transacionais e incluindo objetos operacionais relevantes. O manifesto registra tamanho, SHA-256, tipo, banco, engine e duração. A verificação separa integridade do arquivo (`gzip -t` e hash) da capacidade de restaurar. O restore recebe outro nome de banco, permitindo validar sem sobrescrever o banco original.

## Comandos executados e resultados

```text
python -m py_compile automation/mysqlops.py
python -m unittest discover -s tests -v
docker compose config --quiet
docker compose --profile secondary up -d mariadb
python automation/mysqlops.py provision
python automation/mysqlops.py health-check
python automation/mysqlops.py seed
python automation/mysqlops.py backup
python automation/mysqlops.py verify-backup secondary_db_20261008T224540Z.sql.gz
python automation/mysqlops.py restore secondary_db_20261008T224540Z.sql.gz
```

Resultados observados:

- 9 testes automatizados aprovados;
- serviço `mariadb` saudável em `mariadb:11.4.3`;
- versão reportada: `11.4.3-MariaDB-ubu2404`;
- tabelas válidas: `customers`, `ticket_events`, `tickets`;
- backup: `mysql/backup/secondary_db_20261008T224540Z.sql.gz`;
- tamanho: 1281 bytes;
- SHA-256: `24deb503ae18647c09d4d540f8a7234d510fac779751045aa22e7cae5d23839d`;
- `gzip -t` e manifesto aprovados;
- restore validado em `secondary_restore_20261008224542`;
- contagens no restore: 1 customer, 1 ticket e 1 evento.

O resumo estruturado está em `mariadb-result-20261008T224545Z.json`.

## Limitações e riscos

O backup validado é lógico; ainda não há teste de falha do serviço, verificação de Performance Schema, monitoramento dedicado ou restore de permissões/usuários. O dump é mantido localmente e não deve ser adicionado ao Git. As senhas do Compose são de laboratório e devem ser substituídas localmente antes de qualquer uso fora do ambiente descartável.

## Pendências e critério de desbloqueio

1. Performance Schema: executar uma consulta lenta controlada, consultar eventos e registrar interpretação em `benchmarks/mysql/`.
2. Observabilidade: adicionar exporter compatível e métricas MariaDB ao Prometheus/Grafana, com evidência de mudança.
3. Incidente: documentar e executar em ambiente descartável uma falha ou indisponibilidade do MariaDB, incluindo detecção, mitigação e recuperação.

O Check 6 só será totalmente validado quando esses três grupos possuírem evidência reproduzível.

## Próximo passo recomendado

A próxima rodada permanece na Fase 6 e deve implementar o diagnóstico de performance com Performance Schema antes de avançar para SQL Server. Isso mantém a prioridade operacional do projeto: primeiro medir e recuperar o banco secundário; depois ampliar a cobertura tecnológica.

## Comandos granulares para salvar e commitar manualmente

Não foram executados `git add`, `git commit` ou `git push` pelo agente.

```powershell
git add .env.example docker-compose.yml mysql automation/mysqlops.py automation/README.md README.md tests/test_mysqlops.py mysql/backup/secondary_db_20261008T224540Z.sql.gz.manifest.json evidence/phase-6/mariadb-result-20261008T224545Z.json
git commit -m "feat: add MariaDB backup and restore cycle"

git add evidence/phase-6/README.md evidence/phase-6/round-016.md
git commit -m "docs: record MariaDB operational validation"
```
