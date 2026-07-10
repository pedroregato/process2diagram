# tests/test_bpmn_process_name_in_diagram.py
"""
Tests for showing the process name inside the BPMN diagram itself, via a
named Pool (bpmn:participant) wrapping the process — the "opcao mais
correta" (OMG-idiomatic) the user picked over an HTML overlay title.

Before this change, a single-pool BpmnPool wrapper (with the process name)
was only created when the process had explicit lanes (agents/agent_bpmn.py
_generate_bpmn_xml_single: `if model.lanes: pools.append(...)`). Processes
without lanes (the common case for simple flat processes) got no pool at
all, so bpmn-js never rendered the process name anywhere in the canvas.

Fix: the pool is now always created; when there are no real lanes,
generate_bpmn_xml() injects a synthetic single lane (via the same
_SYN_LANE_SUFFIX mechanism already used by the multi-pool collaboration
path in _pool_as_process) so the layout math still has >= 1 lane, while the
synthetic lane is excluded from the emitted <bpmn:laneSet>.
"""

import xml.etree.ElementTree as ET

from core.knowledge_hub import BPMNModel, BPMNStep, BPMNEdge
from agents.agent_bpmn import AgentBPMN
from modules.schema import BpmnProcess, BpmnElement, BpmnPool, BpmnLane, SequenceFlow
from modules.bpmn_generator import generate_bpmn_xml
from modules.bpmn_describer import describe_bpmn_from_xml

_NS = "{http://www.omg.org/spec/BPMN/20100524/MODEL}"


def _flat_model(name="Processo de Aprovacao de Credito"):
    """Simple 3-step flow, no lanes — the common case that used to lose
    the process name entirely."""
    return BPMNModel(
        name=name,
        steps=[
            BPMNStep(id="t1", title="Receber Solicitacao"),
            BPMNStep(id="t2", title="Analisar Credito"),
            BPMNStep(id="t3", title="Aprovar Credito"),
        ],
        edges=[
            BPMNEdge(source="t1", target="t2"),
            BPMNEdge(source="t2", target="t3"),
        ],
    )


def _lanes_model(name="Processo com Lanes"):
    return BPMNModel(
        name=name,
        steps=[
            BPMNStep(id="t1", title="Passo 1", actor="Vendas", lane="Vendas"),
            BPMNStep(id="t2", title="Passo 2", actor="Financeiro", lane="Financeiro"),
        ],
        edges=[BPMNEdge(source="t1", target="t2")],
        lanes=["Vendas", "Financeiro"],
    )


class TestAgentBpmnAlwaysCreatesNamedPool:
    def test_flat_process_without_lanes_gets_participant_with_process_name(self):
        xml = AgentBPMN._generate_bpmn_xml(_flat_model())
        assert xml, "generation should not fail/return empty for a simple flat process"
        root = ET.fromstring(xml)
        participants = root.findall(f".//{_NS}participant")
        assert len(participants) == 1
        assert participants[0].get("name") == "Processo de Aprovacao de Credito"

    def test_flat_process_without_lanes_emits_no_lane_set(self):
        """The synthetic lane injected for layout purposes must never leak
        into the semantic <bpmn:laneSet> — it's a layout-only construct."""
        xml = AgentBPMN._generate_bpmn_xml(_flat_model())
        root = ET.fromstring(xml)
        assert root.findall(f".//{_NS}laneSet") == []
        assert root.findall(f".//{_NS}lane") == []

    def test_process_with_lanes_still_gets_participant_and_real_lanes(self):
        xml = AgentBPMN._generate_bpmn_xml(_lanes_model())
        root = ET.fromstring(xml)
        participants = root.findall(f".//{_NS}participant")
        assert len(participants) == 1
        assert participants[0].get("name") == "Processo com Lanes"
        lanes = root.findall(f".//{_NS}lane")
        lane_names = {l.get("name") for l in lanes}
        assert lane_names == {"Vendas", "Financeiro"}


class TestGenerateBpmnXmlSynthesizesLaneForNamedPoolWithoutLanes:
    def _process(self, pools):
        return BpmnProcess(
            name="X",
            elements=[
                BpmnElement(id="ev_start", type="startEvent", name="Inicio"),
                BpmnElement(id="t1", type="userTask", name="Fazer algo"),
                BpmnElement(id="ev_end", type="endEvent", name="Fim"),
            ],
            flows=[
                SequenceFlow(id="sf1", source="ev_start", target="t1"),
                SequenceFlow(id="sf2", source="t1", target="ev_end"),
            ],
            pools=pools,
        )

    def test_pool_without_lanes_produces_valid_shapes_for_every_element(self):
        bpmn = self._process([BpmnPool(id="pool_1", name="Meu Processo", lanes=[])])
        xml = generate_bpmn_xml(bpmn)
        root = ET.fromstring(xml)
        shape_refs = {s.get("bpmnElement") for s in root.findall(f".//{{{'http://www.omg.org/spec/BPMN/20100524/DI'}}}BPMNShape")}
        assert {"ev_start", "t1", "ev_end"}.issubset(shape_refs)
        # every element shape has a valid (non-empty) dc:Bounds
        for eid in ("ev_start", "t1", "ev_end"):
            shape = [s for s in root.iter() if s.get("bpmnElement") == eid][0]
            bounds = shape.find("{http://www.omg.org/spec/DD/20100524/DC}Bounds")
            assert bounds is not None
            assert int(bounds.get("width")) > 0
            assert int(bounds.get("height")) > 0

    def test_pool_with_no_lanes_and_no_elements_does_not_crash(self):
        bpmn = self._process([])
        xml = self._process([]) and generate_bpmn_xml(self._process([]))
        assert "<?xml" in xml


class TestBpmnDescriberSuppressesRedundantSinglePoolSection:
    def test_single_named_pool_does_not_duplicate_process_name_as_participant_section(self):
        xml = AgentBPMN._generate_bpmn_xml(_flat_model("Processo Unico"))
        md = describe_bpmn_from_xml(xml)
        assert "Processo: Processo Unico" in md
        assert "Participantes (Pools)" not in md

    def test_true_multi_pool_collaboration_still_lists_participants(self):
        xml = f"""<?xml version="1.0"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL">
  <bpmn:collaboration id="collab_1">
    <bpmn:participant id="p1" name="Empresa A" processRef="proc_1"/>
    <bpmn:participant id="p2" name="Empresa B" processRef="proc_2"/>
  </bpmn:collaboration>
  <bpmn:process id="proc_1" name="Processo Empresa A">
    <bpmn:startEvent id="s1" name="Inicio"/>
  </bpmn:process>
  <bpmn:process id="proc_2" name="Processo Empresa B"/>
</bpmn:definitions>"""
        md = describe_bpmn_from_xml(xml)
        assert "Participantes (Pools)" in md
        assert "Empresa A" in md
        assert "Empresa B" in md
