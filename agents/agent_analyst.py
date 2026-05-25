# agents/agent_analyst.py
# ─────────────────────────────────────────────────────────────────────────────
# AgentAnalyst — autonomous analysis agent using a manual tool-calling loop.
#
# Mirrors the pattern of AgentAssistant.chat_with_tools() but:
#  - Single analytical objective (not conversational)
#  - Up to MAX_ITERATIONS = 15 tool rounds
#  - Captures ReActStep for each tool call + observation
#  - Returns AnalysisReport
#  - Works with all existing providers via openai==1.65.0 / anthropic==0.49.0
#    (no LangChain dependency)
#
# Public API:
#   AgentAnalyst(llm_config, project_id, is_admin=False)
#     .run(objective: str) -> AnalysisReport
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field

_log = logging.getLogger(__name__)

MAX_ITERATIONS = 15   # max tool rounds before forcing final answer


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
    Autonomous analysis agent using a manual tool-calling loop.

    Uses the same openai / anthropic SDK already in requirements.txt —
    no LangChain dependency.

    Parameters
    ----------
    llm_config : dict
        Keys: client_type, model, api_key, base_url (optional)
    project_id : str
        Active project UUID
    is_admin : bool
        Whether admin-only tools should be exposed
    """

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
        from core.assistant_tools import (
            AssistantToolExecutor,
            get_tool_schemas_openai,
            get_tool_schemas_anthropic,
        )
        import streamlit as st

        executor = AssistantToolExecutor(
            project_id = self.project_id,
            llm_config = self.llm_config,
        )

        # Clear pending tables from any previous run
        st.session_state.pop("_pending_tables", None)

        client_type = self.llm_config.get("client_type", "openai_compatible")

        if client_type == "anthropic":
            conclusion, total_tk, steps = self._loop_anthropic(
                executor, objective, get_tool_schemas_anthropic()
            )
        else:
            conclusion, total_tk, steps = self._loop_openai(
                executor, objective, get_tool_schemas_openai()
            )

        tables = st.session_state.pop("_pending_tables", [])
        charts = executor.get_pending_charts()

        return AnalysisReport(
            objective  = objective,
            steps      = steps,
            conclusion = conclusion,
            tables     = tables,
            charts     = charts,
            tokens_used = total_tk,
            duration_s = time.time() - t0,
            success    = bool(conclusion),
        )

    # ── OpenAI-compatible loop ────────────────────────────────────────────────

    def _loop_openai(
        self,
        executor,
        objective: str,
        tools: list[dict],
    ) -> tuple[str, int, list[ReActStep]]:
        from openai import OpenAI

        api_key  = self.llm_config.get("api_key", "")
        model    = self.llm_config.get("model", "deepseek-v4-flash")
        base_url = self.llm_config.get("base_url")

        client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)

        msgs: list[dict] = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user",   "content": objective},
        ]
        total_tk = 0
        steps: list[ReActStep] = []

        _thinking_mode     = bool(self.llm_config.get("reasoning_effort"))
        _supports_required = not _thinking_mode and "deepseek-v4" not in model.lower()

        for iteration in range(MAX_ITERATIONS):
            _call_kwargs: dict = dict(
                model      = model,
                messages   = msgs,
                tools      = tools,
                max_tokens = 4096,
            )
            if _thinking_mode:
                _call_kwargs["reasoning_effort"] = self.llm_config["reasoning_effort"]
                _call_kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
            else:
                _call_kwargs["tool_choice"] = ("required" if iteration == 0 else "auto") if _supports_required else "auto"
                _call_kwargs["temperature"] = 0

            resp = client.chat.completions.create(**_call_kwargs)
            total_tk += resp.usage.total_tokens if resp.usage else 0
            choice = resp.choices[0]
            content = choice.message.content or ""
            _reasoning = getattr(choice.message, "reasoning_content", None) or ""

            if choice.finish_reason != "tool_calls" or not choice.message.tool_calls:
                # Final answer
                return content, total_tk, steps

            # Build clean assistant message (avoid SDK-specific extra fields)
            tc_list = choice.message.tool_calls or []
            _amsg = {
                "role":    "assistant",
                "content": content,
                "tool_calls": [
                    {
                        "id":   tc.id,
                        "type": tc.type,
                        "function": {
                            "name":      tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tc_list
                ],
            }
            if _reasoning:
                _amsg["reasoning_content"] = _reasoning
            msgs.append(_amsg)

            for tc in tc_list:
                fn_name = tc.function.name
                try:
                    fn_args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    fn_args = {}

                args_str = json.dumps(fn_args, ensure_ascii=False)[:400]
                step = ReActStep(
                    type       = "action",
                    label      = f"Ferramenta: {fn_name}",
                    tool_name  = fn_name,
                    tool_input = args_str,
                    content    = f"**Ferramenta:** `{fn_name}`\n\n**Input:** {args_str}",
                )

                result = executor.execute(fn_name, fn_args)
                obs = str(result)[:1000]
                step.observation = obs
                steps.append(step)

                msgs.append({
                    "role":         "tool",
                    "tool_call_id": tc.id,
                    "content":      obs,
                })

        # Force final answer after MAX_ITERATIONS
        final_resp = client.chat.completions.create(
            model      = model,
            messages   = msgs + [{
                "role":    "user",
                "content": (
                    "Com base em todos os dados coletados, escreva agora a conclusão completa "
                    "em Português do Brasil."
                ),
            }],
            max_tokens  = 4096,
            temperature = 0,
        )
        total_tk += final_resp.usage.total_tokens if final_resp.usage else 0
        return final_resp.choices[0].message.content or "", total_tk, steps

    # ── Anthropic loop ────────────────────────────────────────────────────────

    def _loop_anthropic(
        self,
        executor,
        objective: str,
        tools: list[dict],
    ) -> tuple[str, int, list[ReActStep]]:
        import anthropic

        api_key = self.llm_config.get("api_key", "")
        model   = self.llm_config.get("model", "claude-sonnet-4-6")

        client = anthropic.Anthropic(api_key=api_key)

        msgs: list[dict] = [{"role": "user", "content": objective}]
        total_tk = 0
        steps: list[ReActStep] = []

        for _ in range(MAX_ITERATIONS):
            resp = client.messages.create(
                model      = model,
                system     = self.SYSTEM_PROMPT,
                tools      = tools,
                messages   = msgs,
                max_tokens = 4096,
            )
            total_tk += (resp.usage.input_tokens + resp.usage.output_tokens) if resp.usage else 0

            if resp.stop_reason != "tool_use":
                text = next((b.text for b in resp.content if hasattr(b, "text")), "")
                return text, total_tk, steps

            tool_use_blocks = [b for b in resp.content if b.type == "tool_use"]
            if not tool_use_blocks:
                text = next((b.text for b in resp.content if hasattr(b, "text")), "")
                return text, total_tk, steps

            msgs.append({"role": "assistant", "content": resp.content})

            tool_results = []
            for tb in tool_use_blocks:
                args_str = json.dumps(tb.input or {}, ensure_ascii=False)[:400]
                step = ReActStep(
                    type       = "action",
                    label      = f"Ferramenta: {tb.name}",
                    tool_name  = tb.name,
                    tool_input = args_str,
                    content    = f"**Ferramenta:** `{tb.name}`\n\n**Input:** {args_str}",
                )

                result = executor.execute(tb.name, tb.input or {})
                obs = str(result)[:1000]
                step.observation = obs
                steps.append(step)

                tool_results.append({
                    "type":        "tool_result",
                    "tool_use_id": tb.id,
                    "content":     obs,
                })

            msgs.append({"role": "user", "content": tool_results})

        # Force final answer after MAX_ITERATIONS
        final_resp = client.messages.create(
            model      = model,
            system     = self.SYSTEM_PROMPT,
            messages   = msgs + [{
                "role":    "user",
                "content": (
                    "Com base em todos os dados coletados, escreva agora a conclusão completa "
                    "em Português do Brasil."
                ),
            }],
            max_tokens = 4096,
        )
        total_tk += (final_resp.usage.input_tokens + final_resp.usage.output_tokens) if final_resp.usage else 0
        text = next((b.text for b in final_resp.content if hasattr(b, "text")), "")
        return text, total_tk, steps
