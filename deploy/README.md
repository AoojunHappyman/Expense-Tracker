# Deploy: Waitress + Caddy on one Linux server

This configuration assumes Caddy is the only proxy, on the same machine as
Waitress. It does not configure a CDN, container network or managed hosting proxy.

## 1. Prepare the server

- Point the domain's A record (and AAAA if used) to the server.
- Install Python, MySQL or connect to a private managed MySQL service.
- Install Caddy using its official installation instructions.
- Allow inbound 80 and 443; keep MySQL and port 8080 private.
- Create a dedicated service user `expense`, clone this repository to
  `/opt/expense-tracker`, and give that user read access to the application.
- Create `/opt/expense-tracker/venv` and install `requirements.txt` in it.

## 2. Configure secrets

Create `/etc/expense-tracker.env`, owned by root with permissions 600:

```dotenv
APP_ENV=production
PUBLIC_URL=https://YOUR_REAL_DOMAIN
SECRET_KEY=YOUR_RANDOM_SECRET
DB_HOST=localhost
DB_NAME=expense_tracker
DB_USER=expense_app
DB_PASSWORD=YOUR_DATABASE_PASSWORD
```

Generate SECRET_KEY locally using `python -c "import secrets; print(secrets.token_hex(32))"`.
Never commit this file. Use a dedicated database account with SELECT, INSERT,
UPDATE and DELETE permissions for runtime; use a separate migration account
with schema modification permissions when applying `schema.sql` or migrations.

For a new database run `schema.sql`. For an existing database back it up and run
`python -m flask --app app migrate-accounts` with migration credentials loaded.
Do not run `schema.sql` as an upgrade for a legacy database.
All workers must share the same SECRET_KEY. Production always enables Secure,
HttpOnly, SameSite=Lax cookies with the `__Host-` cookie prefix.

## 3. Start the application and HTTPS proxy

- Copy `expense-tracker.service` into `/etc/systemd/system/`.
- Run `sudo systemctl daemon-reload` then `sudo systemctl enable --now expense-tracker`.
- Replace `expense.example.com` in Caddyfile with the real domain. It must match
  the host in PUBLIC_URL exactly.
- Merge the site block into `/etc/caddy/Caddyfile` if it already hosts other sites.
- Run `sudo caddy validate --config /etc/caddy/Caddyfile`, then reload the Caddy service.
- Caddy obtains/renews TLS certificates and redirects HTTP to HTTPS once DNS and
  ports 80/443 are reachable. No certificate has been issued by this repository.

Waitress listens only on `127.0.0.1:8080`. It trusts exactly one same-host proxy
for X-Forwarded-For and X-Forwarded-Proto. Caddy supplies these headers. Do not
add ProxyFix or trust arbitrary forwarded headers. Adding another proxy/CDN
requires revisiting these settings to preserve IP-based rate limits.

On Windows, `venv\Scripts\python.exe serve.py` runs the same WSGI server after
the production environment is configured; use an appropriate service manager
for automatic startup. Do not use `python app.py` as the public server.

## 4. Verify before sharing the URL

- `http://YOUR_REAL_DOMAIN/login` redirects to HTTPS.
- HTTPS certificate is valid; login/register/recover load correctly.
- Cookies use Secure, HttpOnly, SameSite=Lax; HSTS is present on HTTPS responses.
- Test two accounts, CRUD and summaries, then log out and verify APIs return 401.
- Verify the rate limiter sees individual client IPs through the proxy.
- Trigger a controlled error only in staging: HTML/JSON must not contain
  database errors, passwords, filesystem paths or tracebacks.
- Verify automatic backups and restore before accepting real users.

Application errors have a reference ID; find it with
`journalctl -u expense-tracker`. Logs intentionally omit exception messages and
request bodies to avoid leaking secrets. Investigate the recorded exception type
and reproduce with test data locally. Never enable the debugger on the public site.

## References

- https://docs.pylonsproject.org/projects/waitress/en/stable/arguments.html
- https://caddyserver.com/docs/automatic-https
- https://caddyserver.com/docs/caddyfile/directives/reverse_proxy
