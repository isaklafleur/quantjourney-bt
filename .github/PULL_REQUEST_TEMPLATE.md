<!--
Thanks for contributing to the QuantJourney Backtester.
A maintainer reviews every pull request and decides how to integrate it — your
change may be merged as-is, adapted, or re-applied through the source of truth
and this PR closed as integrated. See CONTRIBUTING.md.
Keep PRs focused: one strategy or one fix per PR.
-->

## What does this PR do?

<!-- One or two sentences describing the change and why. -->

## Type of change

- [ ] New example strategy
- [ ] Bug fix
- [ ] Documentation
- [ ] Other (describe below)

## For a new example strategy

<!-- Delete this section if not applicable. -->

- **Idea (1–2 sentences):**
- **Mode:** weights / orders / walk-forward
- **Universe:**
- **File:** `strategies/example_<mode>_<NN>_<name>.py`

## Checklist

- [ ] `pytest -q` passes.
- [ ] `ruff check .` is clean.
- [ ] New strategies pass `./strategy.sh <name> --check`.
- [ ] Docstrings follow the existing style (license header + Mode/idea/universe).
- [ ] New strategies are added to `strategies/README.md`.
- [ ] No credentials, API keys, tokens, or private paths are included.
- [ ] The change is focused and described above.
