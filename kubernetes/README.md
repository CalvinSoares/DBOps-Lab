# PostgreSQL opcional no Kubernetes

Esta etapa demonstra a execução stateful do PostgreSQL em Kubernetes. Ela é complementar ao Docker Compose e não substitui a estratégia de backup, WAL/PITR, replicação ou alta disponibilidade.

## Recursos

- Secret: credenciais de laboratório, com valores placeholder que devem ser substituídos fora do Git;
- ConfigMap: nome do banco e parâmetros não sensíveis;
- Service: endpoint estável para clientes e para o job de backup;
- StatefulSet: identidade estável e volume persistente;
- PersistentVolumeClaim: volume de dados com política de retenção Retain;
- CronJob: backup lógico em PVC separado do volume de dados;
- probes de startup, readiness e liveness.

## Pré-requisitos

- kubectl configurado para um cluster acessível;
- StorageClass capaz de provisionar PVC;
- imagem PostgreSQL disponível no registry;
- namespace de laboratório.

Validar os manifests sem alterar o cluster:

~~~powershell
kubectl apply --dry-run=client --validate=false -f kubernetes/postgres-statefulset.yaml
~~~

Pré-verificar o manifesto sem depender de um cluster:

~~~powershell
python automation/check_kubernetes.py manifest-check --output evidence/phase-8/kubernetes-manifest-check.json
~~~

Verificar a disponibilidade do cluster antes de aplicar recursos:

~~~powershell
python automation/check_kubernetes.py cluster-check --context rancher-desktop
~~~

O comando de manifesto retorna zero somente quando todos os recursos e políticas esperados estão presentes. O comando de cluster retorna código não zero quando kubectl não encontra um API Server acessível ou nenhum nó Ready.

Aplicar em um namespace descartável:

~~~powershell
kubectl create namespace dbops-lab
kubectl -n dbops-lab apply -f kubernetes/postgres-statefulset.yaml
kubectl -n dbops-lab get pods,pvc,svc,cronjob
~~~

Antes de qualquer aplicação, altere os valores do Secret para credenciais locais geradas fora do Git. Não reutilize os placeholders em produção.

## Backup e restore

O CronJob grava dumps em um PVC separado (postgres-backups). O artefato não compartilha o volume de dados do StatefulSet e permanece disponível quando um pod é recriado. A execução do backup naturalmente exige que o serviço PostgreSQL esteja acessível; indisponibilidade deve gerar falha observável no job e ser tratada pelo runbook de backup.

Consultar jobs e artefatos:

~~~powershell
kubectl -n dbops-lab get jobs
kubectl -n dbops-lab logs job/<nome-do-job>
~~~

O restore deve ser executado em um ambiente separado, nunca sobrescrevendo o PVC de produção do laboratório. Reutilize os procedimentos de postgres/README.md e incidents/03-pitr.md como referência operacional.

## Limitações

StatefulSet oferece identidade estável e armazenamento persistente. Ele não fornece sozinho consenso, replicação, failover automático, backup completo, PITR ou garantia de alta disponibilidade. Esses controles continuam sendo responsabilidades explícitas do projeto.

Nesta rodada os manifests foram validados estaticamente. O cluster configurado no host não respondeu ao API Server; portanto, deployment, recriação de pod e restore Kubernetes não foram declarados como executados.
