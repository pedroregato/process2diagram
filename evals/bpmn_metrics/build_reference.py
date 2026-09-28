# evals/bpmn_metrics/build_reference.py
# ─────────────────────────────────────────────────────────────────────────────
# Gera a distribuição de referência a partir dos .bpmn originais do repositório
# público da Camunda (o mesmo corpus do dataset do Kaggle):
#
#   git clone --depth 1 https://github.com/camunda/bpmn-for-research.git
#   python -m evals.bpmn_metrics.build_reference ../bpmn-for-research \
#          --out evals/bpmn_metrics/reference/camunda_metrics.csv
#
# Usa o mesmo metrics.py aplicado ao Vichāra, para que as duas distribuições
# sejam medidas exatamente da mesma forma.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from evals.bpmn_metrics.metrics import (
    FLAG_COLUMNS, METRIC_COLUMNS, iter_bpmn_files, metrics_from_file,
)

MIN_TNN = 3   # pools vazias ou com 1–2 nós são rascunhos, não modelos


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("folder", help="pasta com os .bpmn (clone de camunda/bpmn-for-research)")
    ap.add_argument("--out", default="evals/bpmn_metrics/reference/camunda_metrics.csv")
    args = ap.parse_args(argv)

    rows, failed, degenerate = [], 0, 0
    for path in iter_bpmn_files(args.folder):
        try:
            for m in metrics_from_file(path):
                if m.TNN < MIN_TNN:
                    degenerate += 1
                    continue
                m.extra["language"] = "English" if "/English/" in path.as_posix() else "German"
                rows.append(m.row())
        except Exception:  # XML malformado no corpus: ignora e conta
            failed += 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cols = ["source", "process_id", "language"] + METRIC_COLUMNS + FLAG_COLUMNS
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    print(f"{len(rows)} processos gravados em {out} "
          f"({degenerate} degenerados com TNN<{MIN_TNN} e {failed} arquivos ilegíveis ignorados)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
