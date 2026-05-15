# agents/agent_analyst.py
# ─────────────────────────────────────────────────────────────────────────────
# AgentAnalyst — autonomous analysis agent using LangChain tool-calling loop.
#
# Uses langchain.agents.create_agent (LangGraph-backed) which:
#  - calls the LLM with tool definitions (function-calling style)
#  - executes chosen tools, feeds results back
#  - repeats until the LLM produces a final answer with no tool call
#
# Unlike AgentAssistant (≤5 rounds, conversational), AgentAnalyst executes
# multi-step analytical objectives autonomously (up to ~15 tool rounds),
# with full chain-of-thought capture and streaming step display.
#
# Public API:
#   AgentAnalyst(llm_config, project_id, is_admin=False)
#     .run(objective: str) -> AnalysisReport
#
# LangChain imports are lazy (inside run()) to avoid slowing Streamlit cold start.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field

_log = logging.getLogger(__name__)


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class ReActStep:
    """One step in the agent's chain of thought."""
    type: str          # "action" | "observation" | "conclusion" | "error"
    label: str         # short display label
    content: str       # rendered Markdown content for UI
    tool_name: str = ""
    tool_input: str = ""
    observation: str = ""

    def to_dict(self) -> dict:
        return {
            "type":        self.type,
            "label":       self.label,
            "content":     self.content,
            "tool_name":   self.tool_name,
            "tool_input":  self.tool_input,
            "observation": self.observation,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ReActStep":
        return cls(
            type        = d.get("type", ""),
            label       = d.get("label", ""),
            content     = d.get("content", ""),
            tool_name   = d.get("tool_name", ""),
            tool_input  = d.get("tool_input", ""),
            observation = d.get("observation", ""),
        )


@dataclass
class AnalysisReport:
    """Result of an autonomous analysis run."""
    objective: str
    steps: list[ReActStep] = field(default_factory=list)
    conclusion: str = ""
    tables: list[dict] = field(default_factory=list)
    charts: list[dict] = field(default_factory=list)
    tokens_used: int = 0
    duration_s: float = 0.0
    success: bool = True
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "objective":   self.objective,
            "steps":       [s.to_dict() for s in self.steps],
            "conclusion":  self.conclusion,
            "tables":      self.tables,
            "charts":      self.charts,
            "tokens_used": self.tokens_used,
            "duration_s":  self.duration_s,
            "success":     self.success,
            "error":       self.error,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AnalysisReport":
        return cls(
            objective   = d.get("objective", ""),
            steps       = [ReActStep.from_dict(s) for s in d.get("steps", [])],
            conclusion  = d.get("conclusion", ""),
            tables      = d.get("tables", []),
            charts      = d.get("charts", []),
            tokens_used = d.get("tokens_used", 0),
            duration_s  = d.get("duration_s", 0.0),
            success     = d.get("success", True),
            error       = d.get("error", ""),
        )


# ── Main agent ────────────────────────────────────────────────────────────────

class AgentAnalyst:
    """
    Autonomous analysis agent using LangChain tool-calling loop (LangGraph-backed).

    Parameters
    ----------
    llm_config : dict
        Keys: client_type, model, api_key, base_url (optional)
    project_id : str
        Active project UUID
    is_admin : bool
        Whether admin-only tools should be exposed
    """

    # Each tool round = 2 graph steps (agent → tools → agent). 15 rounds = 32 steps.
    RECURSION_LIMIT = 32

    SYSTEM_PROMPT = (
        "Você é um analista sênior de processos de negócios.\n"
        "Execute o objetivo analítico usando as ferramentas disponíveis.\n"
        "Responda SEMPRE em português brasileiro.\n\n"
        "Instruções:\n"
        "1. Antes de cada ação, elabore seu raciocínio.\n"
        "2. Use múltiplas ferramentas para reunir dados antes de concluir.\n"
        "3. Para dados tabulares, use a ferramenta render_table.\n"
        "4. Para contar artefatos, use count_artifacts (não get_requirements).\n"
        "5. Ao final, produza uma conclusão clara com achados e recomendações concretas."
    )

    def __init__(self, llm_config: dict, project_id: str, is_admin: bool = False):
        self.llm_config = llm_config or {}
        self.project_id = project_id
        self.is_admin   = is_admin

    # ── Public API ────────────────────────────────────────────────────────────

    def run(self, objective: str) -> AnalysisReport:
        """Execute an autonomous analytical objective and return a report."""
        t0 = time.time()
        try:
            return self._run_agent(objective, t0)
        except Exception as exc:
            _log.error("AgentAnalyst.run error: %s", exc, exc_info=True)
            return AnalysisReport(
                objective  = objective,
                conclusion = f"Erro na execução da análise: {exc}",
                duration_s = time.time() - t0,
                success    = False,
                error      = str(exc),
            )

    # ── Internal ──────────────────────────────────────────────────────────────

    def _run_agent(self, objective: str, t0: float) -> AnalysisReport:
        # Lazy imports — only executed when Análise Autônoma mode is triggered
        from langchain.agents import create_agent
        from adapters.langchain_tools import build_langchain_tools
        import streamlit as st

        executor_obj, tools = build_langchain_tools(
            self.project_id,
            is_admin   = self.is_admin,
            llm_config = self.llm_config,
        )
        llm = self._build_llm()

        agent_graph = create_agent(
            model         = llm,
            tools         = tools,
            system_prompt = self.SYSTEM_PROMPT,
        )

        # Clear pending tables from any previous run
        st.session_state.pop("_pending_tables", None)

        # Stream to capture intermediate steps
        steps:        list[ReActStep] = []
        final_answer: str             = ""

        try:
            for chunk in agent_graph.stream(
                {"messages": [("user", objective)]},
                config       = {"recursion_limit": self.RECURSION_LIMIT},
                stream_mode  = "updates",
            ):
                for node_name, update in chunk.items():
                    for msg in (update.get("messages") or []):
                        self._process_message(msg, steps)
                        # Track final answer from last AI message
                        content = getattr(msg, "content", "")
                        tc      = getattr(msg, "tool_calls", None)
                        if content and not tc:
                            msg_type = getattr(msg, "type", "")
                            if msg_type == "ai":
                                final_answer = str(content)
        except Exception as exc:
            _log.warning("AgentAnalyst stream interrupted: %s", exc)
            if not final_answer:
                final_answer = f"Análise interrompida: {exc}"

        # Add conclusion step if not already captured
        if final_answer and (not steps or steps[-1].type != "conclusion"):
            steps.append(ReActStep(
                type    = "conclusion",
                label   = "Resposta Final",
                content = final_answer,
            ))

        tables = st.session_state.pop("_pending_tables", [])
        charts = executor_obj.get_pending_charts()

        return AnalysisReport(
            objective  = objective,
            steps      = steps,
            conclusion = final_answer,
            tables     = tables,
            charts     = charts,
            duration_s = time.time() - t0,
            success    = bool(final_answer),
        )

    @staticmethod
    def _process_message(msg, steps: list[ReActStep]) -> None:
        """Extract ReActStep entries from a LangGraph message."""
        msg_type  = getattr(msg, "type", "")
        content   = getattr(msg, "content", "")
        tool_calls = getattr(msg, "tool_calls", None)

        if tool_calls:
            # AI message with tool calls → action steps
            for tc in tool_calls:
                name  = tc.get("name", "tool")
                args  = tc.get("args", {})
                args_str = (
                    json.dumps(args, ensure_ascii=False)
                    if isinstance(args, dict)
                    else str(args)
                )[:400]
                steps.append(ReActStep(
                    type       = "action",
                    label      = f"Ferramenta: {name}",
                    tool_name  = name,
                    tool_input = args_str,
                    content    = f"**Ferramenta:** `{name}`\n\n**Input:** {args_str}",
                ))

        elif msg_type == "tool":
            # ToolMessage → observation for the last unmatched action
            obs = str(content)[:1000]
            for s in reversed(steps):
                if s.type == "action" and not s.observation:
                    s.observation = obs
                    break

    def _build_llm(self):
        """Build a LangChain chat model from llm_config."""
        client_type = self.llm_config.get("client_type", "openai_compatible")
        model       = self.llm_config.get("model", "deepseek-chat")
        api_key     = self.llm_config.get("api_key", "")

        if client_type == "anthropic":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model       = model,
                api_key     = api_key,
                temperature = 0,
                max_tokens  = 4096,
            )

        from langchain_openai import ChatOpenAI
        kwargs: dict = {
            "model":       model,
            "api_key":     api_key,
            "temperature": 0,
            "max_tokens":  4096,
        }
        base_url = self.llm_config.get("base_url")
        if base_url:
            kwargs["base_url"] = base_url
        return ChatOpenAI(**kwargs)
