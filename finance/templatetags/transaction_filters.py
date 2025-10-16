# Save this as: templatetags/transaction_filters.py

from django import template
from decimal import Decimal

register = template.Library()


@register.filter(name='filter_by_type')
def filter_by_type(queryset, transaction_type):
    """
    Filter transactions by type
    Usage: {{ child_transactions|filter_by_type:'drug_payment' }}
    """
    if not queryset:
        return []
    return [t for t in queryset if t.transaction_type == transaction_type]


@register.filter(name='sum_amount')
def sum_amount(transactions):
    """
    Sum the amount field of a list of transactions
    Usage: {{ transactions|sum_amount }}
    """
    if not transactions:
        return Decimal('0.00')

    total = Decimal('0.00')
    for trans in transactions:
        if hasattr(trans, 'amount'):
            total += trans.amount

    return total


@register.filter(name='count_items')
def count_items(child_transactions):
    """
    Count total items in child transactions
    Usage: {{ child_transactions|count_items }}
    """
    if not child_transactions:
        return 0

    counts = {
        'drugs': 0,
        'labs': 0,
        'scans': 0,
        'services': 0
    }

    for trans in child_transactions:
        if trans.transaction_type == 'drug_payment':
            counts['drugs'] += 1
        elif trans.transaction_type == 'lab_payment':
            counts['labs'] += 1
        elif trans.transaction_type == 'scan_payment':
            counts['scans'] += 1
        elif trans.transaction_type == 'service':
            counts['services'] += 1

    return counts


@register.filter(name='get_item_type_badge')
def get_item_type_badge(transaction_type):
    """
    Get a Bootstrap badge class for transaction type
    Usage: {{ transaction.transaction_type|get_item_type_badge }}
    """
    badges = {
        'drug_payment': 'bg-primary',
        'lab_payment': 'bg-success',
        'scan_payment': 'bg-danger',
        'service': 'bg-warning',
        'direct_payment': 'bg-info',
        'wallet_funding': 'bg-success',
        'wallet_withdrawal': 'bg-danger',
    }
    return badges.get(transaction_type, 'bg-secondary')