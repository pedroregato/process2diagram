# pages/DatabaseOverview.py
# ─────────────────────────────────────────────────────────────────────────────
# Visão Geral do Banco de Dados — Process2Diagram
#
# Consolidado de todos os registros no Supabase:
#   • Métricas globais (projetos, reuniões, requisitos, tokens, BPMN, SBVR…)
#   • Breakdown por projeto
#   • Detalhe por reunião (presença de artefatos)
#   • Distribuição de requisitos (tipo × status × prioridade)
#   • Artefatos (BPMN, SBVR, embeddings)
#   • Integridade de dados (reuniões com campos ausentes)
#
# Zero chamadas LLM — consultas somente-leitura ao Supabase.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import pandas as pd
import streamlit as st

from ui.auth_gate import apply_auth_gate
from modules.supabase_client import supabase_configured, get_supabase_client
from modules.cost_estimator import PROVIDER_PRICING, cost_for_tokens

apply_auth_gate()

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# 🗄️ Visão Geral do Banco de Dados")
st.caption(
    "Consolidado de todos os registros armazenados no Supabase — "
    "projetos, reuniões, requisitos, BPMN, SBVR e embeddings. "
    "Nenhum dado é modificado por esta página."
)

if not supabase_configured():
    st.error("⚙️ Supabase não configurado. Adicione as credenciais em Settings → Secrets.")
    st.stop()

db = get_supabase_client()
if not db:
    st.error("Não foi possível conectar ao Supabase.")
    st.stop()

# Quick connectivity probe — tries to count projects rows
try:
    _probe = db.table("projects").select("id", count="exact").limit(1).execute()
    _probe_count = _probe.count if hasattr(_probe, "count") else "?"
    st.caption(f"✅ Supabase conectado · projetos acessíveis (count={_probe_count})")
except Exception as _probe_err:
    st.warning(
        f"⚠️ Supabase conectado mas a tabela **projects** não está acessível: `{_probe_err}`  \n"
        "Verifique se a tabela existe e se a chave possui permissão SELECT."
    )

# Refresh button (top-right)
_, _col_r = st.columns([6, 1])
with _col_r:
    if st.button("🔄 Atualizar", use_container_width=True, key="db_refresh"):
        st.rerun()

# ── Load all data ─────────────────────────────────────────────────────────────
_load_errors: list[str] = []

with st.spinner("Carregando dados do banco…"):

    def _safe(fn, label: str = ""):
        try:
            result = fn()
            return result if result is not None else []
        except Exception as exc:
            if label:
                _load_errors.append(f"**{label}**: `{exc}`")
            return []

    projects = _safe(
        lambda: db.table("projects")
                  .select("*")
                  .order("name").execute().data or [],
        "projects",
    )

    meetings = _safe(
        lambda: db.table("meetings")
                  .select(
                      "id, project_id, meeting_number, title, meeting_date, "
                      "created_at, total_tokens, llm_provider, "
                      "transcript_clean, transcript_raw, minutes_md"
                  ).order("created_at").execute().data or [],
        "meetings",
    )

    requirements = _safe(
        lambda: db.table("requirements")
                  .select("id, project_id, first_meeting_id, req_type, status, priority, created_at")
                  .execute().data or [],
        "requirements",
    )

    sbvr_terms = _safe(
        lambda: db.table("sbvr_terms")
                  .select("id, project_id, meeting_id, term, category")
                  .execute().data or [],
        "sbvr_terms",
    )

    sbvr_rules = _safe(
        lambda: db.table("sbvr_rules")
                  .select("id, project_id, meeting_id, rule_type")
                  .execute().data or [],
        "sbvr_rules",
    )

    bpmn_ok = False
    bpmn_processes: list[dict] = []
    bpmn_versions: list[dict] = []
    try:
        bpmn_processes = db.table("bpmn_processes").select("id, project_id, name, status").execute().data or []
        bpmn_versions  = db.table("bpmn_versions").select("id, process_id, meeting_id, created_at").execute().data or []
        bpmn_ok = True
    except Exception:
        pass

    chunks_ok = False
    transcript_chunks: list[dict] = []
    try:
        transcript_chunks = db.table("transcript_chunks").select("id, project_id, meeting_id").execute().data or []
        chunks_ok = True
    except Exception:
        pass

    batch_log = _safe(
        lambda: db.table("batch_log")
                  .select("id, project_id, status, processed_at, filename")
                  .execute().data or [],
        "batch_log",
    )

# ── Show load errors (if any) ─────────────────────────────────────────────────
if _load_errors:
    with st.expander(f"⚠️ {len(_load_errors)} erro(s) ao carregar tabelas — clique para ver", expanded=True):
        for err in _load_errors:
            st.markdown(f"- {err}")
        st.caption(
            "Possíveis causas: tabela inexistente, coluna ausente, "
            "RLS bloqueando acesso ou chave Supabase sem permissão de leitura."
        )

# ── Build lookup indexes ───────────────────────────────────────────────────────
proj_map = {p["id"]: p for p in projects}
meeting_map = {m["id"]: m for m in meetings}

meeting_ids_with_chunks = {r["meeting_id"] for r in transcript_chunks}
meeting_ids_with_bpmn   = {v["meeting_id"] for v in bpmn_versions if v.get("meeting_id")}

# Per-project aggregates
_zero = lambda: {
    "meetings": 0, "tokens": 0, "req": 0,
    "sbvr_terms": 0, "sbvr_rules": 0, "bpmn_procs": 0,
    "with_transcript": 0, "with_minutes": 0,
    "with_embeddings": 0, "with_bpmn": 0, "chunks": 0,
}
proj_stats: dict[str, dict] = {p["id"]: _zero() for p in projects}

for m in meetings:
    pid = m.get("project_id")
    if pid not in proj_stats:
        proj_stats[pid] = _zero()
    ps = proj_stats[pid]
    ps["meetings"] += 1
    ps["tokens"]   += m.get("total_tokens") or 0
    if m.get("transcript_clean") or m.get("transcript_raw"):
        ps["with_transcript"] += 1
    if m.get("minutes_md"):
        ps["with_minutes"] += 1
    if m["id"] in meeting_ids_with_chunks:
        ps["with_embeddings"] += 1
    if m["id"] in meeting_ids_with_bpmn:
        ps["with_bpmn"] += 1

for r in requirements:
    pid = r.get("project_id")
    if pid in proj_stats:
        proj_stats[pid]["req"] += 1

for t in sbvr_terms:
    pid = t.get("project_id")
    if pid in proj_stats:
        proj_stats[pid]["sbvr_terms"] += 1

for r in sbvr_rules:
    pid = r.get("project_id")
    if pid in proj_stats:
        proj_stats[pid]["sbvr_rules"] += 1

for p in bpmn_processes:
    pid = p.get("project_id")
    if pid in proj_stats:
        proj_stats[pid]["bpmn_procs"] += 1

for c in transcript_chunks:
    pid = c.get("project_id")
    if pid in proj_stats:
        proj_stats[pid]["chunks"] += 1

# Global totals
total_projects  = len(projects)
total_meetings  = len(meetings)
total_req       = len(requirements)
total_tokens    = sum(m.get("total_tokens") or 0 for m in meetings)
total_terms     = len(sbvr_terms)
total_rules     = len(sbvr_rules)
total_bpmn_proc = len(bpmn_processes)
total_bpmn_ver  = len(bpmn_versions)
total_chunks    = len(transcript_chunks)

# Estimated cost (DeepSeek default if provider unknown)
_fallback_prov = list(PROVIDER_PRICING.keys())[0]
total_cost = sum(
    cost_for_tokens(
        int((m.get("total_tokens") or 0) * 0.70),
        int((m.get("total_tokens") or 0) * 0.30),
        m.get("llm_provider") if (m.get("llm_provider") or "").strip() in PROVIDER_PRICING
        else _fallback_prov,
    )
    for m in meetings
)

# ── Global metrics bar ────────────────────────────────────────────────────────
st.markdown("---")
c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
c1.metric("📁 Projetos",    total_projects)
c2.metric("📅 Reuniões",    total_meetings)
c3.metric("📋 Requisitos",  total_req)
c4.metric("🔢 Tokens",      f"{total_tokens:,}")
c5.metric("💰 Custo est.",   f"${total_cost:.4f}")
c6.metric("🔧 Proc. BPMN",  total_bpmn_proc if bpmn_ok else "—")
c7.metric("📚 Chunks",       f"{total_chunks:,}" if chunks_ok else "—")

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tab_proj, tab_meet, tab_req, tab_art, tab_int = st.tabs([
    "📊 Por Projeto",
    "📅 Reuniões",
    "📋 Requisitos",
    "🔧 Artefatos",
    "⚠️ Integridade",
])

# ╔══════════════════════════════════════════════════════╗
# ║  TAB 1 — Por Projeto                                ║
# ╚══════════════════════════════════════════════════════╝
with tab_proj:
    if not projects:
        st.info("Nenhum projeto encontrado.")
    else:
        rows = []
        for p in projects:
            pid  = p["id"]
            ps   = proj_stats.get(pid, _zero())
            n_m  = ps["meetings"]
            rows.append({
                "Projeto":         p.get("name", "—"),
                "Sigla":           p.get("sigla") or "—",
                "Reuniões":        n_m,
                "Requisitos":      ps["req"],
                "Tokens":          f'{ps["tokens"]:,}',
                "Transcrições":    f'{ps["with_transcript"]}/{n_m}',
                "Atas":            f'{ps["with_minutes"]}/{n_m}',
                "Embeddings":      f'{ps["with_embeddings"]}/{n_m}' if chunks_ok else "—",
                "BPMN":            f'{ps["with_bpmn"]}/{n_m}' if bpmn_ok else "—",
                "SBVR Termos":     ps["sbvr_terms"],
                "SBVR Regras":     ps["sbvr_rules"],
                "Proc. BPMN":      ps["bpmn_procs"] if bpmn_ok else "—",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # Summary cards per project
        st.markdown("---")
        for p in projects:
            pid = p["id"]
            ps  = proj_stats.get(pid, _zero())
            n_m = ps["meetings"]
            with st.expander(
                f"**{p.get('name')}**"
                + (f" ({p.get('sigla')})" if p.get("sigla") else ""),
                expanded=False,
            ):
                col_a, col_b, col_c, col_d = st.columns(4)
                col_a.metric("Reuniões", n_m)
                col_b.metric("Requisitos", ps["req"])
                col_c.metric("Tokens", f"{ps['tokens']:,}")
                col_d.metric(
                    "Custo est.",
                    f"${sum(cost_for_tokens(int((m.get('total_tokens') or 0)*.7), int((m.get('total_tokens') or 0)*.3), m.get('llm_provider') if (m.get('llm_provider') or '').strip() in PROVIDER_PRICING else _fallback_prov) for m in meetings if m.get('project_id') == pid):.4f}",
                )
                col_e, col_f, col_g, col_h = st.columns(4)
                col_e.metric("Com transcrição", f"{ps['with_transcript']}/{n_m}")
                col_f.metric("Com ata",          f"{ps['with_minutes']}/{n_m}")
                col_g.metric("Com embeddings",   f"{ps['with_embeddings']}/{n_m}" if chunks_ok else "—")
                col_h.metric("Com BPMN",          f"{ps['with_bpmn']}/{n_m}" if bpmn_ok else "—")

# ╔══════════════════════════════════════════════════════╗
# ║  TAB 2 — Reuniões                                   ║
# ╚══════════════════════════════════════════════════════╝
with tab_meet:
    if not meetings:
        st.info("Nenhuma reunião encontrada.")
    else:
        # Optional project filter
        all_proj_names = ["(todos)"] + [p["name"] for p in projects]
        sel_proj = st.selectbox("Filtrar por projeto", all_proj_names, key="dbo_meet_proj")

        rows = []
        for m in meetings:
            pid   = m.get("project_id")
            pname = (proj_map.get(pid) or {}).get("name") or "—"
            if sel_proj != "(todos)" and pname != sel_proj:
                continue
            tok   = m.get("total_tokens") or 0
            prov  = (m.get("llm_provider") or "").strip() or "—"
            rows.append({
                "Projeto":      pname,
                "Nº":           m.get("meeting_number") or "—",
                "Título":       m.get("title") or "(sem título)",
                "Data":         str(m.get("meeting_date") or "—"),
                "Provedor":     prov,
                "Tokens":       f"{tok:,}" if tok else "—",
                "Transcrição":  "✅" if (m.get("transcript_clean") or m.get("transcript_raw")) else "❌",
                "Ata":          "✅" if m.get("minutes_md") else "❌",
                "Embeddings":   "✅" if m["id"] in meeting_ids_with_chunks else ("❌" if chunks_ok else "—"),
                "BPMN":         "✅" if m["id"] in meeting_ids_with_bpmn   else ("❌" if bpmn_ok   else "—"),
            })

        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            st.caption(f"{len(rows)} reunião(ões) exibida(s).")
        else:
            st.info("Nenhuma reunião para o filtro selecionado.")

# ╔══════════════════════════════════════════════════════╗
# ║  TAB 3 — Requisitos                                 ║
# ╚══════════════════════════════════════════════════════╝
with tab_req:
    if not requirements:
        st.info("Nenhum requisito encontrado.")
    else:
        sel_proj_req = st.selectbox(
            "Filtrar por projeto",
            ["(todos)"] + [p["name"] for p in projects],
            key="dbo_req_proj",
        )

        def _req_proj_filter(r: dict) -> bool:
            if sel_proj_req == "(todos)":
                return True
            pid = r.get("project_id")
            return (proj_map.get(pid) or {}).get("name") == sel_proj_req

        reqs_f = [r for r in requirements if _req_proj_filter(r)]

        if not reqs_f:
            st.info("Nenhum requisito para o filtro selecionado.")
        else:
            c1, c2, c3 = st.columns(3)

            # By type
            type_counts = defaultdict(int)
            for r in reqs_f:
                type_counts[r.get("req_type") or "—"] += 1
            df_type = pd.DataFrame(
                [{"Tipo": k, "Qtd": v} for k, v in sorted(type_counts.items(), key=lambda x: -x[1])]
            )

            # By status
            status_counts = defaultdict(int)
            for r in reqs_f:
                status_counts[r.get("status") or "—"] += 1
            df_status = pd.DataFrame(
                [{"Status": k, "Qtd": v} for k, v in sorted(status_counts.items(), key=lambda x: -x[1])]
            )

            # By priority
            prio_counts = defaultdict(int)
            for r in reqs_f:
                prio_counts[r.get("priority") or "—"] += 1
            df_prio = pd.DataFrame(
                [{"Prioridade": k, "Qtd": v} for k, v in sorted(prio_counts.items(), key=lambda x: -x[1])]
            )

            with c1:
                st.markdown(f"**Por tipo** · {len(reqs_f)} total")
                st.dataframe(df_type, use_container_width=True, hide_index=True)
            with c2:
                st.markdown("**Por status**")
                st.dataframe(df_status, use_container_width=True, hide_index=True)
            with c3:
                st.markdown("**Por prioridade**")
                st.dataframe(df_prio, use_container_width=True, hide_index=True)

            # Cross-tab: type × status
            st.markdown("#### Tipo × Status")
            pivot_rows: list[dict] = []
            for rtype in sorted(type_counts.keys()):
                row: dict = {"Tipo": rtype}
                for status in sorted(status_counts.keys()):
                    row[status] = sum(
                        1 for r in reqs_f
                        if (r.get("req_type") or "—") == rtype
                        and (r.get("status") or "—") == status
                    )
                pivot_rows.append(row)
            st.dataframe(pd.DataFrame(pivot_rows), use_container_width=True, hide_index=True)

            # Bar chart
            try:
                import altair as alt
                chart = (
                    alt.Chart(df_type)
                    .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
                    .encode(
                        x=alt.X("Tipo:N", sort="-y", title=None),
                        y=alt.Y("Qtd:Q", title="Quantidade"),
                        color=alt.Color("Tipo:N", legend=None,
                                        scale=alt.Scale(scheme="tableau10")),
                        tooltip=["Tipo:N", "Qtd:Q"],
                    )
                    .properties(height=220, title="Requisitos por tipo")
                )
                st.altair_chart(chart, use_container_width=True)
            except ImportError:
                pass

# ╔══════════════════════════════════════════════════════╗
# ║  TAB 4 — Artefatos (BPMN, SBVR, Embeddings)        ║
# ╚══════════════════════════════════════════════════════╝
with tab_art:
    # ── BPMN ──────────────────────────────────────────────────────────────────
    st.markdown("### 🔧 BPMN")
    if not bpmn_ok:
        st.warning("Tabelas `bpmn_processes` / `bpmn_versions` não encontradas no banco.")
    elif not bpmn_processes:
        st.info("Nenhum processo BPMN registrado.")
    else:
        # Build BPMN table
        versions_per_proc = defaultdict(int)
        for v in bpmn_versions:
            versions_per_proc[v.get("process_id")] += 1

        bpmn_rows = []
        for bp in bpmn_processes:
            pid   = bp.get("project_id")
            pname = (proj_map.get(pid) or {}).get("name") or "—"
            bpmn_rows.append({
                "Projeto":  pname,
                "Processo": bp.get("name") or "—",
                "Status":   bp.get("status") or "—",
                "Versões":  versions_per_proc.get(bp["id"], 0),
            })
        st.dataframe(pd.DataFrame(bpmn_rows), use_container_width=True, hide_index=True)
        st.caption(f"{total_bpmn_proc} processo(s) · {total_bpmn_ver} versão(ões) total")

    st.markdown("---")

    # ── SBVR ──────────────────────────────────────────────────────────────────
    st.markdown("### 📚 SBVR")
    col_t, col_r_ = st.columns(2)
    with col_t:
        st.markdown(f"**Termos ({total_terms})**")
        if sbvr_terms:
            cat_counts = defaultdict(int)
            for t in sbvr_terms:
                cat_counts[t.get("category") or "—"] += 1
            df_cat = pd.DataFrame(
                [{"Categoria": k, "Qtd": v}
                 for k, v in sorted(cat_counts.items(), key=lambda x: -x[1])]
            )
            st.dataframe(df_cat, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum termo SBVR registrado.")
    with col_r_:
        st.markdown(f"**Regras ({total_rules})**")
        if sbvr_rules:
            rtype_counts = defaultdict(int)
            for r in sbvr_rules:
                rtype_counts[r.get("rule_type") or "—"] += 1
            df_rt = pd.DataFrame(
                [{"Tipo de Regra": k, "Qtd": v}
                 for k, v in sorted(rtype_counts.items(), key=lambda x: -x[1])]
            )
            st.dataframe(df_rt, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma regra SBVR registrada.")

    st.markdown("---")

    # ── Embeddings ────────────────────────────────────────────────────────────
    st.markdown("### 🔮 Embeddings (pgvector)")
    if not chunks_ok:
        st.warning("Tabela `transcript_chunks` não encontrada. Execute o schema SQL para habilitá-la.")
    elif not transcript_chunks:
        st.info("Nenhum chunk de embedding registrado.")
    else:
        chunks_per_meeting: dict[str, int] = defaultdict(int)
        for c in transcript_chunks:
            chunks_per_meeting[c.get("meeting_id")] += 1

        emb_rows = []
        for m in meetings:
            mid   = m["id"]
            pid   = m.get("project_id")
            pname = (proj_map.get(pid) or {}).get("name") or "—"
            n_ch  = chunks_per_meeting.get(mid, 0)
            emb_rows.append({
                "Projeto":  pname,
                "Nº":       m.get("meeting_number") or "—",
                "Reunião":  m.get("title") or "(sem título)",
                "Chunks":   n_ch,
                "Indexado": "✅" if n_ch > 0 else "❌",
            })
        df_emb = pd.DataFrame(emb_rows)
        indexed = sum(1 for r in emb_rows if r["Chunks"] > 0)
        st.metric("Reuniões indexadas", f"{indexed}/{len(emb_rows)}")
        st.dataframe(df_emb, use_container_width=True, hide_index=True)
        st.caption(f"Total: {total_chunks:,} chunks · {indexed} reuniões indexadas")

    st.markdown("---")

    # ── Tokens & Provedores ───────────────────────────────────────────────────
    st.markdown("### 💰 Tokens & Provedores LLM")
    if not meetings:
        st.info("Nenhuma reunião encontrada.")
    else:
        prov_stats: dict[str, dict] = defaultdict(lambda: {"meetings": 0, "tokens": 0})
        for m in meetings:
            prov = (m.get("llm_provider") or "").strip() or f"(desconhecido → {_fallback_prov})"
            prov_stats[prov]["meetings"] += 1
            prov_stats[prov]["tokens"]   += m.get("total_tokens") or 0

        token_rows = []
        for prov, ps in sorted(prov_stats.items(), key=lambda x: -x[1]["tokens"]):
            tok  = ps["tokens"]
            prov_key = prov if prov in PROVIDER_PRICING else _fallback_prov
            cost = cost_for_tokens(int(tok * 0.70), int(tok * 0.30), prov_key)
            token_rows.append({
                "Provedor":   prov,
                "Reuniões":   ps["meetings"],
                "Tokens":     f"{tok:,}",
                "Custo est.": f"${cost:.4f}",
            })
        st.dataframe(pd.DataFrame(token_rows), use_container_width=True, hide_index=True)
        st.caption(
            f"Total: {total_tokens:,} tokens · Custo estimado: ${total_cost:.4f} "
            f"(split 70% entrada / 30% saída)"
        )

# ╔══════════════════════════════════════════════════════╗
# ║  TAB 5 — Integridade de Dados                       ║
# ╚══════════════════════════════════════════════════════╝
with tab_int:

    # ── Build issues ──────────────────────────────────────────────────────────
    _FIELDS = ["transcrição", "ata", "embeddings", "BPMN", "tokens", "provedor LLM"]
    _N_FIELDS = len(_FIELDS)

    issues: list[dict] = []
    _meeting_issues: dict[str, list[str]] = {}   # meeting_id → missing list
    for m in meetings:
        pid   = m.get("project_id")
        pname = (proj_map.get(pid) or {}).get("name") or "—"
        mid   = m["id"]
        missing: list[str] = []
        if not (m.get("transcript_clean") or m.get("transcript_raw")):
            missing.append("transcrição")
        if not m.get("minutes_md"):
            missing.append("ata")
        if chunks_ok and mid not in meeting_ids_with_chunks:
            missing.append("embeddings")
        if bpmn_ok and mid not in meeting_ids_with_bpmn:
            missing.append("BPMN")
        if not (m.get("total_tokens") or 0):
            missing.append("tokens")
        if not (m.get("llm_provider") or "").strip():
            missing.append("provedor LLM")
        _meeting_issues[mid] = missing
        if missing:
            issues.append({
                "_mid":      mid,
                "_missing":  missing,
                "Projeto":   pname,
                "Nº":        m.get("meeting_number") or "?",
                "Reunião":   m.get("title") or "(sem título)",
                "Data":      str(m.get("meeting_date") or "—"),
                "Ausentes":  ", ".join(missing),
                "Score":     f"{_N_FIELDS - len(missing)}/{_N_FIELDS}",
            })

    field_counts: dict[str, int] = defaultdict(int)
    for row in issues:
        for fld in row["_missing"]:
            field_counts[fld] += 1

    # ── Health Score ──────────────────────────────────────────────────────────
    _total_slots   = total_meetings * _N_FIELDS
    _missing_slots = sum(len(v) for v in _meeting_issues.values())
    _health_pct    = round(100 * (1 - _missing_slots / _total_slots)) if _total_slots else 100
    _complete       = sum(1 for v in _meeting_issues.values() if not v)

    st.markdown("#### 📊 Saúde Geral")
    _hc1, _hc2, _hc3, _hc4 = st.columns(4)
    _hc1.metric("Saúde geral",        f"{_health_pct}%",
                delta=None, help="% dos campos preenchidos em todas as reuniões")
    _hc2.metric("Reuniões completas", f"{_complete}/{total_meetings}")
    _hc3.metric("Com problemas",      len(issues))
    _hc4.metric("Campos ausentes",    _missing_slots)

    _bar_filled = "█" * (_health_pct // 5)
    _bar_empty  = "░" * (20 - _health_pct // 5)
    _bar_color  = "🟢" if _health_pct >= 90 else ("🟡" if _health_pct >= 70 else "🔴")
    st.markdown(
        f"{_bar_color} `{_bar_filled}{_bar_empty}` **{_health_pct}%** integridade"
    )

    st.markdown("---")

    if not issues:
        st.success("✅ Todas as reuniões possuem os campos principais preenchidos.")
    else:
        st.warning(
            f"⚠️ **{len(issues)} reunião(ões) com dados ausentes** de {total_meetings} no total."
        )

        # Campo × contagem
        st.markdown("#### Campos ausentes por frequência")
        _fc_cols = st.columns(min(len(field_counts), 6))
        _fc_items = sorted(field_counts.items(), key=lambda x: -x[1])
        for _i, (_fld, _cnt) in enumerate(_fc_items):
            _icon = {"transcrição":"📝","ata":"📋","embeddings":"🔮",
                     "BPMN":"🔧","tokens":"🔢","provedor LLM":"⚙️"}.get(_fld, "❓")
            _fc_cols[_i % len(_fc_cols)].metric(f"{_icon} {_fld.capitalize()}", _cnt)

        # Detalhe por reunião
        with st.expander("📋 Detalhes por reunião", expanded=False):
            df_issues = pd.DataFrame(
                [{k: v for k, v in r.items() if not k.startswith("_")} for r in issues]
            )
            st.dataframe(df_issues, use_container_width=True, hide_index=True)

        # ══════════════════════════════════════════════════════════════════════
        # AÇÕES DE CORREÇÃO
        # ══════════════════════════════════════════════════════════════════════
        st.markdown("---")
        st.markdown("### 🔧 Corrigir Problemas")

        # ── Fix 1: Provedor LLM ───────────────────────────────────────────────
        if field_counts.get("provedor LLM", 0):
            with st.expander(
                f"⚙️ Definir provedor LLM ausente · {field_counts['provedor LLM']} reunião(ões)",
                expanded=True,
            ):
                _affected_prov = [
                    m for m in meetings
                    if not (m.get("llm_provider") or "").strip()
                ]
                st.caption(
                    "Reuniões processadas antes do campo `llm_provider` ser registrado. "
                    "Definir o provedor correto melhora a estimativa de custo."
                )
                _prov_names = list(PROVIDER_PRICING.keys())
                _chosen_prov = st.selectbox(
                    "Provedor a atribuir", _prov_names, key="fix_prov_sel"
                )
                _prov_preview = [
                    {
                        "Nº": m.get("meeting_number") or "—",
                        "Reunião": m.get("title") or "(sem título)",
                        "Data": str(m.get("meeting_date") or "—"),
                    }
                    for m in _affected_prov
                ]
                st.dataframe(
                    pd.DataFrame(_prov_preview), use_container_width=True, hide_index=True
                )
                if st.button(
                    f"✅ Atribuir '{_chosen_prov}' a {len(_affected_prov)} reunião(ões)",
                    key="fix_prov_btn",
                ):
                    _ok_count = 0
                    for _m in _affected_prov:
                        try:
                            db.table("meetings").update(
                                {"llm_provider": _chosen_prov}
                            ).eq("id", _m["id"]).execute()
                            _ok_count += 1
                        except Exception as _e:
                            st.error(f"Erro ao atualizar reunião {_m.get('title')}: {_e}")
                    if _ok_count:
                        st.success(f"✅ {_ok_count} reunião(ões) atualizadas.")
                        st.rerun()

        # ── Fix 2: Embeddings ─────────────────────────────────────────────────
        if field_counts.get("embeddings", 0):
            with st.expander(
                f"🔮 Gerar embeddings ausentes · {field_counts['embeddings']} reunião(ões)",
                expanded=True,
            ):
                _affected_emb = [
                    m for m in meetings
                    if chunks_ok
                    and m["id"] not in meeting_ids_with_chunks
                    and (m.get("transcript_clean") or m.get("transcript_raw"))
                ]
                _no_transcript = field_counts.get("embeddings", 0) - len(_affected_emb)
                if _no_transcript:
                    st.warning(
                        f"{_no_transcript} reunião(ões) não têm transcrição armazenada "
                        "e não podem ser indexadas."
                    )
                if not _affected_emb:
                    st.info("Nenhuma reunião indexável sem embedding encontrada.")
                else:
                    st.caption(
                        f"{len(_affected_emb)} reunião(ões) com transcrição mas sem embedding. "
                        "Informe a chave do provedor de embedding para gerar."
                    )
                    _emb_provider = st.selectbox(
                        "Provedor de embedding",
                        ["Google Gemini", "OpenAI"],
                        key="fix_emb_prov",
                    )
                    _emb_key = st.text_input(
                        "API Key", type="password", key="fix_emb_key",
                        help="Google AI Studio key (Gemini) ou OpenAI key.",
                    )
                    _emb_preview = [
                        {
                            "Nº": m.get("meeting_number") or "—",
                            "Reunião": m.get("title") or "(sem título)",
                            "Projeto": (proj_map.get(m.get("project_id")) or {}).get("name") or "—",
                        }
                        for m in _affected_emb
                    ]
                    st.dataframe(
                        pd.DataFrame(_emb_preview), use_container_width=True, hide_index=True
                    )

                    if st.button(
                        f"⚡ Gerar embeddings para {len(_affected_emb)} reunião(ões)",
                        key="fix_emb_btn",
                        disabled=not _emb_key.strip(),
                    ):
                        try:
                            from modules.embeddings import chunk_text, embed_text
                            from core.project_store import save_transcript_embeddings
                        except ImportError as _ie:
                            st.error(f"Módulo de embeddings não disponível: {_ie}")
                            st.stop()

                        _emb_ok = 0
                        _emb_fail = 0
                        _prog = st.progress(0, text="Iniciando…")
                        for _i, _m in enumerate(_affected_emb):
                            _title = _m.get("title") or f"Reunião {_i+1}"
                            _prog.progress(
                                (_i) / len(_affected_emb),
                                text=f"Processando: {_title} ({_i+1}/{len(_affected_emb)})",
                            )
                            _text = _m.get("transcript_clean") or _m.get("transcript_raw") or ""
                            try:
                                _chunks = chunk_text(_text)
                                if not _chunks:
                                    st.warning(f"⚠️ {_title}: nenhum chunk gerado.")
                                    _emb_fail += 1
                                    continue
                                _embeddings = [
                                    embed_text(_c, _emb_key.strip(), _emb_provider)
                                    for _c in _chunks
                                ]
                                save_transcript_embeddings(
                                    _m["id"],
                                    _m.get("project_id"),
                                    _chunks,
                                    _embeddings,
                                )
                                _emb_ok += 1
                            except Exception as _e:
                                st.error(f"❌ {_title}: {_e}")
                                _emb_fail += 1
                        _prog.progress(1.0, text="Concluído.")
                        if _emb_ok:
                            st.success(
                                f"✅ Embeddings gerados para {_emb_ok} reunião(ões)."
                                + (f" · {_emb_fail} falha(s)." if _emb_fail else "")
                            )
                            st.rerun()
                        else:
                            st.error("Nenhum embedding gerado. Verifique a chave e tente novamente.")

        # ── Fix 3: Ata ausente → MinutesBackfill ─────────────────────────────
        if field_counts.get("ata", 0):
            with st.expander(
                f"📋 Gerar atas ausentes · {field_counts['ata']} reunião(ões)",
                expanded=False,
            ):
                st.info(
                    f"**{field_counts['ata']} reunião(ões) sem ata gerada.** "
                    "Use a página Minutes Backfill para gerar as atas retroativamente "
                    "(requer API key LLM e transcrição armazenada)."
                )
                st.page_link("pages/MinutesBackfill.py", label="→ Ir para Minutes Backfill", icon="📝")

        # ── Fix 4: BPMN ausente → BpmnBackfill ───────────────────────────────
        if field_counts.get("BPMN", 0):
            with st.expander(
                f"🔧 Gerar BPMN ausente · {field_counts['BPMN']} reunião(ões)",
                expanded=False,
            ):
                st.info(
                    f"**{field_counts['BPMN']} reunião(ões) sem diagrama BPMN.** "
                    "Use a página BPMN Backfill para gerar os diagramas retroativamente "
                    "(requer API key LLM e transcrição armazenada)."
                )
                st.page_link("pages/BpmnBackfill.py", label="→ Ir para BPMN Backfill", icon="🔧")

        # ── Fix 5: Transcrição ausente → TranscriptBackfill ───────────────────
        if field_counts.get("transcrição", 0):
            with st.expander(
                f"📝 Transcrições ausentes · {field_counts['transcrição']} reunião(ões)",
                expanded=False,
            ):
                st.info(
                    f"**{field_counts['transcrição']} reunião(ões) sem transcrição armazenada.** "
                    "Use a página Transcript Backfill para fazer o upload dos arquivos originais."
                )
                st.page_link(
                    "pages/TranscriptBackfill.py",
                    label="→ Ir para Transcript Backfill",
                    icon="📑",
                )

    # ── Batch log summary ──────────────────────────────────────────────────────
    if batch_log:
        st.markdown("---")
        st.markdown("#### 🔄 Histórico do Batch Runner")
        status_counts_bl: dict[str, int] = defaultdict(int)
        for row in batch_log:
            status_counts_bl[row.get("status") or "—"] += 1

        col_ok, col_err, col_tot = st.columns(3)
        col_ok.metric("✅ Sucesso",   status_counts_bl.get("success", 0))
        col_err.metric("❌ Erro",      status_counts_bl.get("error", 0))
        col_tot.metric("Total batch", len(batch_log))

st.markdown("---")
st.caption(
    "🗄️ Dados lidos diretamente do Supabase. Clique em **🔄 Atualizar** para recarregar. "
    "As ações de correção na aba Integridade modificam dados no banco."
)
