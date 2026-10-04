# Rodada 012 — Snapshots Prometheus durante game days

## Identificação

- **Projeto:** DB Operations Lab — Resilient Multi-Database Platform
- **Fase:** 5 — Incidentes e game days, com aceite pendente da observabilidade
- **Rodada:** 012
- **Agentes:** Observabilidade, QA/Incidentes, DBA PostgreSQL, DevOps/Automação e orquestrador
- **Data/hora da validação final:** 2026-10-03 21:43:25 -03:00 (America/Sao_Paulo)
- **Status:** dois incidentes observados com mudança real antes/durante/depois; terceiro incidente de disponibilidade pendente

## Objetivo e escopo

O objetivo foi comprovar mudança de métricas durante os game days, e não apenas a existência de séries. O executor de incidentes recebeu `--observe-prometheus`, que captura uma consulta instantânea no Prometheus em três fases:

1. antes: baseline antes de abrir a sessão do incidente;
2. durante: polling até o valor representar a condição do incidente;
3. depois: polling até a métrica retornar ao estado normal ou expirar o limite de observação.

Foram observados query lenta e lock. Banco indisponível não foi interrompido porque isso exige autorização explícita ou um ambiente descartável separado.

## Estado antes da alteração

- O exporter, Prometheus e Grafana já estavam saudáveis.
- Os game days registravam `pg_stat_activity` e `pg_blocking_pids`, mas não capturavam a série Prometheus na janela do incidente.
- O check de dashboard de três incidentes continuava pendente.
- O scrape do Prometheus era de 15 segundos; um snapshot único poderia retornar a amostra anterior.

## Alterações realizadas

### `automation/run_incident.py`

Adicionados:

- `prometheus_snapshot`, usando somente a API local do Prometheus;
- `metric_value`, que extrai o valor numérico da série sem armazenar segredos;
- opção `--observe-prometheus`;
- snapshots para query age e lock waits;
- espera durante a janela ativa para capturar o scrape atualizado;
- espera pós-incidente para confirmar retorno a zero/aproximadamente zero;
- invalidação do game day caso a série não demonstre condição durante e recuperação depois.

O lock usa `lock_timeout='20s'` somente na sessão de espera, permitindo que o scrape de 15 segundos observe o bloqueio. A sessão bloqueadora continua sendo uma transação criada pelo próprio teste e sofre rollback/limpeza.

### Documentação

- `incidents/README.md`: comandos com `--observe-prometheus`.
- `automation/README.md`: explicação dos snapshots.
- `monitoring/README.md`: estado atualizado para dois incidentes observados e um pendente.
- `docs/EVIDENCE_MATRIX.md`: observabilidade continua `in-progress`, com o motivo explícito.

## Comandos executados e resultados

### Testes

```powershell
python -m py_compile automation/run_incident.py
python -m unittest discover -s tests -v
```

Resultado: sintaxe aprovada e `5` testes aprovados.

### Query lenta observada

```powershell
python automation/run_incident.py slow-query --execute --duration 20 --observe-prometheus
```

Evidência final: [`incident-slow-query-20261004T004325Z.json`](incident-slow-query-20261004T004325Z.json).

Valores capturados da série `dbops_activity_max_query_age_seconds{datname="dbops"}`:

- antes: `0.001353` segundos;
- durante: `1.642766` segundos;
- depois: `0.000728` segundos;
- status: `validated=true`.

Além do Prometheus, a sessão foi observada em `pg_stat_activity` com `wait_event_type=Timeout` e `wait_event=PgSleep`. O PID temporário foi `5310` e não ficou ativo após o teste.

### Lock observado

```powershell
python automation/run_incident.py lock --execute --observe-prometheus
```

Evidência: [`incident-lock-20261004T004240Z.json`](incident-lock-20261004T004240Z.json).

Valores capturados da série `dbops_lock_waits_blocked_queries{datname="dbops"}`:

- antes: `0`;
- durante: `1`;
- depois: `0`;
- status: `validated=true`.

O cenário também confirmou PID bloqueador `5263`, PID aguardando `5264`, `wait_event=transactionid` e SQLSTATE `55P03`. A tabela do laboratório foi removida no cleanup.

### Validação final da stack

```powershell
python -m unittest discover -s tests -v
python automation/check_monitoring.py
```

Resultado: `5` testes unitários aprovados e check de monitoramento com código `0`. A evidência [`monitoring-result-20261004T004448Z.json`](../phase-0/monitoring-result-20261004T004448Z.json) confirmou exporter HTTP `200`, Grafana health/dashboard `200`, `pg_up=1`, targets PostgreSQL e node `up=1`, 10 painéis, 1 grupo de alertas, 1 série de lock waits e 1 série de backup lógico sem falha.

## Decisão sobre o terceiro incidente

O critério da Fase 4 pede três incidentes com mudança observável. Dois já foram capturados com mudança e recuperação. Não executei `docker compose stop postgres` porque isso interromperia o serviço compartilhado e seria uma operação disruptiva sem autorização explícita. O runbook [`04-database-down.md`](../../incidents/04-database-down.md) permanece pronto para execução em janela aprovada ou projeto Compose descartável.

## Checks e evidências

- Check 4 — dashboards/probes exercitados durante incidentes: parcialmente concluído; dois incidentes com snapshots PromQL validados, terceiro pendente.
- Check 5 — query lenta: validado com mudança de métrica e retorno.
- Check 5 — lock: validado com mudança de métrica, bloqueador e retorno.
- Check 5 — banco indisponível: runbook documentado, execução pendente.
- Nenhuma credencial, dump ou dado pessoal foi gravado nas evidências.

## Limitações e riscos

- A métrica de query age é atualizada pelo ciclo de scrape; por isso o executor aguarda a série mudar.
- O game day de lock usa bloqueio transacional, não deadlock cíclico.
- Query lenta de 20 segundos fica abaixo do alerta de 30 segundos por 2 minutos; o objetivo desta rodada foi provar a mudança da série, não disparar o alerta.
- O aceite completo de três incidentes continua bloqueado até o terceiro cenário ser executado com segurança.

## Próximo passo

Executar o runbook de indisponibilidade em ambiente descartável, ou obter autorização explícita para uma janela controlada, capturando `up{job="postgresql"}` e `pg_up` antes/durante/depois. Depois fechar o check da Fase 4 e iniciar o plano MySQL/MariaDB.

## Comandos granulares para o usuário salvar e commitar

Estes comandos não foram executados pelo agente:

```powershell
git add automation/run_incident.py incidents/README.md automation/README.md monitoring/README.md evidence/phase-5/incident-slow-query-20261004T004325Z.json evidence/phase-5/incident-lock-20261004T004240Z.json evidence/phase-0/monitoring-result-20261004T004448Z.json
git commit -m "feat: capture Prometheus snapshots during incidents"

git add evidence/phase-5/round-012.md
git commit -m "docs: record incident metric snapshots"
```

As alterações em `docs/` e `AGENTS.md` continuam ignoradas conforme a decisão da Rodada 003.
