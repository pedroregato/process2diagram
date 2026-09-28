"""Testes de evals/bpmn_metrics/metrics.py — métricas estruturais BPMN (V3)."""

from __future__ import annotations

import math

import pytest

from evals.bpmn_metrics.metrics import (
    metrics_from_xml, repair_duplicate_attributes, size_band,
)

NS = 'xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"'


def _doc(body: str, root_attrs: str = NS) -> str:
    return f'<definitions {root_attrs}><process id="P1" name="Teste">{body}</process></definitions>'


def _flows(*pairs: tuple[str, str]) -> str:
    return "".join(
        f'<sequenceFlow id="f{i}" sourceRef="{s}" targetRef="{t}"/>' for i, (s, t) in enumerate(pairs)
    )


XOR_DIAMOND = _doc(
    '<startEvent id="s"/><task id="a"/><exclusiveGateway id="g1"/>'
    '<task id="b"/><task id="c"/><exclusiveGateway id="g2"/><endEvent id="e"/>'
    + _flows(("s", "a"), ("a", "g1"), ("g1", "b"), ("g1", "c"), ("b", "g2"), ("c", "g2"), ("g2", "e"))
)


def test_xor_diamond_counts_and_cfc():
    (m,) = metrics_from_xml(XOR_DIAMOND)
    assert (m.TNA, m.TNE, m.TNG, m.TNN, m.TNSF) == (3, 2, 2, 7, 7)
    assert m.TNGXOR == 2 and m.TNGAND == 0
    assert m.CFC == 2                 # XOR split com fan-out 2
    assert m.AGD == 3.0 and m.MGD == 3
    assert m.GM == 0                  # split e join equilibrados
    assert m.GH == 0.0                # um só tipo de gateway
    assert not (m.no_start or m.no_end or m.no_gateway)
    assert m.implicit_joins == 0


def test_or_split_uses_power_set_and_and_split_counts_one():
    or3 = _doc(
        '<startEvent id="s"/><inclusiveGateway id="g"/><task id="a"/><task id="b"/><task id="c"/>'
        + _flows(("s", "g"), ("g", "a"), ("g", "b"), ("g", "c"))
    )
    and3 = or3.replace("inclusiveGateway", "parallelGateway")
    assert metrics_from_xml(or3)[0].CFC == 7      # 2^3 − 1
    assert metrics_from_xml(and3)[0].CFC == 1


def test_gateway_heterogeneity_is_entropy_base3():
    body = (
        '<parallelGateway id="g1"/><exclusiveGateway id="g2"/><inclusiveGateway id="g3"/>'
    )
    (m,) = metrics_from_xml(_doc(body))
    assert m.GH == pytest.approx(1.0)
    (m2,) = metrics_from_xml(_doc('<parallelGateway id="g1"/><exclusiveGateway id="g2"/>'))
    assert m2.GH == pytest.approx(round(-2 * 0.5 * math.log(0.5, 3), 4))


def test_mismatch_when_split_has_no_join():
    body = (
        '<startEvent id="s"/><exclusiveGateway id="g"/><task id="a"/><task id="b"/><endEvent id="e"/>'
        + _flows(("s", "g"), ("g", "a"), ("g", "b"), ("a", "e"), ("b", "e"))
    )
    (m,) = metrics_from_xml(_doc(body))
    assert m.GM == 2          # fan-out 2, nenhum join XOR
    assert m.implicit_joins == 1   # o endEvent recebe 2 fluxos sem gateway


def test_link_pair_is_resolved_into_direct_flow():
    body = (
        '<startEvent id="s"/><task id="a"/>'
        '<intermediateThrowEvent id="link_throw_a_b"><linkEventDefinition id="l1" name=""/></intermediateThrowEvent>'
        '<intermediateCatchEvent id="link_catch_a_b"><linkEventDefinition id="l2" name=""/></intermediateCatchEvent>'
        '<task id="b"/><endEvent id="e"/>'
        + _flows(("s", "a"), ("a", "link_throw_a_b"), ("link_catch_a_b", "b"), ("b", "e"))
    )
    (m,) = metrics_from_xml(_doc(body))
    assert m.extra["link_pairs"] == 1
    assert m.TNIE == 0 and m.TNN == 4 and m.TNSF == 3
    assert m.goto_events == 0
    (raw,) = metrics_from_xml(_doc(body), resolve_links=False)
    assert raw.TNIE == 2 and raw.goto_events == 2


def test_collaboration_yields_one_row_per_process():
    xml = (
        f'<definitions {NS}><collaboration id="c"/>'
        '<process id="P1"><startEvent id="s1"/></process>'
        '<process id="P2"><startEvent id="s2"/><endEvent id="e2"/></process></definitions>'
    )
    rows = metrics_from_xml(xml)
    assert [r.process_id for r in rows] == ["P1", "P2"]


def test_duplicate_root_namespace_is_repaired():
    bad = _doc('<startEvent id="s"/>', root_attrs=f'{NS} {NS} xmlns:xsi="x" xmlns:xsi="x"')
    fixed = repair_duplicate_attributes(bad.encode())
    assert fixed.count(b'xmlns="') == 1 and fixed.count(b"xmlns:xsi=") == 1
    (m,) = metrics_from_xml(bad)
    assert m.extra["repaired_xml"] is True and m.TNSE == 1


@pytest.mark.parametrize("tnn,band", [(0, "<10"), (9, "<10"), (10, "10–19"), (29, "20–29"), (30, "≥30")])
def test_size_band(tnn, band):
    assert size_band(tnn) == band
