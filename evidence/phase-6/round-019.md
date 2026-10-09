# Rodada 019 — observabilidade MariaDB

## Identificação

- Fase: 6 — MySQL/MariaDB secundário
- Data/hora: 2026-10-08 19:54:44 -03:00
- Agente responsável: Observabilidade / DevOps / DBA secundário
- Status: exporter, coleta Prometheus, alertas e dashboards validados

## Objetivo e escopo

Esta rodada integrou o MariaDB ao stack de observabilidade. O serviço passou a expor métricas por `mysqld_exporter`, o Prometheus recebeu um target `mariadb`, regras de alerta foram adicionadas e um dashboard Grafana específico foi provisionado.

Foram cobertas disponibilidade, conexões, threads ativos, queries lentas, uptime e temporárias em disco. Não foram criadas métricas customizadas para RPO/RTO nem métricas de replicação, pois este laboratório ainda não possui réplica MariaDB configurada.

## Estado observado antes

O Prometheus e o Grafana existentes cobriam PostgreSQL e sistema operacional. O MariaDB possuía Performance Schema e game day, mas não tinha exporter, target, alertas ou dashboard próprio.

## Arquivos criados ou alterados

- `.env.example`: imagem e porta do exporter MariaDB.
- `docker-compose.yml`: serviço `mariadb-exporter`, profile `monitoring` + `secondary`, geração interna de `.my.cnf` e dependência do health check do MariaDB.
- `mysql/init/001_schema.sql`: permissões mínimas do usuário de laboratório para o exporter.
- `monitoring/prometheus.yml`: target `mariadb-exporter:9104` no job `mariadb`.
- `monitoring/alerts.yml`: alertas de exporter indisponível, banco indisponível, conexões altas e aumento de queries lentas.
- `monitoring/grafana/dashboards/dbops-mariadb.json`: dashboard com cinco painéis.
- `automation/check_mariadb_monitoring.py`: check de endpoint, target, séries e resultado estruturado.
- `tests/test_mariadb_monitoring.py`: testes estáticos das métricas essenciais.
- `README.md`, `automation/README.md` e `monitoring/README.md`: comandos, portas e limitações documentados.
- `docs/EVIDENCE_MATRIX.md`: observabilidade MariaDB marcada como validada.

## Comandos executados e resultados

```text
python automation/mysqlops.py provision
docker compose --profile monitoring --profile secondary up -d mariadb mariadb-exporter prometheus
docker compose --profile monitoring --profile secondary up -d grafana
python -m py_compile automation/check_mariadb_monitoring.py
python -m unittest discover -s tests -v
python automation/check_mariadb_monitoring.py
```

Resultados observados:

- 15 testes automatizados aprovados;
- exporter `prom/mysqld-exporter:v0.15.1` estável;
- endpoint do exporter respondeu HTTP 200 com 192.535 bytes de métricas;
- target Prometheus `mariadb` respondeu `up=1`;
- `mysql_up=1`;
- conexões: 1;
- threads ativos: 1;
- queries lentas: 0;
- uptime observado: 363 segundos;
- quatro regras MariaDB carregadas: `MariaDBExporterDown`, `MariaDBDown`, `MariaDBConnectionsHigh` e `MariaDBSlowQueriesIncreasing`;
- dashboard `dbops-mariadb` carregado no Grafana com cinco painéis;
- dashboard PostgreSQL existente continuou carregado com dez painéis;
- Grafana foi validado na porta local 33000 porque 3000 e 3001 já estavam ocupadas nesta máquina.

O primeiro resultado Prometheus está em `mariadb-monitoring-20261008T225343Z.json`; a validação final após a subida completa do stack está em `mariadb-monitoring-20261008T225522Z.json`. A validação da API Grafana está em `mariadb-grafana-20261008T225444Z.json`.

## Problemas encontrados e correções

1. A imagem inicial `prometheuscommunity/mysqld-exporter` não existia no registry utilizado. Foi substituída por `prom/mysqld-exporter:v0.15.1`.
2. A versão do exporter não aceitou `DATA_SOURCE_NAME`; o container passou a gerar `.my.cnf` temporário com variáveis de ambiente e iniciar com `--config.my-cnf`.
3. O comando shell foi ajustado para usar um único argumento para o entrypoint `/bin/sh -c`, evitando interpretação incorreta do Compose.
4. A porta 3000 e depois 3001 estavam ocupadas. Nenhum processo externo foi encerrado; o `.env` local usou 33000.

Essas tentativas não foram tratadas como sucesso; somente a execução final foi registrada como validada.

## Conceitos demonstrados

O exporter transforma status do banco em métricas Prometheus. O target `up` mede a cadeia de coleta, enquanto `mysql_up` diferencia exporter acessível de banco consultável. As regras separam falha de coleta, falha do banco, saturação de conexões e crescimento de queries lentas. O dashboard é provisionado por arquivo e não depende de configuração manual na interface.

## Limitações e riscos

As credenciais são interpoladas apenas no container e permanecem no `.env` ignorado. O usuário `dbops_mysql` recebeu somente as permissões necessárias ao exporter. As métricas de queries lentas são contadores globais; uma investigação detalhada continua sendo feita pelo Performance Schema. O ambiente local possui conflito de portas, então a porta Grafana deve ser ajustada conforme a máquina.

## Próximo passo recomendado

A Fase 6 está completa. O próximo passo é iniciar a Fase 7 com SQL Server Developer e Windows: documentar a execução disponível, backup full/differential/log, CHECKSUM, compressão, restore separado e Query Store ou waits.

## Comandos granulares para salvar e commitar manualmente

Não foram executados `git add`, `git commit` ou `git push` pelo agente.

```powershell
git add .env.example docker-compose.yml mysql/init/001_schema.sql monitoring/prometheus.yml monitoring/alerts.yml monitoring/grafana/dashboards/dbops-mariadb.json automation/check_mariadb_monitoring.py tests/test_mariadb_monitoring.py README.md automation/README.md monitoring/README.md
git commit -m "feat: add MariaDB monitoring stack"

git add evidence/phase-6/mariadb-monitoring-20261008T225343Z.json evidence/phase-6/mariadb-grafana-20261008T225444Z.json evidence/phase-6/README.md evidence/phase-6/round-019.md
git commit -m "docs: record MariaDB monitoring validation"
```
