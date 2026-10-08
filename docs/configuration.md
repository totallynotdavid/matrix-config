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
lowercase public DNS name, and the four must differ.

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

The file must contain exactly `administrator`, `space` and `rooms`, with the
keys shown. `rooms` must hold at least one room. `display_name` and `name` must
not be blank. The administrator's username, the Space key and the room keys
become account names and room aliases, so each may use only `a-z`, `0-9` and
`. _ = -`, and the Space key and the room keys must be unique.

All rooms are private and are children of the Space. The installer creates them
in the order listed.

## Validation

[`element_chat/config.py`](../element_chat/config.py) enforces the rules for
both files. The installer's `preflight` phase and the tests run by
`./element check` load the files through it, so an invalid file stops the
installer before it changes the server, and the error names the file and the
field.

The static files that customize Element and the account pages are in
[`chart/files/`](../chart/files); see [Architecture](architecture.md#chart).
