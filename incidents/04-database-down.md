# Incidente 04 — banco indisponível

## Detecção

1. Confirmar falha em `python automation/dbops.py health-check`.
2. Conferir `docker compose ps`, logs do PostgreSQL e `up{job="postgresql"}`.
3. Separar falha de processo, porta, credenciais, volume ou filesystem.

## Contenção e diagnóstico

Não remover o volume `postgres_data`. Coletar logs, status do container, espaço e último backup conhecido antes de reiniciar.

## Game day isolado

Para validar detecção e recuperação sem interromper o laboratório principal:

```powershell
python automation/run_database_down.py
python automation/run_database_down.py --execute
```

O cenário usa o projeto Compose `dbops_incident_down`, um PostgreSQL descartável, exporter e Prometheus próprios. O executor confirma `pg_up=1`, para somente `incident-postgres`, confirma `pg_up=0`, inicia o serviço novamente e confirma `pg_up=1`. No final remove somente os containers e volumes desse projeto isolado.

## Recuperação do ambiente principal

Em uma janela autorizada, reiniciar somente o serviço afetado com `docker compose up -d postgres`, acompanhar o health check e, se o volume estiver comprometido, iniciar recuperação em ambiente separado usando o backup físico validado.

## Validação

Executar provisionamento/health check, confirmar `pg_up=1`, testar uma leitura e validar que WAL e backups voltaram a funcionar.

## Limitação

O game day isolado não prova recuperação do volume de produção; prova detecção, contenção e retorno de disponibilidade em um ambiente descartável. O container principal nunca é parado pelo executor.
