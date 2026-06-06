# agents/agent_minutes.py
# ─────────────────────────────────────────────────────────────────────────────
# Minutes Agent — produces structured meeting minutes from transcript.
#
# Reads:  hub.transcript_clean, hub.nlp.actors (optional enrichment)
# Writes: hub.minutes  (MinutesModel)
# Exports (via to_markdown): Markdown string ready for DOCX/PDF rendering
#
# Robustness: system prompt is embedded as _EMBEDDED_SKILL so the agent works
# even if skills/skill_minutes.md cannot be read (filesystem / path issues).
# The skill file is loaded first and takes precedence for easy editing.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from datetime import datetime

from agents.base_agent import BaseAgent
from core.knowledge_hub import KnowledgeHub, MinutesModel, ActionItem

_PREPOSITIONS = {"de", "da", "do", "das", "dos", "e", "a", "o", "em", "no", "na"}

# ── Embedded system prompt (fallback if skill file cannot be loaded) ──────────
# This is the canonical prompt; skills/skill_minutes.md is kept for editing only.
_EMBEDDED_SKILL = """\
## Convenção de Iniciais dos Participantes

Antes de processar qualquer conteúdo, extraia os nomes dos participantes e
calcule suas iniciais. Use essas iniciais em todo o documento para atribuir
falas, decisões e encaminhamentos.

**Regra de cálculo:** primeiras letras dos dois primeiros nomes significativos,
ignorando preposições (de, da, do, das, dos, e).

Exemplos:
- João Luís Ferreira → **JL**
- Maria de Fátima Duarte → **MF** (ignora "de")
- Natasha Cristine Costa → **NC**
- Pedro Gentil Regato → **PG**

Use as iniciais em:
- Decisões: "[MF] Ficou definido que o catálogo mestre é obrigatório"
- Action items campo `raised_by`: quem levantou/solicitou a tarefa
- Resumo por tópico: atribua falas relevantes com [INICIAL]

## Identidade

Você é um secretário executivo especializado em documentação corporativa.
Produz atas de reunião precisas, objetivas e rastreáveis a partir de
transcrições. Você jamais inventa informações: se algo não foi dito
explicitamente, retorne array vazio [] ou null — NUNCA strings
placeholder como "Não mencionado", "N/A", "Não identificado" ou similares.

## Estrutura da Ata

A ata deve seguir esta estrutura:

1. **Cabeçalho**: título da reunião, data, local/modalidade, participantes (nome completo + iniciais).
2. **Pauta**: lista dos tópicos discutidos (inferida do conteúdo).
3. **Resumo por tópico**: síntese rica de cada ponto discutido — inclua contexto,
   argumentos relevantes, posicionamentos, dúvidas levantadas e conclusões.
   Atribua falas importantes com [INICIAL]: antes do conteúdo.
   Mínimo de 3-5 linhas por tópico em reuniões longas.
4. **Decisões tomadas**: lista objetiva das decisões com responsável e iniciais de quem decidiu.
5. **Action Items**: tarefa | quem levantou | responsável | prazo.
6. **Próxima reunião**: data/hora se mencionada, ou null.

**Formato dos participantes no JSON:**
"participants": ["Nome Completo (XX)", ...] onde XX são as iniciais calculadas.

## Extração de Decisões

Uma decisão é qualquer afirmação que fecha um ponto em discussão:
escolhas, aprovações, definições, acordos, recusas e posicionamentos.
Não confunda com sugestões ou perguntas em aberto.

Sinais linguísticos de decisão:
- "então vai ser assim", "ficou definido", "vamos fazer"
- "aprovado", "decidimos", "não vamos", "vai ficar"
- Conclusões implícitas: quando um debate termina com posicionamento claro

**Transcrições longas contêm muitas decisões espalhadas — leia a transcrição
inteira antes de concluir que não há decisões.** Reuniões de 1h+ tipicamente
produzem 5 a 20 decisões.

## Extração de Action Items

Sinais linguísticos que indicam action items:
- "vai fazer", "ficou de", "vai enviar", "precisa verificar"
- "até [data]", "para a próxima semana", "até sexta"
- "[Nome] vai...", "[Papel] deve..."
- Tarefas implícitas: quando alguém se compromete a resolver algo

**Reuniões de 1h+ tipicamente produzem 5 a 15 action items.**
Procure atribuições de responsabilidade em toda a extensão da transcrição.

Se o responsável não for claro → "A definir".
Se o prazo não for mencionado → null.

## Prioridade dos Action Items

- **high**: prazo imediato ou criticidade explicitada ("urgente", "bloqueador")
- **normal**: padrão
- **low**: melhorias, sugestões sem urgência

## Formato de Saída (JSON — NUNCA use markdown)

{
  "title": "<título da reunião ou 'Reunião sem título'>",
  "date": "<data mencionada ou null>",
  "location": "<local ou modalidade, ex: 'Remota — Teams' ou null>",
  "participants": ["<nome ou papel>"],
  "agenda": ["<tópico 1>", "<tópico 2>"],
  "summary": [
    { "topic": "<tópico>", "content": "<resumo neutro>" }
  ],
  "decisions": ["<decisão 1>", "<decisão 2>"],
  "action_items": [
    {
      "task": "<descrição da tarefa>",
      "responsible": "<nome ou papel, ou 'A definir'>",
      "deadline": "<prazo ou null>",
      "priority": "normal",
      "raised_by": "<iniciais de quem levantou a tarefa, ex: 'MF', ou null>"
    }
  ],
  "next_meeting": "<data e hora ou null>",
  "meeting_antipatterns": [
    {
      "type": "<nome do antipadrão>",
      "description": "<como se manifestou>",
      "examples": ["<citação 1>"]
    }
  ]
}

## Detecção de Antipadrões de Reunião

Após extrair todos os campos acima, analise a transcrição e identifique antipadrões
de condução que comprometem a rastreabilidade do conhecimento gerado.

Avalie os seguintes antipadrões e inclua apenas os que realmente ocorreram:

- **Participante Ausente**: alguém responde por outro ("vou perguntar para X", "X não pôde vir mas disse que...")
- **Compromisso Condicional**: comprometimentos vagos ou condicionais ("vou tentar", "se der", "talvez")
- **Proxy Sem Autonomia**: participante que não consegue decidir nada; tudo fica "para confirmar depois"
- **Multitarefa**: evidência de distração, falas interrompidas abruptamente, retomadas sem contexto
- **Patrocinador Ausente**: reunião sem declaração de propósito na abertura; escopo não definido
- **Facilitador Viesado**: facilitador emite opinião de conteúdo como se fosse decisão do grupo
- **Decisão Implícita**: grupo age como se uma decisão tivesse sido tomada sem que ninguém a verbalizasse

Para cada antipadrão detectado, inclua:
- `type`: nome do antipadrão (use exatamente os nomes listados acima)
- `description`: uma frase descrevendo como se manifestou nesta reunião específica
- `examples`: lista de 1–3 citações literais (ou próximas do literal) da transcrição que evidenciam o antipadrão

Se nenhum antipadrão for detectado, retorne array vazio `[]`.

Adicione ao JSON de saída o campo:
```
"meeting_antipatterns": [
  {
    "type": "<nome do antipadrão>",
    "description": "<como se manifestou>",
    "examples": ["<citação 1>", "<citação 2>"]
  }
]
```

## Detecção de Antipadrões de Reunião

Após extrair todos os campos acima, analise a transcrição e identifique antipadrões
de condução que comprometem a rastreabilidade do conhecimento gerado.

Avalie os seguintes antipadrões e inclua apenas os que realmente ocorreram:

- **Participante Ausente**: alguém responde por outro ("vou perguntar para X", "X não pôde vir mas disse que...")
- **Compromisso Condicional**: comprometimentos vagos ou condicionais ("vou tentar", "se der", "talvez")
- **Proxy Sem Autonomia**: participante que não consegue decidir nada; tudo fica "para confirmar depois"
- **Multitarefa**: evidência de distração, falas interrompidas abruptamente, retomadas sem contexto
- **Patrocinador Ausente**: reunião sem declaração de propósito na abertura; escopo não definido
- **Facilitador Viesado**: facilitador emite opinião de conteúdo como se fosse decisão do grupo
- **Decisão Implícita**: grupo age como se uma decisão tivesse sido tomada sem que ninguém a verbalizasse

Para cada antipadrão detectado, inclua:
- `type`: nome do antipadrão (use exatamente os nomes listados acima)
- `description`: uma frase descrevendo como se manifestou nesta reunião específica
- `examples`: lista de 1–3 citações literais (ou próximas do literal) da transcrição

Se nenhum antipadrão for detectado, retorne array vazio [].

Adicione ao JSON de saída:
"meeting_antipatterns": [
  {
    "type": "<nome do antipadrão>",
    "description": "<como se manifestou>",
    "examples": ["<citação 1>", "<citação 2>"]
  }
]

## Regras Críticas

1. **Neutralidade**: não emita opiniões ou julgamentos sobre o conteúdo.
2. **Fidelidade**: use o vocabulário da transcrição; não substitua termos técnicos.
3. **Completude**: toda decisão e todo action item identificável deve estar na lista.
   Uma reunião de 2h sem decisões ou sem action items é improvável — releia antes de concluir isso.
4. **Sem invenção**: se não foi dito, não está na ata.
5. **Sem placeholders**: arrays vazios [] quando não há itens. NUNCA strings como "Não mencionado".
6. **Output language**: {output_language}
7. **Retorne APENAS o JSON**. Nenhum texto, nenhum markdown, nenhuma explicação.
"""


def _compute_initials(full_name: str) -> str:
    """Returns initials from the first two significant words of a name."""
    words = [w for w in full_name.split() if w.lower() not in _PREPOSITIONS]
    return "".join(w[0].upper() for w in words[:2]) if len(words) >= 2 else ""


class AgentMinutes(BaseAgent):

    name = "minutes"
    skill_path = "skills/skill_minutes.md"

    # ── Prompt ────────────────────────────────────────────────────────────────

    def build_prompt(self, hub: KnowledgeHub, output_language: str = "Auto-detect") -> tuple[str, str]:
        lang = self._language_instruction(output_language)

        # Use file-based skill if loaded; fall back to embedded constant.
        # This guarantees the agent works even if the skill file cannot be read
        # (case sensitivity on Linux, CWD issues, Streamlit Cloud cold starts).
        raw_skill = self._skill if self._skill.strip() else _EMBEDDED_SKILL
        system = raw_skill.replace("{output_language}", lang)

        if getattr(hub, "context_skill", "").strip():
            system += f"\n\n## Conhecimento do Contexto\n\n{hub.context_skill.strip()}"

        if getattr(hub, "context_files_text", "").strip():
            system += f"\n\n## Documentos de Referência do Contexto\n\n{hub.context_files_text.strip()}"

        actor_hint = ""
        if hub.nlp.actors:
            actor_hint = f"\nParticipants identified by NLP: {', '.join(hub.nlp.actors)}"

        # Pass full transcript — truncation to 12k was causing severe quality loss
        # (only ~5% of a 2h meeting visible). DeepSeek context window supports ~80k chars.
        transcript = hub.transcript_clean

        user = (
            f"Produce the structured meeting minutes from this transcript:{actor_hint}\n\n"
            f"{transcript}"
        )
        return system, user

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(self, hub: KnowledgeHub, output_language: str = "Auto-detect") -> KnowledgeHub:
        system, user = self.build_prompt(hub, output_language)
        data = self._call_with_retry(system, user, hub)

        hub.minutes = self._build_model(data)
        hub.minutes.ready = True
        hub.minutes.minutes_md = AgentMinutes.to_markdown(hub.minutes)
        hub.mark_agent_run(self.name)
        hub.bump()
        return hub

    # ── Model building ────────────────────────────────────────────────────────

    @staticmethod
    def _build_model(data: dict) -> MinutesModel:
        action_items = [
            ActionItem(
                task=ai.get("task", ""),
                responsible=ai.get("responsible", "A definir"),
                deadline=ai.get("deadline") or None,
                priority=ai.get("priority", "normal"),
                raised_by=ai.get("raised_by") or None,
            )
            for ai in data.get("action_items", [])
        ]
        # Parse meeting antipatterns
        raw_antipatterns = data.get("meeting_antipatterns") or []
        meeting_antipatterns = [
            {
                "type": ap.get("type", ""),
                "description": ap.get("description", ""),
                "examples": ap.get("examples") or [],
            }
            for ap in raw_antipatterns
            if isinstance(ap, dict) and ap.get("type")
        ]

        return MinutesModel(
            title=data.get("title", "Reunião"),
            date=data.get("date") or "",
            location=data.get("location") or "",
            participants=data.get("participants", []),
            agenda=data.get("agenda", []),
            summary=data.get("summary", []),
            decisions=data.get("decisions", []),
            action_items=action_items,
            next_meeting=data.get("next_meeting") or None,
            assumptions=data.get("assumptions") or [],
            open_questions=data.get("open_questions") or [],
            risks_identified=data.get("risks_identified") or [],
            dependencies=data.get("dependencies") or [],
            stakeholder_needs=data.get("stakeholder_needs") or [],
            meeting_antipatterns=meeting_antipatterns,
        )

    # ── Markdown export ───────────────────────────────────────────────────────

    @staticmethod
    def to_markdown(minutes: MinutesModel) -> str:
        """Render MinutesModel as a structured Markdown document."""
        lines: list[str] = []
        now = datetime.now().strftime("%d/%m/%Y")

        # Header
        lines += [
            f"# {minutes.title}",
            "",
            f"**Data:** {minutes.date or 'Não informada'}  ",
            f"**Local/Modalidade:** {minutes.location or 'Não informada'}  ",
            f"**Gerado em:** {now}",
            "",
        ]

        # Participants — format: "Nome Completo (XX)" already from LLM,
        # or compute initials as fallback for legacy entries without them.
        if minutes.participants:
            lines += ["## Participantes", ""]
            for p in minutes.participants:
                # If initials already embedded by LLM (e.g. "João Luís (JL)"), use as-is
                if "(" in p and ")" in p:
                    lines.append(f"- {p}")
                else:
                    # Compute initials as fallback
                    initials = _compute_initials(p)
                    suffix = f" ({initials})" if initials else ""
                    lines.append(f"- {p}{suffix}")
            lines.append("")

        # Agenda
        if minutes.agenda:
            lines += ["## Pauta", ""]
            for i, item in enumerate(minutes.agenda, 1):
                lines.append(f"{i}. {item}")
            lines.append("")

        # Summary
        if minutes.summary:
            lines += ["## Resumo da Reunião", ""]
            for block in minutes.summary:
                topic = block.get("topic", "")
                content = block.get("content", "")
                if topic:
                    lines.append(f"### {topic}")
                lines.append(content)
                lines.append("")

        # Decisions
        if minutes.decisions:
            lines += ["## Decisões Tomadas", ""]
            for d in minutes.decisions:
                lines.append(f"- {d}")
            lines.append("")

        # Action Items
        if minutes.action_items:
            lines += ["## Encaminhamentos / Action Items", ""]
            lines += [
                "| # | Tarefa | Levantado por | Responsável | Prazo | Prioridade |",
                "|---|--------|---------------|-------------|-------|------------|",
            ]
            priority_labels = {"high": "🔴 Alta", "normal": "🟡 Normal", "low": "🟢 Baixa"}
            for i, ai in enumerate(minutes.action_items, 1):
                prio = priority_labels.get(ai.priority, ai.priority)
                deadline = ai.deadline or "—"
                raised = f"**{ai.raised_by}**" if ai.raised_by else "—"
                lines.append(f"| {i} | {ai.task} | {raised} | {ai.responsible} | {deadline} | {prio} |")
            lines.append("")

        # Next meeting
        if minutes.next_meeting:
            lines += ["## Próxima Reunião", "", f"**{minutes.next_meeting}**", ""]

        # Meeting antipatterns (if any)
        antipatterns = getattr(minutes, "meeting_antipatterns", [])
        if antipatterns:
            lines += ["## ⚠️ Alertas de Condução", ""]
            lines.append(
                "*Os seguintes antipadrões foram detectados nesta reunião. "
                "Eles podem ter reduzido a qualidade dos artefatos gerados.*"
            )
            lines.append("")
            for ap in antipatterns:
                ap_type = ap.get("type", "")
                ap_desc = ap.get("description", "")
                ap_examples = ap.get("examples", [])
                lines.append(f"**{ap_type}:** {ap_desc}")
                for ex in ap_examples:
                    lines.append(f'  > "{ex}"')
                lines.append("")

        lines += [
            "---",
            f"*Ata gerada automaticamente pelo Process2Diagram — {now}*",
        ]

        return "\n".join(lines)

    # ── Verification Report ───────────────────────────────────────────────────

    @staticmethod
    def to_verification_report(minutes: "MinutesModel") -> str:
        """
        Generate a structured Markdown verification checklist to be presented
        back to participants after the pipeline runs.

        Based on the 'verification session' concept from model-based workshop
        methodology: facilitator presents each artifact element and participants
        confirm or correct. Helps catch errors and builds SME ownership of artifacts.
        """
        lines: list[str] = []
        now = datetime.now().strftime("%d/%m/%Y")

        lines += [
            f"# Roteiro de Verificação — {minutes.title}",
            "",
            f"**Reunião:** {minutes.date or 'Data não registrada'}  ",
            f"**Gerado em:** {now}  ",
            "",
            "> Este roteiro deve ser apresentado aos participantes da reunião em uma",
            "> sessão de verificação (presencial ou remota). Para cada item, o facilitador",
            "> lê em voz alta e aguarda confirmação ou correção dos participantes.",
            "> Marque ✅ quando confirmado, ✏️ quando corrigido.",
            "",
            "---",
            "",
        ]

        # Decisions
        if minutes.decisions:
            lines += ["## Decisões — Verificar com os Participantes", ""]
            for i, d in enumerate(minutes.decisions, 1):
                lines.append(f"- [ ] **Decisão {i}:** {d}")
            lines.append("")
            lines.append(
                "*Perguntar: \"Esta decisão foi tomada conforme registrado? "
                "Há alguma nuance ou condição que ficou faltando?\"*"
            )
            lines.append("")

        # Action Items
        if minutes.action_items:
            lines += ["## Encaminhamentos — Confirmar Responsável e Prazo", ""]
            for i, ai in enumerate(minutes.action_items, 1):
                deadline = ai.deadline or "prazo a definir"
                resp = ai.responsible or "responsável a definir"
                lines.append(f"- [ ] **Encaminhamento {i}:** {ai.task}  ")
                lines.append(f"  Responsável: **{resp}** · Prazo: **{deadline}**")
            lines.append("")
            lines.append(
                "*Perguntar: \"O responsável confirma a tarefa e o prazo? "
                "Há alguma dependência ou risco que impede a entrega?\"*"
            )
            lines.append("")

        # Open Questions
        if minutes.open_questions:
            lines += ["## Perguntas em Aberto — Definir Responsável pela Resposta", ""]
            for i, q in enumerate(minutes.open_questions, 1):
                lines.append(f"- [ ] **{i}.** {q}")
            lines.append("")

        # Risks
        if minutes.risks_identified:
            lines += ["## Riscos Identificados — Validar e Decidir Ação", ""]
            for i, r in enumerate(minutes.risks_identified, 1):
                lines.append(f"- [ ] **{i}.** {r}")
            lines.append("")

        # Antipatterns alert
        antipatterns = getattr(minutes, "meeting_antipatterns", [])
        if antipatterns:
            lines += ["## ⚠️ Alertas de Condução — Para Melhorar a Próxima Reunião", ""]
            lines.append(
                "Os seguintes antipadrões foram detectados. Discuta com o grupo "
                "antes de encerrar a sessão de verificação:"
            )
            lines.append("")
            for ap in antipatterns:
                ap_type = ap.get("type", "")
                ap_desc = ap.get("description", "")
                lines.append(f"- **{ap_type}:** {ap_desc}")
            lines.append("")

        lines += [
            "---",
            "",
            "## Encerramento da Sessão de Verificação",
            "",
            "- [ ] Todos os itens foram revisados",
            "- [ ] Correções foram anotadas e serão aplicadas",
            "- [ ] Próxima reunião ou follow-up agendado (se necessário)",
            "",
            "---",
            f"*Roteiro gerado pelo Process2Diagram — {now}*",
        ]

        return "\n".join(lines)
