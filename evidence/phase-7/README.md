# Evidências da Fase 7 — SQL Server/Windows

Esta pasta registra o primeiro ciclo SQL Server executado no Windows. O ambiente disponível é SQL Server Express 2019, não Developer.

## Artefatos

- `round-020.md`: ambiente, CLI, backups e limitações da rodada;
- `round-021.md`: restore full + differential + log em banco separado;
- `round-022.md`: Query Store e análise de waits;
- `sqlserver-result-20261008T225652Z.json`: resumo sem credenciais da execução.
- `sqlserver-restore-20261008T225834Z.json`: resultado estruturado do restore.
- `sqlserver-performance-20261008T230012Z.json`: runtime stats e waits filtrados.

Os arquivos `.bak` e `.trn` ficam no diretório de backup do serviço SQL Server e são ignorados pelo Git.
