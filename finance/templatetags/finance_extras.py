# finance/templatetags/finance_extras.py

from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def currency(value):
    """Format a number as currency with Naira symbol"""
    if value is None:
        return "₦0.00"
    try:
        # Convert to decimal for precision
        decimal_value = Decimal(str(value))
        # Format with commas and 2 decimal places
        formatted = "{:,.2f}".format(decimal_value)
        return f"₦{formatted}"
    except (TypeError, ValueError, Decimal.InvalidOperation):
        return "₦0.00"

@register.filter
def percentage(value, total):
    """Calculate percentage of value from total"""
    if not total or total == 0:
        return "0%"
    try:
        percentage = (Decimal(str(value)) / Decimal(str(total))) * 100
        return f"{percentage:.1f}%"
    except (TypeError, ValueError, Decimal.InvalidOperation, ZeroDivisionError):
        return "0%"

@register.filter
def abs_value(value):
    """Return absolute value"""
    try:
        return abs(Decimal(str(value)))
    except (TypeError, ValueError, Decimal.InvalidOperation):
        return 0

@register.filter
def multiply(value, multiplier):
    """Multiply value by multiplier"""
    try:
        return Decimal(str(value)) * Decimal(str(multiplier))
    except (TypeError, ValueError, Decimal.InvalidOperation):
        return 0

@register.filter
def divide(value, divisor):
    """Divide value by divisor"""
    try:
        if divisor == 0:
            return 0
        return Decimal(str(value)) / Decimal(str(divisor))
    except (TypeError, ValueError, Decimal.InvalidOperation, ZeroDivisionError):
        return 0

@register.simple_tag
def transaction_badge_class(transaction_type):
    """Return appropriate Bootstrap badge class for transaction type"""
    badge_classes = {
        'wallet_funding': 'bg-success',
        'consultation_payment': 'bg-primary',
        'drug_payment': 'bg-info',
        'lab_payment': 'bg-warning',
        'scan_payment': 'bg-secondary',
        'drug_refund': 'bg-success',
        'lab_refund': 'bg-success',
        'scan_refund': 'bg-success',
        'wallet_withdrawal': 'bg-danger',
    }
    return badge_classes.get(transaction_type, 'bg-secondary')

@register.simple_tag
def status_badge_class(status):
    """Return appropriate Bootstrap badge class for status"""
    status_classes = {
        'completed': 'bg-success',
        'pending': 'bg-warning',
        'failed': 'bg-danger',
        'cancelled': 'bg-secondary',
        'PENDING': 'bg-warning',
        'APPROVED': 'bg-success',
        'DISCREPANCY': 'bg-danger',
    }
    return status_classes.get(status, 'bg-secondary')

@register.filter
def replace(value, args):
    """Replace characters in string. Usage: {{ value|replace:"_,' '" }}"""
    try:
        old, new = args.split(',', 1)  # Split only on first comma
        return str(value).replace(old, new)
    except (ValueError, AttributeError):
        return value

@register.filter
def format_transaction_type(value):
    """Format transaction type for display"""
    if not value:
        return ""
    # Replace underscores with spaces and title case
    return str(value).replace('_', ' ').title()

# Create empty __init__.py file in templatetags directory
# finance/templatetags/__init__.py
# (empty file)