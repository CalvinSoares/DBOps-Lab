# Rodada 007 — Fase 2: PITR em cluster PostgreSQL separado

## Identificação

- **Projeto:** DB Operations Lab — Resilient Multi-Database Platform
- **Fase:** 2 — Backup, restore e recuperação PostgreSQL
- **Rodada:** 007
- **Agentes:** DBA PostgreSQL, DevOps/Automação, QA/Incidentes e orquestrador
- **Data/hora:** 2026-10-03 20:27:49 -03:00 (America/Sao_Paulo)
- **Status:** PITR validado; métricas de backup, retenção e RPO/RTO de produção continuam pendentes

## Objetivo e escopo

Provar que um backup físico e os WALs arquivados conseguem recuperar o PostgreSQL para um horário definido, em um container separado do servidor principal.

O cenário executado foi:

1. selecionar e verificar o backup físico `dbops_20261003T230613Z`;
2. criar dados sintéticos identificados por UUID no banco principal;
3. inserir um evento `pitr_before_incident`;
4. capturar um horário-alvo imediatamente depois desse evento;
5. inserir um evento `pitr_after_incident`, representando a alteração posterior ao incidente;
6. forçar a troca de WAL e aguardar o arquivamento;
7. copiar o backup físico para uma árvore temporária de recuperação;
8. iniciar um container PostgreSQL separado com `recovery.signal`, `restore_command` e `recovery_target_time`;
9. validar que o evento anterior ao alvo existe, que o evento posterior não existe e que o cluster foi promovido;
10. remover somente os registros sintéticos do banco principal com a opção explícita `--cleanup`.

Ficaram fora desta rodada: armazenamento remoto/imutável, retenção automática, failover, replicação síncrona e uma declaração de RPO/RTO de produção.

## Estado antes da rodada

- backup físico e arquivamento de WAL já estavam validados na Rodada 006;
- o restore lógico ainda ocorria em banco isolado dentro do mesmo servidor;
- não havia procedimento automatizado de recuperação temporal;
- o Check 2 ainda não tinha PITR nem restore em ambiente separado aprovados.

## Alterações realizadas

### `automation/dbops.py`

- adicionado o comando `pitr`;
- seleção do backup físico informado por `--base-artifact` ou do backup físico mais recente;
- verificação de `backup_manifest`, SHA-256, tamanho, quantidade de arquivos e `pg_verifybackup` antes do PITR;
- criação de customer, ticket e eventos sintéticos com marcador UUID;
- definição do horário-alvo entre os dois eventos;
- criação de `postgresql.auto.conf` com `restore_command`, `recovery_target_time`, `recovery_target_action=promote` e `recovery_target_inclusive=false`;
- criação de `recovery.signal`;
- montagem somente leitura do diretório de WAL no container recuperado;
- espera por `pg_is_in_recovery() = false`, em vez de considerar apenas `pg_isready`, pois o PostgreSQL pode aceitar conexões de leitura antes de concluir a recuperação;
- uso do usuário administrativo configurado (`dbops_admin` neste laboratório), porque a imagem foi inicializada com esse nome e não possui automaticamente uma role `postgres`;
- timeout de três segundos nos probes externos para evitar CLI pendurada;
- limpeza explícita dos marcadores somente com `--cleanup`;
- gravação do resultado da execução em JSON sem credenciais.

### `automation/README.md`

Documentado o comando `pitr`, o significado de `--cleanup` e `--keep-recovery`, além da evidência JSON gerada.

### `.gitignore` e `postgres/recovery/.gitkeep`

O diretório de clusters temporários foi adicionado à estrutura do projeto e seus dados gerados são ignorados pelo Git. O `.gitkeep` preserva somente a estrutura.

### Evidências JSON

Adicionados resultados reproduzíveis em:

- `evidence/phase-0/pitr-result-20261003T232426Z_309777ab.json`;
- `evidence/phase-0/pitr-result-20261003T232641Z_4b84fee3.json`.

O segundo é a execução final usada nos números deste relatório; o primeiro preserva a execução independente usada na inspeção do cluster recuperado.

## Falhas encontradas e correções

### Falha 1 — tipo indeterminado no JSONB

A primeira execução falhou ao usar o parâmetro diretamente em `jsonb_build_object`, retornando `IndeterminateDatatype`. O parâmetro passou a ser explicitamente convertido para `text` com `%s::text`. Os registros sintéticos parciais foram localizados pelo padrão `pitr-*` e removidos de forma direcionada.

### Falha 2 — role inexistente no cluster recuperado

Os logs do container mostraram que a recuperação alcançou o horário-alvo e promoveu o cluster, mas a validação consultava a role fixa `postgres`. Como o laboratório foi inicializado com `POSTGRES_USER=dbops_admin`, a consulta passou a usar `settings.admin_user`.

### Falha 3 — prontidão prematura

`pg_isready` pode indicar estado de leitura antes do fim do recovery. O probe foi alterado para consultar `pg_is_in_recovery()` e aguardar explicitamente o valor `false`.

## Comandos executados e resultados

### PITR final

```powershell
python automation/dbops.py pitr --base-artifact dbops_20261003T230613Z --cleanup --keep-recovery
```

Resultado observado:

- código de saída: `0`;
- backup base: `dbops_20261003T230613Z`;
- horário-alvo: `2026-10-03T23:26:41.543349+00:00`;
- horário do evento posterior: `2026-10-03T23:26:41.544092+00:00`;
- diferença temporal controlada entre alvo e evento posterior: aproximadamente `0,000743 s`;
- duração reportada pela CLI: `38,75 s`;
- marcador anterior recuperado: `1`;
- marcador posterior recuperado: `0`;
- `recovery_in_progress`: `false`;
- `source_markers_cleaned`: `true`;
- WAL no momento do teste: `21` segmentos arquivados e `0` falhas;
- JSON: `evidence/phase-0/pitr-result-20261003T232641Z_4b84fee3.json`.

A árvore do cluster foi removida após a inspeção para não deixar aproximadamente 72 MB de dados temporários no workspace. O JSON e este relatório permanecem como evidência.

### Validação independente de um cluster recuperado

Uma execução anterior, preservada com `--keep-recovery`, foi iniciada uma segunda vez apenas para inspeção. A consulta retornou:

```text
pitr-6de5e05312d34670ae1ef90f3e7eaecb@example.invalid
pitr_before_incident|6de5e05312d34670ae1ef90f3e7eaecb|before
f
```

Isso prova que o dado anterior ao alvo existe, que não há evento posterior recuperado e que o cluster não permanece em recovery.

### Checks finais

```powershell
python -m py_compile automation/dbops.py
python -m unittest discover -s tests -v
python automation/dbops.py health-check
```

Resultado: compilação aprovada, `2` testes unitários aprovados e health check aprovado com PostgreSQL 16.4, `4` tabelas e `1` migration.

## Checks concluídos nesta rodada

- Check 2 — restore em ambiente separado: concluído.
- Check 2 — PITR para horário definido: concluído.
- Check 2 — backup físico, WAL e manifesto: permanecem aprovados pelas Rodadas 006 e 007.
- Check 2 — validação completa de permissões pós-restore, idade/falha em métrica e política de RPO/RTO operacional: pendente.
- Check 5 — PITR para horário específico: evidência técnica criada, mas o runbook de incidente será formalizado na Fase 5.
- Checks 3, 4, 6, 7 e 8: pendentes.

## Limitações, riscos e decisões

- O RPO observado nesta simulação é uma diferença temporal artificial de menos de 1 ms entre o alvo e o evento posterior; não deve ser apresentado como RPO de produção.
- Os `38,75 s` medidos incluem troca/arquivamento de WAL, preparação do cluster, recuperação, validação e limpeza lógica; são uma medição deste laboratório, não um SLA.
- O armazenamento de backup continua local e não oferece proteção contra perda do host.
- O procedimento ainda não mede idade do último backup nem expõe falhas de backup como métrica Prometheus.
- O container separado prova recuperação operacional, não alta disponibilidade automática.
- A recuperação usa cópia local do backup; a próxima evolução deverá documentar retenção e armazenamento independente.

## Próximo passo

Avançar para a Fase 3 — tuning PostgreSQL: dataset conhecido, query lenta reproduzível, `EXPLAIN (ANALYZE, BUFFERS)` antes/depois, índice composto, `ANALYZE`, locks e comparação objetiva de buffers e tempo. O PITR será reutilizado depois em um runbook da Fase 5.

## Comandos granulares para o usuário salvar e commitar

Estes comandos não foram executados pelo agente:

```powershell
git add .env.example docker-compose.yml README.md automation/dbops.py automation/README.md .gitignore postgres/backup/artifacts/.gitkeep postgres/backup/artifacts/dbops_20261003T225857Z.dump.manifest.json postgres/backup/physical/.gitkeep postgres/backup/physical/dbops_20261003T230613Z.manifest.json postgres/backup/wal/.gitkeep postgres/recovery/.gitkeep evidence/phase-0/pitr-result-20261003T232426Z_309777ab.json evidence/phase-0/pitr-result-20261003T232641Z_4b84fee3.json
git commit -m "feat: automate PostgreSQL point-in-time recovery"

git add evidence/phase-0/round-007.md
git commit -m "docs: record PostgreSQL PITR validation"
```

As alterações em `docs/` e `AGENTS.md` continuam ignoradas conforme a decisão da Rodada 003.
