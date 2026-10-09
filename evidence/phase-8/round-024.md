# Round 024 — Manifests stateful e backup separado

## Identificação

- **Fase:** 8 — Kubernetes opcional
- **Data/hora:** 2026-10-09T01:01:30Z
- **Agente responsável:** agente orquestrador/DevOps
- **Projeto:** DB Operations Lab — Resilient Multi-Database Platform

## Objetivo e escopo

Preparar uma execução Kubernetes opcional para PostgreSQL, sem apresentar StatefulSet como alta disponibilidade automática. O escopo incluiu StatefulSet com PVC persistente, política de retenção, ConfigMap, Secret de laboratório, Services, probes e CronJob de backup lógico em PVC separado.

Ficaram fora do escopo: aplicar recursos em cluster, recriar pod, executar restore Kubernetes, configurar replicação/failover e publicar credenciais.

## Estado observado antes da alteração

- kubectl 1.32.3 estava instalado.
- O contexto atual era k3d-meu-cluster.
- kubectl get nodes --request-timeout=5s não recebeu resposta do API Server em https://host.docker.internal:61467.
- kubernetes/ continha apenas .gitkeep.
- O Check 8 estava pendente e a matriz classificava Kubernetes como optional.

## Arquivos criados ou alterados

### kubernetes/postgres-statefulset.yaml

Manifesto multi-documento com:

- Namespace dbops-lab;
- Secret com placeholders, sem credenciais reais;
- ConfigMap com PGDATA e checksums de inicialização;
- Service headless para identidade do StatefulSet;
- Service postgres-client para clientes e backup;
- StatefulSet PostgreSQL 16.4 com uma réplica;
- volumeClaimTemplates para dados;
- persistentVolumeClaimRetentionPolicy Retain;
- startup, readiness e liveness probes usando pg_isready;
- limites e requests de CPU/memória;
- PVC postgres-backups separado do volume de dados;
- CronJob a cada seis horas usando pg_dump no PVC de backup separado.

### kubernetes/README.md

Documentados pré-requisitos, dry-run, aplicação em namespace descartável, consulta de jobs, restore separado e limitações do StatefulSet. O texto explica que o storage de backup é independente do ciclo de vida do pod, mas a execução do backup ainda depende do serviço estar acessível.

### README.md

O status operacional passou a registrar que os manifests Kubernetes existem, mas a validação runtime depende de um cluster acessível.

### docs/CHECKS.md

O Check 8 permaneceu desmarcado. Foi adicionada uma nota explícita separando manifests preparados de execução runtime validada.

### docs/EVIDENCE_MATRIX.md

A linha Kubernetes passou a apontar para o manifesto, o README específico e esta evidência, mantendo status optional e registrando o bloqueio de runtime.

## Comandos executados e resultados

### Verificação de ferramentas

~~~powershell
kubectl version --client=true --output=json
kubectl config current-context
kubectl get nodes --request-timeout=5s
~~~

Resultado: cliente kubectl v1.32.3 e contexto k3d-meu-cluster presentes; consulta ao cluster falhou por timeout no API Server. Nenhum recurso foi aplicado.

### Verificação estrutural do manifesto

Foi conferida a presença de StatefulSet, PVC, ConfigMap, Secret, Service, três probes, CronJob, claim separado para backup e retenção Retain.

Resultado: todos os nove itens passaram.

### Integridade do diff

~~~powershell
git diff --check
~~~

Resultado: código de saída 0. Os avisos exibidos referem-se somente a conversão LF/CRLF de arquivos já modificados.

## Evidências geradas

- kubernetes/postgres-statefulset.yaml
- kubernetes/README.md
- evidence/phase-8/README.md
- evidence/phase-8/round-024.md

## Riscos, limitações e decisões

- O Secret contém apenas placeholder e deve ser substituído fora do Git antes de aplicar.
- O manifesto usa PostgreSQL 16.4 e uma réplica; isso não configura HA.
- O PVC de backup é separado do PVC de dados, mas não é uma estratégia de armazenamento externo ou retenção off-site.
- O CronJob gera backup lógico, não substitui base backup, WAL archiving ou PITR já demonstrados no caminho Docker Compose.
- Não foi declarado sucesso de deployment, probe, recriação ou restore porque o API Server não respondeu.

## Pendências e critério de desbloqueio

- Aplicar o manifesto em um cluster acessível.
- Validar Pending/Running dos PVCs e pod.
- Executar um Job de backup e confirmar o dump no PVC separado.
- Recriar o pod e confirmar persistência dos dados.
- Restaurar o dump em um ambiente separado.
- Atualizar o Check 8 somente após essas evidências runtime existirem.

## Próximo passo recomendado

Primeiro, o usuário deve revisar e commitar as rodadas pendentes. Depois, se quiser concluir Kubernetes, iniciar um cluster local acessível, substituir o Secret por valores locais e executar os testes runtime acima.
