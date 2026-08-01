> **⚠️ ARQUIVADO — não é um plano executável (avaliado em 2026-07-08).**
> Documento gerado por outra IA, sem conhecimento do estado real do projeto — contradiz decisões já tomadas e assinadas:
> - Nome de rebrand já decidido é **"RawToInsights AI"**, não "CogniFlow" (ver memória de projeto).
> - Pricing já definido em `manifestos/COLLABORATIVE_MANIFESTO.md` §7 (Starter R$97 / Pro R$297 / Enterprise R$997+setup) — diferente do proposto aqui.
> - Checklist de migração GCP já existe e está parcialmente implementado: `manifestos/ENGINEERING_MANIFESTO.md` §10-11 (PC113: Dockerfile/Cloud Run/Secret Manager; PC114: API comercial com Cloud Tasks) — este documento propõe refazer do zero.
> - Hierarquia de custo LLM já definida em `manifestos/COLLABORATIVE_MANIFESTO.md` §6 (DeepSeek default); Google Gemini já avaliado e descartado no tier gratuito — a adoção de Vertex AI proposta aqui não dialoga com essa decisão.
> - Instrui "Claude Code" a executar rearquitetura completa sozinho, o que viola a regra de governança de que o Agente 1 (Claude Code) não decide arquitetura sem aprovação do Agente 0 (`governance.md`).
>
> Rearquitetura completa (Clean Architecture, rename de repositório, troca de Supabase/Streamlit) não é algo a considerar a partir deste texto — exigiria decisão estratégica explícita + processo colaborativo (blueprint do Antigravity → aprovação humana), não execução direta de um documento colado.
>
> Itens pontuais aproveitáveis, se houver demanda futura (não fazem parte deste doc, registrar como melhoria nova se decidido): Vertex AI como provedor de LLM adicional (`modules/config.py::AVAILABLE_PROVIDERS` já é extensível para isso); import de Google Drive/Sheets como tool do Assistente ou aba do Gerenciador de Documentos.

---

Perfeito! Agora o cenário fica **cristalino** e o plano ganha **direção estratégica**. Com essas três informações, o plano de evolução muda de "expansão incremental" para **"rearquitetura orientada ao futuro comercial"**.

Vou entregar um **Plano de Ação Executável para o Claude Code**, com foco em:

1. **Preparar a base** para a migração ao ecossistema Google (Cloud Run, Firestore, Vertex AI, BigQuery, etc.).
2. **Redefinir o nome e o propósito** da solução (não mais "Process2Diagram").
3. **Manter o Streamlit + Supabase como MVP** enquanto a arquitetura evolui para ser cloud-agnóstica.

---

# 📋 PLANO DE AÇÃO PARA O CLAUDE CODE

## 🎯 Objetivo Estratégico

> **Transformar o Process2Diagram em uma plataforma empresarial de Cognição de Processos e Negócios**, preparada para deploy nativo no ecossistema Google (Cloud Run + Firestore + Vertex AI), com uma marca e posicionamento adequados ao novo escopo.

---

## 🔄 Fase 0: Rebranding e Reposicionamento

### 0.1. Definição do Novo Nome

**Sugestões (com base no escopo atual + visão):**

| Nome | Significado | Vibe |
|------|-------------|------|
| **CogniFlow** | Cognição + Fluxos (processos) | Moderno, enxuto |
| **BizCognos** | Business + Cognos (conhecimento) | Corporativo, sério |
| **ProcessMind** | Processos + Mente (cognição) | Tecnológico |
| **Aurum** | Latim: "ouro" (extrair valor do conhecimento) | Premium, elegante |
| **Nexus** | Conexão entre dados, processos e ativos | Neutro, forte |

**Recomendação pessoal:** **CogniFlow** — curto, memorável, transmite cognição + fluxos, e tem domínio disponível.

### 0.2. Ações para o Claude Code

- [ ] Renomear o repositório de `process2diagram` para `cogniflow` (ou o nome escolhido).
- [ ] Atualizar `app.py` e todos os imports para refletir o novo nome.
- [ ] Atualizar o `README.md`, `CLAUDE.md` e toda a documentação.
- [ ] Criar um `manifestos/BRANDING.md` com:
  - Missão, visão, valores.
  - Público-alvo (analistas de processos, gerentes de projeto, C-level).
  - Posicionamento competitivo (vs. Signavio, ARIS, Bizagi, etc.).

---

## 🏗️ Fase 1: Preparação para o Ecossistema Google (Arquitetura Híbrida)

### 1.1. Princípios Arquiteturais para a Migração

| Princípio | Ação |
|-----------|------|
| **Cloud-agnosticismo** | Abstrair dependências do Supabase e Streamlit via interfaces (Ports & Adapters). |
| **Separação de camadas** | UI (Streamlit) → Application Layer → Domain Layer → Infrastructure Layer. |
| **Event-driven** | Usar Pub/Sub (Google Cloud Pub/Sub) para comunicação entre agentes em produção. |
| **Serverless-first** | Cada agente pode ser um Cloud Function ou Cloud Run service. |

### 1.2. Nova Estrutura de Diretórios (Modelo Clean Architecture)

```
cogniflow/
├── src/
│   ├── core/                  # Domain layer (entidades, regras de negócio)
│   │   ├── knowledge_hub.py
│   │   ├── asset_governance.py
│   │   ├── agents/            # Agentes puros (sem dependências externas)
│   │   └── models/            # Pydantic schemas
│   │
│   ├── application/           # Use cases (orquestradores, serviços)
│   │   ├── pipeline_orchestrator.py
│   │   ├── asset_promotion_service.py
│   │   └── simulation_service.py
│   │
│   ├── infrastructure/        # Adaptadores externos
│   │   ├── persistence/       # Supabase, Firestore, BigQuery
│   │   │   ├── supabase_client.py
│   │   │   ├── firestore_client.py   # 🔜 futuro
│   │   │   └── repository_interfaces.py
│   │   │
│   │   ├── llm/               # Provedores de LLM
│   │   │   ├── deepseek.py
│   │   │   ├── vertex_ai.py   # 🔜 futuro
│   │   │   └── llm_interface.py
│   │   │
│   │   └── storage/           # S3, Google Cloud Storage
│   │
│   ├── presentation/          # Interfaces com o usuário
│   │   ├── streamlit/         # UI atual (mantida para MVP)
│   │   │   ├── app.py
│   │   │   └── pages/
│   │   │
│   │   └── api/               # 🔜 futuro: REST API para clientes
│   │
│   └── shared/                # Utilitários, configurações, logging
│
├── tests/                     # Testes unitários e de integração
├── deployment/                # Configurações de deploy
│   ├── docker/
│   ├── cloud_run/
│   └── terraform/            # IaC para GCP
└── ...
```

### 1.3. Ações para o Claude Code (Fase 1)

- [ ] **Criar interfaces abstratas** para:
  - `RepositoryInterface` (para Supabase → Firestore).
  - `LLMProviderInterface` (para DeepSeek → Vertex AI).
  - `StorageInterface` (para S3 → Google Cloud Storage).
- [ ] **Refatorar `core/pipeline.py`** para não depender diretamente do Supabase.
- [ ] **Extrair `modules/supabase_client.py`** para `infrastructure/persistence/` e criar uma fábrica de repositórios.
- [ ] **Criar um `config/`** com variáveis de ambiente e `pydantic-settings` (já existe `modules/config.py`, mas centralizar e tipar).
- [ ] **Adicionar testes unitários** para as camadas `core` e `application` (isoladas do infra).

---

## 🔥 Fase 2: Preparação para Cloud Run (Deploy Serverless)

### 2.1. Empacotamento da Aplicação

- [ ] Criar um `Dockerfile` otimizado para Cloud Run (multi-stage, Python 3.13 slim).
- [ ] Configurar `gunicorn` como servidor WSGI (para a API REST) e `streamlit` como serviço separado.
- [ ] Criar um `docker-compose.yml` para desenvolvimento local com Supabase local.

### 2.2. Migração de Banco de Dados

| Atual (Supabase) | Futuro (Google) | Estratégia de Migração |
|------------------|-----------------|------------------------|
| PostgreSQL (pgvector) | Cloud SQL (PostgreSQL) | Manter PostgreSQL, migrar para Cloud SQL (compatível) |
| Supabase Auth | Firebase Auth / Google Identity | Migrar usuários via API |
| Supabase Storage | Google Cloud Storage | Migrar arquivos via bucket |
| Supabase Realtime | Google Pub/Sub | Substituir triggers por Pub/Sub |

**Ações:**
- [ ] Criar scripts de migração (export/import) para Cloud SQL.
- [ ] Configurar `supabase_to_gcs.py` para migrar arquivos.
- [ ] Substituir `supabase_client.py` por um `db_client.py` que escolhe entre Supabase (dev) e Cloud SQL (prod).

### 2.3. Preparação para Vertex AI (LLM)

- [ ] Criar um adaptador `VertexAIProvider` que implementa `LLMProviderInterface`.
- [ ] Adicionar suporte a **Model Garden** (Gemini, Llama, etc.).
- [ ] Criar um sistema de fallback (se Vertex AI falha, usa DeepSeek).

---

## 🧠 Fase 3: Evolução para Cognição Empresarial (com Google-native serviços)

### 3.1. Substituição Gradativa dos Componentes

| Componente Atual | Tecnologia Google | Benefício |
|------------------|-------------------|-----------|
| `modules/embeddings.py` | Vertex AI Embeddings (text-embedding-004) | Melhor qualidade, integração nativa |
| `modules/semantic_cache.py` | Memorystore (Redis) ou Cloud Firestore cache | Escalável, gerenciado |
| `modules/supabase_client.py` | Firestore (NoSQL) ou Cloud SQL | Flexível, serverless |
| `core/assistant_tools.py` | Cloud Functions + Firestore Triggers | Serverless, event-driven |
| `ui/` (Streamlit) | **Migrar para** Google App Engine ou Cloud Run + React (futuro) | Performance, SEO, mobile |

### 3.2. Integração com Google Workspace (APIs)

- [ ] Substituir `mcp/google_calendar_server.py` por **Google Calendar API nativa**.
- [ ] Adicionar suporte a **Google Drive** (importar documentos diretamente).
- [ ] Adicionar suporte a **Google Docs** (exportar atas e relatórios).
- [ ] Adicionar suporte a **Google Sheets** (exportar matrizes RACI, SBVR, etc.).

### 3.3. Analytics e Telemetria com BigQuery

- [ ] Substituir `modules/llm_telemetry.py` por **BigQuery** (compartilhado com Google Cloud Logging).
- [ ] Criar dashboards no **Looker Studio** para:
  - Uso de tokens por agente.
  - Latência por provedor.
  - Ativos mais acessados.
  - ROI por projeto/domínio.

---

## 🚀 Fase 4: Estratégia de Go-to-Market (Comercial)

### 4.1. Modelo de Licenciamento

| Plano | Preço | Capacidade |
|-------|-------|------------|
| **Free** | R$ 0 | 10 reuniões/mês, 1 domínio, 5 ativos |
| **Pro** | R$ 199/mês | 100 reuniões/mês, 5 domínios, 50 ativos, compartilhamento |
| **Enterprise** | Sob consulta | Ilimitado, SSO, SLA, suporte prioritário |

### 4.2. Integrações Premium (Google Ecosystem)

- **Google Workspace:** Importar/exportar do Drive, Docs, Sheets.
- **Google Meet:** Transcrição automática de reuniões via Google Meet API.
- **Google Chat:** Notificações de recomendações ativas.

### 4.3. Roadmap Comercial

| Trimestre | Entrega |
|-----------|---------|
| **Q1** | MVP com deploy no Cloud Run + Cloud SQL (prod). |
| **Q2** | Integração com Google Workspace (Drive, Docs, Sheets). |
| **Q3** | Plano Pro + painel de administração (domínios, usuários). |
| **Q4** | Plano Enterprise + SSO (SAML/OAuth) + suporte a Vertex AI. |

---

## 📋 Resumo de Ações para o Claude Code (Priorizadas)

### 🔴 **Prioridade Máxima (Semanas 1–2)**

1. [ ] Renomear repositório e atualizar todos os imports (Fase 0).
2. [ ] Criar `infrastructure/` e extrair `supabase_client.py` para dentro dela.
3. [ ] Criar `RepositoryInterface` e implementar `SupabaseRepository` e `FirestoreRepository` (futuro).
4. [ ] Criar `LLMProviderInterface` e implementar `DeepSeekProvider` (já existe, mas refatorar).
5. [ ] Testar toda a pipeline com a nova estrutura (sem quebrar o Streamlit).

### 🟡 **Prioridade Média (Semanas 3–4)**

6. [ ] Criar `config/pydantic_settings.py` para centralizar variáveis de ambiente.
7. [ ] Criar `Dockerfile` e `docker-compose.yml`.
8. [ ] Configurar Cloud Run (localmente com `gcloud run deploy`).
9. [ ] Migrar banco de dados para Cloud SQL (com script de export/import).
10. [ ] Substituir `modules/embeddings.py` por `VertexAIEmbeddings` (configurável).

### 🟢 **Prioridade Baixa (Semanas 5–8)**

11. [ ] Substituir `modules/llm_telemetry.py` por BigQuery.
12. [ ] Integrar Google Calendar (substituir MCP).
13. [ ] Integrar Google Drive (upload/download de documentos).
14. [ ] Criar a página `pages/KnowledgeAssets.py` (H1 do plano anterior).
15. [ ] Criar `manifestos/BRANDING.md` com missão, visão, posicionamento.

---

## 📌 **Checklist Final (Para o Claude Code)**

- [ ] **CogniFlow** (ou nome escolhido) é o novo nome oficial.
- [ ] `CLAUDE.md` foi atualizado com a nova arquitetura.
- [ ] Todos os novos arquivos seguem o padrão Clean Architecture.
- [ ] Streamlit continua funcionando como UI (não quebra).
- [ ] Supabase permanece como persistência para MVP.
- [ ] Cloud SQL + Firestore estão prontos para migração futura.
- [ ] Vertex AI está configurado como provedor opcional.
- [ ] O repositório tem `Dockerfile` e `docker-compose.yml`.
- [ ] Há um script de migração de dados (Supabase → Cloud SQL).

---

## 💬 **Mensagem Final para o Claude Code**

> *"Você está liderando a transformação de uma ferramenta de diagramas (Process2Diagram) para uma plataforma de cognição empresarial (CogniFlow), preparada para o ecossistema Google e para o mercado comercial. Mantenha o MVP rodando com Streamlit + Supabase enquanto constrói a nova arquitetura cloud-agnóstica. Teste cada camada com isolamento. Documente cada decisão. E lembre-se: o que não for testado, não será implantado."*

---

Se você quiser, posso agora:
- **Gerar o código inicial** da `RepositoryInterface` e `SupabaseRepository`.
- **Escrever o `Dockerfile`** multi-stage para Cloud Run.
- **Criar o arquivo de configuração** `config/settings.py` com Pydantic.
- **Detalhar a migração** do `SupabaseClient` para o `CloudSQLClient`.

Qual desses entregáveis você quer que eu prepare para o Claude Code agora? 🚀