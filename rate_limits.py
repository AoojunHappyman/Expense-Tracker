"""Shared MySQL-backed request limits, independent of browser sessions/workers."""
import hashlib
import hmac

from flask import current_app, request

RATE_LIMIT_SQL = '''CREATE TABLE IF NOT EXISTS auth_rate_limits (
    bucket_key CHAR(64) PRIMARY KEY,
    attempts INT UNSIGNED NOT NULL,
    expires_at DATETIME NOT NULL,
    INDEX idx_rate_expiry (expires_at)
) ENGINE=InnoDB'''

# All POST attempts count, including successful requests.
LIMITS = {
    'login': ((30, 900), (10, 900)),
    'register': ((5, 3600), None),
    'recover': ((10, 900), (5, 900)),
}


def check_auth_limit(connect, endpoint):
    """Return seconds until retry, or zero. Never trust forwarded IP headers."""
    ip_limit, account_limit = LIMITS[endpoint]
    scopes = [('ip', request.remote_addr or 'unknown', ip_limit)]
    username = request.form.get('username', '').strip().lower()
    if account_limit and username:
        scopes.append(('account', username, account_limit))
    conn = connect()
    cursor = conn.cursor()
    retry_after = 0
    try:
        for scope, identity, (limit, seconds) in scopes:
            key = hmac.new(
                current_app.secret_key.encode(),
                f'{endpoint}:{scope}:{identity}'.encode(),
                hashlib.sha256,
            ).hexdigest()
            # The upsert locks the bucket, so concurrent workers cannot lose increments.
            cursor.execute(
                '''INSERT INTO auth_rate_limits (bucket_key, attempts, expires_at)
                   VALUES (%s, 1, TIMESTAMPADD(SECOND, %s, UTC_TIMESTAMP()))
                   ON DUPLICATE KEY UPDATE
                       attempts = IF(expires_at <= UTC_TIMESTAMP(), 1, LEAST(attempts + 1, 1000000)),
                       expires_at = IF(expires_at <= UTC_TIMESTAMP(),
                           TIMESTAMPADD(SECOND, %s, UTC_TIMESTAMP()), expires_at)''',
                (key, seconds, seconds),
            )
            cursor.execute(
                '''SELECT attempts, GREATEST(1, TIMESTAMPDIFF(SECOND, UTC_TIMESTAMP(), expires_at))
                   FROM auth_rate_limits WHERE bucket_key = %s FOR UPDATE''', (key,)
            )
            attempts, remaining = cursor.fetchone()
            if attempts > limit:
                retry_after = max(retry_after, remaining)
        conn.commit()
        # Bounded housekeeping after releasing bucket locks.
        cursor.execute('DELETE FROM auth_rate_limits WHERE expires_at < UTC_TIMESTAMP() LIMIT 100')
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
    return retry_after
