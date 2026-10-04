# Incidente 08 — backup corrompido ou inválido

## Detecção

Nunca tratar a existência do arquivo como sucesso. Executar `verify-backup`, validar manifesto, tamanho, SHA-256 e `pg_restore --list`.

## Contenção

Isolar o artefato inválido, preservá-lo para diagnóstico e selecionar o backup anterior ou seguinte que tenha verificação aprovada. Não sobrescrever o original.

## Recuperação e validação

Restaurar somente um artefato validado em ambiente separado e comparar schema, migrations e dados. A automação cria uma cópia truncada temporária e exige que a verificação falhe:

```powershell
python automation/run_incident.py backup-invalid --execute
```

O arquivo de teste é removido ao final; o dump original permanece intacto.
