"""Run with: python -m flask --app app migrate-accounts / assign-legacy USERNAME."""
import click
from rate_limits import RATE_LIMIT_SQL

USERS_SQL = '''CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    recovery_hash CHAR(64) NOT NULL,
    auth_version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4'''


def register_commands(app, connect):
    @app.cli.command('migrate-accounts')
    def migrate_accounts():
        """Add accounts; legacy transactions remain unassigned and private."""
        conn = connect()
        cursor = conn.cursor()
        try:
            cursor.execute(USERS_SQL)
            cursor.execute(RATE_LIMIT_SQL)
            cursor.execute("SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'transactions' AND COLUMN_NAME = 'user_id'")
            if not cursor.fetchone()[0]:
                cursor.execute('ALTER TABLE transactions ADD COLUMN user_id INT NULL')
            cursor.execute("SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'transactions' AND INDEX_NAME = 'idx_transactions_user_date'")
            if not cursor.fetchone()[0]:
                cursor.execute('ALTER TABLE transactions ADD INDEX idx_transactions_user_date (user_id, date)')
            cursor.execute("SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA = DATABASE() AND TABLE_NAME = 'transactions' AND CONSTRAINT_NAME = 'fk_transactions_user'")
            if not cursor.fetchone()[0]:
                cursor.execute('ALTER TABLE transactions ADD CONSTRAINT fk_transactions_user FOREIGN KEY (user_id) REFERENCES users(id)')
            conn.commit()
            cursor.execute('SELECT COUNT(*) FROM transactions WHERE user_id IS NULL')
            click.echo(f'Migration complete. Unassigned legacy rows: {cursor.fetchone()[0]}')
        finally:
            cursor.close()
            conn.close()

    @app.cli.command('purge-auth-limits')
    def purge_auth_limits():
        """Remove expired rate-limit counters outside the login request path."""
        conn = connect()
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM auth_rate_limits WHERE expires_at < UTC_TIMESTAMP() LIMIT 10000')
            count = cursor.rowcount
            conn.commit()
            click.echo(f'Removed {count} expired counters.')
        finally:
            cursor.close()
            conn.close()

    @app.cli.command('assign-legacy')
    @click.argument('username')
    def assign_legacy(username):
        """Assign unowned legacy records to an explicitly selected registered user."""
        conn = connect()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT id FROM users WHERE username = %s', (username.lower(),))
            user = cursor.fetchone()
            if not user:
                raise click.ClickException('Account not found. Register the owner account first.')
            cursor.execute('UPDATE transactions SET user_id = %s WHERE user_id IS NULL', (user[0],))
            count = cursor.rowcount
            conn.commit()
            click.echo(f'Assigned {count} legacy records to {username}.')
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()
