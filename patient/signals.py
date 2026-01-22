from decimal import Decimal

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.html import escape
from django.utils.timezone import now
from django.db import transaction
from datetime import datetime, date, time, timedelta
import logging
from admin_site.models import ActivityLogModel
from consultation.models import PatientQueueModel
from finance.models import PatientTransactionModel
from patient.models import RegistrationFeeModel, PatientModel, PatientWalletModel, RegistrationPaymentModel

logger = logging.getLogger(__name__)


# Helper: display actor as staff __str__ if available, else user full name/username, else "System"
def get_actor_display(user):
    if not user:
        return "System"
    try:
        profile = getattr(user, 'user_staff_profile', None)  # from StaffProfileModel.related_name
        if profile and getattr(profile, 'staff', None):
            return str(profile.staff)  # uses StaffModel.__str__()
    except Exception:
        pass
    full_name = user.get_full_name().strip()
    return full_name or user.username or "System"


# --- Track changes on update ---
@receiver(pre_save, sender=RegistrationFeeModel)
def track_registration_fee_changes(sender, instance, **kwargs):
    if not instance.pk:
        return  # skip new objects (handled in post_save)

    try:
        old_instance = RegistrationFeeModel.objects.get(pk=instance.pk)
    except RegistrationFeeModel.DoesNotExist:
        return

    changes = []
    for field in ['title', 'amount', 'patient_type']:  # only track these fields
        old_value = getattr(old_instance, field)
        new_value = getattr(instance, field)
        if old_value != new_value:
            changes.append(f"{field} changed from '{old_value}' → '{new_value}'")

    if changes:
        log_html = f"""
        <div class='bg-warning text-dark p-2' style='border-radius:5px;'>
            <p>
                <b>{escape(get_actor_display(instance.updated_by))}</b>
                updated <b>Registration Fee</b>: {escape(instance.title)}<br>
                {"; ".join(changes)}<br>
                <span class='float-end small'>{now().strftime("%Y-%m-%d %H:%M:%S")}</span>
            </p>
        </div>
        """
        ActivityLogModel.objects.create(
            log=log_html,
            category='patient',
            sub_category='registration_fee',
            keywords='registration_fee__update',
            user=instance.updated_by
        )


# --- Create log ---
@receiver(post_save, sender=RegistrationFeeModel)
def log_registration_fee_create(sender, instance, created, **kwargs):
    if created:
        log_html = f"""
        <div class='bg-success text-white p-2' style='border-radius:5px;'>
            <p>
                <b>{escape(get_actor_display(instance.created_by))}</b>
                created a new <b>Registration Fee</b>: {escape(instance.title)} 
                ({instance.patient_type.upper()}) - ₦{instance.amount}<br>
                <span class='float-end small'>{now().strftime("%Y-%m-%d %H:%M:%S")}</span>
            </p>
        </div>
        """
        ActivityLogModel.objects.create(
            log=log_html,
            category='patient',
            sub_category='registration_fee',
            keywords='registration_fee__create',
            user=instance.created_by
        )


@receiver(post_save, sender=PatientModel)
def create_patient_wallet(sender, instance, created, **kwargs):
    """
    A signal to automatically create a PatientWalletModel whenever a new
    PatientModel is created. This ensures every patient has a wallet.
    """
    if created:
        # Use get_or_create to safely create the wallet, preventing duplicates.
        PatientWalletModel.objects.get_or_create(patient=instance)


# --- Delete log ---
@receiver(post_delete, sender=RegistrationFeeModel)
def log_registration_fee_delete(sender, instance, **kwargs):
    actor = instance.updated_by or instance.created_by
    log_html = f"""
    <div class='bg-danger text-white p-2' style='border-radius:5px;'>
        <p>
            <b>{escape(get_actor_display(actor))}</b>
            deleted <b>Registration Fee</b>: {escape(instance.title)} 
            ({instance.patient_type.upper()}) - ₦{instance.amount}<br>
            <span class='float-end small'>{now().strftime("%Y-%m-%d %H:%M:%S")}</span>
        </p>
    </div>
    """
    ActivityLogModel.objects.create(
        log=log_html,
        category='patient',
        sub_category='registration_fee',
        keywords='registration_fee__delete',
        user=actor
    )


@receiver(post_save, sender=RegistrationPaymentModel)
def create_consultation_payment(sender, instance: RegistrationPaymentModel, created, **kwargs):
    """
    After a patient is created, if registration_payment.consultation_paid is True,
    create ConsultationPayment and add the patient to the queue.
    """
    if not created:
        return

    payment = instance
    if not payment:
        return

    # Only proceed if consultation was paid
    if not getattr(payment, 'consultation_paid', False):
        return

    try:
        with transaction.atomic():
            # 1. Create ConsultationPaymentModel

            validity_days = payment.consultation_fee.validity_in_days
            today = date.today()
            cutoff_time = time(20, 0)  # 8:00 PM
            start_date_for_validity = today if timezone.now().time() < cutoff_time else today + timedelta(days=1)
            valid_till = start_date_for_validity + timedelta(days=validity_days - 1)

            consult_payment = PatientTransactionModel.objects.create(
                registration_payment=payment,
                fee_structure=payment.consultation_fee,
                transaction_type='consultation_payment',
                transaction_direction='out',
                amount=payment.consultation_fee.amount if payment.consultation_fee else 0,
                direct_payment_amount=payment.consultation_fee.amount if payment.consultation_fee else 0,
                date=date.today(),
                payment_method=payment.payment_method or 'cash',
                status='completed',
                received_by=payment.created_by,
                old_balance=0,
                new_balance=0,
                valid_till = valid_till
            )

    except Exception as e:
        logger.error(f"Failed to create consultation payment: {e}", exc_info=True)


@receiver(post_save, sender=PatientModel)
def link_consultation_payment_and_queue(sender, instance: PatientModel, created, **kwargs):
    """
    After a patient is created, if registration_payment.consultation_paid is True,
    create ConsultationPayment and add the patient to the queue.
    """
    if not created:
        return

    payment = getattr(instance, 'registration_payment', None)
    if not payment:
        logger.warning(f"Patient {instance.pk} has no registration payment linked.")
        return

    try:
        with transaction.atomic():
            # 1. Link Patient to consultation
            consult_payment = PatientTransactionModel.objects.get(registration_payment=payment)
            consult_payment.patient = instance
            consult_payment.save()

            logger.info(f"Consultation linked to patient {instance.pk}")

    except Exception as e:
        logger.error(f"Failed to create consultation link for patient {instance.pk}: {e}", exc_info=True)

    # Only proceed if consultation was paid
    if not getattr(payment, 'consultation_paid', False):
        return

    try:
        with transaction.atomic():

            # 2. Add patient to PatientQueueModel
            PatientQueueModel.objects.create(
                patient=instance,
                payment=consult_payment,
                status='waiting_vitals'
            )

            logger.info(f"Queue created for patient {instance.pk}")

    except Exception as e:
        logger.error(f"Failed to create queue for patient {instance.pk}: {e}", exc_info=True)
