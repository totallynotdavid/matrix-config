# Contributing

## Set up

Install [mise](https://mise.jdx.dev), then run:

```bash
mise run install
```

[`mise.toml`](../mise.toml) pins Python, uv, helm, gitleaks and oxfmt. The helm
version matches the one the installer downloads
([`element_chat/installation.py`](../element_chat/installation.py)). The install
task syncs the Python dev tools from `uv.lock`.

## Check a change

```bash
mise run check
```

The task writes nothing. It runs:

- `lint`: ruff, oxfmt for Markdown, JSON and YAML, and gitleaks over the tree.
- `typecheck`: `mypy --strict` over `deploy.py`, `element_chat/` and `tests/`.
- `test`: the pytest suite in [`tests/`](../tests), without the `integration`
  marker.

`mise run fix` applies the safe ruff fixes and formats every file.

The suite covers:

- `test_config.py` loads `deployment.json` and `organization.json` and rejects
  invalid files.
- `test_users.py` validates worker CSV files.
- `test_chart.py` compiles `chart/files/room_creation_policy.py`. Its
  `integration` test runs `helm dependency build`, `helm lint --strict` and
  `helm template` on the chart and checks the rendered hook. The dependency
  build downloads the ESS chart from `ghcr.io`, so `mise run test:integration`
  needs network access.

To run one file, use `uv run pytest tests/test_users.py`.

The tests do not touch a cluster. The installer phases, `verify` and the user
import need a real server. Try a change to them on a clean Ubuntu 26.04 server
(see [Installation](../docs/installation.md)) and finish with
`sudo ./element verify`.

Add a test for the behavior you change. Call the real function with real files,
not a mock.

## Documentation

`mise run fix` formats Markdown. Each fact lives in one document. The
[manual](../docs/readme.md) lists which document owns what.
