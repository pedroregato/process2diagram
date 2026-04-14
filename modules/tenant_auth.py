# modules/tenant_auth.py
# ─────────────────────────────────────────────────────────────────────────────
# Autenticação multi-tenant via Supabase.
#
# Fluxo:
#   1. Busca o tenant pelo domain_slug
#   2. Busca o usuário (tenant_id, login)
#   3. Compara SHA-256 da senha com o hash armazenado
#   4. Retorna dict com info do tenant + usuário, ou None se inválido
#
# Fallback: quando Supabase não está configurado ou as tabelas não existem,
# retorna None — o caller deve tentar auth.login_valido() como fallback.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import hashlib
from modules.supabase_client import get_supabase_client


def _hash(senha: str) -> str:
    return hashlib.sha256(senha.encode()).hexdigest()


def login_tenant(domain: str, login: str, password: str) -> dict | None:
    """Valida credenciais multi-tenant no Supabase.

    Args:
        domain:   Slug do domínio/empresa (ex: "fgv"). Case-insensitive.
        login:    Login do usuário. Case-insensitive.
        password: Senha em texto claro — comparada contra SHA-256 armazenado.

    Returns:
        dict com {tenant_id, domain, tenant_name, user_id, user_name,
                  display_name, role} em caso de sucesso, ou None.
    """
    client = get_supabase_client()
    if client is None:
        return None

    domain_slug = domain.lower().strip()
    login_norm  = login.lower().strip()

    # ── 1. Busca tenant ───────────────────────────────────────────────────────
    try:
        resp = (
            client.table("tenants")
            .select("id, display_name, active")
            .eq("domain_slug", domain_slug)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
    except Exception:
        return None

    if not rows:
        return None

    tenant = rows[0]
    if not tenant.get("active", True):
        return None

    tenant_id = tenant["id"]

    # ── 2. Busca usuário ──────────────────────────────────────────────────────
    try:
        resp = (
            client.table("tenant_users")
            .select("id, display_name, role, active, password_hash")
            .eq("tenant_id", tenant_id)
            .eq("login", login_norm)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
    except Exception:
        return None

    if not rows:
        return None

    user = rows[0]
    if not user.get("active", True):
        return None

    # ── 3. Verifica senha ─────────────────────────────────────────────────────
    if user.get("password_hash", "").strip() != _hash(password):
        return None

    return {
        "tenant_id":    tenant_id,
        "domain":       domain_slug,
        "tenant_name":  tenant["display_name"],
        "user_id":      user["id"],
        "user_name":    login_norm,
        "display_name": user["display_name"],
        "role":         user.get("role", "user"),
    }


def login_tenant_debug(domain: str, login: str, password: str) -> tuple[dict | None, str]:
    """Versão diagnóstica de login_tenant — retorna (resultado, motivo_falha).
    Usar apenas para debug; remover após resolver o problema.
    """
    client = get_supabase_client()
    if client is None:
        return None, "Supabase client é None (credenciais não configuradas)"

    domain_slug = domain.lower().strip()
    login_norm  = login.lower().strip()

    try:
        resp = (
            client.table("tenants")
            .select("id, display_name, active")
            .eq("domain_slug", domain_slug)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
    except Exception as e:
        return None, f"Erro na query tenants: {e}"

    if not rows:
        return None, f"Tenant não encontrado para domain_slug='{domain_slug}'"

    tenant = rows[0]
    if not tenant.get("active", True):
        return None, "Tenant inativo"

    tenant_id = tenant["id"]

    try:
        resp = (
            client.table("tenant_users")
            .select("id, display_name, role, active, password_hash")
            .eq("tenant_id", tenant_id)
            .eq("login", login_norm)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
    except Exception as e:
        return None, f"Erro na query tenant_users: {e}"

    if not rows:
        return None, f"Usuário '{login_norm}' não encontrado no tenant {tenant_id}"

    user = rows[0]
    if not user.get("active", True):
        return None, "Usuário inativo"

    stored = user.get("password_hash", "").strip()
    computed = _hash(password)
    if stored != computed:
        return None, f"Hash não confere. Armazenado={stored[:12]}… Calculado={computed[:12]}…"

    result = {
        "tenant_id":    tenant_id,
        "domain":       domain_slug,
        "tenant_name":  tenant["display_name"],
        "user_id":      user["id"],
        "user_name":    login_norm,
        "display_name": user["display_name"],
        "role":         user.get("role", "user"),
    }
    return result, "OK"


def tenant_auth_available() -> bool:
    """True quando o Supabase está configurado e a tabela tenants existe."""
    client = get_supabase_client()
    if client is None:
        return False
    try:
        client.table("tenants").select("id").limit(1).execute()
        return True
    except Exception:
        return False
