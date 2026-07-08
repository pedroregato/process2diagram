# services/export_service.py
def make_filename(base_name: str, ext: str, prefix: str, suffix: str) -> str:
    """Gera nome de arquivo no formato: prefixo_base_sufixo.ext"""
    safe_base = base_name.replace(" ", "_")
    return f"{prefix}{safe_base}{suffix}.{ext.lstrip('.')}"


def format_date_suffix(raw_date) -> str:
    """
    Normaliza uma data de reunião (DD/MM/AAAA extraído pelo LLM, ISO
    AAAA-MM-DD vindo do banco, ou um objeto datetime.date) para um sufixo
    de nome de arquivo — sempre AAAA-MM-DD (seguro para nome de arquivo e
    ordena corretamente numa pasta). PC159: antes, `suffix` era sempre a
    data em que o download foi PEDIDO (`date.today()`), não a data da
    REUNIÃO — dois exports da mesma reunião em dias diferentes geravam
    nomes diferentes, e o nome não ajudava a identificar de qual reunião
    se tratava. Retorna a data de hoje quando raw_date está vazio/ausente.
    """
    import re
    from datetime import date as _date

    if isinstance(raw_date, _date):
        return raw_date.isoformat()

    s = str(raw_date or "").strip()
    if not s or s.lower() in ("none", "null", "—", "-"):
        return _date.today().isoformat()

    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", s)
    if m:
        d, mth, y = m.groups()
        return f"{y}-{mth}-{d}"

    return s[:10].replace("/", "-")
