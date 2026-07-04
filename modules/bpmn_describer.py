# modules/bpmn_describer.py
# ─────────────────────────────────────────────────────────────────────────────
# BPMN XML → descrição textual estruturada — presentation layer, zero I/O.
#
# Extraído de core/tools/tools_bpmn_sbvr.py::AssistantToolExecutor.describe_bpmn_process()
# (PC116/BPMN Studio) para funcionar com qualquer XML — salvo no projeto ou colado
# livremente — não apenas processos já persistidos no banco. describe_bpmn_process()
# continua resolvendo process_name → XML e delega a este módulo para o parsing.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import xml.etree.ElementTree as ET

_BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"

_KNOWN_TYPES = {
    "task", "userTask", "serviceTask", "manualTask", "businessRuleTask",
    "scriptTask", "sendTask", "receiveTask", "callActivity",
    "startEvent", "endEvent", "intermediateCatchEvent", "intermediateThrowEvent",
    "boundaryEvent", "exclusiveGateway", "parallelGateway", "inclusiveGateway",
    "eventBasedGateway", "complexGateway",
}

_TYPE_LABELS = {
    "exclusiveGateway": "Decisão exclusiva (XOR)",
    "parallelGateway":  "Fork/join paralelo (AND)",
    "inclusiveGateway": "Gateway inclusivo (OR)",
    "eventBasedGateway": "Gateway baseado em evento",
    "startEvent": "Evento de início",
    "endEvent":   "Evento de fim",
    "userTask":    "Tarefa humana",
    "serviceTask": "Tarefa de sistema",
    "manualTask":  "Tarefa manual",
    "businessRuleTask": "Regra de negócio",
    "sendTask":    "Envio de mensagem",
    "receiveTask": "Recebimento de mensagem",
    "callActivity": "Subprocesso chamado",
    "intermediateCatchEvent": "Evento intermediário (captura)",
    "intermediateThrowEvent": "Evento intermediário (lançamento)",
    "boundaryEvent": "Evento de fronteira",
}


def describe_bpmn_from_xml(
    xml_str: str,
    process_name: str = "",
    version: str | int = "",
) -> str:
    """Gera descrição textual estruturada de um processo a partir de XML BPMN 2.0 puro.

    Não faz nenhum acesso a banco — funciona com qualquer XML válido, salvo no
    projeto ou colado livremente (BPMN Studio, modo "Descrever").

    Args:
        xml_str: XML BPMN 2.0 completo.
        process_name: nome de exibição opcional para o cabeçalho. Quando vazio,
            tenta extrair de ``<bpmn:process name="...">``; se ausente, usa
            "Processo BPMN".
        version: rótulo de versão opcional para o cabeçalho (ex.: número da versão
            salva). Omitido do cabeçalho quando vazio.

    Retorna Markdown com participantes, fluxo numerado passo-a-passo e resultados
    possíveis. Erros de parsing retornam uma mensagem de erro clara (nunca lança
    exceção).
    """
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError as exc:
        return f"Erro de parsing no XML: {exc}"

    if not process_name:
        proc_elem = root.find(f".//{{{_BPMN_NS}}}process")
        process_name = (proc_elem.get("name") if proc_elem is not None else "") or "Processo BPMN"

    # Coletar elementos com nomes e tipos
    elem_map: dict[str, dict] = {}
    lane_elements: dict[str, list[str]] = {}  # lane_name → [elem_ids]
    pool_names: list[str] = []
    flows: list[tuple] = []  # (src_id, tgt_id, label)

    for elem in root.iter():
        tag = elem.tag
        eid = elem.get("id", "")
        name = (elem.get("name") or "").strip()
        local = tag.replace(f"{{{_BPMN_NS}}}", "")

        if local in _KNOWN_TYPES and eid:
            elem_map[eid] = {"name": name, "type": local}
        elif local == "sequenceFlow" and eid:
            flows.append((elem.get("sourceRef", ""), elem.get("targetRef", ""), name))
        elif local == "lane" and eid:
            lane_name = name
            refs = [c.text.strip() for c in elem if c.tag == f"{{{_BPMN_NS}}}flowNodeRef" and c.text]
            lane_elements[lane_name] = refs
        elif local == "participant" and name:
            pool_names.append(name)

    # Mapear saídas por elemento
    outgoing_map: dict[str, list] = {}
    for src, tgt, lbl in flows:
        outgoing_map.setdefault(src, []).append((tgt, lbl))

    # Determinar ordem topológica simples (BFS a partir de startEvents)
    start_ids = [eid for eid, e in elem_map.items() if "start" in e["type"].lower()]
    visited: list[str] = []
    queue = list(start_ids)
    seen: set[str] = set(start_ids)
    while queue:
        cur = queue.pop(0)
        visited.append(cur)
        for tgt, _ in outgoing_map.get(cur, []):
            if tgt not in seen and tgt in elem_map:
                seen.add(tgt)
                queue.append(tgt)
    # Append any remaining (cycles / unreachable)
    for eid in elem_map:
        if eid not in seen:
            visited.append(eid)

    # Mapear cada elemento à sua lane
    elem_to_lane: dict[str, str] = {}
    for lane_name, refs in lane_elements.items():
        for ref in refs:
            elem_to_lane[ref] = lane_name

    # Construir descrição
    header = f"## Processo: {process_name}"
    if version:
        header += f" (v{version})"
    lines = [header, ""]

    if pool_names:
        lines += ["### Participantes (Pools)", ""]
        for p in pool_names:
            lines.append(f"- **{p}**")
        lines.append("")

    if lane_elements:
        lines += ["### Participantes (Lanes)", ""]
        for lane_name in lane_elements:
            lines.append(f"- **{lane_name}**")
        lines.append("")

    lines += ["### Fluxo do Processo", ""]
    step_num = 0
    for eid in visited:
        e = elem_map.get(eid)
        if not e:
            continue
        step_num += 1
        ename = e["name"] or f"[sem nome — {eid}]"
        etype = e["type"]
        type_label = _TYPE_LABELS.get(etype, etype)
        lane = elem_to_lane.get(eid, "")
        lane_str = f" ({lane})" if lane else ""

        outs = outgoing_map.get(eid, [])
        if "gateway" in etype.lower():
            if outs:
                out_desc = "; ".join(
                    f'"{lbl}" → {elem_map.get(tgt, {}).get("name", tgt)}'
                    for tgt, lbl in outs if lbl
                ) or "; ".join(
                    elem_map.get(tgt, {}).get("name", tgt) for tgt, _ in outs
                )
                lines.append(f"{step_num}. **{ename}**{lane_str} — {type_label}: {out_desc}.")
            else:
                lines.append(f"{step_num}. **{ename}**{lane_str} — {type_label}.")
        elif "end" in etype.lower():
            lines.append(f"{step_num}. **{ename}**{lane_str} — {type_label}. *(resultado final)*")
        else:
            lines.append(f"{step_num}. **{ename}**{lane_str} — {type_label}.")

    end_names = [elem_map[e]["name"] for e in visited
                 if elem_map.get(e, {}).get("type", "").startswith("end") and elem_map[e]["name"]]
    if end_names:
        lines += ["", "### Resultados Possíveis", ""]
        for n in end_names:
            lines.append(f"- {n}")

    return "\n".join(lines)
