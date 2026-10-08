# Installation

## Requirements

The installer stops in its first phase unless the server has:

- Ubuntu 26.04 on x86_64.
- Python 3.11 or later.
- At least 8 GB of RAM.
- At least 30 GB of free disk space on `/`.
- No k3s and no cloudflared. A running `k3s` or `cloudflared` service, or the
  files `/etc/rancher/k3s/k3s.yaml` or `/etc/cloudflared/token`, count as
  existing infrastructure.

It also needs root and outbound HTTPS access to `get.helm.sh`, `dl.k8s.io`,
`github.com`, `get.k3s.io` and `ghcr.io`.

Before you start, set the product name and the four hostnames in
[`deployment.json`](configuration.md#deploymentjson), and the administrator,
Space and rooms in [`organization.json`](configuration.md#organizationjson). You
also need a Cloudflare account that serves those hostnames.

## Run the installer

```bash
sudo ./install
```

`./install` is `./element install`. It refuses to start when
`/var/lib/element-chat/installation.json` exists. Resume instead (see
[Resume](#resume)).

The installer runs these phases in order:

| Phase          | What it does                                                                                                                                                           |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `preflight`    | Checks the requirements above and validates the two configuration files.                                                                                               |
| `tools`        | Downloads helm, kubectl and cloudflared into `/usr/local/bin`, checks each SHA-256 sum and version, downloads the k3s install script, and renders and lints the chart. |
| `k3s`          | Installs the pinned k3s version. Waits for the node and Traefik to be ready.                                                                                           |
| `tunnel`       | Prints the hostnames to route, asks for the tunnel token, and starts a `cloudflared` systemd service.                                                                  |
| `application`  | Installs the Helm release `ess` into the namespace `ess` and waits up to 12 minutes. A failed install rolls back.                                                      |
| `organization` | Creates the administrator account, the Space and the team rooms.                                                                                                       |
| `verify`       | Runs the checks in [Verify](#verify).                                                                                                                                  |

The pinned versions are in
[`element_chat/installation.py`](../element_chat/installation.py).

## Cloudflare Tunnel

The `tunnel` phase pauses for a token. Create a remotely managed Cloudflare
Tunnel first:

1. Add a public hostname for each of the four hosts in `deployment.json`
   (`chat`, `matrix`, `account`, `admin`). Point each one to
   `http://localhost:80`.
2. Add a final catch-all rule with the service `http_status:404`.
3. Copy the tunnel token and paste it at the `Cloudflare Tunnel token:` prompt.
   The input is hidden.

The installer rejects a token shorter than 80 characters or one that contains
whitespace. It stores the token in `/etc/cloudflared/token` (mode 0600) and
defines the service in `/etc/systemd/system/cloudflared.service`.

## After the install

The administrator's username comes from `organization.json`. The generated
password is in `/var/lib/element-chat/bootstrap-credentials.txt` (mode 0600), a
CSV with the columns `username,password`. The installer prints the path on the
last line.

## Resume

The installer records each finished phase in
`/var/lib/element-chat/installation.json`. If a phase fails, fix the cause and
run:

```bash
sudo ./element install --resume
```

Finished phases are skipped. If the installer stops before it writes that file,
run `sudo ./install` again. Resuming a finished installation fails and tells you
to verify. Running `./install` when the file exists fails and names the resume
command.

## Verify

```bash
sudo ./element verify
```

It fails on the first check that does not hold:

- The `k3s` and `cloudflared` services are active.
- The Helm release `ess` has status `deployed`.
- Every pod in the namespace `ess` is running and ready (completed pods are
  ignored).
- `https://<matrix host>/_matrix/client/versions` returns a version list.
- `https://<chat host>/config.json` has the configured brand, the matrix host as
  the homeserver, Spanish as the default language and the custom translations
  URL.
- `https://<account host>` serves a page with `<html lang="es">`.
- `https://<admin host>` responds.

The URL checks go through the Cloudflare Tunnel, so the tunnel must work from
the server.
