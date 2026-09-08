"""Account sessions and one-time recovery codes."""
import hashlib
import os
import secrets
from contextlib import contextmanager
from datetime import timedelta

from flask import g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
import mysql.connector
from rate_limits import LIMITS, check_auth_limit


def init_auth(app, connect):
    app.config.update(
        SECRET_KEY=app.config.get('SECRET_KEY') or os.environ.get('SECRET_KEY') or secrets.token_hex(32),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=app.config.get('PRODUCTION', False) or os.environ.get('COOKIE_SECURE') == '1',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
        MAX_CONTENT_LENGTH=16384,
    )

    @contextmanager
    def database():
        conn = connect()
        cursor = conn.cursor(dictionary=True)
        try:
            yield conn, cursor
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def csrf_token():
        if 'csrf' not in session:
            session['csrf'] = secrets.token_urlsafe(32)
        return session['csrf']

    app.jinja_env.globals['csrf_token'] = csrf_token

    @app.before_request
    def protect():
        g.user = None
        if request.endpoint == 'static':
            return
        if session.get('user_id'):
            with database() as (_, cursor):
                cursor.execute('SELECT id, username, auth_version FROM users WHERE id = %s', (session['user_id'],))
                user = cursor.fetchone()
            if user and user['auth_version'] == session.get('auth_version'):
                g.user = user
            else:
                session.clear()
        if request.path.startswith('/api/') and not g.user:
            return jsonify(error='กรุณาเข้าสู่ระบบ'), 401
        if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
            token = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token', '')
            if not token or not secrets.compare_digest(token, session.get('csrf', '')):
                if request.path.startswith('/api/'):
                    return jsonify(error='เซสชันหมดอายุ กรุณารีเฟรชหน้า'), 400
                return render_template('auth.html', mode='login', error='เซสชันหมดอายุ กรุณาลองใหม่'), 400

        if request.method == 'POST' and request.endpoint in LIMITS:
            try:
                retry_after = check_auth_limit(connect, request.endpoint)
            except mysql.connector.Error:
                app.logger.error('Authentication rate-limit storage unavailable')
                return render_template('auth.html', mode=request.endpoint,
                                       error='ระบบเข้าสู่บัญชีไม่พร้อมใช้งานชั่วคราว กรุณาลองใหม่ภายหลัง'), 503
            if retry_after:
                response = app.make_response((render_template(
                    'auth.html', mode=request.endpoint,
                    error=f'ลองทำรายการบ่อยเกินไป กรุณารอ {(retry_after + 59) // 60} นาทีแล้วลองใหม่',
                ), 429))
                response.headers['Retry-After'] = str(retry_after)
                return response

    @app.after_request
    def no_private_cache(response):
        if request.endpoint != 'static':
            response.headers['Cache-Control'] = 'no-store'
        return response

    def credentials():
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')
        if not 3 <= len(username) <= 50 or not all(c in 'abcdefghijklmnopqrstuvwxyz0123456789_-' for c in username):
            raise ValueError('ชื่อผู้ใช้ต้องมี 3–50 ตัว ใช้ a–z, 0–9, _ หรือ -')
        if not 12 <= len(password) <= 128:
            raise ValueError('รหัสผ่านต้องมี 12–128 ตัวอักษร')
        return username, password

    def start_session(user_id, version):
        session.clear()
        session['user_id'] = user_id
        session['auth_version'] = version
        session.permanent = True
        csrf_token()

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'GET':
            return render_template('auth.html', mode='register')
        try:
            username, password = credentials()
            code = secrets.token_urlsafe(32)
            with database() as (conn, cursor):
                cursor.execute('INSERT INTO users (username, password_hash, recovery_hash) VALUES (%s, %s, %s)',
                               (username, generate_password_hash(password), hashlib.sha256(code.encode()).hexdigest()))
                user_id = cursor.lastrowid
                conn.commit()
            start_session(user_id, 1)
            return render_template('recovery_code.html', code=code)
        except ValueError as error:
            return render_template('auth.html', mode='register', error=str(error)), 400
        except mysql.connector.IntegrityError:
            return render_template('auth.html', mode='register', error='ชื่อผู้ใช้นี้ไม่สามารถใช้ได้'), 400

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'GET':
            return render_template('auth.html', mode='login')
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')
        with database() as (_, cursor):
            cursor.execute('SELECT id, password_hash, auth_version FROM users WHERE username = %s', (username,))
            user = cursor.fetchone()
        if user and len(password) <= 128 and check_password_hash(user['password_hash'], password):
            start_session(user['id'], user['auth_version'])
            return redirect(url_for('index'))
        return render_template('auth.html', mode='login', error='ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง'), 400

    @app.post('/logout')
    def logout():
        session.clear()
        return redirect(url_for('login'))

    @app.route('/recover', methods=['GET', 'POST'])
    def recover():
        if request.method == 'GET':
            return render_template('auth.html', mode='recover')
        try:
            username, password = credentials()
        except ValueError as error:
            return render_template('auth.html', mode='recover', error=str(error)), 400
        recovery_hash = hashlib.sha256(request.form.get('recovery_code', '').strip().encode()).hexdigest()
        code = secrets.token_urlsafe(32)
        with database() as (conn, cursor):
            cursor.execute('SELECT id, auth_version FROM users WHERE username = %s AND recovery_hash = %s FOR UPDATE',
                           (username, recovery_hash))
            user = cursor.fetchone()
            if not user:
                conn.rollback()
                return render_template('auth.html', mode='recover', error='ชื่อผู้ใช้หรือรหัสกู้บัญชีไม่ถูกต้อง'), 400
            cursor.execute('UPDATE users SET password_hash = %s, recovery_hash = %s, auth_version = auth_version + 1 WHERE id = %s',
                           (generate_password_hash(password), hashlib.sha256(code.encode()).hexdigest(), user['id']))
            conn.commit()
        start_session(user['id'], user['auth_version'] + 1)
        return render_template('recovery_code.html', code=code)
