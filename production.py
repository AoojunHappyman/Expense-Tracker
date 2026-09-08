"""Production configuration, response headers, and public error responses."""
import os
import secrets
from urllib.parse import urlsplit

from flask import jsonify, render_template, request, abort
from werkzeug.exceptions import HTTPException


def configure_runtime(app):
    production = os.getenv('APP_ENV', 'development') == 'production'
    app.config['PRODUCTION'] = production
    app.config['DEBUG'] = False
    app.config['PROPAGATE_EXCEPTIONS'] = False if production else None
    if production:
        key = os.getenv('SECRET_KEY', '')
        if len(key) < 32 or key.startswith(('replace_', 'your_')):
            raise RuntimeError('Production requires a random SECRET_KEY of at least 32 characters')
        origin = urlsplit(os.getenv('PUBLIC_URL') or os.getenv('RENDER_EXTERNAL_URL', ''))
        if origin.scheme != 'https' or not origin.hostname or origin.username or origin.password or origin.path not in ('', '/') or origin.query or origin.fragment:
            raise RuntimeError('Production requires PUBLIC_URL=https://your-domain')
        app.config['PUBLIC_HOST'] = origin.netloc.lower()
        app.config['SECRET_KEY'] = key
        app.config['SESSION_COOKIE_SECURE'] = True
        app.config['SESSION_COOKIE_NAME'] = '__Host-expense_session'
        app.config['SESSION_COOKIE_PATH'] = '/'
        app.config['SESSION_COOKIE_DOMAIN'] = None

    @app.before_request
    def check_public_origin():
        if app.config['PRODUCTION']:
            if request.host.lower() != app.config['PUBLIC_HOST'] or not request.is_secure:
                abort(400)

    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        if app.config['PRODUCTION'] and request.is_secure:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response

    @app.errorhandler(HTTPException)
    def http_error(error):
        message = {
            400: 'คำขอไม่ถูกต้อง กรุณารีเฟรชหน้าแล้วลองใหม่',
            404: 'ไม่พบหน้าที่คุณต้องการ',
            405: 'ไม่รองรับวิธีเรียกใช้งานนี้',
            413: 'ข้อมูลที่ส่งมีขนาดใหญ่เกินไป',
        }.get(error.code, 'ไม่สามารถทำรายการได้ กรุณาลองใหม่')
        response = error.get_response()
        if request.path.startswith('/api/'):
            response.set_data(app.json.dumps({'error': message}))
            response.content_type = 'application/json'
        else:
            response.set_data(render_template('error.html', status=error.code, message=message))
            response.content_type = 'text/html; charset=utf-8'
        return response

    @app.errorhandler(Exception)
    def unexpected_error(error):
        reference = secrets.token_hex(8)
        # Do not log request bodies, passwords, connection strings or exception messages.
        app.logger.error('Unhandled error reference=%s type=%s endpoint=%s',
                         reference, type(error).__name__, request.endpoint)
        message = 'ระบบขัดข้องชั่วคราว กรุณาลองใหม่ภายหลัง'
        if request.path.startswith('/api/'):
            return jsonify(error=message, reference=reference), 500
        return render_template('error.html', status=500, message=message, reference=reference), 500
