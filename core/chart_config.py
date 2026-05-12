# core/chart_config.py
# Chart colour palettes shared between pages/Assistente.py and core/assistant_tools.py.
# Kept in a separate file with no imports so it can be safely imported anywhere.

CHART_PALETTES: dict = {
    "P2D Dark":    ["#3b82f6", "#C97B1A", "#10b981", "#8b5cf6", "#ef4444", "#06b6d4", "#f59e0b", "#ec4899"],
    "Azul Oceano": ["#0369a1", "#0ea5e9", "#38bdf8", "#7dd3fc", "#1e40af", "#3b82f6", "#60a5fa", "#93c5fd"],
    "Floresta":    ["#166534", "#16a34a", "#4ade80", "#86efac", "#14532d", "#15803d", "#22c55e", "#bbf7d0"],
    "Laranja":     ["#9a3412", "#ea580c", "#fb923c", "#fdba74", "#7c2d12", "#c2410c", "#f97316", "#fed7aa"],
    "Roxo":        ["#4c1d95", "#7c3aed", "#a78bfa", "#ddd6fe", "#581c87", "#7e22ce", "#c084fc", "#f3e8ff"],
    "Cinza":       ["#1e293b", "#475569", "#94a3b8", "#cbd5e1", "#0f172a", "#334155", "#64748b", "#e2e8f0"],
}

DEFAULT_PALETTE = "P2D Dark"
