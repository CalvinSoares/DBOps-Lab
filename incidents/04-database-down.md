# Incidente 04 — banco indisponível

## Detecção

1. Confirmar falha em `python automation/dbops.py health-check`.
2. Conferir `docker compose ps`, logs do PostgreSQL e `up{job="postgresql"}`.
3. Separar falha de processo, porta, credenciais, volume ou filesystem.

## Contenção e diagnóstico

Não remover o volume `postgres_data`. Coletar logs, status do container, espaço e último backup conhecido antes de reiniciar.

## Recuperação

Reiniciar somente o serviço afetado com `docker compose up -d postgres`, acompanhar o health check e, se o volume estiver comprometido, iniciar recuperação em ambiente separado usando o backup físico validado.

## Validação

Executar provisionamento/health check, confirmar `pg_up=1`, testar uma leitura e validar que WAL e backups voltaram a funcionar.

## Limitação

Derrubar o container é uma ação disruptiva. Este runbook fica em modo planejado nesta rodada; só deve ser executado com confirmação e janela de teste.
