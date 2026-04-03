# ui/tabs/__init__.py
from .quality_tab import render as render_quality
from .bpmn_tabs import render_bpmn, render_mermaid, render_validation
from .minutes_tab import render as render_minutes
from .requirements_tab import render as render_requirements
from .synthesizer_tab import render as render_synthesizer
from .export_tab import render as render_export
from .dev_tools_tab import render as render_dev_tools
