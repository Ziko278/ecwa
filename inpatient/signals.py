from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Surgery
from .views import get_inpatient_settings

"""
Signals for automatic charging and task generation in inpatient module.
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from datetime import datetime, timedelta, time
import re

from .models import Admission, AdmissionTask, AdmissionType
from pharmacy.models import DrugOrderModel
from laboratory.models import LabTestOrderModel
from scan.models import ScanOrderModel
from service.models import PatientServiceTransaction
from finance.models import PatientTransactionModel


# ============================================
# HELPER FUNCTIONS
# ============================================

def get_inpatient_settings():
    """Get or create inpatient settings instance"""
    from .models import InpatientSettings
    settings, created = InpatientSettings.objects.get_or_create(
        id=1,
        defaults={}
    )
    return settings


def check_and_charge_consultation_fee(ward_round):
    """
    Check if consultation fee should be charged during this ward round.
    Only charge if:
    1. No previous fee OR
    2. Previous fee validity has expired
    """
    admission = ward_round.admission
    if not admission:
        return

    admission_type = admission.admission_type
    if not admission_type:
        return

    should_charge = False

    if not admission.last_consultation_fee_date:
        should_charge = True
    elif admission.last_consultation_fee_valid_until:
        if ward_round.created_at.date() > admission.last_consultation_fee_valid_until:
            should_charge = True

    if not should_charge:
        return

    consultation_fee = admission.consultation_fee_used or admission_type.consultation_fee

    from insurance.models import PatientInsuranceModel, InsuranceClaimModel
    from django.contrib.contenttypes.models import ContentType

    patient_insurance = PatientInsuranceModel.objects.filter(
        patient=admission.patient,
        is_active=True,
        is_verified=True
    ).first()

    patient_amount = consultation_fee
    covered_amount = Decimal('0.00')

    if patient_insurance and patient_insurance.coverage_plan.consultation_covered:
        coverage_pct = patient_insurance.coverage_plan.consultation_coverage_percentage
        covered_amount = (consultation_fee * coverage_pct) / Decimal('100')
        patient_amount = consultation_fee - covered_amount

        InsuranceClaimModel.objects.create(
            patient_insurance=patient_insurance,
            claim_type='ward_round',
            content_type=ContentType.objects.get_for_model(ward_round),
            object_id=ward_round.id,
            total_amount=consultation_fee,
            covered_amount=covered_amount,
            patient_amount=patient_amount,
            service_date=timezone.now(),
            status='pending',
            created_by=admission.admitted_by
        )

    wallet_portion = Decimal('0.00')
    debt_portion = Decimal('0.00')

    if admission.deposit_balance >= patient_amount:
        wallet_portion = patient_amount
        admission.deposit_balance -= patient_amount
    else:
        wallet_portion = admission.deposit_balance
        debt_portion = patient_amount - wallet_portion
        admission.deposit_balance = Decimal('0.00')

    admission.total_charges += consultation_fee
    admission.last_consultation_fee_date = ward_round.created_at.date()
    admission.last_consultation_fee_valid_until = (
            ward_round.created_at.date() +
            timedelta(days=admission_type.consultation_fee_duration_days)
    )
    admission.save(update_fields=[
        'deposit_balance', 'total_charges',
        'last_consultation_fee_date',
        'last_consultation_fee_valid_until'
    ])

    PatientTransactionModel.objects.create(
        patient=admission.patient,
        transaction_type='admission_payment',
        transaction_direction='out',
        amount=patient_amount,
        admission=admission,
        wallet_amount_used=wallet_portion,
        direct_payment_amount=debt_portion,
        payment_method='admission',
        received_by=admission.admitted_by,
        old_balance=admission.deposit_balance + wallet_portion,
        new_balance=admission.deposit_balance,
        status='completed',
        date=timezone.now().date()
    )


# Replace the existing charge_initial_admission_fees function with this:

def charge_initial_admission_fees(admission):
    if admission.status != 'active' or not admission.admission_activated_date:
        return

    settings = get_inpatient_settings()
    admission_type = admission.admission_type

    # Determine bed rate (priority: Bed.daily_rate → AdmissionType.bed_daily_fee → settings.bed_daily_cost)
    if admission.bed and admission.bed.daily_rate:
        bed_rate = admission.bed.daily_rate
    elif admission_type and admission_type.bed_daily_fee:
        bed_rate = admission_type.bed_daily_fee
    else:
        bed_rate = settings.bed_daily_cost

    # Snapshot rates
    admission.bed_rate_used = bed_rate
    admission.consultation_fee_used = admission_type.consultation_fee if admission_type else Decimal('0.00')

    total_initial_charges = Decimal('0.00')

    # One-time admission fee
    admission_fee = Decimal('0.00')
    if settings.admission_billing_type == 'one_time' and settings.admission_amount > 0:
        admission_fee = settings.admission_amount
        admission.admission_fee_charged = admission_fee
        total_initial_charges += admission_fee

    # First day bed fee
    if settings.bed_billing_for_admission == 'daily':
        total_initial_charges += bed_rate
    elif settings.bed_billing_for_admission == 'one_time':
        total_initial_charges += bed_rate

    admission.save(update_fields=['bed_rate_used', 'consultation_fee_used', 'admission_fee_charged'])

    if total_initial_charges == Decimal('0.00'):
        return

    # Insurance check (keeping existing logic)
    from insurance.models import PatientInsuranceModel, InsuranceClaimModel
    from django.contrib.contenttypes.models import ContentType

    patient_insurance = PatientInsuranceModel.objects.filter(
        patient=admission.patient,
        is_active=True,
        is_verified=True
    ).first()

    patient_amount = total_initial_charges
    covered_amount = Decimal('0.00')

    if patient_insurance and admission_type and patient_insurance.coverage_plan.is_admission_type_covered(admission_type):
        coverage_pct = patient_insurance.coverage_plan.admission_coverage_percentage
        covered_amount = (total_initial_charges * coverage_pct) / Decimal('100')
        patient_amount = total_initial_charges - covered_amount

        InsuranceClaimModel.objects.create(
            patient_insurance=patient_insurance,
            claim_type='admission',
            content_type=ContentType.objects.get_for_model(admission),
            object_id=admission.id,
            total_amount=total_initial_charges,
            covered_amount=covered_amount,
            patient_amount=patient_amount,
            service_date=timezone.now(),
            status='pending',
            created_by=admission.admitted_by
        )

    # Charge from deposit
    wallet_portion = Decimal('0.00')
    debt_portion = Decimal('0.00')

    if admission.deposit_balance >= patient_amount:
        wallet_portion = patient_amount
        admission.deposit_balance -= patient_amount
    else:
        wallet_portion = admission.deposit_balance
        debt_portion = patient_amount - wallet_portion
        admission.deposit_balance = Decimal('0.00')

    admission.total_charges += total_initial_charges
    admission.save(update_fields=['deposit_balance', 'total_charges'])

    PatientTransactionModel.objects.create(
        patient=admission.patient,
        transaction_type='admission_payment',
        transaction_direction='out',
        amount=patient_amount,
        admission=admission,
        wallet_amount_used=wallet_portion,
        direct_payment_amount=debt_portion,
        payment_method='admission',
        received_by=admission.admitted_by,
        old_balance=admission.deposit_balance + wallet_portion,
        new_balance=admission.deposit_balance,
        status='completed',
        date=timezone.now().date()
    )


# MODIFY the existing signal to only charge when status becomes 'active'
@receiver(post_save, sender=Admission)
def handle_admission_activation(sender, instance, created, **kwargs):
    """
    When admission status changes to 'active':
    1. Charge initial admission fee (if enabled)
    2. Charge first day bed fee

    This replaces the old handle_admission_creation signal.
    """
    # Only charge when admission is activated
    update_fields = kwargs.get('update_fields')

    # Skip if this save was triggered by charge_initial_admission_fees itself
    if update_fields and set(update_fields).issubset({
        'bed_rate_used', 'consultation_fee_used', 'admission_fee_charged',
        'deposit_balance', 'total_charges'
    }):
        return

    if instance.status == 'active' and instance.admission_activated_date:
        transaction.on_commit(lambda: charge_initial_admission_fees(instance))


def parse_dosage_frequency(dosage_instructions):
    """
    Parse dosage instructions to determine frequency.
    Returns: (times_per_day, time_intervals)

    Examples:
    - "OD" or "once daily" -> (1, ['08:00'])
    - "BD" or "twice daily" -> (2, ['08:00', '20:00'])
    - "TDS" or "three times" -> (3, ['08:00', '14:00', '20:00'])
    - "QDS" or "four times" -> (4, ['08:00', '14:00', '20:00', '02:00'])
    - "Q4H" -> (6, every 4 hours)
    - "Q6H" -> (4, every 6 hours)
    """
    dosage_lower = dosage_instructions.lower()

    # OD patterns
    if any(pattern in dosage_lower for pattern in ['od', 'once', 'daily', '1/day', '1x']):
        return (1, [time(8, 0)])  # 8 AM

    # BD patterns
    if any(pattern in dosage_lower for pattern in ['bd', 'bid', 'twice', '2/day', '2x', 'q12h']):
        return (2, [time(8, 0), time(20, 0)])  # 8 AM, 8 PM

    # TDS patterns
    if any(pattern in dosage_lower for pattern in ['tds', 'tid', 'thrice', 'three times', '3/day', '3x', 'q8h']):
        return (3, [time(8, 0), time(14, 0), time(20, 0)])  # 8 AM, 2 PM, 8 PM

    # QDS patterns
    if any(pattern in dosage_lower for pattern in ['qds', 'qid', 'four times', '4/day', '4x', 'q6h']):
        return (4, [time(8, 0), time(14, 0), time(20, 0), time(2, 0)])  # 8 AM, 2 PM, 8 PM, 2 AM

    # Q4H
    if 'q4h' in dosage_lower:
        return (6, [time(0, 0), time(4, 0), time(8, 0), time(12, 0), time(16, 0), time(20, 0)])

    # Q3H
    if 'q3h' in dosage_lower:
        return (8, [time(0, 0), time(3, 0), time(6, 0), time(9, 0), time(12, 0), time(15, 0), time(18, 0), time(21, 0)])

    # Default: once daily
    return (1, [time(8, 0)])


def parse_duration_in_days(duration_str):
    """
    Parse duration string to days.
    Examples: "5 days", "1 week", "2 weeks", "1 month"
    """
    if not duration_str:
        return 7  # Default 7 days

    duration_lower = duration_str.lower()

    # Extract number
    match = re.search(r'(\d+)', duration_lower)
    if not match:
        return 7

    number = int(match.group(1))

    if 'week' in duration_lower:
        return number * 7
    elif 'month' in duration_lower:
        return number * 30
    else:  # Assume days
        return number


def generate_drug_administration_tasks(drug_order, first_dose_time):
    """
    Generate administration tasks for a drug order.

    Args:
        drug_order: DrugOrderModel instance
        first_dose_time: time object for the first dose
    """
    if not drug_order.admission:
        return  # Only generate tasks for admission-related orders

    # Parse frequency and duration
    frequency, default_times = parse_dosage_frequency(drug_order.dosage_instructions)
    duration_days = parse_duration_in_days(drug_order.duration)
    hours_per_dose = 24 // frequency  # e.g. QID=6hrs, TDS=8hrs, BD=12hrs, OD=24hrs

    now = timezone.now()

    # Anchor all tasks from the first dose datetime
    # This avoids the day+time combination bug where times past midnight
    # on day 0 were incorrectly compared against today and skipped
    if first_dose_time:
        first_dose_datetime = timezone.make_aware(
            datetime.combine(now.date(), first_dose_time)
        )
    else:
        # Fallback: use default times from parse_dosage_frequency
        first_dose_datetime = timezone.make_aware(
            datetime.combine(now.date(), default_times[0])
        )

    tasks_created = 0

    # Single flat loop: total tasks = frequency × duration_days
    # e.g. QID for 1 day = 4 tasks, BD for 3 days = 6 tasks
    for i in range(frequency * duration_days):
        scheduled_datetime = first_dose_datetime + timedelta(hours=i * hours_per_dose)

        # Skip tasks that are more than 5 minutes in the past
        # (small grace period to account for processing delay)
        if scheduled_datetime < now - timedelta(minutes=5):
            continue

        AdmissionTask.objects.create(
            admission=drug_order.admission,
            task_type='drug',
            drug_order=drug_order,
            description=f"Administer {drug_order.drug.brand_name or drug_order.drug.generic_name} - {drug_order.dosage_instructions}",
            scheduled_datetime=scheduled_datetime,
            status='pending',
            is_recurring=True,
            recurrence_pattern=drug_order.dosage_instructions,
            priority='normal',
            created_by=drug_order.ordered_by
        )
        tasks_created += 1

    return tasks_created


# ============================================
# SIGNALS
# ============================================

# @receiver(post_save, sender=Admission)
# def handle_admission_creation(sender, instance, created, **kwargs):
#     """
#     When a new admission is created:
#     1. Charge initial admission fee (if enabled)
#     2. Charge first day bed fee
#     """
#     if created and instance.status == 'active':
#         # Use transaction.on_commit to ensure the admission is saved first
#         transaction.on_commit(lambda: charge_initial_admission_fees(instance))


# @receiver(post_save, sender=WardRound)
# def handle_ward_round_creation(sender, instance, created, **kwargs):
#     """
#     When a new ward round is created:
#     1. Check if consultation fee should be charged
#     2. If yes, charge it from admission deposit
#     """
#     if created and instance.status in ['in_progress', 'completed']:
#         transaction.on_commit(lambda: check_and_charge_consultation_fee(instance))


@receiver(post_save, sender=DrugOrderModel)
def handle_drug_order_for_admission(sender, instance, created, **kwargs):
    """
    When a drug is ordered for an admitted patient:
    1. Charge from admission deposit (if admission exists)
    2. Generate administration tasks (if requested)
    """
    if not instance.admission:
        return  # Not an admission-related order

    if created:
        # Generate tasks if requested
        if instance.generate_tasks and instance.first_dose_time:
            transaction.on_commit(
                lambda: generate_drug_administration_tasks(instance, instance.first_dose_time)
            )


@receiver(post_save, sender=LabTestOrderModel)
def handle_lab_order_for_admission(sender, instance, created, **kwargs):
    """
    When a lab test is ordered for an admitted patient:
    Charge from admission deposit (if admission exists and status is pending)
    """
    # This will be handled by your existing payment flow
    # Just ensuring the admission FK is set
    pass


@receiver(post_save, sender=ScanOrderModel)
def handle_scan_order_for_admission(sender, instance, created, **kwargs):
    """
    When a scan is ordered for an admitted patient:
    Charge from admission deposit (if admission exists and status is pending)
    """
    # This will be handled by your existing payment flow
    # Just ensuring the admission FK is set
    pass


@receiver(post_save, sender=PatientServiceTransaction)
def handle_service_for_admission(sender, instance, created, **kwargs):
    """
    When a service is ordered for an admitted patient:
    Charge from admission deposit (if admission exists)
    """
    # This will be handled by your existing payment flow
    pass


@receiver(post_save, sender=Surgery)
def create_orders_from_surgery_package(sender, instance, created, **kwargs):
    """
    When a new Surgery is created, automatically create drug, lab, and scan orders
    based on the items in the associated SurgeryType package.
    """
    if created and instance.status == 'scheduled':
        surgery_type = instance.surgery_type
        settings = get_inpatient_settings()

        # Create Drug Orders if enabled
        if settings.compile_surgery_drugs:
            for item in surgery_type.surgerydrug_set.filter(is_optional=False):
                DrugOrderModel.objects.get_or_create(
                    patient=instance.patient,
                    drug=item.drug,
                    surgery=instance,
                    defaults={
                        'quantity_ordered': item.quantity,
                        'dosage_instructions': item.timing,
                        'ordered_by': instance.created_by,
                        'status': 'pending',
                        'admission': instance.admission
                    }
                )

        # Create Lab Test Orders if enabled
        if settings.compile_surgery_labs:
            for item in surgery_type.surgerylab_set.filter(is_optional=False):
                LabTestOrderModel.objects.get_or_create(
                    patient=instance.patient,
                    template=item.lab,
                    surgery=instance,
                    defaults={
                        'ordered_by': instance.created_by,
                        'status': 'pending',
                        'source': 'doctor',
                        'admission': instance.admission
                    }
                )

        # Create Scan Orders if enabled
        if settings.compile_surgery_scans:
            for item in surgery_type.surgeryscan_set.filter(is_optional=False):
                ScanOrderModel.objects.get_or_create(
                    patient=instance.patient,
                    template=item.scan,
                    surgery=instance,
                    defaults={
                        'ordered_by': instance.created_by,
                        'status': 'pending',
                        'clinical_indication': f"For {surgery_type.name}",
                        'admission': instance.admission
                    }
                )
