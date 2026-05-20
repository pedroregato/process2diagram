# pages/PaymentAdmin.py
# ─────────────────────────────────────────────────────────────────────────────
# Billing Admin — preview interativo das mensagens ao usuário, simulacao de
# pagamentos e gestao de creditos. Acesso: admin / master apenas.
# ─────────────────────────────────────────────────────────────────────────────

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st
from ui.auth_gate import apply_auth_gate
from modules.auth import is_admin
from ui.components.page_header import render_page_header
from modules.billing import (
    PLANS, get_plan,
    upsert_credits, set_contribuidor, reset_trial, list_users_credits,
    log_payment, list_payments,
)

apply_auth_gate()

if not is_admin():
    st.error("Acesso restrito a administradores.")
    st.stop()

render_page_header(
    "💳", "Billing & Pagamentos",
    "Simule pagamentos, visualize previews das mensagens ao usuario e gerencie creditos.",
)

# ── Configuracao rapida (sessao) ───────────────────────────────────────────────
with st.expander("Configuracao rapida", expanded=True):
    c1, c2 = st.columns(2)
    with c1:
        pix_inp = st.text_input(
            "Chave PIX",
            value=st.session_state.get("_billing_pix_key", ""),
            placeholder="email@exemplo.com",
            help="Exibida nos previews. Configure permanentemente em st.secrets['billing']['pix_key'].",
        )
        st.session_state["_billing_pix_key"] = pix_inp.strip() or "[SUA-CHAVE-PIX]"
    with c2:
        prod_inp = st.text_input(
            "Nome do produto",
            value=st.session_state.get("_billing_product", "Process2Diagram"),
        )
        st.session_state["_billing_product"] = prod_inp.strip() or "Process2Diagram"

_pix     = st.session_state["_billing_pix_key"]
_product = st.session_state["_billing_product"]

# ── Abas ──────────────────────────────────────────────────────────────────────
tab_prev, tab_sim, tab_users, tab_log = st.tabs([
    "Preview das mensagens",
    "Simular pagamento",
    "Usuarios e creditos",
    "Log de transacoes",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — PREVIEW
# ══════════════════════════════════════════════════════════════════════════════
with tab_prev:

    # ── inicializa flags de estado do preview ─────────────────────────────────
    for _k, _v in [
        ("_pv_show_qr",     False),
        ("_pv_show_ty_don", False),
        ("_pv_plan_sel",    None),
        ("_pv_show_qr_plan",False),
        ("_pv_show_ty_plan",False),
        ("_pv_balloon_done",False),
    ]:
        if _k not in st.session_state:
            st.session_state[_k] = _v

    # ═══════════════════════════════════════════════════════════════════════════
    # A. Banner de doacao voluntaria (sidebar)
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("### A. Banner de Doacao Voluntaria")
    st.caption(
        "Aparece no sidebar na primeira consulta do dia, enquanto o usuario estiver no periodo de degustacao. "
        "Nao bloqueia o uso — apenas lembra."
    )

    col_banner, _ = st.columns([1, 2])
    with col_banner:

        # Banner principal
        st.markdown(
            f"""
            <div style="background:#0d2a4a;border-radius:10px;border-left:3px solid #22c55e;
                        padding:14px 16px;font-family:'Segoe UI',sans-serif;">
              <div style="color:#22c55e;font-weight:700;font-size:0.9rem;margin-bottom:8px;">
                Apoie o {_product}
              </div>
              <p style="color:#cbd5e1;font-size:0.82rem;line-height:1.5;margin:0 0 4px;">
                Este projeto e gratuito e sem fins lucrativos. Se ele te ajudou, considere
                uma doacao via PIX (qualquer valor).
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        b1, b2 = st.columns(2)
        with b1:
            if st.button("Quero apoiar", key="pv_apoiar", use_container_width=True, type="primary"):
                st.session_state["_pv_show_qr"]     = True
                st.session_state["_pv_show_ty_don"] = False
        with b2:
            if st.button("Fechar", key="pv_fechar", use_container_width=True):
                st.session_state["_pv_show_qr"]     = False
                st.session_state["_pv_show_ty_don"] = False

        # QR Code PIX (apos clicar "Quero apoiar")
        if st.session_state["_pv_show_qr"] and not st.session_state["_pv_show_ty_don"]:
            st.markdown(
                f"""
                <div style="background:#0a1929;border:1px solid #22c55e;border-radius:8px;
                            padding:20px;text-align:center;margin-top:10px;font-family:'Segoe UI',sans-serif;">
                  <div style="color:#22c55e;font-weight:600;font-size:0.85rem;margin-bottom:14px;">
                    Escaneie o QR Code PIX
                  </div>
                  <div style="background:#ffffff;width:150px;height:150px;margin:0 auto 14px;
                              border-radius:8px;display:flex;align-items:center;justify-content:center;
                              font-size:0.65rem;color:#6b7280;border:1px solid #e5e7eb;flex-direction:column;gap:4px;">
                    <span style="font-size:1.5rem;">QR</span>
                    <span>QR Code aqui</span>
                    <span style="font-size:0.6rem;">(gerado pelo gateway)</span>
                  </div>
                  <div style="color:#94a3b8;font-size:0.75rem;margin-bottom:6px;">Ou copie a chave PIX:</div>
                  <code style="color:#22c55e;font-size:0.78rem;background:#0f2235;
                               padding:6px 14px;border-radius:4px;display:inline-block;">{_pix}</code>
                  <div style="color:#64748b;font-size:0.7rem;margin-top:14px;font-style:italic;">
                    Qualquer valor e bem-vindo
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Ja apoiei — ver agradecimento", key="pv_ty_don_btn", use_container_width=True):
                st.session_state["_pv_show_ty_don"] = True
                st.rerun()

        # Mensagem de agradecimento (doacao voluntaria)
        if st.session_state["_pv_show_ty_don"]:
            st.markdown(
                """
                <div style="background:#052e16;border:1px solid #22c55e;border-radius:10px;
                            padding:22px;text-align:center;margin-top:10px;font-family:'Segoe UI',sans-serif;">
                  <div style="font-size:2rem;margin-bottom:8px;">&#128153;</div>
                  <div style="color:#22c55e;font-weight:700;font-size:1rem;margin-bottom:8px;">
                    Obrigado pelo apoio!
                  </div>
                  <div style="color:#86efac;font-size:0.85rem;line-height:1.5;">
                    Sua contribuicao mantem este projeto gratuito e em constante evolucao.
                    Muito obrigado!
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Resetar preview A", key="pv_reset_a"):
                st.session_state["_pv_show_qr"]     = False
                st.session_state["_pv_show_ty_don"] = False
                st.rerun()

    st.divider()

    # ═══════════════════════════════════════════════════════════════════════════
    # B. Modal de planos pagos (pos-degustacao)
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("### B. Modal de Planos Pagos")
    st.caption(
        "Exibido quando o usuario tenta iniciar uma consulta e o periodo de degustacao expirou "
        "ou os creditos acabaram. Substitui a area de resultados."
    )

    # Cabecalho do modal
    st.markdown(
        """
        <div style="background:#0f2235;border:2px solid #f59e0b;border-radius:12px;
                    padding:28px 32px 20px;font-family:'Segoe UI',sans-serif;margin-bottom:4px;">
          <div style="text-align:center;margin-bottom:20px;">
            <div style="font-size:2.2rem;margin-bottom:8px;">&#128683;</div>
            <div style="color:#f59e0b;font-size:1.2rem;font-weight:700;margin-bottom:6px;">
              Periodo de degustacao encerrado
            </div>
            <div style="color:#94a3b8;font-size:0.9rem;">
              Escolha um plano para continuar processando transcricoes.
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Linhas de planos
    for plan in PLANS:
        credit_text = "Ilimitado / mes" if plan.ilimitado else f"{plan.creditos} reunioes"
        is_sel   = st.session_state["_pv_plan_sel"] == plan.key
        bg       = "#0c2744" if is_sel else "#0f2235"
        border   = "2px solid #f59e0b" if plan.destaque else "1px solid #1e3a5f"
        badge_html = (
            '<span style="background:#f59e0b;color:#000;font-size:0.62rem;font-weight:700;'
            'padding:2px 8px;border-radius:10px;margin-left:8px;">POPULAR</span>'
            if plan.destaque else ""
        )
        c_info, c_price, c_btn = st.columns([4, 2, 3])
        with c_info:
            st.markdown(
                f"""
                <div style="background:{bg};{border.replace('border:','border:')};border-radius:8px;
                            padding:12px 16px;font-family:'Segoe UI',sans-serif;">
                  <div style="color:#e0e7f0;font-weight:600;font-size:0.92rem;">
                    {plan.label}{badge_html}
                  </div>
                  <div style="color:#94a3b8;font-size:0.8rem;margin-top:3px;">{credit_text}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with c_price:
            st.markdown(
                f"""
                <div style="background:{bg};border:{border};border-radius:8px;
                            padding:12px 16px;text-align:center;font-family:'Segoe UI',sans-serif;">
                  <span style="color:#f59e0b;font-weight:700;font-size:1.1rem;">R$ {plan.valor:.0f}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with c_btn:
            btn_type = "primary" if plan.destaque else "secondary"
            if st.button(
                f"Pagar via PIX — {plan.label}",
                key=f"pv_plan_{plan.key}",
                use_container_width=True,
                type=btn_type,
            ):
                st.session_state["_pv_plan_sel"]     = plan.key
                st.session_state["_pv_show_qr_plan"] = True
                st.session_state["_pv_show_ty_plan"] = False
                st.session_state["_pv_balloon_done"] = False
                st.rerun()

    # QR code para o plano selecionado
    if st.session_state["_pv_show_qr_plan"] and not st.session_state["_pv_show_ty_plan"]:
        sel = get_plan(st.session_state["_pv_plan_sel"])
        if sel:
            credit_label = "ilimitadas / mes" if sel.ilimitado else f"{sel.creditos} reunioes"
            st.markdown(
                f"""
                <div style="background:#0a1929;border:1px solid #22c55e;border-radius:12px;
                            padding:28px;text-align:center;margin-top:16px;font-family:'Segoe UI',sans-serif;">
                  <div style="color:#22c55e;font-weight:700;font-size:1rem;margin-bottom:4px;">
                    Plano {sel.label} &mdash; R$ {sel.valor:.0f}
                  </div>
                  <div style="color:#94a3b8;font-size:0.82rem;margin-bottom:18px;">
                    {credit_label} apos confirmacao do pagamento
                  </div>
                  <div style="background:#ffffff;width:160px;height:160px;margin:0 auto 16px;
                              border-radius:8px;display:flex;align-items:center;justify-content:center;
                              font-size:0.65rem;color:#6b7280;border:1px solid #e5e7eb;flex-direction:column;gap:4px;">
                    <span style="font-size:1.8rem;">QR</span>
                    <span>QR Code PIX</span>
                    <span>R$ {sel.valor:.0f}</span>
                    <span style="font-size:0.6rem;">(gerado pelo gateway)</span>
                  </div>
                  <div style="color:#94a3b8;font-size:0.78rem;margin-bottom:8px;">Chave PIX:</div>
                  <code style="color:#22c55e;font-size:0.82rem;background:#0f2235;
                               padding:8px 18px;border-radius:4px;display:inline-block;">{_pix}</code>
                  <div style="margin-top:18px;padding:12px 16px;background:#0c2744;border-radius:8px;
                              border-left:3px solid #3b82f6;font-size:0.82rem;color:#93c5fd;text-align:left;">
                    Apos realizar o PIX, clique em <strong>"Ja paguei &mdash; verificar"</strong>
                    para liberar seus creditos automaticamente.
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Ja paguei — verificar", key="pv_paid_btn", type="primary", use_container_width=True):
                st.session_state["_pv_show_ty_plan"] = True
                st.rerun()

    # Mensagem de agradecimento (plano pago)
    if st.session_state["_pv_show_ty_plan"]:
        sel = get_plan(st.session_state["_pv_plan_sel"])
        if sel:
            credit_label = "ilimitadas / mes" if sel.ilimitado else f"{sel.creditos} reunioes"
            st.markdown(
                f"""
                <div style="background:#052e16;border:1px solid #22c55e;border-radius:12px;
                            padding:36px;text-align:center;margin-top:16px;font-family:'Segoe UI',sans-serif;">
                  <div style="font-size:2.8rem;margin-bottom:14px;">&#9989;</div>
                  <div style="color:#22c55e;font-weight:700;font-size:1.25rem;margin-bottom:10px;">
                    Pagamento confirmado!
                  </div>
                  <div style="color:#86efac;font-size:0.95rem;line-height:1.65;margin-bottom:22px;">
                    Seus creditos foram adicionados com sucesso.<br>
                    Agora voce pode processar <strong>{credit_label}</strong>.
                  </div>
                  <div style="background:#0f2235;border-radius:8px;padding:14px 20px;display:inline-block;
                              border:1px solid #1e3a5f;font-family:'Segoe UI',sans-serif;">
                    <span style="color:#94a3b8;font-size:0.8rem;">Plano:</span>
                    <span style="color:#e0e7f0;font-weight:600;margin-left:8px;">{sel.label}</span>
                    &nbsp;&nbsp;
                    <span style="color:#94a3b8;font-size:0.8rem;">Creditos:</span>
                    <span style="color:#f59e0b;font-weight:600;margin-left:8px;">
                      {'Ilimitados' if sel.ilimitado else sel.creditos}
                    </span>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if not st.session_state["_pv_balloon_done"]:
                st.balloons()
                st.session_state["_pv_balloon_done"] = True

            if st.button("Resetar preview B", key="pv_reset_b"):
                for k in ["_pv_plan_sel", "_pv_show_qr_plan", "_pv_show_ty_plan", "_pv_balloon_done"]:
                    st.session_state[k] = False if k != "_pv_plan_sel" else None
                st.rerun()

    st.divider()

    # ═══════════════════════════════════════════════════════════════════════════
    # C. Nao pagou ainda (polling timeout)
    # ═══════════════════════════════════════════════════════════════════════════
    st.markdown("### C. Pagamento nao identificado")
    st.caption("Exibido quando o usuario clica em 'Ja paguei' mas o gateway ainda nao confirmou.")
    st.markdown(
        """
        <div style="background:#1c0a00;border:1px solid #f59e0b;border-radius:10px;
                    padding:22px;text-align:center;font-family:'Segoe UI',sans-serif;max-width:520px;">
          <div style="font-size:1.8rem;margin-bottom:10px;">&#8987;</div>
          <div style="color:#f59e0b;font-weight:700;font-size:1rem;margin-bottom:8px;">
            Ainda nao identificamos seu pagamento
          </div>
          <div style="color:#fcd34d;font-size:0.85rem;line-height:1.6;margin-bottom:14px;">
            O processamento do PIX pode levar alguns minutos.
            Tente novamente em instantes ou envie o comprovante para
            <strong>contato@seudominio.com</strong> e liberaremos manualmente.
          </div>
          <div style="display:flex;gap:10px;justify-content:center;">
            <button style="background:#f59e0b;color:#000;border:none;border-radius:6px;
                           padding:9px 20px;font-size:0.82rem;font-weight:600;cursor:pointer;">
              Verificar novamente
            </button>
            <button style="background:transparent;color:#94a3b8;border:1px solid #374151;
                           border-radius:6px;padding:9px 16px;font-size:0.82rem;cursor:pointer;">
              Fechar
            </button>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # D. Selo de contribuidor (sidebar)
    # ═══════════════════════════════════════════════════════════════════════════
    st.divider()
    st.markdown("### D. Selo de Contribuidor (sidebar)")
    st.caption("Exibido no sidebar para usuarios marcados como is_contribuidor = true.")
    _, col_seal, __ = st.columns([1, 2, 1])
    with col_seal:
        st.markdown(
            """
            <div style="background:#1e1b4b;border:1px solid #818cf8;border-radius:8px;
                        padding:10px 14px;display:flex;align-items:center;gap:10px;
                        font-family:'Segoe UI',sans-serif;">
              <span style="font-size:1.3rem;">&#11088;</span>
              <div>
                <div style="color:#a5b4fc;font-weight:700;font-size:0.82rem;">Contribuidor</div>
                <div style="color:#6366f1;font-size:0.72rem;">Obrigado pelo apoio!</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — SIMULAR PAGAMENTO
# ══════════════════════════════════════════════════════════════════════════════
with tab_sim:
    st.markdown(
        "Simula um pagamento aprovado — adiciona creditos diretamente no Supabase sem chamar o gateway. "
        "Use para testes ou para liberar manualmente usuarios que pagaram via PIX mas tiveram problemas."
    )
    st.markdown("---")

    c1, c2 = st.columns(2)
    with c1:
        sim_uid   = st.text_input("User ID", placeholder="user_abc123", key="sim_uid")
        sim_email = st.text_input("Email", placeholder="usuario@email.com", key="sim_email")
    with c2:
        plan_opts = {
            p.key: f"{p.label}  —  R$ {p.valor:.0f}  ({p.creditos if not p.ilimitado else 'ilimitado'} reunioes)"
            for p in PLANS
        }
        sim_plan_key = st.selectbox(
            "Plano simulado",
            list(plan_opts.keys()),
            format_func=lambda k: plan_opts[k],
            key="sim_plan",
        )
        sim_note = st.text_input(
            "Observacao interna",
            placeholder="Pagamento manual aprovado — comprovante recebido",
            key="sim_note",
        )

    # Resultado persistido (sobrevive ao rerun)
    if "_sim_result" in st.session_state:
        lvl, msg = st.session_state.pop("_sim_result")
        if lvl == "ok":
            st.success(msg)
        else:
            st.error(msg)

    if st.button("Simular pagamento aprovado", type="primary", use_container_width=True, key="sim_exec"):
        if not sim_uid.strip():
            st.error("Informe o User ID.")
        else:
            plan         = get_plan(sim_plan_key)
            creditos_add = 0 if plan.ilimitado else plan.creditos
            ok_cred = upsert_credits(sim_uid.strip(), sim_email.strip(), creditos_add, plan.key)
            ok_log  = log_payment(
                sim_uid.strip(), sim_email.strip(),
                plan.valor, plan.key, creditos_add,
                status="simulated",
                external_id=sim_note.strip() or "admin-simulation",
            )
            if ok_cred:
                label = "ilimitado" if plan.ilimitado else f"{plan.creditos} creditos"
                st.session_state["_sim_result"] = (
                    "ok",
                    f"Simulacao concluida: **{plan.label}** (R$ {plan.valor:.0f}) "
                    f"-> **{label}** adicionados para `{sim_uid.strip()}`."
                    + ("" if ok_log else "  (aviso: log de pagamento falhou)"),
                )
            else:
                st.session_state["_sim_result"] = (
                    "err",
                    "Falha ao adicionar creditos. Verifique se a tabela `user_credits` "
                    "existe no Supabase (execute setup/supabase_migration_billing.sql).",
                )
            st.rerun()

    st.markdown("---")
    st.markdown("#### SQL de migracao")
    st.caption("Execute no Supabase SQL Editor antes de usar as funcionalidades de billing.")
    _sql_path = Path(__file__).parent.parent / "setup" / "supabase_migration_billing.sql"
    try:
        _sql_content = _sql_path.read_text(encoding="utf-8")
    except Exception:
        _sql_content = "-- Arquivo nao encontrado: setup/supabase_migration_billing.sql"
    with st.expander("Ver SQL completo", expanded=False):
        st.code(_sql_content, language="sql")
    st.download_button(
        "Baixar supabase_migration_billing.sql",
        data=_sql_content,
        file_name="supabase_migration_billing.sql",
        mime="text/plain",
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — USUARIOS E CREDITOS
# ══════════════════════════════════════════════════════════════════════════════
with tab_users:
    users = list_users_credits()

    if not users:
        st.info(
            "Nenhum registro em `user_credits`. "
            "Execute a migracao SQL na aba 'Simular pagamento' e depois simule um pagamento."
        )
    else:
        import pandas as pd

        _cols_show = [c for c in [
            "user_id", "email", "creditos_restantes", "plano",
            "degustacao_ativa", "is_contribuidor", "updated_at",
        ] if c in pd.DataFrame(users).columns]

        df_u = pd.DataFrame(users)[_cols_show]
        st.dataframe(df_u, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("#### Acoes manuais")

        uid_opts = [u["user_id"] for u in users]
        col_sel, col_delta, col_plano = st.columns([3, 1, 2])
        with col_sel:
            edit_uid = st.selectbox("Usuario", uid_opts, key="edit_uid")
        with col_delta:
            delta = st.number_input(
                "Delta creditos", value=0, step=5, key="edit_delta",
                help="Positivo = adicionar, negativo = remover",
            )
        with col_plano:
            u_data   = next((u for u in users if u["user_id"] == edit_uid), {})
            edit_plano = st.text_input("Plano", value=u_data.get("plano", ""), key="edit_plano")

        if "_edit_result" in st.session_state:
            lvl, msg = st.session_state.pop("_edit_result")
            st.success(msg) if lvl == "ok" else st.error(msg)

        ca, cb, cc = st.columns(3)
        with ca:
            if st.button("Aplicar creditos", use_container_width=True, key="edit_apply"):
                ok = upsert_credits(edit_uid, u_data.get("email", ""), delta, edit_plano)
                st.session_state["_edit_result"] = ("ok", "Creditos atualizados.") if ok else ("err", "Falha.")
                st.rerun()
        with cb:
            is_contrib = u_data.get("is_contribuidor", False)
            label_c = "Remover contribuidor" if is_contrib else "Marcar como contribuidor"
            if st.button(label_c, use_container_width=True, key="edit_contrib"):
                ok = set_contribuidor(edit_uid, not is_contrib)
                st.session_state["_edit_result"] = ("ok", "Status de contribuidor atualizado.") if ok else ("err", "Falha.")
                st.rerun()
        with cc:
            if st.button("Resetar degustacao", use_container_width=True, key="edit_reset"):
                ok = reset_trial(edit_uid)
                st.session_state["_edit_result"] = ("ok", "Degustacao resetada — creditos zerados.") if ok else ("err", "Falha.")
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — LOG DE TRANSACOES
# ══════════════════════════════════════════════════════════════════════════════
with tab_log:
    payments = list_payments()

    if not payments:
        st.info("Nenhuma transacao registrada ainda. Simule um pagamento na aba anterior.")
    else:
        import pandas as pd

        _pay_cols = [c for c in [
            "created_at", "user_id", "email", "plano", "valor", "creditos", "status", "external_id",
        ] if c in pd.DataFrame(payments).columns]

        df_pay = pd.DataFrame(payments)[_pay_cols]
        if "created_at" in df_pay.columns:
            df_pay["created_at"] = df_pay["created_at"].astype(str).str[:19]

        st.dataframe(df_pay, use_container_width=True, hide_index=True)

        st.markdown("---")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total transacoes", len(df_pay))
        if "valor" in df_pay.columns:
            c2.metric("Volume total (R$)", f"{df_pay['valor'].sum():.2f}")
        if "status" in df_pay.columns:
            c3.metric("Confirmados (paid)", int((df_pay["status"] == "paid").sum()))
            c4.metric("Simulados", int((df_pay["status"] == "simulated").sum()))
