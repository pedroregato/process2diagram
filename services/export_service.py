# services/export_service.py
def make_filename(base_name: str, ext: str, prefix: str, suffix: str) -> str:
    """Gera nome de arquivo no formato: prefixo_base_sufixo.ext"""
    safe_base = base_name.replace(" ", "_")
    return f"{prefix}{safe_base}{suffix}.{ext.lstrip('.')}"
