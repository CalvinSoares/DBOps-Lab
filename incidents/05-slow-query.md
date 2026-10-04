# Incidente 05 — query lenta

## Detecção

Usar o alerta de idade de query, o painel Grafana e `pg_stat_activity`. Confirmar duração, banco, PID, wait event e impacto em CPU/I/O.

## Diagnóstico

1. Capturar a consulta sem registrar credenciais.
2. Usar `EXPLAIN (ANALYZE, BUFFERS)` somente em cópia ou com cautela em produção.
3. Verificar estatísticas, índice, cardinalidade, locks e sessões concorrentes.

## Contenção e recuperação

Cancelar somente a sessão autorizada do incidente se ela estiver degradando o serviço. Aplicar alteração reversível (índice, estatística ou consulta) após registrar plano antes/depois.

## Validação

Confirmar redução de latência, buffers e linhas lidas, além do retorno do painel. O game day controlado pode ser executado com `python automation/run_incident.py slow-query --execute --duration 5`.
