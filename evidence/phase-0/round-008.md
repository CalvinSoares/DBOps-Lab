# Rodada 008 — Fase 3: tuning e diagnóstico PostgreSQL

## Identificação

- **Projeto:** DB Operations Lab — Resilient Multi-Database Platform
- **Fase:** 3 — Tuning e diagnóstico
- **Rodada:** 008
- **Agentes:** DBA PostgreSQL, DevOps/Automação, QA/Incidentes e orquestrador
- **Data/hora:** 2026-10-03 21:04:24 -03:00 (America/Sao_Paulo)
- **Status:** benchmark de plano e lock validado

## Objetivo e escopo

Demonstrar investigação de performance baseada em evidência, sem alterar as tabelas de aplicação. A rodada deveria produzir:

1. dataset conhecido e reproduzível;
2. consulta propositalmente lenta;
3. `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` antes;
4. hipótese de índice composto;
5. `ANALYZE` e plano depois;
6. comparação de tempo, nós do plano, linhas removidas e buffers;
7. cenário seguro de lock com sessão bloqueadora identificada.

O escopo não incluiu tuning permanente das tabelas de produção, alteração global de parâmetros, teste de CPU do host ou configuração de log de queries lentas. Esses itens permanecem para evoluções posteriores.

## Estado antes da rodada

- Check 3 estava completamente pendente;
- não havia benchmark PostgreSQL versionado;
- não havia evidência de `EXPLAIN (ANALYZE, BUFFERS)` antes/depois;
- não havia demonstração de `pg_stat_activity` e `pg_blocking_pids` em lock.

## Alterações realizadas

### `automation/benchmark_postgres.py`

Criado um executor reproduzível que:

- aceita `--rows` e exige pelo menos 10.000 linhas;
- cria um schema único `benchmark_<run_id>`;
- insere dados sintéticos com `generate_series`;
- executa `ANALYZE` antes do plano inicial;
- captura planos JSON antes e depois;
- cria índice composto `(customer_id, status, created_at DESC)` com `order_id` incluído;
- captura métricas recursivamente de todos os nós do plano;
- reproduz lock com `SELECT ... FOR UPDATE`;
- aplica `lock_timeout=5s` na sessão bloqueada;
- consulta `pg_stat_activity` e `pg_blocking_pids`;
- remove o schema somente com `--cleanup`;
- retorna código não zero em falha e grava resultado sem credenciais.

### `benchmarks/postgres/README.md`

Documentada a hipótese, o comando de execução, o significado dos artefatos e quando um índice não deve ser criado.

### `tests/test_benchmark_postgres.py`

Adicionado teste unitário da extração de métricas de planos aninhados.

### Artefatos gerados

- `benchmarks/postgres/runs/20261004T000351Z_a48486b9/plan-before.json`;
- `benchmarks/postgres/runs/20261004T000351Z_a48486b9/plan-after.json`;
- `benchmarks/postgres/runs/20261004T000351Z_a48486b9/result.json`.

O schema sintético foi removido ao final e não permanece no PostgreSQL.

## Falhas encontradas e correções

### Import ao executar o arquivo diretamente

A primeira execução falhou porque `python automation/benchmark_postgres.py` não colocava a raiz do projeto no caminho de importação. O script passou a adicionar a raiz de forma explícita antes de importar `automation.dbops`.

### Operador `%` interpretado como placeholder

A segunda execução chegou ao PostgreSQL, mas o psycopg interpretou os operadores `%` de `generate_series` como placeholders. Os operadores foram escapados como `%%` na string parametrizada.

Nenhum desses testes incompletos foi usado como evidência.

## Comandos executados e resultados

### Testes prévios

```powershell
python -m py_compile automation/benchmark_postgres.py
python -m unittest discover -s tests -v
```

Resultado: compilação aprovada e `3` testes unitários aprovados.

### Benchmark final

```powershell
python automation/benchmark_postgres.py --rows 200000 --cleanup
```

Resultado: código `0`, `200000` linhas geradas, duração total de `7,344 s`, schema removido após a coleta.

Consulta analisada:

```sql
SELECT order_id, customer_id, status, created_at
FROM "benchmark_20261004t000351z_a48486b9"."orders"
WHERE customer_id = 777
  AND status = 'open'
  AND created_at >= TIMESTAMPTZ '2026-01-01'
ORDER BY created_at DESC
LIMIT 50;
```

### Plano antes

- nós: `Limit`, `Gather Merge`, `Sort`, `Seq Scan`;
- tempo de execução: `20,872 ms`;
- linhas removidas pelo filtro: `66600`;
- buffers compartilhados em cache: `16670`;
- buffers compartilhados lidos: `0`.

### Alteração

Foi criado o índice:

```sql
CREATE INDEX idx_benchmark_20261004t000351z_a48486b9_customer_status_created
ON benchmark_20261004t000351z_a48486b9.orders
    (customer_id, status, created_at DESC)
INCLUDE (order_id);
```

Depois foi executado `ANALYZE` na tabela.

### Plano depois

- nós: `Limit`, `Index Only Scan`;
- tempo de execução: `0,145 ms`;
- linhas removidas pelo filtro: `0`;
- buffers compartilhados em cache: `100`;
- buffers compartilhados lidos: `8`.

A comparação medida foi de `20,872 ms` para `0,145 ms`, aproximadamente 144 vezes menor nesta execução. Esse número é específico do dataset, hardware e cache do laboratório; não é uma garantia de produção.

### Lock e sessão bloqueadora

Resultado observado:

- sessão titular: PID `3047`;
- sessão bloqueada: PID `3048`;
- `wait_event_type`: `Lock`;
- `wait_event`: `transactionid`;
- `pg_blocking_pids(3048)`: `[3047]`;
- erro esperado da sessão bloqueada: `LockNotAvailable`;
- mensagem: `canceling statement due to lock timeout`;
- validação: `true`.

A sessão titular foi revertida e todas as conexões foram fechadas no bloco de limpeza.

### Checks finais

```powershell
python automation/dbops.py health-check
```

Resultado: health check aprovado com PostgreSQL 16.4, `4` tabelas, `1` migration e aproximadamente `7,7 MB` no banco de laboratório.

## Checks concluídos nesta rodada

- Check 3 — consulta lenta reproduzível: concluído.
- Check 3 — plano antes/depois com `EXPLAIN (ANALYZE, BUFFERS)`: concluído.
- Check 3 — hipótese, índice isolado, `ANALYZE` e comparação: concluído.
- Check 3 — buffers, linhas removidas e tempo: concluído.
- Check 3 — lock, bloqueador e mitigação por timeout: concluído.
- Checks 0, 1 e 2: permanecem aprovados conforme evidências anteriores.
- Check 4 em diante: pendentes.

## Limitações e riscos

- O benchmark usa dados artificiais e não representa cardinalidade, distribuição ou concorrência de uma carga real.
- Os buffers compartilhados são uma proxy de I/O/cache; não houve medição de CPU do host.
- A consulta final usa um índice específico; antes de aplicar índice em produção devem ser avaliados seletividade, custo de escrita, duplicidade e tamanho.
- O cenário reproduz lock e timeout, mas ainda não é um runbook formal em `incidents/`; isso pertence à Fase 5.
- Não foi configurado ainda `log_min_duration_statement`, `auto_explain` ou coleta de queries lentas.

## Próximo passo

Avançar para a Fase 4 — observabilidade: Prometheus, exporter PostgreSQL, métricas de disponibilidade, conexões, espaço, latência, queries lentas, deadlocks, idade do backup e dashboards com dados reais.

## Comandos granulares para o usuário salvar e commitar

Estes comandos não foram executados pelo agente:

```powershell
git add automation/benchmark_postgres.py benchmarks/postgres/README.md benchmarks/postgres/runs/20261004T000351Z_a48486b9/plan-before.json benchmarks/postgres/runs/20261004T000351Z_a48486b9/plan-after.json benchmarks/postgres/runs/20261004T000351Z_a48486b9/result.json tests/test_benchmark_postgres.py README.md
git commit -m "feat: add PostgreSQL tuning and lock benchmark"

git add evidence/phase-0/round-008.md
git commit -m "docs: record PostgreSQL tuning evidence"
```

As alterações em `docs/` e `AGENTS.md` continuam ignoradas conforme a decisão da Rodada 003.
