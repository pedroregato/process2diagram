# evals/bpmn_metrics/compare.py
# ─────────────────────────────────────────────────────────────────────────────
# Compara os BPMNs do Vichāra com a distribuição de referência (Camunda) por
# faixa de tamanho e gera um relatório Markdown + CSV por processo.
#
# Fontes possíveis para os BPMNs do Vichāra:
#   --from-supabase          última versão de cada processo em bpmn_versions
#                            (usa st.secrets["supabase"], como o app)
#   --from-dir PASTA         arquivos .bpmn exportados
#   --from-csv ARQUIVO       métricas já calculadas (mesmas colunas)
#
# Exemplo:
#   python -m evals.bpmn_metrics.compare --from-supabase \
#          --out evals/bpmn_metrics/reports/2026-09-28
#
# Nada aqui chama LLM nem grava no banco.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from datetime import date
from pathlib import Path

from evals.bpmn_metrics.metrics import (
    FLAG_COLUMNS, METRIC_COLUMNS, SIZE_BANDS, iter_bpmn_files,
    metrics_from_file, metrics_from_xml, size_band,
)

REFERENCE_CSV = Path(__file__).parent / "reference" / "camunda_metrics.csv"
# métricas de complexidade comparadas por percentil (quanto maior, pior)
COMPLEXITY = ["CFC", "GM", "AGD", "MGD", "TNG", "GH"]
ALERT_PERCENTILE = 95


# ── carga ─────────────────────────────────────────────────────────────────────

def _num(v: str):
    if v in ("True", "False", "true", "false"):
        return v.lower() == "true"
    try:
        f = float(v)
        return int(f) if f.is_integer() else f
    except (TypeError, ValueError):
        return v


def read_csv(path: str | Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return [{k: _num(v) for k, v in r.items()} for r in csv.DictReader(fh)]


def load_from_dir(folder: str) -> list[dict]:
    return [m.row() for p in iter_bpmn_files(folder) for m in metrics_from_file(p)]


def load_from_supabase() -> list[dict]:
    """Última versão de cada processo (bpmn_versions). Só estrutura sai daqui."""
    from modules.supabase_client import get_supabase_client  # import tardio: evita Streamlit fora deste modo

    db = get_supabase_client()
    if db is None:
        raise SystemExit("Supabase não configurado (st.secrets['supabase']).")
    rows = (
        db.table("bpmn_versions")
        .select("process_id, bpmn_xml, created_at, meeting_id")
        .order("created_at", desc=True)
        .execute()
        .data
        or []
    )
    latest: dict[str, dict] = {}
    for r in rows:
        latest.setdefault(r["process_id"], r)
    out = []
    for pid, r in latest.items():
        try:
            for pool, m in enumerate(metrics_from_xml(r["bpmn_xml"] or "", source=pid), start=1):
                row = m.row()
                row.update(pool=pool, date=(r.get("created_at") or "")[:10],
                           studio=r.get("meeting_id") is None)
                out.append(row)
        except Exception as exc:  # XML ilegível: registra e segue
            out.append({"source": pid, "parse_error": str(exc)[:120]})
    return out


# ── estatística ───────────────────────────────────────────────────────────────

def percentile_rank(value: float, population: list[float]) -> float:
    """% da referência com valor ≤ value (0–100)."""
    if not population:
        return float("nan")
    return 100.0 * sum(1 for x in population if x <= value) / len(population)


def quantile(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    s = sorted(values)
    idx = (len(s) - 1) * q
    lo, hi = int(idx), min(int(idx) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (idx - lo)


def compare(target: list[dict], reference: list[dict], min_tnn: int = 3) -> tuple[list[dict], dict]:
    # Complexidade só faz sentido entre modelos que têm gateway: sem gateway
    # todas as métricas são 0 por construção (efeito teto). Por isso os
    # percentis e medianas usam só TNG > 0 dos dois lados.
    ref_by_band: dict[str, list[dict]] = {}
    for r in reference:
        if r["TNG"] > 0:
            ref_by_band.setdefault(size_band(r["TNN"]), []).append(r)
    ref_all_by_band: dict[str, int] = {}
    for r in reference:
        b = size_band(r["TNN"])
        ref_all_by_band[b] = ref_all_by_band.get(b, 0) + 1

    scored = []
    for r in target:
        if "parse_error" in r or r.get("TNN", 0) < min_tnn:
            continue
        band = size_band(r["TNN"])
        ref = ref_by_band.get(band, [])
        row = dict(r, band=band)
        alerts = []
        for k in COMPLEXITY if r["TNG"] > 0 else []:
            pct = percentile_rank(r[k], [x[k] for x in ref])
            row[f"pct_{k}"] = round(pct, 1)
            if pct > ALERT_PERCENTILE and r[k] > quantile([x[k] for x in ref], 0.95):
                alerts.append(k)
        row["alerts"] = ",".join(alerts)
        scored.append(row)

    summary = {"bands": {}, "flags": {}, "n_target": len(scored), "n_reference": len(reference)}
    for _, _, band in SIZE_BANDS:
        t_all = [r for r in scored if r["band"] == band]
        t = [r for r in t_all if r["TNG"] > 0]
        ref = ref_by_band.get(band, [])
        summary["bands"][band] = {
            "n_target_all": len(t_all),
            "n_reference_all": ref_all_by_band.get(band, 0),
            "n_target": len(t),
            "n_reference": len(ref),
            **{
                k: {
                    "target_median": statistics.median([r[k] for r in t]) if t else None,
                    "ref_p50": quantile([r[k] for r in ref], 0.5),
                    "ref_p95": quantile([r[k] for r in ref], 0.95),
                }
                for k in ["TNN"] + COMPLEXITY
            },
        }
    for flag in FLAG_COLUMNS + ["no_gateway"]:
        tv = [bool(r.get(flag)) for r in scored]
        rv = [bool(r.get(flag)) for r in reference if r.get("TNN", 0) >= min_tnn]
        summary["flags"][flag] = {
            "target_pct": 100 * sum(tv) / len(tv) if tv else 0,
            "reference_pct": 100 * sum(rv) / len(rv) if rv else 0,
        }
    summary["type_mix"] = {
        who: {
            k: sum(r[k] for r in rows) for k in ("TNGAND", "TNGXOR", "TNGOR")
        }
        for who, rows in (("target", scored), ("reference", reference))
    }
    return scored, summary


# ── relatório ─────────────────────────────────────────────────────────────────

def _fmt(v) -> str:
    if v is None:
        return "—"
    return f"{v:.2f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


def render_markdown(scored: list[dict], summary: dict, title: str = "Vichāra") -> str:
    lines = [
        f"# Métricas BPMN — {title} × referência Camunda",
        "",
        f"_Gerado em {date.today().isoformat()} por `evals/bpmn_metrics/compare.py`._",
        "",
        f"- Processos avaliados: **{summary['n_target']}** (TNN ≥ 3)",
        f"- Referência: **{summary['n_reference']}** processos do corpus Camunda BPMN for Research",
        "- Links throw/catch resolvidos como fluxo direto antes de medir.",
        "",
        "## Distribuição por tamanho (TNN)",
        "",
        "| Faixa | Vichāra | Referência |",
        "|---|---|---|",
    ]
    tot_t = sum(b["n_target_all"] for b in summary["bands"].values()) or 1
    tot_r = sum(b["n_reference_all"] for b in summary["bands"].values()) or 1
    for band, b in summary["bands"].items():
        lines.append(
            f"| {band} | {b['n_target_all']} ({100 * b['n_target_all'] / tot_t:.0f}%) "
            f"| {b['n_reference_all']} ({100 * b['n_reference_all'] / tot_r:.0f}%) |"
        )
    lines += [
        "",
        "## Complexidade por faixa (só processos com gateway)",
        "",
        "Mediana do Vichāra / p50 da referência / p95 da referência.",
        "",
        "| Faixa | n Vichāra | n ref | " + " | ".join(COMPLEXITY[:4]) + " |",
        "|---|---|---|" + "---|" * 4,
    ]
    for band, b in summary["bands"].items():
        cells = [
            f"{_fmt(b[k]['target_median'])} / {_fmt(b[k]['ref_p50'])} / {_fmt(b[k]['ref_p95'])}"
            for k in COMPLEXITY[:4]
        ]
        lines.append(f"| {band} | {b['n_target']} | {b['n_reference']} | " + " | ".join(cells) + " |")

    lines += ["", "## Sinais estruturais (% dos processos)", "", "| Sinal | Vichāra | Referência |", "|---|---|---|"]
    for flag, v in summary["flags"].items():
        lines.append(f"| {flag} | {v['target_pct']:.0f}% | {v['reference_pct']:.0f}% |")

    mix = summary["type_mix"]
    lines += ["", "## Mix de gateways", "", "| | AND | XOR | OR |", "|---|---|---|---|"]
    for who in ("target", "reference"):
        tot = sum(mix[who].values()) or 1
        lines.append(
            f"| {'Vichāra' if who == 'target' else 'Referência'} | "
            + " | ".join(f"{100 * mix[who][k] / tot:.0f}%" for k in ("TNGAND", "TNGXOR", "TNGOR"))
            + " |"
        )

    flagged = [r for r in scored if r["alerts"]]
    lines += ["", f"## Processos acima do p{ALERT_PERCENTILE} da faixa ({len(flagged)})", ""]
    if flagged:
        lines += ["| Processo | Pool | Faixa | TNN | CFC | GM | Alertas |", "|---|---|---|---|---|---|---|"]
        for r in sorted(flagged, key=lambda r: -r["CFC"]):
            lines.append(
                f"| {str(r['source'])[:8]} | {r.get('pool', '')} | {r['band']} | {r['TNN']} | "
                f"{r['CFC']} | {r['GM']} | {r['alerts']} |"
            )
    else:
        lines.append("Nenhum.")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Compara BPMNs com a referência Camunda")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-supabase", action="store_true")
    src.add_argument("--from-dir")
    src.add_argument("--from-csv")
    ap.add_argument("--reference", default=str(REFERENCE_CSV))
    ap.add_argument("--out", default=f"evals/bpmn_metrics/reports/{date.today().isoformat()}")
    args = ap.parse_args(argv)

    if args.from_supabase:
        target = load_from_supabase()
    elif args.from_dir:
        target = load_from_dir(args.from_dir)
    else:
        target = read_csv(args.from_csv)
    reference = read_csv(args.reference)

    scored, summary = compare(target, reference)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(render_markdown(scored, summary), encoding="utf-8")
    cols = sorted({k for r in scored for k in r}, key=lambda k: (k not in ("source", "pool", "band"), k))
    with (out / "vichara_metrics.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(scored)
    print(f"Relatório em {out / 'report.md'} ({summary['n_target']} processos)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
