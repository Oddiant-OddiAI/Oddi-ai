# Laptop SSD and Google Drive chat storage

ODDI keeps account-scoped chat JSON files on the laptop SSD and mirrors them to
the configured Google Drive folder. Render reads and writes the Drive copy, so
the public site can still load accounts and chats while the laptop is off. The
laptop sync worker pulls Drive changes back to the SSD when it is online.

## Storage layout

- Laptop chats: `%LOCALAPPDATA%\OddiAI\ChatHistory\account-<local-id>\<chat-id>.json`
- Laptop Library blobs: `%LOCALAPPDATA%\OddiAI\files\user_<local-id>\<storage-key>`
- Laptop account and Library metadata: `%LOCALAPPDATA%\OddiAI\users.db`
- Drive chats: `accounts/account-<stable-account-id>/chat-<chat-id>.json`
- Account login records in Drive: the matching account's `account.json`

The laptop launcher keeps chats, Library files, and the local database under the
same `%LOCALAPPDATA%\OddiAI` data folder. On first startup after this change,
files from the former `C:\ODDI_STORAGE\files` folder are copied into the new
Library folder. The old copies are retained as a recovery fallback; deleting a
Library item through ODDI removes both copies.

Account folders use a stable ID derived from the normalized account email on
Drive. Sync maps that folder to the laptop's local account ID, so local numeric
IDs may differ without mixing account histories. Existing laptop chat files
are uploaded during sync; Drive-created accounts and conversations are copied
to the laptop.

The laptop app commits chat changes to its SSD first, then queues the Drive
mirror in the background so a slow Drive request does not delay a chat reply.
The public Render site writes to Drive so it can serve every device whether
the laptop is on or off. When the laptop app is running, it pulls new Drive
chats to the SSD in the background (about every 30 seconds) and before local
login or registration. If the app closes before a queued mirror finishes, the
local copy remains safe and the next sync pass uploads it. Drive is the shared
sync source; the laptop keeps its own per-account copy.

## Shared workspaces

Shared groups use the chat database locally. On Drive-backed Render hosting,
configure `ODDI_SHARED_WORKSPACES_DATABASE_URL` with a persistent PostgreSQL
connection string in the Render environment. Group membership, invitations,
and live messages are stored there so different accounts and app instances see
the same workspace. Render's temporary local SQLite file is not suitable for
this data. Invitations appear inside ODDI and expire after 14 days. Groups have
no fixed member limit; admins can invite as many ODDI members as they need.

## Google Drive setup

ODDI authenticates to the owner's personal My Drive using Google OAuth user
credentials. Set these values in the laptop `.env` and Render Environment:

```dotenv
GOOGLE_CLIENT_ID="..."
GOOGLE_CLIENT_SECRET="..."
GOOGLE_REFRESH_TOKEN="..."
GOOGLE_DRIVE_FOLDER_ID="1bzGLXgYppJd5Sr0TCP_sA92alXMTd_6R"
```

`GOOGLE_REFRESH_TOKEN` must be authorized for the full Drive scope
`https://www.googleapis.com/auth/drive`, because the destination folder already
exists in personal My Drive. The Google Drive API must be enabled for the OAuth
client's Cloud project. Google OAuth testing-mode refresh tokens expire after
seven days, so the consent app needs production publishing for ongoing sync.

The service-account private key previously pasted into chat is exposed. Revoke
that key in Google Cloud IAM and remove the old `GOOGLE_DRIVE_PRIVATE_KEY` and
`GOOGLE_DRIVE_CLIENT_EMAIL` variables from Render. Never share the refresh
token, client secret, or `.env`.

## Start ODDI on the laptop

From PowerShell in this project folder:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\run_laptop_server.ps1
```

The laptop writes its local chat files under the current Windows profile's
LocalAppData folder. Keep `users.db` and the chat folder private and backed up.
The app starts even if Drive is temporarily unreachable; sync retries in the
background. A successful sync requires the laptop to be online and the Drive
credentials and folder permissions to be valid.

The Data tab in Settings shows the local chat count, queued chat changes and
deletions, the last successful sync, and the current Drive connection state. It
also offers a manual sync and, when OAuth authorization has expired, a Drive
reconnect link. Pending-change counts are saved in the local account chat index
so restarting the laptop app does not hide queued work.
