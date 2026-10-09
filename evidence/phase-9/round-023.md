# Round 023 — Auditoria final de documentação e portfólio

## Identificação

- **Fase:** 9 — empacotamento e apresentação do portfólio
- **Data/hora de registro:** 2026-10-08T23:01:56Z
- **Agente responsável:** agente orquestrador/documentação
- **Projeto:** DB Operations Lab — Resilient Multi-Database Platform

## Objetivo e escopo

Esta rodada fechou a apresentação pública do laboratório depois das validações de PostgreSQL, MariaDB e SQL Server. O escopo incluiu auditoria dos links principais do README, criação de uma arquitetura visual versionável, atualização do texto para refletir o estado real do projeto, criação de bullets de currículo baseados somente em evidências e atualização da matriz de evidências.

Ficaram fora do escopo: publicação no GitHub, `git add`, commit, push, criação de release, implementação de Kubernetes e criação de novas métricas operacionais.

## Estado observado antes da alteração

- O README tinha um diagrama textual, mas não uma imagem de arquitetura própria.
- O README descrevia MariaDB e SQL Server como extensões planejadas, embora as fases 6 e 7 já tivessem evidências locais validadas.
- A matriz já apontava a performance do SQL Server, mas não tinha uma linha específica para o empacotamento do portfólio.
- Não havia um documento separado com descrição de projeto e bullets de currículo baseados nos resultados medidos.
- `AGENTS.md` e `docs/` permanecem ignorados pelo Git conforme a política local; suas alterações são deliberadamente locais.

## Alterações realizadas

### `architecture/dbops-lab.svg`

Criado um diagrama SVG versionável mostrando a CLI Python, os três bancos, volumes, backups/WAL, Prometheus, Grafana, incidentes e a trilha de evidências. O formato SVG foi escolhido para manter a arquitetura legível no GitHub sem depender de um arquivo binário.

### `architecture/README.md`

Atualizado para incorporar o SVG e descrever o estado atual: PostgreSQL como caminho crítico, MariaDB validado, SQL Server validado no Windows/Express e a limitação de compressão da edição instalada. Também foi mantida a explicação de que Kubernetes não equivale automaticamente a alta disponibilidade.

### `README.md`

Atualizado para:

- apontar a arquitetura visual logo na seção de arquitetura;
- listar evidências de MariaDB e SQL Server;
- refletir que as duas extensões foram validadas com profundidade proporcional;
- incluir as portas dos exporters;
- explicar a execução separada do SQL Server no Windows;
- documentar que `GRAFANA_PORT` pode ser alterada no `.env` quando a porta padrão estiver ocupada;
- preservar a separação entre metas de RPO/RTO e resultados realmente medidos.

Após os checks, o diagrama textual antigo foi removido do README porque mostrava somente PostgreSQL e poderia divergir da arquitetura visual atual. A árvore do repositório também passou a listar a pasta `portfolio/`.

### `portfolio/CURRICULUM.md`

Criado documento de apresentação profissional. Os bullets usam somente resultados encontrados em `benchmarks/` e `evidence/`, incluindo a comparação medida do benchmark MariaDB, o ciclo de backup/restore do SQL Server e a análise de Query Store/waits. O texto explicita que se trata de projeto de laboratório e registra a limitação do SQL Server Express.

### `docs/EVIDENCE_MATRIX.md`

Adicionada a competência de empacotamento de portfólio, vinculando arquitetura, README, currículo e esta rodada a um critério de validade reproduzível. A linha de performance do SQL Server já existente foi preservada como `validated` porque aponta para o artefato da rodada 022.

### `docs/CHECKS.md`

O check final de portfólio permanece marcado como concluído porque a arquitetura visual, as evidências, o roteiro curto e a origem das métricas estão presentes. O check de Kubernetes continua pendente/opcional e não foi mascarado por esta rodada.

## Comandos executados e resultados

### Integridade do diff

```powershell
git diff --check
```

Resultado: aprovado, sem erro de whitespace. O Git exibiu somente avisos de conversão LF/CRLF para arquivos já modificados.

### Testes automatizados

```powershell
python -m unittest discover -s tests -v
```

Resultado: `Ran 19 tests` e `OK`.

### Validação da configuração Compose

```powershell
docker compose --profile monitoring --profile secondary config --quiet
```

Resultado: código de saída `0`, sem diagnóstico de configuração.

### Auditoria de caminhos do pacote

Foi verificada a existência de oito caminhos essenciais: `architecture/dbops-lab.svg`, `README.md`, `architecture/README.md`, `portfolio/CURRICULUM.md`, `docs/CHECKS.md`, `docs/EVIDENCE_MATRIX.md`, `evidence/phase-6/round-019.md` e `evidence/phase-7/round-022.md`.

Resultado: `README/package links: all 8 paths present`.

## Evidências geradas

- `architecture/dbops-lab.svg`
- `portfolio/CURRICULUM.md`
- `evidence/phase-9/README.md`
- `evidence/phase-9/round-023.md`
- `docs/EVIDENCE_MATRIX.md`, mantido localmente conforme o `.gitignore`
- `docs/CHECKS.md`, mantido localmente conforme o `.gitignore`

## Riscos, limitações e decisões

- Os artefatos de evidência anteriores permanecem não versionados até que o usuário revise e faça os commits manualmente.
- O SQL Server validado é Express 2019, não Developer; por isso compressão foi testada e registrada como limitação, não como capacidade disponível.
- O projeto não declara RPO/RTO medidos sem teste correspondente.
- O SVG documenta a arquitetura operacional do laboratório; ele não representa uma topologia de produção nem uma promessa de HA.
- Nenhuma operação Git de escrita foi executada pelo agente.

## Pendências e critério de desbloqueio

- **Kubernetes:** opcional; avançar somente se o usuário quiser ampliar o portfólio depois que os commits das fases atuais estiverem organizados.
- **Publicação no GitHub:** pendente por política; desbloqueada quando o usuário revisar, adicionar, commitar e executar o push manualmente.
- **Métricas de currículo:** não há pendência técnica; qualquer novo número deve primeiro ser produzido em benchmark/evidence.

## Próximo passo recomendado

O próximo passo imediato é o usuário revisar e commitar esta rodada junto dos arquivos funcionais que ainda estiverem pendentes. Depois disso, o projeto está pronto para apresentação como portfólio. Kubernetes pode ser tratado como uma rodada separada, sem alterar o caminho crítico já validado.
