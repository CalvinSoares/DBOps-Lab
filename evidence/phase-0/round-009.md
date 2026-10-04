# Rodada 009 — Fase 4: observabilidade PostgreSQL

## Identificação

- **Projeto:** DB Operations Lab — Resilient Multi-Database Platform
- **Fase:** 4 — Observabilidade e operação
- **Rodada:** 009
- **Agentes:** Observabilidade, DevOps/Automação, DBA PostgreSQL, QA/Incidentes e orquestrador
- **Data/hora:** 2026-10-03 21:19:30 -03:00 (America/Sao_Paulo)
- **Status:** coleta, dashboard e regras de alerta validados; exercícios de incidentes e métricas de backup pendentes

## Objetivo e escopo

Construir a primeira camada operacional do laboratório com:

1. PostgreSQL exporter usando a role `dbops_monitor`;
2. node-exporter para o ambiente Linux monitorado;
3. Prometheus com targets reais e regras de alerta;
4. Grafana provisionado por arquivos;
5. dashboard com disponibilidade, conexões, tamanho, transações, deadlocks, queries ativas, idade de query, CPU e memória;
6. check automatizado que consulta endpoints, PromQL, regras e API do Grafana.

O aceite completo de dashboards exercitados durante três incidentes e métricas de idade/falha de backup ficou deliberadamente fora desta rodada.

## Estado antes da rodada

- Prometheus e Grafana já apareciam no Compose, mas estavam apenas como placeholders;
- `monitoring/prometheus.yml` não tinha targets de PostgreSQL nem sistema operacional;
- não havia exporter PostgreSQL, node-exporter, dashboard provisionado ou regras;
- Check 4 estava completamente pendente.

## Alterações realizadas

### `docker-compose.yml`

- adicionados `postgres-exporter` com imagem `quay.io/prometheuscommunity/postgres-exporter:v0.15.0`;
- adicionados `node-exporter` com imagem `prom/node-exporter:v1.8.2`;
- ambos entram somente com `--profile monitoring`;
- exporter PostgreSQL conecta como `dbops_monitor` na rede Compose;
- Grafana passou a montar provisioning de datasource e dashboards;
- Prometheus passou a montar `alerts.yml`;
- node-exporter usa volume Linux somente leitura em `/host`;
- removida a opção `rslave`, incompatível com este Docker Desktop/Windows;
- porta host do node-exporter definida como `19100` para evitar conflito local; o target interno permanece `node-exporter:9100`.

### `.env.example` e `.env` local

Adicionadas imagens e portas pinadas para Prometheus exporter e node-exporter. O `.env` local recebeu os mesmos valores, sem ser versionado.

### `monitoring/prometheus.yml`

Configurados os jobs `postgresql` e `node`, além do carregamento de `/etc/prometheus/alerts.yml`.

### `monitoring/alerts.yml`

Criadas regras para:

- exporter PostgreSQL indisponível — `critical`;
- conexões acima do limite didático — `warning`;
- deadlock novo — `warning`;
- query ativa acima de 30 segundos — `warning`;
- filesystem com menos de 15% livre — `critical`.

Cada regra possui condição PromQL, duração, severidade, resumo e ação operacional.

### `monitoring/postgres_exporter_queries.yaml`

Adicionada consulta customizada do exporter para expor:

- `dbops_activity_active_queries`;
- `dbops_activity_max_query_age_seconds`.

Essas métricas representam sessões ativas e a idade da query ativa mais antiga por banco, vindas de `pg_stat_activity`.

### Grafana

- `monitoring/grafana/provisioning/datasources/prometheus.yml` provisiona Prometheus como datasource padrão;
- `monitoring/grafana/provisioning/dashboards/dashboards.yml` provisiona dashboards por arquivo;
- `monitoring/grafana/dashboards/dbops-postgres.json` contém 8 painéis;
- diretórios `plugins` e `alerting` possuem `.gitkeep` para evitar avisos de diretório ausente no Grafana.

### `automation/check_monitoring.py`

Criado check que:

- consulta `/metrics` do PostgreSQL exporter;
- consulta targets e PromQL do Prometheus;
- valida `pg_up`, `up{job="postgresql"}`, `up{job="node"}`;
- valida séries de CPU e idade máxima de query;
- valida regras carregadas em `/api/v1/rules`;
- valida saúde do Grafana;
- autentica na API do Grafana e confirma o dashboard `dbops-postgres`;
- grava JSON de evidência em `evidence/phase-0/`;
- retorna código não zero se qualquer camada falhar.

## Falhas encontradas e correções

### Montagem `rslave` no Docker Desktop/Windows

O node-exporter falhou com `path / is mounted on / but it is not a shared or slave mount`. A opção de propagação foi removida, mantendo o volume `/host:ro`. O container passou a iniciar e o Prometheus confirmou o target `node` como saudável.

### Porta host 9100 ocupada por outro serviço

O endpoint local `9100` respondia a uma aplicação diferente, embora o target interno do Prometheus estivesse correto. A porta host foi alterada para `19100`; o serviço continua escutando `9100` dentro da rede Compose.

### Nome real das métricas customizadas

O exporter prefixou o nome do bloco de consulta, produzindo `dbops_activity_max_query_age_seconds` em vez do nome inicialmente presumido. Dashboard, alerta e check foram ajustados após inspeção do endpoint real.

## Comandos executados e resultados

### Validação estática

```powershell
docker compose config --quiet
python -m py_compile automation/check_monitoring.py
python -m json.tool monitoring/grafana/dashboards/dbops-postgres.json
python -m unittest discover -s tests -v
```

Resultado: configuração Compose, Python, dashboard JSON e `3` testes unitários aprovados.

### Subida do stack

```powershell
docker compose --profile monitoring up -d
```

Serviços observados como ativos:

- PostgreSQL 16.4 saudável;
- Prometheus 2.54.1;
- Grafana 11.2.0;
- postgres-exporter v0.15.0;
- node-exporter v1.8.2.

### Check operacional final

```powershell
python automation/check_monitoring.py
```

Resultado observado:

- código de saída: `0`;
- exporter HTTP: `200`;
- Prometheus target PostgreSQL: `up=1`;
- `pg_up`: `1`;
- Prometheus target node: `up=1`;
- séries de CPU encontradas: `96`;
- série de idade de query: `1`;
- Grafana health: `200`;
- dashboard Grafana: `200`;
- painéis provisionados: `8`;
- grupos de alertas carregados: `1`;
- evidência final: `evidence/phase-0/monitoring-result-20261004T002226Z.json`.

Após o check, `docker compose --profile monitoring ps` confirmou os cinco serviços operacionais: PostgreSQL saudável, Prometheus, Grafana, postgres-exporter e node-exporter ativos. O node-exporter ficou publicado em `19100` no host e em `9100` dentro da rede Compose.

## Checks concluídos nesta rodada

- Check 4 — Prometheus coleta PostgreSQL: concluído.
- Check 4 — Grafana mostra disponibilidade, conexões, espaço e latência: concluído.
- Check 4 — queries ativas, deadlocks, CPU e memória: concluído.
- Check 4 — severidade, condição e ação dos alertas: concluído.
- Check 4 — fontes reais e ausência de painel decorativo: concluído.
- Check 4 — idade/falha de backup: pendente.
- Check 4 — dashboards exercitados durante três incidentes: pendente para a Fase 5.
- Checks 0 a 3: permanecem aprovados pelas rodadas anteriores.

## Limitações, riscos e decisões

- O node-exporter representa o ambiente Linux do Docker/WSL2, não necessariamente o Windows nativo.
- O dashboard não afirma idade ou sucesso de backup; essas métricas ainda não existem no exporter.
- As regras de alerta estão carregadas e avaliadas como saudáveis, mas ainda não foram exercitadas durante game days.
- A métrica de idade de query é uma visão agregada de `pg_stat_activity`; não substitui análise de plano, locks ou logs.
- O alerta de conexões usa limite didático de 50 sessões e deve ser calibrado para a capacidade real.

## Próximo passo

Formalizar a Fase 5 — incidentes e game days: executar query lenta, lock/deadlock, banco indisponível e disco cheio; comprovar que dashboards e alertas mudam; adicionar runbooks e métricas de idade/falha de backup.

## Comandos granulares para o usuário salvar e commitar

Estes comandos não foram executados pelo agente:

```powershell
git add .env.example docker-compose.yml monitoring automation/check_monitoring.py monitoring/README.md monitoring/postgres_exporter_queries.yaml evidence/phase-0/monitoring-result-*.json README.md automation/README.md
git commit -m "feat: add PostgreSQL monitoring stack"

git add evidence/phase-0/round-009.md
git commit -m "docs: record observability validation"
```

As alterações em `docs/` e `AGENTS.md` continuam ignoradas conforme a decisão da Rodada 003.
