# Guia de Implementação — `render_table` + Exportação Excel
**Process2Diagram v4.15 → v4.16**  
**Feature:** Ferramenta `render_table` no AgentAssistant com exportação nativa para `.xlsx` com gráficos

---

## Visão Geral

O objetivo é permitir que o LLM, ao responder perguntas que produzem dados tabulares (custos, action items, requisitos, embeddings, etc.), chame a ferramenta `render_table` em vez de escrever uma tabela Markdown livre. Isso captura os dados estruturados e disponibiliza automaticamente um botão **"⬇️ Exportar para Excel"** logo abaixo da resposta, gerando um `.xlsx` com tabela formatada e gráficos nativos do Excel.

### Fluxo resumido

```
Usuário: "Crie tabela de custo de embeddings por reunião do projeto SDEA e um gráfico de barras"
        │
        ▼
AgentAssistant.chat_with_tools() — Modo A (tool-use)
        │
        ├── LLM chama get_meeting_list(), ferramentas de dados…
        │
        └── LLM chama render_table(title, columns, rows, chart_type, chart_x_col, chart_y_cols)
                │
                ▼
        AssistantToolExecutor.execute("render_table", args)
          ├── persiste args em st.session_state["_pending_table"]
          └── retorna "✅ Tabela registrada para exibição."
                │
                ▼
        Assistente.py detecta _pending_table
          ├── renderiza tabela HTML elegante no chat
          └── renderiza st.download_button "⬇️ Exportar para Excel"
                │
                ▼ (usuário clica)
        modules/excel_exporter.py → BytesIO com .xlsx
          ├── Aba "Dados" — tabela formatada, auto-filtro, zebra stripes
          ├── Aba "Gráfico" — BarChart/PieChart/LineChart nativo Excel
          └── Aba "Metadados" — projeto, data, pergunta original
```

---

## Arquivos a criar/modificar

| Arquivo | Ação | Descrição |
|---|---|---|
| `modules/excel_exporter.py` | **CRIAR** | Geração do `.xlsx` em memória (BytesIO) |
| `core/assistant_tools.py` | **MODIFICAR** | Adicionar schema `render_table` (OpenAI + Anthropic) + handler no Executor |
| `pages/Assistente.py` | **MODIFICAR** | Detectar `_pending_table`, renderizar tabela + botão Excel |
| `skills/skill_assistant.md` | **MODIFICAR** | Instruir o LLM a usar `render_table` para dados tabulares |
| `requirements.txt` | **MODIFICAR** | Adicionar `openpyxl>=3.1.5` |
| `CLAUDE.md` | **MODIFICAR** | Documentar a nova ferramenta e o novo módulo |

---

## Passo 1 — `requirements.txt`

Adicionar ao final:

```
openpyxl>=3.1.5
```

> **Verificação:** `openpyxl` pode já ser dependência transitiva de `python-docx`. Confirmar com
> `pip show openpyxl` no ambiente. Se já estiver presente, apenas adicionar a linha para
> declaração explícita da versão mínima.

---

## Passo 2 — Criar `modules/excel_exporter.py`

Criar o arquivo do zero. Ele é totalmente independente do restante do código — nenhuma importação de módulos do projeto.

```python
# modules/excel_exporter.py
# ─────────────────────────────────────────────────────────────────────────────
# Excel export for AssistantAgent render_table results.
#
# Public API:
#   export_table_to_excel(table_data: dict, question: str, project_name: str) -> bytes
#
# table_data keys (match render_table tool schema):
#   title       str           — sheet/chart title
#   columns     list[str]     — column headers
#   rows        list[list]    — data rows (each row = list of values)
#   chart_type  str|None      — "bar" | "pie" | "line" | None
#   chart_x_col str|None      — column name for X axis (bar/line) or labels (pie)
#   chart_y_cols list[str]|None — column names for Y axis series
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import io
from datetime import datetime
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import (
    PatternFill, Font, Alignment, Border, Side, numbers
)
from openpyxl.chart import BarChart, PieChart, LineChart, Reference
from openpyxl.chart.series import DataPoint
from openpyxl.utils import get_column_letter


# ── Brand colours (aligned with Process2Diagram IBM Plex theme) ───────────────
_NAVY       = "0F172A"   # header background
_ACCENT     = "1D4ED8"   # chart accent blue
_ZEBRA      = "F1F5F9"   # alternate row fill
_WHITE      = "FFFFFF"
_BORDER_CLR = "CBD5E1"

_HEADER_FONT  = Font(name="Calibri", bold=True, color=_WHITE, size=11)
_BODY_FONT    = Font(name="Calibri", size=10)
_TITLE_FONT   = Font(name="Calibri", bold=True, size=13, color=_NAVY)
_META_FONT    = Font(name="Calibri", size=9, color="64748B", italic=True)

_HEADER_FILL  = PatternFill("solid", fgColor=_NAVY)
_ZEBRA_FILL   = PatternFill("solid", fgColor=_ZEBRA)

_THIN_BORDER  = Border(
    left=Side(style="thin", color=_BORDER_CLR),
    right=Side(style="thin", color=_BORDER_CLR),
    top=Side(style="thin", color=_BORDER_CLR),
    bottom=Side(style="thin", color=_BORDER_CLR),
)

_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
_LEFT   = Alignment(horizontal="left",   vertical="center", wrap_text=True)


# ── Public entry point ────────────────────────────────────────────────────────

def export_table_to_excel(
    table_data: dict[str, Any],
    question: str = "",
    project_name: str = "",
) -> bytes:
    """
    Build a .xlsx file in memory and return raw bytes suitable for
    st.download_button(data=...).

    Parameters
    ----------
    table_data : dict
        Payload from the render_table tool call (title, columns, rows,
        chart_type, chart_x_col, chart_y_cols).
    question : str
        Original user question — stored in the Metadata sheet.
    project_name : str
        Active project name — stored in the Metadata sheet.
    """
    wb = Workbook()

    # ── Sheet 1: data ─────────────────────────────────────────────────────────
    ws_data = wb.active
    ws_data.title = _safe_sheet_name(table_data.get("title", "Dados"))

    _write_data_sheet(
        ws=ws_data,
        title=table_data.get("title", ""),
        columns=table_data.get("columns", []),
        rows=table_data.get("rows", []),
    )

    # ── Sheet 2: chart (optional) ─────────────────────────────────────────────
    chart_type  = (table_data.get("chart_type") or "").lower()
    chart_x_col = table_data.get("chart_x_col")
    chart_y_cols = table_data.get("chart_y_cols") or []

    if chart_type in ("bar", "pie", "line") and chart_x_col and chart_y_cols:
        ws_chart = wb.create_sheet(title="Gráfico")
        _write_chart_sheet(
            wb=wb,
            ws_chart=ws_chart,
            ws_data=ws_data,
            table_data=table_data,
            chart_type=chart_type,
            chart_x_col=chart_x_col,
            chart_y_cols=chart_y_cols,
        )

    # ── Sheet 3: metadata ─────────────────────────────────────────────────────
    ws_meta = wb.create_sheet(title="Metadados")
    _write_metadata_sheet(ws_meta, table_data, question, project_name)

    # ── Serialise to bytes ────────────────────────────────────────────────────
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── Data sheet ────────────────────────────────────────────────────────────────

def _write_data_sheet(
    ws,
    title: str,
    columns: list[str],
    rows: list[list],
) -> None:
    if not columns:
        return

    # Title row
    ws.merge_cells(start_row=1, start_column=1,
                   end_row=1, end_column=len(columns))
    title_cell = ws.cell(row=1, column=1, value=title or "Dados")
    title_cell.font      = _TITLE_FONT
    title_cell.alignment = _CENTER
    title_cell.fill      = PatternFill("solid", fgColor="E2E8F0")
    ws.row_dimensions[1].height = 28

    # Header row (row 2)
    for col_idx, col_name in enumerate(columns, start=1):
        cell = ws.cell(row=2, column=col_idx, value=col_name)
        cell.font      = _HEADER_FONT
        cell.fill      = _HEADER_FILL
        cell.alignment = _CENTER
        cell.border    = _THIN_BORDER
    ws.row_dimensions[2].height = 22

    # Data rows (starting row 3)
    for row_idx, row in enumerate(rows, start=3):
        fill = _ZEBRA_FILL if row_idx % 2 == 0 else None
        for col_idx, value in enumerate(row, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.font      = _BODY_FONT
            cell.alignment = _LEFT
            cell.border    = _THIN_BORDER
            if fill:
                cell.fill = fill

    # Auto-fit column widths
    for col_idx, col_name in enumerate(columns, start=1):
        col_values = [str(col_name)] + [str(r[col_idx - 1]) for r in rows if col_idx - 1 < len(r)]
        max_len = min(max((len(v) for v in col_values), default=10), 60)
        ws.column_dimensions[get_column_letter(col_idx)].width = max_len + 2

    # Auto-filter on header row
    if rows:
        ws.auto_filter.ref = (
            f"A2:{get_column_letter(len(columns))}{len(rows) + 2}"
        )

    # Freeze header rows
    ws.freeze_panes = "A3"


# ── Chart sheet ───────────────────────────────────────────────────────────────

def _write_chart_sheet(
    wb, ws_chart, ws_data,
    table_data: dict,
    chart_type: str,
    chart_x_col: str,
    chart_y_cols: list[str],
) -> None:
    columns   = table_data.get("columns", [])
    rows      = table_data.get("rows", [])
    title_str = table_data.get("title", "")
    n_rows    = len(rows)

    if not columns or not rows:
        return

    # Map column names → 1-based indices in ws_data
    # Data starts at row 3 in ws_data (row 1 = title, row 2 = headers)
    try:
        x_col_idx = columns.index(chart_x_col) + 1
    except ValueError:
        x_col_idx = 1

    y_col_indices = []
    for yc in chart_y_cols:
        try:
            y_col_indices.append(columns.index(yc) + 1)
        except ValueError:
            pass

    if not y_col_indices:
        return

    data_start_row = 3
    data_end_row   = data_start_row + n_rows - 1

    if chart_type == "bar":
        chart = BarChart()
        chart.type    = "col"
        chart.grouping = "clustered"
        chart.overlap = 0
    elif chart_type == "line":
        chart = LineChart()
    elif chart_type == "pie":
        chart = PieChart()
    else:
        return

    chart.title  = title_str
    chart.style  = 10
    chart.width  = 22
    chart.height = 14

    # X axis / category labels
    cats = Reference(
        ws_data,
        min_col=x_col_idx,
        min_row=data_start_row,
        max_row=data_end_row,
    )

    # Y series
    for y_idx in y_col_indices:
        data_ref = Reference(
            ws_data,
            min_col=y_idx,
            min_row=data_start_row - 1,   # include header as series title
            max_row=data_end_row,
        )
        chart.add_data(data_ref, titles_from_data=True)

    if chart_type != "pie":
        chart.set_categories(cats)
        chart.shape = 4
    else:
        # Pie: categories are the labels
        chart.series[0].explosion = 10   # slight slice separation
        chart.dataLabels = None

    ws_chart.add_chart(chart, "B2")

    # Label the sheet
    ws_chart["A1"].value     = f"Gráfico — {title_str}"
    ws_chart["A1"].font      = _TITLE_FONT
    ws_chart["A1"].alignment = _LEFT


# ── Metadata sheet ────────────────────────────────────────────────────────────

def _write_metadata_sheet(
    ws,
    table_data: dict,
    question: str,
    project_name: str,
) -> None:
    meta_rows = [
        ("Projeto",         project_name),
        ("Exportado em",    datetime.now().strftime("%Y-%m-%d %H:%M")),
        ("Título da tabela", table_data.get("title", "")),
        ("Pergunta original", question),
        ("Colunas",         ", ".join(table_data.get("columns", []))),
        ("Total de linhas", len(table_data.get("rows", []))),
        ("Tipo de gráfico", table_data.get("chart_type") or "nenhum"),
        ("Gerado por",      "Process2Diagram — AgentAssistant"),
    ]
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 60

    for r_idx, (label, value) in enumerate(meta_rows, start=1):
        lc = ws.cell(row=r_idx, column=1, value=label)
        vc = ws.cell(row=r_idx, column=2, value=str(value))
        lc.font      = Font(name="Calibri", bold=True, size=10, color=_NAVY)
        vc.font      = _BODY_FONT
        lc.alignment = _LEFT
        vc.alignment = _LEFT


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_sheet_name(name: str) -> str:
    """Truncate to 31 chars and strip characters illegal in Excel sheet names."""
    illegal = r'\/*?:[]'
    for ch in illegal:
        name = name.replace(ch, "")
    return name[:31] or "Dados"
```

---

## Passo 3 — Modificar `core/assistant_tools.py`

### 3.1 — Adicionar schema da ferramenta `render_table`

Dentro de `get_tool_schemas_openai()`, adicionar ao final da lista de tools:

```python
{
    "type": "function",
    "function": {
        "name": "render_table",
        "description": (
            "Use this tool INSTEAD of writing a Markdown table whenever the response "
            "contains structured tabular data. This captures the data for Excel export. "
            "Call this once per table. Do NOT call it for purely narrative responses."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Descriptive title for the table and chart (e.g. 'Custo de Embeddings por Reunião — SDEA')."
                },
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Column header names, in display order."
                },
                "rows": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {}
                    },
                    "description": "Data rows. Each row is an array of values matching the columns order. Values may be strings, numbers, or null."
                },
                "chart_type": {
                    "type": "string",
                    "enum": ["bar", "pie", "line", "none"],
                    "description": "Chart type to generate in Excel. Use 'none' if the data is not suitable for charting."
                },
                "chart_x_col": {
                    "type": "string",
                    "description": "Column name to use as X axis (bar/line) or slice labels (pie). Required when chart_type != 'none'."
                },
                "chart_y_cols": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Column names to use as Y axis series. One series = one column. Required when chart_type != 'none'."
                }
            },
            "required": ["title", "columns", "rows", "chart_type"]
        }
    }
},
```

### 3.2 — Adicionar schema no formato Anthropic

Dentro de `get_tool_schemas_anthropic()`, adicionar ao final da lista:

```python
{
    "name": "render_table",
    "description": (
        "Use this tool INSTEAD of writing a Markdown table whenever the response "
        "contains structured tabular data. This captures the data for Excel export. "
        "Call this once per table. Do NOT call it for purely narrative responses."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Descriptive title for the table and chart."
            },
            "columns": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Column header names, in display order."
            },
            "rows": {
                "type": "array",
                "items": {"type": "array", "items": {}},
                "description": "Data rows. Each row is an array of values matching the columns order."
            },
            "chart_type": {
                "type": "string",
                "enum": ["bar", "pie", "line", "none"],
                "description": "Chart type to generate in Excel."
            },
            "chart_x_col": {
                "type": "string",
                "description": "Column name for X axis or pie labels."
            },
            "chart_y_cols": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Column names for Y axis series."
            }
        },
        "required": ["title", "columns", "rows", "chart_type"]
    }
},
```

### 3.3 — Adicionar handler em `AssistantToolExecutor.execute()`

Localizar o bloco `if name == "get_meeting_list":` (ou equivalente) e adicionar **antes** do bloco `else` final de fallback:

```python
elif name == "render_table":
    # Persist table data for Assistente.py to render + offer Excel download.
    # Store in a list to support multiple tables per conversation turn.
    import streamlit as st
    pending = st.session_state.get("_pending_tables", [])
    pending.append({
        "title":       args.get("title", "Tabela"),
        "columns":     args.get("columns", []),
        "rows":        args.get("rows", []),
        "chart_type":  args.get("chart_type", "none"),
        "chart_x_col": args.get("chart_x_col"),
        "chart_y_cols": args.get("chart_y_cols", []),
    })
    st.session_state["_pending_tables"] = pending
    col_count = len(args.get("columns", []))
    row_count = len(args.get("rows", []))
    return f"✅ Tabela '{args.get('title', '')}' registrada ({row_count} linhas × {col_count} colunas)."
```

> **Nota:** `render_table` não é uma ferramenta admin-gated — qualquer usuário autenticado pode usá-la.
> Certificar-se de que `"render_table"` NÃO está no frozenset `_ADMIN_TOOLS`.

---

## Passo 4 — Modificar `pages/Assistente.py`

### 4.1 — Adicionar import no topo

```python
from modules.excel_exporter import export_table_to_excel
from datetime import datetime
```

### 4.2 — Função helper para renderizar tabela HTML

Adicionar antes da função `render_chat_messages()` (ou equivalente local):

```python
def _render_pending_tables(project_name: str, last_question: str) -> None:
    """
    Reads st.session_state["_pending_tables"], renders each table as
    an st.dataframe + Excel download button, then clears the list.
    
    Must be called AFTER the assistant response is written to session_state
    and OUTSIDE any st.spinner / conditional block.
    """
    pending: list[dict] = st.session_state.pop("_pending_tables", [])
    if not pending:
        return

    for table_data in pending:
        title = table_data.get("title", "Tabela")
        columns = table_data.get("columns", [])
        rows = table_data.get("rows", [])

        if not columns or not rows:
            continue

        # ── Render as st.dataframe ────────────────────────────────────────────
        import pandas as pd
        df = pd.DataFrame(rows, columns=columns)
        st.markdown(f"**{title}**")
        st.dataframe(df, use_container_width=True, hide_index=True)

        # ── Excel export button ───────────────────────────────────────────────
        # Key must be unique per table to avoid Streamlit DuplicateWidgetID.
        # Use title hash as suffix.
        key_suffix = abs(hash(title)) % 100000

        # Generate Excel bytes and persist BEFORE rendering the button
        # (download_button triggers rerun — data must survive it).
        cache_key = f"_excel_bytes_{key_suffix}"
        if cache_key not in st.session_state:
            st.session_state[cache_key] = export_table_to_excel(
                table_data=table_data,
                question=last_question,
                project_name=project_name,
            )

        chart_label = ""
        ct = table_data.get("chart_type", "none")
        if ct and ct != "none":
            chart_label = f" + gráfico {ct}"

        filename = (
            f"p2d_tabela_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        )

        st.download_button(
            label=f"⬇️ Exportar para Excel{chart_label}",
            data=st.session_state[cache_key],
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"btn_excel_{key_suffix}",
        )
```

### 4.3 — Chamar `_render_pending_tables` após cada resposta do assistente

Localizar o bloco onde a resposta do assistente é adicionada a `st.session_state["messages"]` e, imediatamente após, adicionar a chamada:

```python
# Exemplo — adaptar ao bloco existente de processamento de resposta:

# ... (código existente que obtém 'response' do LLM e grava em session_state) ...
st.session_state["messages"].append({
    "role": "assistant",
    "content": response,
    # ... outros campos existentes (timestamp, provider, tools_used) ...
})

# ── Renderizar tabelas pendentes (se o LLM chamou render_table) ───────────────
_render_pending_tables(
    project_name=st.session_state.get("selected_project_name", ""),
    last_question=question,   # variável local com a pergunta do usuário
)
```

> **Atenção ao posicionamento:** `_render_pending_tables` deve ser chamado **fora** de qualquer
> bloco `with st.spinner()` e **após** a resposta já estar gravada em `session_state`.
> O `st.pop("_pending_tables")` dentro da função garante que, se o usuário recarregar
> a página, as tabelas não reapareçam duplicadas.

### 4.4 — Lidar com múltiplas tabelas por resposta

A implementação acima já suporta múltiplas tabelas por turno — `_pending_tables` é uma lista. O LLM pode chamar `render_table` duas vezes numa mesma resposta (ex: "Tabela de tokens" + "Tabela de custos") e ambas serão renderizadas em sequência.

---

## Passo 5 — Modificar `skills/skill_assistant.md`

Adicionar a seguinte seção ao system prompt do assistente (localizar o bloco de instruções de ferramentas e adicionar após a listagem das ferramentas existentes):

```markdown
## Exibição de Dados Tabulares

Quando a resposta incluir dados que naturalmente se organizam em tabela
(listas de reuniões com atributos, action items, requisitos, custos, contagens, etc.),
use a ferramenta `render_table` em vez de escrever uma tabela Markdown.

Diretrizes:
- Chame `render_table` uma vez por tabela.
- Inclua `chart_type` quando o dado for quantitativo e um gráfico agregar valor
  (ex: distribuição de action items por responsável → "bar"; proporções → "pie").
- Defina `chart_x_col` como a coluna de categoria (ex: "Reunião", "Responsável").
- Defina `chart_y_cols` como a(s) coluna(s) numéricas (ex: ["Tokens", "Chunks"]).
- Use `chart_type: "none"` para tabelas puramente textuais (ex: lista de decisões).
- Após chamar `render_table`, você pode adicionar texto explicativo na sua resposta
  normalmente — as duas coisas coexistem.
- Não escreva a tabela também em Markdown — o `render_table` já cuida da exibição.
```

---

## Passo 6 — Atualizar `CLAUDE.md`

### 6.1 — Adicionar `modules/excel_exporter.py` na seção Repository Structure

```
│   ├── excel_exporter.py         # export_table_to_excel() — BytesIO .xlsx with formatted table + native Excel charts
```

### 6.2 — Atualizar a seção RAG Assistant — Tool catalog

No bloco de ferramentas disponíveis, adicionar `render_table` à lista de non-admin tools:

```
│    render_table(title, columns, rows, chart_type, chart_x_col?, chart_y_cols?) │
│    → persists to st.session_state["_pending_tables"]; triggers Excel download  │
```

### 6.3 — Adicionar nota sobre `_pending_tables`

Na seção de Session State, adicionar:

```
- `_pending_tables` — list[dict] — set by AssistantToolExecutor when render_table is called;
  consumed and cleared by _render_pending_tables() in Assistente.py after each assistant turn.
- `_excel_bytes_{hash}` — bytes — cached Excel file per table; keyed by title hash to survive rerun.
```

### 6.4 — Atualizar versão

```
**Current version:** v4.16
```

---

## Comportamento esperado após implementação

### Exemplo 1 — Tabela simples com gráfico

**Pergunta do usuário:**
> "Crie uma tabela mostrando o custo de embeddings e quantidade de tokens e chunks de cada reunião do projeto SDEA e também um gráfico de barras com esta visão"

**O que acontece:**
1. LLM chama `get_meeting_list()` → obtém reuniões do SDEA
2. LLM chama `get_meeting_summary()` ou consulta chunks para obter contagens
3. LLM chama `render_table(title="Custo de Embeddings — SDEA", columns=["Reunião","Tokens","Chunks","Custo (USD)"], rows=[...], chart_type="bar", chart_x_col="Reunião", chart_y_cols=["Tokens","Chunks"])`
4. LLM responde com texto explicativo
5. Interface exibe: tabela interativa (`st.dataframe`) + botão **"⬇️ Exportar para Excel + gráfico bar"**
6. Ao clicar: download de `p2d_tabela_20260513_1432.xlsx` com:
   - Aba "Custo de Embeddings — SDEA" — tabela formatada, zebra stripes, auto-filtro
   - Aba "Gráfico" — BarChart nativo Excel com séries Tokens e Chunks por Reunião
   - Aba "Metadados" — projeto, data, pergunta original

### Exemplo 2 — Múltiplas tabelas

**Pergunta:**
> "Me dê uma tabela com os action items da reunião 3 e outra com os requisitos de alta prioridade"

LLM chama `render_table` duas vezes. Interface exibe duas tabelas em sequência, cada uma com seu próprio botão de download Excel independente.

### Exemplo 3 — Tabela sem gráfico

**Pergunta:**
> "Liste as decisões tomadas nas últimas 5 reuniões"

LLM chama `render_table(..., chart_type="none")`. Interface exibe apenas a tabela formatada + botão Excel (sem aba de gráfico no arquivo).

---

## Checklist de validação

Após implementar, testar os seguintes cenários no Streamlit local antes do push:

- [ ] Pergunta gera tabela simples — `render_table` é chamado, tabela aparece no chat
- [ ] Botão "Exportar para Excel" aparece abaixo da tabela
- [ ] Arquivo `.xlsx` baixado abre corretamente no Excel/LibreOffice
- [ ] Aba "Gráfico" existe e renderiza o gráfico ao abrir no Excel
- [ ] `st.download_button` não quebra o histórico do chat após o rerun
- [ ] Duas tabelas na mesma resposta geram dois botões com IDs distintos (sem `DuplicateWidgetID`)
- [ ] Provedor DeepSeek chama `render_table` corretamente (schema OpenAI)
- [ ] Provedor Claude (Anthropic) chama `render_table` corretamente (schema Anthropic)
- [ ] Pergunta puramente narrativa (sem dados tabulares) → `render_table` não é chamado → nenhum botão Excel aparece
- [ ] `_pending_tables` é limpo após a renderização (não persiste para o próximo turno)

---

## Riscos e mitigações

| Risco | Mitigação |
|---|---|
| LLM ignora `render_table` e escreve tabela Markdown mesmo assim | Instrução explícita na `skill_assistant.md` + verificar se a instrução está no system prompt ativo (`_build_system_prompt_tools`) |
| LLM chama `render_table` com `rows` vazio | Handler verifica `if not columns or not rows: continue` — tabela vazia é silenciosamente ignorada |
| `_excel_bytes_{key}` não sobrevive ao rerun | Gerado e persistido em `session_state` ANTES do `st.download_button` — mesmo padrão já usado no projeto |
| `DuplicateWidgetID` quando mesma tabela aparece duas vezes | Key usa `abs(hash(title))` — se dois títulos idênticos colidirem, adicionar índice ao hash: `f"btn_excel_{key_suffix}_{idx}"` |
| `openpyxl` não instalado no Streamlit Cloud | Declarado explicitamente em `requirements.txt` — Streamlit Cloud instala no cold start |
| Títulos longos (>31 chars) quebram nome da aba Excel | `_safe_sheet_name()` trunca para 31 e remove caracteres ilegais |
| LLM envia `chart_y_cols` com nome de coluna inexistente | `_write_chart_sheet` silencia o erro via `try/except ValueError` na indexação |

---

*Guia gerado em 2026-05-13 — Process2Diagram v4.15 → v4.16*
