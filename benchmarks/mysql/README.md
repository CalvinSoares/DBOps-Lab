# Benchmark de performance do MariaDB

O benchmark desta pasta demonstra uma investigação operacional controlada, sem usar dados reais. A automação cria `performance_orders`, popula uma quantidade configurável de linhas e executa a consulta:

```sql
SELECT COUNT(*)
FROM performance_orders
WHERE region = 'north' AND status = 'open';
```

O procedimento coleta o plano sem índice, mede a consulta, cria o índice composto `(region, status)`, executa `ANALYZE TABLE`, coleta o plano novamente e consulta o digest em `performance_schema.events_statements_summary_by_digest`.

Execute a partir da raiz:

```powershell
python automation/benchmark_mysql.py --rows 50000 --repetitions 20
```

Cada execução cria `runs/<timestamp>/` com:

- `explain-before.tsv`;
- `explain-after.tsv`;
- `performance-schema.tsv`;
- `result.json`.

O benchmark é reproduzível, mas seus tempos dependem de CPU, memória, armazenamento, carga e versão do MariaDB. A conclusão deve usar o resultado salvo da execução, não uma estimativa genérica.
