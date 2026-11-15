# Contributing to Process2Diagram

Thanks for helping out. The full contributor guide, with setup, the architecture tour, screenshots and good first issues, is in **[`docs/CONTRIBUTOR_GUIDE.html`](docs/CONTRIBUTOR_GUIDE.html)**. Download the file and open it in a browser. This page is the short version.

> The UI, internal docs and many comments are in Brazilian Portuguese. That's intentional. English is fine for code, commits and PRs.

## How `main` is protected

Every push to `main` **auto-deploys to Streamlit Cloud**, so `main` is protected by the ruleset **"Protect main"**:

- Changes reach `main` only through a **pull request**, with **1 approving review**
- An approval is dismissed when new commits are pushed
- All review conversations must be resolved before merging
- Force-pushes and deletion of `main` are blocked

Repository admins can bypass these rules. Everyone else goes through PRs.

## Workflow

```bash
git checkout main && git pull origin main
git checkout -b feat/short-description     # feat/ fix/ docs/ refactor/ test/
# ... make small, focused commits ...
pytest tests/
streamlit run app.py
git push -u origin feat/short-description
gh pr create --base main --fill            # or use the GitHub UI
```

Rebase onto `origin/main` before you ask for review (`git push --force-with-lease` on **your** branch only).

## Non-negotiable conventions

Read `CLAUDE.md` first. Most important:

- New agents inherit from `BaseAgent` and are registered in `Orchestrator._PLAN` and `core/rerun_handlers.py`. Never instantiate agents from pages.
- New `KnowledgeHub` fields always get a guard in `KnowledgeHub.migrate()`.
- Skill files use lowercase names. Check with `git ls-files skills/` (Streamlit Cloud runs on case-sensitive Linux).
- Supabase access is **fail-open**: return `[]` or `None` and never let an exception reach the UI.
- Analysis pages use `require_active_project()`, never a local project selectbox.
- New assistant tools go in the matching mixin in `core/tools/`, not in `core/assistant_tools.py`.
- Pin dependencies to exact versions (`pkg==1.2.3`).
- API keys stay in `st.session_state` only. Never commit `secrets.toml`, `.env` or credentials.

## PR checklist

- [ ] Branch is up to date with `main`
- [ ] `pytest tests/` passes and the app starts locally
- [ ] `migrate()` updated if `KnowledgeHub` changed
- [ ] Skill filenames verified with `git ls-files skills/`
- [ ] New dependencies pinned
- [ ] No secrets or personal data in the diff
- [ ] Supabase migrations (`setup/*.sql`) called out in the PR description
- [ ] Feature noted in `claude_guideline/roadmap.md`

## Data

Some contexts in the deployed app hold real pilot data, so treat them as confidential. For experiments, use a course/demo context and the fictional transcripts in `demos/aurora/` or `test-scenarios/`.
