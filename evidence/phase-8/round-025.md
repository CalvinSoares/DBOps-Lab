# Round 025 — Diagnóstico de disponibilidade do cluster Kubernetes

## Identificação

- **Fase:** 8 — Kubernetes opcional
- **Data/hora:** 2026-10-09T01:02:11Z
- **Agente responsável:** agente orquestrador/DevOps
- **Projeto:** DB Operations Lab — Resilient Multi-Database Platform

## Objetivo e escopo

Verificar se existe um API Server Kubernetes acessível para executar a validação runtime dos manifests da rodada 024. O escopo foi somente diagnóstico de contexto, cliente kubectl, Docker e containers. Nenhum recurso Kubernetes foi aplicado, criado ou removido.

## Estado observado

- Docker Engine respondeu com versão 29.1.3 e havia 9 containers em execução.
- kubectl versão 1.32.3 estava instalado.
- O contexto atual era k3d-meu-cluster.
- O contexto rancher-desktop também estava configurado.
- O binário k3d não estava instalado no PATH.

## Comandos executados e resultados

### Contextos configurados

~~~powershell
kubectl config current-context
kubectl config get-contexts
~~~

Resultado: contexto atual k3d-meu-cluster; também existe rancher-desktop.

### Contexto k3d

~~~powershell
kubectl get nodes --request-timeout=5s
~~~

Resultado: falha por timeout ao acessar https://host.docker.internal:61467. O API Server não respondeu.

### Contexto Rancher Desktop

~~~powershell
kubectl --context rancher-desktop get nodes --request-timeout=5s
~~~

Resultado: conexão recusada em 127.0.0.1:6443. O Kubernetes do Rancher Desktop não está ativo ou não está escutando nessa porta.

### Docker e k3d

~~~powershell
docker info --format 'Server={{.ServerVersion}} Containers={{.Containers}} Running={{.ContainersRunning}}'
docker ps -a
Get-Command k3d
~~~

Resultado: Docker está saudável e executando os serviços do DB Operations Lab; k3d não está instalado. Não foi feita instalação nem criação de cluster.

## Evidências geradas

- Este relatório em evidence/phase-8/round-025.md.
- O manifesto continua em kubernetes/postgres-statefulset.yaml.
- A rodada 024 continua sendo a evidência dos recursos Kubernetes preparados.

## Riscos, limitações e decisões

- Criar um cluster pode consumir memória e alterar o ambiente local; por isso não foi feito automaticamente.
- O Docker estar ativo não significa que um API Server Kubernetes esteja ativo.
- Nenhum check runtime foi marcado como concluído.
- O PostgreSQL Docker Compose não foi interrompido nem alterado.

## Pendência e critério de desbloqueio

O usuário precisa ativar Kubernetes no Rancher Desktop ou instalar/iniciar uma distribuição local compatível, confirmar que kubectl get nodes responde e então aplicar os manifests em um namespace descartável.

O desbloqueio ocorre quando este comando retornar pelo menos um nó Ready:

~~~powershell
kubectl get nodes --request-timeout=10s
~~~

## Próximo passo recomendado

Ativar um único cluster local, selecionar o contexto correto e executar primeiro o dry-run. Depois aplicar o manifesto, validar PVC/pod/service, executar o backup, recriar o pod e restaurar o dump em ambiente separado.
