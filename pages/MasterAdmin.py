# pages/MasterAdmin.py
# ─────────────────────────────────────────────────────────────────────────────
# Painel de administração master — Process2Diagram
#
# Página única e contextual: seleciona o domínio no topo e todas as operações
# aparecem abaixo — usuários, projetos e configurações daquele domínio.
# Acessível apenas para usuários com role == 'master'.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations
import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st
from ui.auth_gate import apply_auth_gate

apply_auth_gate()

# ── Guard de perfil ────────────────────────────────────────────────────────────
if st.session_state.get("_role") != "master":
    st.error("🚫 Acesso restrito. Esta página requer o perfil **master**.")
    st.stop()

from modules.tenant_auth import (
    list_all_tenants, list_users_by_tenant,
    create_tenant, create_user,
    toggle_tenant_active, toggle_user_active,
    update_user_role, reset_user_password,
    update_user_accounts,
)
from modules.tenant_config import (
    load_all_config, save_config, delete_config,
    mask_key, PROVIDER_KEY_MAP, PREFS_MAP, PREFS_LABELS,
)
from core.project_store import list_projects, list_contexts, create_project

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("# 🛡️ Master Administration")
st.caption(
    f"**{st.session_state.get('_usuario_nome', '')}** "
    f"· domínio `{st.session_state.get('_domain', '')}` · perfil `master`"
)

# Mensagens persistidas (sobrevivem ao st.rerun())
if "_master_ok" in st.session_state:
    st.success(st.session_state.pop("_master_ok"))
if "_master_err" in st.session_state:
    st.error(st.session_state.pop("_master_err"))

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# SEÇÃO 1 — Visão geral + Domínios
# ══════════════════════════════════════════════════════════════════════════════
tenants = list_all_tenants()

# Métricas rápidas — globais (todos os tenants)
from core.project_store import list_contexts as _list_ctx_all
total_users    = sum(len(list_users_by_tenant(t["id"])[0]) for t in tenants)
total_projects = len(_list_ctx_all()) or 0  # sem filtro de tenant — total global
c1, c2, c3 = st.columns(3)
c1.metric("Domínios",  len(tenants))
c2.metric("Usuários",  total_users)
c3.metric("Projetos",  total_projects)

st.markdown("---")

# ── Criar novo domínio ─────────────────────────────────────────────────────────
with st.expander("➕ Novo Domínio", expanded=len(tenants) == 0):
    ca, cb, cc = st.columns([2, 3, 1])
    slug_inp = ca.text_input("Slug", key="m_slug", placeholder="acme")
    name_inp = cb.text_input("Nome completo", key="m_name", placeholder="Acme Corporation")
    cc.write(""); cc.write("")
    if cc.button("Criar", key="m_create_tenant", type="primary", use_container_width=True):
        ok, msg = create_tenant(slug_inp, name_inp)
        st.session_state["_master_ok" if ok else "_master_err"] = msg
        st.rerun()

# ── Seletor de domínio ─────────────────────────────────────────────────────────
if not tenants:
    st.info("Nenhum domínio cadastrado. Crie o primeiro acima.")
    st.stop()

tenant_opts  = {f"{t['domain_slug']}  —  {t['display_name']}": t for t in tenants}
sel_label    = st.selectbox("🌐 Domínio ativo", list(tenant_opts.keys()), key="m_sel_domain")
sel_tenant   = tenant_opts[sel_label]
sel_tid      = sel_tenant["id"]
sel_slug     = sel_tenant["domain_slug"]
sel_name     = sel_tenant["display_name"]
is_active    = sel_tenant["active"]

# Contextos do domínio selecionado (filtrado por sel_tid)
all_projects = list_contexts(tenant_id=sel_tid) if sel_tid else []

col_name, col_status, col_toggle = st.columns([4, 1, 1])
col_name.markdown(f"### {sel_name}")
col_status.markdown(f"{'🟢 Ativo' if is_active else '🔴 Inativo'}")
lbl_tog = "Desativar" if is_active else "Ativar"
if col_toggle.button(lbl_tog, key="m_tog_domain", use_container_width=True):
    if toggle_tenant_active(sel_tid, not is_active):
        st.session_state["_master_ok"] = f"Domínio '{sel_slug}' {lbl_tog.lower()}do."
    else:
        st.session_state["_master_err"] = "Erro ao alterar status do domínio."
    st.rerun()

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# SEÇÃO 2 — Usuários do domínio selecionado
# ══════════════════════════════════════════════════════════════════════════════
users, users_err = list_users_by_tenant(sel_tid)
st.markdown(f"### 👥 Usuários — {sel_slug} ({len(users)})")

if users_err:
    st.error(f"⚠️ Não foi possível carregar os usuários: `{users_err}`")
    with st.expander("🔍 Possíveis causas", expanded=True):
        st.markdown(
            "**1. Colunas opcionais ausentes** — as colunas `google_account` e `ms_teams_account` "
            "podem não ter sido criadas ainda. Execute no Supabase SQL Editor:\n"
            "```sql\n"
            "ALTER TABLE tenant_users ADD COLUMN IF NOT EXISTS google_account TEXT;\n"
            "ALTER TABLE tenant_users ADD COLUMN IF NOT EXISTS ms_teams_account TEXT;\n"
            "```\n\n"
            "**2. RLS bloqueando a leitura** — se o Supabase usa a chave `anon` (não `service_role`), "
            "o RLS pode estar impedindo o SELECT. Adicione uma policy permissiva ou use a chave `service_role` "
            "em `st.secrets[\"supabase\"][\"key\"]`:\n"
            "```sql\n"
            "ALTER TABLE tenant_users ENABLE ROW LEVEL SECURITY;\n"
            "CREATE POLICY \"allow_all\" ON tenant_users USING (true) WITH CHECK (true);\n"
            "```"
        )

with st.expander("➕ Novo Usuário", expanded=False):
    ua, ub = st.columns(2)
    new_login  = ua.text_input("Login",         key="m_new_login",  placeholder="joao.silva")
    new_uname  = ub.text_input("Nome completo", key="m_new_uname",  placeholder="João Silva")
    new_pass   = ua.text_input("Senha",         key="m_new_pass",   type="password")
    new_role   = ub.selectbox("Perfil",         ["user", "admin", "master"], key="m_new_role")
    if st.button("Criar usuário", key="m_create_user", type="primary"):
        ok, msg = create_user(sel_tid, new_login, new_pass, new_uname, new_role)
        st.session_state["_master_ok" if ok else "_master_err"] = msg
        st.rerun()

role_icons = {"master": "🛡️", "admin": "🟢", "user": "🔵"}
for u in users:
    icon   = role_icons.get(u["role"], "⚪")
    suffix = "" if u["active"] else " *(inativo)*"
    with st.expander(f"{icon} {u['login']}  —  {u['display_name']}{suffix}", expanded=False):
        col1, col2, col3 = st.columns(3)

        role_list = ["user", "admin", "master"]
        cur_idx   = role_list.index(u["role"]) if u["role"] in role_list else 0
        new_role_val = col1.selectbox("Perfil", role_list, index=cur_idx,
                                      key=f"m_role_{u['id']}")
        if col1.button("Salvar perfil", key=f"m_save_role_{u['id']}", use_container_width=True):
            if update_user_role(u["id"], new_role_val):
                st.session_state["_master_ok"] = f"Perfil de '{u['login']}' → '{new_role_val}'."
            else:
                st.session_state["_master_err"] = "Erro ao alterar perfil."
            st.rerun()

        new_pwd = col2.text_input("Nova senha", type="password", key=f"m_pwd_{u['id']}")
        if col2.button("Redefinir senha", key=f"m_reset_{u['id']}", use_container_width=True):
            if new_pwd and len(new_pwd) >= 6:
                if reset_user_password(u["id"], new_pwd):
                    st.session_state["_master_ok"] = f"Senha de '{u['login']}' redefinida."
                else:
                    st.session_state["_master_err"] = "Erro ao redefinir senha."
            else:
                st.session_state["_master_err"] = "Senha deve ter ao menos 6 caracteres."
            st.rerun()

        lbl_u = "Desativar" if u["active"] else "Ativar"
        col3.write(""); col3.write("")
        if col3.button(lbl_u, key=f"m_tog_user_{u['id']}", use_container_width=True):
            if toggle_user_active(u["id"], not u["active"]):
                st.session_state["_master_ok"] = f"Usuário '{u['login']}' {lbl_u.lower()}do."
            else:
                st.session_state["_master_err"] = "Erro ao alterar status."
            st.rerun()

        # ── Contas de integração ──────────────────────────────────────────────
        st.markdown(
            "<div style='font-size:.78rem;color:#8899AA;margin-top:.6rem'>"
            "Contas de integração</div>",
            unsafe_allow_html=True,
        )
        acc1, acc2, acc_save = st.columns([3, 3, 1])
        goog_val  = u.get("google_account")   or ""
        teams_val = u.get("ms_teams_account") or ""
        new_goog  = acc1.text_input(
            "Conta Google",
            value=goog_val,
            placeholder="usuario@gmail.com",
            key=f"m_goog_{u['id']}",
        )
        new_teams = acc2.text_input(
            "Conta Microsoft Teams",
            value=teams_val,
            placeholder="usuario@empresa.com",
            key=f"m_teams_{u['id']}",
        )
        acc_save.write(""); acc_save.write("")
        if acc_save.button("💾", key=f"m_save_acc_{u['id']}",
                           help="Salvar contas de integração", type="primary",
                           use_container_width=True):
            if update_user_accounts(u["id"], new_goog, new_teams):
                st.session_state["_master_ok"] = (
                    f"Contas de integração de '{u['login']}' atualizadas."
                )
            else:
                st.session_state["_master_err"] = "Erro ao salvar contas de integração."
            st.rerun()

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# SEÇÃO 3 — Contextos
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(f"### 📁 Contextos ({len(all_projects)})")
st.caption(f"Contextos do domínio **{sel_slug}**. Troque o domínio no seletor acima para gerenciar outros domínios.")

with st.expander("➕ Novo Contexto", expanded=False):
    pa, pb, pc = st.columns([3, 2, 1])
    proj_name  = pa.text_input("Nome do contexto", key="m_proj_name",
                                placeholder="Mapeamento de Processos RH")
    proj_sigla = pb.text_input("Sigla (máx 10)", key="m_proj_sigla",
                                placeholder="RH", max_chars=10)
    proj_desc  = st.text_area("Descrição (opcional)", key="m_proj_desc", height=68)
    if st.button("Criar contexto", key="m_create_proj", type="primary"):
        if proj_name.strip():
            result = create_project(proj_name.strip(), proj_desc.strip(), proj_sigla.strip(), tenant_id=sel_tid)
            if result:
                st.session_state["_master_ok"] = f"Contexto '{proj_name.strip()}' criado."
            else:
                st.session_state["_master_err"] = "Erro ao criar contexto."
        else:
            st.session_state["_master_err"] = "Nome do contexto é obrigatório."
        st.rerun()

if all_projects:
    import pandas as pd
    proj_df = pd.DataFrame([
        {
            "Nome":    p.get("name", ""),
            "Sigla":   p.get("sigla", "") or "—",
            "Descrição": (p.get("description", "") or "")[:60],
        }
        for p in all_projects
    ])
    st.dataframe(proj_df, use_container_width=True, hide_index=True)
else:
    st.info("Nenhum projeto cadastrado ainda.")

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# SEÇÃO 4 — Configurações do domínio selecionado
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(f"### ⚙️ Configurações — {sel_slug}")

cfg = load_all_config(sel_tid)

# Mensagem de salvo dentro desta seção
if "_master_cfg_ok" in st.session_state:
    st.success(st.session_state.pop("_master_cfg_ok"))

# ── API Keys ───────────────────────────────────────────────────────────────────
st.markdown("#### 🔑 API Keys")
all_key_map = {
    **PROVIDER_KEY_MAP,
    "Embedding":  "embedding_key",
    "Assistente": "assistant_key",
}
for label, key_name in all_key_map.items():
    val = cfg.get(key_name, "")
    ck, cv, cd = st.columns([2, 4, 1])
    ck.markdown(f"**{label}**")
    if val:
        cv.success(f"`{mask_key(val)}`")
        if cd.button("🗑", key=f"m_del_{sel_tid}_{key_name}", help="Remover"):
            if delete_config(sel_tid, key_name):
                st.session_state["_master_cfg_ok"] = f"{label} removida de {sel_slug}."
            st.rerun()
    else:
        inp_col, save_col = cv.columns([4, 1])
        new_v = inp_col.text_input(
            label, type="password", label_visibility="collapsed",
            placeholder=f"{label} key...", key=f"m_inp_{sel_tid}_{key_name}",
        )
        if save_col.button("💾", key=f"m_save_{sel_tid}_{key_name}",
                           help="Salvar", type="primary"):
            v = new_v.strip()
            if v and len(v) >= 10:
                if save_config(sel_tid, key_name, v):
                    st.session_state["_master_cfg_ok"] = f"{label} salva para {sel_slug}."
                else:
                    st.session_state["_master_err"] = "Erro ao salvar."
            else:
                st.session_state["_master_err"] = "Chave muito curta."
            st.rerun()
        cd.write("")

# ── Preferências ───────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("#### ⚙️ Preferências salvas")
pref_rows = [
    {"Preferência": PREFS_LABELS.get(sk, sk), "Valor": cfg.get(ck, "")}
    for sk, (ck, _) in PREFS_MAP.items()
    if cfg.get(ck, "")
]
if pref_rows:
    import pandas as pd
    st.dataframe(pd.DataFrame(pref_rows), use_container_width=True, hide_index=True)
else:
    st.caption("Nenhuma preferência salva para este domínio.")

# ══════════════════════════════════════════════════════════════════════════════
# SEÇÃO 5 — Logs de Acesso
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### 📋 Logs de Acesso")

from core.project_store import list_login_logs

col_lf1, col_lf2, col_lf3 = st.columns(3)
with col_lf1:
    log_domain = st.selectbox(
        "Domínio",
        ["Todos"] + sorted({t.get("slug", "") for t in tenants if t.get("slug")}) + ["local"],
        key="m_log_domain",
    )
with col_lf2:
    log_status = st.selectbox(
        "Status",
        ["Todos", "✅ Sucesso", "❌ Falha"],
        key="m_log_status",
    )
with col_lf3:
    log_limit = st.selectbox("Últimos", [50, 100, 200, 500], key="m_log_limit")

_domain_filter  = None if log_domain == "Todos" else log_domain
_success_filter = None
if log_status == "✅ Sucesso":
    _success_filter = True
elif log_status == "❌ Falha":
    _success_filter = False

logs = list_login_logs(domain=_domain_filter, success=_success_filter, limit=log_limit)

if not logs:
    st.info("Nenhum evento de login registrado com os filtros selecionados.")
else:
    n_ok  = sum(1 for l in logs if l.get("success"))
    n_fail = len(logs) - n_ok
    mc1, mc2, mc3 = st.columns(3)
    mc1.metric("Total exibidos", len(logs))
    mc2.metric("✅ Sucessos",    n_ok)
    mc3.metric("❌ Falhas",     n_fail)

    rows = []
    for ev in logs:
        ts = (ev.get("logged_at") or "")
        # Formata: "2026-04-22 14:35:07" → separa data e hora
        date_part = ts[:10] if len(ts) >= 10 else ts
        time_part = ts[11:19] if len(ts) >= 19 else ""
        rows.append({
            "Data":     date_part,
            "Hora":     time_part,
            "Login":    ev.get("login", "—"),
            "Domínio":  ev.get("domain", "—"),
            "Perfil":   ev.get("role") or "—",
            "Status":   "✅ Sucesso" if ev.get("success") else "❌ Falha",
            "Motivo":   ev.get("fail_reason") or "",
        })

    import pandas as pd
    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
    )

    # Export CSV
    csv = pd.DataFrame(rows).to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Exportar CSV",
        data=csv,
        file_name="login_logs.csv",
        mime="text/csv",
        key="m_log_csv",
    )

# ══════════════════════════════════════════════════════════════════════════════
# SEÇÃO 6 — Agent Cards
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### 🤖 Agent Cards")
st.caption("Catálogo de agentes do pipeline — capacidades, artefatos e dependências de cada especialista.")

import streamlit.components.v1 as _stc_mac
from core.agent_registry import get_agent_cards

_all_cards = get_agent_cards()

# ── KPIs ───────────────────────────────────────────────────────────────────────
_k1, _k2, _k3, _k4 = st.columns(4)
_k1.metric("Total de agentes",       len(_all_cards))
_k2.metric("Pipeline automático",    sum(1 for c in _all_cards if c.get("pipeline_phase") != "on_demand"))
_k3.metric("Sob demanda",            sum(1 for c in _all_cards if c.get("pipeline_phase") == "on_demand"))
_k4.metric("Python puro (sem LLM)",  sum(1 for c in _all_cards if c.get("mode") == "pure_python"))

# ── Filtros ────────────────────────────────────────────────────────────────────
_PHASE_LABELS = {
    "pre": "Pré-pipeline", "core": "Core", "enrichment": "Enriquecimento",
    "output": "Saída", "post": "Pós-pipeline", "on_demand": "Sob demanda",
}
_unique_phases = sorted({c.get("pipeline_phase", "") for c in _all_cards}, key=lambda p: list(_PHASE_LABELS).index(p) if p in _PHASE_LABELS else 9)
_fa, _fb, _fc = st.columns([2, 2, 4])
_phase_filter = _fa.selectbox("Fase",     ["Todas"] + _unique_phases,            key="mac_phase", format_func=lambda v: "Todas" if v == "Todas" else _PHASE_LABELS.get(v, v))
_mode_filter  = _fb.selectbox("Modo",     ["Todos", "llm", "pure_python"],        key="mac_mode",  format_func=lambda v: {"Todos": "Todos", "llm": "LLM", "pure_python": "Python puro"}.get(v, v))

_filtered = [
    c for c in _all_cards
    if (_phase_filter == "Todas" or c.get("pipeline_phase") == _phase_filter)
    and (_mode_filter == "Todos" or c.get("mode") == _mode_filter)
]

# ── Grid HTML ──────────────────────────────────────────────────────────────────
_PHASE_STYLE = {
    "pre":        ("rgba(88,28,135,.30)",  "#C4B5FD"),
    "core":       ("rgba(30,58,138,.30)",  "#93C5FD"),
    "enrichment": ("rgba(6,78,59,.30)",    "#6EE7B7"),
    "output":     ("rgba(120,53,15,.30)",  "#FCD34D"),
    "post":       ("rgba(20,83,45,.30)",   "#86EFAC"),
    "on_demand":  ("rgba(55,65,81,.30)",   "#D1D5DB"),
}
_MODE_STYLE = {
    "llm":         ("rgba(30,64,175,.30)",  "#93C5FD"),
    "pure_python": ("rgba(5,150,105,.30)",  "#6EE7B7"),
}

def _build_cards_html(cards: list[dict]) -> str:
    rows_html = ""
    for card in cards:
        dname  = card.get("display_name", card.get("name", ""))
        desc   = card.get("description", "")
        phase  = card.get("pipeline_phase", "core")
        mode   = card.get("mode", "llm")
        fatal  = card.get("fatal", True)
        arts   = card.get("artifacts") or []
        deps   = card.get("dependencies") or []
        reads  = card.get("reads") or []

        ph_bg, ph_fg = _PHASE_STYLE.get(phase, ("rgba(55,65,81,.30)", "#D1D5DB"))
        mo_bg, mo_fg = _MODE_STYLE.get(mode, ("rgba(55,65,81,.30)", "#D1D5DB"))
        ph_label = _PHASE_LABELS.get(phase, phase)
        mo_label = "LLM" if mode == "llm" else "Python puro"

        fatal_badge = "" if fatal else '<span class="badge" style="background:rgba(180,83,9,.30);color:#FCD34D">não-fatal</span>'

        arts_html = "".join(
            f'<span class="tag">{a}</span>' for a in arts[:3]
        )
        if len(arts) > 3:
            arts_html += f'<span class="tag more">+{len(arts)-3}</span>'

        deps_html = (
            f'<div class="deps">⛓ Requer: {", ".join(deps)}</div>'
            if deps else ""
        )
        reads_html = ""
        if reads:
            reads_short = reads[:2]
            reads_html = '<div class="deps">📥 ' + " · ".join(reads_short)
            if len(reads) > 2:
                reads_html += f" +{len(reads)-2}"
            reads_html += "</div>"

        rows_html += f"""
        <div class="card">
          <div class="badges">
            <span class="badge" style="background:{ph_bg};color:{ph_fg}">{ph_label}</span>
            <span class="badge" style="background:{mo_bg};color:{mo_fg}">{mo_label}</span>
            {fatal_badge}
          </div>
          <div class="name">{dname}</div>
          <div class="desc">{desc}</div>
          {'<div class="arts">' + arts_html + '</div>' if arts_html else ''}
          {reads_html}
          {deps_html}
        </div>"""

    n_cols = min(3, max(1, len(cards)))
    return f"""<!DOCTYPE html><html><head><style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:transparent;font-family:'Segoe UI',system-ui,sans-serif;padding:2px}}
.grid{{display:grid;grid-template-columns:repeat({n_cols},1fr);gap:10px}}
.card{{
  background:#0D1B2A;border:1px solid #1C3150;border-radius:10px;
  padding:13px 15px;display:flex;flex-direction:column;gap:7px;
  transition:border-color .18s,transform .18s
}}
.card:hover{{border-color:#3E6A99;transform:translateY(-1px)}}
.badges{{display:flex;flex-wrap:wrap;gap:5px}}
.badge{{font-size:.62rem;font-weight:700;letter-spacing:.04em;padding:2px 8px;border-radius:20px}}
.name{{font-size:.88rem;font-weight:700;color:#E2EAF6;line-height:1.25}}
.desc{{font-size:.76rem;color:#7A9AB8;line-height:1.45}}
.arts{{display:flex;flex-wrap:wrap;gap:4px;margin-top:1px}}
.tag{{font-size:.65rem;color:#4EA8A8;background:rgba(78,168,168,.12);padding:2px 7px;border-radius:4px}}
.tag.more{{color:#6B7280;background:rgba(107,114,128,.10)}}
.deps{{font-size:.67rem;color:#4E6070;margin-top:1px}}
</style></head><body>
<div class="grid">{rows_html}</div>
</body></html>"""

if _filtered:
    _card_height = 160 * (len(_filtered) // 3 + (1 if len(_filtered) % 3 else 0)) + 30
    _stc_mac.html(_build_cards_html(_filtered), height=min(_card_height, 800), scrolling=True)
else:
    st.info("Nenhum agente encontrado com os filtros selecionados.")

# ── Painel de inspeção detalhada ───────────────────────────────────────────────
st.markdown("#### 🔍 Inspecionar agente")
_agent_opts = {f"{c.get('display_name', c.get('name',''))} ({c.get('name','')})": c for c in _filtered}
_sel_label  = st.selectbox("Selecione um agente para ver detalhes completos",
                            ["— selecione —"] + list(_agent_opts.keys()), key="mac_sel")

if _sel_label != "— selecione —":
    _sc = _agent_opts[_sel_label]
    _phase  = _sc.get("pipeline_phase", "")
    _mode   = _sc.get("mode", "llm")
    _fatal  = _sc.get("fatal", True)

    _dc1, _dc2, _dc3 = st.columns(3)
    _dc1.markdown(f"**Fase**  \n`{_PHASE_LABELS.get(_phase, _phase)}`")
    _dc2.markdown(f"**Modo**  \n`{'LLM' if _mode == 'llm' else 'Python puro'}`")
    _dc3.markdown(f"**Não-fatal**  \n`{'sim' if not _fatal else 'não'}`")

    _dca, _dcb = st.columns(2)
    with _dca:
        st.markdown("**Módulo**")
        st.code(_sc.get("module", "—"), language=None)
        if _sc.get("skill_file"):
            st.markdown("**Skill file**")
            st.code(_sc.get("skill_file"), language=None)
        if _sc.get("standard"):
            st.markdown(f"**Padrão:** `{_sc['standard']}`")

    with _dcb:
        if _sc.get("reads"):
            st.markdown("**Lê de (hub)**")
            for r in _sc["reads"]:
                st.markdown(f"- `{r}`")
        if _sc.get("writes"):
            st.markdown("**Escreve em**")
            for w in _sc["writes"]:
                st.markdown(f"- `{w}`")

    if _sc.get("artifacts"):
        st.markdown("**Artefatos gerados**")
        for a in _sc["artifacts"]:
            st.markdown(f"- {a}")

    if _sc.get("dependencies"):
        st.markdown(f"**Dependências:** `{', '.join(_sc['dependencies'])}`")

    # Campos extras específicos do card
    _extra_skip = {"name","class","module","display_name","description","pipeline_phase",
                   "mode","fatal","reads","writes","artifacts","dependencies","skill_file","standard"}
    _extras = {k: v for k, v in _sc.items() if k not in _extra_skip and v}
    if _extras:
        with st.expander("📋 Metadados adicionais", expanded=False):
            for k, v in _extras.items():
                if isinstance(v, list):
                    st.markdown(f"**{k}:** " + " · ".join(str(i) for i in v))
                else:
                    st.markdown(f"**{k}:** `{v}`")
