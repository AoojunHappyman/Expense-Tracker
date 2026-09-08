"""Opt-in MySQL integration tests using a disposable, isolated database.
Run: $env:RUN_MYSQL_TESTS='1'; python -m unittest discover -s tests -v
"""
import os
import re
import secrets
import unittest
from pathlib import Path
from unittest.mock import patch

import mysql.connector
from werkzeug.security import check_password_hash
from app import app, DB_CONFIG


@unittest.skipUnless(os.getenv('RUN_MYSQL_TESTS') == '1', 'Requires local MySQL; creates an isolated test database')
class AccountIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_name = 'expense_test_' + secrets.token_hex(8)
        config = {k: v for k, v in DB_CONFIG.items() if k != 'database'}
        cls.admin = mysql.connector.connect(**config)
        cursor = cls.admin.cursor()
        cursor.execute(f'CREATE DATABASE `{cls.db_name}` CHARACTER SET utf8mb4')
        cls.config = {**config, 'database': cls.db_name}
        cls.db_patch = patch('app.get_db_connection', side_effect=lambda: mysql.connector.connect(**cls.config))
        cls.db_patch.start()
        conn = mysql.connector.connect(**cls.config)
        cur = conn.cursor()
        schema = Path('schema.sql').read_text(encoding='utf-8')
        # Only create tables; never run the application database selection.
        schema = schema[schema.index('CREATE TABLE'):]
        for statement in schema.split(';'):
            if statement.strip():
                cur.execute(statement)
        conn.commit()
        cur.close()
        conn.close()
        cursor.close()
        app.config['TESTING'] = True

    @classmethod
    def tearDownClass(cls):
        cls.db_patch.stop()
        assert re.fullmatch(r'expense_test_[0-9a-f]{16}', cls.db_name)
        cursor = cls.admin.cursor()
        cursor.execute(f'DROP DATABASE `{cls.db_name}`')
        cursor.close()
        cls.admin.close()

    def setUp(self):
        conn = mysql.connector.connect(**self.config)
        cur = conn.cursor()
        cur.execute('DELETE FROM auth_rate_limits')
        conn.commit()
        cur.close()
        conn.close()

    def test_login_limit_survives_sessions_and_forwarded_headers(self):
        for attempt in range(11):
            client = app.test_client()
            client.get('/login')
            response = client.post('/login', data={
                'username': ' Shared_User ', 'password': 'wrong', 'csrf_token': self.csrf(client),
            }, environ_overrides={'REMOTE_ADDR': f'192.0.2.{attempt + 1}'},
                headers={'X-Forwarded-For': f'198.51.100.{attempt + 1}'})
            self.assertEqual(response.status_code, 400 if attempt < 10 else 429)
        self.assertGreater(int(response.headers['Retry-After']), 0)
        self.assertIn('no-store', response.headers['Cache-Control'])
        # Expire the stored window without sleeping.
        conn = mysql.connector.connect(**self.config)
        cur = conn.cursor()
        cur.execute('UPDATE auth_rate_limits SET expires_at = UTC_TIMESTAMP() - INTERVAL 1 SECOND')
        conn.commit()
        cur.close()
        conn.close()
        self.assertEqual(client.post('/login', data={'username':'shared_user','password':'wrong','csrf_token':self.csrf(client)}).status_code, 400)

    def test_ip_limit_blocks_rotating_usernames_and_forged_headers(self):
        client = app.test_client()
        client.get('/login')
        for attempt in range(31):
            response = client.post('/login', data={
                'username': f'unknown_{attempt}', 'password':'wrong', 'csrf_token':self.csrf(client),
            }, headers={'X-Forwarded-For':f'198.51.100.{attempt + 1}'})
            self.assertEqual(response.status_code,400 if attempt < 30 else 429)
        self.assertEqual(client.get('/login').status_code,200)

    def test_register_and_recover_limits_are_independent(self):
        client = app.test_client()
        client.get('/register')
        for attempt in range(6):
            response = client.post('/register',data={'username':'bad','password':'short','csrf_token':self.csrf(client)})
            self.assertEqual(response.status_code,400 if attempt < 5 else 429)
        for attempt in range(6):
            response = client.post('/recover',data={'username':'unknown','password':'long-enough-password','recovery_code':'wrong','csrf_token':self.csrf(client)})
            self.assertEqual(response.status_code,400 if attempt < 5 else 429)
        self.assertEqual(client.post('/login',data={'username':'unknown','password':'wrong','csrf_token':self.csrf(client)}).status_code,400)

    def test_concurrent_requests_cannot_bypass_limit(self):
        from concurrent.futures import ThreadPoolExecutor
        from rate_limits import check_auth_limit
        def attempt(_):
            with app.test_request_context('/login',method='POST',data={'username':'parallel_user'}):
                return check_auth_limit(lambda: mysql.connector.connect(**self.config),'login')
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(attempt,range(14)))
        self.assertEqual(sum(result == 0 for result in results),10)
        self.assertEqual(sum(result > 0 for result in results),4)

    def csrf(self, client):
        with client.session_transaction() as session:
            return session['csrf']

    def register(self):
        client = app.test_client()
        name = 'u_' + secrets.token_hex(6)
        client.get('/register')
        response = client.post('/register', data={'username': name, 'password': 'long-test-password', 'csrf_token': self.csrf(client)})
        self.assertEqual(response.status_code, 200)
        code = re.search(r'<code class="recovery-code">([^<]+)</code>', response.text).group(1)
        return client, name, code

    def transaction(self, client, amount):
        payload = dict(type='expense', amount=str(amount), category='อาหาร', note='', date='2026-09-08', user_id=999)
        response = client.post('/api/transactions', json=payload, headers={'X-CSRF-Token': self.csrf(client)})
        self.assertEqual(response.status_code, 201)
        return response.get_json()['id'], payload

    def test_auth_and_cross_account_isolation(self):
        anonymous = app.test_client()
        for method, path in [('GET','/api/transactions'),('POST','/api/transactions'),('PUT','/api/transactions/1'),('DELETE','/api/transactions/1'),('GET','/api/summary'),('GET','/api/insights')]:
            self.assertEqual(anonymous.open(path, method=method).status_code, 401)
        self.assertEqual(anonymous.get('/').status_code, 302)
        a, _, _ = self.register()
        b, _, _ = self.register()
        aid, payload = self.transaction(a, 12.34)
        bid, _ = self.transaction(b, 98.76)
        for client, own, other, amount in [(a, aid, bid, 12.34), (b, bid, aid, 98.76)]:
            self.assertEqual([r['id'] for r in client.get('/api/transactions').get_json()], [own])
            summary = client.get('/api/summary')
            self.assertEqual(summary.status_code, 200)
            self.assertEqual(summary.get_json()['totals']['expense'], amount)
            self.assertEqual(summary.get_json()['by_category'][0]['total'], amount)
            self.assertEqual(summary.get_json()['by_month']['expense'], [amount])
            insights = client.get('/api/insights')
            self.assertEqual(insights.status_code, 200)
            self.assertEqual(insights.get_json()['top_categories'][0]['total'], amount)
            self.assertEqual(insights.get_json()['busiest_day']['total'], amount)
            for method in ['PUT','DELETE']:
                response = client.open(f'/api/transactions/{other}', method=method, json=payload, headers={'X-CSRF-Token': self.csrf(client)})
                self.assertEqual(response.status_code, 404)
        self.assertEqual(a.put(f'/api/transactions/{aid}', json=payload, headers={'X-CSRF-Token':self.csrf(a)}).status_code, 200)
        self.assertEqual(a.delete(f'/api/transactions/{aid}').status_code, 400)
        self.assertEqual(a.delete(f'/api/transactions/{aid}',headers={'X-CSRF-Token':self.csrf(a)}).status_code, 200)
        self.assertEqual(len(b.get('/api/transactions').get_json()), 1)

    def test_login_logout_and_single_use_recovery(self):
        original, name, code = self.register()
        other = app.test_client()
        other.get('/login')
        self.assertEqual(other.post('/login', data={'username':name,'password':'wrong','csrf_token':self.csrf(other)}).status_code,400)
        self.assertEqual(other.post('/login', data={'username':name,'password':'long-test-password','csrf_token':self.csrf(other)}).status_code,302)
        recover = app.test_client()
        recover.get('/recover')
        response = recover.post('/recover', data={'username':name,'password':'new-test-password','recovery_code':code,'csrf_token':self.csrf(recover)})
        self.assertEqual(response.status_code,200)
        new_code = re.search(r'<code class="recovery-code">([^<]+)</code>',response.text).group(1)
        self.assertNotEqual(new_code,code)
        self.assertEqual(original.get('/api/transactions').status_code,401)
        self.assertEqual(other.get('/api/transactions').status_code,401)
        self.assertEqual(recover.post('/recover',data={'username':name,'password':'another-password','recovery_code':code,'csrf_token':self.csrf(recover)}).status_code,400)
        self.assertEqual(recover.post('/logout',data={'csrf_token':self.csrf(recover)}).status_code,302)
        self.assertEqual(recover.get('/api/transactions').status_code,401)
        recover.get('/login')
        self.assertEqual(recover.post('/login',data={'username':name,'password':'new-test-password','csrf_token':self.csrf(recover)}).status_code,302)
        conn = mysql.connector.connect(**self.config)
        cur=conn.cursor(dictionary=True)
        cur.execute('SELECT password_hash, recovery_hash FROM users WHERE username = %s',(name,))
        row=cur.fetchone()
        self.assertTrue(check_password_hash(row['password_hash'],'new-test-password'))
        self.assertNotEqual(row['recovery_hash'],new_code)
        cur.close()
        conn.close()

    def test_duplicate_registration_and_csrf(self):
        _, name, _ = self.register()
        client=app.test_client()
        client.get('/register')
        self.assertEqual(client.post('/register',data={'username':name,'password':'long-test-password'}).status_code,400)
        self.assertEqual(client.post('/register',data={'username':name,'password':'long-test-password','csrf_token':self.csrf(client)}).status_code,400)
        self.assertEqual(client.get('/api/transactions').status_code,401)
