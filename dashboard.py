"""Build dashboard sections from one consistent set of transactions."""
from collections import defaultdict
from decimal import Decimal
from datetime import date, datetime, timedelta, timezone
import re


def validate_filters(month='', category='', kind=''):
    if month and (not re.fullmatch(r'[1-9][0-9]{3}-(0[1-9]|1[0-2])', month)):
        raise ValueError('Invalid month; use YYYY-MM')
    if kind not in ('', 'income', 'expense'):
        raise ValueError('Invalid transaction type')
    if len(category) > 50:
        raise ValueError('Invalid category')


def build_dashboard(rows, month='', category='', kind='', today=None):
    validate_filters(month, category, kind)
    filter_kind = kind
    options = sorted({row['category'] for row in rows})
    matching = [row for row in rows if (not category or row['category'] == category)
                and (not kind or row['type'] == kind)]
    today = today or datetime.now(timezone(timedelta(hours=7))).date()
    reference = date.fromisoformat(month + '-01') if month else today.replace(day=1)
    previous_month = (reference - timedelta(days=1)).strftime('%Y-%m')
    current_month = reference.strftime('%Y-%m')
    expense_totals = defaultdict(lambda: Decimal(0))
    for row in matching:
        if row['type'] == 'expense':
            expense_totals[row['date'].strftime('%Y-%m')] += Decimal(str(row['amount']))
    rows = [row for row in matching if not month or row['date'].strftime('%Y-%m') == month]
    totals = {'income': Decimal(0), 'expense': Decimal(0)}
    categories = defaultdict(lambda: {'total': Decimal(0), 'count': 0})
    months = defaultdict(lambda: {'income': Decimal(0), 'expense': Decimal(0)})
    days = [Decimal(0) for _ in range(7)]
    transactions = []
    for row in rows:
        amount = Decimal(str(row['amount']))
        kind = row['type']
        month = row['date'].strftime('%Y-%m')
        totals[kind] += amount
        months[month][kind] += amount
        if kind == 'expense':
            categories[row['category']]['total'] += amount
            categories[row['category']]['count'] += 1
            days[row['date'].weekday()] += amount
        transactions.append({**row, 'amount': float(amount), 'date': row['date'].isoformat()})
    ranking = sorted(categories, key=lambda key: (-categories[key]['total'], key))
    labels = sorted(months)
    thai_days = ['จันทร์', 'อังคาร', 'พุธ', 'พฤหัสบดี', 'ศุกร์', 'เสาร์', 'อาทิตย์']
    busiest = max(range(7), key=lambda index: days[index])
    comparison = None
    if filter_kind != 'income':
        current, previous = expense_totals[current_month], expense_totals[previous_month]
        comparison = dict(
            current_month=current_month, previous_month=previous_month,
            current_total=float(current), previous_total=float(previous),
            pct_change=round(float((current - previous) / previous * 100), 1)
            if previous else (0 if not current else None),
        )
    return {
        'category_options': options,
        'transactions': transactions,
        'summary': {
            'totals': {**{key: float(value) for key, value in totals.items()}, 'balance': float(totals['income'] - totals['expense'])},
            'by_category': [{'category': key, 'total': float(categories[key]['total'])} for key in ranking],
            'by_month': {'labels': labels, **{kind: [float(months[month][kind]) for month in labels] for kind in totals}},
        },
        'insights': {
            'top_categories': [{'category': key, 'total': float(categories[key]['total']), 'count': categories[key]['count']} for key in ranking[:3]],
            'day_breakdown': [{'day': day, 'total': float(days[index])} for index, day in enumerate(thai_days)],
            'busiest_day': {'day': thai_days[busiest], 'total': float(days[busiest])} if any(days) else None,
            'month_comparison': comparison,
        },
    }
