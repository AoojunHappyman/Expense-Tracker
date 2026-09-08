"""Render-only entrypoint. TLS terminates at Render's managed ingress."""
import os
from pathlib import Path

if os.getenv('RENDER') != 'true':
    raise RuntimeError('Use serve_render.py only inside Render')
os.environ['APP_ENV'] = 'production'

from waitress import serve
from app import app, get_db_connection


def initialize_tables():
    # Add empty tables to the selected database; never copy local users or data.
    schema = Path(__file__).with_name('schema.sql').read_text(encoding='utf-8')
    schema = schema[schema.index('CREATE TABLE'):]
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        for statement in schema.split(';'):
            if statement.strip():
                cursor.execute(statement)
        conn.commit()
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    if os.getenv('INIT_DB') == '1':
        initialize_tables()
    serve(
        app,
        listen=f"0.0.0.0:{int(os.getenv('PORT', '10000'))}",
        threads=4,
        trusted_proxy='*',
        trusted_proxy_count=1,
        trusted_proxy_headers={'x-forwarded-for', 'x-forwarded-proto'},
        clear_untrusted_proxy_headers=True,
        expose_tracebacks=False,
        max_request_body_size=16384,
    )
