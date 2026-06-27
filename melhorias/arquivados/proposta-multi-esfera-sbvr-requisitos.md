Aqui está a proposta de melhoria completa e pronta para ser colada diretamente no terminal do **Claude Code** dentro do PyCharm.

---

```markdown
# Proposta de Melhoria: Multi-Esfera para SBVR + Rastreabilidade entre Regras e Requisitos

## Objetivo Estratégico

Evoluir o Process2Diagram para suportar **múltiplas esferas do negócio** (Marketing, Financeiro, RH, Operações, Jurídico, Tecnologia) dentro do framework OMG (BMM + SBVR + BPMN + IEEE 830), garantindo que cada regra de negócio seja atribuível a um dono e rastreável até requisitos específicos.

## Contexto Atual vs. Esperado

| Aspecto | Estado Atual | Estado Esperado |
|---------|--------------|------------------|
| SBVR | Extrai regras sem contexto de esfera | Regras com `sphere` + `sphere_owner` |
| Requirements | Independente do SBVR | Campo `business_rule_refs: List[str]` |
| Orquestrador | SBVR executa depois de Requirements | SBVR antes de Requirements |
| Relatório | Lista plana de regras | Agrupado por esfera + badges de rastreabilidade |
| BMM | Isolado | Políticas BMM vinculadas às regras SBVR |

## Arquivos a Serem Modificados

### 1. `core/knowledge_hub.py` — Modelos de Dados

**Localização:** Linhas ~150-200 (após definição de `TranscriptQualityModel`)

**O que fazer:** Adicionar novos campos às dataclasses existentes

```python
# Adicionar após a classe BusinessRule (atualmente dentro do SBVR)
@dataclass
class BusinessRule:
    """OMG SBVR Business Rule com contexto multi-esfera"""
    rule_id: str  # BR-001
    structural_fact: str  # "Campanha → tem → Público-alvo"
    operational_restriction: str  # "É proibido criar campanha sem público-alvo"
    sphere: Literal["marketing", "financeiro", "rh", "operacoes", "juridico", "tecnologia", "geral"]
    sphere_owner: str  # "CMO", "CFO", "CHRO", "COO", "CTO", "CEO"
    bmm_policy_ref: Optional[str]  # "POL-001" — referência a hub.bmm.policies
    speaker_quote: str  # "Fala original do cliente"
    source_meeting_id: Optional[str]  # UUID da reunião (se disponível)

@dataclass
class SBVRModel:
    """Container para SBVR artifacts"""
    vocabulary: List[BusinessTerm]
    rules: List[BusinessRule]  # <-- ATUALIZAR este campo para usar BusinessRule acima
    rule_facts: List[str]  # Fatos atômicos extraídos (backcompat)

# Adicionar campo em RequirementItem (já existe dentro de RequirementsModel)
@dataclass
class RequirementItem:
    id: str  # REQ-001
    title: str
    description: str
    priority: Literal["alta", "media", "baixa"]
    status: Literal["proposto", "aprovado", "implementado", "bloqueado"]
    business_rule_refs: List[str] = field(default_factory=list)  # ["BR-001", "BR-003"]
    sphere: Optional[str] = None  # Herdado da regra de negócio, para filtro rápido
    # Campos existentes: category, owner, created_at...
```

**Instrução para o Claude:** Mantenha compatibilidade retroativa via `__post_init__` ou método `migrate()` para converter SBVR antigo (lista de strings) para novo formato.

---

### 2. `agents/agent_sbvr.py` — Extração com Esfera

**Localização:** Método `build_prompt()` e método `run()`

**O que fazer:** Atualizar o prompt e o parser para extrair campos de esfera

```python
# Em build_prompt(), adicionar contexto BMM se disponível
def build_prompt(self, hub, output_language="Auto-detect") -> tuple[str, str]:
    base_prompt = self._load_skill()  # skill_sbvr.md (atualizado abaixo)
    
    # Adicionar contexto BMM se existir
    bmm_context = ""
    if hub.bmm and hub.bmm.policies:
        policies_text = "\n".join([f"- {p}" for p in hub.bmm.policies[:5]])
        bmm_context = f"""
## Políticas Corporativas (BMM) para Contexto
As seguintes políticas da empresa podem influenciar as regras de negócio:
{policies_text}

Para cada regra extraída, indique se ela implementa alguma destas políticas (use `bmm_policy_ref`).
"""
    
    system = base_prompt + bmm_context
    user = f"""
Extraia todas as regras de negócio da transcrição abaixo.
Idioma de saída: {output_language}

Transcrição:
{hub.transcript_clean[:15000]}  # Limite para evitar estouro de contexto
"""
    return system, user

# Em run(), modificar o parser para aceitar novo schema
def run(self, hub, output_language="Auto-detect") -> KnowledgeHub:
    system, user = self.build_prompt(hub, output_language)
    data = self._call_with_retry(system, user, hub)
    
    # Schema esperado (ver skill_sbvr.md atualizado)
    # {
    #   "rules": [
    #     {
    #       "rule_id": "BR-001",
    #       "structural_fact": "...",
    #       "operational_restriction": "...",
    #       "sphere": "marketing",
    #       "sphere_owner": "CMO",
    #       "bmm_policy_ref": null,
    #       "speaker_quote": "..."
    #     }
    #   ],
    #   "vocabulary": [...]
    # }
    
    if "rules" in data:
        parsed_rules = []
        for rule_data in data["rules"]:
            # Validação de esfera
            valid_spheres = ["marketing", "financeiro", "rh", "operacoes", "juridico", "tecnologia", "geral"]
            sphere = rule_data.get("sphere", "geral")
            if sphere not in valid_spheres:
                sphere = "geral"
            
            parsed_rules.append(BusinessRule(
                rule_id=rule_data.get("rule_id", f"BR-{len(parsed_rules)+1:03d}"),
                structural_fact=rule_data.get("structural_fact", ""),
                operational_restriction=rule_data.get("operational_restriction", ""),
                sphere=sphere,
                sphere_owner=rule_data.get("sphere_owner", "CEO"),
                bmm_policy_ref=rule_data.get("bmm_policy_ref"),
                speaker_quote=rule_data.get("speaker_quote", ""),
                source_meeting_id=hub.meta.meeting_id if hasattr(hub.meta, 'meeting_id') else None
            ))
        
        hub.sbvr.rules = parsed_rules
        hub.sbvr.rule_facts = [r.structural_fact for r in parsed_rules]  # backcompat
    
    hub.mark_agent_run(self.name)
    hub.bump()
    return hub
```

---

### 3. `skills/skill_sbvr.md` — Novo Prompt com Esferas

**Localização:** `skills/skill_sbvr.md` (substituir conteúdo)

```markdown
# Papel: Especialista OMG SBVR com Contexto Multi-Esfera

Você é um analista de negócios especializado em SBVR (Semantics of Business Vocabulary and Rules). Sua tarefa é extrair regras de negócio de transcrições de reuniões, identificando não apenas a lógica, mas também **qual esfera do negócio** cada regra pertence.

## Esferas do Negócio (Business Spheres)

| Esfera | Descrição | Dono Típico |
|--------|-----------|--------------|
| `marketing` | Campanhas, público-alvo, branding, comunicação | CMO |
| `financeiro` | Orçamento, aprovação de verba, custos, receita | CFO |
| `rh` | Contratação, onboarding, avaliação, benefícios | CHRO |
| `operacoes` | Processos diários, logística, qualidade, estoque | COO |
| `juridico` | Contratos, compliance, LGPD, termos de uso | CLO |
| `tecnologia` | Infraestrutura, segurança, arquitetura, dados | CTO |
| `geral` | Transversal, políticas corporativas | CEO |

## Formato de Saída

Retorne um JSON estritamente válido:

```json
{
  "vocabulary": [
    {
      "term": "Público-alvo",
      "definition": "Segmento de clientes que uma campanha de marketing visa atingir",
      "sphere": "marketing"
    }
  ],
  "rules": [
    {
      "rule_id": "BR-001",
      "structural_fact": "Campanha → tem → Público-alvo",
      "operational_restriction": "É proibido criar uma campanha sem um público-alvo definido",
      "sphere": "marketing",
      "sphere_owner": "CMO",
      "bmm_policy_ref": null,
      "speaker_quote": "Toda campanha tem que ter um público-alvo, senão não sai do papel. — Joana (Marketing)"
    }
  ]
}
```

## Regras de Extração

1. **Separe fato estrutural de restrição operacional** — o fato é a verdade do negócio; a restrição é o que não pode acontecer.
2. **Identifique a esfera** pelo contexto da fala:
   - "orçamento", "verba", "custo" → `financeiro`
   - "campanha", "cliente", "público" → `marketing`
   - "contrato", "cláusula", "LGPD" → `juridico`
3. **Preserve a citação original** em `speaker_quote` com o nome do falante, se disponível.
4. **Conecte com BMM** se a transcrição mencionar políticas ou estratégias corporativas.
5. **Regras sem esfera clara** → use `geral` e dono `CEO`.

## Exemplo de Transcrição

> "No marketing, a política é clara: não pode lançar campanha sem aprovação do financeiro. E o financeiro só aprova se tiver orçamento reservado."

**Saída esperada:**

```json
{
  "rules": [
    {
      "rule_id": "BR-001",
      "structural_fact": "Campanha → depende de → Aprovação do Financeiro",
      "operational_restriction": "É proibido lançar campanha sem aprovação do financeiro",
      "sphere": "marketing",
      "sphere_owner": "CMO",
      "bmm_policy_ref": null,
      "speaker_quote": "não pode lançar campanha sem aprovação do financeiro"
    },
    {
      "rule_id": "BR-002",
      "structural_fact": "Aprovação Financeira → exige → Orçamento Reservado",
      "operational_restriction": "É proibido aprovar financeiramente uma campanha sem orçamento reservado",
      "sphere": "financeiro",
      "sphere_owner": "CFO",
      "bmm_policy_ref": null,
      "speaker_quote": "financeiro só aprova se tiver orçamento reservado"
    }
  ]
}
```
```

---

### 4. `agents/agent_requirements.py` — Rastreabilidade para SBVR

**Localização:** Método `run()` e `build_prompt()`

**O que fazer:** Adicionar instrução para vincular requisitos a regras SBVR

```python
# Em build_prompt(), adicionar regras SBVR como contexto
def build_prompt(self, hub, output_language="Auto-detect") -> tuple[str, str]:
    base_prompt = self._load_skill()  # SKILL_REQUIREMENTS.md
    
    # Adicionar regras SBVR disponíveis para rastreamento
    sbvr_context = ""
    if hub.sbvr and hub.sbvr.rules:
        rules_summary = "\n".join([
            f"- {rule.rule_id}: {rule.operational_restriction or rule.structural_fact} (Esfera: {rule.sphere})"
            for rule in hub.sbvr.rules[:10]
        ])
        sbvr_context = f"""
## Regras de Negócio (SBVR) que este sistema/processo deve realizar

As seguintes regras de negócio foram identificadas e DEVEM ser realizadas por requisitos funcionais:

{rules_summary}

Para cada requisito que você extrair, indique quais regras SBVR ele realiza usando o campo `business_rule_refs`.
"""
    
    system = base_prompt + sbvr_context
    user = f"""
Extraia requisitos funcionais da transcrição abaixo.
Idioma de saída: {output_language}

Transcrição:
{hub.transcript_clean[:15000]}
"""
    return system, user

# Em run(), atualizar o parser para incluir business_rule_refs
def run(self, hub, output_language="Auto-detect") -> KnowledgeHub:
    system, user = self.build_prompt(hub, output_language)
    data = self._call_with_retry(system, user, hub)
    
    if "requirements" in data:
        parsed_reqs = []
        for req_data in data["requirements"]:
            # Mapear regras de negócio mencionadas
            rule_refs = req_data.get("business_rule_refs", [])
            
            # Se o requisito mencionar "regra BR-XXX" no texto, extrair automaticamente
            import re
            found_rules = re.findall(r'BR-(\d{3})', req_data.get("description", ""))
            for br_id in found_rules:
                full_id = f"BR-{br_id}"
                if full_id not in rule_refs:
                    rule_refs.append(full_id)
            
            parsed_reqs.append(RequirementItem(
                id=req_data.get("id", f"REQ-{len(parsed_reqs)+1:03d}"),
                title=req_data.get("title", ""),
                description=req_data.get("description", ""),
                priority=req_data.get("priority", "media"),
                status=req_data.get("status", "proposto"),
                business_rule_refs=rule_refs,
                sphere=req_data.get("sphere")  # Pode herdar da regra mais relevante
            ))
        
        hub.requirements.items = parsed_reqs
    
    hub.mark_agent_run(self.name)
    hub.bump()
    return hub
```

---

### 5. `agents/orchestrator.py` — Reordenar Execução

**Localização:** Método `run()` — ajustar a ordem dos agentes

**O que fazer:** Mover SBVR para antes de Requirements

```python
# Localizar a sequência atual (aproximadamente linha 80-120)
# Substituir a ordem:

# ORDEM ATUAL (ERRADA):
# - AgentMinutes (paralelo com Requirements)
# - AgentRequirements
# - AgentSBVR
# - AgentBMM

# ORDEM CORRETA (MULTI-ESFERA):
def _get_agent_sequence(self, config):
    """Retorna a ordem de execução respeitando dependências"""
    sequence = []
    
    # 1. Qualidade da transcrição (sempre primeiro)
    if config.get("run_quality", True):
        sequence.append(AgentTranscriptQuality)
    
    # 2. BPMN (processo base, independente)
    if config.get("run_bpmn", True):
        sequence.append(AgentBPMN)
    
    # 3. SBVR (regras de negócio com esferas) — AGORA ANTES DOS REQUISITOS
    if config.get("run_sbvr", False):
        sequence.append(AgentSBVR)
    
    # 4. Requirements (requisitos que realizam as regras SBVR)
    if config.get("run_requirements", True):
        sequence.append(AgentRequirements)
    
    # 5. Minutes (atas capturam decisões, pode usar regras já extraídas)
    if config.get("run_minutes", True):
        sequence.append(AgentMinutes)
    
    # 6. BMM (estratégia, políticas — alimenta SBVR na próxima execução)
    if config.get("run_bmm", False):
        sequence.append(AgentBMM)
    
    # 7. Synthesizer (relatório final)
    if config.get("run_synthesizer", False):
        sequence.append(AgentSynthesizer)
    
    return sequence
```

**Nota:** O `AgentMinutes` e `AgentRequirements` não rodam mais em paralelo (pois Requirements agora depende do SBVR). Isso é aceitável porque o ganho de rastreabilidade justifica a perda de paralelismo.

---

### 6. `modules/executive_html.py` — Relatório com Esferas

**Localização:** Método `generate_html()` — seção de SBVR e Requisitos

**O que fazer:** Agrupar regras por esfera e mostrar badges de rastreabilidade

```python
# Dentro de generate_html(), localizar a seção de SBVR (aprox. linha 200-250)

def generate_html(self, hub: KnowledgeHub) -> str:
    # ... código existente ...
    
    # --- SEÇÃO SBVR POR ESFERA ---
    sbvr_html = ""
    if hub.sbvr and hub.sbvr.rules:
        # Agrupar regras por esfera
        rules_by_sphere = {}
        for rule in hub.sbvr.rules:
            sphere = rule.sphere
            if sphere not in rules_by_sphere:
                rules_by_sphere[sphere] = []
            rules_by_sphere[sphere].append(rule)
        
        # Cores por esfera
        sphere_colors = {
            "marketing": "#FF6B6B", "financeiro": "#4ECDC4", "rh": "#45B7D1",
            "operacoes": "#96CEB4", "juridico": "#FFEAA7", "tecnologia": "#DDA0DD",
            "geral": "#95A5A6"
        }
        
        sbvr_html = "<div class='sbvr-spheres'>"
        for sphere, rules in rules_by_sphere.items():
            color = sphere_colors.get(sphere, "#95A5A6")
            sbvr_html += f"""
            <div class='sphere-card' style='border-left: 4px solid {color}; margin-bottom: 20px; padding: 15px; background: #f9f9f9;'>
                <h3 style='color: {color}; margin-top: 0;'>
                    🎯 {sphere.upper()} 
                    <span style='font-size: 14px; color: #666;'>({len(rules)} regras)</span>
                </h3>
                <ul>
            """
            for rule in rules:
                sbvr_html += f"""
                    <li>
                        <strong>{rule.rule_id}</strong>: {rule.operational_restriction or rule.structural_fact}
                        <br><span style='font-size: 12px; color: #888;'>Dono: {rule.sphere_owner}</span>
                        {f"<br><span style='font-size: 11px; color: #aaa;'>Citação: \"{rule.speaker_quote[:100]}\"</span>" if rule.speaker_quote else ""}
                    </li>
                """
            sbvr_html += "</ul></div>"
        sbvr_html += "</div>"
    
    # --- SEÇÃO REQUISITOS COM BADGES ---
    req_html = ""
    if hub.requirements and hub.requirements.items:
        req_html = "<table class='requirements-table'>"
        req_html += "<tr><th>ID</th><th>Título</th><th>Regras de Negócio</th><th>Esfera</th><th>Prioridade</th></tr>"
        for req in hub.requirements.items:
            badges = ""
            for br_ref in req.business_rule_refs[:3]:  # Limite de 3 badges
                # Encontrar a esfera da regra para cor do badge
                sphere = "geral"
                if hub.sbvr and hub.sbvr.rules:
                    matching_rule = next((r for r in hub.sbvr.rules if r.rule_id == br_ref), None)
                    if matching_rule:
                        sphere = matching_rule.sphere
                badge_color = sphere_colors.get(sphere, "#95A5A6")
                badges += f"<span style='background: {badge_color}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 11px; margin-right: 5px;'>{br_ref}</span>"
            
            req_html += f"""
            <tr>
                <td>{req.id}</td>
                <td>{req.title}</td>
                <td>{badges or '—'}</td>
                <td>{req.sphere or '—'}</td>
                <td><span class='priority-{req.priority}'>{req.priority}</span></td>
            </tr>
            """
        req_html += "</table>"
    
    # Injetar no HTML final (substituir as seções antigas)
    # Localizar <!-- SBVR SECTION --> e <!-- REQUIREMENTS SECTION --> no template
    html = html.replace("<!-- SBVR_SECTION -->", sbvr_html)
    html = html.replace("<!-- REQUIREMENTS_SECTION -->", req_html)
    
    return html
```

---

### 7. `ui/tabs/sbvr_tab.py` — Visualização Interativa por Esfera

**Localização:** Função `render_sbvr_tab()`

**O que fazer:** Adicionar filtro por esfera e métricas

```python
def render_sbvr_tab(hub: KnowledgeHub):
    """Renderiza SBVR com filtro por esfera"""
    st.subheader("📋 Regras de Negócio (SBVR)")
    
    if not hub.sbvr or not hub.sbvr.rules:
        st.info("Nenhuma regra de negócio extraída. Ative o agente SBVR nas configurações.")
        return
    
    # Métricas por esfera
    rules = hub.sbvr.rules
    spheres = list(set(r.sphere for r in rules))
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total de Regras", len(rules))
    with col2:
        st.metric("Esferas", len(spheres))
    with col3:
        st.metric("Regras com Dono", sum(1 for r in rules if r.sphere_owner and r.sphere_owner != "CEO"))
    with col4:
        # Contar quantas regras são realizadas por requisitos
        realized = sum(1 for r in rules if any(
            r.rule_id in req.business_rule_refs 
            for req in hub.requirements.items
        )) if hub.requirements else 0
        st.metric("Realizadas por Requisitos", f"{realized}/{len(rules)}")
    
    # Filtro por esfera
    selected_sphere = st.selectbox("Filtrar por Esfera", ["Todas"] + spheres)
    
    filtered_rules = [r for r in rules if selected_sphere == "Todas" or r.sphere == selected_sphere]
    
    # Exibir regras em expansores por esfera
    if selected_sphere == "Todas":
        for sphere in spheres:
            sphere_rules = [r for r in rules if r.sphere == sphere]
            with st.expander(f"🎯 {sphere.upper()} ({len(sphere_rules)} regras)"):
                for rule in sphere_rules:
                    st.markdown(f"""
                    **{rule.rule_id}** — {rule.operational_restriction or rule.structural_fact}
                    - 👤 Dono: {rule.sphere_owner}
                    - 💬 Citação: "{rule.speaker_quote[:150]}{'...' if len(rule.speaker_quote) > 150 else ''}"
                    """)
                    # Mostrar requisitos vinculados
                    if hub.requirements:
                        linked_reqs = [req.id for req in hub.requirements.items if rule.rule_id in req.business_rule_refs]
                        if linked_reqs:
                            st.caption(f"🔗 Realizado por: {', '.join(linked_reqs)}")
                    st.divider()
    else:
        for rule in filtered_rules:
            st.markdown(f"""
            **{rule.rule_id}** — {rule.operational_restriction or rule.structural_fact}
            - 👤 Dono: {rule.sphere_owner}
            - 💬 Citação: "{rule.speaker_quote[:150]}{'...' if len(rule.speaker_quote) > 150 else ''}"
            """)
```

---

### 8. `core/rerun_handlers.py` — Suporte para Re-execução com Dependências

**Localização:** Função `handle_rerun()`

**O que fazer:** Garantir que re-run de SBVR invalide Requirements

```python
def handle_rerun(agent_name: str, hub: KnowledgeHub, config: dict) -> KnowledgeHub:
    """Re-executa um agente específico, respeitando dependências"""
    
    if agent_name == "sbvr":
        # Re-executa SBVR
        from agents.agent_sbvr import AgentSBVR
        hub = AgentSBVR().run(hub, config.get("output_language", "Auto-detect"))
        
        # ⚠️ INVALIDA REQUISITOS (pois regras mudaram)
        if hub.requirements:
            st.session_state["_sbvr_changed"] = True
            hub.requirements = RequirementsModel(items=[])  # Limpa requisitos
            st.warning("Regras SBVR foram atualizadas. Requisitos serão re-extraídos na próxima execução completa.")
        
    elif agent_name == "requirements":
        # Verifica se SBVR existe antes de re-executar
        if not hub.sbvr or not hub.sbvr.rules:
            st.warning("⚠️ Execute o agente SBVR primeiro para obter regras de negócio.")
            return hub
        
        from agents.agent_requirements import AgentRequirements
        hub = AgentRequirements().run(hub, config.get("output_language", "Auto-detect"))
    
    # ... resto do código existente ...
    
    return hub
```

---

## Testes para Validar a Implementação

### Teste 1: Extração Multi-Esfera

**Entrada (transcrição simulada):**
```
Joana (Marketing): No marketing, toda campanha precisa ter um público-alvo definido.
Carlos (Financeiro): E nenhuma campanha pode ser aprovada sem orçamento reservado. Isso é regra.
```

**Esperado:**
- BR-001: Esfera `marketing`, Dono `CMO`
- BR-002: Esfera `financeiro`, Dono `CFO`

### Teste 2: Rastreabilidade

**Entrada (requisitos gerados a partir das regras):**
- REQ-001: "Sistema deve exigir seleção de público-alvo ao criar campanha" → `business_rule_refs: ["BR-001"]`
- REQ-002: "Workflow de aprovação deve verificar reserva orçamentária" → `business_rule_refs: ["BR-002"]`

**Esperado:** Badges no relatório HTML mostrando "Baseado em BR-001 (Marketing)"

### Teste 3: Re-execução com Invalidação

**Cenário:** 
1. Executar pipeline completo (SBVR → Requirements)
2. Re-executar apenas SBVR com nova regra
3. Verificar se `hub.requirements` foi limpo e aviso exibido

---

## Critérios de Aceite

- [ ] `KnowledgeHub.sbvr.rules` contém `sphere`, `sphere_owner`, `bmm_policy_ref`
- [ ] `KnowledgeHub.requirements.items` contém `business_rule_refs`
- [ ] Orquestrador executa SBVR antes de Requirements
- [ ] Relatório HTML agrupa regras por esfera com cores distintas
- [ ] Badges nos requisitos mostram `BR-XXX` com cor da esfera correspondente
- [ ] `sbvr_tab.py` tem filtro por esfera e métricas de realização
- [ ] Re-execução de SBVR invalida Requirements automaticamente
- [ ] Compatibilidade retroativa com SBVR antigo (lista de strings) via `migrate()`
- [ ] Nenhum erro de importação circular entre agentes

---

## Execução no Claude Code

Cole este prompt no terminal do Claude Code dentro do PyCharm:

```
Implemente a proposta de melhoria "Multi-Esfera para SBVR + Rastreabilidade entre Regras e Requisitos" conforme o arquivo markdown fornecido.

Priorize:
1. Modificações em core/knowledge_hub.py (modelos)
2. Atualização de skills/skill_sbvr.md (novo prompt)
3. agents/agent_sbvr.py (parser com esfera)
4. agents/orchestrator.py (reordenação)

Após implementar, execute os testes de validação descritos na seção "Testes para Validar a Implementação" e reporte os resultados.
```

---

## Observações Finais

1. **Não há necessidade de novas dependências** — tudo usa bibliotecas já presentes (re para regex, dataclasses).
2. **Backcompat garantida** via campo `rule_facts` existente no SBVRModel.
3. **Escalável** para novas esferas — basta adicionar à lista `valid_spheres`.
4. **Integração com BMM** já prevista via `bmm_policy_ref`.

Esta melhoria torna o Process2Diagram um sistema verdadeiramente **multi-esfera**, alinhado com as práticas OMG de governança empresarial.
```

---

Este documento está pronto para ser colado diretamente no Claude Code. Ele contém:

1. **Objetivo claro** e contexto
2. **Arquivos específicos** com localizações aproximadas
3. **Código exato** para cada modificação
4. **Testes** para validação
5. **Comando final** para execução no Claude Code
