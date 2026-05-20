# modules/billing.py
# ─────────────────────────────────────────────────────────────────────────────
# Billing & Credits — voluntary donations + paid plans.
#
# Design:
#   - PLANS: source of truth for pricing (edit here, UI updates automatically)
#   - user_credits table: per-user balance + trial state
#   - pagamentos table: immutable payment log
#   - All Supabase calls are fail-open (return None/False/[] on error)
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ── Plan catalog ──────────────────────────────────────────────────────────────

@dataclass
class Plan:
    key:       str
    label:     str
    valor:     float   # R$
    creditos:  int     # number of pipeline runs; 0 = unlimited
    ilimitado: bool = False
    destaque:  bool = False  # highlighted as "popular" in UI


PLANS: list[Plan] = [
    Plan("p10",  "Basico",        10.0,  15),
    Plan("p20",  "Essencial",     20.0,  40, destaque=True),
    Plan("p35",  "Profissional",  35.0,  80),
    Plan("p50",  "Avancado",      50.0, 120),
    Plan("p80",  "Ilimitado",     80.0,   0, ilimitado=True),
]


def get_plan(key: str) -> Optional[Plan]:
    return next((p for p in PLANS if p.key == key), None)


# ── Supabase helpers ──────────────────────────────────────────────────────────

def _db():
    from modules.supabase_client import get_supabase_client
    return get_supabase_client()


# ── user_credits CRUD ─────────────────────────────────────────────────────────

def get_user_credits(user_id: str) -> Optional[dict]:
    """Return the user_credits row for user_id, or None."""
    try:
        db = _db()
        if not db:
            return None
        rows = db.table("user_credits").select("*").eq("user_id", user_id).limit(1).execute().data or []
        return rows[0] if rows else None
    except Exception:
        return None


def upsert_credits(user_id: str, email: str, delta: int, plano: str = "") -> bool:
    """Add (positive) or subtract (negative) credits. Creates row if absent."""
    try:
        db = _db()
        if not db:
            return False
        existing = get_user_credits(user_id)
        if existing:
            new_total = max(0, existing.get("creditos_restantes", 0) + delta)
            patch: dict = {"creditos_restantes": new_total}
            if plano:
                patch["plano"] = plano
            db.table("user_credits").update(patch).eq("user_id", user_id).execute()
        else:
            db.table("user_credits").insert({
                "user_id":            user_id,
                "email":              email,
                "creditos_restantes": max(0, delta),
                "plano":              plano,
                "degustacao_ativa":   True,
            }).execute()
        return True
    except Exception:
        return False


def set_contribuidor(user_id: str, value: bool) -> bool:
    try:
        db = _db()
        if not db:
            return False
        db.table("user_credits").update({"is_contribuidor": value}).eq("user_id", user_id).execute()
        return True
    except Exception:
        return False


def reset_trial(user_id: str) -> bool:
    """Re-enable trial and zero credits for a user."""
    try:
        db = _db()
        if not db:
            return False
        db.table("user_credits").update({
            "degustacao_ativa":          True,
            "data_expiracao_degustacao": None,
            "creditos_restantes":        0,
        }).eq("user_id", user_id).execute()
        return True
    except Exception:
        return False


def list_users_credits(limit: int = 200) -> list[dict]:
    try:
        db = _db()
        if not db:
            return []
        return (
            db.table("user_credits")
            .select("*")
            .order("updated_at", desc=True)
            .limit(limit)
            .execute().data or []
        )
    except Exception:
        return []


# ── pagamentos CRUD ───────────────────────────────────────────────────────────

def log_payment(
    user_id:     str,
    email:       str,
    valor:       float,
    plano:       str,
    creditos:    int,
    status:      str = "simulated",
    external_id: str = "",
) -> bool:
    """Append an immutable payment record."""
    try:
        db = _db()
        if not db:
            return False
        db.table("pagamentos").insert({
            "user_id":     user_id,
            "email":       email,
            "valor":       valor,
            "plano":       plano,
            "creditos":    creditos,
            "status":      status,
            "external_id": external_id,
        }).execute()
        return True
    except Exception:
        return False


def list_payments(limit: int = 200) -> list[dict]:
    try:
        db = _db()
        if not db:
            return []
        return (
            db.table("pagamentos")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute().data or []
        )
    except Exception:
        return []
