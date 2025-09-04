from django.db.models.signals import post_save
from django.dispatch import receiver
from finance.models import *

#
# @receiver(post_save, sender=Expense)
# def update_bank_balance_on_expense(sender, instance, created, **kwargs):
#     """Automatically deduct expense from bank balance when expense is recorded"""
#     if created:
#         # This is a simplified approach - in real world you'd specify which account
#         # For now, we'll use the first active account
#         try:
#             account = BankAccount.objects.filter(is_active=True).first()
#             if account:
#                 account.balance -= instance.amount
#                 account.save(update_fields=['balance'])
#         except Exception:
#             pass  # Handle gracefully in production
#
#
# @receiver(post_save, sender=Income)
# def update_bank_balance_on_income(sender, instance, created, **kwargs):
#     """Automatically add income to bank balance when income is recorded"""
#     if created:
#         try:
#             account = BankAccount.objects.filter(is_active=True).first()
#             if account:
#                 account.balance += instance.amount
#                 account.save(update_fields=['balance'])
#         except Exception:
#             pass
#
#
# @receiver(post_save, sender=SalaryRecord)
# def update_bank_balance_on_salary(sender, instance, created, **kwargs):
#     """Deduct salary payment from bank balance when marked as paid"""
#     if not created and instance.is_paid and instance.paid_date:
#         # Only process when salary is marked as paid
#         try:
#             account = BankAccount.objects.filter(is_active=True).first()
#             if account:
#                 account.balance -= instance.net_salary
#                 account.save(update_fields=['balance'])
#         except Exception:
#             pass