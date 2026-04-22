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
)
from modules.tenant_config import (
    load_all_config, save_config, delete_config,
    mask_key, PROVIDER_KEY_MAP, PREFS_MAP, PREFS_LABELS,
)
from core.project_store import list_projects, create_project

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

# Métricas rápidas
total_users = sum(len(list_users_by_tenant(t["id"])) for t in tenants)
all_projects = list_projects() or []
c1, c2, c3 = st.columns(3)
c1.metric("Domínios",  len(tenants))
c2.metric("Usuários",  total_users)
c3.metric("Projetos",  len(all_projects))

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
users = list_users_by_tenant(sel_tid)
st.markdown(f"### 👥 Usuários — {sel_slug} ({len(users)})")

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

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# SEÇÃO 3 — Projetos
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(f"### 📁 Projetos ({len(all_projects)})")
st.caption(
    "Projetos são globais (ainda sem isolamento por domínio). "
    "O isolamento por tenant será implementado na Fase D."
)

with st.expander("➕ Novo Projeto", expanded=False):
    pa, pb, pc = st.columns([3, 2, 1])
    proj_name  = pa.text_input("Nome do projeto", key="m_proj_name",
                                placeholder="Mapeamento de Processos RH")
    proj_sigla = pb.text_input("Sigla (máx 10)", key="m_proj_sigla",
                                placeholder="RH", max_chars=10)
    proj_desc  = st.text_area("Descrição (opcional)", key="m_proj_desc", height=68)
    if st.button("Criar projeto", key="m_create_proj", type="primary"):
        if proj_name.strip():
            result = create_project(proj_name.strip(), proj_desc.strip(), proj_sigla.strip())
            if result:
                st.session_state["_master_ok"] = f"Projeto '{proj_name.strip()}' criado."
            else:
                st.session_state["_master_err"] = "Erro ao criar projeto."
        else:
            st.session_state["_master_err"] = "Nome do projeto é obrigatório."
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
