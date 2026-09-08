import os
import unittest
from unittest.mock import patch
from flask import Flask, session
from production import configure_runtime


class ProductionTests(unittest.TestCase):
    def make_app(self):
        app = Flask(__name__, template_folder='../templates')
        with patch.dict(os.environ, {'APP_ENV':'production','SECRET_KEY':'a'*64,'PUBLIC_URL':'https://expense.example.com'}):
            configure_runtime(app)
        @app.route('/session')
        def cookie():
            session['hello']='world'
            return 'ok'
        @app.route('/api/broken')
        @app.route('/broken')
        def broken():
            raise RuntimeError('secret-password database-host private-path')
        return app

    def test_production_refuses_bad_settings(self):
        for key, url in [('', 'https://example.com'), ('replace_with_a_random_secret','https://example.com'), ('a'*64,'http://example.com')]:
            with patch.dict(os.environ, {'APP_ENV':'production','SECRET_KEY':key,'PUBLIC_URL':url}):
                with self.assertRaises(RuntimeError):
                    configure_runtime(Flask(__name__))

    def test_https_host_and_cookie(self):
        app = self.make_app()
        app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')
        client=app.test_client()
        self.assertEqual(client.get('/session',base_url='http://expense.example.com').status_code,400)
        self.assertEqual(client.get('/session',base_url='https://evil.example').status_code,400)
        response=client.get('/session',base_url='https://expense.example.com')
        self.assertEqual(response.status_code,200)
        for value in ['__Host-expense_session=', 'Secure', 'HttpOnly', 'SameSite=Lax', 'Path=/']:
            self.assertIn(value,response.headers['Set-Cookie'])
        self.assertIn('max-age=',response.headers['Strict-Transport-Security'])
        self.assertEqual(response.headers['X-Frame-Options'],'DENY')

    def test_errors_do_not_disclose_details(self):
        app=self.make_app()
        client=app.test_client()
        with self.assertLogs(app.logger,level='ERROR') as logs:
            for path in ['/broken','/api/broken']:
                response=client.get(path,base_url='https://expense.example.com')
                self.assertEqual(response.status_code,500)
                self.assertNotIn('secret-password',response.text)
                self.assertNotIn('RuntimeError',response.text)
        self.assertNotIn('secret-password',' '.join(logs.output))
        response=client.get('/api/missing',base_url='https://expense.example.com')
        self.assertEqual(response.status_code,404)
        self.assertIn('error',response.get_json())
