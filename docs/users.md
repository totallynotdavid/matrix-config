# Users

`./element users` creates accounts from a CSV file and adds each account to the
Space and to its team rooms. It works only after the installation is complete.

## The CSV file

```csv
username,display_name,teams
alice,Alicia Pérez,operations
bob,Roberto Díaz,sales;general
```

| Column         | Rule                                                               |
| -------------- | ------------------------------------------------------------------ |
| `username`     | Lowercase letters, digits and `.` `_` `=` `-`. Unique in the file. |
| `display_name` | Required.                                                          |
| `teams`        | One or more team keys, separated by `;`.                           |

The header must be exactly `username,display_name,teams`. A team key is the
`key` of an entry in `rooms` in
[`organization.json`](configuration.md#organizationjson).

The file must be outside this repository and readable only by its owner:

```bash
chmod 600 /path/to/users.csv
```

## Import

```bash
sudo ./element users /path/to/users.csv
```

The command checks the whole file before it creates anything. It stops if any
username already exists. Then it creates each account, waits for Synapse to know
it, and joins the account to the Space and its team rooms. The accounts are not
administrators, so they cannot create rooms or send invites.

An account is `@<username>:<matrix host>`.

## Credentials and receipts

Each import writes two files under `/var/lib/element-chat/imports`:

- `credentials-<timestamp>.csv` with the columns `username,initial_password`.
- `users-<timestamp>.json`, the receipt. It records which accounts exist and
  which rooms each has joined.

Both files are mode 0600.

## Resume an import

If an import stops, resume it from its receipt:

```bash
sudo ./element users --resume /var/lib/element-chat/imports/users-TIMESTAMP.json
```

The import continues with the accounts and room joins the receipt does not list
as done. Resuming a finished import fails.
