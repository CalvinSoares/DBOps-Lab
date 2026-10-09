# Rodada 018 — game day de indisponibilidade do MariaDB

## Identificação

- Fase: 6 — MySQL/MariaDB secundário
- Data/hora: 2026-10-08 19:49:56 -03:00
- Agente responsável: DBA secundário / QA/Incidentes
- Status: falha simulada e recuperação validadas em ambiente descartável

## Objetivo e escopo

Esta rodada criou um runbook e uma automação para simular indisponibilidade do MariaDB. O cenário sobe um projeto Docker Compose separado, valida disponibilidade, interrompe somente o serviço descartável, observa a falha, reinicia o serviço, valida `SELECT 1` e remove seus recursos.

O volume persistente e o container MariaDB principal não foram utilizados nem interrompidos. Não foi simulada corrupção de volume, perda de dados, disco cheio ou falha no banco principal.

## Estado observado antes

O Check 6 possuía provisionamento, backup/restore, consistência e Performance Schema validados, mas a simulação de falha MariaDB ainda estava pendente. Já existia um padrão de game day PostgreSQL isolado, que foi usado apenas como referência de segurança e estrutura.

## Arquivos criados ou alterados

- `incidents/docker-compose.mariadb-down.yml`: Compose descartável sem volume persistente.
- `incidents/09-mariadb-down.md`: runbook com impacto, detecção, contenção, diagnóstico, recuperação, validação e limitações.
- `automation/run_mariadb_down.py`: executor com `dry-run` padrão, modo `--execute`, estados antes/durante/depois, códigos de saída e cleanup.
- `tests/test_mariadb_down.py`: testes de isolamento e presença do plano de recuperação.
- `incidents/README.md`: cenário adicionado à matriz de incidentes.
- `automation/README.md`: comandos e limites documentados.
- `README.md`: status operacional do MariaDB atualizado.
- `evidence/phase-6/README.md`: inventário da evidência da fase atualizado.
- `docs/CHECKS.md` e `docs/EVIDENCE_MATRIX.md`: falha do MariaDB marcada como validada.

## Comandos executados e resultados

```text
python -m py_compile automation/run_mariadb_down.py
python -m unittest discover -s tests -v
python automation/run_mariadb_down.py
python automation/run_mariadb_down.py --execute
python automation/run_mariadb_down.py --execute
```

Checks estáticos:

- 13 testes automatizados aprovados;
- modo `dry-run` retornou plano sem executar interrupção;
- cenário apontou para `dbops_incident_mariadb` e `incident-mariadb`;
- ausência de volume persistente confirmada no Compose descartável.

Primeira execução real:

- o stack isolado iniciou e `SELECT 1` funcionou;
- a automação falhou ao tentar localizar o container depois do `stop`, porque usava `docker compose ps -q`, que não lista containers parados;
- cleanup foi executado com sucesso;
- essa falha foi registrada em `incident-mariadb-down-20261008T224931Z.json`.

Correção aplicada:

- `service_id()` passou a usar `docker compose ps -a -q`, permitindo inspecionar também containers parados.

Segunda execução real:

- antes: container `running/healthy` e `SELECT 1` aprovado;
- durante: container `exited/unhealthy` após parada controlada;
- depois: container `running/healthy` e `SELECT 1` aprovado;
- cleanup: concluído;
- resultado: `validated: true`.

A evidência completa está em `incident-mariadb-down-20261008T224958Z.json`. O MariaDB principal continuou saudável durante e após o game day.

## Conceitos demonstrados

O cenário separa disponibilidade do serviço de recuperação de dados. A parada controlada testa detecção e retorno do processo, mas não afirma que um volume corrompido pode ser recuperado. O uso de um projeto Compose próprio, sem volume persistente, reduz o blast radius e torna o teste repetível. O estado `healthy` é complementado por uma consulta real para evitar declarar sucesso apenas pelo status do container.

## Limitações e riscos

O incidente foi executado em MariaDB descartável sem volume. Não mede RTO de produção, não testa corrupção de dados e não substitui restore validado. O resultado demonstra o procedimento operacional e a proteção contra atingir o banco principal.

## Pendências e critério de desbloqueio

O Check 6 está completo conforme seu escopo atual. Permanece como melhoria de observabilidade a inclusão de exporter, dashboard e alertas MariaDB no stack Prometheus/Grafana. Essa melhoria deve ser feita antes ou junto do início do SQL Server para manter a visão operacional uniforme.

## Próximo passo recomendado

Iniciar a observabilidade específica do MariaDB — exporter, disponibilidade, conexões, tamanho, queries lentas e idade do backup — e validar uma mudança de métrica durante o game day. Depois disso, iniciar a Fase 7 de SQL Server/Windows.

## Comandos granulares para salvar e commitar manualmente

Não foram executados `git add`, `git commit` ou `git push` pelo agente.

```powershell
git add incidents/docker-compose.mariadb-down.yml incidents/09-mariadb-down.md automation/run_mariadb_down.py tests/test_mariadb_down.py incidents/README.md automation/README.md README.md evidence/phase-6/incident-mariadb-down-20261008T224912Z.json evidence/phase-6/incident-mariadb-down-20261008T224931Z.json evidence/phase-6/incident-mariadb-down-20261008T224958Z.json
git commit -m "feat: add MariaDB outage game day"

git add evidence/phase-6/README.md evidence/phase-6/round-018.md
git commit -m "docs: record MariaDB outage recovery"
```
