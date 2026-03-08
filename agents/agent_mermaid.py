# agents/agent_mermaid.py
# ─────────────────────────────────────────────────────────────────────────────
# Mermaid Diagram Generator for BPMN processes
# Handles sanitization and generation of Mermaid flowchart syntax
# ─────────────────────────────────────────────────────────────────────────────

import re
from typing import Optional, List, Dict, Any
from core.knowledge_hub import BPMNModel, BPMNStep, BPMNEdge


class MermaidGenerator:
    """Gera diagramas Mermaid a partir de modelos BPMN."""

    # Mapeamento de caracteres acentuados para seus equivalentes ASCII
    ACENTOS_MAP = {
        'á': 'a', 'à': 'a', 'ã': 'a', 'â': 'a', 'ä': 'a',
        'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'í': 'i', 'ì': 'i', 'î': 'i', 'ï': 'i',
        'ó': 'o', 'ò': 'o', 'õ': 'o', 'ô': 'o', 'ö': 'o',
        'ú': 'u', 'ù': 'u', 'û': 'u', 'ü': 'u',
        'ç': 'c', 'ñ': 'n',
        'Á': 'A', 'À': 'A', 'Ã': 'A', 'Â': 'A', 'Ä': 'A',
        'É': 'E', 'È': 'E', 'Ê': 'E', 'Ë': 'E',
        'Í': 'I', 'Ì': 'I', 'Î': 'I', 'Ï': 'I',
        'Ó': 'O', 'Ò': 'O', 'Õ': 'O', 'Ô': 'O', 'Ö': 'O',
        'Ú': 'U', 'Ù': 'U', 'Û': 'U', 'Ü': 'U',
        'Ç': 'C', 'Ñ': 'N'
    }

    # Caracteres proibidos no Mermaid (serão substituídos por espaço)
    PROIBIDOS_PATTERN = r'[()\[\]{}/\\:;|<>]'

    @classmethod
    def sanitize_text(cls, text: Optional[str]) -> str:
        """
        Remove/replace characters that break Mermaid syntax.

        Args:
            text: Texto a ser sanitizado

        Returns:
            Texto sanitizado ou "Step" se vazio
        """
        if not text:
            return "Step"

        # 1. Substitui caracteres acentuados
        for acento, sem_acento in cls.ACENTOS_MAP.items():
            text = text.replace(acento, sem_acento)

        # 2. Substitui aspas duplas por simples
        text = text.replace('"', "'")

        # 3. Remove caracteres proibidos (substitui por espaço)
        text = re.sub(cls.PROIBIDOS_PATTERN, " ", text)

        # 4. Remove espaços múltiplos
        text = re.sub(r' {2,}', " ", text)

        # 5. Remove espaços no início e fim
        text = text.strip()

        return text or "Step"

    @classmethod
    def needs_quotes(cls, text: str) -> bool:
        """
        Verifica se um texto precisa de aspas no Mermaid.

        Args:
            text: Texto a ser verificado

        Returns:
            True se precisa de aspas, False caso contrário
        """
        if not text:
            return False

        # Precisa de aspas se contém espaços
        if ' ' in text:
            return True

        # Precisa de aspas se começa com número
        if text and text[0].isdigit():
            return True

        # Precisa de aspas se contém pontuação
        if any(c in text for c in '.,;:!@#$%&*()[]{}'):
            return True

        return False

    @classmethod
    def format_node(cls, step: BPMNStep) -> str:
        """
        Formata um nó do diagrama Mermaid.

        Args:
            step: BPMNStep a ser formatado

        Returns:
            Linha Mermaid para o nó
        """
        node_id = step.id
        label = cls.sanitize_text(step.title)

        if step.is_decision:
            # Nó de decisão: usa chaves
            return f'    {node_id}{{{label}}}'
        else:
            # Nó de tarefa: usa colchetes
            return f'    {node_id}[{label}]'

    @classmethod
    def format_edge(cls, edge: BPMNEdge) -> str:
        """
        Formata uma aresta do diagrama Mermaid.

        Args:
            edge: BPMNEdge a ser formatada

        Returns:
            Linha Mermaid para a aresta
        """
        source = edge.source
        target = edge.target

        if edge.label:
            safe_label = cls.sanitize_text(edge.label)
            if safe_label:
                if cls.needs_quotes(safe_label):
                    arrow = f'-- "{safe_label}" -->'
                else:
                    arrow = f'-- {safe_label} -->'
            else:
                arrow = "-->"
        else:
            arrow = "-->"

        return f'    {source} {arrow} {target}'

    @classmethod
    def generate(cls, model: BPMNModel) -> str:
        """
        Gera um diagrama Mermaid completo a partir de um modelo BPMN.

        Args:
            model: BPMNModel com steps e edges

        Returns:
            String com a sintaxe Mermaid do diagrama
        """
        lines = ["flowchart TD"]

        # Adiciona nós (steps)
        for step in model.steps:
            lines.append(cls.format_node(step))

        # Adiciona arestas (edges)
        for edge in model.edges:
            lines.append(cls.format_edge(edge))

        # Adiciona estilo para nós de decisão
        decision_ids = [s.id for s in model.steps if s.is_decision]
        for did in decision_ids:
            lines.append(f'    style {did} fill:#fff3cd,stroke:#f59e0b')

        return "\n".join(lines)


# Função de conveniência para uso direto
def generate_mermaid(model: BPMNModel) -> str:
    """Gera diagrama Mermaid a partir de um modelo BPMN."""
    return MermaidGenerator.generate(model)
