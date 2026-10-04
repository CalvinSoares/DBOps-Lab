# Rodada 010 — Fase 5: incidentes e game days

## Identificação

- **Projeto:** DB Operations Lab — Resilient Multi-Database Platform
- **Fase:** 5 — Incidentes e game days
- **Rodada:** 010
- **Agentes:** QA/Incidentes, DBA PostgreSQL, DevOps/Automação, Observabilidade, documentação e orquestrador
- **Data/hora da validação final:** 2026-10-03 21:28:29 -03:00 (America/Sao_Paulo)
- **Status:** runbooks criados; três cenários controlados validados; incidentes destrutivos e réplica pendentes

## Objetivo e escopo

Esta rodada transforma os incidentes previstos no plano em procedimentos repetíveis e adiciona um executor seguro para game days PostgreSQL. O escopo incluído foi:

1. criar oito runbooks com impacto, detecção, contenção, diagnóstico, recuperação, validação e limitações;
2. executar os oito cenários em modo `dry-run`;
3. executar query lenta, lock e backup inválido em modo controlado;
4. garantir que o backup original não seja alterado pela simulação de corrupção;
5. criar testes unitários do planejador de incidentes;
6. atualizar checks, matriz de evidências e README.

Ficaram deliberadamente fora: derrubar o PostgreSQL, preencher disco, simular exclusão real de dados e provocar atraso de réplica. Essas ações exigem ambiente descartável, janela de teste e/ou uma réplica que ainda não existe no Compose.

## Estado observado antes da rodada

- PostgreSQL, Prometheus, Grafana, exporters e backup lógico já estavam disponíveis.
- Não havia diretório `incidents/` nem um executor dedicado de game days.
- O Check 5 estava totalmente pendente.
- O PITR já havia sido validado na Fase 2, mas não estava referenciado em um runbook de incidente.

## Arquivos criados ou alterados

### Executor e testes

- `automation/run_incident.py`: CLI com oito cenários, `dry-run` padrão, `--execute` explícito, códigos de saída e JSON de evidência.
- `tests/test_run_incident.py`: valida que os oito incidentes têm plano e que planejamento nunca é marcado como validado.

### Runbooks

- `incidents/README.md`: regras de execução e matriz de cenários.
- `incidents/01-delete-data.md`: contenção e recuperação de exclusão acidental.
- `incidents/02-pitr.md`: PITR até horário específico usando cluster separado.
- `incidents/03-disk-full.md`: espaço, WAL, contenção e limpeza segura.
- `incidents/04-database-down.md`: diagnóstico sem remover volume persistente.
- `incidents/05-slow-query.md`: triagem por métricas, sessão e plano.
- `incidents/06-lock.md`: bloqueador, espera, rollback e validação.
- `incidents/07-replication-lag.md`: procedimento e limitação enquanto não há réplica.
- `incidents/08-invalid-backup.md`: rejeição de artefato inválido sem sobrescrever o original.
- `evidence/phase-5/README.md`: convenção das evidências da fase.

### Documentação de projeto

- `README.md`: passou a apontar para os game days medidos e separar cenários pendentes.
- `automation/README.md`: adicionou comandos e limites do executor.
- `docs/CHECKS.md`: marcou procedimentos e cenários controlados, mantendo pendências destrutivas explícitas.
- `docs/EVIDENCE_MATRIX.md`: mudou Incidentes para `in-progress` e apontou para os JSONs da fase.

## Como a automação funciona

O comando sem `--execute` não conecta no banco: apenas materializa o plano e grava `status: planned`. Isso evita que uma repetição acidental cause impacto operacional.

Com `--execute`:

- `slow-query` abre uma sessão temporária com `pg_sleep`, observa `pg_stat_activity`, captura PID, idade e `wait_event`, e encerra naturalmente;
- `lock` cria uma tabela temporária do laboratório, mantém uma linha bloqueada, executa uma segunda sessão com `lock_timeout`, captura `pg_blocking_pids` e faz rollback/limpeza;
- `backup-invalid` copia o dump mais recente, trunca somente a cópia, exige falha da verificação e revalida o dump original antes de remover os artefatos temporários;
- os demais incidentes rejeitam execução automática nesta rodada e dependem do runbook.

Os nomes de tabela, caminhos e parâmetros usados nos testes são fixos e pertencem ao laboratório. Nenhuma senha ou query com credencial é salva nos JSONs.

## Comandos executados e resultados

### Sintaxe e testes

```powershell
python -m py_compile automation/run_incident.py
python -m unittest discover -s tests -v
```

Resultado: sintaxe aprovada e `5` testes aprovados.

### Planejamento dos oito incidentes

```powershell
python automation/run_incident.py delete-data
python automation/run_incident.py pitr
python automation/run_incident.py disk-full
python automation/run_incident.py database-down
python automation/run_incident.py slow-query
python automation/run_incident.py lock
python automation/run_incident.py replication-lag
python automation/run_incident.py backup-invalid
```

Resultado: oito comandos retornaram `0`, com status `planned`. As evidências estão em `evidence/phase-5/incident-*.json` com timestamp UTC `2026-10-04T00:27:26Z` ou posterior.

### Query lenta

```powershell
python automation/run_incident.py slow-query --execute --duration 5
```

Resultado validado em [`incident-slow-query-20261004T002745Z.json`](incident-slow-query-20261004T002745Z.json): PID `4344`, sessão observada como `active`, `wait_event_type=Timeout`, `wait_event=PgSleep`, duração solicitada de 5 segundos e encerramento normal.

### Lock

```powershell
python automation/run_incident.py lock --execute
```

Resultado validado em [`incident-lock-20261004T002747Z.json`](incident-lock-20261004T002747Z.json): PID bloqueador `4348`, PID aguardando `4349`, `wait_event=transactionid`, `pg_blocking_pids=[4348]`, SQLSTATE `55P03` (`LockNotAvailable`) e rollback automático.

### Backup inválido

```powershell
python automation/run_incident.py backup-invalid --execute
```

Resultado final validado em [`incident-backup-invalid-20261004T002829Z.json`](incident-backup-invalid-20261004T002829Z.json): a cópia `incident_invalid_20261004T002829Z.dump` foi rejeitada com `ValidationError`, foi removida e `source_still_valid=true` para `dbops_20261003T225857Z.dump`.

## Checks e evidências

- Check 5 — procedimento de exclusão acidental: concluído documentalmente.
- Check 5 — PITR: concluído na Fase 2 e referenciado no runbook.
- Check 5 — disco cheio: contenção e validação documentadas; execução pendente.
- Check 5 — banco indisponível: diagnóstico e recuperação documentados; execução pendente.
- Check 5 — query lenta: game day validado.
- Check 5 — lock/deadlock: game day validado.
- Check 5 — backup inválido: detecção e preservação do original validadas.
- Check 5 — runbooks com impacto, causa, recuperação e lições: concluído.
- Aceite completo da Fase 4 sobre mudança de dashboards durante incidentes: ainda pendente de um check específico que capture PromQL durante a janela dos incidentes.

## Limitações, riscos e decisões

- A query lenta durou 5 segundos, abaixo do alerta didático de 30 segundos; o game day valida visibilidade em `pg_stat_activity`, não o disparo desse alerta específico.
- O lock foi um bloqueio transacional controlado, não um deadlock cíclico; a identificação do bloqueador foi validada sem risco de dados.
- O teste de backup inválido usou uma cópia truncada e revalidou o original.
- Não foi executado `docker compose stop`, preenchimento de filesystem ou exclusão real.
- Não há réplica configurada; o runbook de lag está documentado como não aplicável.
- Os JSONs de `dry-run` têm `validated=false` por design: planejamento não é prova de recuperação.

## Próximo passo

Adicionar métricas de idade/falha de backup ao exporter, capturar mudança de PromQL durante os game days, e depois executar os cenários de indisponibilidade e disco cheio em um ambiente descartável. Só então fechar completamente os gates de observabilidade e incidentes.

## Comandos granulares para o usuário salvar e commitar

Estes comandos não foram executados pelo agente:

```powershell
git add automation/run_incident.py tests/test_run_incident.py incidents evidence/phase-5/incident-*.json evidence/phase-5/README.md README.md automation/README.md
git commit -m "feat: add controlled incident game days"

git add evidence/phase-5/round-010.md
git commit -m "docs: record incident game days"
```

As alterações em `docs/` e `AGENTS.md` continuam ignoradas conforme a decisão da Rodada 003.
