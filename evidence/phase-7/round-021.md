# Rodada 021 — restore SQL Server em ambiente separado

## Identificação

- Fase: 7 — SQL Server Developer e Windows
- Data/hora: 2026-10-08 19:58:34 -03:00
- Agente responsável: DBA secundário / QA
- Status: cadeia full + differential + transaction log restaurada e validada

## Objetivo e escopo

Esta rodada provou que os backups produzidos na rodada anterior podem ser aplicados em um banco separado. O restore usou full com `NORECOVERY`, differential com `NORECOVERY`, transaction log com `RECOVERY`, `MOVE` para arquivos distintos, `CHECKSUM`, `DBCC CHECKDB` e leitura de uma tabela de validação.

O banco original `DBOpsLabSqlServer` não foi sobrescrito. O alvo destrutível foi exclusivamente `DBOpsLabSqlServer_Restore`, protegido pela opção `--execute` da CLI.

## Estado observado antes

Os backups full, differential e log estavam validados com `RESTORE VERIFYONLY`, mas ainda não havia restore completo em banco separado. A CLI tinha provisionamento e backup, mas não possuía subcomando `restore`.

## Arquivos criados ou alterados

- `automation/sqlserverops.py`: adicionado `restore` com dry-run padrão, `--execute`, `MOVE`, cadeia de recuperação, `DBCC CHECKDB` e consulta de validação.
- `tests/test_sqlserverops.py`: teste do plano de restore e uso de `NORECOVERY`.
- `sqlserver/README.md`: procedimento reproduzível de restore.
- `README.md`: status SQL Server atualizado.
- `docs/CHECKS.md` e `docs/EVIDENCE_MATRIX.md`: restore separado marcado como validado.
- `evidence/phase-7/sqlserver-restore-20261008T225834Z.json`: resumo estruturado sem credenciais.

## Comandos executados e resultados

```text
python -m py_compile automation/sqlserverops.py
python -m unittest discover -s tests -v
python automation/sqlserverops.py restore --full <full.bak> --differential <differential.bak> --log <log.trn>
python automation/sqlserverops.py restore --full <full.bak> --differential <differential.bak> --log <log.trn> --execute
```

Checks:

- dry-run exibiu o plano e não alterou banco;
- 18 testes automatizados aprovados;
- full restaurado em 0,694 s;
- differential restaurado em 0,447 s;
- transaction log restaurado em 0,155 s;
- banco alvo ficou `ONLINE`;
- `DBCC CHECKDB` não reportou erros;
- `dbo.lab_probe` retornou 1 linha;
- banco original permaneceu separado.

## Conceitos demonstrados

`NORECOVERY` mantém o banco indisponível para receber a próxima etapa da cadeia. O diferencial depende do full e o transaction log fecha a sequência com `RECOVERY`. `MOVE` impede colisão com os arquivos físicos do banco original. `DBCC CHECKDB` valida consistência lógica/física e a consulta final comprova que o schema/dado mínimo está acessível.

## Limitações e pendências

O restore foi executado no SQL Server Express local, não no Developer. Query Store ou análise de waits ainda não foi realizada. Compressão continua limitada pela edição Express e foi documentada na rodada 020. A pasta de dados do serviço não é necessariamente legível pelo usuário interativo, por isso a evidência usa a saída do `sqlcmd` e não leitura direta dos arquivos.

## Próximo passo recomendado

Investigar uma consulta ou espera no SQL Server usando Query Store, se disponível, ou DMVs de waits. Depois registrar diferenças de jobs, permissões, caminhos e observabilidade para concluir a Fase 7.

## Comandos granulares para salvar e commitar manualmente

Não foram executados `git add`, `git commit` ou `git push` pelo agente.

```powershell
git add .env.example README.md automation/sqlserverops.py sqlserver/README.md tests/test_sqlserverops.py
git commit -m "feat: add SQL Server separate restore"

git add evidence/phase-7/README.md evidence/phase-7/sqlserver-restore-20261008T225834Z.json evidence/phase-7/round-021.md
git commit -m "docs: record SQL Server restore validation"
```
