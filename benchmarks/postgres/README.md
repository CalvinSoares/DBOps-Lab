# Benchmark PostgreSQL — tuning e locks

O script `automation/benchmark_postgres.py` cria um schema sintético único, executa uma consulta seletiva sem índice, coleta `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`, cria um índice composto, executa `ANALYZE`, coleta o plano novamente e reproduz um lock entre duas sessões.

## Execução

```powershell
python automation/benchmark_postgres.py --rows 200000 --cleanup
```

Sem `--cleanup`, o schema `benchmark_<run_id>` permanece no PostgreSQL para inspeção. Com `--cleanup`, somente o schema criado pela execução é removido após os arquivos de evidência serem gravados.

Cada execução gera em `benchmarks/postgres/runs/<run_id>/`:

- `plan-before.json`: plano antes do índice;
- `plan-after.json`: plano depois do índice e do `ANALYZE`;
- `result.json`: métricas resumidas, comparação e lock.

## Hipótese

A consulta filtra por `customer_id`, `status` e `created_at`, ordenando pela data. Sem um índice compatível, a expectativa é uma varredura sequencial e filtragem de muitas linhas. O índice composto `(customer_id, status, created_at DESC)` deve permitir acesso seletivo e reduzir linhas examinadas e buffers.

O resultado deve ser interpretado pelo plano real, não pela hipótese. Um índice não deve ser criado automaticamente quando a coluna tem baixa seletividade, quando a consulta é rara, quando o custo de escrita supera o ganho ou quando já existe um índice equivalente.

## Lock

Uma sessão mantém `SELECT ... FOR UPDATE`; outra tenta atualizar a mesma linha com `lock_timeout=5s`; uma terceira consulta `pg_stat_activity` e `pg_blocking_pids`. O update bloqueado deve terminar com `LockNotAvailable`, e a transação da sessão titular é revertida.
