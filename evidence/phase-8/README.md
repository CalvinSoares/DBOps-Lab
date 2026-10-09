# Evidências da Fase 8 — Kubernetes opcional

Esta pasta registra a preparação dos manifests Kubernetes para PostgreSQL. A fase permanece opcional e não bloqueia o núcleo validado do portfólio.

## Rodada registrada

- [Round 024 — manifests stateful e backup separado](round-024.md)
- [Round 025 — diagnóstico de disponibilidade do cluster](round-025.md)
- [Round 026 — pré-verificação automatizada dos manifests](round-026.md)

## Estado

Os recursos StatefulSet, PVC, ConfigMap, Secret, Services, probes e CronJob de backup foram preparados. A validação runtime está pendente porque o contexto kubectl local não conseguiu acessar o API Server.
