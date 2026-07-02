# core/tools/tools_executive_advanced.py
# Auto-extracted from core/assistant_tools.py (split PC115) — mixin for AssistantToolExecutor.
# Methods here assume `self` is an AssistantToolExecutor instance (project_id, llm_config,
# _meeting_cache, _pending_charts, _palette — set in AssistantToolExecutor.__init__).

from __future__ import annotations
import re
from core.chart_config import CHART_PALETTES, DEFAULT_PALETTE
from core.tools._shared import _compute_initials


EXECUTIVE_ADVANCED_SCHEMAS: list[dict] = [
            {
                "type": "function",
                "function": {
                    "name": "reordenar_requisitos",
                    "description": (
                        "Reordena os requisitos do projeto atualizando o campo sort_order. "
                        "Pode receber uma nova ordem explícita (lista de IDs como ['REQ-003','REQ-001']) "
                        "ou um critério de agrupamento ('tipo' ou 'prioridade'). "
                        "Use quando o usuário pedir para reorganizar, priorizar ou agrupar requisitos."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "nova_ordem": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": (
                                    "Lista explícita de identificadores de requisitos na nova ordem "
                                    "(ex: ['REQ-003','REQ-001','REQ-002']). "
                                    "Mutuamente exclusivo com agrupar_por."
                                ),
                            },
                            "agrupar_por": {
                                "type": "string",
                                "enum": ["tipo", "prioridade"],
                                "description": (
                                    "Reagrupa automaticamente todos os requisitos por tipo (Funcional → "
                                    "Não Funcional → Regra de Negócio) ou por prioridade (Crítico → Alto → "
                                    "Médio → Baixo). Mutuamente exclusivo com nova_ordem."
                                ),
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "inserir_secao_ata",
                    "description": (
                        "Insere uma nova seção (## Título) na ata de uma reunião. "
                        "Posição pode ser 'inicio', 'fim', 'antes_decisoes', 'apos_participantes' "
                        "ou qualquer nome de seção existente prefixado com 'antes_' ou 'apos_'. "
                        "Use quando o usuário pedir para adicionar seção, acrescentar riscos, "
                        "inserir observações ou enriquecer uma ata existente."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "meeting_number": {
                                "type": "integer",
                                "description": "Número da reunião cuja ata será editada.",
                            },
                            "titulo": {
                                "type": "string",
                                "description": "Título da nova seção (sem ##, ex: 'Riscos Identificados').",
                            },
                            "conteudo": {
                                "type": "string",
                                "description": "Conteúdo Markdown da nova seção.",
                            },
                            "posicao": {
                                "type": "string",
                                "description": (
                                    "Onde inserir: 'inicio', 'fim' (padrão), 'antes_decisoes', "
                                    "'apos_participantes' ou qualquer 'antes_<nome>' / 'apos_<nome>'."
                                ),
                            },
                        },
                        "required": ["meeting_number", "titulo", "conteudo"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "vincular_regra_debate",
                    "description": (
                        "Cria um vínculo entre uma regra SBVR e uma questão IBIS, registrando "
                        "a relação semântica entre elas (justifica, contradiz ou limita). "
                        "Use quando o usuário pedir para ligar uma regra a um debate, "
                        "vincular SBVR a IBIS ou documentar a justificativa de uma regra."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "rule_id": {
                                "type": "string",
                                "description": "Identificador da regra SBVR (ex: 'RN-012').",
                            },
                            "ibis_question_id": {
                                "type": "string",
                                "description": "Identificador da questão IBIS (ex: 'Q-042').",
                            },
                            "relacao": {
                                "type": "string",
                                "enum": ["justifica", "contradiz", "limita"],
                                "description": "Tipo de relação: justifica (padrão), contradiz ou limita.",
                            },
                        },
                        "required": ["rule_id", "ibis_question_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mesclar_reunioes",
                    "description": (
                        "Mescla duas reuniões: transfere todos os artefatos (requisitos, SBVR, BPMN, "
                        "transcrição, ata) da reunião absorvida para a reunião mantida, concatena as atas "
                        "e exclui a reunião absorvida. "
                        "Use preview=true para ver o impacto antes de confirmar. "
                        "Use quando o usuário pedir para unir, combinar ou mesclar duas reuniões."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "manter_meeting": {
                                "type": "integer",
                                "description": "Número da reunião que será mantida (destinatária dos artefatos).",
                            },
                            "absorver_meeting": {
                                "type": "integer",
                                "description": "Número da reunião que será absorvida e excluída.",
                            },
                            "razao": {
                                "type": "string",
                                "description": "Motivo da mesclagem (registrado na ata combinada).",
                            },
                            "preview": {
                                "type": "boolean",
                                "description": "Se true, retorna preview sem executar. Padrão: true (segurança).",
                            },
                        },
                        "required": ["manter_meeting", "absorver_meeting"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "mapa_rastreabilidade",
                    "description": (
                        "Gera um mapa de rastreabilidade para um requisito ou tema, mostrando "
                        "as conexões com falas na transcrição, passos do BPMN, regras SBVR e "
                        "debates IBIS. Use quando o usuário pedir 'de onde veio esse requisito', "
                        "'qual parte da transcrição originou a regra X', 'rastreabilidade de REQ-042' "
                        "ou 'onde esse tema é discutido'."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "req_number": {
                                "type": "integer",
                                "description": "Número do requisito (ex: 42 para REQ-042). Mutuamente exclusivo com topic.",
                            },
                            "topic": {
                                "type": "string",
                                "description": "Tema para busca por palavra-chave (ex: 'autenticação biométrica'). Mutuamente exclusivo com req_number.",
                            },
                            "include_transcript": {
                                "type": "boolean",
                                "description": "Incluir falas da transcrição. Padrão: true.",
                            },
                            "include_bpmn": {
                                "type": "boolean",
                                "description": "Incluir processos BPMN relacionados. Padrão: true.",
                            },
                            "include_sbvr": {
                                "type": "boolean",
                                "description": "Incluir regras SBVR relacionadas. Padrão: true.",
                            },
                            "include_ibis": {
                                "type": "boolean",
                                "description": "Incluir debates IBIS relacionados. Padrão: true.",
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "simular_cenario",
                    "description": (
                        "Simula o impacto de uma mudança de decisão ou escopo no projeto. "
                        "Analisa os requisitos afetados, dependências implícitas, regras SBVR a "
                        "revisar, riscos e retorna uma recomendação. "
                        "Use quando o usuário perguntar 'e se movermos X para Fase 2?', "
                        "'o que acontece se removermos REQ-042?', 'impacto de mudar Y', "
                        "'simule o cenário onde...' ou qualquer análise de mudança hipotética."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "descricao": {
                                "type": "string",
                                "description": "Descrição do cenário ou mudança proposta em linguagem natural.",
                            },
                            "requisitos_afetados": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Lista de IDs de requisitos afetados (ex: ['REQ-042','REQ-043']). Opcional — se omitido, o sistema infere pelos keywords.",
                            },
                            "restricoes": {
                                "type": "object",
                                "description": "Restrições do projeto como objeto JSON (ex: {\"prazo\": \"6 meses\", \"equipe\": \"4 devs\"}).",
                            },
                        },
                        "required": ["descricao"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "verificar_conformidade",
                    "description": (
                        "Verifica se os requisitos do projeto estão cobertos pelos documentos da "
                        "biblioteca (BRDs, contratos, especificações). Retorna um relatório de "
                        "cobertura com gaps e ações recomendadas. "
                        "Use quando o usuário pedir 'nossos requisitos cobrem o BRD?', "
                        "'há gaps no contrato?', 'conformidade com documento X', "
                        "'quais cláusulas não estão mapeadas' ou análise de aderência."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "doc_id": {
                                "type": "string",
                                "description": "ID de um documento específico para analisar. Se omitido, analisa todos os documentos do projeto.",
                            },
                            "req_type_filter": {
                                "type": "string",
                                "description": "Filtrar por tipo de requisito: 'Funcional', 'Não Funcional' ou 'Regra de Negócio'.",
                            },
                            "threshold": {
                                "type": "number",
                                "description": "Limiar de similaridade para considerar coberto (0–1). Padrão: 0.75.",
                            },
                            "mode": {
                                "type": "string",
                                "enum": ["keyword", "llm"],
                                "description": "Modo de análise: 'keyword' (rápido, padrão) ou 'llm' (LLM para cobertura semântica profunda).",
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gerar_deck_executivo",
                    "description": (
                        "Gera um deck executivo completo (Markdown) consolidando todos os "
                        "artefatos do projeto: visão/missão (BMM), métricas, requisitos, "
                        "processos BPMN, ROI-TR, pendências e recomendações. "
                        "Use quando o usuário pedir 'gere uma apresentação', 'preciso de um "
                        "deck para o comitê', 'resumo executivo do projeto', 'prepare slides'."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "incluir_secoes": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": (
                                    "Seções a incluir. Padrão: todas. Opções: 'resumo_executivo', "
                                    "'metricas_principais', 'evolucao_requisitos', 'processos_bpmn', "
                                    "'indicadores_roi', 'pendencias', 'recomendacoes'."
                                ),
                            },
                            "meeting_numbers": {
                                "type": "array",
                                "items": {"type": "integer"},
                                "description": "Reuniões a incluir. Padrão: todas.",
                            },
                            "tema_cores": {
                                "type": "string",
                                "enum": ["corporativo", "moderno", "clean"],
                                "description": "Estilo visual. Padrão: 'corporativo'.",
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "gerar_project_charter",
                    "description": (
                        "Gera um Project Charter formal em Markdown consolidando todos os "
                        "artefatos: visão, missão, stakeholders, escopo (requisitos), "
                        "processos BPMN, regras SBVR, riscos (contradições), cronograma "
                        "(datas das reuniões + encaminhamentos). "
                        "Use quando o usuário pedir 'gere o Project Charter', 'crie o documento "
                        "de abertura do projeto', 'preciso de um term of reference', 'PDD do projeto'."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "incluir_riscos": {
                                "type": "boolean",
                                "description": "Incluir seção de riscos baseada em contradições abertas. Padrão: true.",
                            },
                            "incluir_cronograma": {
                                "type": "boolean",
                                "description": "Incluir cronograma inferido das datas de reunião e encaminhamentos. Padrão: true.",
                            },
                            "incluir_stakeholders": {
                                "type": "boolean",
                                "description": "Incluir seção de stakeholders extraídos das atas. Padrão: true.",
                            },
                            "incluir_escopo": {
                                "type": "boolean",
                                "description": "Incluir breakdown do escopo por tipo de requisito. Padrão: true.",
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sincronizar_calendario",
                    "description": (
                        "Sincroniza os encaminhamentos (itens de ação) das atas com o Google Calendar. "
                        "Direção 'to_calendar': cria eventos para cada encaminhamento sem evento. "
                        "Direção 'from_calendar': atualiza status dos itens já sincronizados. "
                        "Direção 'bidirectional': ambas. "
                        "Use quando o usuário pedir para agendar tarefas, sincronizar calendário "
                        "ou criar eventos a partir dos encaminhamentos das reuniões."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "direction": {
                                "type": "string",
                                "enum": ["to_calendar", "from_calendar", "bidirectional"],
                                "description": "Direção da sincronização. Padrão: 'to_calendar'.",
                            },
                            "meeting_number": {
                                "type": "integer",
                                "description": "Reunião específica (opcional — padrão: todas as reuniões).",
                            },
                            "default_duration": {
                                "type": "integer",
                                "description": "Duração em minutos para cada evento criado. Padrão: 30.",
                            },
                            "default_work_start": {
                                "type": "string",
                                "description": "Horário de início da janela de trabalho no formato HH:MM. Padrão: '09:00'.",
                            },
                            "default_work_end": {
                                "type": "string",
                                "description": "Horário de fim da janela de trabalho no formato HH:MM. Padrão: '18:00'.",
                            },
                        },
                        "required": [],
                    },
                },
            },
]

class _ExecutiveAdvancedToolsMixin:
    """Mixin: tools_executive_advanced tools."""

    def _llm_call(self, system: str, user: str, max_tokens: int = 3000) -> str:
        """Shared LLM call helper used by gerar_deck_executivo and gerar_project_charter."""
        provider_cfg = self.llm_config.get("provider_cfg", {})
        api_key      = self.llm_config.get("api_key", "")
        model        = self.llm_config.get("model", "deepseek-v4-flash")
        client_type  = provider_cfg.get("client_type", "openai_compatible")

        if client_type == "anthropic":
            import anthropic as _ant
            ac  = _ant.Anthropic(api_key=api_key)
            msg = ac.messages.create(
                model=model, max_tokens=max_tokens, system=system,
                messages=[{"role": "user", "content": user}],
            )
            return (msg.content[0].text or "").strip()
        else:
            from openai import OpenAI as _OAI
            client = _OAI(api_key=api_key, base_url=provider_cfg.get("base_url"))
            kwargs: dict = dict(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                max_tokens=max_tokens,
            )
            if not provider_cfg.get("reasoning_effort") and "deepseek-v4" not in model.lower():
                kwargs["temperature"] = 0.35
            return (client.chat.completions.create(**kwargs).choices[0].message.content or "").strip()

    def gerar_deck_executivo(
        self,
        incluir_secoes: list | None = None,
        meeting_numbers: list | None = None,
        tema_cores: str = "corporativo",
    ) -> str:
        """Generate a Markdown executive deck from all project artifacts."""
        meetings = self._get_meetings()
        if meeting_numbers:
            meetings = [m for m in meetings if m.get("meeting_number") in meeting_numbers]
        if not meetings:
            return "Nenhuma reunião encontrada para gerar o deck executivo."

        bmm  = self.get_bmm()
        ckf  = self.get_ckf()
        bpmn = self.list_bpmn_processes()
        roi  = self.calculate_meeting_roi()

        try:
            from modules.supabase_client import get_supabase_client
            db = get_supabase_client()
            reqs = (
                db.table("requirements")
                .select("req_type, priority, status")
                .eq("project_id", self.project_id)
                .execute().data or []
            ) if db else []
        except Exception:
            reqs = []

        n_reqs   = len(reqs)
        n_func   = sum(1 for r in reqs if r.get("req_type") == "Funcional")
        n_nf     = sum(1 for r in reqs if r.get("req_type") == "Não Funcional")
        n_rn     = sum(1 for r in reqs if r.get("req_type") == "Regra de Negócio")
        n_crit   = sum(1 for r in reqs if r.get("priority") == "Crítico")
        n_active = sum(1 for r in reqs if (r.get("status") or "").lower() == "active")

        actions: list[str] = []
        for m in meetings:
            ai = self._section(m.get("minutes_md") or "", "Itens de Ação", "Action Items", "Ações")
            if ai:
                actions.append(f"Reunião {m.get('meeting_number')}: {ai[:150]}")

        bmm_ctx  = bmm[:1500]  if "não encontrad" not in bmm.lower()  else "(não disponível)"
        ckf_ctx  = ckf[:600]   if "não encontrad" not in ckf.lower()  else "(não disponível)"
        bpmn_ctx = bpmn[:600]
        roi_ctx  = roi[:600]
        ai_ctx   = "\n".join(actions[:4]) or "(nenhum)"

        sections = incluir_secoes or [
            "resumo_executivo", "metricas_principais", "evolucao_requisitos",
            "processos_bpmn", "indicadores_roi", "pendencias", "recomendacoes",
        ]

        system = (
            "Você é especialista em apresentações executivas. "
            "Gere um deck executivo em Markdown estruturado. "
            "Cada slide começa com ## (H2). Bullet points concisos, máx 5 por slide. "
            "Tom formal e objetivo. Responda em Português do Brasil."
        )
        user = (
            f"Gere um deck executivo de {len(sections)} slides para um projeto de software.\n\n"
            f"**Dados:**\n"
            f"- Reuniões: {len(meetings)} | Requisitos: {n_reqs} "
            f"({n_func} Func / {n_nf} NF / {n_rn} RN) | Críticos: {n_crit} | Ativos: {n_active}\n\n"
            f"**BMM (Visão/Missão/Objetivos):**\n{bmm_ctx}\n\n"
            f"**Processos BPMN:**\n{bpmn_ctx}\n\n"
            f"**ROI-TR das reuniões:**\n{roi_ctx}\n\n"
            f"**CKF (Contexto estratégico):**\n{ckf_ctx}\n\n"
            f"**Encaminhamentos pendentes:**\n{ai_ctx}\n\n"
            f"**Seções solicitadas:** {', '.join(sections)}\n\n"
            "**Slides obrigatórios:**\n"
            "1. ## 🎯 Visão Geral — visão, missão, objetivo central\n"
            "2. ## 📊 Métricas Principais — KPIs quantitativos\n"
            "3. ## 📋 Análise de Requisitos — breakdown e cobertura\n"
            "4. ## ⚙️ Processos de Negócio — processos BPMN modelados\n"
            "5. ## 📈 Qualidade das Reuniões — ROI-TR resumido\n"
            "6. ## ⚠️ Pendências — encaminhamentos em aberto\n"
            "7. ## 🚀 Próximos Passos — 3-5 ações priorizadas\n\n"
            "Máx 5 bullets por slide. Total aprox. 400 palavras."
        )

        try:
            deck = self._llm_call(system, user, max_tokens=3000)
        except Exception as exc:
            return f"❌ Erro ao gerar deck executivo: {exc}"

        return f"# 📊 Deck Executivo — Process2Diagram\n\n{deck}"

    def gerar_project_charter(
        self,
        incluir_riscos: bool = True,
        incluir_cronograma: bool = True,
        incluir_stakeholders: bool = True,
        incluir_escopo: bool = True,
    ) -> str:
        """Generate a formal project charter in Markdown from all project artifacts."""
        meetings = self._get_meetings()
        if not meetings:
            return "Nenhuma reunião encontrada no projeto para gerar o Project Charter."

        bmm  = self.get_bmm()
        ckf  = self.get_ckf()
        bpmn = self.list_bpmn_processes()

        try:
            from modules.supabase_client import get_supabase_client
            db = get_supabase_client()
            reqs = (
                db.table("requirements")
                .select("req_number, title, description, req_type, priority, status")
                .eq("project_id", self.project_id)
                .order("req_number")
                .execute().data or []
            ) if db else []
        except Exception:
            reqs = []

        try:
            from core.project_store import list_sbvr_rules
            rules = list_sbvr_rules(self.project_id)[:8]
        except Exception:
            rules = []

        try:
            from core.knowledge_store import get_contradictions
            contras = get_contradictions(self.project_id, status="open", limit=8)
        except Exception:
            contras = []

        participants: list[str] = []
        action_items: list[str] = []
        dates: list[str] = []
        for m in meetings:
            md = m.get("minutes_md") or ""
            p  = self._section(md, "Participantes")
            if p:
                participants.append(f"Reunião {m.get('meeting_number')}: {p[:200]}")
            ai = self._section(md, "Itens de Ação", "Action Items", "Ações")
            if ai:
                action_items.append(f"Reunião {m.get('meeting_number')}: {ai[:200]}")
            dt = m.get("meeting_date")
            if dt:
                dates.append(str(dt)[:10])

        n_reqs = len(reqs)
        n_func = sum(1 for r in reqs if r.get("req_type") == "Funcional")
        n_nf   = sum(1 for r in reqs if r.get("req_type") == "Não Funcional")
        n_rn   = sum(1 for r in reqs if r.get("req_type") == "Regra de Negócio")

        top_reqs_txt = "\n".join(
            f"  REQ-{r.get('req_number',0):03d} [{r.get('req_type','—')}/{r.get('priority','—')}]: "
            f"{r.get('title','')} — {(r.get('description') or '')[:80]}"
            for r in reqs[:15]
        ) or "(nenhum)"

        rules_txt  = "\n".join(f"  [{r.get('rule_id','')}] {r.get('statement','')}" for r in rules) or "(nenhuma)"
        contra_txt = "\n".join(f"  [{c.get('severity','—')}] {c.get('description','')[:100]}" for c in contras) or "(nenhuma)"
        parts_txt  = "\n".join(participants[:5]) or "(não disponível)"
        ai_txt     = "\n".join(action_items[:5]) or "(nenhum)"
        period     = f"{min(dates)} a {max(dates)}" if dates else "não disponível"
        bmm_ctx    = bmm[:2000] if "não encontrad" not in bmm.lower() else "(não disponível)"
        ckf_ctx    = ckf[:800]  if "não encontrad" not in ckf.lower() else "(não disponível)"

        optional = []
        if incluir_stakeholders:
            optional.append("5. ## 👥 Stakeholders")
        if incluir_escopo:
            optional.append("6. ## 📋 Escopo e Requisitos")
        if incluir_riscos:
            optional.append("8. ## ⚠️ Riscos e Restrições")
        if incluir_cronograma:
            optional.append("9. ## 📅 Cronograma e Próximos Passos")

        system = (
            "Você é especialista em gestão de projetos (PMO). "
            "Gere um Project Charter formal e completo em Markdown. "
            "Linguagem formal e profissional. Responda em Português do Brasil."
        )
        user = (
            f"Gere um Project Charter formal para um projeto de software.\n\n"
            f"**BMM (Visão/Missão/Objetivos/Estratégias/Políticas):**\n{bmm_ctx}\n\n"
            f"**CKF:**\n{ckf_ctx}\n\n"
            f"**Reuniões:** {len(meetings)} | **Período:** {period}\n\n"
            f"**Participantes:**\n{parts_txt}\n\n"
            f"**Requisitos:** {n_reqs} total ({n_func} Func / {n_nf} NF / {n_rn} RN)\n{top_reqs_txt}\n\n"
            f"**Processos BPMN:**\n{bpmn[:500]}\n\n"
            f"**Regras SBVR:**\n{rules_txt}\n\n"
            f"**Contradições em Aberto (Riscos):**\n{contra_txt}\n\n"
            f"**Encaminhamentos Pendentes:**\n{ai_txt}\n\n"
            "**Seções obrigatórias do charter:**\n"
            "1. ## 🎯 Identificação do Projeto\n"
            "2. ## 📌 Visão e Missão\n"
            "3. ## 🎯 Objetivos Estratégicos\n"
            "4. ## 🔭 Escopo (dentro / fora)\n"
            + ("\n".join(optional)) + "\n"
            "7. ## ⚙️ Processos de Negócio Mapeados\n"
            "10. ## 📜 Premissas e Restrições\n\n"
            "Linguagem formal de PMO. Máx 900 palavras."
        )

        try:
            charter = self._llm_call(system, user, max_tokens=3500)
        except Exception as exc:
            return f"❌ Erro ao gerar Project Charter: {exc}"

        return (
            f"# 📄 Project Charter\n\n"
            f"*Gerado pelo Process2Diagram — {len(meetings)} reunião(ões) | {n_reqs} requisitos*\n\n"
            "---\n\n"
            + charter
        )

    def mapa_rastreabilidade(
        self,
        req_number: int | None = None,
        topic: str | None = None,
        include_transcript: bool = True,
        include_bpmn: bool = True,
        include_sbvr: bool = True,
        include_ibis: bool = True,
    ) -> str:
        """Build a traceability map for a requirement or topic."""
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        if not req_number and not topic:
            return (
                "Informe `req_number` (número do requisito, ex: 42) "
                "ou `topic` (tema para busca, ex: 'autenticação biométrica')."
            )

        try:
            q = (
                db.table("requirements")
                .select("id, req_number, title, description, req_type, status, priority")
                .eq("project_id", self.project_id)
            )
            if req_number:
                q = q.eq("req_number", req_number)
            all_rows = q.order("req_number").execute().data or []
        except Exception as exc:
            return f"Erro ao buscar requisitos: {exc}"

        if topic and not req_number:
            kw = topic.lower()
            all_rows = [
                r for r in all_rows
                if kw in (r.get("title") or "").lower()
                or kw in (r.get("description") or "").lower()
            ][:5]

        if not all_rows:
            hint = f"REQ-{req_number:03d}" if isinstance(req_number, int) else f"'{topic}'"
            return f"Nenhum requisito encontrado para {hint}."

        lines = [
            "# 🔗 Mapa de Rastreabilidade",
            f"*{len(all_rows)} requisito(s) analisado(s)*\n",
        ]

        for r in all_rows[:5]:
            n      = r.get("req_number", "?")
            title  = r.get("title", "")
            desc   = r.get("description", "")
            rtype  = r.get("req_type", "—")
            prio   = r.get("priority", "—")
            req_id = f"REQ-{n:03d}" if isinstance(n, int) else f"REQ-{n}"

            lines += [
                f"---\n## 🔷 {req_id} — {title}",
                f"**Tipo:** {rtype} | **Prioridade:** {prio}",
            ]
            if desc:
                lines.append(f"**Descrição:** {desc[:200]}{'…' if len(desc) > 200 else ''}")
            lines.append("")

            # ── Transcript
            if include_transcript:
                try:
                    tr = self.search_transcript(query=title)
                    if not any(x in tr.lower() for x in ("não encontrad", "sem palavras", "consulta sem")):
                        tr_lines = tr.splitlines()
                        lines.append("### 📝 Falas na Transcrição")
                        lines += tr_lines[:10]
                        if len(tr_lines) > 10:
                            lines.append(f"*… {len(tr_lines) - 10} linha(s) adicionais*")
                    else:
                        lines.append("### 📝 Falas na Transcrição\n_Nenhuma fala encontrada_")
                except Exception:
                    lines.append("### 📝 Falas na Transcrição\n_Erro ao buscar_")
                lines.append("")

            # ── BPMN
            if include_bpmn:
                try:
                    from core.project_store import list_bpmn_processes
                    procs = list_bpmn_processes(self.project_id)
                    words = [w for w in title.lower().split() if len(w) > 3]
                    matched = [
                        p for p in procs
                        if any(w in (p.get("name") or "").lower() for w in words)
                    ]
                    if matched:
                        lines.append("### ⚙️ Processos BPMN Relacionados")
                        for p in matched[:3]:
                            lines.append(
                                f"- **{p.get('name')}** — {p.get('version_count', 0)} versão(ões) "
                                f"[{p.get('status', '—')}]"
                            )
                    else:
                        lines.append(
                            "### ⚙️ Processos BPMN Relacionados\n"
                            "_Nenhum processo com nome diretamente relacionado_"
                        )
                except Exception:
                    pass
                lines.append("")

            # ── SBVR
            if include_sbvr:
                try:
                    sbvr = self.get_sbvr_rules(keyword=title)
                    if "nenhuma" not in sbvr.lower():
                        lines.append("### 📐 Regras SBVR Relacionadas")
                        lines.append(sbvr[:800])
                    else:
                        lines.append("### 📐 Regras SBVR Relacionadas\n_Nenhuma regra encontrada_")
                except Exception:
                    pass
                lines.append("")

            # ── IBIS
            if include_ibis:
                try:
                    ibis_qs = self._load_ibis_questions(topic_filter=title)
                    _icon = {"decided": "✅", "deferred": "⏳", "unresolved": "❓"}
                    if ibis_qs:
                        lines.append("### 🗺️ Debates IBIS Relacionados")
                        for q2 in ibis_qs[:4]:
                            rt   = (q2.get("resolution") or {}).get("type", "unresolved")
                            lines.append(
                                f"- {_icon.get(rt, '❓')} **{q2.get('id','?')}** "
                                f"(Reunião {q2.get('_mnum','?')}): {q2.get('statement','')}"
                            )
                        if len(ibis_qs) > 4:
                            lines.append(f"*… e mais {len(ibis_qs) - 4} debate(s)*")
                    else:
                        lines.append("### 🗺️ Debates IBIS Relacionados\n_Nenhum debate encontrado_")
                except Exception:
                    pass
                lines.append("")

        return "\n".join(lines)

    def simular_cenario(
        self,
        descricao: str,
        requisitos_afetados: list | None = None,
        restricoes: dict | None = None,
    ) -> str:
        """Simulate the impact of a scenario change using LLM + project data."""
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        # 1. Load all requirements
        try:
            all_reqs = (
                db.table("requirements")
                .select("req_number, title, description, req_type, priority, status")
                .eq("project_id", self.project_id)
                .order("req_number")
                .execute().data or []
            )
        except Exception as exc:
            return f"Erro ao buscar requisitos: {exc}"

        if not all_reqs:
            return "Nenhum requisito encontrado no projeto para simular impacto."

        # 2. Identify affected requirements
        affected_rows: list[dict] = []
        if requisitos_afetados:
            for raw_id in requisitos_afetados:
                key = raw_id.strip().upper().replace("REQ-", "").lstrip("0") or "0"
                try:
                    n = int(key)
                    match = next((r for r in all_reqs if r.get("req_number") == n), None)
                    if match and match not in affected_rows:
                        affected_rows.append(match)
                except ValueError:
                    kw = raw_id.lower()
                    affected_rows += [
                        r for r in all_reqs
                        if kw in (r.get("title") or "").lower() and r not in affected_rows
                    ][:2]
        else:
            words = [w for w in descricao.lower().split() if len(w) > 4]
            affected_rows = [
                r for r in all_reqs
                if any(
                    w in (r.get("title") or "").lower()
                    or w in (r.get("description") or "").lower()
                    for w in words
                )
            ][:5]

        # 3. Build compact context
        def _fmt_reqs(reqs: list, label: str) -> str:
            if not reqs:
                return f"{label}: (nenhum identificado)"
            lines = [label + ":"]
            for r in reqs[:12]:
                n = r.get("req_number", "?")
                lines.append(
                    f"  REQ-{n:03d} [{r.get('req_type','—')}/{r.get('priority','—')}]: "
                    f"{r.get('title','')} — {(r.get('description') or '')[:80]}"
                )
            return "\n".join(lines)

        try:
            from core.project_store import list_sbvr_rules
            rules = list_sbvr_rules(self.project_id)
            words = [w for w in descricao.lower().split() if len(w) > 4]
            rel_rules = [
                r for r in rules
                if any(w in (r.get("statement") or "").lower() for w in words)
            ][:5]
            rules_ctx = "\n".join(
                f"  [{r.get('rule_id','')}] {r.get('statement','')}" for r in rel_rules
            ) or "(nenhuma regra diretamente relacionada)"
        except Exception:
            rules_ctx = "(não disponível)"

        try:
            from core.knowledge_store import get_contradictions
            contras = get_contradictions(self.project_id, status="open", limit=10)
            words = [w for w in descricao.lower().split() if len(w) > 4]
            rel_contras = [
                c for c in contras
                if any(w in (c.get("description") or "").lower() for w in words)
            ][:3]
            contra_ctx = "\n".join(
                f"  [{c.get('severity','—')}] {c.get('description','')}" for c in rel_contras
            ) or "(nenhuma contradição relacionada)"
        except Exception:
            contra_ctx = "(não disponível)"

        restricoes_str = (
            "\n".join(f"  - {k}: {v}" for k, v in restricoes.items())
            if restricoes else "  (não informadas)"
        )

        system_prompt = (
            "Você é especialista em análise de impacto de mudanças em projetos de software. "
            "Analise o cenário proposto e retorne análise de impacto clara em Markdown. "
            "Seja conciso e prático. Responda em Português do Brasil."
        )
        user_prompt = (
            f"## Cenário proposto\n{descricao}\n\n"
            f"## Restrições\n{restricoes_str}\n\n"
            f"## Requisitos diretamente afetados\n{_fmt_reqs(affected_rows, 'Afetados')}\n\n"
            f"## Todos os requisitos do projeto\n{_fmt_reqs(all_reqs, 'Todos')}\n\n"
            f"## Regras SBVR relacionadas\n{rules_ctx}\n\n"
            f"## Contradições abertas relacionadas\n{contra_ctx}\n\n"
            "## Responda com:\n"
            "1. **Sumário do Impacto** (🔴 Alto / 🟡 Médio / 🟢 Baixo) com justificativa\n"
            "2. **Requisitos bloqueados ou afetados indiretamente**\n"
            "3. **Regras SBVR a revisar**\n"
            "4. **Riscos e efeitos colaterais**\n"
            "5. **Recomendação final** (prosseguir / revisar / não prosseguir)\n\n"
            "Máximo 600 palavras."
        )

        # 4. LLM call
        try:
            provider_cfg = self.llm_config.get("provider_cfg", {})
            api_key      = self.llm_config.get("api_key", "")
            model        = self.llm_config.get("model", "deepseek-v4-flash")
            client_type  = provider_cfg.get("client_type", "openai_compatible")

            if client_type == "anthropic":
                import anthropic as _ant
                ac  = _ant.Anthropic(api_key=api_key)
                msg = ac.messages.create(
                    model=model, max_tokens=2048, system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                analysis = (msg.content[0].text or "").strip()
            else:
                from openai import OpenAI as _OAI
                client = _OAI(api_key=api_key, base_url=provider_cfg.get("base_url"))
                kwargs: dict = dict(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": user_prompt},
                    ],
                    max_tokens=2048,
                )
                if not provider_cfg.get("reasoning_effort") and "deepseek-v4" not in model.lower():
                    kwargs["temperature"] = 0.3
                analysis = (client.chat.completions.create(**kwargs).choices[0].message.content or "").strip()

        except Exception as exc:
            # Heuristic fallback
            n_aff   = len(affected_rows)
            impact  = "🔴 Alto" if n_aff >= 3 else ("🟡 Médio" if n_aff >= 1 else "🟢 Baixo")
            analysis = (
                f"**Análise heurística** *(LLM indisponível: {exc})*\n\n"
                f"- **Impacto estimado:** {impact}\n"
                f"- **{n_aff}** requisito(s) diretamente identificado(s) como afetado(s).\n"
                f"- Verifique dependências com os demais {len(all_reqs)} requisitos manualmente.\n"
                f"- Regras SBVR relacionadas:\n{rules_ctx[:300]}\n"
            )

        return (
            f"# 🔮 Simulação de Cenário\n\n"
            f"**Cenário:** {descricao}\n\n"
            "---\n\n"
            + analysis
        )

    def verificar_conformidade(
        self,
        doc_id: str | None = None,
        req_type_filter: str | None = None,
        threshold: float = 0.75,
        mode: str = "keyword",
    ) -> str:
        """Check coverage of project requirements against library documents."""
        from modules.supabase_client import get_supabase_client
        from modules.document_store import list_documents, get_document
        import re as _re

        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        # 1. Get documents
        if doc_id:
            doc = get_document(doc_id)
            if not doc:
                return f"Documento com ID `{doc_id}` não encontrado."
            docs = [doc]
        else:
            docs = [d for d in list_documents(project_id=self.project_id, limit=30) if d.get("content_text")]

        if not docs:
            return (
                "Nenhum documento com conteúdo encontrado. "
                "Faça upload e indexe documentos via **📄 Documentos**."
            )

        # 2. Get requirements
        try:
            q = (
                db.table("requirements")
                .select("req_number, title, description, req_type, priority")
                .eq("project_id", self.project_id)
                .order("req_number")
            )
            if req_type_filter:
                q = q.eq("req_type", req_type_filter)
            reqs = q.execute().data or []
        except Exception as exc:
            return f"Erro ao buscar requisitos: {exc}"

        if not reqs:
            hint = f" do tipo '{req_type_filter}'" if req_type_filter else ""
            return f"Nenhum requisito{hint} encontrado no projeto."

        # 3. Keyword helper
        _STOP = {
            "a","o","as","os","de","do","da","dos","das","em","no","na","nos","nas",
            "para","que","um","uma","e","ou","se","com","por","mas","é","ser","ter",
            "ao","à","não","como","mais","deve","há","este","esta","seu","sua","foi",
            "sendo","está","são","pelo","pela","isso","cada","todos","todas",
        }

        def _words(text: str) -> set:
            return {
                w for w in _re.sub(r"[^\w\sáéíóúâêôãçÁÉÍÓÚÂÊÔÃÇ]", " ", text.lower()).split()
                if w not in _STOP and len(w) > 2
            }

        def _score(req_w: set, doc_w: set) -> float:
            return len(req_w & doc_w) / len(req_w) if req_w else 0.0

        # Pre-compute doc word sets (cap content at 50k chars for performance)
        doc_word_sets = [
            (d, _words((d.get("content_text") or "")[:50_000]))
            for d in docs
        ]

        # 4. Analyse each requirement
        covered, partial, uncovered = 0, 0, 0
        gap_rows: list[tuple] = []  # (req_id, title, score, doc_title, doc_id)

        for r in reqs:
            n      = r.get("req_number", "?")
            title  = r.get("title", "")
            desc   = r.get("description", "")
            req_id = f"REQ-{n:03d}" if isinstance(n, int) else f"REQ-{n}"
            rw     = _words(f"{title} {desc}")

            best_score, best_doc = 0.0, None
            for d, dw in doc_word_sets:
                s = _score(rw, dw)
                if s > best_score:
                    best_score, best_doc = s, d

            if best_score >= threshold:
                covered += 1
            elif best_score >= threshold * 0.55:
                partial += 1
                gap_rows.append((req_id, title, best_score, best_doc))
            else:
                uncovered += 1
                gap_rows.append((req_id, title, best_score, best_doc))

        total = len(reqs)
        pct   = 100 * covered / total if total else 0
        icon  = "✅" if pct >= 80 else ("🟡" if pct >= 50 else "🔴")

        lines = [
            "# 🔍 Relatório de Conformidade",
            f"**Documentos analisados:** {len(docs)}  |  **Requisitos:** {total}\n",
            f"## {icon} Cobertura Geral: **{pct:.0f}%** ({covered}/{total})\n",
            f"| Cobertos ✅ | Parciais 🟡 | Não mapeados ❌ |",
            f"|---|---|---|",
            f"| {covered} | {partial} | {uncovered} |\n",
        ]

        if gap_rows:
            lines.append("## ⚠️ Gaps e Cobertura Parcial\n")
            # Sort: uncovered first, then partial
            gap_rows.sort(key=lambda x: x[2])
            for req_id, title, score, d in gap_rows[:20]:
                status     = "❌" if score < threshold * 0.55 else "🟡"
                doc_label  = d.get("title", "—") if d else "nenhum documento"
                lines.append(
                    f"- {status} **{req_id}** — {title}\n"
                    f"  Cobertura: {score:.0%} | Melhor match: *{doc_label}*"
                )
            if len(gap_rows) > 20:
                lines.append(f"*… e mais {len(gap_rows) - 20} requisito(s) com gap*")

        if mode == "llm" and gap_rows:
            lines.append(
                "\n> **Modo LLM:** análise semântica profunda ainda não disponível nesta versão. "
                "Os gaps acima foram identificados por correspondência de palavras-chave (keyword). "
                "Para análise semântica completa, use a aba **⚗️ Extrair Artefatos** em Documentos."
            )

        if uncovered > 0 or partial > 0:
            lines += [
                "\n## 📋 Ações Recomendadas",
                f"- **{uncovered}** requisito(s) sem cobertura — considere criar documentos de especificação.",
                f"- **{partial}** requisito(s) com cobertura parcial — revise a completude dos documentos existentes.",
                "- Use **📄 Documentos** para adicionar BRDs, contratos ou specs e re-execute esta análise.",
            ]

        return "\n".join(lines)

    def reordenar_requisitos(
        self,
        nova_ordem: list | None = None,
        agrupar_por: str | None = None,
    ) -> str:
        """Reorder requirements by updating sort_order."""
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        try:
            rows = (
                db.table("requirements")
                .select("id, req_number, req_type, priority")
                .eq("project_id", self.project_id)
                .execute().data or []
            )
        except Exception as exc:
            return f"Erro ao acessar requisitos: {exc}"

        if not rows:
            return "Nenhum requisito encontrado no projeto."

        # Build id-keyed index: "REQ-001" -> row
        req_by_key: dict = {}
        for r in rows:
            n = r.get("req_number")
            if isinstance(n, int):
                req_by_key[f"REQ-{n:03d}"] = r

        if nova_ordem:
            order_map: dict = {}
            for i, raw_id in enumerate(nova_ordem):
                key = raw_id.strip().upper()
                if not key.startswith("REQ-"):
                    key = f"REQ-{key}"
                if key not in req_by_key:
                    return (
                        f"Requisito '{raw_id}' não encontrado. "
                        "Use identificadores como 'REQ-001'."
                    )
                order_map[req_by_key[key]["id"]] = i + 1

            updated, errors = 0, []
            for rid, order in order_map.items():
                try:
                    db.table("requirements").update({"sort_order": order}).eq("id", rid).execute()
                    updated += 1
                except Exception as exc:
                    errors.append(str(exc))

            msg = f"✅ {updated} requisito(s) reordenado(s) com sucesso."
            if errors:
                msg += f"\n⚠️ {len(errors)} erro(s): " + "; ".join(errors[:3])
            return msg

        elif agrupar_por in ("tipo", "prioridade"):
            priority_rank = {"Crítico": 0, "Alto": 1, "Médio": 2, "Baixo": 3}
            type_rank     = {"Funcional": 0, "Não Funcional": 1, "Regra de Negócio": 2}

            def _key(r: dict):
                if agrupar_por == "prioridade":
                    return (priority_rank.get(r.get("priority") or "", 99), r.get("req_number", 0))
                return (type_rank.get(r.get("req_type") or "", 99), r.get("req_number", 0))

            sorted_rows = sorted(rows, key=_key)
            updated, errors = 0, []
            for i, r in enumerate(sorted_rows):
                try:
                    db.table("requirements").update({"sort_order": i + 1}).eq("id", r["id"]).execute()
                    updated += 1
                except Exception as exc:
                    errors.append(str(exc))

            msg = f"✅ {updated} requisito(s) agrupados por **{agrupar_por}** e reordenados."
            if errors:
                msg += f"\n⚠️ {len(errors)} erro(s): " + "; ".join(errors[:3])
            return msg

        else:
            return (
                "Informe `nova_ordem` (lista de IDs como ['REQ-003','REQ-001']) "
                "ou `agrupar_por` ('tipo' ou 'prioridade')."
            )

    def inserir_secao_ata(
        self,
        meeting_number: int,
        titulo: str,
        conteudo: str,
        posicao: str = "fim",
    ) -> str:
        """Insert a new ## section into a meeting's minutes_md."""
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        m = self._find_meeting(meeting_number)
        if not m:
            return f"Reunião {meeting_number} não encontrada."

        mid        = m["id"]
        minutes_md = m.get("minutes_md") or ""
        new_section = f"\n## {titulo}\n\n{conteudo}\n"

        if not minutes_md:
            minutes_md = f"# Ata — Reunião {meeting_number}\n{new_section}"
        elif re.search(rf'##\s*{re.escape(titulo)}', minutes_md, re.IGNORECASE):
            return (
                f"⚠️ A seção **{titulo}** já existe na ata da Reunião {meeting_number}. "
                "Para atualizar o conteúdo existente, use apply_text_correction."
            )
        else:
            pl = posicao.lower().strip()
            if pl == "inicio":
                h1 = re.search(r'^#\s+.+\n', minutes_md, re.MULTILINE)
                pos = h1.end() if h1 else 0
                minutes_md = minutes_md[:pos] + new_section + minutes_md[pos:]
            elif pl.startswith("antes_"):
                ref = pl[len("antes_"):].replace("_", " ")
                pat = re.search(rf'(##\s*{re.escape(ref)}\b)', minutes_md, re.IGNORECASE)
                if pat:
                    minutes_md = minutes_md[:pat.start()] + new_section + "\n" + minutes_md[pat.start():]
                else:
                    minutes_md = minutes_md.rstrip() + "\n" + new_section
            elif pl.startswith("apos_") or pl.startswith("após_"):
                prefix = "apos_" if pl.startswith("apos_") else "após_"
                ref = pl[len(prefix):].replace("_", " ")
                sec = re.search(
                    rf'(##\s*{re.escape(ref)}[^\n]*\n[\s\S]*?)(?=\n##|\Z)',
                    minutes_md, re.IGNORECASE,
                )
                if sec:
                    minutes_md = minutes_md[:sec.end()] + "\n" + new_section + minutes_md[sec.end():]
                else:
                    minutes_md = minutes_md.rstrip() + "\n" + new_section
            else:
                # "fim" or unknown
                minutes_md = minutes_md.rstrip() + "\n" + new_section

        try:
            db.table("meetings").update({"minutes_md": minutes_md}).eq("id", mid).execute()
            self._meeting_cache = None
            return f"✅ Seção **{titulo}** inserida na ata da Reunião {meeting_number} (posição: {posicao})."
        except Exception as exc:
            return f"❌ Erro ao salvar ata: {exc}"

    def vincular_regra_debate(
        self,
        rule_id: str,
        ibis_question_id: str,
        relacao: str = "justifica",
    ) -> str:
        """Create or update a SBVR rule ↔ IBIS debate link."""
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        valid = {"justifica", "contradiz", "limita"}
        if relacao not in valid:
            return f"Relação inválida: '{relacao}'. Use: {', '.join(sorted(valid))}."

        try:
            existing = (
                db.table("sbvr_ibis_links")
                .select("id")
                .eq("project_id", self.project_id)
                .eq("rule_id", rule_id)
                .eq("ibis_question_id", ibis_question_id)
                .execute().data or []
            )
            if existing:
                db.table("sbvr_ibis_links").update({"relacao": relacao}).eq("id", existing[0]["id"]).execute()
                return (
                    f"✅ Vínculo atualizado: **{rule_id}** → **{ibis_question_id}** "
                    f"(relação: {relacao})."
                )
            db.table("sbvr_ibis_links").insert({
                "project_id":      self.project_id,
                "rule_id":         rule_id,
                "ibis_question_id": ibis_question_id,
                "relacao":         relacao,
            }).execute()
            return (
                f"✅ Vínculo criado: regra **{rule_id}** *{relacao}* questão **{ibis_question_id}**."
            )
        except Exception as exc:
            return (
                f"❌ Erro ao vincular: {exc}\n"
                "Certifique-se de que a migration Fase 2 foi executada "
                "(setup/supabase_migration_fase2.sql)."
            )

    def mesclar_reunioes(
        self,
        manter_meeting: int,
        absorver_meeting: int,
        razao: str = "",
        preview: bool = True,
    ) -> str:
        """Merge two meetings: transfer all artifacts and delete the absorbed one."""
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        m_manter   = self._find_meeting(manter_meeting)
        m_absorver = self._find_meeting(absorver_meeting)
        if not m_manter:
            return f"Reunião {manter_meeting} não encontrada."
        if not m_absorver:
            return f"Reunião {absorver_meeting} não encontrada."
        if manter_meeting == absorver_meeting:
            return "As duas reuniões não podem ser a mesma."

        mid_manter   = m_manter["id"]
        mid_absorver = m_absorver["id"]

        # Collect artifacts from absorbed meeting
        try:
            reqs = (
                db.table("requirements").select("req_number, title")
                .eq("first_meeting_id", mid_absorver)
                .execute().data or []
            )
        except Exception:
            reqs = []

        has_minutes = bool(m_absorver.get("minutes_md"))

        if preview:
            lines = [
                f"**Preview da mesclagem** — Reunião {absorver_meeting} → Reunião {manter_meeting}",
                f"- Razão: {razao or '(não informada)'}",
                f"- {len(reqs)} requisito(s) serão reatribuídos para a Reunião {manter_meeting}:",
            ]
            for r in reqs[:5]:
                n = r.get("req_number", "?")
                lines.append(f"  - REQ-{n:03d}: {r.get('title', '')}" if isinstance(n, int) else f"  - {r.get('title', '')}")
            if len(reqs) > 5:
                lines.append(f"  - ... e mais {len(reqs) - 5}")
            lines.append(
                f"- Ata da Reunião {absorver_meeting}: "
                f"{'será concatenada à ata da Reunião ' + str(manter_meeting) if has_minutes else 'vazia — nenhuma alteração'}"
            )
            lines.append(f"- Reunião {absorver_meeting} será **excluída** após a mesclagem.")
            lines.append("\nPara confirmar, chame novamente com `preview=false`.")
            return "\n".join(lines)

        try:
            # Reatribuir requirements
            for col in ("first_meeting_id", "last_meeting_id"):
                try:
                    db.table("requirements").update({col: mid_manter}).eq(col, mid_absorver).execute()
                except Exception:
                    pass

            # Reatribuir outros artefatos
            for tbl, col in [
                ("sbvr_terms",        "meeting_id"),
                ("sbvr_rules",        "meeting_id"),
                ("bpmn_versions",     "meeting_id"),
                ("transcript_chunks", "meeting_id"),
            ]:
                try:
                    db.table(tbl).update({col: mid_manter}).eq(col, mid_absorver).execute()
                except Exception:
                    pass

            # Concatenar atas
            if has_minutes:
                minutes_manter   = m_manter.get("minutes_md") or ""
                minutes_absorver = m_absorver.get("minutes_md") or ""
                razao_note       = f" — {razao}" if razao else ""
                separator = (
                    f"\n\n---\n"
                    f"*Conteúdo mesclado da Reunião {absorver_meeting}{razao_note}*\n\n"
                )
                merged = minutes_manter.rstrip() + separator + minutes_absorver
                try:
                    db.table("meetings").update({"minutes_md": merged}).eq("id", mid_manter).execute()
                except Exception:
                    pass

            # Excluir reunião absorvida
            db.table("meetings").delete().eq("id", mid_absorver).execute()
            self._meeting_cache = None

            return (
                f"✅ Mesclagem concluída.\n"
                f"- Reunião {absorver_meeting} absorvida pela Reunião {manter_meeting}.\n"
                f"- {len(reqs)} requisito(s) reatribuídos.\n"
                f"- Atas {'concatenadas' if has_minutes else 'sem alteração (absorvida era vazia)'}.\n"
                f"- Reunião {absorver_meeting} excluída."
                + (f"\n- Razão registrada: {razao}" if razao else "")
            )
        except Exception as exc:
            return f"❌ Erro durante a mesclagem: {exc}"

    def sincronizar_calendario(
        self,
        direction: str = "to_calendar",
        meeting_number: int | None = None,
        default_duration: int = 30,
        default_work_start: str = "09:00",
        default_work_end: str = "18:00",
    ) -> str:
        """Sync meeting action items with Google Calendar."""
        from modules.calendar_client import calendar_configured, create_event
        if not calendar_configured():
            return "⚙️ Google Calendar não configurado neste ambiente."
        from modules.supabase_client import get_supabase_client
        import datetime as _dt
        import re as _re
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        meetings = self._load_meetings()
        if meeting_number is not None:
            meetings = [m for m in meetings if m.get("meeting_number") == meeting_number]
            if not meetings:
                return f"Reunião {meeting_number} não encontrada."

        synced, errors, notes = 0, 0, []

        if direction in ("to_calendar", "bidirectional"):
            today = _dt.date.today()
            try:
                h_start, m_start = map(int, default_work_start.split(":"))
            except ValueError:
                h_start, m_start = 9, 0
            start_base = _dt.datetime(today.year, today.month, today.day, h_start, m_start)
            end_base   = start_base + _dt.timedelta(minutes=max(default_duration, 15))
            start_str  = start_base.strftime("%Y-%m-%dT%H:%M:00")
            end_str    = end_base.strftime("%Y-%m-%dT%H:%M:00")

            for m in meetings:
                m_num      = m.get("meeting_number", "?")
                minutes_md = m.get("minutes_md") or ""
                action_txt = self._section(minutes_md, "Itens de Ação", "Action Items", "Ações")
                if not action_txt.strip():
                    continue

                items = [
                    line.strip().lstrip("-•*1234567890.)").strip()
                    for line in action_txt.splitlines()
                    if line.strip() and line.strip()[0] in "-•*0123456789"
                ]

                for item in items[:10]:
                    if not item:
                        continue
                    # Skip if already synced
                    try:
                        already = (
                            db.table("calendar_sync_items")
                            .select("id")
                            .eq("project_id", self.project_id)
                            .eq("meeting_id", m["id"])
                            .eq("action_text", item[:500])
                            .execute().data or []
                        )
                        if already:
                            continue
                    except Exception:
                        pass  # table may not exist yet; proceed anyway

                    try:
                        result_txt = create_event(
                            summary=f"[P2D] {item[:80]}",
                            start_datetime=start_str,
                            end_datetime=end_str,
                            description=f"Encaminhamento — Reunião {m_num} (Process2Diagram)",
                            project_id=self.project_id,
                        )
                        id_match  = _re.search(r'ID:\s+(\S+)', result_txt or "")
                        event_id  = id_match.group(1) if id_match else None
                        try:
                            db.table("calendar_sync_items").insert({
                                "project_id":     self.project_id,
                                "meeting_id":     m["id"],
                                "action_text":    item[:500],
                                "google_event_id": event_id,
                                "sync_direction": "to_calendar",
                                "status":         "synced",
                                "last_sync_at":   _dt.datetime.utcnow().isoformat() + "Z",
                            }).execute()
                        except Exception:
                            pass  # log but don't abort
                        synced += 1
                    except Exception as exc:
                        errors += 1
                        notes.append(f"⚠️ Reunião {m_num}: {str(exc)[:80]}")

        if direction in ("from_calendar", "bidirectional"):
            try:
                tracked = (
                    db.table("calendar_sync_items")
                    .select("id, google_event_id, action_text")
                    .eq("project_id", self.project_id)
                    .eq("status", "synced")
                    .execute().data or []
                )
                notes.append(
                    f"📅 Sync reverso: {len(tracked)} item(s) rastreados no Google Calendar "
                    "(atualização de status requer webhook — não disponível nesta versão)."
                )
            except Exception as exc:
                notes.append(f"⚠️ Erro no sync reverso: {exc}")

        lines = [f"**Sincronização de Calendário** — direção: `{direction}`"]
        if direction in ("to_calendar", "bidirectional"):
            lines.append(f"✅ {synced} encaminhamento(s) criados no Google Calendar.")
            if errors:
                lines.append(f"⚠️ {errors} erro(s).")
            if synced == 0 and errors == 0:
                lines.append(
                    "ℹ️ Todos os encaminhamentos já estavam sincronizados "
                    "ou nenhuma ata contém itens de ação."
                )
        lines.extend(notes[:5])
        return "\n".join(lines)
