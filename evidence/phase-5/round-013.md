# Rodada 013 — Game day isolado de banco indisponível

## Identificação

- **Projeto:** DB Operations Lab — Resilient Multi-Database Platform
- **Fase:** 5 — Incidentes e game days
- **Rodada:** 013
- **Agentes:** QA/Incidentes, Observabilidade, DBA PostgreSQL, DevOps/Automação e orquestrador
- **Data/hora da validação final:** 2026-10-04 13:50:37 -03:00 (America/Sao_Paulo)
- **Status:** game day validado; terceiro incidente observável concluído

## Objetivo e escopo

Fechar o terceiro cenário necessário para o aceite de observabilidade sem interromper o PostgreSQL principal. Foi criado um Compose descartável contendo:

- PostgreSQL isolado;
- PostgreSQL Exporter isolado;
- Prometheus isolado;
- volume próprio;
- rede própria;
- projeto Compose próprio: `dbops_incident_down`.

O teste parou somente o container `incident-postgres`, observou a métrica `pg_up` cair para zero, iniciou o container novamente e confirmou o retorno para um. Ao final, containers e volumes descartáveis foram removidos.

## Estado antes da alteração

- Query lenta e lock já tinham snapshots Prometheus antes/durante/depois.
- O Check 4 ainda estava pendente porque faltava um terceiro incidente observável.
- O runbook de indisponibilidade existia, mas só estava em modo planejado.
- O Compose principal e o volume `postgres_data` estavam ativos e não deveriam ser interrompidos.

## Arquivos criados ou alterados

### `incidents/docker-compose.database-down.yml`

Define o ambiente descartável com imagens pinadas vindas do `.env`, credenciais somente por variável de ambiente, volume isolado e Prometheus exposto na porta `19090`.

### `incidents/prometheus.database-down.yml`

Configura scrape de 2 segundos para o exporter isolado, permitindo observar a transição rapidamente.

### `automation/run_database_down.py`

Implementa:

- `dry-run` padrão;
- execução explícita com `--execute`;
- subida do stack isolado;
- polling de `pg_up=1` antes do incidente;
- parada apenas de `incident-postgres`;
- polling de `pg_up=0` durante a indisponibilidade;
- subida do serviço;
- polling de `pg_up=1` após a recuperação;
- cleanup com `down --volumes --remove-orphans` no projeto isolado;
- JSON de evidência sem segredos;
- códigos de saída não zero em falhas.

### `tests/test_database_down.py`

Adicionados dois testes unitários para confirmar isolamento do projeto/porta e leitura da série `pg_up`.

### `incidents/04-database-down.md`

Atualizado com o procedimento reproduzível e a distinção entre o game day descartável e uma recuperação do ambiente principal.

## Comandos executados e resultados

### Sintaxe, testes e dry-run

```powershell
python -m py_compile automation/run_database_down.py
python -m unittest discover -s tests -v
python automation/run_database_down.py
```

Resultado:

- sintaxe aprovada;
- `7` testes unitários aprovados;
- dry-run retornou código `0`;
- nenhum container principal foi alterado.

### Game day real

```powershell
python automation/run_database_down.py --execute
```

Evidência: [`incident-database-down-20261004T165037Z.json`](incident-database-down-20261004T165037Z.json).

Resultado observado:

- stack isolado iniciado: aprovado;
- PostgreSQL isolado disponível: `pg_up=1`;
- indisponibilidade observada: `pg_up=0`;
- serviço recuperado: `pg_up=1`;
- cleanup do projeto e volumes isolados: concluído;
- status final: `validated=true`;
- código de saída: `0`.

Sequência validada:

```text
pg_up=1  →  pg_up=0  →  pg_up=1
```

### Regresão do ambiente principal

```powershell
python -m unittest discover -s tests -v
python automation/check_monitoring.py
docker compose --profile monitoring ps
```

Resultado: `7` testes aprovados; PostgreSQL principal `healthy`; `pg_up=1`; targets PostgreSQL e node ativos; Grafana health/dashboard `200`; 10 painéis; backup lógico sem falha. A evidência final da regressão é [`monitoring-result-20261004T165141Z.json`](../phase-0/monitoring-result-20261004T165141Z.json).

## Checks atualizados

- Check 4 — dashboards exercitados durante três incidentes: concluído.
- Check 5 — banco indisponível possui diagnóstico e recuperação: game day isolado concluído.
- Check 5 — query lenta, lock e backup inválido: já validados nas rodadas anteriores.
- Check 5 — disco cheio: continua pendente por risco operacional.
- Check 5 — atraso de réplica: não aplicável enquanto não houver réplica configurada.

## Limitações, riscos e decisões

- O teste comprova detecção e recuperação de um container descartável, não falha física do volume principal.
- O PostgreSQL principal não foi parado.
- O Prometheus isolado usa scrape de 2 segundos apenas para reduzir a duração do game day; isso não altera o intervalo do monitoramento principal.
- A execução remove os volumes do projeto descartável de propósito, portanto não deve ser apontada para o projeto principal.

## Próximo passo

Com o aceite de observabilidade concluído, iniciar a Fase 6: MySQL/MariaDB com provisionamento, health check, backup lógico, restore, consistência, Performance Schema e um incidente controlado.

## Comandos granulares para o usuário salvar e commitar

Estes comandos não foram executados pelo agente:

```powershell
git add automation/run_database_down.py tests/test_database_down.py incidents/docker-compose.database-down.yml incidents/prometheus.database-down.yml incidents/04-database-down.md incidents/README.md evidence/phase-5/incident-database-down-20261004T165037Z.json evidence/phase-0/monitoring-result-20261004T165141Z.json
git commit -m "feat: add isolated database outage game day"

git add evidence/phase-5/round-013.md
git commit -m "docs: record database outage game day"
```

As alterações em `docs/` e `AGENTS.md` continuam ignoradas conforme a política do projeto.
