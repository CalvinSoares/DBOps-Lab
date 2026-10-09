# Rodada 017 — diagnóstico de performance do MariaDB

## Identificação

- Fase: 6 — MySQL/MariaDB secundário
- Data/hora: 2026-10-08 19:48:05 -03:00
- Agente responsável: DBA secundário / QA
- Status: Performance Schema e tuning controlado validados; incidente ainda pendente

## Objetivo e escopo

Esta rodada habilitou explicitamente o Performance Schema no serviço MariaDB e executou uma investigação reproduzível de consulta lenta. O benchmark criou dados sintéticos, coletou o plano sem índice, aplicou um índice composto, coletou o plano depois e comparou duração e métricas do digest.

Ficaram fora desta rodada o exporter, dashboard, alertas e simulação de falha. O benchmark não representa carga de produção e não autoriza declarar um ganho geral de performance.

## Estado observado antes

O primeiro ciclo MariaDB estava validado, mas `@@performance_schema` retornava `0` e não havia benchmark secundário. O serviço foi alterado para iniciar com `mariadbd --performance-schema=ON`.

## Arquivos criados ou alterados

- `docker-compose.yml`: habilitado `--performance-schema=ON` somente no serviço MariaDB do profile `secondary`.
- `automation/benchmark_mysql.py`: criada automação com preparação de dataset, medição, `EXPLAIN`, índice composto, `ANALYZE TABLE`, coleta de digest e saída JSON.
- `tests/test_benchmark_mysql.py`: adicionados testes da consulta controlada e da coleta pelo Performance Schema.
- `mysql/README.md`: documentado o comando de benchmark e os artefatos.
- `automation/README.md`: incluído o fluxo MariaDB de performance.
- `benchmarks/mysql/README.md`: documentado o método e as limitações de interpretação.
- `docs/CHECKS.md` e `docs/EVIDENCE_MATRIX.md`: Performance Schema marcado como validado porque há evidência reproduzível.

## Comandos executados e resultados

```text
docker compose --profile secondary up -d mariadb
SELECT @@performance_schema;
python -m py_compile automation/benchmark_mysql.py
python -m unittest discover -s tests -v
python automation/benchmark_mysql.py --rows 50000 --repetitions 20
```

Resultados:

- `@@performance_schema = 1`;
- 11 testes automatizados aprovados;
- dataset sintético: 50.000 linhas;
- consulta executada 20 vezes antes e depois;
- resultado sem índice: 4.166 linhas;
- resultado com índice: 4.166 linhas;
- duração antes: 0,657 s;
- duração depois: 0,531 s;
- razão medida antes/depois: 1,237x;
- plano antes: `ALL`, sem índice, estimativa de 50.000 linhas;
- plano depois: `ref`, índice `idx_performance_orders_region_status`, estimativa de 4.166 linhas, `Using index`;
- Performance Schema: digest encontrado com 40 execuções, 1.083.320 linhas examinadas e 184,694 ms acumulados no snapshot.

Os artefatos estão em `benchmarks/mysql/runs/20261008T224805Z/`.

## Conceitos demonstrados

`EXPLAIN` evidencia a forma de acesso escolhida pelo otimizador, mas não substitui medição real. O índice composto atende exatamente aos predicados de igualdade da consulta e permite acesso `ref` com cobertura do resultado. `ANALYZE TABLE` atualiza estatísticas depois da alteração. O Performance Schema fornece visão agregada por digest, incluindo contagem, tempo acumulado e linhas examinadas, útil para priorizar investigação operacional.

## Limitações e riscos

O tempo inclui a execução via cliente de laboratório e não é um benchmark isolado de produção. A diferença observada foi de 1,237x nesta máquina e nesta carga; não deve ser copiada para currículo como percentual universal. O Performance Schema agrega sessões e execuções existentes, portanto o digest deve ser interpretado junto com o timestamp e os arquivos da rodada. A tabela é sintética e pertence ao laboratório.

## Pendências e critério de desbloqueio

1. Incidente MariaDB: criar runbook e executar uma falha em ambiente descartável, com detecção, contenção, recuperação e validação.
2. Observabilidade MariaDB: adicionar exporter e métrica no Prometheus/Grafana, com mudança observável.

O Check 6 ainda não está totalmente validado porque a simulação de falha permanece pendente.

## Próximo passo recomendado

Continuar na Fase 6 com um runbook de indisponibilidade do MariaDB e uma execução isolada. Depois disso, completar as métricas do banco secundário antes de iniciar SQL Server.

## Comandos granulares para salvar e commitar manualmente

Não foram executados `git add`, `git commit` ou `git push` pelo agente.

```powershell
git add docker-compose.yml automation/benchmark_mysql.py tests/test_benchmark_mysql.py mysql/README.md automation/README.md benchmarks/mysql/README.md benchmarks/mysql/runs/20261008T224805Z evidence/phase-6/round-017.md
git commit -m "feat: add MariaDB Performance Schema benchmark"
```
