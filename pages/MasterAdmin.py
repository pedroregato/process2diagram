# pages/MasterAdmin.py
# ─────────────────────────────────────────────────────────────────────────────
# Painel de administração master — Process2Diagram
#
# Acessível apenas para usuários com role == 'master'.
# Permite gerenciar domínios, usuários e configurações de todos os tenants.
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

# ── Verificação de perfil ──────────────────────────────────────────────────────
if st.session_state.get("_role") != "master":
    st.error("🚫 Acesso restrito. Esta página requer o perfil **master**.")
    st.stop()

from modules.tenant_auth import (
    list_all_tenants, list_users_by_tenant,
    create_tenant, create_user,
    toggle_tenant_active, toggle_user_active,
    update_user_role, reset_user_password,
)
from modules.tenant_config import load_all_config, save_config, delete_config, mask_key, PROVIDER_KEY_MAP, EXTRA_KEY_MAP, PREFS_MAP, PREFS_LABELS

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("# 🛡️ Master Administration")
st.caption(
    f"Logado como **{st.session_state.get('_usuario_nome', '')}** "
    f"(`{st.session_state.get('_domain', '')}`) · Perfil: `master`"
)
st.markdown("---")

# Mensagens persistidas
if "_master_ok" in st.session_state:
    st.success(st.session_state.pop("_master_ok"))
if "_master_err" in st.session_state:
    st.error(st.session_state.pop("_master_err"))

tab_domains, tab_users, tab_config = st.tabs([
    "🌐 Domínios",
    "👥 Usuários",
    "⚙️ Configurações por Domínio",
])

# ╔══════════════════════════════════╗
# ║  TAB 1 — Domínios               ║
# ╚══════════════════════════════════╝
with tab_domains:
    tenants = list_all_tenants()

    # ── Criar novo domínio ────────────────────────────────────────────────────
    with st.expander("➕ Criar novo domínio", expanded=len(tenants) == 0):
        c1, c2, c3 = st.columns([2, 3, 1])
        slug = c1.text_input("Slug (ex: fgv)", key="master_new_slug", placeholder="fgv")
        name = c2.text_input("Nome completo", key="master_new_name", placeholder="Fundação Getúlio Vargas")
        c3.write("")
        c3.write("")
        if c3.button("Criar", key="master_create_tenant", type="primary", use_container_width=True):
            ok, msg = create_tenant(slug, name)
            if ok:
                st.session_state["_master_ok"] = msg
            else:
                st.session_state["_master_err"] = msg
            st.rerun()

    st.markdown("---")
    st.markdown(f"#### Domínios cadastrados ({len(tenants)})")

    if not tenants:
        st.info("Nenhum domínio cadastrado ainda.")
    else:
        for t in tenants:
            active_icon = "🟢" if t["active"] else "🔴"
            with st.expander(f"{active_icon} **{t['domain_slug']}** — {t['display_name']}", expanded=False):
                col_id, col_toggle = st.columns([4, 1])
                col_id.caption(f"ID: `{t['id']}`")
                label = "Desativar" if t["active"] else "Ativar"
                if col_toggle.button(label, key=f"master_toggle_tenant_{t['id']}", use_container_width=True):
                    if toggle_tenant_active(t["id"], not t["active"]):
                        st.session_state["_master_ok"] = f"Domínio '{t['domain_slug']}' {'desativado' if t['active'] else 'ativado'}."
                    else:
                        st.session_state["_master_err"] = "Erro ao alterar status."
                    st.rerun()

                users = list_users_by_tenant(t["id"])
                st.caption(f"{len(users)} usuário(s) cadastrado(s)")

# ╔══════════════════════════════════╗
# ║  TAB 2 — Usuários               ║
# ╚══════════════════════════════════╝
with tab_users:
    tenants_for_sel = list_all_tenants()
    if not tenants_for_sel:
        st.info("Cadastre um domínio primeiro.")
    else:
        tenant_options = {f"{t['domain_slug']} — {t['display_name']}": t["id"] for t in tenants_for_sel}
        sel_tenant_label = st.selectbox("Selecionar domínio", list(tenant_options.keys()), key="master_sel_tenant_users")
        sel_tenant_id = tenant_options[sel_tenant_label]
        sel_tenant_slug = sel_tenant_label.split(" — ")[0]

        st.markdown("---")

        # ── Criar usuário ─────────────────────────────────────────────────────
        with st.expander("➕ Criar novo usuário", expanded=False):
            col_a, col_b = st.columns(2)
            new_login   = col_a.text_input("Login", key="master_new_login", placeholder="joao.silva")
            new_name    = col_b.text_input("Nome completo", key="master_new_uname", placeholder="João Silva")
            new_pass    = col_a.text_input("Senha", type="password", key="master_new_pass")
            new_role    = col_b.selectbox("Perfil", ["user", "admin", "master"], key="master_new_role")
            if st.button("Criar usuário", key="master_create_user", type="primary"):
                ok, msg = create_user(sel_tenant_id, new_login, new_pass, new_name, new_role)
                if ok:
                    st.session_state["_master_ok"] = msg
                else:
                    st.session_state["_master_err"] = msg
                st.rerun()

        st.markdown("---")

        # ── Listar usuários ───────────────────────────────────────────────────
        users = list_users_by_tenant(sel_tenant_id)
        st.markdown(f"#### Usuários de **{sel_tenant_slug}** ({len(users)})")

        if not users:
            st.info("Nenhum usuário neste domínio.")
        else:
            role_icons = {"master": "🛡️", "admin": "🟢", "user": "🔵"}
            for u in users:
                icon = role_icons.get(u["role"], "⚪")
                active_mark = "" if u["active"] else " *(inativo)*"
                with st.expander(f"{icon} {u['login']} — {u['display_name']}{active_mark}", expanded=False):
                    col1, col2, col3 = st.columns(3)

                    # Alterar perfil
                    new_role_val = col1.selectbox(
                        "Perfil", ["user", "admin", "master"],
                        index=["user", "admin", "master"].index(u["role"]) if u["role"] in ["user","admin","master"] else 0,
                        key=f"master_role_{u['id']}",
                    )
                    if col1.button("Salvar perfil", key=f"master_save_role_{u['id']}", use_container_width=True):
                        if update_user_role(u["id"], new_role_val):
                            st.session_state["_master_ok"] = f"Perfil de '{u['login']}' alterado para '{new_role_val}'."
                        else:
                            st.session_state["_master_err"] = "Erro ao alterar perfil."
                        st.rerun()

                    # Redefinir senha
                    new_pwd = col2.text_input("Nova senha", type="password", key=f"master_pwd_{u['id']}")
                    if col2.button("Redefinir senha", key=f"master_reset_pwd_{u['id']}", use_container_width=True):
                        if new_pwd and len(new_pwd) >= 6:
                            if reset_user_password(u["id"], new_pwd):
                                st.session_state["_master_ok"] = f"Senha de '{u['login']}' redefinida."
                            else:
                                st.session_state["_master_err"] = "Erro ao redefinir senha."
                        else:
                            st.session_state["_master_err"] = "Senha deve ter ao menos 6 caracteres."
                        st.rerun()

                    # Ativar/desativar
                    label_toggle = "Desativar" if u["active"] else "Ativar"
                    col3.write("")
                    col3.write("")
                    if col3.button(label_toggle, key=f"master_toggle_user_{u['id']}", use_container_width=True):
                        if toggle_user_active(u["id"], not u["active"]):
                            st.session_state["_master_ok"] = f"Usuário '{u['login']}' {label_toggle.lower()}do."
                        else:
                            st.session_state["_master_err"] = "Erro ao alterar status."
                        st.rerun()

# ╔══════════════════════════════════════════════════════╗
# ║  TAB 3 — Configurações por Domínio                  ║
# ╚══════════════════════════════════════════════════════╝
with tab_config:
    tenants_for_cfg = list_all_tenants()
    if not tenants_for_cfg:
        st.info("Cadastre um domínio primeiro.")
    else:
        tenant_cfg_options = {f"{t['domain_slug']} — {t['display_name']}": t["id"] for t in tenants_for_cfg}
        sel_cfg_label = st.selectbox("Selecionar domínio", list(tenant_cfg_options.keys()), key="master_sel_tenant_cfg")
        sel_cfg_id    = tenant_cfg_options[sel_cfg_label]
        sel_cfg_slug  = sel_cfg_label.split(" — ")[0]

        st.markdown("---")

        cfg = load_all_config(sel_cfg_id)

        # ── API Keys ──────────────────────────────────────────────────────────
        st.markdown("#### 🔑 API Keys")
        all_key_map = {**PROVIDER_KEY_MAP, "Embedding": "embedding_key", "Assistente": "assistant_key"}
        for label, key_name in all_key_map.items():
            val = cfg.get(key_name, "")
            col_lbl, col_val, col_del = st.columns([2, 4, 1])
            col_lbl.markdown(f"**{label}**")
            if val:
                col_val.success(f"`{mask_key(val)}`")
                if col_del.button("🗑", key=f"master_del_key_{sel_cfg_id}_{key_name}", help="Remover"):
                    if delete_config(sel_cfg_id, key_name):
                        st.session_state["_master_ok"] = f"{label} removida de {sel_cfg_slug}."
                    st.rerun()
            else:
                col_val.caption("❌ Não configurada")

        # ── Preferências ──────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("#### ⚙️ Preferências salvas")
        pref_rows = []
        for state_key, (config_key, _) in PREFS_MAP.items():
            val = cfg.get(config_key, "")
            if val:
                pref_rows.append({"Preferência": PREFS_LABELS.get(state_key, state_key), "Valor": val})
        if pref_rows:
            import pandas as pd
            st.dataframe(pd.DataFrame(pref_rows), use_container_width=True, hide_index=True)
        else:
            st.caption("Nenhuma preferência salva para este domínio.")
