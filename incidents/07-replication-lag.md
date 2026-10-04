# Incidente 07 — atraso de réplica

## Detecção

Este cenário só é aplicável depois que uma réplica PostgreSQL for configurada. Consultar LSN do primário e da réplica, `pg_stat_replication`, replay LSN, estado de WAL e métricas de lag.

## Contenção e diagnóstico

Separar atraso de transporte, archive, replay, I/O e carga da réplica. Evitar direcionar tráfego de leitura para uma réplica fora do limite operacional.

## Recuperação e validação

Corrigir a causa, acompanhar o lag até retornar ao limite definido e validar consultas de leitura. Se a réplica estiver irrecuperável, reconstruí-la a partir de backup físico validado.

## Estado atual

A replicação não está habilitada no Compose desta fase. O cenário é documentado como não aplicável, não como incidente validado.
