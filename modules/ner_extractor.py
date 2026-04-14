# modules/ner_extractor.py
# ─────────────────────────────────────────────────────────────────────────────
# NER para transcrições de reuniões.
#
# Extração em três passes:
#   1. spaCy pt_core_news_lg  — PER→PESSOA, ORG→UNIDADE (confidence 0.8)
#   2. Regex patterns         — CARGO, AREA, UNIDADE, PESSOA (confidence 0.7)
#   3. Dicionário de entidades conhecidas carregado do Supabase (confidence 0.95)
#
# Sem dependências externas além do que já está em requirements.txt
# (spaCy já instalado; unicodedata é stdlib).
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import re
import unicodedata
from typing import Optional

# ── Lazy singleton do modelo spaCy ────────────────────────────────────────────

_nlp = None


def _get_nlp():
    """Carrega pt_core_news_lg uma única vez por processo."""
    global _nlp
    if _nlp is None:
        try:
            import spacy
            _nlp = spacy.load("pt_core_news_lg")
        except Exception:
            _nlp = False  # marca como indisponível para não tentar de novo
    return _nlp if _nlp else None


# ── Padrões regex ─────────────────────────────────────────────────────────────
# Compilados uma vez no nível do módulo.

_PATTERNS: dict[str, list[re.Pattern]] = {
    "PESSOA": [
        # Títulos seguidos de nome
        re.compile(
            r"\b(?:Sr\.?|Sra\.?|Dr\.?|Dra\.?|Eng\.?|Prof\.?|Profa\.?)\s+"
            r"[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ][a-záéíóúâêîôûãõç]+(?:\s+[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ][a-záéíóúâêîôûãõç]+)*",
            re.UNICODE,
        ),
        # Dois ou mais nomes capitalizados (≥3 chars cada)
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
            r"Técnico|Tecnico|Assistente|Subgerente|Subchefe|Gestor[a]?|"
            r"Assessor[a]?|Secretári[ao]|Secretario|Presidente|Vice-Presidente)"
            r"(?:\s+(?:de|do|da|dos|das|de\s+\w+))*",
            re.IGNORECASE | re.UNICODE,
        ),
    ],
    "AREA": [
        # Departamento / Setor / Divisão de X
        re.compile(
            r"\b(?:Departamento|Setor|Divisão|Divisao|Coordenação|Coordenacao|"
            r"Gerência|Gerencia|Célula|Celula|Núcleo|Nucleo)\s+(?:de|do|da|dos|das)\s+"
            r"[A-Za-záéíóúâêîôûãõç]+(?:\s+[A-Za-záéíóúâêîôûãõç]+)*",
            re.UNICODE,
        ),
        # Siglas e áreas comuns
        re.compile(
            r"\b(?:TI|RH|DHO|DP|Financeiro|Contabilidade|Comercial|Jurídico|Juridico|"
            r"Operações|Operacoes|Auditoria|Marketing|Logística|Logistica|Compras|"
            r"Suprimentos|Compliance|Governança|Governanca|Controladoria|"
            r"Recursos\s+Humanos|Tecnologia\s+da\s+Informação|Tecnologia\s+da\s+Informacao)\b",
            re.IGNORECASE | re.UNICODE,
        ),
    ],
    "UNIDADE": [
        # Unidades organizacionais de alto nível
        re.compile(
            r"\b(?:Diretoria|Superintendência|Superintendencia|Secretaria|"
            r"Presidência|Presidencia|Vice-Presidência|Vice-Presidencia|"
            r"Subsecretaria|Subdiretoria|Conselho|Reitoria|Pró-Reitoria)"
            r"(?:\s+(?:de|do|da|dos|das|Executiva?|Geral))*"
            r"(?:\s+[A-Za-záéíóúâêîôûãõç]+(?:\s+[A-Za-záéíóúâêîôûãõç]+)*)?",
            re.IGNORECASE | re.UNICODE,
        ),
        # Unidade / Filial / Regional + qualificador
        re.compile(
            r"\b(?:Unidade|Filial|Regional|Nacional|Estadual|Municipal)\s+"
            r"(?:de\s+)?[A-Za-záéíóúâêîôûãõç]+\b",
            re.IGNORECASE | re.UNICODE,
        ),
    ],
}

# Mapeamento de labels spaCy → tipos do projeto
_SPACY_LABEL_MAP = {
    "PER":  "PESSOA",
    "ORG":  "UNIDADE",
    "LOC":  None,   # ignorado
    "MISC": None,   # ignorado
}


# ── Normalização ──────────────────────────────────────────────────────────────

def normalize_entity(text: str, entity_type: str) -> str:
    """Remove acentos e padroniza o nome para maiúsculas."""
    # NFKD decompõe os caracteres acentuados; filtramos os combining marks
    nfd = unicodedata.normalize("NFKD", text)
    without_accents = "".join(c for c in nfd if not unicodedata.combining(c))
    normalized = without_accents.upper().strip()

    # Simplificações específicas por tipo
    if entity_type == "CARGO":
        for full, short in [
            ("COORDENADOR DE ", "COORDENADOR "),
            ("COORDENADORA DE ", "COORDENADORA "),
            ("GERENTE DE ", "GERENTE "),
            ("DIRETORA DE ", "DIRETORA "),
            ("DIRETOR DE ", "DIRETOR "),
        ]:
            normalized = normalized.replace(full, short)

    return normalized


# ── Extrator principal ────────────────────────────────────────────────────────

class EntityRecognizer:
    """
    Extrai entidades nomeadas de textos de reuniões (PESSOA, AREA, UNIDADE, CARGO).

    Usage:
        rec = EntityRecognizer()
        rec.load_dictionary(project_id)   # opcional — carrega dicionário do Supabase
        entities = rec.extract(transcript)
    """

    def __init__(self):
        self._known: dict[str, list[str]] = {k: [] for k in _PATTERNS}

    # ── Dicionário ────────────────────────────────────────────────────────────

    def load_dictionary(self, project_id: str) -> int:
        """
        Carrega entidades conhecidas da tabela entity_dictionary para este projeto.
        Retorna a quantidade de entidades carregadas.
        """
        try:
            from modules.supabase_client import get_supabase_client
            db = get_supabase_client()
            if not db:
                return 0
            rows = (
                db.table("entity_dictionary")
                .select("entity_text, entity_type")
                .eq("project_id", project_id)
                .execute()
                .data or []
            )
            for row in rows:
                t = row.get("entity_type", "")
                if t in self._known:
                    self._known[t].append(row["entity_text"])
            return len(rows)
        except Exception:
            return 0

    # ── Extração ──────────────────────────────────────────────────────────────

    def extract(self, text: str) -> list[dict]:
        """
        Extrai entidades do texto em três passes e retorna lista deduplicada.

        Cada item:
          text, type, normalized, confidence, start, end, context, source
        """
        entities: list[dict] = []

        # Passe 1: spaCy NER
        nlp = _get_nlp()
        if nlp:
            try:
                doc = nlp(text[:100_000])  # limite de segurança para textos longos
                for ent in doc.ents:
                    mapped = _SPACY_LABEL_MAP.get(ent.label_)
                    if mapped:
                        entities.append({
                            "text":       ent.text,
                            "type":       mapped,
                            "start":      ent.start_char,
                            "end":        ent.end_char,
                            "confidence": 0.8,
                            "source":     "spacy",
                        })
            except Exception:
                pass

        # Passe 2: Regex patterns
        for entity_type, patterns in _PATTERNS.items():
            for pat in patterns:
                for m in pat.finditer(text):
                    entities.append({
                        "text":       m.group().strip(),
                        "type":       entity_type,
                        "start":      m.start(),
                        "end":        m.end(),
                        "confidence": 0.7,
                        "source":     "regex",
                    })

        # Passe 3: Dicionário de entidades conhecidas
        for entity_type, known_list in self._known.items():
            for known in known_list:
                if not known:
                    continue
                pos = 0
                lower_text = text.lower()
                lower_known = known.lower()
                while True:
                    idx = lower_text.find(lower_known, pos)
                    if idx == -1:
                        break
                    entities.append({
                        "text":       text[idx: idx + len(known)],
                        "type":       entity_type,
                        "start":      idx,
                        "end":        idx + len(known),
                        "confidence": 0.95,
                        "source":     "dictionary",
                    })
                    pos = idx + 1

        # Filtrar entidades com texto vazio ou muito curto
        entities = [e for e in entities if len(e["text"].strip()) >= 3]

        # Deduplicar e resolver sobreposições
        entities = self._deduplicate(entities)

        # Adicionar contexto e normalização
        for e in entities:
            ctx_s = max(0, e["start"] - 80)
            ctx_e = min(len(text), e["end"] + 80)
            e["context"]    = text[ctx_s:ctx_e].replace("\n", " ")
            e["normalized"] = normalize_entity(e["text"], e["type"])

        return entities

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _deduplicate(entities: list[dict]) -> list[dict]:
        """
        Remove duplicatas e sobreposições.
        Para spans sobrepostos mantém o de maior confiança.
        """
        # Remover duplicatas exatas (mesmo texto, tipo e posição)
        seen: set[tuple] = set()
        unique: list[dict] = []
        for e in entities:
            key = (e["start"], e["end"], e["type"])
            if key not in seen:
                seen.add(key)
                unique.append(e)

        # Ordenar por posição de início
        unique.sort(key=lambda x: (x["start"], -x["confidence"]))

        # Resolver sobreposições — manter maior confiança
        result: list[dict] = []
        last_end = -1
        for e in unique:
            if e["start"] >= last_end:
                result.append(e)
                last_end = e["end"]
            elif e["confidence"] > result[-1]["confidence"]:
                result[-1] = e
                last_end = e["end"]

        return result


# ── Funções de conveniência ───────────────────────────────────────────────────

def extract_entities(
    text: str,
    project_id: Optional[str] = None,
) -> list[dict]:
    """
    Atalho: cria um EntityRecognizer, carrega dicionário do projeto (se fornecido)
    e executa a extração.
    """
    rec = EntityRecognizer()
    if project_id:
        rec.load_dictionary(project_id)
    return rec.extract(text)


def save_entities(
    meeting_id: str,
    project_id: str,
    entities: list[dict],
) -> tuple[int, str | None]:
    """
    Persiste entidades extraídas na tabela meeting_entities.
    Limpa entidades anteriores da reunião antes de inserir (re-extração idempotente).
    Retorna (n_salvos, erro | None).
    """
    try:
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return 0, "Supabase não configurado."

        # Limpar extração anterior para esta reunião
        db.table("meeting_entities").delete().eq("meeting_id", meeting_id).execute()

        if not entities:
            return 0, None

        rows = [
            {
                "meeting_id":      meeting_id,
                "project_id":      project_id,
                "entity_text":     e["text"],
                "entity_type":     e["type"],
                "normalized_name": e["normalized"],
                "confidence_score": e["confidence"],
                "context":         e.get("context", ""),
                "start_position":  e["start"],
                "end_position":    e["end"],
                "source":          e.get("source", ""),
            }
            for e in entities
        ]

        db.table("meeting_entities").insert(rows).execute()
        return len(rows), None

    except Exception as exc:
        return 0, str(exc)
