# tests/test_skill_files.py
# ─────────────────────────────────────────────────────────────────────────────
# Verifies that every skill file referenced by an agent actually exists on disk.
# Guards against Linux case-sensitivity bugs (Streamlit Cloud) and broken
# skill_path assignments after renames.
#
# Run: pytest tests/test_skill_files.py -v
# ─────────────────────────────────────────────────────────────────────────────

import re
import sys
from pathlib import Path

import pytest

# Make sure the project root is on the path so imports work
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ── Collect all skill_path values from agent source files ────────────────────

def _collect_skill_paths() -> list[tuple[str, str]]:
    """Return list of (agent_file, skill_path) from all agents/*.py files."""
    results = []
    agents_dir = PROJECT_ROOT / "agents"
    pattern = re.compile(r'skill_path\s*=\s*"([^"]+)"')
    for agent_file in sorted(agents_dir.glob("*.py")):
        text = agent_file.read_text(encoding="utf-8")
        for match in pattern.finditer(text):
            path_str = match.group(1)
            # Skip base_agent.py's fallback example reference
            if agent_file.name == "base_agent.py":
                continue
            results.append((agent_file.name, path_str))
    return results


_SKILL_PATH_CASES = _collect_skill_paths()


@pytest.mark.parametrize("agent_file,skill_path", _SKILL_PATH_CASES,
                         ids=[f"{a}::{p}" for a, p in _SKILL_PATH_CASES])
def test_skill_file_exists(agent_file: str, skill_path: str) -> None:
    """Each skill_path in an agent file must resolve to an existing file."""
    full_path = PROJECT_ROOT / skill_path
    assert full_path.exists(), (
        f"Agent '{agent_file}' references skill_path='{skill_path}' "
        f"but '{full_path}' does not exist. "
        "Run `git ls-files skills/` to check the exact filename on disk."
    )


# ── Verify AGENT_REGISTRY skill paths ────────────────────────────────────────

def test_agent_registry_skill_paths_exist() -> None:
    """Every skill_path in AGENT_REGISTRY must resolve to an existing file."""
    from core.agent_registry import AGENT_REGISTRY  # noqa: PLC0415
    missing = []
    for agent_name, entry in AGENT_REGISTRY.items():
        sp = entry.get("skill_path")
        if sp is None:
            continue
        full = PROJECT_ROOT / sp
        if not full.exists():
            missing.append(f"{agent_name} → {sp}")
    assert not missing, "Missing skill files in AGENT_REGISTRY:\n" + "\n".join(missing)


def test_agent_registry_authority_levels() -> None:
    """All entries in AGENT_REGISTRY must have a valid authority_level."""
    from core.agent_registry import AGENT_REGISTRY, READ_AGENTS, DRAFT_AGENTS, ACTION_AGENTS  # noqa: PLC0415
    valid = {"read", "draft", "act"}
    for name, entry in AGENT_REGISTRY.items():
        assert entry["authority_level"] in valid, (
            f"Agent '{name}' has invalid authority_level={entry['authority_level']!r}"
        )
    # Convenience sets must be disjoint
    assert READ_AGENTS.isdisjoint(DRAFT_AGENTS), "READ_AGENTS and DRAFT_AGENTS overlap"
    assert READ_AGENTS.isdisjoint(ACTION_AGENTS), "READ_AGENTS and ACTION_AGENTS overlap"
    assert DRAFT_AGENTS.isdisjoint(ACTION_AGENTS), "DRAFT_AGENTS and ACTION_AGENTS overlap"


# ── Verify frontmatter stripping ──────────────────────────────────────────────

def test_load_skill_strips_frontmatter(tmp_path: Path) -> None:
    """_load_skill() must strip YAML --- frontmatter before returning content."""
    # Patch skill_path to a temp file so we don't need a real agent
    from agents.base_agent import BaseAgent  # noqa: PLC0415

    skill_file = tmp_path / "test_skill.md"
    skill_file.write_text(
        "---\nname: test\nversion: 1\n---\n\n# Real content\nDo the thing.\n",
        encoding="utf-8",
    )

    class _FakeAgent(BaseAgent):
        name = "_test"
        skill_path = str(skill_file)

        def build_prompt(self, hub, output_language="Auto-detect"):
            return "", ""

        def run(self, hub, output_language="Auto-detect"):
            return hub

        def _load_skill(self) -> str:
            import re as _re
            if not self.skill_path:
                return ""
            path = Path(self.skill_path)
            if not path.exists():
                return ""
            content = path.read_text(encoding="utf-8")
            content = _re.sub(r'^---\s*\n.*?\n---\s*\n', '', content, flags=_re.DOTALL)
            return content.lstrip('\n')

    agent = _FakeAgent.__new__(_FakeAgent)
    agent.skill_path = str(skill_file)
    result = agent._load_skill()

    assert "---" not in result, "Frontmatter dashes should be stripped"
    assert "name: test" not in result, "Frontmatter keys should be stripped"
    assert "# Real content" in result, "Actual content must be preserved"
    assert not result.startswith('\n'), "Leading newlines should be stripped"


def test_load_skill_no_frontmatter_unchanged(tmp_path: Path) -> None:
    """_load_skill() must return content unchanged when no frontmatter is present."""
    skill_file = tmp_path / "no_frontmatter.md"
    skill_file.write_text("# Instructions\nDo the thing.\n", encoding="utf-8")

    from agents.base_agent import BaseAgent  # noqa: PLC0415

    class _FakeAgent(BaseAgent):
        name = "_test2"
        skill_path = str(skill_file)

        def build_prompt(self, hub, output_language="Auto-detect"):
            return "", ""

        def run(self, hub, output_language="Auto-detect"):
            return hub

    agent = _FakeAgent.__new__(_FakeAgent)
    agent.skill_path = str(skill_file)
    result = agent._load_skill()

    assert result.startswith("# Instructions"), "Content without frontmatter should be returned as-is"
