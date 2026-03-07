"""
setup_v3.py
Cria a estrutura de pastas e arquivos __init__.py da arquitetura v3
no projeto Process2Diagram, sem tocar em nenhum arquivo existente.

Uso:
    Coloque este script na raiz do projeto e execute:
    python setup_v3.py
"""

import os
import sys
from pathlib import Path

# ── Configuração ──────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# Pastas que devem existir na v3
REQUIRED_DIRS = [
    "modules",          # já existe na v2 — só garante que está lá
    "core",             # NOVO
    "agents",           # NOVO
    "skills",           # NOVO
]

# Arquivos __init__.py necessários para os novos packages Python
INIT_FILES = [
    "core/__init__.py",
    "agents/__init__.py",
]

# ── Helpers ───────────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
YELLOW = "\033[93m"
GRAY   = "\033[90m"
RESET  = "\033[0m"

def log_created(path):  print(f"  {GREEN}[criado]{RESET}  {path}")
def log_exists(path):   print(f"  {GRAY}[existe]{RESET}  {path}")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print()
    print("=" * 55)
    print("  Process2Diagram — Setup Estrutura v3")
    print(f"  Raiz: {PROJECT_ROOT}")
    print("=" * 55)

    # 1. Criar pastas
    print("\n📁 Pastas:\n")
    for dir_name in REQUIRED_DIRS:
        dir_path = PROJECT_ROOT / dir_name
        if dir_path.exists():
            log_exists(dir_name + "/")
        else:
            dir_path.mkdir(parents=True)
            log_created(dir_name + "/")

    # 2. Criar __init__.py (apenas se não existir)
    print("\n📄 Arquivos __init__.py:\n")
    for rel_path in INIT_FILES:
        file_path = PROJECT_ROOT / rel_path
        if file_path.exists():
            log_exists(rel_path)
        else:
            file_path.write_text(f"# {file_path.parent.name} package\n", encoding="utf-8")
            log_created(rel_path)

    # 3. Relatório final
    print()
    print("=" * 55)
    print("  Estrutura esperada após este script:")
    print("=" * 55)
    tree = """
  process2diagram/
  ├── app.py
  ├── requirements.txt
  ├── setup_v3.py           ← este script
  │
  ├── modules/              (existente — não alterado)
  │   ├── config.py
  │   ├── session_security.py
  │   └── ...
  │
  ├── core/                 (novo)
  │   └── __init__.py
  │
  ├── agents/               (novo)
  │   └── __init__.py
  │
  └── skills/               (novo)
"""
    print(tree)
    print("  Próximo passo: copie os arquivos .py e .md")
    print("  gerados pelo assistente para as pastas acima.")
    print("=" * 55)
    print()

if __name__ == "__main__":
    main()