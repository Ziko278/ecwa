"""
insurance/signals.py

Automatic insurance claim creation for hospital orders.
When a patient with valid insurance gets a service, a claim is automatically
created and routed to the insurance department for manual HMO submission.
"""

import logging
from decimal import Decimal, ROUND_HALF_UP

from django.apps import apps as django_apps
from django.db.models.signals import post_save
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver# Assuming these are your actual model paths
from .models import InsuranceClaimModel, PatientInsuranceModel, InsuranceClaimSummary

logger = logging.getLogger(__name__)

# insurance/signals.py



@receiver(post_save, sender=InsuranceClaimModel)
def create_or_update_claim_summary(sender, instance, created, **kwargs):
    """
    Automatically create or update claim summary when a claim is saved.
    Groups claims by consultation, admission, or surgery.
    """
    # Skip if claim already has a summary
    if instance.claim_summary:
        # Just recalculate the existing summary
        instance.claim_summary.recalculate_totals()
        return

    # Determine the source (consultation, admission, or surgery)
    # This is based on the related order's source
    consultation = None
    admission = None
    surgery = None

    # Try to get consultation from the related order
    if instance.content_object:
        # Check if the order has consultation, admission, or surgery
        if hasattr(instance.content_object, 'consultation') and instance.content_object.consultation:
            consultation = instance.content_object.consultation
        elif hasattr(instance.content_object, 'admission') and instance.content_object.admission:
            admission = instance.content_object.admission
        elif hasattr(instance.content_object, 'surgery') and instance.content_object.surgery:
            surgery = instance.content_object.surgery

    # If no source found, we can't create a summary
    if not (consultation or admission or surgery):
        return

    # Try to find existing summary for this source
    summary = None

    if consultation:
        summary = InsuranceClaimSummary.objects.filter(
            consultation=consultation,
            patient_insurance=instance.patient_insurance
        ).first()
    elif admission:
        summary = InsuranceClaimSummary.objects.filter(
            admission=admission,
            patient_insurance=instance.patient_insurance
        ).first()
    elif surgery:
        summary = InsuranceClaimSummary.objects.filter(
            surgery=surgery,
            patient_insurance=instance.patient_insurance
        ).first()

    # Create new summary if doesn't exist
    if not summary:
        summary = InsuranceClaimSummary.objects.create(
            consultation=consultation,
            admission=admission,
            surgery=surgery,
            patient_insurance=instance.patient_insurance,
            created_by=instance.created_by
        )

    # Link claim to summary
    instance.claim_summary = summary
    # Use update to avoid triggering signal again
    InsuranceClaimModel.objects.filter(pk=instance.pk).update(claim_summary=summary)

    # Recalculate totals
    summary.recalculate_totals()


@receiver(post_delete, sender=InsuranceClaimModel)
def update_summary_on_claim_delete(sender, instance, **kwargs):
    """
    Update claim summary when a claim is deleted.
    """
    if instance.claim_summary:
        summary = instance.claim_summary
        # Check if summary still has claims
        if summary.claims.count() == 0:
            # Delete empty summary
            summary.delete()
        else:
            # Recalculate totals
            summary.recalculate_totals()


# -------------------------
# Helpers (Unchanged)
# -------------------------
def get_active_patient_insurance(patient):
    """
    Return active, verified PatientInsuranceModel for the patient or None.
    """
    try:
        insurance = (
            PatientInsuranceModel.objects.filter(
                patient=patient,
                is_active=True,
                is_verified=True,
            )
            .select_related("coverage_plan", "hmo")
            .first()
        )
        if insurance and getattr(insurance, "is_valid", True):
            return insurance
        return None
    except Exception:
        logger.exception("Error getting patient insurance")
        return None


def check_service_coverage(order, claim_type, coverage_plan):
    """
    Return dict: {'is_covered': bool, 'coverage_percentage': Decimal, 'reason': str}
    """
    result = {"is_covered": False, "coverage_percentage": Decimal("0.00"), "reason": ""}
    # This function's logic remains the same as it correctly checks coverage plans.
    # No changes are needed here based on the models provided.
    try:
        if claim_type == "drug":
            drug = getattr(order, "drug", None)
            if not drug:
                result["reason"] = "No drug specified in order"
                return result
            # Assuming your coverage_plan model has a method is_drug_covered
            if coverage_plan.is_drug_covered(drug):
                result["is_covered"] = True
                result["coverage_percentage"] = Decimal(str(coverage_plan.drug_coverage_percentage))
            else:
                result["reason"] = f'Drug "{getattr(drug, "brand_name", drug)}" not covered by plan'

        elif claim_type in ("laboratory", "lab"):
            # Your model is LabTestOrderModel, which has a 'template' field
            lab_test = getattr(order, "template", None)
            if not lab_test:
                result["reason"] = "No lab test template specified in order"
                return result
            if coverage_plan.is_lab_covered(lab_test):
                result["is_covered"] = True
                result["coverage_percentage"] = Decimal(str(coverage_plan.lab_coverage_percentage))
            else:
                result["reason"] = f'Lab test "{getattr(lab_test, "name", lab_test)}" not covered by plan'

        elif claim_type in ("scan", "radiology"):
             # Your model is ScanOrderModel, which has a 'template' field
            scan = getattr(order, "template", None)
            if not scan:
                result["reason"] = "No scan template specified in order"
                return result
            if coverage_plan.is_radiology_covered(scan):
                result["is_covered"] = True
                result["coverage_percentage"] = Decimal(str(coverage_plan.radiology_coverage_percentage))
            else:
                result["reason"] = f'Scan "{getattr(scan, "name", scan)}" not covered by plan'

        elif claim_type == "surgery":
            surgery_type = getattr(order, "surgery_type", None)
            if not surgery_type:
                result["reason"] = "No surgery type specified"
                return result
            if coverage_plan.is_surgery_covered(surgery_type):
                result["is_covered"] = True
                result["coverage_percentage"] = Decimal(str(coverage_plan.surgery_coverage_percentage))
            else:
                result["reason"] = f'Surgery "{getattr(surgery_type, "name", surgery_type)}" not covered by plan'

    except Exception:
        logger.exception("Error checking coverage")
        result["reason"] = "Error checking coverage"

    return result


def _get_obj_for_order_and_type(order, claim_type):
    """Return the related billed object for include/exclude checks"""
    if claim_type == "drug":
        return getattr(order, "drug", None)
    if claim_type in ("laboratory", "lab"):
        return getattr(order, "template", None) # Corrected to 'template'
    if claim_type in ("scan", "radiology"):
        return getattr(order, "template", None) # Corrected to 'template'
    if claim_type == "surgery":
        return getattr(order, "surgery_type", None)
    return None


# -------------------------
# Claim creation + calculation (REFACTORED and CORRECTED)
# -------------------------
def create_insurance_claim(order, patient, claim_type, total_amount, created_by=None):
    """
    Calculates coverage and creates the insurance claim in a single operation.
    """
    try:
        patient_insurance = get_active_patient_insurance(patient)
        if not patient_insurance:
            logger.info("No active insurance for patient %s - claim not created.", getattr(patient, "id", patient))
            return None

        coverage_plan = patient_insurance.coverage_plan
        coverage_info = check_service_coverage(order, claim_type, coverage_plan)
        if not coverage_info["is_covered"]:
            logger.info("Service not covered for patient %s: %s", getattr(patient, "id", patient), coverage_info["reason"])
            return None

        total_amount = Decimal(str(total_amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if total_amount <= 0:
            logger.info("Order %s has non-positive amount (%s) - claim not created.", getattr(order, "id", order), total_amount)
            return

        covered_amount = Decimal("0.00")
        patient_amount = total_amount
        obj = _get_obj_for_order_and_type(order, claim_type)

        try:
            if hasattr(coverage_plan, "compute_coverage_for_amount"):
                res = coverage_plan.compute_coverage_for_amount(service_type=claim_type, amount=total_amount, obj=obj)
                covered = Decimal(res.get("covered", "0.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                patient_portion = (total_amount - covered).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            else:
                pct = Decimal(str(coverage_info.get("coverage_percentage", Decimal("0.00"))))
                covered = (total_amount * pct / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                patient_portion = (total_amount - covered).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            covered_amount = covered
            patient_amount = patient_portion
        except Exception:
            logger.exception("Failed to compute coverage via plan; falling back to basic percentage.")
            pct = Decimal(str(coverage_info.get("coverage_percentage", Decimal("0.00"))))
            covered_amount = (total_amount * pct / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            patient_amount = (total_amount - covered_amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        content_type = ContentType.objects.get_for_model(type(order))
        claim = InsuranceClaimModel.objects.create(
            patient_insurance=patient_insurance,
            claim_type=claim_type,
            content_type=content_type,
            object_id=getattr(order, "id", None),
            total_amount=total_amount,
            covered_amount=covered_amount,
            patient_amount=patient_amount,
            service_date=timezone.now(),
            status="pending",
            created_by=created_by,
            notes=f"Auto-generated claim for {claim_type} order",
        )

        logger.info(
            "Claim %s created for %s order %s: Total=%s, Est. Coverage=%s, Patient Portion=%s",
            claim.claim_number,
            claim_type,
            order.id,
            total_amount,
            claim.covered_amount,
            claim.patient_amount,
        )
        return claim

    except Exception:
        logger.exception("Generic error creating insurance claim for order %s", getattr(order, "id", order))
        return None


# -------------------------
# Specific Signal Handlers (TAILORED TO YOUR MODELS)
# -------------------------
def create_drug_claim(sender, instance, created, **kwargs):
    if not created:
        return

    patient = getattr(instance, "patient", None)
    created_by = getattr(instance, "ordered_by", None)

    if not patient:
        logger.warning("Drug Order %s has no patient. Claim not created.", instance.id)
        return

    # Calculate total amount from related drug's price and ordered quantity
    try:
        price = instance.drug.selling_price
        quantity = instance.quantity_ordered
        # Convert float quantity to Decimal safely
        total_amount = price * Decimal(str(quantity))
    except Exception as e:
        logger.error("Could not calculate total_amount for Drug Order %s: %s. Claim not created.", instance.id, e)
        return

    create_insurance_claim(order=instance, patient=patient, claim_type="drug", total_amount=total_amount, created_by=created_by)


def create_lab_claim(sender, instance, created, **kwargs):
    if not created:
        return

    patient = getattr(instance, "patient", None)
    # The amount is on the LabTestOrderModel itself
    total_amount = getattr(instance, "amount_charged", None)
    created_by = getattr(instance, "ordered_by", None)

    if not patient:
        logger.warning("Lab Order %s has no patient. Claim not created.", instance.id)
        return
    if total_amount is None:
        logger.warning("Lab Order %s has no 'amount_charged' field or value. Claim not created.", instance.id)
        return

    create_insurance_claim(order=instance, patient=patient, claim_type="laboratory", total_amount=total_amount, created_by=created_by)


def create_scan_claim(sender, instance, created, **kwargs):
    if not created:
        return

    patient = getattr(instance, "patient", None)
    # The amount is on the ScanOrderModel itself
    total_amount = getattr(instance, "amount_charged", None)
    created_by = getattr(instance, "ordered_by", None)

    if not patient:
        logger.warning("Scan Order %s has no patient. Claim not created.", instance.id)
        return
    if total_amount is None:
        logger.warning("Scan Order %s has no 'amount_charged' field or value. Claim not created.", instance.id)
        return

    create_insurance_claim(order=instance, patient=patient, claim_type="scan", total_amount=total_amount, created_by=created_by)


def create_surgery_claim(sender, instance, created, **kwargs):
    if not created:
        return

    patient = getattr(instance, "patient", None)
    # The amount is calculated via a property on the Surgery model
    total_amount = getattr(instance, "total_surgery_cost", None)
    created_by = getattr(instance, "created_by", None) or getattr(instance, "primary_surgeon", None)

    if not patient:
        logger.warning("Surgery %s has no patient. Claim not created.", instance.id)
        return
    if total_amount is None:
        logger.warning("Surgery %s has no 'total_surgery_cost' property or value. Claim not created.", instance.id)
        return

    create_insurance_claim(order=instance, patient=patient, claim_type="surgery", total_amount=total_amount, created_by=created_by)


# -------------------------
# Connect handlers
# -------------------------
def connect_signals():
    # It's important that the app_label and model_name match your project structure
    try:
        # Assuming your apps are named 'pharmacy', 'laboratory', 'scan', and 'inpatient'
        PharmacyOrder = django_apps.get_model("pharmacy", "DrugOrderModel")
        LabOrder = django_apps.get_model("laboratory", "LabTestOrderModel")
        ScanOrder = django_apps.get_model("scan", "ScanOrderModel")
        SurgeryOrder = django_apps.get_model("inpatient", "Surgery")
    except LookupError as e:
        logger.exception("A model was not found when connecting insurance signals: %s. Signals may not be connected.", e)
        return

    post_save.connect(create_drug_claim, sender=PharmacyOrder, dispatch_uid="insurance_auto_claim_drug_v2")
    post_save.connect(create_lab_claim, sender=LabOrder, dispatch_uid="insurance_auto_claim_lab_v2")
    post_save.connect(create_scan_claim, sender=ScanOrder, dispatch_uid="insurance_auto_claim_scan_v2")
    post_save.connect(create_surgery_claim, sender=SurgeryOrder, dispatch_uid="insurance_auto_claim_surgery_v2")
    logger.info("Insurance signals correctly connected with specific model logic.")
