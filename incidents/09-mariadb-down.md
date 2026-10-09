# Incidente 09 — MariaDB indisponível

## Escopo e impacto

O serviço MariaDB secundário não aceita conexões. O impacto esperado é indisponibilidade do banco secundário e das aplicações que dependem dele. O banco PostgreSQL principal não faz parte deste cenário.

## Detecção

1. Confirmar o estado do serviço com `docker compose --profile secondary ps`.
2. Executar `python automation/mysqlops.py health-check` e registrar código de saída.
3. Conferir logs do container e o health check `healthcheck.sh --connect --innodb_initialized`.
4. Separar falha de processo, credenciais, porta, volume e filesystem.

## Contenção

Não remover o volume `mariadb_data` e não executar `docker compose down --volumes` no ambiente principal. Coletar status, logs, espaço em disco e idade do último backup antes de qualquer ação destrutiva.

## Diagnóstico e recuperação

```powershell
docker compose --profile secondary ps
docker compose --profile secondary logs --tail 100 mariadb
python automation/mysqlops.py health-check
docker compose --profile secondary up -d mariadb
python automation/mysqlops.py health-check
```

Se o volume estiver comprometido, preservar o diretório de backup e restaurar em uma instância separada usando `python automation/mysqlops.py restore <arquivo.sql.gz>`. A recuperação do volume principal deve ser feita somente em janela autorizada.

## Game day isolado

```powershell
python automation/run_mariadb_down.py
python automation/run_mariadb_down.py --execute
```

O executor usa o projeto Compose `dbops_incident_mariadb`, um container MariaDB sem volume persistente e sem conexão com o serviço principal. Ele valida disponibilidade, para somente o container descartável, confirma a indisponibilidade, inicia o serviço novamente, testa `SELECT 1` e remove apenas os recursos do projeto isolado.

## Validação e lições

O incidente só é considerado validado quando os estados antes/durante/depois estiverem registrados, o retorno de `SELECT 1` for bem-sucedido e o cleanup do projeto isolado terminar sem erro. Este game day prova detecção, contenção e retorno de disponibilidade; não prova recuperação de um volume de produção.
