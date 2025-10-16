from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.timezone import now

from admin_site.model_info import TEMPORAL_STATUS, RECEIPT_FORMAT
from human_resource.models import StaffModel


class FinanceSettingModel(models.Model):
    minimum_funding = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )

    maximum_funding = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('500000.00'),
        help_text="The maximum amount a patient can fund their wallet with in one transaction."
    )
    allow_negative_balance = models.BooleanField(
        default=False,
        help_text="If True, patients can have a negative wallet balance (post-paid). If False, payments will fail if balance is insufficient."
    )


class ExpenseCategory(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Expense Categories"


class OtherPaymentService(models.Model):
    """Services not covered by main modules that patients can pay for"""
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, null=True)
    category = models.CharField(
        max_length=50,
        choices=[
            ('medical_services', 'Medical Services'),
            ('diagnostic_services', 'Diagnostic Services'),
            ('documents', 'Medical Documents'),
            ('equipment_rental', 'Equipment Rental'),
            ('facility_services', 'Facility Services'),
            ('professional_fees', 'Professional Fees'),
            ('other', 'Other'),
        ]
    )
    default_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Default amount (can be overridden during payment)"
    )
    is_fixed_amount = models.BooleanField(
        default=False,
        help_text="If true, amount cannot be changed during payment"
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['category', 'name']

    def __str__(self):
        return self.name


class WalletWithdrawalRecord(models.Model):
    """Record of money withdrawn from the patient wallet"""
    patient = models.ForeignKey(
        'patient.PatientModel',
        on_delete=models.CASCADE,
        related_name='withdrawals'
    )
    transaction = models.OneToOneField(
        'PatientTransactionModel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Link to the corresponding OUT transaction record"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    withdrawn_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wallet_withdrawals_processed'
    )
    withdrawal_date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-withdrawal_date']
        verbose_name = "Wallet Withdrawal Record"

    def __str__(self):
        return f"Withdrawal of ₦{self.amount} for {self.patient}"


class PatientTransactionModel(models.Model):
    patient = models.ForeignKey('patient.PatientModel', on_delete=models.SET_NULL, null=True)

    TRANSACTION_TYPE = (
        ('wallet_funding', 'WALLET FUNDING'),
        ('consultation_payment', 'CONSULTATION PAYMENT'),
        ('drug_payment', 'DRUG PAYMENT'),
        ('lab_payment', 'LAB PAYMENT'),
        ('scan_payment', 'SCAN PAYMENT'),
        ('admission_payment', 'ADMISSION PAYMENT'),
        ('surgery_payment', 'SURGERY PAYMENT'),
        ('service', 'SERVICE'),
        ('item', 'ITEM PURCHASE'),
        ('other_payment', 'OTHER PAYMENT'),
        ('drug_refund', 'DRUG REFUND'),
        ('lab_refund', 'LAB REFUND'),
        ('scan_refund', 'SCAN REFUND'),
        ('admission_refund', 'ADMISSION REFUND'),
        ('surgery_refund', 'SURGERY REFUND'),
        ('other_refund', 'OTHER REFUND'),
        ('wallet_withdrawal', 'WALLET WITHDRAWAL'),
        ('refund_to_wallet', 'REFUND TO WALLET'),
        ('wallet_correction', 'WALLET CORRECTION'),
        ('direct_payment', 'DIRECT PAYMENT'),  # NEW: For parent multi-payment transactions
    )

    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE)
    transaction_direction = models.CharField(max_length=20, choices=(('in', 'IN'), ('out', 'OUT')))

    # Related service records
    fee_structure = models.ForeignKey('consultation.ConsultationFeeModel', on_delete=models.SET_NULL, null=True,
                                      blank=True)
    lab_structure = models.ForeignKey('laboratory.LabTestOrderModel', on_delete=models.SET_NULL, null=True,
                                      blank=True)
    admission = models.ForeignKey('inpatient.Admission', on_delete=models.SET_NULL, null=True, blank=True)
    surgery = models.ForeignKey('inpatient.Surgery', on_delete=models.SET_NULL, null=True, blank=True)
    service = models.ForeignKey('service.PatientServiceTransaction', on_delete=models.SET_NULL, null=True,
                                blank=True)
    other_service = models.ForeignKey(OtherPaymentService, on_delete=models.SET_NULL, null=True, blank=True)
    drug_order = models.ForeignKey('pharmacy.DrugOrderModel', on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='transactions')

    scan_order = models.ForeignKey('scan.ScanOrderModel', on_delete=models.SET_NULL, null=True,  blank=True,  related_name='transactions')
    # NEW FIELDS
    parent_transaction = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='child_transactions',
        help_text="Links child transactions to parent payment transaction"
    )

    wallet_amount_used = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Amount deducted from wallet for this transaction (for mixed payments)"
    )

    direct_payment_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Amount paid directly (cash/card/transfer) for this transaction"
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    old_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    new_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    date = models.DateField()
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    transaction_id = models.CharField(max_length=100, blank=True, db_index=True)
    payment_method = models.CharField(max_length=50, blank=True)

    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'PENDING'),
            ('completed', 'COMPLETED'),
            ('failed', 'FAILED'),
            ('cancelled', 'CANCELLED')
        ],
        default='completed'
    )

    remittance = models.ForeignKey(
        'MoneyRemittance',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions'
    )
    valid_till = models.DateField(
        null=True,
        blank=True,
        help_text="The date until which the paid service is valid (e.g., for consultations)."
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.transaction_id:
            from django.db import transaction
            from django.db.models import Max
            from django.db.models.functions import Cast, Right
            from django.db.models import IntegerField
            import time
            import random

            today_str = date.today().strftime('%Y%m%d')
            max_retries = 5
            retry_count = 0

            while retry_count < max_retries:
                try:
                    with transaction.atomic():
                        # Use select_for_update to lock the query and prevent race conditions
                        # Alternative approach using Max aggregation for better performance
                        last_transaction_data = PatientTransactionModel.objects.filter(
                            transaction_id__startswith=f'trn-{today_str}'
                        ).aggregate(
                            max_id=Max(
                                Cast(
                                    Right('transaction_id', 4),
                                    IntegerField()
                                )
                            )
                        )

                        last_number = last_transaction_data['max_id'] or 0
                        new_number = last_number + 1

                        # Format the number with leading zeros
                        formatted_number = f"{new_number:04}"
                        potential_transaction_id = f"trn-{today_str}{formatted_number}"

                        # Double-check uniqueness (extra safety)
                        if PatientTransactionModel.objects.filter(
                                transaction_id=potential_transaction_id
                        ).exists():
                            # If somehow this ID exists, increment and try again
                            new_number += 1
                            formatted_number = f"{new_number:04}"
                            potential_transaction_id = f"trn-{today_str}{formatted_number}"

                        self.transaction_id = potential_transaction_id
                        break

                except Exception as e:
                    retry_count += 1
                    if retry_count >= max_retries:
                        # Fallback: use timestamp with random suffix if all retries fail
                        import uuid
                        timestamp = int(time.time() * 1000)  # milliseconds
                        random_suffix = str(uuid.uuid4())[:4]
                        self.transaction_id = f"trn-{today_str}{timestamp}{random_suffix}"
                        break
                    else:
                        # Wait briefly before retry with some jitter
                        time.sleep(0.01 + random.uniform(0, 0.02))
                        continue

        super().save(*args, **kwargs)

    def clean(self):
        """Validate transaction direction based on type"""
        funding_types = ['wallet_funding', 'refund_to_wallet']
        payment_types = [
            'consultation_payment', 'drug_payment', 'lab_payment',
            'scan_payment', 'admission_payment', 'surgery_payment', 'other_payment'
        ]
        refund_types = [
            'drug_refund', 'lab_refund', 'scan_refund',
            'admission_refund', 'surgery_refund', 'other_refund', 'wallet_withdrawal'
        ]
        withdrawal_types = ['wallet_withdrawal']

        if self.transaction_type in funding_types and self.transaction_direction != 'in':
            raise ValidationError('Funding transactions must be "in" direction')
        elif self.transaction_type in (payment_types + withdrawal_types) and self.transaction_direction != 'out':
            raise ValidationError('Payment/withdrawal transactions must be "out" direction')
        elif self.transaction_type in refund_types and self.transaction_direction != 'in':
            raise ValidationError('Refund transactions must be "in" direction')

    def __str__(self):
        return f"{self.get_transaction_type_display()}"

    @property
    def is_credit(self):
        return self.transaction_direction == 'in'

    @property
    def is_debit(self):
        return self.transaction_direction == 'out'

    @property
    def is_parent_transaction(self):
        """Check if this is a parent transaction with children"""
        return self.parent_transaction is None and self.child_transactions.exists()

    @property
    def is_child_transaction(self):
        """Check if this is a child transaction"""
        return self.parent_transaction is not None

    @property
    def is_standalone_transaction(self):
        """Check if this is a standalone transaction (old style)"""
        return self.parent_transaction is None and not self.child_transactions.exists()

    @property
    def total_items_count(self):
        """Get total count of items in this transaction"""
        if self.is_parent_transaction:
            return self.child_transactions.count()
        return 1 if self.is_standalone_transaction else 0

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['patient', 'transaction_type']),
            models.Index(fields=['date']),
            models.Index(fields=['status']),
            models.Index(fields=['parent_transaction']),  # NEW INDEX
        ]


class PatientRefundModel(models.Model):
    patient = models.ForeignKey('patient.PatientModel', on_delete=models.SET_NULL, null=True)


class MoneyRemittance(models.Model):
    """
    Represents a batch of funds remitted by a staff member to the finance department.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('DISCREPANCY', 'Discrepancy Noted'),
    ]

    remittance_id = models.CharField(max_length=50, unique=True, blank=True)
    remitted_by = models.ForeignKey(User, related_name='remittances_made', on_delete=models.PROTECT)
    approved_by = models.ForeignKey(User, related_name='remittances_approved', on_delete=models.SET_NULL, null=True,
                                    blank=True)

    total_cash_expected = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_transfer_expected = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_remitted_cash = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text="The actual amount of cash being handed over."
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    notes = models.TextField(blank=True, help_text="Notes explaining any discrepancy or details about the remittance.")

    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.remittance_id:
            today_str = self.created_at.strftime('%Y%m%d') if self.created_at else datetime.now().strftime('%Y%m%d')
            prefix = f'REM-{today_str}'
            last_remit = MoneyRemittance.objects.filter(remittance_id__startswith=prefix).order_by(
                'remittance_id').last()

            if last_remit:
                last_num = int(last_remit.remittance_id[-3:])
                new_num = last_num + 1
            else:
                new_num = 1

            self.remittance_id = f'{prefix}-{new_num:03d}'
        super().save(*args, **kwargs)

    @property
    def cash_discrepancy(self):
        return self.total_cash_expected - self.amount_remitted_cash

    def __str__(self):
        return f"Remittance {self.remittance_id} by {self.remitted_by.username}"


class Expense(models.Model):
    expense_number = models.CharField(max_length=50, unique=True, blank=True)  # Now optional at the form level
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.CASCADE)
    department = models.ForeignKey('human_resource.DepartmentModel', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    paid_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    invoice_reference = models.CharField(max_length=200, blank=True)
    payment_method = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def save(self, *args, **kwargs):
        if not self.expense_number:
            # Generate a unique number based on the date and an incrementing count
            today_str = now().strftime('%Y%m%d')
            prefix = f'EXP-{today_str}'
            last_expense = Expense.objects.filter(expense_number__startswith=prefix).order_by('expense_number').last()

            if last_expense:
                last_num = int(last_expense.expense_number[-3:])
                new_num = last_num + 1
            else:
                new_num = 1

            self.expense_number = f'{prefix}-{new_num:03d}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.expense_number} - {self.title} - {self.amount}"


class IncomeCategory(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Income Categories"


class Income(models.Model):
    income_number = models.CharField(max_length=50, unique=True, blank=True)  # Allow it to be blank initially
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey('IncomeCategory', on_delete=models.CASCADE)
    department = models.ForeignKey('human_resource.DepartmentModel', on_delete=models.CASCADE, blank=True, null=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField(default=now)
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    source = models.CharField(max_length=200, blank=True)
    receipt_number = models.CharField(max_length=100, blank=True)
    payment_method = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def save(self, *args, **kwargs):
        if not self.income_number:
            # Generate a unique number based on the date and an incrementing count for that day
            today_str = now().strftime('%Y%m%d')
            prefix = f'INC-{today_str}'
            last_income = Income.objects.filter(income_number__startswith=prefix).order_by('income_number').last()

            if last_income:
                last_num = int(last_income.income_number[-3:])
                new_num = last_num + 1
            else:
                new_num = 1

            self.income_number = f'{prefix}-{new_num:03d}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.income_number} - {self.title} - {self.amount}"


# -------------------- SALARY MANAGEMENT --------------------

class StaffBankDetail(models.Model):
    staff = models.OneToOneField(StaffModel, related_name='bank_details', on_delete=models.CASCADE)
    bank_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=20)
    account_name = models.CharField(max_length=200)
    sort_code = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.staff.__str__()} - {self.bank_name}"


class SalaryStructure(models.Model):
    staff = models.OneToOneField(StaffModel, related_name='salary_structure', on_delete=models.CASCADE)
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

    @property
    def total_deductions(self):
        """Calculates the sum of all deductions."""
        return self.tax_amount + self.pension_amount

    def __str__(self):
        return f"{self.staff.get_full_name()} - {self.basic_salary}"


class SalaryRecord(models.Model):
    staff = models.ForeignKey(StaffModel, on_delete=models.CASCADE)
    month = models.PositiveIntegerField()
    year = models.PositiveIntegerField()

    # Fields populated from SalaryStructure
    basic_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    housing_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    transport_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    medical_allowance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_allowances = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # --- NEW EDITABLE FIELDS ---
    bonus = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                help_text="Any additional bonus for this month.")
    other_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                           help_text="e.g., salary advance, loan repayment")
    notes = models.CharField(max_length=255, blank=True, help_text="Optional notes for this payslip.")

    # Fields for deductions (can still be auto-populated)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    pension_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Payment Tracking
    is_paid = models.BooleanField(default=False)
    paid_date = models.DateField(null=True, blank=True)
    paid_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    # --- NEW FIELD FOR PART-PAYMENT ---
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                      help_text="Tracks the actual amount paid.")

    class Meta:
        unique_together = ('staff', 'month', 'year')
        ordering = ['-year', '-month', 'staff__first_name']

    # --- UPDATED PROPERTIES ---
    @property
    def gross_salary(self):
        return (self.basic_salary + self.housing_allowance + self.transport_allowance +
                self.medical_allowance + self.other_allowances + self.bonus)

    @property
    def total_deductions(self):
        return self.tax_amount + self.pension_amount + self.other_deductions

    @property
    def net_salary(self):
        return self.gross_salary - self.total_deductions

    @property
    def payment_status(self):
        if self.is_paid:
            return "Paid"
        if self.amount_paid > 0 and self.amount_paid < self.net_salary:
            return "Partially Paid"
        return "Pending"

    def __str__(self):
        return f"Salary for {self.staff} - {self.month}/{self.year}"

