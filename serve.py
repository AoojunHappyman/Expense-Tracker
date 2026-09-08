"""Production WSGI entrypoint behind a same-host Caddy reverse proxy."""
import os

# Set before importing the application: production refuses incomplete configuration.
os.environ['APP_ENV'] = 'production'

from waitress import serve
from app import app


if __name__ == '__main__':
    serve(
        app,
        listen='127.0.0.1:8080',
        threads=4,
        trusted_proxy='127.0.0.1',
        trusted_proxy_count=1,
        trusted_proxy_headers={'x-forwarded-for', 'x-forwarded-proto'},
        clear_untrusted_proxy_headers=True,
        expose_tracebacks=False,
        max_request_body_size=16384,
    )
