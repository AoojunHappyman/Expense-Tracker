"""Build dashboard sections from one consistent set of transactions."""
from collections import defaultdict
from decimal import Decimal


def build_dashboard(rows):
    totals = {'income': Decimal(0), 'expense': Decimal(0)}
    categories = defaultdict(lambda: {'total': Decimal(0), 'count': 0})
    months = defaultdict(lambda: {'income': Decimal(0), 'expense': Decimal(0)})
    expense_months = set()
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
            expense_months.add(month)
        transactions.append({**row, 'amount': float(amount), 'date': row['date'].isoformat()})
    ranking = sorted(categories, key=lambda key: (-categories[key]['total'], key))
    labels = sorted(months)
    thai_days = ['จันทร์', 'อังคาร', 'พุธ', 'พฤหัสบดี', 'ศุกร์', 'เสาร์', 'อาทิตย์']
    busiest = max(range(7), key=lambda index: days[index])
    comparison = None
    latest = sorted(expense_months, reverse=True)[:2]
    if len(latest) == 2:
        current, previous = (months[month]['expense'] for month in latest)
        comparison = dict(current_month=latest[0], current_total=float(current), previous_total=float(previous),
                          pct_change=round(float((current - previous) / previous * 100), 1) if previous else 0)
    return {
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
