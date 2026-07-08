# tests/test_agent_bpmn_multipool_documentation.py
"""
Regression guard for a real gap found 2026-07-05 (PC132): in collaboration
(multi-pool) BPMN XML, exclusiveGateway steps never got their `description`
written to the <documentation> tag — a separate code path in
AgentBPMN._build_pool_elements() (the `is_decision` branch) omitted the
`documentation=step.description` kwarg that both the event branch and the
task branch already passed. Single-pool XML generation was never affected
(gateways there share the same code path as tasks). Confirmed via a direct
scan of every BpmnElement(...) construction site in agents/agent_bpmn.py.
"""

import xml.etree.ElementTree as ET

from agents.agent_bpmn import AgentBPMN
from core.knowledge_hub import BPMNModel, BPMNPoolData, BPMNStep, BPMNEdge, BPMNMessageFlow

_NS = "{http://www.omg.org/spec/BPMN/20100524/MODEL}"


def _make_collab_model_with_gateway_description():
    pool_a = BPMNPoolData(
        pool_id="pool_a",
        name="Contratante",
        steps=[
            BPMNStep(id="S01", title="Analisar Proposta", task_type="userTask", lane="Compras"),
            BPMNStep(id="S02", title="Proposta Aprovada?", task_type="exclusiveGateway",
                     is_decision=True, lane="Compras",
                     description="Verifica se a proposta atende aos critérios técnicos e comerciais."),
            BPMNStep(id="S03", title="Assinar Contrato", task_type="userTask", lane="Compras"),
        ],
        edges=[
            BPMNEdge(source="S01", target="S02"),
            BPMNEdge(source="S02", target="S03", label="Aprovada"),
        ],
        lanes=["Compras"],
    )
    pool_b = BPMNPoolData(
        pool_id="pool_b",
        name="Fornecedor",
        steps=[
            BPMNStep(id="T01", title="Enviar Proposta", task_type="userTask", lane="Comercial"),
        ],
        edges=[],
        lanes=["Comercial"],
    )
    return BPMNModel(
        name="Contratação",
        is_collaboration=True,
        pool_models=[pool_a, pool_b],
        message_flows_data=[
            BPMNMessageFlow(id="mf_1", source_pool="pool_b", source_step="T01",
                             target_pool="pool_a", target_step="S01", name="Proposta"),
        ],
    )


class TestMultiPoolGatewayDocumentation:
    def test_gateway_description_reaches_documentation_tag(self):
        model = _make_collab_model_with_gateway_description()
        xml_str = AgentBPMN._generate_bpmn_xml(model)
        assert xml_str, "XML generation failed"

        root = ET.fromstring(xml_str)
        # PC154: labels are now hard-wrapped with literal '\n' at generation
        # time (bpmn_generator.py::_wrap_label) so bpmn-js renders correctly
        # even when its own canvas-based auto-wrap is broken by fingerprinting
        # blockers — normalize whitespace before comparing.
        gateway = next(
            g for g in root.iter(f"{_NS}exclusiveGateway")
            if (g.get("name") or "").replace("\n", " ") == "Proposta Aprovada?"
        )
        doc = gateway.find(f"{_NS}documentation")
        assert doc is not None, "gateway is missing <documentation> entirely"
        assert doc.text == "Verifica se a proposta atende aos critérios técnicos e comerciais."

    def test_single_pool_gateway_documentation_unaffected(self):
        """Regression guard: single-pool path already worked — must keep working."""
        from core.knowledge_hub import BPMNModel as _BM
        model = _BM(
            name="Processo",
            steps=[
                BPMNStep(id="S01", title="Analisar", task_type="userTask", lane="Time"),
                BPMNStep(id="S02", title="Aprovado?", task_type="exclusiveGateway",
                         is_decision=True, lane="Time",
                         description="Critério de aprovação interno."),
                BPMNStep(id="S03", title="Prosseguir", task_type="userTask", lane="Time"),
            ],
            edges=[
                BPMNEdge(source="S01", target="S02"),
                BPMNEdge(source="S02", target="S03", label="Sim"),
            ],
            lanes=["Time"],
        )
        xml_str = AgentBPMN._generate_bpmn_xml(model)
        root = ET.fromstring(xml_str)
        gateway = next(
            g for g in root.iter(f"{_NS}exclusiveGateway")
            if g.get("name") == "Aprovado?"
        )
        doc = gateway.find(f"{_NS}documentation")
        assert doc is not None
        assert doc.text == "Critério de aprovação interno."
