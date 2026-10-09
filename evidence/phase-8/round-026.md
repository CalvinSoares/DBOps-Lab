# Round 026 — Pré-verificação automatizada dos manifests Kubernetes

## Identificação

- **Fase:** 8 — Kubernetes opcional
- **Data/hora:** 2026-10-09T01:05:48Z
- **Agente responsável:** agente orquestrador/DevOps
- **Projeto:** DB Operations Lab — Resilient Multi-Database Platform

## Objetivo e escopo

Criar uma verificação reproduzível que possa ser executada antes de aplicar os manifests Kubernetes. A verificação separa a integridade local do manifesto da disponibilidade do cluster e retorna códigos de saída diferentes para erro de manifesto e indisponibilidade do API Server.

Ficaram fora do escopo: aplicação de recursos, alteração de cluster, criação de Secret real, recriação de pod e restore.

## Estado observado antes da alteração

- O manifesto da rodada 024 existia e já havia sido revisado por verificações textuais manuais.
- O API Server dos contextos locais continuava indisponível.
- Não havia CLI dedicada para repetir os checks sem inspeção manual.

## Alterações realizadas

### automation/check_kubernetes.py

Criada CLI com dois comandos:

- manifest-check: valida StatefulSet, PVC, ConfigMap, Secret, Service, probes, CronJob, claim separado, política Retain e Secret placeholder;
- cluster-check: executa kubectl get nodes -o json, conta nós Ready e retorna código não zero em timeout, erro do kubectl, JSON inválido ou ausência de nó Ready.

Ambos os comandos produzem JSON com timestamp UTC, duração, status e detalhes suficientes para diagnóstico. O modo cluster não imprime credenciais nem dados do cluster além da contagem de nós.

### tests/test_kubernetes.py

Adicionados testes para manifesto válido, manifesto incompleto, cluster com nó Ready e API Server indisponível.

### kubernetes/README.md

Adicionados comandos de pré-verificação local e checagem de cluster, incluindo a semântica dos códigos de saída.

## Comandos executados e resultados

~~~powershell
python automation/check_kubernetes.py manifest-check --output evidence/phase-8/kubernetes-manifest-check.json
~~~

Resultado: código de saída 0; todos os checks locais passaram. O JSON foi salvo no caminho indicado.

~~~powershell
python automation/check_kubernetes.py cluster-check --context k3d-meu-cluster
~~~

Resultado esperado e observado: código de saída 3 porque o API Server não respondeu dentro do timeout. A falha foi tratada como indisponibilidade, não como sucesso.

~~~powershell
python -m unittest discover -s tests -v
~~~

Resultado: todos os testes passaram, incluindo os quatro testes de Kubernetes.

~~~powershell
git diff --check
~~~

Resultado: aprovado. Os avisos de LF/CRLF referem-se somente a arquivos já modificados.

## Evidências geradas

- automation/check_kubernetes.py
- tests/test_kubernetes.py
- evidence/phase-8/kubernetes-manifest-check.json
- evidence/phase-8/round-026.md

## Riscos, limitações e decisões

- A validação local verifica contratos essenciais, mas não substitui validação pelo API Server.
- O script não interpreta YAML genericamente; ele valida os marcadores operacionais exigidos pelo manifesto deste laboratório.
- O Check 8 continua pendente porque deployment, persistência, recriação e restore não foram executados.
- Nenhuma operação Git de escrita foi executada pelo agente.

## Próximo passo recomendado

Quando o cluster estiver acessível, executar cluster-check, substituir o Secret placeholder fora do Git, aplicar o manifesto e coletar evidências runtime. Até lá, o projeto possui um preflight reproduzível e o Kubernetes continua opcional.
