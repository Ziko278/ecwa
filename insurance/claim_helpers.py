# insurance/claim_helpers.py
"""
Helper functions for claim-based insurance payment processing.
These utilities check for approved claims and calculate patient amounts accordingly.
"""

from decimal import Decimal, ROUND_HALF_UP
from django.contrib.contenttypes.models import ContentType
from insurance.models import InsuranceClaimModel


def _quantize(amount):
    """Safely quantize a decimal amount to 2 decimal places."""
    return Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def get_claim_for_order(order, order_type_hint=None):
    """
    Get the insurance claim associated with an order.

    Args:
        order: The order instance (DrugOrderModel, LabTestOrderModel, etc.)
        order_type_hint: Optional hint like 'drug', 'lab', 'scan' for optimization

    Returns:
        InsuranceClaimModel instance or None
    """
    try:
        content_type = ContentType.objects.get_for_model(type(order))

        # Try to find an approved or partially approved claim
        claim = InsuranceClaimModel.objects.filter(
            content_type=content_type,
            object_id=order.id,
            status__in=['approved', 'partially_approved', 'paid']
        ).first()

        return claim
    except Exception:
        return None


def get_pending_claim_for_order(order):
    """
    Check if there's a pending claim for an order.

    Returns:
        dict with 'has_pending_claim', 'claim', 'claim_number'
    """
    try:
        content_type = ContentType.objects.get_for_model(type(order))

        claim = InsuranceClaimModel.objects.filter(
            content_type=content_type,
            object_id=order.id,
            status__in=['pending', 'processing']
        ).first()

        return {
            'has_pending_claim': claim is not None,
            'claim': claim,
            'claim_number': claim.claim_number if claim else None,
            'claim_status': claim.status if claim else None
        }
    except Exception:
        return {
            'has_pending_claim': False,
            'claim': None,
            'claim_number': None,
            'claim_status': None
        }


def calculate_patient_amount_with_claim(order, base_amount):
    """
    Calculate the patient's payment amount considering approved claims.

    If there's an approved/partially approved claim:
        - Use claim.patient_amount
    Otherwise:
        - Return full base_amount (no insurance deduction)

    Args:
        order: The order instance
        base_amount: The total cost of the service

    Returns:
        dict with:
            - patient_amount: What patient must pay
            - covered_amount: What insurance covers
            - has_approved_claim: Boolean
            - claim_number: Claim reference (if exists)
            - claim_status: Status of claim
    """
    base_amount = _quantize(base_amount)

    # Check for approved claim
    claim = get_claim_for_order(order)

    if claim:
        return {
            'patient_amount': _quantize(claim.patient_amount),
            'covered_amount': _quantize(claim.covered_amount),
            'has_approved_claim': True,
            'claim_number': claim.claim_number,
            'claim_status': claim.status,
            'base_amount': base_amount
        }

    # No approved claim - patient pays full amount
    return {
        'patient_amount': base_amount,
        'covered_amount': Decimal('0.00'),
        'has_approved_claim': False,
        'claim_number': None,
        'claim_status': None,
        'base_amount': base_amount
    }


def get_orders_with_claim_info(orders, order_type):
    """
    Bulk process orders and attach claim information.

    Args:
        orders: QuerySet or list of order instances
        order_type: 'drug', 'lab', 'scan', 'service'

    Returns:
        List of dicts with order data and claim info
    """
    results = []

    for order in orders:
        # Determine base amount based on order type
        if order_type == 'drug':
            base_amount = (
                order.drug.selling_price * Decimal(str(order.quantity_ordered))
                if hasattr(order, 'drug') and hasattr(order.drug, 'selling_price')
                else Decimal('0.00')
            )
        elif order_type in ['lab', 'scan']:
            base_amount = (
                    getattr(order, 'amount_charged', None) or
                    getattr(order.template, 'price', Decimal('0.00'))
            )
        elif order_type == 'service':
            base_amount = getattr(order, 'total_amount', Decimal('0.00'))
        else:
            base_amount = Decimal('0.00')

        # Calculate with claim
        claim_info = calculate_patient_amount_with_claim(order, base_amount)

        # Check for pending claim
        pending_info = get_pending_claim_for_order(order)

        results.append({
            'order': order,
            'base_amount': claim_info['base_amount'],
            'patient_amount': claim_info['patient_amount'],
            'covered_amount': claim_info['covered_amount'],
            'has_approved_claim': claim_info['has_approved_claim'],
            'claim_number': claim_info['claim_number'],
            'claim_status': claim_info['claim_status'],
            'has_pending_claim': pending_info['has_pending_claim'],
            'pending_claim_number': pending_info['claim_number'],
            'pending_claim_status': pending_info['claim_status']
        })

    return results


def bulk_calculate_total_with_claims(order_ids_by_type):
    """
    Calculate total payment amount for multiple orders considering claims.

    Args:
        order_ids_by_type: dict like {
            'drug': [1, 2, 3],
            'lab': [4, 5],
            'scan': [6]
        }

    Returns:
        dict with total_amount and breakdown by type
    """
    from pharmacy.models import DrugOrderModel
    from laboratory.models import LabTestOrderModel
    from scan.models import ScanOrderModel

    total = Decimal('0.00')
    breakdown = {}

    # Process drugs
    if order_ids_by_type.get('drug'):
        drug_orders = DrugOrderModel.objects.filter(
            id__in=order_ids_by_type['drug']
        ).select_related('drug')

        drug_results = get_orders_with_claim_info(drug_orders, 'drug')
        drug_total = sum(r['patient_amount'] for r in drug_results)
        total += drug_total
        breakdown['drug'] = {
            'total': drug_total,
            'count': len(drug_results),
            'items': drug_results
        }

    # Process labs
    if order_ids_by_type.get('lab'):
        lab_orders = LabTestOrderModel.objects.filter(
            id__in=order_ids_by_type['lab']
        ).select_related('template')

        lab_results = get_orders_with_claim_info(lab_orders, 'lab')
        lab_total = sum(r['patient_amount'] for r in lab_results)
        total += lab_total
        breakdown['lab'] = {
            'total': lab_total,
            'count': len(lab_results),
            'items': lab_results
        }

    # Process scans
    if order_ids_by_type.get('scan'):
        scan_orders = ScanOrderModel.objects.filter(
            id__in=order_ids_by_type['scan']
        ).select_related('template')

        scan_results = get_orders_with_claim_info(scan_orders, 'scan')
        scan_total = sum(r['patient_amount'] for r in scan_results)
        total += scan_total
        breakdown['scan'] = {
            'total': scan_total,
            'count': len(scan_results),
            'items': scan_results
        }

    return {
        'total_amount': _quantize(total),
        'breakdown': breakdown
    }