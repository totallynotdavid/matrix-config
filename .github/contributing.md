# Contributing

## Set up

You need Python 3.11 or later and [mise](https://mise.jdx.dev). The Python code
and its tests have no third-party dependencies. `mise run check` installs the
helm version pinned in [`mise.toml`](../mise.toml), which matches the one the
installer downloads
([`element_chat/installation.py`](../element_chat/installation.py)).

## Check a change

```bash
mise run check
```

The task runs `./element check`, which runs every test in [`tests/`](../tests)
with `unittest`:

- `test_config.py` loads `deployment.json` and `organization.json` and rejects
  invalid files.
- `test_users.py` validates worker CSV files.
- `test_chart.py` compiles `chart/files/room_creation_policy.py`, then runs
  `helm dependency build`, `helm lint --strict` and `helm template` on the chart
  and checks the rendered hook. The dependency build downloads the ESS chart
  from `ghcr.io`, so it needs network access.

The command ends with `Repository checks passed.` and exits 1 when a test fails.
To run one file, use `python3 -m unittest tests.test_users`.

The tests do not touch a cluster. The installer phases, `verify` and the user
import need a real server. Try a change to them on a clean Ubuntu 26.04 server
(see [Installation](../docs/installation.md)) and finish with
`sudo ./element verify`.

Add a test for the behavior you change. Call the real function with real files,
not a mock.

## Documentation

Format Markdown with:

```bash
bunx prettier --print-width 80 --prose-wrap always --write '**/*.md'
```

Each fact lives in one document. The [manual](../docs/readme.md) lists which
document owns what.
