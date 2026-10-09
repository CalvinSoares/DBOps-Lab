# Arquitetura do DB Operations Lab

![Arquitetura do DB Operations Lab](dbops-lab.svg)

O diagrama representa o estado atual do laboratório após as fases PostgreSQL, MariaDB e SQL Server. O caminho crítico é PostgreSQL; MariaDB e SQL Server demonstram extensões operacionais com profundidade proporcional ao ambiente disponível.

## Estado inicial da Fase 0

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

## Decisões atuais

- PostgreSQL é o caminho crítico e será aprofundado antes dos bancos secundários.
- Prometheus e Grafana usam profiles para manter o stack opcional.
- Exporters usam privilégios mínimos e credenciais somente no `.env` local.
- Volumes do Compose são persistentes, mas ainda não constituem uma estratégia de backup.
- Portas locais previstas: PostgreSQL `5432`, Prometheus `9090` e Grafana `3000`.
- MariaDB está validado com exporter e game day; SQL Server está validado no Windows/Express com limitação de compressão documentada.
- Kubernetes permanece opcional e não representa HA automaticamente.
