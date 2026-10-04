# Incidente 03 — filesystem sem espaço

## Impacto

Backups, WAL, logs ou escrituras do banco podem falhar. O risco inclui indisponibilidade e perda da capacidade de arquivar WAL.

## Detecção

1. Confirmar `NodeFilesystemLow` no Prometheus e executar `health-check`.
2. Medir o filesystem e os diretórios de dados, backup e WAL.
3. Verificar se o banco está bloqueado por falha de archive ou sem espaço temporário.

## Contenção

Suspender cargas não essenciais e novos backups concorrentes. Não remover WAL ou arquivos do PostgreSQL manualmente. Preservar logs do alerta e o inventário de arquivos.

## Recuperação e validação

Liberar somente artefatos temporários ou backups expirados conforme a política de retenção. Confirmar espaço livre, `pg_stat_archiver`, health check, criação de WAL e uma operação de backup.

## Alternativa e segurança

Se a limpeza segura não for suficiente, ampliar o volume ou mover backups para armazenamento aprovado. A simulação com preenchimento de disco exige ambiente descartável, janela aprovada e não é executada automaticamente.
