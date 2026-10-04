# Fase 5 — Incidentes e game days

Esta pasta contém runbooks para operar o laboratório sob falha. O objetivo é registrar o caminho completo: impacto, detecção, contenção, diagnóstico, recuperação, validação, alternativa e lições aprendidas.

## Regras de execução

- Leia o runbook antes de agir.
- Use ambiente descartável para qualquer teste que possa perder dados ou interromper o serviço.
- A automação `python automation/run_incident.py <incidente>` faz apenas planejamento por padrão.
- `--execute` é obrigatório para executar os cenários controlados e gera evidência em `evidence/phase-5/`.
- Não execute `database-down`, `disk-full` ou exclusão real sem confirmação explícita, janela de teste e plano de retorno.
- Nunca altere ou trunque um backup original. A simulação de backup inválido usa uma cópia temporária.

## Cenários

| Cenário | Runbook | Automação | Estado desta rodada |
|---|---|---|---|
| Exclusão acidental | [`01-delete-data.md`](01-delete-data.md) | planejamento | runbook criado |
| PITR para horário específico | [`02-pitr.md`](02-pitr.md) | planejamento; PITR já validado na Fase 2 | evidência anterior reutilizada |
| Disco cheio | [`03-disk-full.md`](03-disk-full.md) | planejamento | não executado por risco operacional |
| Banco indisponível | [`04-database-down.md`](04-database-down.md) | planejamento | não executado por interromper o serviço |
| Query lenta | [`05-slow-query.md`](05-slow-query.md) | `--execute` | game day controlado |
| Lock/deadlock | [`06-lock.md`](06-lock.md) | `--execute` | game day controlado |
| Atraso de réplica | [`07-replication-lag.md`](07-replication-lag.md) | planejamento | não aplicável sem réplica |
| Backup inválido | [`08-invalid-backup.md`](08-invalid-backup.md) | `--execute` | cópia isolada |

## Comandos

```powershell
python automation/run_incident.py slow-query
python automation/run_incident.py slow-query --execute --duration 20 --observe-prometheus
python automation/run_incident.py lock --execute --observe-prometheus
python automation/run_incident.py backup-invalid --execute
python automation/run_incident.py database-down
```

`--observe-prometheus` captura a métrica selecionada antes, durante e depois do incidente. O modo sem `--execute` retorna `0` e registra um plano com status `planned`. Uma execução real validada retorna `0`; falhas de configuração, banco ou validação retornam códigos não zero.
