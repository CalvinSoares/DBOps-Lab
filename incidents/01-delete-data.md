# Incidente 01 — exclusão acidental de dados

## Impacto

Registros de clientes, tickets ou eventos foram removidos ou alterados indevidamente. O impacto deve ser medido por tabela, janela temporal e consumidores afetados.

## Detecção

1. Confirmar o alerta ou relato e o horário em UTC.
2. Consultar logs da aplicação, auditoria disponível e contagens atuais.
3. Não executar novos deletes ou restores sobre o banco primário antes de preservar evidências.

## Contenção e diagnóstico

1. Suspender a rotina que está escrevendo dados, se necessário.
2. Registrar `pg_stat_activity`, WAL disponível e o último backup físico válido.
3. Definir `recovery_target_time` imediatamente antes do evento.

## Recuperação

Executar o runbook [`02-pitr.md`](02-pitr.md) em cluster separado. Comparar as tabelas recuperadas com o primário e exportar somente os registros aprovados. A promoção ou merge deve ser uma decisão explícita do responsável pela aplicação.

## Validação e alternativa

Validar contagens, chaves, amostras e integridade referencial. Se o PITR não puder alcançar a janela, restaurar o último backup válido e declarar o RPO perdido, sem inventar um horário de recuperação.

## Lições aprendidas

Registrar causa, ausência/presença de auditoria, cobertura do backup, RPO observado e ação preventiva.
