# SPEC: Cache Semântico para process2diagram (p2d)

**Status:** AVALIADA — implementação parcial em 2026-07-15, arquivada
**Autor:** Pedro (spec gerada com apoio de Claude)
**Data:** 2026-07-15
**Escopo:** Camada de roteamento/classificação de agentes + camada de geração de artefatos (BPMN, atas, relatórios)

---

## Nota de fechamento (2026-07-15)

Avaliação contra o código real revelou:

1. **O p2d já tem um cache rodando exatamente onde esta spec propõe** — `services/semantic_cache.py` (tabela `llm_cache`), plugado em `agents/base_agent.py::_call_llm()`. Já é global (todos os agentes, não só BPMN/ata), já é PII-safe (cacheia o output cru pré-desanitização), já tem stats/admin tool (`get_cache_stats`, `clear_llm_cache`). Só que é por hash exato (SHA256), não por similaridade de embedding.
2. **Seção 5.1 (cache de roteamento) não tem onde plugar** — pressupõe um classificador de trechos de transcrição dentro do Orchestrator que não existe; o pipeline roda agentes completos (BPMN/Minutes/Requirements/SBVR/BMM/Synthesizer) sobre a transcrição inteira, não faz triagem por trecho.
3. **`group_id`/tabela `groups`** não existem no p2d — o isolamento real é `project_id`/`tenant_id`. A spec foi escrita sem checar o schema atual (mesmo padrão de erro já visto em outras propostas externas avaliadas neste projeto — ver `changelog.md`).
4. A única lacuna real identificada (motivação nº1: "revisão marginal" da mesma transcrição gera cache miss porque o hash é exato) foi **implementada de forma barata e segura**: `SemanticCache.compute_hash()` agora normaliza espaços em branco (colapsa runs de whitespace, strip) antes de hashear — pega diferenças de formatação sem tocar em pontuação/conteúdo, sem custo de embedding, sem risco de falso positivo.
5. **A camada de embedding completa (seções 3, 4, 5.2) foi avaliada e descartada por ora**: exigiria pagar 1 chamada de embedding em TODA chamada de LLM (hit ou miss), e para geração de artefato (BPMN/ata) um falso positivo por similaridade entregaria o artefato de uma transcrição errada — risco real sem ganho demonstrado (nenhum relato de "reprocessar quase-idêntico" como problema de produção). Pode ser revisitada se esse padrão de uso aparecer de fato.

Decisão tomada com o usuário via `AskUserQuestion` — escolheu a opção "normalização barata no cache existente" entre as alternativas apresentadas (scaffold completo desligado / arquivar sem código / normalização). Mudança em `services/semantic_cache.py`, sem migração nova, sem mudança de comportamento fora do hashing.

---

## 1. Motivação

O p2d hoje reprocessa do zero cada chamada de agente, mesmo quando:

- A mesma transcrição (ou uma revisão marginal dela) é reenviada para reprocessamento.
- Múltiplas reuniões do mesmo grupo geram trechos de transcrição estruturalmente idênticos (ex.: abertura de reunião, itens de pauta recorrentes, "próximos passos" repetidos semana a semana).
- Sub-tarefas de classificação/roteamento (ex.: "este trecho é uma decisão, uma ação ou uma observação?") se repetem com alta frequência entre sessões e grupos.

Cada uma dessas chamadas paga o custo total de latência e tokens do provider (DeepSeek/Anthropic/OpenAI/Groq/Gemini/Grok), mesmo quando a resposta correta já existe em cache semântico.

Referência conceitual: padrão de cache semântico com Redis Enterprise descrito em [iMasters, 10/07/2026](https://imasters.com.br/banco-de-dados/arquitetura-cognitiva-de-baixa-latencia-padrao-rag-com-cache). Esta spec adapta o padrão para a stack real do p2d: **Supabase + pgvector**, sem Azure/Redis Enterprise.

---

## 2. Duas camadas de cache, dois regimes de risco

O artigo original trata cache semântico como uma coisa só. Para o p2d, isso é perigoso: falso positivo em roteamento é barato (no pior caso, reclassifica), mas falso positivo em geração de artefato **entrega um BPMN ou uma ata errada ao usuário**. Portanto a spec define dois módulos com políticas distintas.

| | Cache de Roteamento/Classificação | Cache de Geração de Artefato |
|---|---|---|
| Uso | Intent classification, decisão de qual agente/skill acionar, triagem de trechos de transcrição | BPMN, minuta de ata, requisitos, BMM/SBVR, relatório executivo |
| Threshold de similaridade | 0.92 | 0.985 |
| Escopo de busca | Global por tipo de tarefa | Estritamente por `group_id` (nunca cross-tenant) |
| TTL | 7 dias | 30 dias, com invalidação manual |
| Efeito de falso positivo | Reclassificação incorreta, corrigível no próprio pipeline | Artefato de negócio incorreto entregue ao usuário |
| Aprovação humana no miss | Não | Mantém o fluxo atual (tournament de validação BPMN, revisão humana) |

---

## 3. Schema Supabase (pgvector)

```sql
-- Extensão necessária (uma vez por projeto Supabase)
create extension if not exists vector;

-- Tabela única com discriminador de camada, isolada por group_id
create table if not exists semantic_cache (
    id                uuid primary key default gen_random_uuid(),
    cache_layer        text not null check (cache_layer in ('routing', 'artifact')),
    group_id          uuid not null references groups(id),
    task_type         text not null,        -- ex: 'intent_classification', 'bpmn_generation', 'ata_geracao'
    input_text        text not null,        -- texto original (para debug/auditoria)
    input_embedding   vector(1536) not null,
    cached_response   jsonb not null,       -- payload completo da resposta do agente
    source_agent      text not null,        -- qual agente gerou a resposta original
    hit_count         integer not null default 0,
    created_at        timestamptz not null default now(),
    last_hit_at       timestamptz,
    expires_at        timestamptz not null
);

-- Índice HNSW para busca aproximada de vizinhos mais próximos
create index if not exists idx_semantic_cache_embedding
    on semantic_cache using hnsw (input_embedding vector_cosine_ops);

-- Índice composto para restringir busca por grupo + camada + tipo de tarefa antes do KNN
create index if not exists idx_semantic_cache_scope
    on semantic_cache (group_id, cache_layer, task_type, expires_at);
```

**Nota de isolamento:** seguindo o padrão já estabelecido no p2d de UPDATEs isolados por grupo no Supabase, toda consulta ao cache **deve** filtrar por `group_id` antes de calcular a distância vetorial. Nunca fazer KNN global sem esse filtro — isso vazaria conteúdo de um grupo para outro.

---

## 4. Módulo `SemanticCacheAdapter`

Novo arquivo: `core/semantic_cache.py` (nome sujeito ao layout real do repositório — ajustar ao `sys.path.insert` já usado nas páginas Streamlit).

```python
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from supabase import Client


@dataclass
class CacheConfig:
    layer: str                # 'routing' ou 'artifact'
    similarity_threshold: float
    ttl_days: int


CACHE_CONFIGS = {
    "routing": CacheConfig(layer="routing", similarity_threshold=0.92, ttl_days=7),
    "artifact": CacheConfig(layer="artifact", similarity_threshold=0.985, ttl_days=30),
}


class SemanticCacheAdapter:
    """
    Cache semântico sobre pgvector/Supabase.
    Nunca instanciar diretamente fora do Orchestrator — seguir o mesmo
    padrão de acesso controlado usado para os agentes do p2d.
    """

    def __init__(self, supabase_client: Client, embedding_fn):
        self.db = supabase_client
        # embedding_fn: callable(text: str) -> list[float], injeta o provider
        # de embeddings escolhido (ver seção 6 sobre qual provider usar).
        self.embed = embedding_fn

    def check_cache(
        self,
        *,
        group_id: str,
        task_type: str,
        input_text: str,
        layer: str,
    ) -> Optional[dict[str, Any]]:
        config = CACHE_CONFIGS[layer]
        query_vector = self.embed(input_text)

        # RPC no Supabase (função SQL abaixo) já filtra por group_id/layer/task_type
        # e por expires_at > now(), retornando o vizinho mais próximo com score.
        result = self.db.rpc(
            "match_semantic_cache",
            {
                "p_group_id": group_id,
                "p_layer": layer,
                "p_task_type": task_type,
                "p_query_embedding": query_vector,
                "p_match_count": 1,
            },
        ).execute()

        if not result.data:
            return None

        top = result.data[0]
        similarity = top["similarity"]  # 1 - cosine_distance, calculado na função SQL

        if similarity >= config.similarity_threshold:
            self._register_hit(top["id"])
            return {
                "cached_response": top["cached_response"],
                "similarity": similarity,
                "source_agent": top["source_agent"],
                "cache_hit": True,
            }
        return None

    def save_to_cache(
        self,
        *,
        group_id: str,
        task_type: str,
        input_text: str,
        response_payload: dict[str, Any],
        source_agent: str,
        layer: str,
    ) -> None:
        config = CACHE_CONFIGS[layer]
        query_vector = self.embed(input_text)
        expires_at = datetime.now(timezone.utc) + timedelta(days=config.ttl_days)

        self.db.table("semantic_cache").insert({
            "cache_layer": layer,
            "group_id": group_id,
            "task_type": task_type,
            "input_text": input_text,
            "input_embedding": query_vector,
            "cached_response": response_payload,
            "source_agent": source_agent,
            "expires_at": expires_at.isoformat(),
        }).execute()

    def _register_hit(self, cache_id: str) -> None:
        self.db.rpc("increment_cache_hit", {"p_cache_id": cache_id}).execute()

    def invalidate_group(self, group_id: str, layer: Optional[str] = None) -> None:
        """Invalidação manual — usar quando o usuário reporta artefato incorreto
        ou quando a lógica de um agente muda de versão."""
        query = self.db.table("semantic_cache").delete().eq("group_id", group_id)
        if layer:
            query = query.eq("cache_layer", layer)
        query.execute()
```

Função SQL correspondente (criar via migração, seguindo o padrão `migrate()` idempotente já usado em outros projetos como SDD Studio):

```sql
create or replace function match_semantic_cache(
    p_group_id uuid,
    p_layer text,
    p_task_type text,
    p_query_embedding vector(1536),
    p_match_count int default 1
)
returns table (
    id uuid,
    cached_response jsonb,
    source_agent text,
    similarity float
)
language sql stable
as $$
    select
        id,
        cached_response,
        source_agent,
        1 - (input_embedding <=> p_query_embedding) as similarity
    from semantic_cache
    where group_id = p_group_id
      and cache_layer = p_layer
      and task_type = p_task_type
      and expires_at > now()
    order by input_embedding <=> p_query_embedding
    limit p_match_count;
$$;

create or replace function increment_cache_hit(p_cache_id uuid)
returns void
language sql
as $$
    update semantic_cache
    set hit_count = hit_count + 1, last_hit_at = now()
    where id = p_cache_id;
$$;
```

---

## 5. Pontos de integração no p2d

### 5.1 Camada de roteamento/classificação

Local de integração: dentro do `Orchestrator`, antes de despachar para o agente de classificação de trechos de transcrição.

```python
# Dentro do Orchestrator, antes de instanciar o agente classificador
cache_result = semantic_cache.check_cache(
    group_id=hub.group_id,
    task_type="intent_classification",
    input_text=trecho_transcricao,
    layer="routing",
)
if cache_result:
    classification = cache_result["cached_response"]
else:
    classification = self._run_classifier_agent(trecho_transcricao)  # via handle_rerun()
    semantic_cache.save_to_cache(
        group_id=hub.group_id,
        task_type="intent_classification",
        input_text=trecho_transcricao,
        response_payload=classification,
        source_agent="ClassifierAgent",
        layer="routing",
    )
```

**Restrição arquitetônica preservada:** o agente continua sendo instanciado apenas via Orchestrator/`handle_rerun()`. O cache intercepta *antes* dessa chamada — nunca substitui o padrão de instanciação quando há cache miss.

### 5.2 Camada de geração de artefatos

Aplicar **somente** para os agentes de geração de BPMN e de ata, e **somente** quando o texto de entrada (transcrição ou seção dela) for suficientemente similar a uma execução anterior *do mesmo grupo*. Dado o threshold de 0.985, isso cobre essencialmente:

- Reprocessamento do mesmo arquivo de transcrição sem alterações.
- Pequenas correções de digitação/pontuação na transcrição que não mudam o conteúdo de negócio.

Não cobre (propositalmente): reuniões diferentes com pauta parecida — a similaridade textual entre duas reuniões distintas dificilmente ultrapassa 0.985 mesmo quando o assunto é o mesmo, o que é o comportamento desejado.

```python
cache_result = semantic_cache.check_cache(
    group_id=hub.group_id,
    task_type="bpmn_generation",
    input_text=hub.transcricao_normalizada,
    layer="artifact",
)
if cache_result:
    hub.bpmn_result = cache_result["cached_response"]
    hub.bpmn_source = f"cache (similaridade {cache_result['similarity']:.4f})"
    # Mesmo em cache hit, o tournament de validação BPMN permanece obrigatório —
    # o cache acelera geração, não substitui validação.
else:
    hub.bpmn_result = self._run_bpmn_tournament(hub)  # fluxo LangGraph existente, inalterado
    semantic_cache.save_to_cache(
        group_id=hub.group_id,
        task_type="bpmn_generation",
        input_text=hub.transcricao_normalizada,
        response_payload=hub.bpmn_result,
        source_agent="BPMNTournamentOrchestrator",
        layer="artifact",
    )
```

**Decisão de design deliberada:** cache hit na camada de artefato **não pula** o tournament de validação BPMN. O cache evita reprocessar a *geração*, mas a validação continua rodando sobre o resultado — isso preserva a garantia de qualidade existente e reduz o risco de um artefato defeituoso persistir via cache indefinidamente.

Salvar `hub` em `session_state` antes do render do widget continua obrigatório, sem alteração nesse ponto do fluxo.

---

## 6. Embeddings

O texto de entrada precisa ser vetorizado antes de consultar o cache. Como o p2d já usa múltiplos providers (DeepSeek como default, mais Anthropic/OpenAI/Groq/Gemini/Grok), recomenda-se:

- Usar um único provider de embeddings fixo para todo o cache (não alternar por sessão), para garantir que os vetores armazenados sejam comparáveis entre si. Trocar de provider de embeddings invalida todo o cache existente.
- Se DeepSeek não expuser endpoint de embeddings adequado, usar OpenAI `text-embedding-3-small` (1536 dimensões, compatível com o schema acima) ou Gemini `text-embedding-004`, mantendo o `vector(1536)` alinhado.
- Documentar a escolha em `CLAUDE.md`/`SKILL.md` do p2d para evitar troca acidental futura — igual ao registro já feito para a depreciação do `deepseek-chat`.

---

## 7. Observabilidade

Adicionar ao painel de BI/status semanal (o mesmo usado nos relatórios FGV/DTI):

- Taxa de cache hit por `task_type` e por `cache_layer`.
- Economia estimada de tokens/custo por semana (comparando `hit_count` × custo médio de chamada evitada).
- Alertas quando `hit_count` de uma entrada da camada `artifact` ultrapassar N (indica possível transcrição duplicada real, útil para detectar retrabalho).

---

## 8. Plano de rollout

1. **Fase 1** — Migração do schema + função SQL, sem uso em produção. Validar com dados sintéticos.
2. **Fase 2** — Ativar apenas `layer="routing"` em ambiente de homologação. Medir taxa de hit real por 1–2 semanas antes de promover.
3. **Fase 3** — Ativar `layer="artifact"` apenas para `bpmn_generation`, mantendo tournament de validação sempre ativo. Acompanhar de perto os primeiros hits manualmente antes de confiar no threshold de 0.985.
4. **Fase 4** — Expandir `layer="artifact"` para geração de ata e relatório executivo, se a fase 3 não apresentar falsos positivos.

Rollback: `invalidate_group()` zera o cache de um grupo específico sem exigir migração ou deploy.

---

## 9. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Vazamento cross-tenant via KNN sem filtro de `group_id` | Filtro de `group_id` obrigatório na função SQL, não apenas na camada Python |
| Cache "engessa" um artefato incorreto por 30 dias | `invalidate_group()` manual + tournament de validação continua rodando mesmo em cache hit |
| Troca de provider de embeddings invalida cache silenciosamente | Registrar provider de embeddings usado por entrada (campo adicional `embedding_provider`, opcional na v2 do schema) |
| Falso positivo de similaridade em transcrições curtas (poucas palavras têm cosseno alto por acaso) | Aplicar tamanho mínimo de texto (ex.: 50 tokens) antes de considerar elegível para cache — abaixo disso, sempre recalcular |

---

## 10. Fora de escopo desta spec

- Cache de nível de infraestrutura (Redis) — não necessário; pgvector no Supabase já atende ao volume esperado do p2d.
- Re-ranking com cross-encoder mencionado no artigo de origem — relevante para RAG de busca em base de conhecimento, não para o fluxo atual do p2d (que não faz retrieval sobre uma KB externa, e sim síntese direta de transcrições).
- Cache para o módulo de transcrição ao vivo (Camada 1–3) — merece spec própria dado o caráter incremental (Extractor/Synthesizer) desse pipeline.