import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from app import app


class TransactionApiTests(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()
        self.valid = dict(type='expense', amount='10.25', category=' อาหาร ', note=' มื้อเช้า ', date='2026-09-08')
        self.connection = MagicMock()
        self.cursor = MagicMock()
        auth_cursor = MagicMock()
        auth_cursor.fetchone.return_value = {'id': 7, 'username': 'test_user', 'auth_version': 1}
        self.connection.cursor.side_effect = lambda **kw: auth_cursor if kw.get('dictionary') else self.cursor
        with self.client.session_transaction() as session:
            session['user_id'] = 7
            session['auth_version'] = 1
            session['csrf'] = 'test-csrf'
        self.client.environ_base['HTTP_X_CSRF_TOKEN'] = 'test-csrf'
        self.cursor.fetchone.return_value = (1,)
        self.cursor.lastrowid = 1
        self.db = patch('app.get_db_connection', return_value=self.connection)
        self.connect = self.db.start()
        self.addCleanup(self.db.stop)

    def send(self, method, payload):
        path = '/api/transactions' if method == 'POST' else '/api/transactions/1'
        return self.client.open(path, method=method, json=payload)

    def test_invalid_payloads_never_open_database(self):
        invalid = [None, [], 'text', 1, {}, {'amount': '10'}]
        for key, values in {
            'type': ['invalid', None, [], {}],
            'amount': [0, -1, True, None, [], {}, 'NaN', 'Infinity', '-Infinity', 'abc', '0.001', '100000000', '1e999999'],
            'category': ['', '   ', None, [], 'ก' * 51],
            'note': [None, {}, 'ก' * 256],
            'date': [None, 123, '2026-02-30', '2026-9-8', '20260908', '0999-01-01', '2026-09-08T00:00:00'],
        }.items():
            invalid.extend({**self.valid, key: value} for value in values)
        for method in ('POST', 'PUT'):
            for payload in invalid:
                with self.subTest(method=method, payload=payload):
                    response = self.send(method, payload)
                    self.assertEqual(response.status_code, 400)
                    self.assertIn('error', response.get_json())
        self.cursor.execute.assert_not_called()

    def test_malformed_json_returns_json_error(self):
        for method, path in [('POST', '/api/transactions'), ('PUT', '/api/transactions/1')]:
            response = self.client.open(path, method=method, data='{', content_type='application/json')
            self.assertEqual(response.status_code, 400)
            self.assertIn('error', response.get_json())
        self.cursor.execute.assert_not_called()

    def test_valid_create_and_update_preserve_decimal_and_trim_text(self):
        for method, status in [('POST', 201), ('PUT', 200)]:
            with self.subTest(method=method):
                response = self.send(method, self.valid)
                self.assertEqual(response.status_code, status)
                values = self.cursor.execute.call_args.args[1]
                self.assertEqual(values[:5], ('expense', Decimal('10.25'), 'อาหาร', 'มื้อเช้า', date(2026, 9, 8)))
        self.connection.commit.assert_called()
        self.cursor.close.assert_called()
        self.connection.close.assert_called()

    def test_amount_limits_and_leap_date(self):
        for amount in ['0.01', '99999999.99']:
            response = self.send('POST', {**self.valid, 'amount': amount, 'date': '2024-02-29'})
            self.assertEqual(response.status_code, 201)

    def test_unchanged_update_succeeds(self):
        self.cursor.rowcount = 0
        response = self.send('PUT', self.valid)
        self.assertEqual(response.status_code, 200)
        self.connection.commit.assert_called_once()

    def test_missing_update_is_404_without_update(self):
        self.cursor.fetchone.return_value = None
        response = self.send('PUT', self.valid)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.cursor.execute.call_count, 1)
        self.connection.commit.assert_not_called()
        self.connection.rollback.assert_called_once()
        self.assertEqual(self.connection.close.call_count, 2)

    def test_database_failure_rolls_back_and_closes(self):
        self.cursor.execute.side_effect = RuntimeError('database unavailable')
        for method in ['POST', 'PUT']:
            with self.assertRaises(RuntimeError):
                self.send(method, self.valid)
        self.assertEqual(self.connection.rollback.call_count, 2)
        self.assertEqual(self.cursor.close.call_count, 2)
        self.assertEqual(self.connection.close.call_count, 4)


if __name__ == '__main__':
    unittest.main()
