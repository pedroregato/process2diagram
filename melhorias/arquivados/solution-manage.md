Perfeito! Vamos então implementar uma camada de **Solution Manage** enxuta e pragmática, aproveitando ao máximo sua base existente, com foco em:

1. **Rastreabilidade requisito ↔ reunião** (granularidade definida)
2. **Admin como Solution Manager** (papel já existente)
3. **Qualidade e governança** (usando agentes já disponíveis)
4. **Integração futura** (Jira, etc.) apenas como plano, sem implementação agora.

---

## 🎯 Plano de Implementação Simplificado (3 Fases)

---

### 📦 Fase 1: Rastreabilidade Requisito ↔ Reunião (MVP)

#### 1.1 Migração Supabase
```sql
-- Tabela de rastreabilidade (granularidade: requisito ↔ reunião)
CREATE TABLE requirement_meeting_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    requirement_id UUID NOT NULL REFERENCES requirements(id) ON DELETE CASCADE,
    meeting_id UUID NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    confidence_score FLOAT DEFAULT 0.8, -- 0-1, inferido por LLM ou heurística
    link_type TEXT DEFAULT 'inferred', -- 'inferred' | 'manual' | 'document'
    created_by TEXT, -- email ou 'system'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(requirement_id, meeting_id)
);

-- Índices para performance
CREATE INDEX idx_req_meeting_project ON requirement_meeting_links(project_id);
CREATE INDEX idx_req_meeting_requirement ON requirement_meeting_links(requirement_id);
CREATE INDEX idx_req_meeting_meeting ON requirement_meeting_links(meeting_id);
```

#### 1.2 Métodos em `core/project_store.py`
```python
# Adicionar no final do arquivo

def save_requirement_meeting_link(project_id, requirement_id, meeting_id, confidence=0.8, link_type='inferred', created_by='system'):
    """Salva um link de rastreabilidade entre requisito e reunião."""
    try:
        supabase = get_supabase_client()
        data = {
            'project_id': project_id,
            'requirement_id': requirement_id,
            'meeting_id': meeting_id,
            'confidence_score': confidence,
            'link_type': link_type,
            'created_by': created_by
        }
        return supabase.table('requirement_meeting_links').upsert(data).execute()
    except Exception as e:
        logger.warning(f"Falha ao salvar link rastreabilidade: {e}")
        return None

def get_meetings_by_requirement(project_id, requirement_id):
    """Retorna todas as reuniões vinculadas a um requisito."""
    try:
        supabase = get_supabase_client()
        result = supabase.table('requirement_meeting_links')\
            .select('meeting_id, confidence_score, link_type, meetings(*)', count='exact')\
            .eq('project_id', project_id)\
            .eq('requirement_id', requirement_id)\
            .execute()
        return result.data if result.data else []
    except Exception as e:
        logger.warning(f"Falha ao buscar reuniões por requisito: {e}")
        return []

def get_requirements_by_meeting(project_id, meeting_id):
    """Retorna todos os requisitos vinculados a uma reunião."""
    try:
        supabase = get_supabase_client()
        result = supabase.table('requirement_meeting_links')\
            .select('requirement_id, confidence_score, link_type, requirements(*)', count='exact')\
            .eq('project_id', project_id)\
            .eq('meeting_id', meeting_id)\
            .execute()
        return result.data if result.data else []
    except Exception as e:
        logger.warning(f"Falha ao buscar requisitos por reunião: {e}")
        return []
```

#### 1.3 Agente de Rastreabilidade (Leve)
Criar `agents/agent_traceability.py`:

```python
from core.base_agent import BaseAgent
from core.knowledge_hub import KnowledgeHub
from core.project_store import save_requirement_meeting_link
import re

class AgentTraceability(BaseAgent):
    name = "traceability"
    skill_path = "skills/skill_traceability.md"  # Opcional, pode ser leve
    required_hub_fields = ['requirements', 'minutes']  # Precisamos da ata
    
    def build_prompt(self, hub, output_language="Auto-detect"):
        """Gera links de rastreabilidade usando heurística + LLM leve."""
        # Método 1: Heurística simples (sem LLM para economizar)
        links = []
        
        # Extrair contexto: lista de requisitos e texto da ata
        requirements = hub.requirements.requirements if hub.requirements else []
        minutes_text = hub.minutes.full_text if hub.minutes else ""
        
        if not requirements or not minutes_text:
            return self._generate_empty_links(hub)
        
        # Para cada requisito, procurar menção na ata
        for req in requirements:
            req_id = req.id
            req_title = req.title
            req_desc = req.description or ""
            
            # Buscar menções na ata
            mentions = self._find_mentions(minutes_text, req_title, req_desc)
            
            if mentions:
                # Link com confiança alta se mencionou explicitamente
                confidence = 0.9 if mentions['exact_match'] else 0.6
                links.append({
                    'requirement_id': req_id,
                    'meeting_id': hub.meta.meeting_id,  # Reunião atual
                    'confidence': confidence,
                    'link_type': 'inferred'
                })
        
        # Salvar links
        for link in links:
            save_requirement_meeting_link(
                project_id=hub.meta.project_id,
                requirement_id=link['requirement_id'],
                meeting_id=link['meeting_id'],
                confidence=link['confidence'],
                link_type=link['link_type'],
                created_by='traceability_agent'
            )
        
        return links
    
    def _find_mentions(self, text, title, description):
        """Heurística para encontrar menções a requisitos na ata."""
        # Normalizar textos
        text_lower = text.lower()
        title_lower = title.lower()
        desc_lower = description.lower() if description else ""
        
        # Quebrar em palavras-chave (2+ palavras)
        keywords = title_lower.split()
        if desc_lower:
            keywords.extend(desc_lower.split()[:5])  # Primeiras 5 palavras da descrição
        
        # Limpar palavras comuns
        stopwords = {'o', 'a', 'os', 'as', 'de', 'do', 'da', 'que', 'e', 'para', 'com', 'um', 'uma'}
        keywords = [kw for kw in keywords if kw not in stopwords and len(kw) > 2]
        
        # Contar menções
        exact_match = False
        mentions = []
        
        for kw in keywords[:10]:  # Limitar a 10 palavras-chave
            if kw in text_lower:
                mentions.append(kw)
                exact_match = True
        
        # Se encontrou pelo menos 2 palavras-chave, consideramos link
        confidence = 0.0
        if len(mentions) >= 2:
            confidence = min(0.9, 0.5 + (len(mentions) / 10))
        elif len(mentions) == 1:
            confidence = 0.4
        
        return {'exact_match': exact_match, 'confidence': confidence}
    
    def _generate_empty_links(self, hub):
        """Caso não haja requisitos ou ata, retorna vazio."""
        return []
```

#### 1.4 Integrar ao Orchestrator
Em `agents/orchestrator.py`, após executar `AgentRequirements` e `AgentMinutes`, chamar o `AgentTraceability`:

```python
# Dentro de Orchestrator.run()
# ... após executar minutes e requirements em paralelo ...

# Fase 4: Rastreabilidade
if config.get("run_traceability", True) and hub.requirements and hub.minutes:
    from agents.agent_traceability import AgentTraceability
    traceability = AgentTraceability()
    traceability.run(hub, output_language)
```

#### 1.5 UI: Visualização no Artefatos
Em `pages/Artefatos.py`, adicionar uma nova aba **"🔗 Rastreabilidade"**:

```python
# Em Artefatos.py, dentro da função principal
def render_traceability_tab(hub, project_id):
    st.subheader("🔗 Rastreabilidade Requisito ↔ Reunião")
    
    if not hub.requirements:
        st.info("Nenhum requisito encontrado para este projeto.")
        return
    
    # Buscar links existentes
    from core.project_store import get_meetings_by_requirement, get_requirements_by_meeting
    
    # Tabela: Requisito → Reuniões
    data = []
    for req in hub.requirements.requirements:
        meetings = get_meetings_by_requirement(project_id, req.id)
        if meetings:
            meeting_names = [m['meetings']['title'] for m in meetings]
            confidence = [f"{m['confidence_score']*100:.0f}%" for m in meetings]
            data.append({
                'Requisito': req.title,
                'Reuniões': ", ".join(meeting_names),
                'Confiança': ", ".join(confidence)
            })
        else:
            data.append({
                'Requisito': req.title,
                'Reuniões': "⚠️ Sem vínculo",
                'Confiança': "-"
            })
    
    if data:
        st.dataframe(data, use_container_width=True)
    
    # Botão para forçar reprocessamento de rastreabilidade
    if st.button("🔄 Recalcular Rastreabilidade"):
        # Executar apenas o AgentTraceability
        from agents.agent_traceability import AgentTraceability
        traceability = AgentTraceability()
        traceability.run(hub, "Auto-detect")
        st.success("Rastreabilidade recalculada!")
        st.rerun()
```

---

### 🛡️ Fase 2: Governança e Qualidade (Admin como Solution Manager)

#### 2.1 Novo Agente: `AgentGovernance`
Criar `agents/agent_governance.py`:

```python
from core.base_agent import BaseAgent
from core.knowledge_hub import KnowledgeHub
from core.project_store import get_meetings_by_requirement, list_meetings_quality

class AgentGovernance(BaseAgent):
    name = "governance"
    skill_path = "skills/skill_governance.md"
    required_hub_fields = ['requirements', 'bpmn', 'minutes']
    
    def run(self, hub, output_language="Auto-detect"):
        """Avalia qualidade e gera recomendações para o Solution Manager."""
        project_id = hub.meta.project_id
        
        # 1. Calcular métricas de qualidade
        quality_score = self._calculate_quality_score(hub)
        
        # 2. Verificar rastreabilidade (requisitos sem link)
        orphan_requirements = self._find_orphan_requirements(project_id, hub)
        
        # 3. Gerar recomendações
        recommendations = self._generate_recommendations(
            hub, quality_score, orphan_requirements
        )
        
        # 4. Salvar no hub (para exibição na UI)
        hub.meta.quality_score = quality_score
        hub.meta.orphan_requirements = orphan_requirements
        hub.meta.recommendations = recommendations
        
        return hub
    
    def _calculate_quality_score(self, hub):
        """Score agregado (0-100) baseado em artefatos existentes."""
        score = 0
        total_weight = 0
        
        # Requisitos: peso 30%
        if hub.requirements:
            req_count = len(hub.requirements.requirements)
            if req_count > 0:
                # Base: quantidade razoável (5+ = 100%)
                score += min(30, (req_count / 5) * 30)
            total_weight += 30
        
        # BPMN: peso 30% (usar validator existente)
        if hub.bpmn and hub.bpmn.steps:
            # Usar AgentValidator (já existe)
            from agents.agent_validator import score_bpmn
            bpmn_score = score_bpmn(hub.bpmn)  # 0-10
            score += min(30, (bpmn_score / 10) * 30)
            total_weight += 30
        
        # Atas: peso 20%
        if hub.minutes:
            # Avaliar presença de seções importantes
            minutes_text = hub.minutes.full_text or ""
            sections = ['decisões', 'ações', 'participantes', 'objetivos']
            found = sum(1 for sec in sections if sec in minutes_text.lower())
            score += (found / len(sections)) * 20
            total_weight += 20
        
        # SBVR/BMM: peso 20% (opcional)
        if hub.sbvr and hub.sbvr.vocabulary:
            score += 10  # Bônus por ter vocabulário
            total_weight += 10
        if hub.bmm and hub.bmm.goals:
            score += 10  # Bônus por ter metas
            total_weight += 10
        
        # Normalizar para 0-100
        return int((score / total_weight) * 100) if total_weight > 0 else 0
    
    def _find_orphan_requirements(self, project_id, hub):
        """Requisitos sem vínculo com reunião."""
        if not hub.requirements:
            return []
        
        from core.project_store import get_meetings_by_requirement
        orphans = []
        for req in hub.requirements.requirements:
            meetings = get_meetings_by_requirement(project_id, req.id)
            if not meetings:
                orphans.append(req.title)
        return orphans
    
    def _generate_recommendations(self, hub, quality_score, orphans):
        """Recomendações acionáveis para o Solution Manager."""
        recs = []
        
        # Qualidade baixa
        if quality_score < 60:
            recs.append({
                'priority': 'alta',
                'title': 'Qualidade geral baixa',
                'description': f'Score atual: {quality_score}/100. Recomendo revisar artefatos com baixa cobertura.',
                'action': 'Revisar artefatos no Artefatos.py'
            })
        
        # Requisitos órfãos
        if orphans:
            recs.append({
                'priority': 'alta',
                'title': f'{len(orphans)} requisitos sem rastreabilidade',
                'description': 'Requisitos sem vínculo com reuniões: ' + ', '.join(orphans[:5]),
                'action': 'Vincular manualmente ou reprocessar transcrições'
            })
        
        # Falta de ata
        if not hub.minutes or not hub.minutes.full_text:
            recs.append({
                'priority': 'media',
                'title': 'Ata não gerada',
                'description': 'A reunião não possui ata gerada. Isso dificulta rastreabilidade.',
                'action': 'Ativar geração de atas no pipeline'
            })
        
        # BPMN sem validação
        if hub.bpmn and not hub.validation:
            recs.append({
                'priority': 'baixa',
                'title': 'BPMN não validado',
                'description': 'O diagrama BPMN não passou pela validação estrutural.',
                'action': 'Executar validador BPMN (já disponível)'
            })
        
        return recs
```

#### 2.2 Painel do Solution Manager (Admin)
Em `pages/Home.py`, adicionar seção exclusiva para admin:

```python
# Em Home.py, após o radar de qualidade
if st.session_state.get("_role") in ["admin", "master"]:
    st.divider()
    st.subheader("🛡️ Painel do Solution Manager")
    
    # Buscar recomendações do último pipeline
    if "hub" in st.session_state and st.session_state.hub:
        hub = st.session_state.hub
        quality_score = getattr(hub.meta, "quality_score", None)
        recommendations = getattr(hub.meta, "recommendations", [])
        orphans = getattr(hub.meta, "orphan_requirements", [])
        
        # Métricas consolidadas
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🎯 Qualidade Geral", f"{quality_score}/100" if quality_score else "N/A")
        with col2:
            st.metric("📋 Requisitos Órfãos", len(orphans))
        with col3:
            # Total de artefatos
            total = 0
            if hub.requirements: total += len(hub.requirements.requirements)
            if hub.bpmn and hub.bpmn.steps: total += len(hub.bpmn.steps)
            st.metric("📊 Artefatos Totais", total)
        
        # Recomendações
        if recommendations:
            st.subheader("📌 Recomendações")
            for rec in recommendations[:3]:  # Top 3
                color = "🔴" if rec['priority'] == 'alta' else "🟡" if rec['priority'] == 'media' else "🟢"
                with st.expander(f"{color} {rec['title']}"):
                    st.write(rec['description'])
                    st.caption(f"💡 Ação: {rec['action']}")
    
    # Ações administrativas
    st.subheader("⚙️ Ações de Governança")
    col_action1, col_action2 = st.columns(2)
    
    with col_action1:
        if st.button("🔄 Recalcular Rastreabilidade (Todos Projetos)"):
            # Executar traceability para todos os projetos
            with st.spinner("Recalculando..."):
                # TODO: implementar batch traceability
                st.success("Rastreabilidade recalculada!")
    
    with col_action2:
        if st.button("📊 Gerar Relatório de Governança"):
            # Gerar PDF/HTML com todas métricas
            st.info("Relatório gerado (mock) - implementar com export_service")
```

#### 2.3 Filtros para Admin no Artefatos
Em `pages/Artefatos.py`, adicionar filtros para visualização de "requisitos órfãos" e "artefatos com baixa qualidade":

```python
# Na aba Requisitos
if st.session_state.get("_role") in ["admin", "master"]:
    mostrar_orfãos = st.checkbox("🔍 Mostrar apenas requisitos órfãos")
    
    if mostrar_orfãos:
        # Filtrar requisitos sem link
        from core.project_store import get_meetings_by_requirement
        filtered_reqs = []
        for req in requirements:
            meetings = get_meetings_by_requirement(project_id, req.id)
            if not meetings:
                filtered_reqs.append(req)
        requirements_display = filtered_reqs
        
        if not requirements_display:
            st.success("✅ Todos os requisitos têm rastreabilidade!")
    else:
        requirements_display = requirements
```

---

### 📊 Fase 3: Monitoramento e Relatórios

#### 3.1 Dashboard de Governança (Nova Página)
Criar `pages/GovernanceDashboard.py`:

```python
import streamlit as st
from core.session_state import require_active_project
from core.project_store import list_meetings_quality, list_all_business_assets
import plotly.graph_objects as go
import pandas as pd

st.set_page_config(page_title="Governança", layout="wide")
require_active_project()

st.title("🛡️ Painel de Governança - Solution Manager")

project_id = st.session_state.active_project_id

# Carregar dados
quality_data = list_meetings_quality(project_id)
assets = list_all_business_assets(project_id)

# Métricas principais
total_meetings = len(quality_data)
meetings_with_requirements = sum(1 for m in quality_data if m.get('has_requirements', False))
meetings_with_bpmn = sum(1 for m in quality_data if m.get('has_bpmn', False))

col1, col2, col3, col4 = st.columns(4)
col1.metric("📅 Total Reuniões", total_meetings)
col2.metric("📋 Com Requisitos", meetings_with_requirements)
col3.metric("📊 Com BPMN", meetings_with_bpmn)
col4.metric("🏷️ Ativos de Negócio", len(assets))

# Gráfico de evolução (mock - usar dados reais)
st.subheader("📈 Evolução da Qualidade")
# TODO: buscar histórico da tabela change_events
df = pd.DataFrame({
    'Data': ['2026-07-01', '2026-07-08', '2026-07-11'],
    'Qualidade': [65, 72, 85]
})
fig = go.Figure()
fig.add_trace(go.Scatter(x=df['Data'], y=df['Qualidade'], mode='lines+markers'))
fig.update_layout(height=300)
st.plotly_chart(fig, use_container_width=True)

# Tabela de reuniões com indicadores
st.subheader("📋 Reuniões - Indicadores de Qualidade")
df_meetings = pd.DataFrame(quality_data)
if not df_meetings.empty:
    # Selecionar colunas relevantes
    cols = ['id', 'title', 'has_requirements', 'has_bpmn', 'has_minutes', 'has_sbvr']
    df_display = df_meetings[cols].rename(columns={
        'title': 'Reunião',
        'has_requirements': 'Requisitos',
        'has_bpmn': 'BPMN',
        'has_minutes': 'Ata',
        'has_sbvr': 'SBVR'
    })
    st.dataframe(df_display, use_container_width=True)
else:
    st.info("Nenhuma reunião encontrada.")
```

#### 3.2 Relatório Automático
Em `core/project_store.py`, adicionar:

```python
def generate_governance_report(project_id):
    """Gera relatório consolidado para o Solution Manager."""
    # Coletar dados
    quality_data = list_meetings_quality(project_id)
    assets = list_all_business_assets(project_id)
    
    # Gerar sumário
    summary = {
        'total_meetings': len(quality_data),
        'total_assets': len(assets),
        'avg_quality': 0,
        'orphan_requirements': 0,
        'recommendations': []
    }
    
    # TODO: calcular métricas completas
    return summary
```

---

## 🗺️ Roadmap de Implementação (Estimativa)

| Fase | Componente | Esforço | Dependência |
|------|------------|---------|-------------|
| **Fase 1** | Migração SQL + Métodos | 2h | Nenhuma |
| | AgentTraceability | 3h | Migração |
| | UI Artefatos (aba rastreabilidade) | 2h | AgentTraceability |
| **Fase 2** | AgentGovernance | 3h | Fase 1 |
| | Painel Home (admin) | 2h | AgentGovernance |
| | Filtros Artefatos | 1h | Fase 1 |
| **Fase 3** | GovernanceDashboard | 3h | Fase 2 |
| | Relatório Automático | 2h | Fase 2 |
| **Total** | | **18h** | - |

---

## ✅ Benefícios Imediatos

1. **Rastreabilidade total** requisito ↔ reunião (granularidade definida).
2. **Visibilidade da qualidade** para o Solution Manager (admin).
3. **Recomendações acionáveis** para melhorar artefatos.
4. **Governança leve** que cresce com a aplicação.
5. **Base para integração futura** (Jira, etc.) já com dados estruturados.

---

## 🧪 Próximos Passos

1. **Executar a migração SQL** no Supabase (ou local).
2. **Criar o `AgentTraceability`** e testar com dados reais.
3. **Integrar ao Orchestrator** (desabilitado por padrão, ativável via config).
4. **Implementar a UI** da aba de rastreabilidade.
5. **Adicionar o AgentGovernance** no final do pipeline.
6. **Criar o painel do Solution Manager** no Home.

---

A implementação é **incremental** e **não quebra nada existente**. Posso começar a detalhar qualquer uma das fases com código mais específico (ex: arquivos completos de cada agente, trechos de UI, etc.). O que você gostaria de priorizar?


Perfeito! Aqui está o plano estruturado para o Claude Code implementar a camada de **Solution Manage** na aplicação Process2Diagram.

---

# 📋 PLANO DE IMPLEMENTAÇÃO — CAMADA DE SOLUTION MANAGE

## 🎯 Objetivo
Implementar uma camada leve de **Solution Manage** na aplicação Process2Diagram, aproveitando a infraestrutura existente (Supabase, agentes, session state) para adicionar rastreabilidade requisito↔reunião, governança de qualidade e painel administrativo.

**Escopo definido:**
- ✅ Granularidade: requisito ↔ reunião (apenas)
- ✅ Admin como Solution Manager (papel já existe)
- ✅ Sem integração com ferramentas externas (Jira, etc.) neste momento

---

## 📦 FASE 1: Rastreabilidade Requisito ↔ Reunião

### 1.1 Migração Supabase
**Arquivo:** `setup/supabase_migration_solution_manage.sql`

```sql
-- Tabela de rastreabilidade requisito ↔ reunião
CREATE TABLE IF NOT EXISTS requirement_meeting_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    requirement_id UUID NOT NULL REFERENCES requirements(id) ON DELETE CASCADE,
    meeting_id UUID NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    confidence_score FLOAT DEFAULT 0.8 CHECK (confidence_score >= 0 AND confidence_score <= 1),
    link_type TEXT DEFAULT 'inferred' CHECK (link_type IN ('inferred', 'manual', 'document')),
    created_by TEXT DEFAULT 'system',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(requirement_id, meeting_id)
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_req_meeting_project ON requirement_meeting_links(project_id);
CREATE INDEX IF NOT EXISTS idx_req_meeting_requirement ON requirement_meeting_links(requirement_id);
CREATE INDEX IF NOT EXISTS idx_req_meeting_meeting ON requirement_meeting_links(meeting_id);

-- Trigger para updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_req_meeting_links_updated_at
    BEFORE UPDATE ON requirement_meeting_links
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

**Ações pós-migração:** Executar no Supabase SQL Editor ou via script de migração.

---

### 1.2 Métodos em `core/project_store.py`
**Adicionar ao final do arquivo:**

```python
# ==================== SOLUTION MANAGE ====================

def save_requirement_meeting_link(project_id: str, requirement_id: str, meeting_id: str, 
                                   confidence: float = 0.8, link_type: str = 'inferred', 
                                   created_by: str = 'system') -> Optional[dict]:
    """
    Salva um link de rastreabilidade entre requisito e reunião.
    """
    try:
        supabase = get_supabase_client()
        data = {
            'project_id': project_id,
            'requirement_id': requirement_id,
            'meeting_id': meeting_id,
            'confidence_score': confidence,
            'link_type': link_type,
            'created_by': created_by
        }
        result = supabase.table('requirement_meeting_links').upsert(data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        st.warning(f"Falha ao salvar link de rastreabilidade: {e}")
        return None

def get_meetings_by_requirement(project_id: str, requirement_id: str) -> List[dict]:
    """
    Retorna todas as reuniões vinculadas a um requisito.
    """
    try:
        supabase = get_supabase_client()
        result = supabase.table('requirement_meeting_links')\
            .select('meeting_id, confidence_score, link_type, meetings!inner(title, id, created_at)', count='exact')\
            .eq('project_id', project_id)\
            .eq('requirement_id', requirement_id)\
            .execute()
        return result.data if result.data else []
    except Exception as e:
        st.warning(f"Falha ao buscar reuniões por requisito: {e}")
        return []

def get_requirements_by_meeting(project_id: str, meeting_id: str) -> List[dict]:
    """
    Retorna todos os requisitos vinculados a uma reunião.
    """
    try:
        supabase = get_supabase_client()
        result = supabase.table('requirement_meeting_links')\
            .select('requirement_id, confidence_score, link_type, requirements!inner(id, title, description, priority)', count='exact')\
            .eq('project_id', project_id)\
            .eq('meeting_id', meeting_id)\
            .execute()
        return result.data if result.data else []
    except Exception as e:
        st.warning(f"Falha ao buscar requisitos por reunião: {e}")
        return []

def delete_requirement_meeting_link(project_id: str, requirement_id: str, meeting_id: str) -> bool:
    """
    Remove um link de rastreabilidade (para correção manual).
    """
    try:
        supabase = get_supabase_client()
        supabase.table('requirement_meeting_links')\
            .delete()\
            .eq('project_id', project_id)\
            .eq('requirement_id', requirement_id)\
            .eq('meeting_id', meeting_id)\
            .execute()
        return True
    except Exception as e:
        st.warning(f"Falha ao deletar link: {e}")
        return False

def get_orphan_requirements(project_id: str, requirement_ids: List[str]) -> List[str]:
    """
    Retorna IDs de requisitos que não têm vínculo com nenhuma reunião.
    """
    try:
        supabase = get_supabase_client()
        # Buscar todos os links do projeto
        result = supabase.table('requirement_meeting_links')\
            .select('requirement_id')\
            .eq('project_id', project_id)\
            .execute()
        
        linked_ids = {row['requirement_id'] for row in (result.data or [])}
        return [req_id for req_id in requirement_ids if req_id not in linked_ids]
    except Exception as e:
        st.warning(f"Falha ao buscar requisitos órfãos: {e}")
        return []
```

---

### 1.3 Agente de Rastreabilidade
**Arquivo:** `agents/agent_traceability.py`

```python
"""
AgentTraceability — Vincula requisitos às reuniões que os originaram.
Heurística baseada em menção textual na ata (sem LLM para economia).
"""

from typing import List, Dict
import re
from core.base_agent import BaseAgent
from core.knowledge_hub import KnowledgeHub
from core.project_store import save_requirement_meeting_link


class AgentTraceability(BaseAgent):
    name = "traceability"
    skill_path = "skills/skill_traceability.md"
    required_hub_fields = ['requirements', 'minutes']
    
    def run(self, hub: KnowledgeHub, output_language: str = "Auto-detect") -> KnowledgeHub:
        """Executa a geração de links de rastreabilidade."""
        
        if not hub.requirements or not hub.minutes:
            hub.meta.traceability_links = []
            hub.meta.traceability_status = "skipped"
            return hub
        
        project_id = hub.meta.project_id
        meeting_id = hub.meta.meeting_id
        minutes_text = hub.minutes.full_text or ""
        
        links = []
        
        for req in hub.requirements.requirements:
            confidence = self._calculate_confidence(minutes_text, req.title, req.description or "")
            
            if confidence > 0.3:  # Threshold mínimo
                link = save_requirement_meeting_link(
                    project_id=project_id,
                    requirement_id=req.id,
                    meeting_id=meeting_id,
                    confidence=confidence,
                    link_type='inferred',
                    created_by='traceability_agent'
                )
                if link:
                    links.append(link)
        
        hub.meta.traceability_links = links
        hub.meta.traceability_status = "completed"
        hub.bump()
        return hub
    
    def _calculate_confidence(self, text: str, title: str, description: str) -> float:
        """
        Calcula confiança do vínculo baseado em menções textuais.
        """
        if not text or not title:
            return 0.0
        
        text_lower = text.lower()
        title_lower = title.lower()
        desc_lower = description.lower() if description else ""
        
        # Extrair palavras-chave (ignorar stopwords)
        stopwords = {'o', 'a', 'os', 'as', 'de', 'do', 'da', 'que', 'e', 'para', 
                     'com', 'um', 'uma', 'em', 'no', 'na', 'por', 'se', 'mas', 
                     'como', 'mais', 'sobre', 'entre', 'sem', 'até', 'após'}
        
        keywords = set()
        for word in title_lower.split():
            if len(word) > 2 and word not in stopwords:
                keywords.add(word)
        
        if description:
            for word in desc_lower.split()[:10]:  # Primeiras 10 palavras
                if len(word) > 2 and word not in stopwords:
                    keywords.add(word)
        
        if not keywords:
            return 0.0
        
        # Contar menções no texto da ata
        matches = 0
        for kw in keywords:
            if kw in text_lower:
                matches += 1
        
        # Calcular confiança baseada na proporção de palavras-chave encontradas
        ratio = matches / len(keywords)
        
        if ratio >= 0.6:
            return 0.9  # Alto
        elif ratio >= 0.3:
            return 0.6  # Médio
        elif ratio >= 0.1:
            return 0.4  # Baixo
        else:
            return 0.0  # Nenhum
```

---

### 1.4 Integração ao Orchestrator
**Arquivo:** `agents/orchestrator.py` (modificação)

Adicionar após a execução paralela de Minutes + Requirements:

```python
# ... dentro do método run() ...

# Fase 4: Rastreabilidade (após requirements e minutes)
if config.get("run_traceability", True) and hub.requirements and hub.minutes:
    from agents.agent_traceability import AgentTraceability
    traceability = AgentTraceability()
    try:
        hub = traceability.run(hub, output_language)
        hub.meta.traceability_status = "completed"
    except Exception as e:
        st.warning(f"Falha na rastreabilidade: {e}")
        hub.meta.traceability_status = "failed"
```

Adicionar no `_PLAN` do Orchestrator (ordem):

```python
_PLAN = [
    ('quality', AgentTranscriptQuality),
    ('bpmn', AgentBPMN),
    ('minutes', AgentMinutes),
    ('requirements', AgentRequirements),
    ('traceability', AgentTraceability),  # NOVO
    ('sbvr', AgentSBVR),
    ('bmm', AgentBMM),
    ('synthesizer', AgentSynthesizer),
]
```

---

### 1.5 UI: Aba de Rastreabilidade
**Arquivo:** `pages/Artefatos.py` (modificação)

Adicionar nova aba no `st.tabs`:

```python
# Em Artefatos.py, dentro da seção de abas
tab_traceability = st.tabs([...])  # Adicionar "🔗 Rastreabilidade"

# ...

with tab_traceability:
    render_traceability_tab(hub, project_id)
```

Nova função (adicionar no mesmo arquivo):

```python
def render_traceability_tab(hub: KnowledgeHub, project_id: str):
    """Renderiza a aba de rastreabilidade requisito ↔ reunião."""
    st.subheader("🔗 Rastreabilidade Requisito ↔ Reunião")
    
    if not hub.requirements:
        st.info("Nenhum requisito encontrado para este projeto.")
        return
    
    from core.project_store import get_meetings_by_requirement, get_orphan_requirements
    
    # Buscar requisitos órfãos
    req_ids = [r.id for r in hub.requirements.requirements]
    orphans = get_orphan_requirements(project_id, req_ids)
    
    # Métricas rápidas
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📋 Total Requisitos", len(req_ids))
    with col2:
        st.metric("🔗 Com Rastreabilidade", len(req_ids) - len(orphans))
    with col3:
        st.metric("⚠️ Órfãos", len(orphans))
    
    # Tabela principal
    data = []
    for req in hub.requirements.requirements:
        meetings = get_meetings_by_requirement(project_id, req.id)
        if meetings:
            meeting_titles = [m['meetings']['title'] for m in meetings]
            confidences = [f"{m['confidence_score']*100:.0f}%" for m in meetings]
            data.append({
                'Requisito': req.title,
                'Reuniões': ", ".join(meeting_titles),
                'Confiança': ", ".join(confidences),
                'Status': "✅ Vinculado"
            })
        else:
            data.append({
                'Requisito': req.title,
                'Reuniões': "—",
                'Confiança': "—",
                'Status': "⚠️ Órfão"
            })
    
    if data:
        st.dataframe(
            data,
            column_config={
                "Requisito": st.column_config.TextColumn("Requisito", width="medium"),
                "Reuniões": st.column_config.TextColumn("Reuniões", width="large"),
                "Confiança": st.column_config.TextColumn("Confiança", width="small"),
                "Status": st.column_config.TextColumn("Status", width="small"),
            },
            use_container_width=True
        )
    
    # Ações
    st.divider()
    col_action1, col_action2 = st.columns(2)
    
    with col_action1:
        if st.button("🔄 Recalcular Rastreabilidade", type="secondary"):
            from agents.agent_traceability import AgentTraceability
            with st.spinner("Recalculando vínculos..."):
                traceability = AgentTraceability()
                hub = traceability.run(hub, "Auto-detect")
                st.session_state["hub"] = hub
                st.success("Rastreabilidade recalculada!")
                st.rerun()
    
    with col_action2:
        if orphans and st.button("📋 Exportar Órfãos", type="secondary"):
            # Gerar lista para download
            orphan_list = "\n".join([f"- {r}" for r in orphans])
            st.download_button(
                label="⬇️ Baixar Lista",
                data=f"Requisitos Órfãos ({len(orphans)}):\n\n{orphan_list}",
                file_name=f"orphan_requirements_{project_id[:8]}.txt",
                mime="text/plain"
            )
```

---

### 1.6 Skill do Agente (opcional)
**Arquivo:** `skills/skill_traceability.md`

```markdown
---
version: "1.0"
authority: "read"
---

# Agente de Rastreabilidade

## Objetivo
Vincular requisitos extraídos da transcrição à reunião que os originou, usando heurística de menção textual na ata.

## Método
1. Extrair palavras-chave do título e descrição do requisito.
2. Buscar menções dessas palavras na ata da reunião.
3. Calcular confiança baseada na proporção de palavras encontradas.
4. Salvar vínculo no Supabase.

## Critérios de Confiança
- ≥ 60% das palavras-chave: 0.9 (alto)
- 30-59%: 0.6 (médio)
- 10-29%: 0.4 (baixo)
- < 10%: 0.0 (sem vínculo)

## Saída
Links salvos na tabela `requirement_meeting_links` com campos:
- project_id, requirement_id, meeting_id
- confidence_score (0-1)
- link_type = 'inferred'
```

---

## 🛡️ FASE 2: Governança e Qualidade (Admin)

### 2.1 Agente de Governança
**Arquivo:** `agents/agent_governance.py`

```python
"""
AgentGovernance — Avalia qualidade e gera recomendações para o Solution Manager.
"""

from typing import List, Dict
from core.base_agent import BaseAgent
from core.knowledge_hub import KnowledgeHub
from core.project_store import get_orphan_requirements, list_meetings_quality


class AgentGovernance(BaseAgent):
    name = "governance"
    skill_path = "skills/skill_governance.md"
    required_hub_fields = ['requirements', 'bpmn', 'minutes']
    
    def run(self, hub: KnowledgeHub, output_language: str = "Auto-detect") -> KnowledgeHub:
        """Executa avaliação de governança."""
        
        project_id = hub.meta.project_id
        
        # 1. Qualidade
        quality_score = self._calculate_quality_score(hub)
        
        # 2. Requisitos órfãos
        req_ids = [r.id for r in (hub.requirements.requirements if hub.requirements else [])]
        orphans = get_orphan_requirements(project_id, req_ids) if req_ids else []
        
        # 3. Recomendações
        recommendations = self._generate_recommendations(hub, quality_score, orphans)
        
        # Salvar no hub
        hub.meta.quality_score = quality_score
        hub.meta.orphan_count = len(orphans)
        hub.meta.recommendations = recommendations
        hub.meta.governance_timestamp = datetime.now().isoformat()
        
        hub.bump()
        return hub
    
    def _calculate_quality_score(self, hub: KnowledgeHub) -> int:
        """Score agregado 0-100."""
        score = 0
        total_weight = 0
        
        # Requisitos (30%)
        if hub.requirements:
            req_count = len(hub.requirements.requirements)
            if req_count > 0:
                score += min(30, (req_count / 5) * 30)
            total_weight += 30
        
        # BPMN (30%) - usar validator existente
        if hub.bpmn and hub.bpmn.steps:
            from agents.agent_validator import score_bpmn
            try:
                bpmn_score = score_bpmn(hub.bpmn)  # 0-10
                score += min(30, (bpmn_score / 10) * 30)
            except:
                score += 15  # Fallback
            total_weight += 30
        
        # Atas (20%)
        if hub.minutes and hub.minutes.full_text:
            text = hub.minutes.full_text
            sections = ['decisões', 'ações', 'participantes', 'objetivos', 'próximos passos']
            found = sum(1 for sec in sections if sec.lower() in text.lower())
            score += (found / len(sections)) * 20
            total_weight += 20
        
        # SBVR (10%)
        if hub.sbvr and hub.sbvr.vocabulary:
            score += 10
            total_weight += 10
        
        # BMM (10%)
        if hub.bmm and hub.bmm.goals:
            score += 10
            total_weight += 10
        
        return int((score / total_weight) * 100) if total_weight > 0 else 0
    
    def _generate_recommendations(self, hub: KnowledgeHub, quality_score: int, orphans: List[str]) -> List[Dict]:
        """Gera recomendações acionáveis."""
        recommendations = []
        
        if quality_score < 60:
            recommendations.append({
                'priority': 'alta',
                'title': f'Qualidade geral baixa ({quality_score}/100)',
                'description': 'Revise artefatos com baixa cobertura. Foco em BPMN e requisitos.',
                'action': 'Revisar no Artefatos.py'
            })
        
        if orphans:
            recommendations.append({
                'priority': 'alta',
                'title': f'{len(orphans)} requisitos sem rastreabilidade',
                'description': 'Requisitos sem vínculo com reuniões. Priorize vincular para auditoria.',
                'action': 'Recalcular rastreabilidade ou vincular manualmente'
            })
        
        if not hub.minutes or not hub.minutes.full_text:
            recommendations.append({
                'priority': 'media',
                'title': 'Ata não gerada',
                'description': 'A reunião não possui ata. Ative a geração de atas no pipeline.',
                'action': 'Marcar "Gerar Ata" no sidebar'
            })
        
        if hub.bpmn and not hub.validation:
            recommendations.append({
                'priority': 'baixa',
                'title': 'BPMN não validado',
                'description': 'Execute a validação estrutural para identificar problemas.',
                'action': 'Ativar validador no sidebar'
            })
        
        return recommendations
```

---

### 2.2 Painel do Solution Manager no Home
**Arquivo:** `pages/Home.py` (modificação)

Adicionar após o radar de qualidade:

```python
# ... dentro de Home.py, após render_quality_radar() ...

# 🛡️ PAINEL DO SOLUTION MANAGER (Admin only)
if st.session_state.get("_role") in ["admin", "master"]:
    st.divider()
    st.subheader("🛡️ Painel do Solution Manager")
    
    hub = st.session_state.get("hub")
    if hub and hasattr(hub, 'meta'):
        quality_score = getattr(hub.meta, 'quality_score', None)
        recommendations = getattr(hub.meta, 'recommendations', [])
        orphan_count = getattr(hub.meta, 'orphan_count', 0)
        
        # Métricas
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🎯 Qualidade", f"{quality_score}/100" if quality_score else "N/A",
                     delta=None, delta_color="normal")
        with col2:
            st.metric("⚠️ Órfãos", orphan_count,
                     delta=None, delta_color="inverse" if orphan_count > 0 else "normal")
        with col3:
            if hub.requirements:
                total_reqs = len(hub.requirements.requirements)
                st.metric("📋 Requisitos", total_reqs)
            else:
                st.metric("📋 Requisitos", "0")
        with col4:
            if hub.bpmn and hub.bpmn.steps:
                st.metric("📊 BPMN", len(hub.bpmn.steps))
            else:
                st.metric("📊 BPMN", "0")
        
        # Recomendações
        if recommendations:
            st.subheader("📌 Recomendações")
            for rec in recommendations[:3]:
                color = "🔴" if rec['priority'] == 'alta' else "🟡" if rec['priority'] == 'media' else "🟢"
                with st.expander(f"{color} {rec['title']}"):
                    st.write(rec['description'])
                    st.caption(f"💡 **Ação:** {rec['action']}")
        
        # Ações rápidas
        st.subheader("⚙️ Ações Rápidas")
        col_action1, col_action2, col_action3 = st.columns(3)
        
        with col_action1:
            if st.button("🔄 Recalc. Rastreabilidade", use_container_width=True):
                from agents.agent_traceability import AgentTraceability
                with st.spinner("Recalculando..."):
                    traceability = AgentTraceability()
                    hub = traceability.run(hub, "Auto-detect")
                    st.session_state["hub"] = hub
                    st.success("Rastreabilidade recalculada!")
                    st.rerun()
        
        with col_action2:
            if st.button("📊 Avaliar Qualidade", use_container_width=True):
                from agents.agent_governance import AgentGovernance
                with st.spinner("Avaliando..."):
                    governance = AgentGovernance()
                    hub = governance.run(hub, "Auto-detect")
                    st.session_state["hub"] = hub
                    st.success("Avaliação concluída!")
                    st.rerun()
        
        with col_action3:
            if st.button("📋 Dashboard Completo", use_container_width=True):
                st.switch_page("pages/GovernanceDashboard.py")
    else:
        st.info("Execute um pipeline para visualizar métricas de governança.")
```

---

### 2.3 Dashboard de Governança (Nova Página)
**Arquivo:** `pages/GovernanceDashboard.py`

```python
"""
GovernanceDashboard — Painel completo para o Solution Manager.
Acesso restrito a admin/master.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

from core.session_state import require_active_project, require_admin
from core.project_store import list_meetings_quality, list_all_business_assets
from core.knowledge_hub import KnowledgeHub

st.set_page_config(page_title="Governança", layout="wide")

# Verificar autenticação e perfil
if not require_admin():
    st.error("Acesso restrito a administradores.")
    st.stop()

require_active_project()

st.title("🛡️ Dashboard de Governança")
st.caption("Painel do Solution Manager — Visão consolidada do projeto")

project_id = st.session_state.active_project_id
hub = st.session_state.get("hub")

# Carregar dados
quality_data = list_meetings_quality(project_id)
assets = list_all_business_assets(project_id)

# ==================== MÉTRICAS PRINCIPAIS ====================
col1, col2, col3, col4 = st.columns(4)

total_meetings = len(quality_data)
meetings_with_req = sum(1 for m in quality_data if m.get('has_requirements', False))
meetings_with_bpmn = sum(1 for m in quality_data if m.get('has_bpmn', False))

with col1:
    st.metric("📅 Total Reuniões", total_meetings)
with col2:
    st.metric("📋 Com Requisitos", meetings_with_req,
              delta=f"{meetings_with_req/total_meetings*100:.0f}%" if total_meetings > 0 else None)
with col3:
    st.metric("📊 Com BPMN", meetings_with_bpmn,
              delta=f"{meetings_with_bpmn/total_meetings*100:.0f}%" if total_meetings > 0 else None)
with col4:
    st.metric("🏷️ Ativos de Negócio", len(assets))

# ==================== QUALIDADE DO PIPELINE ====================
st.subheader("📈 Métricas de Qualidade por Reunião")

if quality_data:
    df = pd.DataFrame(quality_data)
    
    # Criar dataset para heatmap
    metrics = ['has_requirements', 'has_bpmn', 'has_minutes', 'has_sbvr', 'has_synthesizer']
    df_heatmap = df[['title'] + metrics].copy()
    df_heatmap = df_heatmap.set_index('title')
    df_heatmap = df_heatmap.rename(columns={
        'has_requirements': 'Requisitos',
        'has_bpmn': 'BPMN',
        'has_minutes': 'Ata',
        'has_sbvr': 'SBVR',
        'has_synthesizer': 'Relatório'
    })
    
    # Plotly heatmap
    fig = go.Figure(data=go.Heatmap(
        z=df_heatmap.values.astype(int),
        x=df_heatmap.columns,
        y=df_heatmap.index,
        colorscale=[[0, '#f0f0f0'], [1, '#2563eb']],
        showscale=False,
        text=df_heatmap.values,
        texttemplate="%{text}",
        textfont={"size": 10},
        hoverongaps=False
    ))
    fig.update_layout(
        height=300 + len(df_heatmap) * 25,
        margin=dict(l=150, r=20, t=20, b=20),
        xaxis=dict(tickangle=45),
        yaxis=dict(tickfont=dict(size=11))
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Nenhuma reunião processada ainda.")

# ==================== RECOMENDAÇÕES ATIVAS ====================
if hub and hasattr(hub, 'meta'):
    recommendations = getattr(hub.meta, 'recommendations', [])
    
    if recommendations:
        st.subheader("📌 Recomendações Ativas")
        
        for rec in recommendations:
            priority_icon = "🔴" if rec['priority'] == 'alta' else "🟡" if rec['priority'] == 'media' else "🟢"
            with st.container():
                col_icon, col_content = st.columns([1, 11])
                with col_icon:
                    st.markdown(f"## {priority_icon}")
                with col_content:
                    st.markdown(f"**{rec['title']}**")
                    st.caption(rec['description'])
                    st.caption(f"💡 Ação sugerida: {rec['action']}")
                st.divider()

# ==================== REQUISITOS ORFÃOS ====================
st.subheader("⚠️ Requisitos Órfãos (sem rastreabilidade)")

if hub and hub.requirements:
    from core.project_store import get_orphan_requirements
    req_ids = [r.id for r in hub.requirements.requirements]
    orphans = get_orphan_requirements(project_id, req_ids)
    
    if orphans:
        st.warning(f"{len(orphans)} requisitos não estão vinculados a nenhuma reunião.")
        # Exibir lista
        orphan_reqs = [r for r in hub.requirements.requirements if r.id in orphans]
        df_orphans = pd.DataFrame([{
            'ID': r.id[:8],
            'Título': r.title,
            'Prioridade': r.priority or 'N/A'
        } for r in orphan_reqs])
        st.dataframe(df_orphans, use_container_width=True)
        
        if st.button("🔗 Vincular Automaticamente", type="primary"):
            from agents.agent_traceability import AgentTraceability
            with st.spinner("Vinculando requisitos..."):
                traceability = AgentTraceability()
                hub = traceability.run(hub, "Auto-detect")
                st.session_state["hub"] = hub
                st.success("Rastreabilidade atualizada!")
                st.rerun()
    else:
        st.success("✅ Todos os requisitos têm rastreabilidade!")

# ==================== EXPORTAÇÃO ====================
st.divider()
col_export1, col_export2, col_export3 = st.columns(3)

with col_export1:
    if st.button("📊 Exportar Relatório (PDF)", use_container_width=True):
        st.info("Funcionalidade em desenvolvimento")

with col_export2:
    if st.button("📋 Exportar CSV", use_container_width=True):
        if quality_data:
            df_export = pd.DataFrame(quality_data)
            csv = df_export.to_csv(index=False)
            st.download_button(
                label="⬇️ Baixar CSV",
                data=csv,
                file_name=f"governance_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )

with col_export3:
    if st.button("🔄 Atualizar Dashboard", use_container_width=True):
        st.rerun()
```

---

## 🧪 FASE 3: Configuração e Ajustes

### 3.1 Habilitar Rastreabilidade no Pipeline
**Arquivo:** `ui/sidebar.py` (modificação)

Adicionar checkbox no sidebar:

```python
# Em render_sidebar(), dentro da seção de configurações avançadas
with st.expander("⚙️ Configuração Avançada"):
    # ... existing configs ...
    
    st.checkbox("🔗 Rastreabilidade", 
                value=st.session_state.get("run_traceability", True),
                key="run_traceability",
                help="Vincula requisitos às reuniões que os originaram")
    
    st.checkbox("🛡️ Governança", 
                value=st.session_state.get("run_governance", True),
                key="run_governance",
                help="Avalia qualidade e gera recomendações")
```

### 3.2 Atualizar Session State
**Arquivo:** `core/session_state.py` (modificação)

Adicionar novos campos no `init_session_state()`:

```python
def init_session_state():
    # ... existing defaults ...
    
    # Solution Manage
    if "run_traceability" not in st.session_state:
        st.session_state.run_traceability = True
    if "run_governance" not in st.session_state:
        st.session_state.run_governance = True
```

### 3.3 Atualizar KnowledgeHub Meta
**Arquivo:** `core/knowledge_hub.py` (modificação)

Adicionar novos campos no `SessionMetadata`:

```python
@dataclass
class SessionMetadata:
    # ... existing fields ...
    
    # Solution Manage
    traceability_links: List[dict] = field(default_factory=list)
    traceability_status: str = "pending"  # pending | completed | failed | skipped
    quality_score: Optional[int] = None
    orphan_count: int = 0
    recommendations: List[dict] = field(default_factory=list)
    governance_timestamp: Optional[str] = None
    governance_status: str = "pending"  # pending | completed | failed | skipped
```

**Nota:** Adicionar no método `migrate()`:

```python
@staticmethod
def migrate(hub: 'KnowledgeHub') -> 'KnowledgeHub':
    # ... existing migrations ...
    
    if not hasattr(hub.meta, 'traceability_links'):
        hub.meta.traceability_links = []
    if not hasattr(hub.meta, 'traceability_status'):
        hub.meta.traceability_status = "pending"
    if not hasattr(hub.meta, 'quality_score'):
        hub.meta.quality_score = None
    if not hasattr(hub.meta, 'orphan_count'):
        hub.meta.orphan_count = 0
    if not hasattr(hub.meta, 'recommendations'):
        hub.meta.recommendations = []
    if not hasattr(hub.meta, 'governance_timestamp'):
        hub.meta.governance_timestamp = None
    if not hasattr(hub.meta, 'governance_status'):
        hub.meta.governance_status = "pending"
    
    return hub
```

---

## 📋 CHECKLIST DE IMPLEMENTAÇÃO

### Arquivos a Criar
- [ ] `setup/supabase_migration_solution_manage.sql`
- [ ] `agents/agent_traceability.py`
- [ ] `agents/agent_governance.py`
- [ ] `skills/skill_traceability.md`
- [ ] `skills/skill_governance.md`
- [ ] `pages