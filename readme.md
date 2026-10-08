# Element Chat

Element Chat installs a self-hosted [Element Server Suite][ess] (Matrix chat)
with a Spanish interface on a new server. It is for an operator who runs chat
for one organization: one administrator account, one Space and a fixed set of
team rooms.

It targets a single clean Ubuntu 26.04 x86_64 server running k3s. A Cloudflare
Tunnel exposes the public sites and Cloudflare serves HTTPS, so the server holds
no certificates. MatrixRTC is disabled.

## Install

On the server, in a checkout of this repository:

```bash
sudo ./install
```

The installer checks the server, installs the tools and k3s, asks for a
Cloudflare Tunnel token, installs Element Server Suite, creates the
administrator, Space and team rooms, and verifies the result:

```text
[preflight] running
[preflight] complete
[tools] running
[tools] complete
[k3s] running
...
[verify] complete
Element Chat is installed. Bootstrap credentials: /var/lib/element-chat/bootstrap-credentials.txt
```

[Installation](docs/installation.md) lists the requirements, the Cloudflare
Tunnel settings and how to resume a stopped install.

## Use

Check a running installation:

```bash
sudo ./element verify
```

Create accounts from a CSV file and add them to their team rooms:

```bash
sudo ./element users /path/to/users.csv
```

## Features

- Installs from one command and resumes after a failure.
- Downloads helm, kubectl and cloudflared at pinned versions and checks their
  SHA-256 sums.
- Takes the product name and the four public hostnames from `deployment.json`.
- Creates the administrator, the Space and the team rooms listed in
  `organization.json`.
- Imports users in bulk with generated passwords and team room membership.
- Serves Element Web and the account pages in Spanish.
- Lets only the administrator and Synapse admins create rooms and send invites.
- Rejects an invalid `deployment.json` or `organization.json` with a message
  that names the field.
- Runs the repository's tests and lints the chart with `./element check`.

## Documentation

- [Manual](docs/readme.md)
- [Contributing](.github/contributing.md)

[ess]: https://github.com/element-hq/ess-helm
