# Rodada 011 — Telemetria de backup e bloqueios

## Identificação

- **Projeto:** DB Operations Lab — Resilient Multi-Database Platform
- **Fase:** Fase 5 em continuidade, fechando pendências operacionais da Fase 4
- **Rodada:** 011
- **Agentes:** DBA PostgreSQL, Observabilidade, DevOps/Automação, QA e orquestrador
- **Data/hora da validação final:** 2026-10-03 21:36:57 -03:00 (America/Sao_Paulo)
- **Status:** métricas de backup e lock validadas; exercício visual durante incidentes ainda pendente

## Objetivo e escopo

Adicionar telemetria operacional que faltava para backup e bloqueios:

1. registrar no PostgreSQL a última tentativa, sucesso, falha, idade, duração, tamanho e artefato de cada tipo de backup;
2. exportar status de backup e sessões aguardando lock para Prometheus;
3. criar alertas para backup falho e backup atrasado;
4. ampliar o dashboard Grafana e o check automatizado;
5. aplicar a migration e executar backup lógico/físico real para alimentar as séries.

Não foram executados backups corrompidos no artefato original, preenchimento de disco, parada do banco ou alteração destrutiva de dados.

## Estado antes da alteração

- O backup gerava manifesto e logs locais, mas não existia uma fonte consultável pelo exporter para idade ou falha.
- O dashboard tinha tamanho do banco, mas não tinha status de backup nem sessões aguardando lock.
- O check de monitoramento validava targets, query age e Grafana, mas não verificava as novas fontes.
- A Fase 4 ainda tinha o check de idade/falha de backup pendente.

## Alterações realizadas

### `migrations/002_backup_status.sql`

Criada a tabela `public.dbops_backup_status` com uma linha por tipo (`logical` e `physical`). O monitor `dbops_monitor` recebe somente `SELECT` nessa tabela. O provisionamento continua idempotente porque a migration é registrada em `schema_migrations`.

### `automation/dbops.py`

Adicionada `record_backup_status`, que:

- grava timestamp da tentativa;
- grava último sucesso e última falha separadamente;
- registra duração, tamanho e nome do artefato;
- incrementa `failure_count` e guarda apenas o tipo do erro, sem mensagem potencialmente sensível;
- não esconde a falha original caso a telemetria não consiga ser escrita.

Os caminhos lógico e físico agora registram sucesso e falha ao redor da execução do backup.

### `monitoring/postgres_exporter_queries.yaml`

Adicionadas consultas customizadas para:

- `dbops_lock_waits_blocked_queries`;
- `dbops_backup_status_age_seconds`;
- `dbops_backup_status_failed`;
- `dbops_backup_status_duration_seconds`;
- `dbops_backup_status_size_bytes`.

O prefixo `dbops_backup_status_` é produzido pelo exporter a partir do nome do bloco YAML. Esse detalhe foi confirmado no endpoint `/metrics` e refletido no dashboard, nos alertas e no check.

### `monitoring/alerts.yml`

Adicionados:

- `PostgreSQLBackupFailed`, severidade `critical`, quando o último backup está ausente ou falhou;
- `PostgreSQLBackupStale`, severidade `warning`, quando o último sucesso tem mais de 24 horas.

### `monitoring/grafana/dashboards/dbops-postgres.json`

O dashboard passou de 8 para 10 painéis, incluindo:

- sessões aguardando lock;
- idade, falha e duração do backup lógico.

### `automation/check_monitoring.py`

O check agora exige séries de idade e falha de backup, confirma `backup_failed=0` para o backup lógico e verifica a série de lock waits.

### Documentação

`monitoring/README.md`, `docs/CHECKS.md` e `docs/EVIDENCE_MATRIX.md` foram atualizados. Os arquivos em `docs/` continuam ignorados pelo Git conforme a política do projeto, mas o estado local foi atualizado para uso dos agentes.

## Comandos executados e resultados

### Validação estática

```powershell
python -m py_compile automation/dbops.py automation/check_monitoring.py
python -m json.tool monitoring/grafana/dashboards/dbops-postgres.json
docker compose config --quiet
```

Resultado: sintaxe Python, JSON do dashboard e Compose aprovados.

### Provisionamento e backup real

```powershell
python automation/dbops.py provision
python automation/dbops.py backup --type both
```

Resultado do provisionamento: migration `002_backup_status.sql` aplicada e 5 roles presentes.

Resultado do backup lógico:

- artefato: `dbops_20261004T003341Z.dump`;
- tamanho: `12776` bytes;
- SHA-256: `cc216c9b98cd8f30295b04dc795a15f956389d7777513f427fc9260d6100e2be`.

Resultado do backup físico: diretório `postgres/backup/physical/dbops_20261004T003342Z`, com manifesto e aproximadamente `72.9 MB` contabilizados pelo status gravado. O valor exato está no endpoint e nos artefatos locais; não foi transformado em métrica de currículo nesta rodada.

### Recriação da observabilidade

```powershell
docker compose --profile monitoring up -d --force-recreate postgres-exporter prometheus grafana
```

O restart foi necessário porque as consultas customizadas são carregadas no início do exporter e as regras/dashboard são carregados na inicialização dos respectivos serviços.

### Check operacional final

```powershell
python automation/check_monitoring.py
```

Evidência final: [`monitoring-result-20261004T003657Z.json`](monitoring-result-20261004T003657Z.json).

Resultado observado:

- código de saída: `0`;
- exporter HTTP: `200`;
- Prometheus target PostgreSQL: `up=1`;
- `pg_up=1`;
- Prometheus target node: `up=1`;
- séries de CPU: `96`;
- série de idade de query: `1`;
- série de lock waits: `1`;
- série de idade de backup lógico: `1`;
- série de falha de backup lógico: `1`, valor atual `0`;
- Grafana health: `200`;
- dashboard Grafana: `200`;
- painéis provisionados: `10`;
- grupos de alertas: `1`.

### Diagnóstico e correção encontrados

Na primeira tentativa, o check procurava `dbops_backup_age_seconds` e não encontrava séries. A inspeção de `/metrics` mostrou os nomes reais prefixados como `dbops_backup_status_age_seconds`, `dbops_backup_status_failed` e demais variantes. Alertas, dashboard e check foram corrigidos; a segunda validação passou.

## Checks atualizados

- Check 4 — idade/falha do backup e tamanho do banco: concluído com evidência reproduzível.
- Check 4 — targets, Grafana, alertas e fontes reais: continuam concluídos.
- Check 4 — dashboards exercitados durante três incidentes: pendente; a validação atual prova fontes e regras, mas não captura uma janela PromQL durante cada incidente.
- Check 5 — query lenta, lock e backup inválido: validados na Rodada 010.
- Check 5 — banco indisponível, disco cheio e réplica: continuam pendentes por risco/ausência de ambiente aplicável.

## Limitações e riscos

- O exporter usa o formato de consultas estendidas marcado como deprecated pela versão `v0.15.0`; ele funciona e foi validado, mas a migração para o formato futuro deve ser planejada.
- O status de backup depende de a operação ser executada pela CLI `dbops.py`; backups externos não atualizam a tabela automaticamente.
- O alerta de backup atrasado usa 24 horas como limite didático. A política real de retenção e frequência ainda deve ser definida junto ao RPO.
- O painel exibe o backup lógico; as métricas físicas também existem e podem receber painel separado em uma rodada posterior.

## Próximo passo

Adicionar um check que capture snapshots PromQL antes/durante/depois de três game days, demonstrando mudança real de query age, lock waits e disponibilidade. Depois disso, fechar o aceite visual da observabilidade e seguir para MySQL/MariaDB.

## Comandos granulares para o usuário salvar e commitar

Estes comandos não foram executados pelo agente:

```powershell
git add migrations/002_backup_status.sql automation/dbops.py automation/check_monitoring.py monitoring/postgres_exporter_queries.yaml monitoring/alerts.yml monitoring/grafana/dashboards/dbops-postgres.json monitoring/README.md evidence/phase-0/monitoring-result-20261004T003657Z.json
git commit -m "feat: expose backup and lock telemetry"

git add evidence/phase-0/round-011.md
git commit -m "docs: record backup telemetry validation"
```

As alterações em `docs/` e `AGENTS.md` continuam ignoradas conforme a decisão da Rodada 003.
