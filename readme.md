# deploy: element chat

Installs Element Server Suite on a new VPS.

## How it works

- k3s runs Element Server Suite.
- Traefik listens on port 80.
- A Cloudflare Tunnel exposes the public websites.
- Cloudflare handles HTTPS.
- MatrixRTC is disabled because Cloudflare Tunnel does not support its UDP traffic.

The public domains and product name are configured in `deployment.json`.

## Install

> [!NOTE]
> The installer only works on a clean server. It will stop if k3s or cloudflared is already installed.

Run:

```bash
./install
```

The installer will:

1. Check the server.
2. Download, checksum, and install the required tools into `/usr/local/bin`.
3. Install k3s.
4. Ask for a Cloudflare Tunnel token.
5. Install Element Server Suite.
6. Create the admin account, Space, and team rooms.
7. Verify everything is working.

When creating the Cloudflare Tunnel, add these hostnames from `deployment.json`:

```text
chat
matrix
account
admin
```

Point each one to:

```text
http://localhost:80
```

Then add a final catch-all rule:

```text
http_status:404
```

Copy the tunnel token and paste it into the installer.

Installation state is saved in:

```text
/var/lib/element-chat/installation.json
```

The admin credentials are written to the file shown at the end of the installation.

If installation stops, resume it with:

```bash
sudo ./element resume
```

## Verify

```bash
sudo ./element verify
```

Checks that k3s, cloudflared, Kubernetes, and Element are working.

## Add users

Create a CSV:

```csv
username,display_name,teams
alice,Alicia Pérez,operations
bob,Roberto Díaz,sales;general
```

Available teams:

- general
- operations
- sales
- management

Import users:

```bash
sudo ./element users -- /path/to/users.csv
```

The generated credentials are saved under:

```text
/var/lib/element-chat/imports
```

If an import is interrupted:

```bash
sudo ./element users-resume -- /var/lib/element-chat/imports/users-TIMESTAMP.json
```

## Check the repository

```bash
./element check
```

Renders the Helm chart with the pinned Helm binary.

## Configuration

- `deployment.json` defines the public domains and product name.
- `organization.json` defines the admin account, Space, and team rooms.
- `chart/values.yaml.tmpl` generates the Helm values.
- `chart/files/` contains static files.
- `deploy.py` pins Helm, kubectl, and cloudflared.
