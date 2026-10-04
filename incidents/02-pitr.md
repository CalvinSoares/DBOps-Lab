# Incidente 02 — PITR para horário específico

## Impacto e pré-condições

Usado para recuperar dados até um instante anterior ao incidente. Exige backup físico válido, WAL arquivado desde o backup e um horário-alvo em UTC.

## Procedimento

1. Identificar `recovery_target_time` anterior ao incidente.
2. Selecionar o backup físico mais recente anterior ao alvo.
3. Executar `python automation/dbops.py pitr --base-artifact <backup-fisico> --cleanup`.
4. Inspecionar o JSON gerado em `evidence/phase-0/`.

## Validação

O resultado deve mostrar cluster separado promovido, `pg_is_in_recovery()` falso, marcador anterior presente e marcador posterior ausente. A evidência validada desta plataforma está em [`round-007.md`](../evidence/phase-0/round-007.md).

## Alternativa e lições

Se faltarem WALs, parar e declarar o limite real de recuperação; não avançar o alvo para esconder perda de dados. Registrar a janela de WAL ausente e revisar retenção, arquivamento e alertas.
