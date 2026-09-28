# evals/bpmn_metrics/metrics.py
# ─────────────────────────────────────────────────────────────────────────────
# Métricas estruturais de qualidade pragmática para BPMN 2.0 (V3 do plano de
# melhorias). Só stdlib — roda sem Streamlit, sem Supabase e sem LLM.
#
# Base: Sánchez-González, García, Ruiz & Mendling (2012), "Quality indicators
# for business process models from a gateway complexity perspective",
# Information and Software Technology 54(11). Mesmas siglas do dataset
# "Camunda's BPMN 2.0 Exploratory Dataset" (Kaggle, A. Kopp, MIT).
#
# Unidade de medida: um <process> (uma pool). Um arquivo com colaboração de
# N pools gera N linhas — igual ao dataset de referência.
#
# Diferença deliberada em relação ao CSV do Kaggle: lá o TNN conta todos os
# filhos do <process> que não são sequenceFlow (inclui laneSet, textAnnotation
# e association). Aqui TNN = TNE + TNA + TNG (só nós de fluxo). Por isso a
# referência é recalculada com este mesmo código sobre os .bpmn originais da
# Camunda (build_reference.py), em vez de usar o CSV do Kaggle.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

ACTIVITY_TAGS = {
    "task", "userTask", "serviceTask", "sendTask", "receiveTask", "manualTask",
    "businessRuleTask", "scriptTask", "subProcess", "callActivity",
    "transaction", "adHocSubProcess",
}
EVENT_TAGS = {
    "startEvent": "TNSE",
    "boundaryEvent": "TNBE",
    "intermediateCatchEvent": "TNIE",
    "intermediateThrowEvent": "TNIE",
    "implicitThrowEvent": "TNIE",
    "endEvent": "TNEE",
}
GATEWAY_KIND = {
    "parallelGateway": "AND",
    "exclusiveGateway": "XOR",
    "eventBasedGateway": "XOR",
    "complexGateway": "XOR",
    "inclusiveGateway": "OR",
}

METRIC_COLUMNS = [
    "TNN", "TNSF", "TNSE", "TNBE", "TNIE", "TNEE", "TNE", "TNA",
    "TNGAND", "TNGXOR", "TNGOR", "TNG", "AGD", "MGD", "CFC", "GM", "GH",
]
FLAG_COLUMNS = [
    "no_start", "no_end", "no_gateway", "orphan_nodes",
    "pass_through_gateways", "mixed_gateways",
    "implicit_joins", "implicit_splits", "goto_events", "link_pairs",
]


def _local(tag: str) -> str:
    """'{ns}exclusiveGateway' → 'exclusiveGateway'."""
    return tag.rsplit("}", 1)[-1]


@dataclass
class ProcessMetrics:
    source: str
    process_id: str
    process_name: str
    TNN: int = 0
    TNSF: int = 0
    TNSE: int = 0
    TNBE: int = 0
    TNIE: int = 0
    TNEE: int = 0
    TNE: int = 0
    TNA: int = 0
    TNGAND: int = 0
    TNGXOR: int = 0
    TNGOR: int = 0
    TNG: int = 0
    AGD: float = 0.0          # grau médio (entrada + saída) dos gateways
    MGD: int = 0              # grau máximo dos gateways
    CFC: int = 0              # Cardoso: XOR-split=fan-out, OR-split=2^n−1, AND-split=1
    GM: int = 0               # mismatch de Mendling: Σ_tipo |Σ fan-out splits − Σ fan-in joins|
    GH: float = 0.0           # heterogeneidade: entropia dos tipos de gateway (log base 3)
    # sinais de modelo incompleto (não entram no índice, mas importam para o Vichāra)
    no_start: bool = False
    no_end: bool = False
    no_gateway: bool = False
    orphan_nodes: int = 0             # nós de fluxo sem nenhuma aresta
    pass_through_gateways: int = 0    # gateway com 1 entrada e 1 saída (inútil)
    mixed_gateways: int = 0           # gateway que é split e join ao mesmo tempo
    implicit_joins: int = 0           # atividade/evento com >1 entrada (merge sem gateway)
    implicit_splits: int = 0          # atividade/evento com >1 saída (split sem gateway)
    goto_events: int = 0              # evento intermediário sem entrada ou sem saída
                                      # (padrão link throw/catch usado como "goto")
    extra: dict = field(default_factory=dict)

    def row(self) -> dict:
        d = asdict(self)
        d.pop("extra")
        d.update(self.extra)
        return d


def _link_key(event: ET.Element) -> str | None:
    """Chave de pareamento throw↔catch se o evento for link, senão None.

    Usa o name do <linkEventDefinition> (ou do evento). Quando vazio — o
    gerador do Vichāra usa o rótulo do fluxo, que costuma ser "" — pareia pelo
    id no padrão link_throw_<orig>_<dest> / link_catch_<orig>_<dest>.
    """
    for sub in event:
        if _local(sub.tag) == "linkEventDefinition":
            name = (sub.get("name") or event.get("name") or "").strip()
            eid = event.get("id", "")
            for prefix in ("link_throw_", "link_catch_"):
                if eid.startswith(prefix):
                    return "id:" + eid[len(prefix):]
            return "name:" + name if name else "id:" + eid
    return None


def _metrics_for_process(proc: ET.Element, source: str, resolve_links: bool = True) -> ProcessMetrics:
    m = ProcessMetrics(
        source=source,
        process_id=proc.get("id", ""),
        process_name=(proc.get("name") or "").strip(),
    )
    node_tag: dict[str, str] = {}       # id → tag local
    links_throw: dict[str, list[str]] = {}   # nome do link → ids dos throws
    links_catch: dict[str, list[str]] = {}   # nome do link → ids dos catches
    flows: list[tuple[str, str]] = []

    for child in proc:
        tag = _local(child.tag)
        cid = child.get("id", "")
        if tag in ACTIVITY_TAGS or tag in EVENT_TAGS or tag in GATEWAY_KIND:
            node_tag[cid] = tag
            if tag in ("intermediateThrowEvent", "intermediateCatchEvent"):
                name = _link_key(child)
                if name is not None:
                    bucket = links_throw if tag == "intermediateThrowEvent" else links_catch
                    bucket.setdefault(name, []).append(cid)
        elif tag == "sequenceFlow":
            flows.append((child.get("sourceRef", ""), child.get("targetRef", "")))

    # Link events são conectores de diagramação (o gerador do Vichāra troca por
    # link throw/catch todo fluxo que cruza ≥ 2 lanes). Para medir o modelo
    # lógico, cada par throw→catch vira um fluxo direto e os dois eventos saem
    # da contagem. Links sem par ficam como estão.
    link_pairs = 0
    if resolve_links:
        for name, throws in links_throw.items():
            catches = links_catch.get(name, [])
            if not catches:
                continue
            link_ids = set(throws) | set(catches)
            sources = [s for s, t in flows if t in throws]
            targets = [t for s, t in flows if s in catches]
            flows = [(s, t) for s, t in flows if s not in link_ids and t not in link_ids]
            flows += [(s, t) for s in sources for t in targets]
            for lid in link_ids:
                node_tag.pop(lid, None)
            link_pairs += 1
    m.extra["link_pairs"] = link_pairs

    gateways: dict[str, str] = {}
    for cid, tag in node_tag.items():
        if tag in ACTIVITY_TAGS:
            m.TNA += 1
        elif tag in EVENT_TAGS:
            setattr(m, EVENT_TAGS[tag], getattr(m, EVENT_TAGS[tag]) + 1)
        else:
            kind = GATEWAY_KIND[tag]
            gateways[cid] = kind
            attr = {"AND": "TNGAND", "XOR": "TNGXOR", "OR": "TNGOR"}[kind]
            setattr(m, attr, getattr(m, attr) + 1)

    m.TNSF = len(flows)
    m.TNE = m.TNSE + m.TNBE + m.TNIE + m.TNEE
    m.TNG = m.TNGAND + m.TNGXOR + m.TNGOR
    m.TNN = m.TNE + m.TNA + m.TNG

    indeg = {n: 0 for n in node_tag}
    outdeg = {n: 0 for n in node_tag}
    for s, t in flows:
        if s in outdeg:
            outdeg[s] += 1
        if t in indeg:
            indeg[t] += 1

    m.orphan_nodes = sum(1 for n in node_tag if indeg[n] == 0 and outdeg[n] == 0)
    for n, tag in node_tag.items():
        if tag in GATEWAY_KIND:
            continue
        m.implicit_joins += indeg[n] > 1
        m.implicit_splits += outdeg[n] > 1
        if EVENT_TAGS.get(tag) == "TNIE" and (indeg[n] == 0) != (outdeg[n] == 0):
            m.goto_events += 1

    degrees = []
    split_fanout = {"AND": 0, "XOR": 0, "OR": 0}
    join_fanin = {"AND": 0, "XOR": 0, "OR": 0}
    for gid, kind in gateways.items():
        i, o = indeg[gid], outdeg[gid]
        degrees.append(i + o)
        if o > 1:
            split_fanout[kind] += o
            m.CFC += {"XOR": o, "OR": 2 ** o - 1, "AND": 1}[kind]
        if i > 1:
            join_fanin[kind] += i
        if i <= 1 and o <= 1:
            m.pass_through_gateways += 1
        if i > 1 and o > 1:
            m.mixed_gateways += 1

    if degrees:
        m.AGD = round(sum(degrees) / len(degrees), 4)
        m.MGD = max(degrees)
    m.GM = sum(abs(split_fanout[k] - join_fanin[k]) for k in split_fanout)

    if m.TNG:
        h = 0.0
        for c in (m.TNGAND, m.TNGXOR, m.TNGOR):
            if c:
                p = c / m.TNG
                h -= p * math.log(p, 3)
        m.GH = round(h, 4)

    m.no_start = m.TNSE == 0
    m.no_end = m.TNEE == 0
    m.no_gateway = m.TNG == 0
    return m


_ATTR_RE = re.compile(rb'\s+([\w:.-]+)\s*=\s*("[^"]*"|\'[^\']*\')')


def repair_duplicate_attributes(xml: bytes) -> bytes:
    """Remove atributos repetidos na tag raiz (ex.: dois xmlns="…").

    Alguns BPMNs antigos do Vichāra (jun/2026) têm xmlns e xmlns:xsi
    declarados duas vezes em <definitions>; parsers estritos recusam o arquivo.
    """
    start = xml.find(b"<", xml.find(b"?>") + 2 if xml.lstrip().startswith(b"<?xml") else 0)
    end = xml.find(b">", start)
    head = xml[start:end]
    seen, out, last = set(), [], 0
    for mt in _ATTR_RE.finditer(head):
        name = mt.group(1)
        if name in seen:
            out.append(head[last:mt.start()])
            last = mt.end()
        seen.add(name)
    out.append(head[last:])
    return xml[:start] + b"".join(out) + xml[end:]


def metrics_from_xml(xml: str | bytes, source: str = "", resolve_links: bool = True) -> list[ProcessMetrics]:
    """Uma entrada por <process> encontrado no documento.

    Se o XML for malformado só por atributos duplicados na raiz, repara e
    marca extra["repaired_xml"] = True.
    """
    if isinstance(xml, str):
        xml = xml.encode("utf-8")
    repaired = False
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        root = ET.fromstring(repair_duplicate_attributes(xml))
        repaired = True
    result = [
        _metrics_for_process(el, source, resolve_links)
        for el in root.iter()
        if _local(el.tag) == "process"
    ]
    for m in result:
        m.extra["repaired_xml"] = repaired
    return result


def metrics_from_file(path: str | Path) -> list[ProcessMetrics]:
    p = Path(path)
    return metrics_from_xml(p.read_bytes(), source=p.name)


def iter_bpmn_files(folder: str | Path) -> Iterable[Path]:
    yield from sorted(Path(folder).rglob("*.bpmn"))


# ── faixas de tamanho usadas na comparação ────────────────────────────────────

SIZE_BANDS = [(0, 9, "<10"), (10, 19, "10–19"), (20, 29, "20–29"), (30, 10**9, "≥30")]


def size_band(tnn: int) -> str:
    for lo, hi, label in SIZE_BANDS:
        if lo <= tnn <= hi:
            return label
    return "?"
