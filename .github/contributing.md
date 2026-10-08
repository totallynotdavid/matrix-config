# Contributing

## Set up

You need Python 3.11 or later and [mise](https://mise.jdx.dev). The Python code
has no third-party dependencies. `mise run check` installs the helm version
pinned in [`mise.toml`](../mise.toml), which matches the one the installer
downloads ([`element_chat/installation.py`](../element_chat/installation.py)).

## Check a change

```bash
mise run check
```

The task runs `./element check`. It loads `deployment.json` and
`organization.json`, compiles `chart/files/room_creation_policy.py`, then runs
`helm dependency build`, `helm lint --strict` and `helm template` on the chart.
The dependency build downloads the ESS chart from `ghcr.io`, so it needs network
access. It ends with `Repository checks passed.`

The command does not touch a cluster. The installer phases, `verify` and the
user import need a real server. Try a change to them on a clean Ubuntu 26.04
server (see [Installation](../docs/installation.md)) and finish with
`sudo ./element verify`.

## Documentation

Format Markdown with:

```bash
bunx prettier --print-width 80 --prose-wrap always --write '**/*.md'
```

Each fact lives in one document. The [manual](../docs/readme.md) lists which
document owns what.
