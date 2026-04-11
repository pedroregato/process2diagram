# modules/text_utils.py
# ─────────────────────────────────────────────────────────────────────────────
# Utilitários de extração de texto — sem dependências externas.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import re

# ── Extração de núcleo nominal de regras de negócio em PT-BR ─────────────────
#
# Técnica: heurística baseada no padrão linguístico das regras de negócio:
#   [Artigo?] [Núcleo nominal] [verbo modal] [predicado]
#
# Exemplos:
#   "O cronograma deve ter data final..." → "Cronograma"
#   "As reuniões de validação dos fluxos devem incluir..." → "Reuniões de validação"
#   "A data de entrega deve ser aprovada..." → "Data de entrega"
#
# Algoritmo:
#   1. Tokenizar por \w+ (ignora pontuação)
#   2. Pular artigos/determinantes iniciais
#   3. Coletar tokens até atingir verbo modal/auxiliar (início do predicado)
#   4. Limitar a 3 tokens e 28 chars; capitalizar
#   Fallback: primeiras 3 palavras com mais de 2 chars

_SKIP_INITIAL: frozenset[str] = frozenset({
    "o", "a", "os", "as", "um", "uma", "uns", "umas",
    "todo", "toda", "todos", "todas", "cada", "qualquer",
    "este", "esta", "estes", "estas", "esse", "essa", "esses", "essas",
    "aquele", "aquela", "aqueles", "aquelas",
})

_MODAL_VERBS: frozenset[str] = frozenset({
    "deve", "devem", "deverá", "deverão", "deveriam",
    "é", "são", "foi", "foram", "será", "serão",
    "pode", "podem", "poderá", "poderão",
    "precisa", "precisam", "precisará",
    "tem", "têm", "terá", "terão",
    "inclui", "incluem", "incluir",
    "exige", "exigem", "requer", "requerem",
    "garante", "garantem", "obriga", "obrigam",
    "representa", "representam", "define", "definem",
    "contém", "contem", "contém",
    "implica", "implicam",
})


# ── Normalização de slug de processo ─────────────────────────────────────────
#
# Usada para comparação de identidade de processos BPMN:
#   "Gestão de Contratos"   → "gestao_contratos"
#   "Fluxo de Aprovação"    → "aprovacao"
#   "Processo de Onboarding" → "onboarding"
#
# Algoritmo:
#   1. Normalizar unicode NFD → remover diacríticos
#   2. Lowercase
#   3. Tokenizar por \w+
#   4. Remover stopwords e termos genéricos de processo
#   5. Juntar com "_"; truncar em max_chars

_PROCESS_STOPWORDS: frozenset[str] = frozenset({
    "o", "a", "os", "as", "e", "de", "do", "da", "dos", "das",
    "em", "no", "na", "nos", "nas", "para", "por", "com", "um", "uma",
    "processo", "fluxo", "diagrama", "procedimento", "roteiro",
    "atividade", "atividades", "workflow", "map", "mapa",
})


def process_slug(name: str, max_chars: int = 60) -> str:
    """Normaliza o nome de um processo BPMN para comparação de identidade.

    Usado para correspondência automática (Opção A): duas reuniões que descrevem
    o mesmo processo produzem o mesmo slug mesmo com variações de capitalização
    ou presença/ausência de preposições.

    Exemplos::

        process_slug("Gestão de Contratos")     → "gestao_contratos"
        process_slug("Fluxo de Aprovação")      → "aprovacao"
        process_slug("Processo de Onboarding")  → "onboarding"
    """
    import unicodedata as _ud
    # Remove diacríticos
    text = _ud.normalize("NFD", name.lower())
    text = "".join(c for c in text if _ud.category(c) != "Mn")
    tokens = re.findall(r"\w+", text)
    tokens = [t for t in tokens if t not in _PROCESS_STOPWORDS and len(t) > 1]
    slug = "_".join(tokens)
    if len(slug) > max_chars:
        slug = slug[:max_chars].rsplit("_", 1)[0]
    return slug or "processo"


# ── Extração de núcleo nominal de regras de negócio em PT-BR ─────────────────

def rule_keyword_pt(statement: str, max_tokens: int = 3, max_chars: int = 28) -> str:
    """Extrai o núcleo nominal (palavra-chave) de uma regra de negócio em PT-BR.

    Projetado para ser chamado no momento da persistência, de modo que o
    resultado seja armazenado como ``nucleo_nominal`` na tabela ``sbvr_rules``
    e reutilizado em todas as exibições subsequentes sem recomputação.

    Retorna string vazia se ``statement`` for vazio ou None.
    """
    if not statement:
        return ""
    tokens = re.findall(r"\w+", statement, re.UNICODE)
    collected: list[str] = []
    for tok in tokens:
        tl = tok.lower()
        # Pular artigos/determinantes enquanto ainda não coletamos nada
        if not collected and tl in _SKIP_INITIAL:
            continue
        # Verbo modal sinaliza início do predicado — núcleo nominal concluído
        if tl in _MODAL_VERBS:
            break
        collected.append(tok)
        if len(collected) >= max_tokens:
            break

    if not collected:
        # Fallback: primeiras 3 palavras substantivas (len > 2)
        collected = [t for t in tokens if len(t) > 2][:3]

    phrase = " ".join(collected)
    if len(phrase) > max_chars:
        phrase = phrase[:max_chars].rsplit(" ", 1)[0]
    return phrase.capitalize() if phrase else ""
