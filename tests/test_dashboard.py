import unittest
from datetime import date
from dashboard import build_dashboard, validate_filters


def row(day, amount, category='food', kind='expense'):
    return dict(id=day, date=date.fromisoformat(day), amount=amount,
                category=category, type=kind, note='')


class DashboardTests(unittest.TestCase):
    def test_shared_filters_and_previous_month_baseline(self):
        rows = [row('2026-09-01', 30), row('2026-08-01', 20),
                row('2026-09-02', 100, 'salary', 'income'),
                row('2026-09-03', 10, 'travel')]
        data = build_dashboard(rows, month='2026-09', category='food', kind='expense')
        self.assertEqual(len(data['transactions']), 1)
        self.assertEqual(data['summary']['totals']['expense'], 30)
        self.assertEqual(data['summary']['by_month']['expense'], [30])
        self.assertEqual(data['summary']['by_category'][0]['total'], 30)
        self.assertEqual(data['insights']['month_comparison']['pct_change'], 50)
        self.assertEqual(data['category_options'], ['food', 'salary', 'travel'])

    def test_gap_is_zero_not_latest_nonempty_month(self):
        data = build_dashboard([row('2026-07-01', 100), row('2026-09-01', 20)], today=date(2026, 9, 13))
        comparison = data['insights']['month_comparison']
        self.assertEqual(comparison['previous_month'], '2026-08')
        self.assertEqual(comparison['previous_total'], 0)
        self.assertIsNone(comparison['pct_change'])

    def test_year_boundary_and_empty_month(self):
        data = build_dashboard([row('2025-12-31', 20)], month='2026-01')
        self.assertEqual(data['transactions'], [])
        self.assertEqual(data['insights']['month_comparison']['pct_change'], -100)
        self.assertEqual(data['insights']['month_comparison']['previous_month'], '2025-12')
        self.assertEqual(build_dashboard([], month='2026-01')['insights']['month_comparison']['pct_change'], 0)

    def test_income_filter_has_no_expense_insights(self):
        data = build_dashboard([row('2026-09-01', 20), row('2026-09-02', 100, kind='income')], kind='income')
        self.assertEqual(data['summary']['totals']['expense'], 0)
        self.assertEqual(data['summary']['by_category'], [])
        self.assertIsNone(data['insights']['month_comparison'])

    def test_invalid_filters(self):
        for month in ['2026-13', '2026-1', '0000-01', '2026-01-01']:
            with self.assertRaises(ValueError):
                validate_filters(month=month)
        with self.assertRaises(ValueError):
            validate_filters(kind='invalid')
