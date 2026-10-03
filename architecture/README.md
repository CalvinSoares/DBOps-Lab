# Arquitetura inicial

## Estado da Fase 0

Nesta fase, o único banco ativo é o PostgreSQL. Prometheus e Grafana existem como perfil opcional de Compose para validar a fundação de observabilidade, mas ainda não coletam métricas do banco.

```text
┌──────────────────────┐
│ automation/dbops.py  │  (Fase 1)
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐       ┌──────────────────────┐
│ PostgreSQL            │──────▶│ Volume postgres_data │
│ serviço principal     │       └──────────────────────┘
└──────────┬───────────┘
           │
           │ exporter (Fase 4)
           ▼
┌──────────────────────┐       ┌──────────────────────┐
│ Prometheus (opcional)│──────▶│ Grafana (opcional)   │
└──────────────────────┘       └──────────────────────┘
```

## Decisões

- PostgreSQL é o caminho crítico e será aprofundado antes dos bancos secundários.
- Prometheus e Grafana usam profiles para não obrigar observabilidade incompleta na primeira execução.
- A role do exporter não é criada nesta fase; ela será criada com privilégios mínimos na fase de provisionamento.
- Volumes do Compose são persistentes, mas ainda não constituem uma estratégia de backup.
- Portas locais previstas: PostgreSQL `5432`, Prometheus `9090` e Grafana `3000`.
- MySQL/MariaDB, SQL Server e Kubernetes entram em fases posteriores e não fazem parte do gate da Fase 0.
