# modules/ner_extractor.py
# ─────────────────────────────────────────────────────────────────────────────
# NER extraction façade.
#
# Primary path : AgentNER (LLM-based) — requires client_info + provider_cfg.
# Fallback path: spaCy pt_core_news_lg + regex — used when no LLM is configured.
#
# Deduplication:
#   - Within an extraction run: by (normalized_name, entity_type)
#   - Within a meeting in the DB: save_entities() deletes previous entries
#     before inserting, so re-runs are idempotent.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import re
import unicodedata
from typing import Optional

# ── Normalisation (shared by both paths) ─────────────────────────────────────

def normalize_entity(text: str, entity_type: str = "") -> str:
    """Remove accents and uppercase. Light simplification for CARGO."""
    nfd = unicodedata.normalize("NFKD", text)
    normalized = "".join(c for c in nfd if not unicodedata.combining(c)).upper().strip()
    if entity_type == "CARGO":
        for full, short in [
            ("COORDENADOR DE ", "COORDENADOR "),
            ("COORDENADORA DE ", "COORDENADORA "),
            ("GERENTE DE ", "GERENTE "),
            ("DIRETOR DE ", "DIRETOR "),
            ("DIRETORA DE ", "DIRETORA "),
        ]:
            normalized = normalized.replace(full, short)
    return normalized


# ── spaCy singleton (fallback path) ──────────────────────────────────────────

_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        try:
            import spacy
            _nlp = spacy.load("pt_core_news_lg")
        except Exception:
            _nlp = False
    return _nlp if _nlp else None


# ── Regex patterns (fallback path) ───────────────────────────────────────────

_PATTERNS: dict[str, list[re.Pattern]] = {
    "PESSOA": [
        re.compile(
            r"\b(?:Sr\.?|Sra\.?|Dr\.?|Dra\.?|Eng\.?|Prof\.?|Profa\.?)\s+"
            r"[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ][a-záéíóúâêîôûãõç]+(?:\s+[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ][a-záéíóúâêîôûãõç]+)*",
            re.UNICODE,
        ),
        re.compile(
            r"\b[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ][a-záéíóúâêîôûãõç]{2,}"
            r"(?:\s+[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ][a-záéíóúâêîôûãõç]{2,})+\b",
            re.UNICODE,
        ),
    ],
    "CARGO": [
        re.compile(
            r"\b(?:Coordenador[a]?|Gerente|Analista|Auditor[a]?|Diretor[a]?|"
            r"Supervisor[a]?|Consultor[a]?|Chefe|Líder|Lider|Especialista|"
            r"Técnico|Tecnico|Assistente|Subgerente|Gestor[a]?|Assessor[a]?|"
            r"Secretári[ao]|Secretario|Presidente|Vice-Presidente)"
            r"(?:\s+(?:de|do|da|dos|das|de\s+\w+))*",
            re.IGNORECASE | re.UNICODE,
        ),
    ],
    "AREA": [
        re.compile(
            r"\b(?:Departamento|Setor|Divisão|Divisao|Coordenação|Coordenacao|"
            r"Gerência|Gerencia|Célula|Celula|Núcleo|Nucleo)\s+(?:de|do|da|dos|das)\s+"
            r"[A-Za-záéíóúâêîôûãõç]+(?:\s+[A-Za-záéíóúâêîôûãõç]+)*",
            re.UNICODE,
        ),
        re.compile(
            r"\b(?:TI|RH|DHO|DP|Financeiro|Contabilidade|Comercial|Jurídico|Juridico|"
            r"Operações|Operacoes|Auditoria|Marketing|Logística|Logistica|Compras|"
            r"Suprimentos|Compliance|Governança|Governanca|Controladoria|"
            r"Recursos\s+Humanos|Tecnologia\s+da\s+Informação|Tecnologia\s+da\s+Informacao)\b",
            re.IGNORECASE | re.UNICODE,
        ),
    ],
    "UNIDADE": [
        re.compile(
            r"\b(?:Diretoria|Superintendência|Superintendencia|Secretaria|"
            r"Presidência|Presidencia|Vice-Presidência|Vice-Presidencia|"
            r"Subsecretaria|Subdiretoria|Conselho|Reitoria|Pró-Reitoria)"
            r"(?:\s+(?:de|do|da|dos|das|Executiva?|Geral))*"
            r"(?:\s+[A-Za-záéíóúâêîôûãõç]+(?:\s+[A-Za-záéíóúâêîôûãõç]+)*)?",
            re.IGNORECASE | re.UNICODE,
        ),
    ],
}

_SPACY_LABEL_MAP = {"PER": "PESSOA", "ORG": "UNIDADE"}


# ── Fallback extraction (spaCy + regex + dictionary) ─────────────────────────

def _extract_fallback(text: str, known: dict[str, list[str]]) -> list[dict]:
    """spaCy + regex + dictionary extraction — used when no LLM is configured."""
    entities: list[dict] = []

    nlp = _get_nlp()
    if nlp:
        try:
            doc = nlp(text[:100_000])
            for ent in doc.ents:
                mapped = _SPACY_LABEL_MAP.get(ent.label_)
                if mapped:
                    entities.append({
                        "text": ent.text, "type": mapped,
                        "start": ent.start_char, "end": ent.end_char,
                        "confidence": 0.8, "source": "spacy",
                    })
        except Exception:
            pass

    for entity_type, patterns in _PATTERNS.items():
        for pat in patterns:
            for m in pat.finditer(text):
                entities.append({
                    "text": m.group().strip(), "type": entity_type,
                    "start": m.start(), "end": m.end(),
                    "confidence": 0.7, "source": "regex",
                })

    for entity_type, known_list in known.items():
        lower_text = text.lower()
        for known_item in known_list:
            if not known_item:
                continue
            pos = 0
            lower_known = known_item.lower()
            while True:
                idx = lower_text.find(lower_known, pos)
                if idx == -1:
                    break
                entities.append({
                    "text": text[idx: idx + len(known_item)], "type": entity_type,
                    "start": idx, "end": idx + len(known_item),
                    "confidence": 0.95, "source": "dictionary",
                })
                pos = idx + 1

    entities = [e for e in entities if len(e["text"].strip()) >= 3]
    entities = _dedup_fallback(entities)

    for e in entities:
        ctx_s = max(0, e["start"] - 80)
        ctx_e = min(len(text), e["end"] + 80)
        e["context"]    = text[ctx_s:ctx_e].replace("\n", " ")
        e["normalized"] = normalize_entity(e["text"], e["type"])

    return entities


def _dedup_fallback(entities: list[dict]) -> list[dict]:
    entities.sort(key=lambda x: (x["start"], -x["confidence"]))
    result: list[dict] = []
    last_end = -1
    for e in entities:
        if e["start"] >= last_end:
            result.append(e)
            last_end = e["end"]
        elif e["confidence"] > result[-1]["confidence"]:
            result[-1] = e
            last_end = e["end"]
    return result


# ── Public API ────────────────────────────────────────────────────────────────

def load_dictionary(project_id: str) -> dict[str, list[str]]:
    """Load known entities from entity_dictionary for the project."""
    known: dict[str, list[str]] = {"PESSOA": [], "AREA": [], "UNIDADE": [], "CARGO": []}
    try:
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return known
        rows = (
            db.table("entity_dictionary")
            .select("entity_text, entity_type")
            .eq("project_id", project_id)
            .execute()
            .data or []
        )
        for row in rows:
            t = row.get("entity_type", "")
            if t in known:
                known[t].append(row["entity_text"])
    except Exception:
        pass
    return known


def extract_entities(
    text: str,
    project_id: Optional[str] = None,
    client_info: Optional[dict] = None,
    provider_cfg: Optional[dict] = None,
) -> tuple[list[dict], int]:
    """
    Extract entities from text.

    - LLM path (primary): when client_info and provider_cfg are provided.
    - Fallback path: spaCy + regex + dictionary when LLM is unavailable.

    Returns (entities, tokens_used). tokens_used is 0 for the fallback path.
    """
    if client_info and provider_cfg and client_info.get("api_key"):
        try:
            from agents.agent_ner import AgentNER
            agent = AgentNER(client_info, provider_cfg)
            entities, tokens = agent.extract_entities(text)
            # Merge with dictionary entities (high confidence, explicit names)
            if project_id:
                known = load_dictionary(project_id)
                existing_keys = {(e["normalized"], e["type"]) for e in entities}
                for entity_type, known_list in known.items():
                    lower_text = text.lower()
                    for known_item in known_list:
                        if not known_item:
                            continue
                        if known_item.lower() in lower_text:
                            norm = normalize_entity(known_item, entity_type)
                            key = (norm, entity_type)
                            if key not in existing_keys:
                                entities.append({
                                    "text": known_item, "type": entity_type,
                                    "normalized": norm, "confidence": 0.95,
                                    "context": "", "source": "dictionary",
                                    "start": 0, "end": 0,
                                })
                                existing_keys.add(key)
            return entities, tokens
        except Exception:
            pass  # fall through to regex/spaCy

    # Fallback: spaCy + regex + dictionary
    known = load_dictionary(project_id) if project_id else {"PESSOA": [], "AREA": [], "UNIDADE": [], "CARGO": []}
    entities = _extract_fallback(text, known)
    return entities, 0


def save_entities(
    meeting_id: str,
    project_id: str,
    entities: list[dict],
) -> tuple[int, str | None]:
    """
    Persist entities to meeting_entities.
    Deletes previous extraction for this meeting first (idempotent re-runs).
    Deduplicates by (normalized_name, entity_type) before inserting.
    Returns (n_saved, error | None).
    """
    try:
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return 0, "Supabase não configurado."

        db.table("meeting_entities").delete().eq("meeting_id", meeting_id).execute()

        if not entities:
            return 0, None

        # Final deduplication before insert: keep one per (normalized_name, type)
        seen: set[tuple] = set()
        rows = []
        for e in entities:
            key = (e.get("normalized", ""), e.get("type", ""))
            if key in seen:
                continue
            seen.add(key)
            rows.append({
                "meeting_id":       meeting_id,
                "project_id":       project_id,
                "entity_text":      e["text"],
                "entity_type":      e["type"],
                "normalized_name":  e.get("normalized", ""),
                "confidence_score": e.get("confidence", 0.9),
                "context":          e.get("context", ""),
                "start_position":   e.get("start", 0),
                "end_position":     e.get("end", 0),
                "source":           e.get("source", ""),
            })

        db.table("meeting_entities").insert(rows).execute()
        return len(rows), None

    except Exception as exc:
        return 0, str(exc)
