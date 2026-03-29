# agents/nlp_chunker.py
# ─────────────────────────────────────────────────────────────────────────────
# NLP/Chunker Agent — pre-processing WITHOUT an LLM call.
#
# Responsibility:
#   1. Clean and normalize transcript text
#   2. Segment text into classified chunks (process, actor, rule, goal, data)
#   3. Extract named entities: persons, roles, systems, documents
#   4. Detect language
#   5. Produce NLPEnvelope for downstream agents
#
# Strategy (PC1 — no LLM):
#   - spaCy pt_core_news_lg for NER and sentence splitting
#   - Falls back to rule-based segmentation if spaCy model not available
#
# PC2 upgrade path:
#   - Replace _classify_segment() with a lightweight LLM call (Groq/LLaMA)
#     for higher accuracy on ambiguous segments.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import re
from typing import Optional

from core.knowledge_hub import KnowledgeHub, NLPEnvelope, NLPSegment


# ── Segment classification patterns ──────────────────────────────────────────

_PROCESS_SIGNALS = re.compile(
    r"\b(passo|etapa|atividade|tarefa|fluxo|processo|step|task|"
    r"então|depois|em seguida|na sequência|primeiro|segundo|terceiro|"
    r"iniciar|executar|realizar|enviar|receber|aprovar|validar|gerar|"
    r"criar|abrir|fechar|registrar|notificar|arquivar|publicar)\b",
    re.IGNORECASE,
)

_RULE_SIGNALS = re.compile(
    r"\b(deve|não pode|obrigatório|proibido|somente se|apenas quando|"
    r"é necessário|é obrigatório|requer|exige|condição|restrição|"
    r"must|shall|required|forbidden|only if)\b",
    re.IGNORECASE,
)

_GOAL_SIGNALS = re.compile(
    r"\b(objetivo|meta|visão|missão|estratégia|intenção|propósito|"
    r"goal|vision|mission|strategy|target)\b",
    re.IGNORECASE,
)

_ACTOR_SIGNALS = re.compile(
    r"\b(equipe|time|departamento|área|setor|gerente|coordenador|analista|"
    r"sistema|plataforma|ferramenta|cliente|usuário|responsável|"
    r"team|manager|analyst|system|user|customer)\b",
    re.IGNORECASE,
)

_STEP_SPLITTERS = [
    re.compile(r"^\s*\d+[\)\.\-]\s+"),                  # "1) ...", "1. ..."
    re.compile(r"^\s*[-•]\s+"),                          # bullets
    re.compile(r"^\s*(passo|etapa|step)\s*\d*[:\-]\s+", re.IGNORECASE),
]

_NARRATIVE_SPLITTER = re.compile(
    r"\b(então|depois|em seguida|na sequência|subsequently|then|next|after that)\b[,:]?\s*",
    re.IGNORECASE,
)


# ── spaCy cache — loaded once per process, not per instantiation ─────────────

def _load_spacy_cached():
    """
    Load spaCy model once and cache at module level.
    Called by NLPChunker._load_spacy() on first instantiation only.
    """
    if not hasattr(_load_spacy_cached, "_cache"):
        try:
            import spacy
            try:
                _load_spacy_cached._cache = spacy.load("pt_core_news_lg")
            except OSError:
                try:
                    _load_spacy_cached._cache = spacy.load("pt_core_news_sm")
                except OSError:
                    _load_spacy_cached._cache = None
        except ImportError:
            _load_spacy_cached._cache = None
    return _load_spacy_cached._cache


# ── NLP Chunker ───────────────────────────────────────────────────────────────

class NLPChunker:
    """
    Lightweight NLP pre-processor. No LLM required.
    Uses spaCy when available; falls back to rule-based processing.
    """

    def __init__(self):
        self._nlp = self._load_spacy()

    # ── Public API ────────────────────────────────────────────────────────────

    def run(self, hub: KnowledgeHub) -> KnowledgeHub:
        """Process transcript and populate hub.nlp. Also sets hub.transcript_clean.

        If hub.transcript_clean is already populated (by TranscriptPreprocessor),
        uses it as the base and applies whitespace normalization only.
        Otherwise falls back to the full _clean() pass.
        """
        base = hub.transcript_clean if hub.transcript_clean else hub.transcript_raw
        clean = self._normalize_whitespace(base)
        hub.transcript_clean = clean

        segments = self._segment_and_classify(clean)
        actors = self._extract_actors(clean, segments)
        entities = self._extract_entities(clean)
        lang = self._detect_language(clean)

        hub.nlp = NLPEnvelope(
            segments=segments,
            actors=actors,
            entities=entities,
            language_detected=lang,
            ready=True,
        )
        hub.bump()
        return hub

    # ── Cleaning ──────────────────────────────────────────────────────────────

    @staticmethod
    def _clean(text: str) -> str:
        """Normalize whitespace and remove spoken-language fillers.

        Kept for backward compatibility. In the main pipeline this is no longer
        called directly — use _normalize_whitespace() instead, since filler
        removal is handled upstream by TranscriptPreprocessor.
        """
        fillers = re.compile(
            r"\b(ã+|é+|ah+|eh+|uh+|hmm+|né|tá|tô|aí|bom|então\.\.\.|"
            r"type\.\.\.|um+|uh+|you know|like|so|well)\b",
            re.IGNORECASE,
        )
        text = re.sub(r"\r\n|\r", "\n", text)
        text = fillers.sub("", text)
        text = re.sub(r"\s{2,}", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        """Light normalization pass: line endings, excess whitespace only.

        Does NOT remove fillers — those are already handled by TranscriptPreprocessor.
        Called by run() when transcript_clean has been pre-populated.
        """
        text = re.sub(r"\r\n|\r", "\n", text)
        text = re.sub(r"[^\S\n]{2,}", " ", text)   # collapse inline spaces only
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    # ── Segmentation ──────────────────────────────────────────────────────────

    def _segment_and_classify(self, text: str) -> list[NLPSegment]:
        """Split text into chunks and classify each one."""
        chunks = self._split_into_chunks(text)
        return [
            NLPSegment(
                text=chunk,
                segment_type=self._classify_segment(chunk),
                actors=self._actors_in_chunk(chunk),
                keywords=self._keywords_in_chunk(chunk),
            )
            for chunk in chunks
            if chunk.strip()
        ]

    @staticmethod
    def _split_into_chunks(text: str) -> list[str]:
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        chunks: list[str] = []
        current: list[str] = []

        for line in lines:
            is_new = any(p.match(line) for p in _STEP_SPLITTERS)
            if is_new and current:
                chunks.append(" ".join(current).strip())
                cleaned = re.sub(
                    r"^\s*(\d+[\)\.\-]|[-•]|passo|etapa|step)\s*\d*[:\-]?\s*",
                    "", line, flags=re.IGNORECASE
                ).strip()
                current = [cleaned]
            else:
                current.append(line)

        if current:
            chunks.append(" ".join(current).strip())

        # Fallback: split by narrative connectors if no structured markers found
        if len(chunks) <= 1 and text.strip():
            parts = _NARRATIVE_SPLITTER.split(text)
            chunks = [p.strip(" ,;:.") for p in parts if p and len(p.strip()) > 10]

        return chunks[:40]  # safety cap

    @staticmethod
    def _classify_segment(text: str) -> str:
        """Classify segment into one of: process | rule | goal | actor | other."""
        if _RULE_SIGNALS.search(text):
            return "rule"
        if _GOAL_SIGNALS.search(text):
            return "goal"
        if _PROCESS_SIGNALS.search(text):
            return "process"
        if _ACTOR_SIGNALS.search(text):
            return "actor"
        return "process"  # default assumption

    # ── Entity extraction ─────────────────────────────────────────────────────

    def _extract_actors(self, text: str, segments: list[NLPSegment]) -> list[str]:
        """Extract unique actor names from all segments + spaCy NER."""
        actor_set: set[str] = set()

        # From segment-level actor detection
        for seg in segments:
            actor_set.update(seg.actors)

        # spaCy PERSON / ORG entities
        if self._nlp:
            doc = self._nlp(text[:4000])  # limit for performance
            for ent in doc.ents:
                if ent.label_ in ("PER", "PERSON", "ORG"):
                    actor_set.add(ent.text.strip())

        # Inline pattern: "Actor:" at line start
        for match in re.finditer(r"^([A-Za-zÀ-ÿ ]{2,30})\s*:", text, re.MULTILINE):
            candidate = match.group(1).strip()
            if len(candidate.split()) <= 4:
                actor_set.add(candidate)

        return sorted(a for a in actor_set if a and len(a) > 1)

    def _extract_entities(self, text: str) -> list[dict]:
        """Run spaCy NER and return entity list."""
        if not self._nlp:
            return []
        doc = self._nlp(text[:4000])
        return [
            {"text": ent.text, "label": ent.label_, "start": ent.start_char, "end": ent.end_char}
            for ent in doc.ents
        ]

    @staticmethod
    def _actors_in_chunk(text: str) -> list[str]:
        actors = []
        m = re.match(r"^([A-Za-zÀ-ÿ ]{2,30})\s*:\s*", text)
        if m:
            actors.append(m.group(1).strip())
        for m2 in _ACTOR_SIGNALS.finditer(text):
            word = m2.group(0).strip()
            if word not in actors:
                actors.append(word)
        return actors[:5]

    @staticmethod
    def _keywords_in_chunk(text: str) -> list[str]:
        words = re.findall(r"\b[A-Za-zÀ-ÿ]{4,}\b", text)
        seen, result = set(), []
        for w in words:
            lw = w.lower()
            if lw not in seen:
                seen.add(lw)
                result.append(w)
        return result[:10]

    # ── Language detection ────────────────────────────────────────────────────

    @staticmethod
    def _detect_language(text: str) -> str:
        """Naive heuristic: count Portuguese vs English stopwords."""
        pt_words = {"de", "do", "da", "em", "para", "que", "com", "uma", "não", "por"}
        en_words = {"the", "is", "are", "and", "in", "of", "to", "that", "with", "not"}
        words = set(re.findall(r"\b\w+\b", text.lower()))
        pt_score = len(words & pt_words)
        en_score = len(words & en_words)
        return "pt" if pt_score >= en_score else "en"

    # ── spaCy loader ──────────────────────────────────────────────────────────

    @staticmethod
    def _load_spacy():
        """Try to load spaCy model. Result is cached at class level after first call."""
        return _load_spacy_cached()
