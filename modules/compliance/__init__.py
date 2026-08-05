# modules/compliance/__init__.py
# LGPD Compliance Layer — PC81

from modules.compliance.detector import (
    detect_pii, PIIDetectionResult, PII_CATEGORY_LABELS, PII_RISK_BADGE,
)
from modules.compliance.audit    import log_audit_event
from modules.compliance.consent  import render_consent_panel

__all__ = [
    "detect_pii",
    "PIIDetectionResult",
    "PII_CATEGORY_LABELS",
    "PII_RISK_BADGE",
    "log_audit_event",
    "render_consent_panel",
]
