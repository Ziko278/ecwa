"""
Helper functions for inpatient module payment processing.
"""
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType

from finance.models import PatientTransactionModel
from insurance.models import PatientInsuranceModel, InsuranceClaimModel


def process_admission_service_payment(order, order_type, admission, ordered_by):
    """
    Process payment for a service ordered during admission.

    This function:
    1. Checks for insurance coverage
    2. Calculates patient amount vs covered amount
    3. Deducts from admission deposit (or adds to debt if insufficient)
    4. Creates appropriate transactions and claims

    Args:
        order: The order instance (DrugOrderModel, LabTestOrderModel, ScanOrderModel, etc.)
        order_type: String ('drug', 'lab', 'scan', 'service')
        admission: Admission instance
        ordered_by: User who ordered the service

    Returns:
        dict with 'success', 'paid_amount', 'debt_added', 'claim_created'
    """
    # Get order total
    if hasattr(order, 'total_amount'):
        total_amount = order.total_amount
    elif hasattr(order, 'amount_charged'):
        total_amount = order.amount_charged
    else:
        total_amount = Decimal('0.00')

    if total_amount <= Decimal('0.00'):
        return {'success': False, 'error': 'Invalid order amount'}

    # Check for insurance
    patient_insurance = PatientInsuranceModel.objects.filter(
        patient=admission.patient,
        is_active=True,
        is_verified=True
    ).first()

    patient_amount = total_amount
    covered_amount = Decimal('0.00')
    claim = None

    if patient_insurance:
        coverage_plan = patient_insurance.coverage_plan
        is_covered = False
        coverage_pct = Decimal('0.00')

        # Check coverage based on order type
        if order_type == 'drug' and coverage_plan.is_drug_covered(order.drug):
            is_covered = True
            coverage_pct = coverage_plan.drug_coverage_percentage
        elif order_type == 'lab' and coverage_plan.is_lab_covered(order.template):
            is_covered = True
            coverage_pct = coverage_plan.lab_coverage_percentage
        elif order_type == 'scan' and coverage_plan.is_radiology_covered(order.template):
            is_covered = True
            coverage_pct = coverage_plan.radiology_coverage_percentage

        if is_covered:
            covered_amount = (total_amount * coverage_pct) / Decimal('100')
            patient_amount = total_amount - covered_amount

            # Create insurance claim
            claim = InsuranceClaimModel.objects.create(
                patient_insurance=patient_insurance,
                claim_type=order_type,
                content_type=ContentType.objects.get_for_model(order),
                object_id=order.id,
                total_amount=total_amount,
                covered_amount=covered_amount,
                patient_amount=patient_amount,
                service_date=timezone.now(),
                status='pending',
                created_by=ordered_by
            )

    # Process payment from deposit
    wallet_portion = Decimal('0.00')
    debt_portion = Decimal('0.00')

    if admission.deposit_balance >= patient_amount:
        # Full payment from deposit
        wallet_portion = patient_amount
        admission.deposit_balance -= patient_amount
    else:
        # Mixed payment (deposit + debt)
        wallet_portion = admission.deposit_balance
        debt_portion = patient_amount - wallet_portion
        admission.deposit_balance = Decimal('0.00')

    # Update admission totals
    admission.total_charges += total_amount
    admission.save()

    # Determine transaction type
    transaction_type_map = {
        'drug': 'drug_payment',
        'lab': 'lab_payment',
        'scan': 'scan_payment',
        'service': 'service'
    }

    # Create transaction
    trans_kwargs = {
        'patient': admission.patient,
        'transaction_type': transaction_type_map.get(order_type, 'other_payment'),
        'transaction_direction': 'out',
        'amount': patient_amount,
        'admission': admission,
        'wallet_amount_used': wallet_portion,
        'direct_payment_amount': debt_portion,
        'payment_method': 'admission',
        'received_by': ordered_by,
        'old_balance': admission.patient.wallet_balance,
        'new_balance': admission.patient.wallet_balance,
        'status': 'completed',
        'date': timezone.now().date()
    }

    # Add order-specific FK
    if order_type == 'drug':
        trans_kwargs['drug_order'] = order
    elif order_type == 'lab':
        trans_kwargs['lab_structure'] = order
    elif order_type == 'scan':
        trans_kwargs['scan_order'] = order
    elif order_type == 'service':
        trans_kwargs['service'] = order

    PatientTransactionModel.objects.create(**trans_kwargs)

    # Update order status and payment method
    if hasattr(order, 'status'):
        order.status = 'paid'
    if hasattr(order, 'payment_method'):
        order.payment_method = 'admission'
    order.save()

    return {
        'success': True,
        'paid_amount': wallet_portion,
        'debt_added': debt_portion,
        'claim_created': claim is not None,
        'claim': claim
    }


def clear_pending_admission_orders(admission, deposit_amount):
    """
    When a deposit is made, clear pending orders in FIFO order.

    Args:
        admission: Admission instance
        deposit_amount: Amount of deposit being added

    Returns:
        dict with 'orders_cleared', 'amount_used'
    """
    from pharmacy.models import DrugOrderModel
    from laboratory.models import LabTestOrderModel
    from scan.models import ScanOrderModel
    from service.models import PatientServiceTransaction

    remaining_deposit = deposit_amount
    orders_cleared = 0

    # Get all pending orders for this admission
    pending_drugs = DrugOrderModel.objects.filter(
        admission=admission,
        status='pending'
    ).order_by('ordered_at')

    pending_labs = LabTestOrderModel.objects.filter(
        admission=admission,
        status='pending'
    ).order_by('ordered_at')

    pending_scans = ScanOrderModel.objects.filter(
        admission=admission,
        status='pending'
    ).order_by('ordered_at')

    pending_services = PatientServiceTransaction.objects.filter(
        admission=admission,
        status='pending_payment'
    ).order_by('created_at')

    # Combine all pending orders into one list with timestamps
    all_pending = []

    for drug in pending_drugs:
        all_pending.append(('drug', drug, drug.ordered_at, drug.total_amount))

    for lab in pending_labs:
        all_pending.append(('lab', lab, lab.ordered_at, lab.total_amount))

    for scan in pending_scans:
        all_pending.append(('scan', scan, scan.ordered_at, scan.total_amount))

    for service in pending_services:
        all_pending.append(('service', service, service.created_at, service.total_amount))

    # Sort by timestamp (FIFO)
    all_pending.sort(key=lambda x: x[2])

    # Clear orders
    for order_type, order, timestamp, amount in all_pending:
        if remaining_deposit >= amount:
            # Can pay in full
            result = process_admission_service_payment(
                order=order,
                order_type=order_type,
                admission=admission,
                ordered_by=order.ordered_by if hasattr(order, 'ordered_by') else order.performed_by
            )

            if result['success']:
                remaining_deposit -= amount
                orders_cleared += 1
        else:
            # Cannot pay this order, stop here
            break

    amount_used = deposit_amount - remaining_deposit

    return {
        'orders_cleared': orders_cleared,
        'amount_used': amount_used
    }