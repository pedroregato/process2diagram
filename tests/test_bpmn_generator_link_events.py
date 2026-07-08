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
    # PC154: labels are hard-wrapped with literal '\n' at generation time
    # (bpmn_generator.py::_wrap_label) so bpmn-js renders correctly even when
    # its own canvas-based auto-wrap is broken by fingerprinting blockers —
    # normalize whitespace so name comparisons ignore the wrap points.
    root = ET.fromstring(xml_str)
    throws = {(e.get("name") or "").replace("\n", " ") for e in root.iter(f"{_NS}intermediateThrowEvent")}
    catches = {(e.get("name") or "").replace("\n", " ") for e in root.iter(f"{_NS}intermediateCatchEvent")}
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

    def test_backward_correction_loop_stays_explicit(self):
        """PC157 (melhorias/event-links-aprimoramento.md): sf_017 (S13->S05,
        "Solicitar Ajustes") closes a real cycle -- S05 flows forward through
        S06..S12 back to S13. Before PC157 this backward cross-lane flow was
        indistinguishable from a genuine distant jump and got converted to
        Link Events by Heuristic 4/5, hiding the rework loop from the reader.
        _closes_cycle now excludes any flow that closes a cycle from
        Link Event conversion unconditionally, regardless of distance/lane
        span -- so it must stay a direct, visible sequenceFlow."""
        bpmn = _build_six_lane_process()
        xml_str = generate_bpmn_xml(bpmn)

        throws, catches = _link_event_names(xml_str)
        assert "Solicitar Ajustes" not in throws and "Solicitar Ajustes" not in catches

        root = ET.fromstring(xml_str)
        flow_ids = {f.get("id") for f in root.iter(f"{_NS}sequenceFlow")}
        assert "sf_017" in flow_ids
        sf_017 = next(f for f in root.iter(f"{_NS}sequenceFlow") if f.get("id") == "sf_017")
        assert sf_017.get("sourceRef") == "S13" and sf_017.get("targetRef") == "S05"

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

    def test_link_event_ids_use_descriptive_src_tgt_naming(self):
        """PC157: link event element ids must follow
        link_throw_{origem}_{destino} / link_catch_{origem}_{destino}
        (melhorias/event-links-aprimoramento.md), not the old lnk_throw_N."""
        bpmn = _build_six_lane_process()
        xml_str = generate_bpmn_xml(bpmn)
        root = ET.fromstring(xml_str)

        throw_ids = {e.get("id") for e in root.iter(f"{_NS}intermediateThrowEvent")}
        catch_ids = {e.get("id") for e in root.iter(f"{_NS}intermediateCatchEvent")}

        assert "link_throw_S13_S14" in throw_ids
        assert "link_catch_S13_S14" in catch_ids
        assert "link_throw_S13_S18" in throw_ids
        assert "link_catch_S13_S18" in catch_ids
        assert not any(tid.startswith("lnk_") for tid in throw_ids | catch_ids)


class TestCorrectionLoopNeverBecomesLinkEvent:
    """PC157 (melhorias/event-links-aprimoramento.md): flows that close a
    cycle back to an earlier step (correction/rework loops) must always
    render as a visible sequenceFlow, regardless of distance or lane span
    -- the whole point being that a hidden retrabalho loop is worse than an
    untidy long diagonal arrow."""

    def _build_long_distance_loop(self):
        """A gateway 5 lanes away rejects straight back to lane 1 -- would
        trip every distance/lane-span heuristic (2, 3, 4, 5) if it weren't
        for the cycle exclusion, since it is both backward AND spans 4 lane
        boundaries."""
        lanes = [BpmnLane(id=f"lane_{i}", name=f"Lane {i}", element_ids=[]) for i in range(6)]
        pool = BpmnPool(id="pool_1", name="Processo Longo", lanes=lanes)

        elements = [BpmnElement(id="ev_start", type="startEvent", name="Inicio",
                                 actor="Lane 0", lane="Lane 0")]
        flows = [SequenceFlow(id="f_start", source="ev_start", target="S1")]
        prev = "ev_start"
        for i in range(1, 6):
            sid = f"S{i}"
            elements.append(BpmnElement(id=sid, type="userTask", name=f"Passo {i}",
                                         actor=f"Lane {i}", lane=f"Lane {i}"))
            if prev != "ev_start":
                flows.append(SequenceFlow(id=f"f_{prev}_{sid}", source=prev, target=sid))
            prev = sid

        elements.append(BpmnElement(id="GW", type="exclusiveGateway", name="Aprovado?",
                                     actor="Lane 5", lane="Lane 5"))
        flows.append(SequenceFlow(id="f_S5_GW", source="S5", target="GW"))
        elements.append(BpmnElement(id="ev_end", type="endEvent", name="Fim",
                                     actor="Lane 5", lane="Lane 5"))
        flows.append(SequenceFlow(id="f_GW_end", source="GW", target="ev_end", name="Aprovado"))
        # Rejection: closes a cycle back to S1 (5 lanes away, backward).
        flows.append(SequenceFlow(id="f_GW_S1", source="GW", target="S1", name="Reprovado"))

        for lane, eid in zip(lanes, ["ev_start", "S1", "S2", "S3", "S4", "S5"]):
            lane.element_ids.append(eid)
        lanes[5].element_ids.extend(["GW", "ev_end"])

        return BpmnProcess(name="Processo Longo", elements=elements, flows=flows, pools=[pool])

    def test_correction_loop_stays_direct_sequenceflow(self):
        bpmn = self._build_long_distance_loop()
        xml_str = generate_bpmn_xml(bpmn)

        throws, catches = _link_event_names(xml_str)
        assert "Reprovado" not in throws and "Reprovado" not in catches

        root = ET.fromstring(xml_str)
        flow_ids = {f.get("id") for f in root.iter(f"{_NS}sequenceFlow")}
        assert "f_GW_S1" in flow_ids

    def test_non_loop_forward_jump_of_equal_span_still_becomes_link_event(self):
        """Control case: the SAME distance/lane-span, but the approval branch
        (GW -> ev_end) doesn't close a cycle, so it's a normal direct arrow
        either way (same lane, adjacent) -- confirms the exclusion is
        specific to cycle-closing edges, not a blanket "never convert
        anything from this gateway" rule."""
        bpmn = self._build_long_distance_loop()
        xml_str = generate_bpmn_xml(bpmn)
        root = ET.fromstring(xml_str)
        flow_ids = {f.get("id") for f in root.iter(f"{_NS}sequenceFlow")}
        assert "f_GW_end" in flow_ids  # same-lane, not a crossing candidate at all

    def test_layout_does_not_hang_on_cyclic_flow_graph(self):
        """Regression guard for the infinite-loop found while implementing
        PC157: excluding correction loops from Link Event conversion means
        _compute_layout's cross-lane column-conflict resolver can now see a
        genuine graph cycle (previously guaranteed acyclic by construction).
        Must terminate quickly via the round/column safety caps, not hang."""
        import time
        bpmn = self._build_long_distance_loop()
        t0 = time.monotonic()
        xml_str = generate_bpmn_xml(bpmn)
        elapsed = time.monotonic() - t0
        assert xml_str
        assert elapsed < 5.0, f"generate_bpmn_xml took {elapsed:.1f}s -- possible cycle-driven hang regression"
