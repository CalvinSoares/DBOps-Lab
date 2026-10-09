# Rodada 022 — Query Store e waits do SQL Server

## Identificação

- Fase: 7 — SQL Server Developer e Windows
- Data/hora: 2026-10-08 20:00:12 -03:00
- Agente responsável: DBA secundário / performance
- Status: Query Store e análise de waits validados no SQL Server Express local

## Objetivo e escopo

Esta rodada completou a investigação de performance da Fase 7. O Query Store foi habilitado no banco de laboratório, uma consulta controlada foi executada 20 vezes, runtime stats foram consultados e waits da instância foram filtrados para remover tarefas internas conhecidas.

O objetivo foi demonstrar o procedimento de diagnóstico, não produzir um benchmark de produção. Não foram alterados planos, índices ou configurações de capacidade com base nesses números.

## Estado observado antes

O restore SQL Server estava validado, mas `sys.database_query_store_options` retornava `OFF` e o check de Query Store/waits permanecia pendente. A consulta inicial de waits continha muitos eventos de background, exigindo filtragem antes da interpretação.

## Arquivos criados ou alterados

- `automation/sqlserverops.py`: adicionado `performance-check`, habilitação idempotente do Query Store, coleta de runtime stats e waits filtrados.
- `tests/test_sqlserverops.py`: teste da presença dos caminhos Query Store e waits.
- `automation/README.md`: comando e comportamento documentados.
- `sqlserver/README.md`: conceitos, interpretação e limitações documentados.
- `README.md`: status SQL Server atualizado.
- `docs/CHECKS.md` e `docs/EVIDENCE_MATRIX.md`: Query Store/waits e Check 7 marcados como validados.
- `evidence/phase-7/sqlserver-performance-20261008T230012Z.json`: resumo estruturado.

## Comandos executados e resultados

```text
sqlcmd -S .\\SQLEXPRESS -E -C -d DBOpsLabSqlServer -Q "SELECT actual_state_desc ..."
python -m py_compile automation/sqlserverops.py
python -m unittest discover -s tests -v
python automation/sqlserverops.py performance-check --repetitions 20
```

Resultados:

- Query Store: `READ_WRITE`;
- 19 testes automatizados aprovados;
- consulta controlada executada 20 vezes;
- duração total do ciclo: 3,047 s;
- Query Store, último intervalo: query id 2, 9 execuções, duração média 0,032 ms, CPU média 0,032 ms e 2 leituras lógicas;
- wait de workload principal: `PAGEIOLATCH_SH`, 6.675 tarefas e 46.782 ms acumulados;
- outros waits observados: `PARALLEL_REDO_WORKER_WAIT_WORK`, `IO_COMPLETION`, `LCK_M_S`, `THREADPOOL` e `BACKUPIO`.

O resultado completo está em `sqlserver-performance-20261008T230012Z.json`.

## Conceitos demonstrados

Query Store mantém histórico agregado por consulta/plano e permite comparar duração, CPU e leituras. `sys.dm_os_wait_stats` é cumulativo desde o início da instância; por isso waits de background foram excluídos e os restantes foram tratados como sinais para investigação, não como causa definitiva. `PAGEIOLATCH_SH` aponta espera de leitura de páginas em memória/armazenamento, enquanto `LCK_M_S` pode indicar espera por locks; ambos exigiriam correlação com sessões, plano e carga antes de uma correção.

## Limitações e riscos

O ambiente é SQL Server Express local e a consulta é sintética. O snapshot de waits não foi zerado, então os valores refletem histórico da instância. Query Store captura a consulta de laboratório e também pode registrar a própria consulta de diagnóstico; a evidência identifica a query id principal para evitar confusão. Não foram incluídas métricas no Prometheus nesta fase.

## Próximo passo recomendado

A Fase 7 está completa no escopo definido. O próximo passo é revisar o README e a matriz de evidências para a apresentação do portfólio, ou iniciar a Fase 8 opcional de Kubernetes sem tratá-la como substituta de HA.

## Comandos granulares para salvar e commitar manualmente

Não foram executados `git add`, `git commit` ou `git push` pelo agente.

```powershell
git add .env.example README.md automation/README.md automation/sqlserverops.py sqlserver/README.md tests/test_sqlserverops.py
git commit -m "feat: add SQL Server Query Store diagnostics"

git add evidence/phase-7/README.md evidence/phase-7/sqlserver-performance-20261008T230012Z.json evidence/phase-7/round-022.md
git commit -m "docs: record SQL Server performance investigation"
```
