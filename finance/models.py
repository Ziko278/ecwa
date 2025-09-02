from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models
from admin_site.model_info import TEMPORAL_STATUS, RECEIPT_FORMAT


class FinanceSettingModel(models.Model):
    default_receipt_format = models.CharField(max_length=50, choices=RECEIPT_FORMAT, blank=True, null=True)
    receipt_signature = models.FileField(upload_to='finance/setting/receipt', blank=True, null=True)


# -------------------- EXPENSE MANAGEMENT --------------------

class ExpenseCategory(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Expense Categories"


class Quotation(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('DEPT_PENDING', 'Department Pending'),
        ('DEPT_APPROVED', 'Department Approved'),
        ('DEPT_REJECTED', 'Department Rejected'),
        ('DEPT_QUERY', 'Department Query'),
        ('GENERAL_PENDING', 'General Pending'),
        ('GENERAL_APPROVED', 'General Approved'),
        ('GENERAL_REJECTED', 'General Rejected'),
        ('GENERAL_QUERY', 'General Query'),
        ('MONEY_COLLECTED', 'Money Collected'),
        ('CANCELLED', 'Cancelled'),
    ]

    quotation_number = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.ForeignKey(ExpenseCategory, on_delete=models.CASCADE)
    department = models.ForeignKey('human_resource.DepartmentModel', on_delete=models.CASCADE)
    requested_by = models.ForeignKey(User, related_name='quotations', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')

    # Department approval
    dept_reviewed_by = models.ForeignKey(User, related_name='dept_reviewed_quotations',
                                         on_delete=models.SET_NULL, null=True, blank=True)
    dept_reviewed_at = models.DateTimeField(null=True, blank=True)
    dept_comments = models.TextField(blank=True)

    # General approval
    general_reviewed_by = models.ForeignKey(User, related_name='general_reviewed_quotations',
                                            on_delete=models.SET_NULL, null=True, blank=True)
    general_reviewed_at = models.DateTimeField(null=True, blank=True)
    general_comments = models.TextField(blank=True)

    # Money collection
    collected_by = models.ForeignKey(User, related_name='collected_quotations',
                                     on_delete=models.SET_NULL, null=True, blank=True)
    collected_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.quotation_number} - {self.title}"

    class Meta:
        ordering = ['-created_at']


class Expense(models.Model):
    expense_number = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.CASCADE)
    department = models.ForeignKey('human_resource.DepartmentModel', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    paid_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    quotation = models.ForeignKey(Quotation, on_delete=models.SET_NULL, null=True, blank=True)  # Link if from quotation
    invoice_reference = models.CharField(max_length=200, blank=True)
    payment_method = models.CharField(max_length=50, blank=True)  # Cash, Bank Transfer, etc.
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.expense_number} - {self.title} - {self.amount}"

    class Meta:
        ordering = ['-date']


# -------------------- INCOME MANAGEMENT --------------------

class IncomeCategory(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Income Categories"


class Income(models.Model):
    income_number = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(IncomeCategory, on_delete=models.CASCADE)
    department = models.ForeignKey('human_resource.DepartmentModel', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    source = models.CharField(max_length=200, blank=True)  # Patient, Insurance, Government, etc.
    receipt_number = models.CharField(max_length=100, blank=True)
    payment_method = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.income_number} - {self.title} - {self.amount}"

    class Meta:
        ordering = ['-date']


# -------------------- SALARY MANAGEMENT --------------------

class StaffBankDetail(models.Model):
    staff = models.OneToOneField(User, related_name='bank_details', on_delete=models.CASCADE)
    bank_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=20)
    account_name = models.CharField(max_length=200)
    sort_code = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.staff.get_full_name()} - {self.bank_name}"


class SalaryStructure(models.Model):
    staff = models.OneToOneField(User, related_name='salary_structure', on_delete=models.CASCADE)
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2)
    housing_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    transport_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    medical_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    other_allowances = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))  # Percentage
    pension_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))  # Percentage
    effective_from = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def gross_salary(self):
        return (self.basic_salary + self.housing_allowance +
                self.transport_allowance + self.medical_allowance + self.other_allowances)

    @property
    def tax_amount(self):
        return self.gross_salary * (self.tax_rate / 100)

    @property
    def pension_amount(self):
        return self.basic_salary * (self.pension_rate / 100)

    @property
    def net_salary(self):
        return self.gross_salary - self.tax_amount - self.pension_amount

    def __str__(self):
        return f"{self.staff.get_full_name()} - {self.basic_salary}"


class SalaryRecord(models.Model):
    staff = models.ForeignKey(User, related_name='salary_records', on_delete=models.CASCADE)
    month = models.PositiveIntegerField()  # 1-12
    year = models.PositiveIntegerField()

    # Copy from salary structure for historical record
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2)
    housing_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    transport_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    medical_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    other_allowances = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    # Additional payments/deductions for this month
    bonus = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    overtime = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    deductions = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    # Calculated fields
    gross_salary = models.DecimalField(max_digits=12, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    pension_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    net_salary = models.DecimalField(max_digits=12, decimal_places=2)

    is_paid = models.BooleanField(default=False)
    paid_date = models.DateField(null=True, blank=True)
    paid_by = models.ForeignKey(User, related_name='processed_salaries',
                                on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Auto-calculate totals
        self.gross_salary = (self.basic_salary + self.housing_allowance +
                             self.transport_allowance + self.medical_allowance +
                             self.other_allowances + self.bonus + self.overtime)
        self.net_salary = self.gross_salary - self.tax_amount - self.pension_amount - self.deductions
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.staff.get_full_name()} - {self.month}/{self.year}"

    class Meta:
        unique_together = ['staff', 'month', 'year']
        ordering = ['-year', '-month']

