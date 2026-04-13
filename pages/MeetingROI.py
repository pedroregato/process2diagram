# pages/MeetingROI.py
# ─────────────────────────────────────────────────────────────────────────────
# Dashboard ROI-TR — Qualidade de Reuniões
#
# Exibe indicadores de qualidade (ROI-TR, TRC, custo estimado) para todas as
# reuniões de um projeto, usando dados já armazenados no Supabase.
#
# Zero chamadas LLM — todos os cálculos são determinísticos.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import pandas as pd
import streamlit as st

from ui.auth_gate import apply_auth_gate
from modules.supabase_client import supabase_configured, get_supabase_client
from modules.meeting_roi_calculator import compute_project_roi, project_summary, MeetingROIData
from modules.cross_meeting_analyzer import (
    find_recurring_topics,
    save_project_scores,
    load_score_history,
)

apply_auth_gate()

# ── Page header ───────────────────────────────────────────────────────────────
st.markdown("# 📊 Qualidade de Reuniões — ROI-TR")
st.caption(
    "Indicador de eficiência das reuniões: ROI-TR (Retorno sobre Investimento de Tempo) "
    "e TRC (Taxa de Retrabalho Conceitual). Calculado a partir de atas, transcrições e "
    "requisitos armazenados. Nenhum dado é modificado por esta página."
)

if not supabase_configured():
    st.error("⚙️ Supabase não configurado. Adicione as credenciais em Configurações → Secrets.")
    st.stop()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Parâmetros")

    cost_per_hour = st.slider(
        "Custo médio por participante (R$/h)",
        min_value=50,
        max_value=500,
        value=150,
        step=10,
        help=(
            "Custo horário médio por participante usado no cálculo do custo estimado "
            "e do ROI-TR. Ajuste conforme o perfil dos participantes do projeto."
        ),
    )

    st.markdown("---")
    st.markdown("#### 📖 Como interpretar")
    st.markdown(
        """
**ROI-TR (0–10)**
> Razão entre decisões concretas geradas e o custo humano investido.

| Score | Classificação |
|---|---|
| 7,5–10 | 🟢 Alto |
| 4,5–7,4 | 🟡 Médio |
| 2,0–4,4 | 🟠 Baixo |
| 0–1,9 | 🔴 Crítico |

**Decisões Concretas (DC)**
Decisões na ata + Itens com responsável e prazo × 2 + Requisitos formalizados × 1,5

**TRC — Taxa de Retrabalho Conceitual**
Proxy linguístico: sinais de repetição de conceitos na transcrição ("como já disse", "de novo", "patinando"...).
"""
    )

# ── Project selector ──────────────────────────────────────────────────────────
db = get_supabase_client()
if not db:
    st.error("Não foi possível conectar ao Supabase.")
    st.stop()

try:
    projects = db.table("projects").select("id, name, sigla").order("name").execute().data or []
except Exception as exc:
    st.error(f"Erro ao carregar projetos: {exc}")
    st.stop()

if not projects:
    st.warning("Nenhum projeto encontrado no banco de dados.")
    st.stop()

project_options = {p["name"]: p for p in projects}
selected_name   = st.selectbox(
    "Projeto",
    list(project_options.keys()),
    key="roi_project_sel",
)
project = project_options[selected_name]
project_id = project["id"]

st.markdown("---")

# ── Compute ───────────────────────────────────────────────────────────────────
with st.spinner("Calculando indicadores..."):
    roi_data = compute_project_roi(project_id, cost_per_hour=float(cost_per_hour))

if not roi_data:
    st.info("Nenhuma reunião encontrada para este projeto.")
    st.stop()

summary = project_summary(roi_data)

# ── KPI summary row ───────────────────────────────────────────────────────────
avg_roi  = summary["avg_roi"]
avg_trc  = summary["avg_trc"]
total_cost = summary["total_cost"]

avg_label = (
    "🟢 Alto" if avg_roi >= 7.5 else
    "🟡 Médio" if avg_roi >= 4.5 else
    "🟠 Baixo" if avg_roi >= 2.0 else
    "🔴 Crítico"
)

best  = summary["best_meeting"]
worst = summary["worst_meeting"]

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric(
    "ROI-TR Médio",
    f"{avg_roi:.1f} / 10",
    delta=avg_label,
    delta_color="off",
)
col2.metric(
    "TRC Médio",
    f"{avg_trc:.0f} %",
    delta="🔴 Alto" if avg_trc > 40 else ("🟠 Médio" if avg_trc > 20 else "🟢 Baixo"),
    delta_color="off",
)
col3.metric(
    "Custo total estimado",
    f"R$ {total_cost:,.0f}" if total_cost > 0 else "—",
    help="Soma dos custos estimados de todas as reuniões.",
)
col4.metric(
    "Melhor reunião",
    f"Reunião {best.meeting_number}",
    delta=f"ROI {best.roi_tr:.1f}",
    delta_color="normal",
)
col5.metric(
    "Pior reunião",
    f"Reunião {worst.meeting_number}",
    delta=f"ROI {worst.roi_tr:.1f}",
    delta_color="inverse",
)

st.markdown("---")

# ── Save scores button ────────────────────────────────────────────────────────
save_col, hist_col = st.columns([1, 4])
with save_col:
    if st.button("💾 Salvar Scores no Banco", use_container_width=True,
                 help="Persiste os indicadores ROI-TR atuais em meeting_quality_scores para análise de tendência."):
        result = save_project_scores(project_id, roi_data)
        if result["saved"] > 0:
            st.toast(f"✅ {result['saved']} scores salvos com sucesso!", icon="✅")
        if result["errors"]:
            for e in result["errors"]:
                st.warning(e)
        if result["saved"] == 0 and not result["errors"]:
            st.info("Tabela meeting_quality_scores não encontrada. Execute o SQL de migração em Configurações → Banco de Dados.")

# ── Charts ─────────────────────────────────────────────────────────────────────
tab_charts, tab_table, tab_detail, tab_cross = st.tabs([
    "📈 Gráficos",
    "📋 Tabela Detalhada",
    "🔍 Detalhes por Reunião",
    "🔄 Tópicos Recorrentes",
])

with tab_charts:
    chart_labels = [f"R{m.meeting_number}" for m in roi_data]

    col_roi, col_trc = st.columns(2)

    with col_roi:
        st.markdown("#### ROI-TR por Reunião")
        df_roi = pd.DataFrame({
            "Reunião": chart_labels,
            "ROI-TR":  [round(m.roi_tr, 2) for m in roi_data],
        }).set_index("Reunião")
        st.bar_chart(df_roi, color="#4F81BD", height=320)

        # Reference lines via annotation
        st.caption(
            "Referências: 🟢 7,5 (Alto) · 🟡 4,5 (Médio) · 🟠 2,0 (Baixo)"
        )

    with col_trc:
        has_trc = any(m.has_transcript for m in roi_data)
        st.markdown("#### TRC — Retrabalho Conceitual (%)")
        if has_trc:
            df_trc = pd.DataFrame({
                "Reunião": chart_labels,
                "TRC (%)": [round(m.trc, 1) for m in roi_data],
            }).set_index("Reunião")
            st.bar_chart(df_trc, color="#C0504D", height=320)
            st.caption(
                "Referências: 🔴 > 40 % (Alto) · 🟠 > 20 % (Médio) · 🟢 ≤ 20 % (Baixo)"
            )
        else:
            st.info("Nenhuma transcrição disponível — TRC não calculável.")

    # Cost chart (only when available)
    costs = [m.cost_estimate for m in roi_data if m.cost_estimate > 0]
    if costs:
        st.markdown("#### Custo Estimado por Reunião (R$)")
        df_cost = pd.DataFrame({
            "Reunião":       chart_labels,
            "Custo (R$)":   [round(m.cost_estimate, 0) for m in roi_data],
        }).set_index("Reunião")
        st.bar_chart(df_cost, color="#9BBB59", height=280)


with tab_table:
    st.markdown("#### Indicadores por Reunião")

    rows = []
    for m in roi_data:
        rows.append({
            "#":             m.meeting_number,
            "Reunião":       m.title[:40] + ("…" if len(m.title) > 40 else ""),
            "Data":          m.date or "—",
            "Part.":         m.n_participants,
            "Duração est.":  f"{m.duration_min:.0f} min" if m.has_transcript else "—",
            "Custo est.":    f"R$ {m.cost_estimate:,.0f}" if m.cost_estimate > 0 else "—",
            "Decisões":      m.n_decisions,
            "Ações compl.":  f"{m.n_actions_complete}/{m.n_actions_total}",
            "Requisitos":    m.n_requirements,
            "ROI-TR":        f"{m.roi_tr:.1f}",
            "Status ROI":    m.roi_label,
            "TRC %":         f"{m.trc:.0f}" if m.has_transcript else "—",
            "Status TRC":    m.trc_label if m.has_transcript else "—",
        })

    df_table = pd.DataFrame(rows)

    def _color_roi(val: str) -> str:
        if "🟢" in val:
            return "background-color: #d1fae5; color: #065f46"
        if "🟡" in val:
            return "background-color: #fef9c3; color: #713f12"
        if "🟠" in val:
            return "background-color: #ffedd5; color: #9a3412"
        if "🔴" in val:
            return "background-color: #fee2e2; color: #7f1d1d"
        return ""

    styled = (
        df_table.style
        .applymap(_color_roi, subset=["Status ROI", "Status TRC"])
        .set_properties(**{"text-align": "center"}, subset=["#", "Part.", "Decisões", "Requisitos", "ROI-TR", "TRC %"])
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)

    # CSV export
    csv = df_table.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Exportar CSV",
        data=csv,
        file_name=f"roi_tr_{selected_name.replace(' ', '_')}.csv",
        mime="text/csv",
        use_container_width=False,
    )


with tab_detail:
    sel_meeting = st.selectbox(
        "Selecione a reunião",
        [f"Reunião {m.meeting_number} — {m.title}" for m in roi_data],
        key="roi_detail_sel",
    )
    # Find selected
    sel_idx   = [f"Reunião {m.meeting_number} — {m.title}" for m in roi_data].index(sel_meeting)
    m: MeetingROIData = roi_data[sel_idx]

    # Header
    data_flags = []
    if m.has_minutes:
        data_flags.append("✅ Ata")
    else:
        data_flags.append("⚠️ Sem ata")
    if m.has_transcript:
        data_flags.append("✅ Transcrição")
    else:
        data_flags.append("⚠️ Sem transcrição")

    st.markdown(f"### Reunião {m.meeting_number} — {m.title}")
    if m.date:
        st.caption(f"📅 {m.date} · " + " · ".join(data_flags))
    else:
        st.caption(" · ".join(data_flags))

    # Score highlight
    score_col, trc_col, cost_col = st.columns(3)
    score_col.metric("ROI-TR", f"{m.roi_tr:.1f} / 10", delta=m.roi_label, delta_color="off")
    trc_col.metric("TRC", f"{m.trc:.0f} %" if m.has_transcript else "—", delta=m.trc_label if m.has_transcript else "", delta_color="off")
    cost_col.metric("Custo estimado", f"R$ {m.cost_estimate:,.0f}" if m.cost_estimate > 0 else "—")

    st.markdown("---")

    # Breakdown
    dc1, dc2, dc3 = st.columns(3)
    with dc1:
        st.markdown("**Insumos de decisão**")
        st.markdown(
            f"- Decisões na ata: **{m.n_decisions}**\n"
            f"- Itens de ação total: **{m.n_actions_total}**\n"
            f"- Itens com resp.+prazo: **{m.n_actions_complete}**\n"
            f"- Requisitos formalizados: **{m.n_requirements}**"
        )
    with dc2:
        st.markdown("**Tempo & custo**")
        if m.has_transcript:
            st.markdown(
                f"- Palavras na transcrição: **{m.word_count:,}**\n"
                f"- Duração estimada: **{m.duration_min:.0f} min** ({m.duration_hours:.1f}h)\n"
                f"- Participantes: **{m.n_participants}**\n"
                f"- Custo/h usado: **R$ {m.cost_per_hour:.0f}**"
            )
        else:
            st.markdown(
                f"- Participantes: **{m.n_participants}**\n"
                "- Duração: não disponível (sem transcrição)\n"
                f"- Custo/h usado: **R$ {m.cost_per_hour:.0f}**"
            )
    with dc3:
        st.markdown("**Sinais de ciclagem (TRC)**")
        if m.has_transcript:
            st.markdown(
                f"- Sinais detectados: **{m.cycle_signals}x**\n"
                f"- TRC calculada: **{m.trc:.0f} %** {m.trc_label}\n\n"
                "_Sinais: 'como já disse', 'de novo', 'patinando', 'novamente'..._"
            )
        else:
            st.markdown("_Transcrição não disponível — TRC não calculável._")

    # Formula explainer
    with st.expander("🧮 Como o ROI-TR é calculado"):
        st.markdown(
            f"""
```
DC (Decisões Concretas):
  = Decisões ({m.n_decisions})
  + Itens com resp.+prazo ({m.n_actions_complete}) × 2
  + Requisitos ({m.n_requirements}) × 1.5
  = {m.dc_score:.1f}

Custo estimado:
  = {m.n_participants} participantes × {m.duration_hours:.2f}h × R$ {m.cost_per_hour:.0f}/h
  = R$ {m.cost_estimate:,.0f}

ROI-TR = min(10, DC × 1000 / Custo × 1.5)
       = min(10, {m.dc_score:.1f} × 1000 / {max(m.cost_estimate, 1):.0f} × 1.5)
       = {m.roi_tr:.2f}
```
"""
        )

with tab_cross:
    st.markdown("#### 🔄 Tópicos Recorrentes entre Reuniões")
    st.caption(
        "Detecta assuntos discutidos em múltiplas reuniões sem resolução definitiva — "
        "o padrão de 'patinação' que gera desgaste e baixo ROI-TR. "
        "Usa embeddings semânticos quando disponíveis; caso contrário, análise de palavras-chave."
    )

    col_thresh, col_btn = st.columns([2, 1])
    with col_thresh:
        sim_threshold = st.slider(
            "Limiar de similaridade semântica",
            min_value=0.80,
            max_value=0.98,
            value=0.87,
            step=0.01,
            format="%.2f",
            help="Maior = correspondências mais estritas. Recomendado: 0.87–0.92",
            key="cross_threshold",
        )
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        run_cross = st.button("🔍 Analisar", use_container_width=True, key="run_cross_btn")

    if run_cross or st.session_state.get("_cross_data_loaded"):
        with st.spinner("Analisando padrões cross-meeting..."):
            topics, method = find_recurring_topics(
                project_id,
                threshold=sim_threshold,
                max_results=30,
            )
        st.session_state["_cross_data_loaded"] = True
        st.session_state["_cross_topics"] = topics
        st.session_state["_cross_method"] = method
    else:
        topics = st.session_state.get("_cross_topics", [])
        method = st.session_state.get("_cross_method", "")

    if topics or method:
        method_label = {
            "semantic": "🧠 Semântico (embeddings)",
            "keyword":  "🔤 Palavras-chave (fallback)",
            "unavailable": "⚠️ Supabase indisponível",
            "error":    "❌ Erro ao consultar banco",
        }.get(method, method)

        st.caption(f"Método de detecção: **{method_label}**")

        if method == "keyword" and not st.session_state.get("_cross_data_loaded"):
            st.info(
                "💡 Embeddings não encontrados para este projeto. "
                "Gere os embeddings na página **Assistente** → '⚡ Gerar Embeddings' "
                "para ativar a análise semântica (mais precisa)."
            )

    if topics:
        st.markdown(f"**{len(topics)} tópico(s) recorrente(s) identificado(s):**")

        for t in topics:
            title_parts = [f"**{t.meetings_str}**"]
            if t.keywords:
                title_parts.append("·  " + "  ·  ".join(t.keywords[:4]))
            if t.similarity > 0:
                title_parts.append(f"  ·  sim. {t.similarity:.2f}")

            with st.expander(
                f"{t.intensity_label}  {'  '.join(title_parts)}",
                expanded=False,
            ):
                meet_list = "  →  ".join(
                    f"**Reunião {n}** — {t.meeting_titles.get(n, '')}"
                    for n in t.meetings
                )
                st.markdown(f"Reuniões envolvidas: {meet_list}")

                if t.keywords:
                    st.markdown(f"Termos-chave: `{'` · `'.join(t.keywords)}`")

                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown(f"*Reunião {t.meetings[0]}:*")
                    st.markdown(
                        f'<div style="background:#f8fafc;border-left:3px solid #94a3b8;'
                        f'padding:8px 12px;border-radius:4px;font-size:0.85rem">'
                        f'{t.excerpt_a}</div>',
                        unsafe_allow_html=True,
                    )
                with col_b:
                    n_b = t.meetings[1] if len(t.meetings) > 1 else t.meetings[0]
                    st.markdown(f"*Reunião {n_b}:*")
                    st.markdown(
                        f'<div style="background:#f8fafc;border-left:3px solid #94a3b8;'
                        f'padding:8px 12px;border-radius:4px;font-size:0.85rem">'
                        f'{t.excerpt_b}</div>',
                        unsafe_allow_html=True,
                    )

        # Summary table
        if len(topics) >= 3:
            st.markdown("---")
            st.markdown("##### Resumo de recorrência por reunião")
            meeting_recurrence: dict[int, int] = {}
            for t in topics:
                for n in t.meetings:
                    meeting_recurrence[n] = meeting_recurrence.get(n, 0) + 1

            df_rec = pd.DataFrame([
                {"Reunião": f"R{n}", "Tópicos recorrentes": cnt}
                for n, cnt in sorted(meeting_recurrence.items())
            ]).set_index("Reunião")
            st.bar_chart(df_rec, color="#a78bfa", height=240)
            st.caption(
                "Reuniões com mais tópicos recorrentes são candidatas prioritárias "
                "para revisão de pauta e implementação de timeboxing."
            )
    elif st.session_state.get("_cross_data_loaded"):
        st.success(
            "✅ Nenhum tópico recorrente detectado com o limiar atual. "
            "Tente reduzir o limiar ou verifique se as transcrições estão disponíveis."
        )

# ── Score history ──────────────────────────────────────────────────────────────
history = load_score_history(project_id)
if history:
    with st.expander("📜 Histórico de Scores ROI-TR", expanded=False):
        st.caption(
            "Registros salvos via '💾 Salvar Scores no Banco'. "
            "Permite acompanhar a evolução dos indicadores ao longo do tempo."
        )
        df_hist = pd.DataFrame(history)
        df_hist["computed_at"] = pd.to_datetime(df_hist["computed_at"]).dt.strftime("%Y-%m-%d %H:%M")
        df_hist = df_hist.rename(columns={
            "meeting_number": "Reunião",
            "computed_at":    "Calculado em",
            "roi_tr":         "ROI-TR",
            "trc":            "TRC %",
            "cost_estimate":  "Custo est.",
            "dc_score":       "DC",
        })
        cols_show = [c for c in ["Reunião", "Calculado em", "ROI-TR", "TRC %", "Custo est.", "DC"] if c in df_hist.columns]
        st.dataframe(df_hist[cols_show], hide_index=True, use_container_width=True)

        if len(df_hist["Reunião"].unique()) > 0:
            pivot = df_hist.pivot_table(index="Calculado em", columns="Reunião", values="ROI-TR", aggfunc="mean")
            if not pivot.empty and len(pivot) > 1:
                st.markdown("**Evolução do ROI-TR por reunião**")
                st.line_chart(pivot, height=280)

# ── Recomendações automáticas ─────────────────────────────────────────────────
st.markdown("---")
st.markdown("## 💡 Recomendações Automáticas")

critical = [m for m in roi_data if m.roi_tr < 2.0]
low_roi  = [m for m in roi_data if 2.0 <= m.roi_tr < 4.5]
high_trc = [m for m in roi_data if m.trc > 40]
no_reqs  = [m for m in roi_data if m.n_requirements == 0 and m.has_minutes]
no_act_done = [m for m in roi_data if m.n_actions_total > 0 and m.n_actions_complete == 0]

if not (critical or low_roi or high_trc or no_reqs or no_act_done):
    st.success(
        "✅ Nenhuma anomalia crítica detectada. O perfil de reuniões do projeto está dentro do esperado."
    )
else:
    if critical:
        nums = ", ".join(f"Reunião {m.meeting_number}" for m in critical)
        st.error(
            f"🔴 **ROI-TR Crítico** — {nums}\n\n"
            "Essas reuniões apresentaram muito baixo retorno em relação ao custo humano. "
            "Revise a pauta, assegure que haja decisões formais registradas e que os "
            "itens de ação tenham responsáveis e prazos definidos."
        )

    if low_roi:
        nums = ", ".join(f"Reunião {m.meeting_number}" for m in low_roi)
        st.warning(
            f"🟠 **ROI-TR Baixo** — {nums}\n\n"
            "Oportunidade de melhoria: aumentar a formalização de decisões e requisitos "
            "nessas reuniões. Implemente timeboxing por tópico e pré-requisitos de conhecimento."
        )

    if high_trc:
        nums = ", ".join(f"Reunião {m.meeting_number}" for m in high_trc)
        st.warning(
            f"🔴 **TRC elevado (>40 %)** — {nums}\n\n"
            "Alta taxa de retrabalho conceitual detectada: os mesmos conceitos estão sendo "
            "explicados repetidamente. Recomendação: enviar glossário/documentação prévia "
            "e designar um facilitador para cortar discussões redundantes."
        )

    if no_reqs:
        nums = ", ".join(f"Reunião {m.meeting_number}" for m in no_reqs)
        st.info(
            f"ℹ️ **Sem requisitos formalizados** — {nums}\n\n"
            "Reuniões com ata mas sem nenhum requisito extraído. Execute o pipeline completo "
            "para essas reuniões ou revise se há requisitos não capturados."
        )

    if no_act_done:
        nums = ", ".join(f"Reunião {m.meeting_number}" for m in no_act_done)
        st.info(
            f"ℹ️ **Itens de ação sem responsável/prazo** — {nums}\n\n"
            "Ações definidas mas sem responsável ou prazo na ata. Esses itens não contribuem "
            "para o ROI-TR. Atualize as atas ou reprocesse com MinutesBackfill."
        )

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "ROI-TR = DC × 1.000 / Custo × 1,5 · "
    "DC = Decisões + Ações_completas × 2 + Requisitos × 1,5 · "
    "Duração estimada: contagem de palavras ÷ 130 ppm · "
    "TRC: proxy linguístico de sinais de repetição na transcrição."
)
