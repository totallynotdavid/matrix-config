# Configuration

Two JSON files at the repository root describe a deployment. The installer reads
them during installation. This repository has no command that applies a later
change to a running server.

## deployment.json

```json
{
  "brand": "Infinity",
  "hosts": {
    "chat": "chat.crmprosolutions.com",
    "matrix": "matrix.crmprosolutions.com",
    "account": "account.crmprosolutions.com",
    "admin": "admin.crmprosolutions.com"
  }
}
```

| Key             | Meaning                                                                                      |
| --------------- | -------------------------------------------------------------------------------------------- |
| `brand`         | The product name. Element Web shows it, and it names the Space.                              |
| `hosts.chat`    | Element Web, where people chat.                                                              |
| `hosts.matrix`  | The Matrix homeserver (Synapse). It is also the server name, so accounts are `@user:<host>`. |
| `hosts.account` | The account pages (Matrix Authentication Service).                                           |
| `hosts.admin`   | Element Admin.                                                                               |

The file must contain exactly `brand` and these four hosts. Each host must be a
lowercase public DNS name, and the four must differ. `./element check` and the
installer's `preflight` phase enforce this
([`element_chat/config.py`](../element_chat/config.py)).

## organization.json

```json
{
  "administrator": {
    "username": "admin",
    "display_name": "Chat administrator"
  },
  "space": {
    "key": "company"
  },
  "rooms": [
    { "key": "general", "name": "General" },
    { "key": "operations", "name": "Operaciones" }
  ]
}
```

(The file in the repository lists four rooms.)

| Key                          | Meaning                                                            |
| ---------------------------- | ------------------------------------------------------------------ |
| `administrator.username`     | The administrator's account name.                                  |
| `administrator.display_name` | Its display name.                                                  |
| `space.key`                  | The alias of the Space. The Space is named after `brand`.          |
| `rooms[].key`                | The alias of a team room. [Users](users.md) refer to rooms by key. |
| `rooms[].name`               | The room's display name.                                           |

All rooms are private and are children of the Space. The installer creates them
in the order listed.

The static files that customize Element and the account pages are in
[`chart/files/`](../chart/files); see [Architecture](architecture.md#chart).
