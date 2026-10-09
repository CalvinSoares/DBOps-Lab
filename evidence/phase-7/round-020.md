# Rodada 020 — fundação SQL Server no Windows

## Identificação

- Fase: 7 — SQL Server Developer e Windows
- Data/hora: 2026-10-08 19:56:52 -03:00
- Agente responsável: DBA secundário / DevOps
- Status: ambiente Windows documentado e full/differential/log com CHECKSUM validados; restore separado e Query Store/waits pendentes

## Objetivo e escopo

Esta rodada iniciou a Fase 7 usando a instância SQL Server disponível no Windows. Foram detectados `sqlcmd` e o serviço `MSSQL$SQLEXPRESS`, documentada a diferença entre Express e Developer, criada uma CLI operacional e executados backups full, differential e transaction log com `CHECKSUM` e `RESTORE VERIFYONLY`.

Compressão foi testada explicitamente. Como a edição Express não suporta `BACKUP DATABASE WITH COMPRESSION`, o comando retornou código 3 e a limitação foi registrada. Nenhum sucesso foi declarado para compressão.

Restore em banco separado, `DBCC CHECKDB`, Query Store e waits ficaram fora desta rodada.

## Estado observado antes

A pasta `sqlserver/` continha apenas `.gitkeep`; não havia documentação, configuração, CLI, banco de laboratório ou evidência SQL Server. O host, porém, possuía `sqlcmd` e uma instância `CALVIN-I5\\SQLEXPRESS` em execução.

## Arquivos criados

- `.env.example`: variáveis de instância, banco, caminho de backup e executável `sqlcmd`.
- `automation/sqlserverops.py`: CLI com `environment-check`, `provision` e `backup` para full/differential/log/all, códigos de saída e validação `RESTORE VERIFYONLY`.
- `tests/test_sqlserverops.py`: testes da CLI para quoting de identificadores e tipos de artefato.
- `sqlserver/README.md`: execução Windows, diferenças Express/Developer, tipos de backup e plano de restore.
- `sqlserver/backup/README.md`: política dos artefatos e validação.
- `evidence/phase-7/README.md`: índice da fase.
- `evidence/phase-7/sqlserver-result-20261008T225652Z.json`: resumo estruturado sem caminhos sensíveis ou credenciais.
- `docs/CHECKS.md` e `docs/EVIDENCE_MATRIX.md`: status atualizado somente para o que foi comprovado.

## Comandos executados e resultados

```text
Get-Command sqlcmd
Get-Service MSSQL$SQLEXPRESS
sqlcmd -S .\\SQLEXPRESS -E -C -Q "SELECT SERVERPROPERTY(...)"
python -m py_compile automation/sqlserverops.py
python automation/sqlserverops.py environment-check
python automation/sqlserverops.py provision
python automation/sqlserverops.py backup --type all
python automation/sqlserverops.py backup --type full --compression
```

Ambiente:

- `sqlcmd`: encontrado em `C:\Program Files\Microsoft SQL Server\Client SDK\ODBC\170\Tools\Binn\SQLCMD.EXE`;
- serviço `MSSQL$SQLEXPRESS`: `Running`;
- edição: `Express Edition (64-bit)`;
- versão: `15.0.2000.5`;
- banco: `DBOpsLabSqlServer`;
- tabela sintética: `dbo.lab_probe`.

Backups sem compressão:

- full: 0,547 s, 11,639 MB/s, CHECKSUM e VERIFYONLY aprovados;
- differential: 0,437 s, 4,237 MB/s, CHECKSUM e VERIFYONLY aprovados;
- transaction log: 0,454 s, 1,754 MB/s, CHECKSUM e VERIFYONLY aprovados.

Compressão:

- `backup --type full --compression` retornou código 3;
- SQL Server Express informou que `BACKUP DATABASE WITH COMPRESSION` não é suportado;
- a limitação foi registrada como comportamento da edição, não como falha silenciosa.

Após a implementação dos testes da CLI, a suíte completa passou com 17 testes aprovados.

O resumo está em `sqlserver-result-20261008T225652Z.json`.

## Conceitos demonstrados

O full estabelece a base da cadeia. O differential depende do último full. O transaction log depende do recovery model `FULL` e mantém a cadeia de logs. `CHECKSUM` protege a escrita/leitura do backup, enquanto `RESTORE VERIFYONLY` valida o conjunto sem restaurar os dados. O teste de compressão mostra por que edition/licenciamento precisa ser verificado antes de prometer uma capacidade operacional.

## Limitações, riscos e pendências

- Express não é Developer; a documentação deixa isso explícito.
- Os artefatos ficam no diretório padrão do SQL Server e a conta do serviço precisa ter acesso ao caminho.
- Não foi possível inferir tamanho via PowerShell porque a pasta do serviço negou leitura ao usuário interativo; throughput veio do próprio `sqlcmd`.
- Restore separado ainda não foi executado.
- Query Store ou waits ainda não foram usados.
- SQL Server Agent não está sendo assumido; a estratégia de jobs será documentada conforme a edição disponível.

## Próximo passo recomendado

Executar restore separado com full + differential + log, usar `MOVE` para arquivos descartáveis, validar `DBCC CHECKDB` e registrar o resultado. Depois investigar waits ou Query Store antes de declarar a Fase 7 completa.

## Comandos granulares para salvar e commitar manualmente

Não foram executados `git add`, `git commit` ou `git push` pelo agente.

```powershell
git add .env.example automation/sqlserverops.py sqlserver/README.md sqlserver/backup/README.md
git commit -m "feat: add SQL Server Windows operations CLI"

git add evidence/phase-7/README.md evidence/phase-7/sqlserver-result-20261008T225652Z.json evidence/phase-7/round-020.md
git commit -m "docs: record SQL Server backup validation"
```
