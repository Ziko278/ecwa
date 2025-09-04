# class ConsultationPaymentModel(models.Model):
#
# """Payment for consultation services"""
#
# patient = models.ForeignKey('patient.PatientModel', on_delete=models.CASCADE, related_name='consultation_payments')
#
# fee_structure = models.ForeignKey(ConsultationFeeModel, on_delete=models.CASCADE)
#
#
#
# # Payment details
#
# amount_due = models.DecimalField(max_digits=10, decimal_places=2, blank=True)
#
# amount_paid = models.DecimalField(max_digits=10, decimal_places=2, blank=True)
#
# balance = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True)
#
#
#
# # Insurance handling
#
# patient_insurance = models.ForeignKey('insurance.PatientInsuranceModel', on_delete=models.SET_NULL, null=True,
#
# blank=True)
#
# insurance_claim = models.OneToOneField('insurance.InsuranceClaimModel', on_delete=models.SET_NULL, null=True,
#
# blank=True)
#
# insurance_coverage = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True)
#
# patient_portion = models.DecimalField(max_digits=10, decimal_places=2, default=0, blank=True)
#
#
#
# # Transaction info
#
# transaction_id = models.CharField(max_length=100, unique=True, blank=True)
#
# payment_method = models.CharField(
#
# max_length=20, blank=True,
#
# choices=[
#
# ('cash', 'Cash'),
#
# ('card', 'Card'),
#
# ('wallet', 'Wallet'),
#
# ('transfer', 'Transfer'),
#
# ('insurance', 'Insurance'),
#
# ],
#
# default='wallet'
#
# )
#
#
#
# # Status
#
# PAYMENT_STATUS = [
#
# ('pending', 'Pending Payment'),
#
# ('partial', 'Partially Paid'),
#
# ('paid', 'Fully Paid'),
#
# ('overpaid', 'Overpaid'),
#
# ]
#
# status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='paid')
#
#
#
# # Tracking
#
# created_at = models.DateTimeField(auto_now_add=True)
#
# paid_at = models.DateTimeField(null=True, blank=True)
#
# processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='consultation_processed_payments')
#
#
#
# class Meta:
#
# db_table = 'consultation_payments'
#
# ordering = ['-created_at']
#
#
#
# def __str__(self):
#
# return f"Payment: {self.patient} - {self.transaction_id} (₦{self.amount_paid})"
#
#
#
# def save(self, *args, **kwargs):
#
# # Generate transaction ID
#
# if not self.transaction_id:
#
# today = date.today().strftime('%Y%m%d')
#
# last_payment = ConsultationPaymentModel.objects.filter(
#
# transaction_id__startswith=f'CSL{today}'
#
# ).order_by('-transaction_id').last()
#
#
#
# if last_payment:
#
# try:
#
# last_num = int(last_payment.transaction_id[-4:])
#
# next_num = last_num + 1
#
# except ValueError:
#
# next_num = 1
#
# else:
#
# next_num = 1
#
#
#
# self.transaction_id = f'CSL{today}{str(next_num).zfill(4)}'
#
#
#
# # Calculate balance and status
#
# self.balance = self.amount_due - self.amount_paid - self.insurance_coverage
#
#
#
# if self.amount_paid == 0:
#
# self.status = 'pending'
#
# elif self.balance > 0:
#
# self.status = 'partial'
#
# elif self.balance == 0:
#
# self.status = 'paid'
#
# else:
#
# self.status = 'overpaid'
#
#
#
# if self.status in ['paid', 'overpaid'] and not self.paid_at:
#
# self.paid_at = datetime.now()
#
#
#
# super().save(*args, **kwargs)
#
#
#
#
#
# i initially have this model in my consultation app, then i added this model:
#
#
#
#
#
# class PatientTransactionModel(models.Model):
#
# patient = models.ForeignKey(PatientModel, on_delete=models.SET_NULL, null=True)
#
# TRANSACTION_TYPE = (
#
# ('wallet_funding', 'WALLET FUNDING'),
#
# ('consultation_payment', 'CONSULTATION PAYMENT'),
#
# ('drug_payment', 'DRUG PAYMENT'),
#
# ('lab_payment', 'LAB PAYMENT'),
#
# ('scan_payment', 'SCAN PAYMENT'),
#
# ('drug_refund', 'DRUG REFUND'),
#
# ('lab_refund', 'LAB REFUND'),
#
# ('scan_refund', 'SCAN REFUND'),
#
# ('wallet_withdrawal', 'WALLET WITHDRAWAL'),
#
# )
#
# transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE)
#
# transaction_direction = models.CharField(max_length=20, choices=(('in', 'IN'), ('out', 'OUT')))
#
# amount = models.DecimalField(
#
# max_digits=12,
#
# decimal_places=2,
#
# validators=[MinValueValidator(Decimal('0.01'))]
#
# )
#
# old_balance = models.DecimalField(
#
# max_digits=12,
#
# decimal_places=2,
#
# validators=[MinValueValidator(Decimal('0.01'))]
#
# )
#
# new_balance = models.DecimalField(
#
# max_digits=12,
#
# decimal_places=2,
#
# validators=[MinValueValidator(Decimal('0.01'))]
#
# )
#
# date = models.DateField()
#
# received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
#
# transaction_id = models.CharField(max_length=100, blank=True, db_index=True)
#
# payment_method = models.CharField(max_length=50, blank=True)
#
# status = models.CharField(
#
# max_length=20,
#
# choices=[
#
# ('pending', 'PENDING'),
#
# ('completed', 'COMPLETED'),
#
# ('failed', 'FAILED'),
#
# ('cancelled', 'CANCELLED')
#
# ],
#
# default='completed'
#
# )
#
# created_at = models.DateTimeField(auto_now_add=True)
#
#
#
