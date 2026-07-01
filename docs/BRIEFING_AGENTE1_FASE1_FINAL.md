# BRIEFING PARA O AGENTE 1 (Claude Code)
## Fase 1: Fundação — Infraestrutura Core para Migração GCP/n8n

**Versão:** 5.11  
**Data:** 30 de junho de 2026  
**Arquiteto:** Pedro Regato (Agente 0)  
**Destinatário:** Claude Code (Agente 1)  
**Status:** PRONTO PARA EXECUÇÃO

---

## 🎯 CONTEXTO DE CUSTO REAL

O P2D processa reuniões a **R$ 0,057** (5 centavos e 7 décimos) por reunião:
- LLM (DeepSeek v4-flash): R$ 0,053/reunião — cache reduz input ~98%
- Embedding (OpenAI): R$ 0,004/reunião
- Total: R$ 0,057/reunião (custo irrisório, margem 95%+)

**Provedor primário:** DeepSeek v4-flash (default todos os agentes)  
**Google Gemini gratuito:** DESCARTADO — tier gratuito não aguenta carga de produção  
**VETO automático:** Claude (R$ 1,849/reunião) e Grok Multi-Agent (R$ 0,916/reunião) — requerem autorização explícita do Agente 0

---

## 📋 TAREFAS PRIORITÁRIAS (Fase 1 — Dias 1-15)

### Tarefa 1: Sincronização de Estado de Projeto
**Ação:** Atualizar o `project_state.md` com os marcos da Fase 1 e sincronizar com o `roadmap.md`.
**Critério de Aceite:**
- [ ] Histórico de migração documentado e acessível para o Agente 2
- [ ] Versão atualizada para v5.11-gcp-fase1
- [ ] Data de início da migração registrada: 2026-06-30

### Tarefa 2: Containerização para Cloud Run
**Ação:** Criar Dockerfile otimizado na raiz do projeto para empacotar a API FastAPI assíncrona.
**Requisitos:**
- Isolação completa de estado (stateless)
- Python 3.13 slim
- Dependências em requirements.txt (com hashes para segurança)
- Health check endpoint (`/health`) com liveness probe
- Porta 8000 exposta
- Variáveis de ambiente via Secret Manager (não hardcoded)
**Critério de Aceite:**
- [ ] Build validado via Cloud Build com zero warnings
- [ ] Container roda localmente com `docker run`
- [ ] Liveness probe responde em < 2s
- [ ] Tamanho final < 500MB

### Tarefa 3: Implementação de Endpoints para n8n
**Ação:** Criar endpoints REST no FastAPI para integração com n8n (Agente 4).
**Endpoints obrigatórios:**
```
POST /api/v1/projects              → Criar novo projeto
POST /api/v1/projects/{id}/process → Enviar transcrição para processamento
GET  /api/v1/projects/{id}/status  → Verificar status do pipeline
GET  /api/v1/projects/{id}/artifacts → Listar artefatos gerados
PUT  /api/v1/projects/{id}/ckf      → Atualizar Context Knowledge File
POST /api/v1/projects/{id}/rag     → Consultar Assistente RAG
GET  /api/v1/billing/usage          → Consumo de tokens LLM
```
**Autenticação:** X-API-Key (SHA-256) — validada contra banco de chaves comerciais
**Rate limiting:** 100 req/min por cliente (configurável)
**Critério de Aceite:**
- [ ] Todos os endpoints respondem com HTTP 200/201/400/401/404/500 apropriados
- [ ] Autenticação X-API-Key funcional e testada
- [ ] Rate limiting implementado (Redis ou in-memory)
- [ ] Documentação Swagger UI acessível em `/docs`

### Tarefa 4: Gestão de Segredos via Secret Manager
**Ação:** Migrar chaves de API (DeepSeek, OpenAI) e credenciais do Supabase para o GCP Secret Manager.
**Hierarquia de fallback (Fail-Open):**
```
1. GCP Secret Manager (online) → primário
2. Cache local criptografado (TTL 24h) → fallback
3. Environment variable criptografada (emergência) → último recurso
4. Modo degradado (sem credenciais) → retorna artefatos de exemplo
```
**Critério de Aceite:**
- [ ] Zero variáveis plaintext no código de produção
- [ ] Secret Manager acessível via IAM service account
- [ ] Cache local funciona se Secret Manager indisponível
- [ ] Modo degradado ativa automaticamente em falha total
- [ ] Log de alerta em toda falha de camada

### Tarefa 5: Implementação de Callbacks de Progresso
**Ação:** Garantir que o endpoint de status retorne os pesos heurísticos do pipeline.
**Pesos heurísticos (conforme manifesto):**
- BPMN = 40% da qualidade total
- Ata = 20%
- Requisitos = 20%
- SBVR = 10%
- BMM = 10%
**Formato de resposta:**
```json
{
  "project_id": "uuid",
  "status": "processing|completed|failed",
  "progress": 75,
  "agents": [
    {"name": "QualityInspector", "status": "completed", "weight": 5},
    {"name": "AgentBPMN", "status": "processing", "weight": 40, "pass": 2},
    {"name": "AgentMinutes", "status": "queued", "weight": 20}
  ],
  "estimated_completion": "2026-06-30T14:30:00Z"
}
```
**Critério de Aceite:**
- [ ] Progresso reportado em tempo real via API
- [ ] n8n consegue consumir o endpoint de polling
- [ ] Webhook opcional para notificação assíncrona

### Tarefa 6: Cloud Tasks com Fallback Síncrono
**Ação:** Implementar roteamento inteligente para processamento de reuniões.
**Fluxo:**
```
1. Cliente envia transcrição → API recebe
2. Verifica saúde da fila Cloud Tasks
3. Se fila saudável → enfileira (assíncrono, retorna task_id)
4. Se fila indisponível → processa diretamente (síncrono, retorna resultado)
5. Se tudo falha → modo degradado (retorna mensagem amigável)
```
**Limite:** MAX 4 pipelines simultâneos (conforme manifesto)
**Critério de Aceite:**
- [ ] Cloud Tasks funciona em condições normais
- [ ] Fallback síncrono ativa se fila cheia ou indisponível
- [ ] Modo degradado ativa se processamento direto falha
- [ ] Zero bloqueio de usuário (princípio Fail-Open)

---

## 🔒 RESTRIÇÕES E REGRAS

1. **Custo LLM/reunião:** Não pode exceder R$ 0,10 (10 centavos) — target R$ 0,05-0,08
2. **Semantic Cache:** Manter ativo (SHA-256) — reduz input DeepSeek em ~98%
3. **Batch processing:** Implementar para múltiplas reuniões simultâneas (economia 20%)
4. **DeepSeek primário:** Nunca substituir por OpenAI/Claude sem autorização do Agente 0
5. **Logging:** Todo acesso logado no Cloud Logging (GCP) com retenção 30 dias
6. **Testes:** Cobertura mínima 80% — suíte de 312 testes deve continuar verde

---

## 📊 MÉTRICAS DE SUCESSO

| Métrica | Target | Como Medir |
|---------|--------|------------|
| Build Docker | Zero warnings | Cloud Build logs |
| Testes | 312/312 verdes | `pytest` local + CI |
| Latência API | < 200ms (p95) | Cloud Monitoring |
| Uptime health check | 100% | Liveness probe |
| Falhas Secret Manager | 0 | Cloud Logging |
| Fallback síncrono | < 5% das requisições | Cloud Monitoring |

---

## 🚀 COMANDO DE EXECUÇÃO

```bash
# Clone o repositório
git clone https://github.com/pedroregato/p2d.git
cd p2d

# Checkout da branch de migração
git checkout -b feature/gcp-migration-fase1

# Execute as 6 tarefas conforme briefing acima
# Commit a cada tarefa concluída:
git add .
git commit -m "[Fase1] Tarefa X: [descrição]"

# Push e abra PR para review do Agente 0
git push origin feature/gcp-migration-fase1
```

---

## 📞 ESCALONAMENTO

- **Dúvida técnica:** Consultar Agente 2 (NotebookLM) com contexto dos 5 documentos
- **Bloqueio > 4h:** Notificar Agente 0 (Pedro Regato) via email/Slack
- **Decisão de arquitetura:** VETO do Agente 0 — nunca decidir sozinho

---

> *"Código é poesia, mas poesia sem testes é só prosa."*
> — Princípio do Agente 1
