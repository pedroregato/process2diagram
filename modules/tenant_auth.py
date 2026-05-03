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


# ── Master admin CRUD ──────────────────────────────────────────────────────────

def list_all_tenants() -> list[dict]:
    """Lista todos os tenants cadastrados."""
    client = get_supabase_client()
    if client is None:
        return []
    try:
        resp = client.table("tenants").select("id, domain_slug, display_name, active, created_at").order("domain_slug").execute()
        return resp.data or []
    except Exception:
        return []


def list_users_by_tenant(tenant_id: str) -> list[dict]:
    """Lista usuários de um tenant (sem expor password_hash)."""
    client = get_supabase_client()
    if client is None:
        return []
    try:
        resp = (
            client.table("tenant_users")
            .select("id, login, display_name, role, active, google_account, ms_teams_account, created_at")
            .eq("tenant_id", tenant_id)
            .order("login")
            .execute()
        )
        return resp.data or []
    except Exception:
        return []


def create_tenant(domain_slug: str, display_name: str) -> tuple[bool, str]:
    """Cria um novo tenant. Retorna (sucesso, mensagem)."""
    client = get_supabase_client()
    if client is None:
        return False, "Supabase não configurado."
    slug = domain_slug.lower().strip().replace(" ", "_")
    if not slug:
        return False, "Slug do domínio não pode ser vazio."
    try:
        client.table("tenants").insert({"domain_slug": slug, "display_name": display_name.strip()}).execute()
        return True, f"Domínio '{slug}' criado com sucesso."
    except Exception as e:
        return False, f"Erro: {e}"


def create_user(tenant_id: str, login: str, password: str, display_name: str, role: str) -> tuple[bool, str]:
    """Cria um usuário em um tenant. Retorna (sucesso, mensagem)."""
    client = get_supabase_client()
    if client is None:
        return False, "Supabase não configurado."
    login_norm = login.lower().strip()
    if not login_norm or not password or not display_name:
        return False, "Login, senha e nome são obrigatórios."
    try:
        client.table("tenant_users").insert({
            "tenant_id":     tenant_id,
            "login":         login_norm,
            "password_hash": _hash(password),
            "display_name":  display_name.strip(),
            "role":          role,
        }).execute()
        return True, f"Usuário '{login_norm}' criado com sucesso."
    except Exception as e:
        return False, f"Erro: {e}"


def toggle_tenant_active(tenant_id: str, active: bool) -> bool:
    """Ativa ou desativa um tenant."""
    client = get_supabase_client()
    if client is None:
        return False
    try:
        client.table("tenants").update({"active": active}).eq("id", tenant_id).execute()
        return True
    except Exception:
        return False


def toggle_user_active(user_id: str, active: bool) -> bool:
    """Ativa ou desativa um usuário."""
    client = get_supabase_client()
    if client is None:
        return False
    try:
        client.table("tenant_users").update({"active": active}).eq("id", user_id).execute()
        return True
    except Exception:
        return False


def update_user_role(user_id: str, role: str) -> bool:
    """Altera o perfil de um usuário."""
    client = get_supabase_client()
    if client is None:
        return False
    if role not in ("user", "admin", "master"):
        return False
    try:
        client.table("tenant_users").update({"role": role}).eq("id", user_id).execute()
        return True
    except Exception:
        return False


def update_user_accounts(user_id: str, google_account: str, ms_teams_account: str) -> bool:
    """Atualiza as contas Google e Microsoft Teams de um usuário."""
    client = get_supabase_client()
    if client is None:
        return False
    try:
        client.table("tenant_users").update({
            "google_account":   google_account.strip() or None,
            "ms_teams_account": ms_teams_account.strip() or None,
        }).eq("id", user_id).execute()
        return True
    except Exception:
        return False


def reset_user_password(user_id: str, new_password: str) -> bool:
    """Redefine a senha de um usuário (SHA-256)."""
    client = get_supabase_client()
    if client is None:
        return False
    try:
        client.table("tenant_users").update({"password_hash": _hash(new_password)}).eq("id", user_id).execute()
        return True
    except Exception:
        return False
