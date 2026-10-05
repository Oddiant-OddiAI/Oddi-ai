# Laptop SSD and Google Drive chat storage

ODDI keeps account-scoped chat JSON files on the laptop SSD and mirrors them to
the configured Google Drive folder. Render reads and writes the Drive copy, so
the public site can still load accounts and chats while the laptop is off. The
laptop sync worker pulls Drive changes back to the SSD when it is online.

## Storage layout

- Laptop chats: `%LOCALAPPDATA%\OddiAI\ChatHistory\account-<local-id>\<chat-id>.json`
- Drive chats: `accounts/account-<stable-account-id>/chat-<chat-id>.json`
- Account login records on the laptop: ignored `users.db`
- Account login records in Drive: the matching account's `account.json`

Account folders use a stable ID derived from the normalized account email on
Drive. Sync maps that folder to the laptop's local account ID, so local numeric
IDs may differ without mixing account histories. Existing laptop chat files
are uploaded during sync; Drive-created accounts and conversations are copied
to the laptop.

The laptop app writes chats to its SSD first and mirrors changes to Drive.
The public Render site writes to Drive so it can serve every device whether
the laptop is on or off. When the laptop app is running, it pulls new Drive
chats to the SSD in the background (about every 30 seconds) and before local
login or registration. Drive is the shared sync source; the laptop keeps its
own per-account copy.

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
