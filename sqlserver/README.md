# SQL Server no Windows

## Ambiente detectado

O host deste laboratório possui `sqlcmd` e uma instância local `.`\\`SQLEXPRESS` ativa. A edição detectada foi `Express Edition (64-bit)`, versão `15.0.2000.5`, SQL Server 2019 RTM. Isso demonstra o caminho operacional Windows, mas não deve ser apresentado como SQL Server Developer.

Para usar Developer em uma VM ou instalação própria, mantenha a mesma CLI e altere `SQLSERVER_INSTANCE`, `SQLSERVER_BACKUP_DIR` e as credenciais conforme o ambiente.

## Configuração

Copie `.env.example` para `.env` e ajuste o diretório para um caminho em que a conta do serviço SQL Server tenha escrita:

```powershell
Copy-Item .env.example .env
```

Não versione `.env`, arquivos `.bak`, `.trn`, `.mdf` ou `.ldf`.

## CLI operacional

```powershell
python automation/sqlserverops.py environment-check
python automation/sqlserverops.py provision
python automation/sqlserverops.py backup --type full
python automation/sqlserverops.py backup --type differential
python automation/sqlserverops.py backup --type log
python automation/sqlserverops.py backup --type all
```

O modo `--compression` solicita compressão explicitamente:

```powershell
python automation/sqlserverops.py backup --type full --compression
```

Na instância Express usada nesta rodada, esse comando retorna código 3 porque compressão de backup não é suportada pela edição. Em Developer, a mesma opção deve ser testada e medida; não se deve inferir suporte apenas pelo nome do comando.

## Tipos de backup

- Full: base para os demais backups e restaurações.
- Differential: alterações desde o último full.
- Transaction log: exige recovery model `FULL` e uma cadeia de log iniciada por full backup.
- `CHECKSUM`: habilitado em cada backup e usado também por `RESTORE VERIFYONLY`.
- Compressão: solicitada somente quando suportada pela edição.

## Restore separado

O restore usa `RESTORE DATABASE` em um nome diferente, com `MOVE` para arquivos `.mdf` e `.ldf` em diretório separado, seguido de `DBCC CHECKDB` e leitura de `dbo.lab_probe`. O banco principal não é sobrescrito durante o teste:

```powershell
python automation/sqlserverops.py restore `
  --full <full.bak> `
  --differential <differential.bak> `
  --log <log.trn>

python automation/sqlserverops.py restore `
  --full <full.bak> `
  --differential <differential.bak> `
  --log <log.trn> `
  --execute
```

Sem `--execute`, a CLI apenas imprime o plano. A execução substitui somente o alvo separado configurado em `--target` (padrão `DBOpsLabSqlServer_Restore`).

## Diferenças Windows/SQL Server

Os caminhos são caminhos Windows e precisam ser acessíveis pela conta do serviço SQL Server, não somente pelo usuário que executa `sqlcmd`. SQL Express não inclui SQL Server Agent e possui limitações de edição; jobs devem ser documentados como Task Scheduler, script externo ou recurso indisponível. Query Store e waits ainda serão investigados em uma rodada posterior.

## Query Store e waits

```powershell
python automation/sqlserverops.py performance-check --repetitions 20
```

O comando habilita Query Store em `READ_WRITE`, executa `SELECT COUNT(*) FROM dbo.lab_probe WHERE id = 1` e coleta duração média, CPU, leituras lógicas, contagem de execuções e waits da instância. A lista de waits exclui tarefas internas conhecidas; os valores continuam cumulativos desde o início da instância e precisam ser correlacionados com carga e intervalo.
