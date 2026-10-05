# Making a change

Start with an issue describing the question, correction or proposed improvement. For an analysis change, include the source and explain how it affects the comparison.

Run the project once using the README instructions, then work on a branch. After changing calculations or SQL, run:

```bash
uv run --locked python pipeline.py build
```

After changing the page, run `pipeline.py serve` and check the calendar, annual comparisons, maps, year selection, sortable tables, a narrow phone view and dark mode. Without a Protomaps key, the ward outlines and tables should still work.

Before committing:

```bash
uv run --locked python -m unittest discover -s tests
uv run --locked python -m compileall -q pipeline.py scripts packages/data/scripts
git add README.md docs apps/web/public packages/data/scripts scripts tests pyproject.toml uv.lock
uv run --locked python scripts/check_public_files.py
git diff --cached --check
```

Stage only the source files you changed. Never add `.cache/`, prepared results, the local map configuration, source exports or credentials. The public-file check inspects the Git index so it checks the bytes that would be committed.

Opening a pull request should explain what readers will see differently, why the change is justified, and which checks passed. Avoid claims about causality that the study design cannot support. To change study years or add later Halloweens, update both the calculations and the page's year controls, captions and coverage notes.
