# tests/test_bpmn_generator_link_events.py
"""
Tests for the lane-crossing -> Link Event heuristics in
modules/bpmn_generator.py (_detect_crossings / _apply_link_events).

Regression guard for a real diagram found 2026-07-05 (PC131): a 6-lane
single-pool "Governanca de IA" process had a decision in the last lane
(Comite) routing FORWARD straight back to the 2nd lane (EGAI), skipping 3
intermediate lanes (Seguranca/Juridico/Arquitetura) entirely. Heuristic 2
(the only prior lane-spanning check) only flags a skip when the skipped
lanes have elements inside the flow's own column range -- here those lanes'
elements sat in an EARLIER column, so the flow escaped conversion despite
spanning 4 lane boundaries, while a same-node BACKWARD flow of the same span
(caught by Heuristic 4) correctly became Link Events. Heuristic 5 closes
this gap: any flow spanning >= 3 lane boundaries (>= 2 intermediate lanes
skipped) is flagged unconditionally, regardless of column overlap.
"""

import xml.etree.ElementTree as ET

from modules.schema import BpmnProcess, BpmnElement, BpmnPool, BpmnLane, SequenceFlow
from modules.bpmn_generator import generate_bpmn_xml

_NS = "{http://www.omg.org/spec/BPMN/20100524/MODEL}"


def _build_six_lane_process():
    """Mirrors the real "Governanca de IA" case: 6 lanes, a long serial chain
    through 5 of them, then a decision in the last lane routing forward to
    two targets in the 2nd lane (S14, S18) plus one backward to a target
    further back in the 2nd lane (S05) -- the backward one already worked
    (Heuristic 4); the two forward ones are what Heuristic 5 must catch.
    """
    lanes = [
        BpmnLane(id="lane_solicitante", name="Solicitante",
                  element_ids=["ev_start", "S01"]),
        BpmnLane(id="lane_egai", name="EGAI",
                  element_ids=["S02", "S03", "S04", "S05", "S06", "S07", "S08",
                               "S14", "S15", "S18", "ev_end"]),
        BpmnLane(id="lane_seguranca", name="Seguranca", element_ids=["S09"]),
        BpmnLane(id="lane_juridico", name="Juridico", element_ids=["S10"]),
        BpmnLane(id="lane_arquitetura", name="Arquitetura", element_ids=["S11"]),
        BpmnLane(id="lane_comite", name="Comite", element_ids=["S12", "S13"]),
    ]
    pool = BpmnPool(id="pool_1", name="Governanca de IA", lanes=lanes)

    def el(eid, etype, name, actor):
        return BpmnElement(id=eid, type=etype, name=name, actor=actor, lane=actor)

    elements = [
        el("ev_start", "startEvent", "Demanda Identificada", "Solicitante"),
        el("S01", "callActivity", "Submeter Demanda", "Solicitante"),
        el("S02", "callActivity", "Triar Demanda", "EGAI"),
        el("S03", "exclusiveGateway", "Documentacao Completa?", "EGAI"),
        el("S04", "callActivity", "Classificar Risco", "EGAI"),
        el("S05", "callActivity", "Avaliar Preliminarmente", "EGAI"),
        el("S06", "exclusiveGateway", "Risco Aceitavel?", "EGAI"),
        el("S07", "callActivity", "Definir Restricoes", "EGAI"),
        el("S08", "callActivity", "Consolidar Recomendacoes", "EGAI"),
        el("S09", "callActivity", "Avaliar Seguranca", "Seguranca"),
        el("S10", "callActivity", "Avaliar Juridico", "Juridico"),
        el("S11", "callActivity", "Avaliar Arquitetura", "Arquitetura"),
        el("S12", "callActivity", "Revisao do Comite", "Comite"),
        el("S13", "exclusiveGateway", "Decisao do Comite", "Comite"),
        el("S14", "callActivity", "Autorizar e Registrar", "EGAI"),
        el("S15", "callActivity", "Monitoramento Continuo", "EGAI"),
        el("S18", "callActivity", "Implementar Restricoes", "EGAI"),
        el("ev_end", "endEvent", "Iniciativa Aprovada", "EGAI"),
    ]

    flows = [
        SequenceFlow(id="sf_start", source="ev_start", target="S01"),
        SequenceFlow(id="sf_001", source="S01", target="S02"),
        SequenceFlow(id="sf_002", source="S02", target="S03"),
        SequenceFlow(id="sf_003", source="S03", target="S01", name="Informacoes Faltantes"),
        SequenceFlow(id="sf_004", source="S03", target="S04", name="Documentacao Completa"),
        SequenceFlow(id="sf_005", source="S04", target="S05"),
        SequenceFlow(id="sf_006", source="S05", target="S06"),
        SequenceFlow(id="sf_007", source="S06", target="S08", name="Risco Aceitavel"),
        SequenceFlow(id="sf_008", source="S06", target="S07", name="Risco Nao Aceitavel"),
        SequenceFlow(id="sf_009", source="S07", target="S08"),
        SequenceFlow(id="sf_010", source="S08", target="S09"),
        SequenceFlow(id="sf_011", source="S09", target="S10"),
        SequenceFlow(id="sf_012", source="S10", target="S11"),
        SequenceFlow(id="sf_013", source="S11", target="S12"),
        SequenceFlow(id="sf_014", source="S12", target="S13"),
        SequenceFlow(id="sf_015", source="S13", target="S14", name="Aprovar"),
        SequenceFlow(id="sf_016", source="S13", target="S18", name="Aprovar com Restricoes"),
        SequenceFlow(id="sf_017", source="S13", target="S05", name="Solicitar Ajustes"),
        SequenceFlow(id="sf_018", source="S18", target="S14"),
        SequenceFlow(id="sf_019", source="S14", target="S15"),
        SequenceFlow(id="sf_end", source="S15", target="ev_end"),
    ]

    return BpmnProcess(name="Governanca de IA", elements=elements, flows=flows, pools=[pool])


def _link_event_names(xml_str):
    root = ET.fromstring(xml_str)
    throws = {e.get("name") for e in root.iter(f"{_NS}intermediateThrowEvent")}
    catches = {e.get("name") for e in root.iter(f"{_NS}intermediateCatchEvent")}
    return throws, catches


class TestFarLaneSpanHeuristic:
    def test_forward_far_lane_span_converted_to_link_events(self):
        """PC131: S13 (lane 6) -> S14 (lane 2) and S13 -> S18 (lane 2) both
        skip 3 intermediate lanes going FORWARD -- must become Link Events
        even though (in the real case) the skipped lanes' own elements sit
        in an earlier column and don't trip Heuristic 2."""
        bpmn = _build_six_lane_process()
        xml_str = generate_bpmn_xml(bpmn)

        throws, catches = _link_event_names(xml_str)
        assert "Aprovar" in throws and "Aprovar" in catches
        assert "Aprovar com Restricoes" in throws and "Aprovar com Restricoes" in catches

        # The original direct sequenceFlow ids for these two must be gone.
        root = ET.fromstring(xml_str)
        flow_ids = {f.get("id") for f in root.iter(f"{_NS}sequenceFlow")}
        assert "sf_015" not in flow_ids
        assert "sf_016" not in flow_ids

    def test_backward_far_lane_span_still_converted(self):
        """Regression guard: the backward case (already handled by
        Heuristic 4 before this change) must still work after adding
        Heuristic 5 -- no double-processing / id collisions."""
        bpmn = _build_six_lane_process()
        xml_str = generate_bpmn_xml(bpmn)

        throws, catches = _link_event_names(xml_str)
        assert "Solicitar Ajustes" in throws and "Solicitar Ajustes" in catches

    def test_adjacent_lane_flows_stay_direct(self):
        """Regression guard: adjacent-lane flows (span 1, e.g. S08->S09,
        S09->S10, S10->S11, S11->S12) must NOT be converted -- Heuristic 5's
        threshold (>=3) must not catch short hops."""
        bpmn = _build_six_lane_process()
        xml_str = generate_bpmn_xml(bpmn)
        root = ET.fromstring(xml_str)
        flow_ids = {f.get("id") for f in root.iter(f"{_NS}sequenceFlow")}
        for fid in ("sf_010", "sf_011", "sf_012", "sf_013"):
            assert fid in flow_ids, f"{fid} (adjacent-lane) should remain a direct sequenceFlow"

    def test_no_link_events_when_all_lanes_adjacent(self):
        """Regression guard: a simple 2-lane process with only adjacent-lane
        flows must produce zero Link Events."""
        lanes = [
            BpmnLane(id="lane_a", name="A", element_ids=["s1", "t1"]),
            BpmnLane(id="lane_b", name="B", element_ids=["t2", "e1"]),
        ]
        pool = BpmnPool(id="pool_1", name="Processo", lanes=lanes)
        elements = [
            BpmnElement(id="s1", type="startEvent", name="Inicio", actor="A", lane="A"),
            BpmnElement(id="t1", type="userTask", name="Fazer A", actor="A", lane="A"),
            BpmnElement(id="t2", type="userTask", name="Fazer B", actor="B", lane="B"),
            BpmnElement(id="e1", type="endEvent", name="Fim", actor="B", lane="B"),
        ]
        flows = [
            SequenceFlow(id="f1", source="s1", target="t1"),
            SequenceFlow(id="f2", source="t1", target="t2"),
            SequenceFlow(id="f3", source="t2", target="e1"),
        ]
        bpmn = BpmnProcess(name="Simples", elements=elements, flows=flows, pools=[pool])
        xml_str = generate_bpmn_xml(bpmn)
        root = ET.fromstring(xml_str)
        assert list(root.iter(f"{_NS}intermediateThrowEvent")) == []
        assert list(root.iter(f"{_NS}intermediateCatchEvent")) == []
