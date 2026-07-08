# core/assistant_tools.py
# ─────────────────────────────────────────────────────────────────────────────
# Tool definitions and executor for AgentAssistant tool-use mode.
#
# Each tool maps to an existing project_store / Supabase query.
# The LLM decides which tools to call based on the question context.
#
# Schemas are provided in two formats:
#   get_tool_schemas_openai()    → OpenAI / DeepSeek / Groq function calling
#   get_tool_schemas_anthropic() → Anthropic tool_use
#
# Execution:
#   executor = AssistantToolExecutor(project_id)
#   result   = executor.execute(tool_name, tool_input_dict)
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations
import re
from core.chart_config import CHART_PALETTES, DEFAULT_PALETTE
from core.tools._shared import _compute_initials, _PT_NAME_PREPS
from core.tools.tools_meetings_requirements import (
    _MeetingsRequirementsToolsMixin, MEETINGS_REQUIREMENTS_SCHEMAS,
)
from core.tools.tools_bpmn_sbvr import _BpmnSbvrToolsMixin, BPMN_SBVR_SCHEMAS
from core.tools.tools_meeting_ops_calendar import (
    _MeetingOpsCalendarToolsMixin, MEETING_OPS_CALENDAR_SCHEMAS,
)
from core.tools.tools_admin_charts_entities import (
    _AdminChartsEntitiesToolsMixin, ADMIN_CHARTS_ENTITIES_SCHEMAS,
)
from core.tools.tools_documents_ibis_diagrams import (
    _DocumentsIbisDiagramsToolsMixin, DOCUMENTS_IBIS_DIAGRAMS_SCHEMAS,
)
from core.tools.tools_knowledge_requirements2 import (
    _KnowledgeRequirements2ToolsMixin, KNOWLEDGE_REQUIREMENTS2_SCHEMAS,
)
from core.tools.tools_executive_advanced import (
    _ExecutiveAdvancedToolsMixin, EXECUTIVE_ADVANCED_SCHEMAS,
)


# ── Tool schemas ──────────────────────────────────────────────────────────────

def get_tool_schemas_openai() -> list[dict]:
    """Tool definitions in OpenAI function-calling format."""
    return (
        MEETINGS_REQUIREMENTS_SCHEMAS
        + BPMN_SBVR_SCHEMAS
        + MEETING_OPS_CALENDAR_SCHEMAS
        + ADMIN_CHARTS_ENTITIES_SCHEMAS
        + DOCUMENTS_IBIS_DIAGRAMS_SCHEMAS
        + KNOWLEDGE_REQUIREMENTS2_SCHEMAS
        + EXECUTIVE_ADVANCED_SCHEMAS
    )


def get_tool_schemas_anthropic() -> list[dict]:
    """Tool definitions in Anthropic tool_use format."""
    return [
        {
            "name": t["function"]["name"],
            "description": t["function"]["description"],
            "input_schema": t["function"]["parameters"],
        }
        for t in get_tool_schemas_openai()
    ]


# ── Tool catalog metadata (for UI display) ────────────────────────────────────

_TOOL_CATEGORIES: dict[str, str] = {
    # Consulta (read-only)
    "get_meeting_list":             "consulta",
    "get_meeting_participants":     "consulta",
    "get_meeting_decisions":        "consulta",
    "get_meeting_action_items":     "consulta",
    "get_meeting_processing_history": "consulta",
    "get_meeting_summary":          "consulta",
    "compare_meeting_transcripts":  "consulta",
    "compare_meetings":             "consulta",
    "show_meeting_transcript":      "consulta",
    "search_transcript":            "consulta",
    "count_artifacts":              "consulta",
    "get_requirements":             "consulta",
    "sample_requirements":          "consulta",
    "analyze_requirement_quality":  "consulta",
    "map_transcript_to_requirements": "consulta",
    "cluster_similar_requirements": "consulta",
    "get_bpmn_execution_log":       "consulta",
    "list_bpmn_processes":          "consulta",
    "review_bpmn_diagram":          "consulta",
    "describe_bpmn_process":        "consulta",
    "ask_bpmn_diagram":             "consulta",
    "generate_bpmn_diagram":        "consulta",
    "save_generated_bpmn":          "admin",
    "suggest_bpmn_corrections":     "consulta",
    "save_bpmn_revision":           "admin",
    "apply_bpmn_corrections":       "admin",
    "list_bpmn_versions":           "consulta",
    "delete_bpmn_version":          "admin",
    "get_sbvr_terms":               "consulta",
    "get_sbvr_rules":               "consulta",
    "list_context_files":           "consulta",
    "calculate_meeting_roi":        "consulta",
    "get_recurring_topics":         "consulta",
    "get_meeting_metadata":         "consulta",
    "preview_meeting_deletion":     "consulta",
    "preview_text_correction":      "consulta",
    "get_speaker_contributions":    "consulta",
    "get_system_capabilities":          "consulta",
    "get_executive_report":         "consulta",    
    "get_users_by_domain":   "consulta",
    "list_all_domains":      "consulta",
    "list_users_by_project": "consulta",
    "set_active_project":    "escrita",
    "rename_meeting":        "escrita",
    "save_context_skill":    "escrita",

    "convert_usd_to_brl": "consulta",
    
    "calendar_diagnose":                "admin",
    # Google Calendar
    "calendar_list_events":             "consulta",
    "calendar_get_event":               "consulta",
    "calendar_suggest_time":            "consulta",
    "calendar_create_event":            "admin",
    "calendar_schedule_action_items":   "admin",
    "calendar_share_with_user":         "admin",
    "calendar_revoke_access":           "admin",
    # Escrita / Modificação
    "add_sbvr_term":                "escrita",
    "update_sbvr_term":             "escrita",
    "update_sbvr_term_by_id":       "escrita",
    "add_sbvr_rule":                "escrita",
    "update_sbvr_rule":             "escrita",
    "update_requirement_status":           "escrita",
    "update_requirement_text":             "escrita",
    "update_requirement_implementation":   "escrita",
    # Admin — escrita privilegiada
    "apply_text_correction":        "admin",
    "rename_meeting":               "admin",
    "batch_rename_meetings":        "admin",
    "delete_meeting":               "admin",
    "delete_project_artifacts":     "admin",
    "fix_missing_llm_provider":     "admin",
    "generate_meeting_embeddings":  "admin",
    "embed_meeting":                "admin",
    "get_database_integrity":       "admin",
    # Geração (LLM-powered) — admin
    "generate_missing_minutes":           "admin",
    "reprocess_meeting_requirements":     "admin",
    "reprocess_communication_noise":      "admin",
    "reprocess_meeting_full":         "admin",
    "reprocess_communication_noise":  "admin",
    "regenerate_executive_report":    "admin",
    "batch_reprocess_requirements":   "admin",
    # Gráficos
    "generate_requirements_chart":    "grafico",
    "generate_meetings_timeline":     "grafico",
    "generate_action_items_chart":    "grafico",
    "generate_roi_chart":             "grafico",
    "generate_custom_chart":          "grafico",
    "generate_requirements_flow_chart":    "grafico",
    "generate_requirements_heatmap":       "grafico",
    "generate_requirements_bubble_chart":  "grafico",
    "generate_requirements_waterfall":     "grafico",
    "generate_meeting_radar_chart":        "grafico",
    "generate_gantt_chart":                "grafico",
    "render_table":                   "consulta",
    "populate_roster":                 "admin",
    "populate_knowledge_hub":          "admin",
    "detect_contradictions":           "admin",
    "resolve_entity_ambiguity":        "admin",
    "lookup_entity":                   "consulta",
    "delete_entity":                   "admin",
    "get_cache_stats":                 "consulta",
    "clear_llm_cache":                 "admin",
    # Documentos
    "list_meeting_documents":          "consulta",
    "get_document_content":            "consulta",
    "search_documents":                "consulta",
    "get_document_types":              "consulta",
    "suggest_document_title":          "escrita",
    # Ajuda P2D
    "get_p2d_help":                    "consulta",
    # Histórico de requisitos
    "get_requirement_history":         "consulta",
    # BMM / CKF
    "get_bmm":                         "consulta",
    "get_ckf":                         "consulta",
    # Knowledge Graph
    "list_kh_entities":                "consulta",
    "list_kh_contradictions":          "consulta",
    "resolve_contradiction":           "escrita",
    "delete_contradiction":            "escrita",
    "list_kh_facts":                   "consulta",
    # Glossário / Skills
    "search_glossary":                 "consulta",
    "read_skill_reference":            "consulta",
    # IBIS / Argumentação
    "search_ibis_debates":             "consulta",
    "get_ibis_timeline":               "grafico",
    "generate_ibis_map":               "grafico",
    # Cross-meeting / agenda
    "generate_next_agenda":            "consulta",
    "cluster_topic_decisions":         "consulta",
    # Plantonista / Diagnóstico
    "sugestoes_plantonista":           "consulta",
    "diagnostico_projeto":             "consulta",
    "verificar_rastreabilidade_obrigatoria": "consulta",
    # Rastreabilidade / Simulação / Conformidade (Fase 3)
    "mapa_rastreabilidade":            "consulta",
    "simular_cenario":                 "consulta",
    "verificar_conformidade":          "consulta",
    # Sugestor / Deck / Charter (Fase 4)
    "sugerir_processos":               "consulta",
    "gerar_deck_executivo":            "consulta",
    "gerar_project_charter":           "consulta",
    "export_project_charter_docx":     "consulta",
    # Editor Estrutural (Fase 2)
    "reordenar_requisitos":            "escrita",
    "inserir_secao_ata":               "admin",
    "vincular_regra_debate":           "escrita",
    "mesclar_reunioes":                "admin",
    # Sincronizador Calendário (Fase 2)
    "sincronizar_calendario":          "admin",
    # A2UI
    "show_bpmn_diagram":               "consulta",
    "show_mermaid_diagram":            "consulta",
    "render_mermaid_code":             "consulta",
    "show_metrics":                    "consulta",
    "render_requirements_table":            "consulta",
    "detect_requirement_contradictions":    "consulta",
    "merge_requirements":                   "admin",
    "diff_requirement":                     "consulta",
    "search_universal":                     "consulta",
    "batch_text_correction":                "admin",
}

# Ferramentas que exigem perfil administrador
_ADMIN_TOOLS: frozenset[str] = frozenset({
    "get_database_integrity",
    "fix_missing_llm_provider",
    "generate_meeting_embeddings",
    "embed_meeting",
    "delete_meeting",
    "delete_project_artifacts",
    "rename_meeting",
    "batch_rename_meetings",
    "apply_text_correction",
    "reprocess_meeting_requirements",
    "reprocess_meeting_full",
    "reprocess_communication_noise",
    "regenerate_executive_report",
    "batch_reprocess_requirements",
    "generate_missing_minutes",
    "calendar_create_event",
    "calendar_schedule_action_items",
    "calendar_share_with_user",
    "calendar_revoke_access",
    "calendar_diagnose",
    "populate_roster",
    "populate_knowledge_hub",
    "detect_contradictions",
    "resolve_entity_ambiguity",
    "delete_entity",
    "delete_bpmn_version",
    "save_bpmn_revision",
    "save_generated_bpmn",
    "apply_bpmn_corrections",
    "clear_llm_cache",
    "inserir_secao_ata",
    "mesclar_reunioes",
    "sincronizar_calendario",
    "merge_requirements",
    "batch_text_correction",
})


def get_tool_catalog() -> list[dict]:
    """
    Return all tools with display metadata: name, description, parameters, category.
    Used by the Assistente UI to render a dynamic tool catalog — NOT sent to any LLM.
    """
    return [
        {
            "name":        t["function"]["name"],
            "description": t["function"]["description"],
            "params":      list(t["function"]["parameters"].get("properties", {}).keys()),
            "required":    t["function"]["parameters"].get("required", []),
            "category":    _TOOL_CATEGORIES.get(t["function"]["name"], "consulta"),
        }
        for t in get_tool_schemas_openai()
    ]


# ── Tool executor ─────────────────────────────────────────────────────────────

class AssistantToolExecutor(
    _MeetingsRequirementsToolsMixin,
    _BpmnSbvrToolsMixin,
    _MeetingOpsCalendarToolsMixin,
    _AdminChartsEntitiesToolsMixin,
    _DocumentsIbisDiagramsToolsMixin,
    _KnowledgeRequirements2ToolsMixin,
    _ExecutiveAdvancedToolsMixin,
):
    """
    Executes tool calls for AgentAssistant.

    Each method queries Supabase via existing project_store functions and
    returns a plain-text result string ready to be injected back into the LLM.
    """

    def __init__(self, project_id: str, llm_config: dict | None = None):
        self.project_id = project_id
        self.llm_config = llm_config or {}   # {"api_key", "model", "provider_cfg", "chart_palette"}
        self._meeting_cache: list[dict] | None = None
        self._pending_charts: list[dict] = []  # Plotly figure dicts accumulated during a turn
        palette_name = self.llm_config.get("chart_palette", DEFAULT_PALETTE)
        self._palette: list[str] = CHART_PALETTES.get(palette_name, CHART_PALETTES[DEFAULT_PALETTE])

    def execute(self, tool_name: str, tool_input: dict) -> str:
        """Route a tool call by name to the appropriate implementation."""
        # ── Permission gate: admin-only tools ─────────────────────────────────
        if tool_name in _ADMIN_TOOLS:
            try:
                from modules.auth import is_admin
                if not is_admin():
                    return (
                        f"⛔ A ferramenta '{tool_name}' requer perfil **administrador**. "
                        "Faça login com uma conta admin para usar esta funcionalidade."
                    )
            except Exception:
                pass  # if auth module unavailable, allow (fail-open for safety)

        try:
            dispatch = {
                "get_system_capabilities":   lambda: self.get_system_capabilities(),
                "get_meeting_list":         lambda: self.get_meeting_list(
                    order_by=tool_input.get("order_by", "number"),
                ),
                "get_meeting_participants":  lambda: self.get_meeting_participants(tool_input["meeting_number"]),
                "get_meeting_decisions":     lambda: self.get_meeting_decisions(tool_input["meeting_number"]),
                "get_meeting_action_items":  lambda: self.get_meeting_action_items(
                    tool_input["meeting_number"],
                    tool_input.get("responsible"),
                ),
                "get_meeting_processing_history": lambda: self.get_meeting_processing_history(
                    tool_input["meeting_number"],
                ),
                "get_meeting_summary":       lambda: self.get_meeting_summary(tool_input["meeting_number"]),
                "search_transcript":         lambda: self.search_transcript(
                    tool_input["query"],
                    tool_input.get("meeting_number"),
                ),
                "count_artifacts":           lambda: self._count_artifacts(
                    artifact_type=tool_input.get("artifact_type", "all"),
                    req_type=tool_input.get("req_type"),
                    status=tool_input.get("status"),
                ),
                "get_requirements":          lambda: (
                    # Guard: bare call with no keyword = almost certainly a count question.
                    # Redirect to count_artifacts to avoid token waste and wrong routing.
                    self._count_artifacts(
                        artifact_type="requirements",
                        req_type=tool_input.get("req_type"),
                        status=tool_input.get("status"),
                    ) + "\n\n[Dica: para LISTAR o conteúdo dos requisitos, chame "
                      "get_requirements com keyword, req_type ou page.]"
                    if (not tool_input.get("keyword")
                        and not tool_input.get("page")
                        and not tool_input.get("meeting_number")
                        and not tool_input.get("count_only"))
                    else self.get_requirements(
                        keyword=tool_input.get("keyword"),
                        req_type=tool_input.get("req_type"),
                        status=tool_input.get("status"),
                        meeting_number=tool_input.get("meeting_number"),
                        page=int(tool_input.get("page") or 1),
                        page_size=int(tool_input.get("page_size") or 50),
                        count_only=bool(tool_input.get("count_only", False)),
                    )
                ),
                "sample_requirements":       lambda: self.sample_requirements(
                    meeting_number=tool_input["meeting_number"],
                    sample_size=int(tool_input.get("sample_size") or 20),
                    seed=tool_input.get("seed"),
                ),
                "analyze_requirement_quality": lambda: self.analyze_requirement_quality(
                    meeting_number=tool_input["meeting_number"],
                ),
                "map_transcript_to_requirements": lambda: self.map_transcript_to_requirements(
                    meeting_number=tool_input["meeting_number"],
                ),
                "cluster_similar_requirements": lambda: self.cluster_similar_requirements(
                    meeting_number=tool_input["meeting_number"],
                    threshold=float(tool_input.get("threshold") or 0.85),
                    max_requirements=int(tool_input.get("max_requirements") or 200),
                ),
                "get_bpmn_execution_log":    lambda: self.get_bpmn_execution_log(),
                "list_bpmn_processes":       lambda: self.list_bpmn_processes(),
                "review_bpmn_diagram":       lambda: self.review_bpmn_diagram(
                    process_name=tool_input["process_name"],
                ),
                "describe_bpmn_process":     lambda: self.describe_bpmn_process(
                    process_name=tool_input["process_name"],
                ),
                "ask_bpmn_diagram":          lambda: self.ask_bpmn_diagram(
                    process_name=tool_input["process_name"],
                    question=tool_input["question"],
                ),
                "generate_bpmn_diagram":     lambda: self.generate_bpmn_diagram(
                    meeting_number=tool_input.get("meeting_number"),
                    description=tool_input.get("description"),
                    n_runs=tool_input.get("n_runs", 1),
                ),
                "save_generated_bpmn":       lambda: self.save_generated_bpmn(
                    process_name=tool_input["process_name"],
                    bpmn_xml=tool_input["bpmn_xml"],
                    mermaid_code=tool_input.get("mermaid_code", ""),
                    meeting_number=tool_input.get("meeting_number"),
                ),
                "suggest_bpmn_corrections":  lambda: self.suggest_bpmn_corrections(
                    process_name=tool_input["process_name"],
                ),
                "save_bpmn_revision":        lambda: self.save_bpmn_revision(
                    process_name=tool_input["process_name"],
                    bpmn_xml=tool_input["bpmn_xml"],
                    process_description=tool_input.get("process_description", ""),
                    meeting_number=tool_input.get("meeting_number"),
                    revision_notes=tool_input.get("revision_notes", ""),
                ),
                "apply_bpmn_corrections":    lambda: self.apply_bpmn_corrections(
                    process_name=tool_input["process_name"],
                    corrections=tool_input.get("corrections", []),
                    version_notes=tool_input.get("version_notes", ""),
                ),
                "list_bpmn_versions":        lambda: self._list_bpmn_versions(tool_input),
                "delete_bpmn_version":       lambda: self._delete_bpmn_version(tool_input),
                "get_sbvr_terms":            lambda: self.get_sbvr_terms(tool_input.get("keyword")),
                "get_sbvr_rules":            lambda: self.get_sbvr_rules(tool_input.get("keyword")),
                "list_context_files":        lambda: self.list_context_files(),
                "add_sbvr_term":             lambda: self.add_sbvr_term(
                    tool_input["term"],
                    tool_input["definition"],
                    tool_input.get("category", "Conceito"),
                ),
                "update_requirement_status": lambda: self.update_requirement_status(
                    new_status=tool_input["new_status"],
                    req_numbers=tool_input.get("req_numbers"),
                    filter_req_type=tool_input.get("filter_req_type"),
                    filter_current_status=tool_input.get("filter_current_status"),
                    filter_meeting_number=tool_input.get("filter_meeting_number"),
                    status_note=tool_input.get("status_note"),
                ),
                "update_requirement_text":   lambda: self.update_requirement_text(
                    req_number=int(tool_input["req_number"]),
                    new_description=tool_input.get("new_description"),
                    new_title=tool_input.get("new_title"),
                    change_note=tool_input.get("change_note"),
                ),
                "update_requirement_implementation": lambda: self.update_requirement_implementation(
                    req_number=int(tool_input["req_number"]),
                    resolution_notes=tool_input["resolution_notes"],
                    new_status=tool_input.get("new_status", "implemented"),
                ),
                "update_sbvr_term":          lambda: self.update_sbvr_term(
                    term=tool_input["term"],
                    new_term=tool_input.get("new_term"),
                    definition=tool_input.get("definition"),
                    category=tool_input.get("category"),
                    origin=tool_input.get("origin", "assistente"),
                ),
                "update_sbvr_term_by_id":    lambda: self.update_sbvr_term_by_id(
                    term_id=tool_input["term_id"],
                    new_term=tool_input.get("new_term"),
                    new_definition=tool_input.get("new_definition"),
                    new_category=tool_input.get("new_category"),
                ),
                "add_sbvr_rule":             lambda: self.add_sbvr_rule(
                    tool_input["statement"],
                    tool_input.get("rule_type", "Behavioral Rule"),
                    tool_input.get("source", "manual"),
                ),
                "update_sbvr_rule":          lambda: self.update_sbvr_rule(
                    rule_id=tool_input["rule_id"],
                    new_statement=tool_input["new_statement"],
                    new_rule_type=tool_input.get("new_rule_type"),
                ),
                "preview_text_correction":   lambda: self.preview_text_correction(
                    tool_input["find_text"],
                    tool_input["replace_text"],
                    tool_input["scope"],
                    tool_input.get("meeting_number"),
                ),
                "apply_text_correction":     lambda: self.apply_text_correction(
                    tool_input["find_text"],
                    tool_input["replace_text"],
                    tool_input["scope"],
                    tool_input.get("meeting_number"),
                ),
                "calculate_meeting_roi":     lambda: self.calculate_meeting_roi(
                    tool_input.get("meeting_number"),
                    float(tool_input.get("cost_per_hour", 150.0)),
                ),
                "get_recurring_topics":           lambda: self.get_recurring_topics(
                    float(tool_input.get("threshold", 0.87)),
                ),
                "get_meeting_metadata":           lambda: self.get_meeting_metadata(
                    tool_input["meeting_number"],
                ),
                "preview_meeting_deletion":       lambda: self.preview_meeting_deletion(
                    tool_input["meeting_number"],
                ),
                "delete_meeting":                 lambda: self.delete_meeting(
                    tool_input["meeting_number"],
                    bool(tool_input.get("confirmed", False)),
                ),
                "delete_project_artifacts":       lambda: self.delete_project_artifacts(
                    bool(tool_input.get("confirmed", False)),
                ),
                "rename_meeting":                 lambda: self.rename_meeting(
                    tool_input["meeting_number"],
                    tool_input["new_title"],
                ),
                "batch_rename_meetings":          lambda: self.batch_rename_meetings(
                    renames=tool_input["renames"],
                ),
                "show_meeting_transcript":        lambda: self.show_meeting_transcript(
                    meeting_number=tool_input["meeting_number"],
                ),
                "compare_meeting_transcripts":    lambda: self.compare_meeting_transcripts(
                    meeting_numbers=tool_input["meeting_numbers"],
                ),
                "compare_meetings":               lambda: self.compare_meetings(
                    meeting_number_a=int(tool_input["meeting_number_a"]),
                    meeting_number_b=int(tool_input["meeting_number_b"]),
                ),
                "reprocess_meeting_requirements": lambda: self.reprocess_meeting_requirements(
                    tool_input["meeting_number"],
                    tool_input.get("output_language", "Auto-detect"),
                    bool(tool_input.get("force_replace", True)),
                ),
                "batch_reprocess_requirements":   lambda: self.batch_reprocess_requirements(
                    tool_input.get("meeting_numbers"),
                    bool(tool_input.get("force_replace", True)),
                    tool_input.get("output_language", "Auto-detect"),
                ),
                "generate_missing_minutes":       lambda: self.generate_missing_minutes(
                    tool_input.get("meeting_numbers"),
                    bool(tool_input.get("force_regenerate", False)),
                    tool_input.get("output_language", "Auto-detect"),
                ),
                "get_speaker_contributions":      lambda: self.get_speaker_contributions(
                    tool_input["participant_name"],
                    tool_input.get("meeting_number"),
                ),
                "calendar_diagnose":               lambda: self.calendar_diagnose(),
                "calendar_list_events":            lambda: self.calendar_list_events(
                    max_results=int(tool_input.get("max_results", 10)),
                    time_min=tool_input.get("time_min"),
                    time_max=tool_input.get("time_max"),
                    query=tool_input.get("query"),
                    project_id=self.project_id,
                ),
                "calendar_get_event":              lambda: self.calendar_get_event(
                    tool_input["event_id"],
                    project_id=self.project_id,
                ),
                "calendar_suggest_time":           lambda: self.calendar_suggest_time(
                    duration_minutes=int(tool_input.get("duration_minutes", 60)),
                    attendees=tool_input.get("attendees"),
                    time_min=tool_input.get("time_min"),
                    time_max=tool_input.get("time_max"),
                    max_suggestions=int(tool_input.get("max_suggestions", 3)),
                    project_id=self.project_id,
                ),
                "calendar_create_event":           lambda: self.calendar_create_event(
                    tool_input["summary"],
                    tool_input["start_datetime"],
                    tool_input["end_datetime"],
                    tool_input.get("description"),
                    tool_input.get("location"),
                    tool_input.get("attendees"),
                    project_id=self.project_id,
                ),
                "calendar_schedule_action_items":  lambda: self.calendar_schedule_action_items(
                    tool_input["meeting_number"],
                    tool_input["default_date"],
                    int(tool_input.get("duration_minutes", 30)),
                    project_id=self.project_id,
                ),
                "calendar_share_with_user":        lambda: self.calendar_share_with_user(
                    tool_input["email"],
                    tool_input.get("role", "writer"),
                    project_id=self.project_id,
                ),
                "calendar_revoke_access":          lambda: self.calendar_revoke_access(
                    tool_input["email"],
                    project_id=self.project_id,
                ),
                "get_database_integrity":         lambda: self.get_database_integrity(),
                "fix_missing_llm_provider":       lambda: self.fix_missing_llm_provider(
                    tool_input["provider"],
                ),
                "generate_meeting_embeddings":    lambda: self.generate_meeting_embeddings(
                    tool_input.get("meeting_numbers"),
                ),
                "embed_meeting":                  lambda: self.embed_meeting(
                    tool_input["meeting_number"],
                    bool(tool_input.get("force", False)),
                ),
                "reprocess_meeting_full":         lambda: self.reprocess_meeting_full(
                    tool_input["meeting_number"],
                    bool(tool_input.get("run_bpmn", False)),
                    bool(tool_input.get("run_quality", False)),
                    tool_input.get("output_language", "Auto-detect"),
                ),
                "reprocess_communication_noise":  lambda: self.reprocess_communication_noise(
                    tool_input["meeting_number"],
                    tool_input.get("output_language", "Auto-detect"),
                ),
                "regenerate_executive_report":    lambda: self.regenerate_executive_report(
                    tool_input["meeting_number"],
                    tool_input.get("output_language", "Auto-detect"),
                ),
                # ── Moedas ───────────────────────────────────────────────
                "convert_usd_to_brl": lambda: self.convert_usd_to_brl(
                    float(tool_input["usd_amount"]),
                ),
                # ── Chart tools ───────────────────────────────────────────────
                "generate_requirements_chart":    lambda: self.generate_requirements_chart(
                    group_by=tool_input.get("group_by", "type"),
                    meeting_number=tool_input.get("meeting_number"),
                ),
                "generate_meetings_timeline":     lambda: self.generate_meetings_timeline(
                    metric=tool_input.get("metric", "all"),
                ),
                "generate_action_items_chart":    lambda: self.generate_action_items_chart(
                    group_by=tool_input.get("group_by", "status"),
                    meeting_number=tool_input.get("meeting_number"),
                ),
                "generate_roi_chart":             lambda: self.generate_roi_chart(
                    cost_per_hour=float(tool_input.get("cost_per_hour", 150.0)),
                ),
                # ── User / Domain query tools ─────────────────────────────────
                "get_users_by_domain":            lambda: self.get_users_by_domain(
                    tool_input["domain"],
                ),
                "list_all_domains":               lambda: self.list_all_domains_tool(),
                "list_users_by_project":          lambda: self.list_users_by_project_tool(
                    tool_input.get("project_id"),
                ),
                "rename_meeting":                 lambda: self.rename_meeting(
                    meeting_number=tool_input["meeting_number"],
                    new_title=tool_input["new_title"],
                ),
                "batch_rename_meetings":          lambda: self.batch_rename_meetings(
                    renames=tool_input["renames"],
                ),
                "show_meeting_transcript":        lambda: self.show_meeting_transcript(
                    meeting_number=tool_input["meeting_number"],
                ),
                "compare_meeting_transcripts":    lambda: self.compare_meeting_transcripts(
                    meeting_numbers=tool_input["meeting_numbers"],
                ),
                "set_active_project":             lambda: self.set_active_project(
                    tool_input["project_name"],
                ),
                "save_context_skill":             lambda: self.save_context_skill(
                    tool_input["skill_md"],
                ),
                "generate_custom_chart":          lambda: self.generate_custom_chart(
                    chart_type=tool_input["chart_type"],
                    title=tool_input["title"],
                    labels=tool_input["labels"],
                    values=[float(v) for v in tool_input["values"]],
                    x_label=tool_input.get("x_label", ""),
                    y_label=tool_input.get("y_label", ""),
                    series_name=tool_input.get("series_name", ""),
                    z_matrix=tool_input.get("z_matrix"),
                    y_axis_labels=tool_input.get("y_axis_labels"),
                ),
                "generate_requirements_flow_chart": lambda: self.generate_requirements_flow_chart(
                    view=tool_input.get("view", "sankey"),
                    meeting_number=tool_input.get("meeting_number"),
                ),
                "generate_requirements_heatmap":    lambda: self.generate_requirements_heatmap(
                    dimension=tool_input.get("dimension", "req_type"),
                ),
                "generate_requirements_bubble_chart": lambda: self.generate_requirements_bubble_chart(),
                "generate_requirements_waterfall":  lambda: self.generate_requirements_waterfall(),
                "generate_meeting_radar_chart":     lambda: self.generate_meeting_radar_chart(
                    meeting_numbers=tool_input.get("meeting_numbers"),
                ),
                "generate_gantt_chart":             lambda: self.generate_gantt_chart(
                    title=tool_input["title"],
                    phases=tool_input["phases"],
                ),
                "populate_roster":          lambda: self._populate_roster(tool_input),
                "populate_knowledge_hub":    lambda: self._populate_knowledge_hub(tool_input),
                "detect_contradictions":     lambda: self._detect_contradictions(),
                "resolve_entity_ambiguity":  lambda: self._resolve_entity_ambiguity(tool_input),
                "lookup_entity":             lambda: self._lookup_entity(tool_input),
                "delete_entity":             lambda: self._delete_entity(tool_input),
                "get_cache_stats":           lambda: self.get_cache_stats(tool_input.get("agent_name")),
                "clear_llm_cache":           lambda: self.clear_llm_cache(tool_input.get("agent_name")),
                "render_table": lambda: self._render_table(tool_input),
                "get_executive_report": lambda: self.get_executive_report(
                    tool_input["meeting_number"],
                ),
                # Document tools
                "list_meeting_documents": lambda: self.list_meeting_documents(
                    meeting_number=tool_input.get("meeting_number"),
                    doc_type=tool_input.get("doc_type"),
                    category=tool_input.get("category"),
                ),
                "get_document_content":   lambda: self.get_document_content(tool_input["doc_id"]),
                "search_documents":       lambda: self.search_documents(
                    query=tool_input["query"],
                    mode=tool_input.get("mode", "semantic"),
                ),
                "get_document_types":     lambda: self.get_document_types_tool(),
                "suggest_document_title": lambda: self.suggest_document_title(
                    doc_id=tool_input["doc_id"],
                    apply=tool_input.get("apply", False),
                ),
                # Histórico de requisitos / BMM / CKF / Knowledge Graph
                "get_requirement_history": lambda: self.get_requirement_history(
                    req_number=tool_input["req_number"],
                ),
                "get_bmm":                lambda: self.get_bmm(
                    meeting_number=tool_input.get("meeting_number"),
                ),
                "get_ckf":                lambda: self.get_ckf(),
                "list_kh_entities":       lambda: self.list_kh_entities(
                    entity_type=tool_input.get("entity_type"),
                    limit=int(tool_input.get("limit", 50)),
                ),
                "list_kh_contradictions": lambda: self.list_kh_contradictions(
                    status=tool_input.get("status", "open"),
                ),
                "resolve_contradiction":  lambda: self.resolve_contradiction(
                    description_query=tool_input["description_query"],
                    resolution_note=tool_input["resolution_note"],
                    resolved_by=tool_input.get("resolved_by", "assistente"),
                    new_status=tool_input.get("new_status", "resolved"),
                ),
                "delete_contradiction":   lambda: self.delete_contradiction(
                    description_query=tool_input["description_query"],
                    confirm=bool(tool_input.get("confirm", False)),
                ),
                "list_kh_facts":          lambda: self.list_kh_facts(
                    fact_type=tool_input.get("fact_type"),
                    limit=int(tool_input.get("limit", 50)),
                ),
                # Ajuda P2D
                "get_p2d_help":           lambda: self.get_p2d_help(tool_input["topic"]),
                # Glossário / Skills
                "search_glossary":        lambda: self.search_glossary(
                    query=tool_input["query"],
                    tag=tool_input.get("tag"),
                ),
                "read_skill_reference":   lambda: self.read_skill_reference(
                    agent=tool_input["agent"],
                    section=tool_input.get("section"),
                ),
                # IBIS
                "search_ibis_debates":    lambda: self.search_ibis_debates(
                    query=tool_input["query"],
                    meeting_number=tool_input.get("meeting_number"),
                    resolution_filter=tool_input.get("resolution_filter", "all"),
                ),
                "get_ibis_timeline":      lambda: self.get_ibis_timeline(
                    topic=tool_input.get("topic"),
                ),
                "generate_ibis_map":      lambda: self.generate_ibis_map(
                    topic=tool_input.get("topic"),
                ),
                # ── Cross-meeting / agenda
                "generate_next_agenda":   lambda: self.generate_next_agenda(
                    topic=tool_input.get("topic"),
                ),
                "cluster_topic_decisions": lambda: self.cluster_topic_decisions(
                    topic=tool_input["topic"],
                    artifact_type=tool_input.get("artifact_type", "all"),
                ),
                # ── A2UI
                "show_bpmn_diagram":      lambda: self.show_bpmn_diagram(
                    process_name=tool_input.get("process_name"),
                    meeting_number=tool_input.get("meeting_number"),
                ),
                "show_mermaid_diagram":   lambda: self.show_mermaid_diagram(
                    meeting_number=tool_input["meeting_number"],
                ),
                "render_mermaid_code":    lambda: self.render_mermaid_code(
                    mermaid_code=tool_input["mermaid_code"],
                    title=tool_input.get("title", ""),
                ),
                "show_metrics":           lambda: self.show_metrics(
                    items=tool_input["items"],
                    title=tool_input.get("title", ""),
                ),
                "render_requirements_table": lambda: self.render_requirements_table(
                    meeting_number=tool_input.get("meeting_number"),
                    req_type=tool_input.get("req_type"),
                    status=tool_input.get("status"),
                    title=tool_input.get("title", ""),
                ),
                "detect_requirement_contradictions": lambda: self.detect_requirement_contradictions(
                    meeting_number=tool_input.get("meeting_number"),
                    req_type=tool_input.get("req_type"),
                    max_reqs=int(tool_input.get("max_reqs") or 80),
                ),
                # ── Plantonista / Diagnóstico
                "sugestoes_plantonista":  lambda: self.sugestoes_plantonista(),
                "diagnostico_projeto":    lambda: self.diagnostico_projeto(
                    include_integrity=bool(tool_input.get("include_integrity", True)),
                    include_contradictions=bool(tool_input.get("include_contradictions", True)),
                    include_roi=bool(tool_input.get("include_roi", True)),
                    include_recurring=bool(tool_input.get("include_recurring", True)),
                    include_pendencies=bool(tool_input.get("include_pendencies", True)),
                ),
                "verificar_rastreabilidade_obrigatoria": lambda: self.verificar_rastreabilidade_obrigatoria(),
                # ── Sugestor / Deck / Charter (Fase 4)
                "sugerir_processos":      lambda: self.sugerir_processos(
                    min_reunioes=int(tool_input.get("min_reunioes", 2)),
                    confidence=float(tool_input.get("confidence", 0.7)),
                    include_evidence=bool(tool_input.get("include_evidence", True)),
                ),
                "gerar_deck_executivo":   lambda: self.gerar_deck_executivo(
                    incluir_secoes=tool_input.get("incluir_secoes"),
                    meeting_numbers=tool_input.get("meeting_numbers"),
                    tema_cores=tool_input.get("tema_cores", "corporativo"),
                ),
                "gerar_project_charter":  lambda: self.gerar_project_charter(
                    incluir_riscos=bool(tool_input.get("incluir_riscos", True)),
                    incluir_cronograma=bool(tool_input.get("incluir_cronograma", True)),
                    incluir_stakeholders=bool(tool_input.get("incluir_stakeholders", True)),
                    incluir_escopo=bool(tool_input.get("incluir_escopo", True)),
                ),
                "export_project_charter_docx": lambda: self.export_project_charter_docx(
                    incluir_riscos=bool(tool_input.get("incluir_riscos", True)),
                    incluir_cronograma=bool(tool_input.get("incluir_cronograma", True)),
                    incluir_stakeholders=bool(tool_input.get("incluir_stakeholders", True)),
                    incluir_escopo=bool(tool_input.get("incluir_escopo", True)),
                ),
                # ── Rastreabilidade / Simulação / Conformidade (Fase 3)
                "mapa_rastreabilidade":   lambda: self.mapa_rastreabilidade(
                    req_number=tool_input.get("req_number"),
                    topic=tool_input.get("topic"),
                    include_transcript=bool(tool_input.get("include_transcript", True)),
                    include_bpmn=bool(tool_input.get("include_bpmn", True)),
                    include_sbvr=bool(tool_input.get("include_sbvr", True)),
                    include_ibis=bool(tool_input.get("include_ibis", True)),
                ),
                "simular_cenario":        lambda: self.simular_cenario(
                    descricao=tool_input["descricao"],
                    requisitos_afetados=tool_input.get("requisitos_afetados"),
                    restricoes=tool_input.get("restricoes"),
                ),
                "verificar_conformidade": lambda: self.verificar_conformidade(
                    doc_id=tool_input.get("doc_id"),
                    req_type_filter=tool_input.get("req_type_filter"),
                    threshold=float(tool_input.get("threshold", 0.75)),
                    mode=tool_input.get("mode", "keyword"),
                ),
                # ── Editor Estrutural (Fase 2)
                "reordenar_requisitos":   lambda: self.reordenar_requisitos(
                    nova_ordem=tool_input.get("nova_ordem"),
                    agrupar_por=tool_input.get("agrupar_por"),
                ),
                "inserir_secao_ata":      lambda: self.inserir_secao_ata(
                    meeting_number=int(tool_input["meeting_number"]),
                    titulo=tool_input["titulo"],
                    conteudo=tool_input["conteudo"],
                    posicao=tool_input.get("posicao", "fim"),
                ),
                "vincular_regra_debate":  lambda: self.vincular_regra_debate(
                    rule_id=tool_input["rule_id"],
                    ibis_question_id=tool_input["ibis_question_id"],
                    relacao=tool_input.get("relacao", "justifica"),
                ),
                "mesclar_reunioes":       lambda: self.mesclar_reunioes(
                    manter_meeting=int(tool_input["manter_meeting"]),
                    absorver_meeting=int(tool_input["absorver_meeting"]),
                    razao=tool_input.get("razao", ""),
                    preview=bool(tool_input.get("preview", True)),
                ),
                # ── Sincronizador Calendário (Fase 2)
                "sincronizar_calendario": lambda: self.sincronizar_calendario(
                    direction=tool_input.get("direction", "to_calendar"),
                    meeting_number=tool_input.get("meeting_number"),
                    default_duration=int(tool_input.get("default_duration", 30)),
                    default_work_start=tool_input.get("default_work_start", "09:00"),
                    default_work_end=tool_input.get("default_work_end", "18:00"),
                ),
                # ── Melhorias Proposta-Assistente ────────────────────────────
                "merge_requirements":     lambda: self.merge_requirements(
                    req_numbers=tool_input["req_numbers"],
                    keep_number=int(tool_input["keep_number"]),
                    merge_strategy=tool_input.get("merge_strategy", "combine"),
                    merge_note=tool_input.get("merge_note", ""),
                ),
                "diff_requirement":       lambda: self.diff_requirement(
                    req_number=int(tool_input["req_number"]),
                    from_version=tool_input.get("from_version"),
                    to_version=tool_input.get("to_version"),
                ),
                "search_universal":       lambda: self.search_universal(
                    query=tool_input["query"],
                    scopes=tool_input.get("scopes"),
                ),
                "batch_text_correction":  lambda: self.batch_text_correction(
                    corrections=tool_input["corrections"],
                    meeting_number=tool_input.get("meeting_number"),
                ),
            }
            if tool_name not in dispatch:
                return f"Ferramenta desconhecida: '{tool_name}'"
            return dispatch[tool_name]()
        except Exception as exc:
            return f"Erro ao executar '{tool_name}': {exc}"
