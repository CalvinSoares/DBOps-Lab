# Incidente 06 — lock ou deadlock

## Detecção e diagnóstico

Consultar `pg_stat_activity`, `pg_locks` e `pg_blocking_pids(pid)`. Registrar PID bloqueador, PID aguardando, relação, wait event e idade da transação.

## Contenção

Confirmar com o responsável da aplicação antes de cancelar uma sessão. Preferir rollback da transação que segura o lock; usar `pg_cancel_backend` antes de `pg_terminate_backend` quando autorizado.

## Validação

Confirmar que a fila foi liberada, que não houve corrupção e que a aplicação voltou a responder. O game day controlado usa `lock_timeout` e rollback automático: `python automation/run_incident.py lock --execute`.

## Lições

Registrar ordem de acesso às tabelas, duração da transação e mudança preventiva necessária.
