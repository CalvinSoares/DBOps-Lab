# Backups SQL Server

Os arquivos de backup são criados no caminho definido por `SQLSERVER_BACKUP_DIR` e permanecem fora do Git. A CLI registra a saída do `sqlcmd` e executa `RESTORE VERIFYONLY WITH CHECKSUM` imediatamente após cada backup.

O primeiro ciclo validado nesta máquina usou SQL Server Express sem compressão: full, differential e transaction log. A compressão foi testada separadamente e retornou erro explícito da edição, sem ser tratada como sucesso.
