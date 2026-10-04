# Laptop hosted ODDI storage

ODDI's account database and chat history are owned by the laptop-hosted app.
Render is only an entry URL: it redirects visitors to the laptop's public HTTPS
tunnel and does not create accounts or keep a second copy of chat history.

## Where data is stored

- Chat messages: `%LOCALAPPDATA%\OddiAI\ChatHistory\account-<id>\<chat-id>.json`
- Session signing key: `%LOCALAPPDATA%\OddiAI\session.key`
- Account/login records and non-chat metadata: the ignored `users.db` file in
  this project folder

On first local startup, existing active, archived, and Bin chats in `users.db`
are moved to account-scoped JSON files, then removed from its chat tables. The
SQLite file is checkpointed and compacted after the move so deleted message
pages do not linger there. Account records remain so existing local accounts
can still sign in. Keep `users.db` backed up privately; do not commit it.

## Run the laptop service

From PowerShell in this project folder:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\run_laptop_server.ps1
```

The service binds to `127.0.0.1:8000`, keeps the session key under the current
Windows profile, and stores chat files in that profile's LocalAppData folder.
Keep the laptop awake and connected for the website to work. The browser on any
device must use the same public hostname and sign in to the same account.

## Connect the public website

Publish only `http://127.0.0.1:8000` through an HTTPS tunnel. Do not enable
router port forwarding for port 8000. In Render, set:

```text
ODDI_LAPTOP_ORIGIN=https://your-public-tunnel-hostname
```

Render then redirects the existing public URL to that HTTPS hostname. A
temporary Cloudflare Quick Tunnel hostname changes when restarted; a stable
public address needs a named tunnel and a domain. If the laptop service is off,
the website cannot read or save chats.

If Google sign-in is enabled, add the tunnel hostname's
`/auth/google/callback` URL to the Google OAuth allowed redirect URIs. Password
sign-in remains on the same account database on the laptop.

The tunnel publishes the ODDI web service, not a Windows drive share. The app
still runs with the permissions of its Windows account, so use a Windows
account without administrator privileges for a public installation. Chat
history files stay on the laptop, while prompts still have to reach the
configured AI provider to generate answers.
