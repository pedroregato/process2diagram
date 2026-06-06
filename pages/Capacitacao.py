# pages/Capacitacao.py
# ─────────────────────────────────────────────────────────────────────────────
# Curso Process2Diagram — Aplicações Corporativas
#
# Página de navegação do curso: lista módulos, exibe cenários e transcrições
# de exemplo. Botão "Carregar no Pipeline" injeta a transcrição em
# st.session_state.transcript_text e redireciona para Pipeline.py.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st
from ui.auth_gate import apply_auth_gate
from ui.components.page_header import render_page_header

apply_auth_gate()

render_page_header(
    "🎓",
    "Curso — Aplicações Corporativas",
    "Cenários reais do mundo corporativo resolvidos com o Process2Diagram.",
)

# ── Definição dos módulos ─────────────────────────────────────────────────────

_BASE = root_dir / "ensino"

_MODULES = [
    {
        "id": "00",
        "titulo": "Fundamentos",
        "icone": "⚡",
        "problema": "Como funciona o pipeline e o que cada agente produz.",
        "duracao": "1h",
        "cenarios": [
            {
                "label": "Hands-on inicial — use a transcrição do Módulo 1A",
                "arquivo": None,
                "descricao": (
                    "Não há transcrição própria neste módulo. Utilize a transcrição "
                    "01A (Aprovação de Fornecedor) para o primeiro pipeline."
                ),
            }
        ],
    },
    {
        "id": "01",
        "titulo": "Mapeamento de Processos sem Consultor",
        "icone": "📐",
        "problema": (
            "A empresa precisa documentar processos para certificação (ISO, SOC 2, LGPD) "
            "mas não tem analista de processos disponível."
        ),
        "duracao": "3h",
        "cenarios": [
            {
                "label": "1A — Homologação de Fornecedores",
                "arquivo": _BASE / "modulo_01_mapeamento_processos" / "transcricao_01a_aprovacao_fornecedor.txt",
                "descricao": (
                    "Construtora Vanguarda. 3 áreas: Compras, Financeiro e Jurídico. "
                    "Análises paralelas, gateways de valor e exceção emergencial."
                ),
            },
            {
                "label": "1B — Concessão de Crédito Pessoal",
                "arquivo": _BASE / "modulo_01_mapeamento_processos" / "transcricao_01b_aprovacao_credito.txt",
                "descricao": (
                    "Financeira Meridional. Múltiplos gateways XOR por score e valor. "
                    "Exercício de XOR join (Check 7 / Pass 5)."
                ),
            },
            {
                "label": "1C — Onboarding de Funcionário",
                "arquivo": _BASE / "modulo_01_mapeamento_processos" / "transcricao_01c_onboarding_funcionario.txt",
                "descricao": (
                    "Logística TerraFirme. Colaboração RH + TI + Facilities com message flows. "
                    "Exercício de Check 8 (choreography balance)."
                ),
            },
        ],
    },
    {
        "id": "02",
        "titulo": "Rastreabilidade de Requisitos",
        "icone": "📋",
        "problema": (
            "O time de TI implementou funcionalidades que ninguém pediu "
            "e não consegue mostrar a origem de cada requisito."
        ),
        "duracao": "2h",
        "cenarios": [
            {
                "label": "2 — Kick-off Portal do Cliente",
                "arquivo": _BASE / "modulo_02_rastreabilidade_requisitos" / "transcricao_02_kickoff_portal_cliente.txt",
                "descricao": (
                    "SegurançaTotal. Portal de autoatendimento para seguros. "
                    "Requisitos IEEE 830 com citação de origem, LGPD, integração com legado."
                ),
            }
        ],
    },
    {
        "id": "03",
        "titulo": "Auditoria e Compliance",
        "icone": "⚖️",
        "problema": (
            "A auditoria exige evidências documentadas de decisões. "
            "Reconstituir isso de e-mails leva semanas."
        ),
        "duracao": "2h",
        "cenarios": [
            {
                "label": "3 — Comitê de Aprovação de Contratos",
                "arquivo": _BASE / "modulo_03_auditoria_compliance" / "transcricao_03_comite_contratos.txt",
                "descricao": (
                    "HospitalCorp. Contrato de cloud R$ 2,3M. "
                    "CFO, Compliance/LGPD e Jurídico. Ata, SBVR e rastro de decisão."
                ),
            }
        ],
    },
    {
        "id": "04",
        "titulo": "Gestão do Conhecimento",
        "icone": "🧠",
        "problema": (
            "Quando um especialista sai da empresa, o conhecimento vai junto. "
            "Onboarding sem documentação gera erros e retrabalho."
        ),
        "duracao": "2h",
        "cenarios": [
            {
                "label": "4 — Captura de Conhecimento com Especialista",
                "arquivo": _BASE / "modulo_04_gestao_conhecimento" / "transcricao_04_captura_conhecimento.txt",
                "descricao": (
                    "EnergiaPlus. Especialista com 28 anos, prestes a se aposentar. "
                    "Conciliação financeira SAP × Salesforce documentada do zero."
                ),
            }
        ],
    },
    {
        "id": "05",
        "titulo": "Governança e ROI de Reuniões",
        "icone": "📊",
        "problema": (
            "A empresa investe horas em reuniões sem saber se está gerando valor. "
            "Gestores não conseguem medir o retorno."
        ),
        "duracao": "2h",
        "cenarios": [
            {
                "label": "5 — Retrospectiva de Sprint",
                "arquivo": _BASE / "modulo_05_governanca_roi" / "transcricao_05_retrospectiva_sprint.txt",
                "descricao": (
                    "FinTechRapida. Sprint review + retrospectiva com métricas. "
                    "ROI-TR, CommunicationNoise (compromissos vagos) e action items."
                ),
            }
        ],
    },
    {
        "id": "06",
        "titulo": "Análise Estratégica com BMM e IBIS",
        "icone": "🎯",
        "problema": (
            "Reuniões de planejamento estratégico produzem slides bonitos mas "
            "os objetivos nunca são rastreados até as iniciativas operacionais."
        ),
        "duracao": "2h",
        "cenarios": [
            {
                "label": "6 — Planejamento Estratégico Anual",
                "arquivo": _BASE / "modulo_06_estrategia_bmm" / "transcricao_06_planejamento_estrategico.txt",
                "descricao": (
                    "MedCenter. Rede de clínicas. CEO + CFO + CTO + Heads. "
                    "Visão, missão, metas, estratégias (BMM) e debate de expansão (IBIS)."
                ),
            }
        ],
    },
]


def _load_transcript(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception as exc:
        return f"[Erro ao carregar transcrição: {exc}]"


def _render_scenario_card(cenario: dict, mod_id: str) -> None:
    arquivo: Path | None = cenario["arquivo"]
    col_info, col_btn = st.columns([4, 1])
    with col_info:
        st.markdown(f"**{cenario['label']}**")
        st.caption(cenario["descricao"])
    with col_btn:
        if arquivo and arquivo.exists():
            btn_key = f"load_{mod_id}_{arquivo.stem}"
            if st.button("▶ Carregar", key=btn_key, help="Carrega no Pipeline"):
                st.session_state.transcript_text = _load_transcript(arquivo)
                st.session_state.pop("hub", None)
                st.session_state.pop("pp_result", None)
                st.session_state.pop("curated_clean", None)
                st.switch_page("pages/Pipeline.py")
        elif arquivo:
            st.caption("⚠️ arquivo não encontrado")

    if arquivo and arquivo.exists():
        with st.expander("📄 Ver transcrição", expanded=False):
            txt = _load_transcript(arquivo)
            st.text_area(
                label="transcrição",
                value=txt,
                height=300,
                disabled=True,
                label_visibility="collapsed",
                key=f"ta_{mod_id}_{cenario['label'][:10]}",
            )
            st.download_button(
                label="⬇ Baixar .txt",
                data=txt,
                file_name=arquivo.name,
                mime="text/plain",
                key=f"dl_{mod_id}_{arquivo.stem}",
            )


# ── Visão geral do curso ──────────────────────────────────────────────────────

with st.expander("📖 Sobre o curso", expanded=False):
    plano_path = _BASE / "PLANO_DO_CURSO.md"
    if plano_path.exists():
        st.markdown(plano_path.read_text(encoding="utf-8"))

st.markdown("---")

# ── Cards dos módulos ─────────────────────────────────────────────────────────

for mod in _MODULES:
    n_cenarios = len(mod["cenarios"])
    header = f"{mod['icone']} **Módulo {mod['id']} — {mod['titulo']}** · {mod['duracao']}"
    with st.expander(header, expanded=False):
        st.markdown(f"> **Problema:** {mod['problema']}")

        guia_path = _BASE / f"modulo_{mod['id']}_{mod['titulo'].lower().replace(' ', '_').replace('ç', 'c').replace('ã', 'a').replace('é', 'e').replace('ê', 'e')}" / "guia.md"
        # Locate guia.md robustly from any matching subfolder
        guia_found: Path | None = None
        for d in _BASE.iterdir():
            if d.is_dir() and d.name.startswith(f"modulo_{mod['id']}_"):
                candidate = d / "guia.md"
                if candidate.exists():
                    guia_found = candidate
                    break

        if guia_found:
            with st.expander("📚 Ver guia do módulo", expanded=False):
                st.markdown(guia_found.read_text(encoding="utf-8"))

        if n_cenarios > 0:
            st.markdown(f"**{'Cenário' if n_cenarios == 1 else f'{n_cenarios} Cenários'}**")
            for cenario in mod["cenarios"]:
                _render_scenario_card(cenario, mod["id"])
                st.markdown("")

st.markdown("---")
st.caption(
    "Process2Diagram — Curso de Aplicações Corporativas · v1.0 · "
    "Transcrições fictícias baseadas em situações reais."
)
