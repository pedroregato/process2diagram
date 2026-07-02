# core/tools/_shared.py
# Small helpers shared across AssistantToolExecutor mixins.

_PT_NAME_PREPS = {"de", "da", "do", "dos", "das", "e", "a", "o", "em"}


def _compute_initials(name: str) -> str:
    """'Maria de Fátima Duarte Miranda' → 'MFDM' (ignora preposições PT)."""
    return "".join(
        p[0].upper()
        for p in name.strip().split()
        if p.lower() not in _PT_NAME_PREPS and p
    )
