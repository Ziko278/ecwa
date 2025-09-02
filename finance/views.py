# views.py
from datetime import timedelta, date
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import now
from django.views.decorators.http import require_http_methods
from django.views.generic import CreateView, ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string

from admin_site.models import SiteInfoModel
from consultation.models import ConsultationFeeModel
from laboratory.models import LabTestOrderModel
from patient.forms import RegistrationPaymentForm
from patient.models import RegistrationPaymentModel, RegistrationFeeModel, PatientModel, PatientWalletModel

import json
from django.core.serializers.json import DjangoJSONEncoder
import uuid

from pharmacy.models import DrugOrderModel
from scan.models import ScanOrderModel


class RegistrationPaymentCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = RegistrationPaymentModel
    form_class = RegistrationPaymentForm
    template_name = "finance/registration_payment/create.html"
    permission_required = "patient.add_registrationpaymentmodel"

    def get_success_url(self):
        return reverse('registration_payment_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        # Generate transaction ID
        if not form.instance.transaction_id:
            form.instance.transaction_id = f"REG{uuid.uuid4().hex[:8].upper()}"

        # Calculate total amount
        total = form.instance.registration_fee.amount if form.instance.registration_fee else 0
        if form.instance.consultation_fee:
            form.instance.consultation_paid = True
            form.instance.consultation_amount = form.instance.consultation_fee.amount
            total += form.instance.consultation_amount

        form.instance.amount = total
        messages.success(self.request, f"Payment recorded successfully! Transaction ID: {form.instance.transaction_id}")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Fetch registration fees
        reg_fees = RegistrationFeeModel.objects.all().values('id', 'title', 'amount', 'patient_type')
        context['registration_fees'] = json.dumps(list(reg_fees), cls=DjangoJSONEncoder)

        # Consultation fees for the select
        context['consultation_fees'] = ConsultationFeeModel.objects.filter(patient_category='regular')
        return context


class RegistrationPaymentDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = RegistrationPaymentModel
    template_name = "finance/registration_payment/detail.html"
    context_object_name = "payment"
    permission_required = "patient.view_registrationpaymentmodel"


class RegistrationPaymentListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = RegistrationPaymentModel
    template_name = "finance/registration_payment/index.html"
    context_object_name = "payments"
    permission_required = "patient.view_registrationpaymentmodel"

    def get_queryset(self):
        qs = RegistrationPaymentModel.objects.select_related('registration_fee', 'consultation_fee', 'created_by')

        # Default: only today's payments
        start_date = self.request.GET.get("start_date")
        end_date = self.request.GET.get("end_date")
        search = self.request.GET.get("search")

        if not start_date and not end_date:
            today = now().date()
            qs = qs.filter(date=today)

        if start_date and end_date:
            qs = qs.filter(date__range=[start_date, end_date])

        if search:
            qs = qs.filter(Q(full_name__icontains=search) | Q(old_card_number__icontains=search) | Q(
                transaction_id__icontains=search))

        return qs.order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Determine timeframe for title
        start_date = self.request.GET.get("start_date")
        end_date = self.request.GET.get("end_date")

        if start_date and end_date:
            if start_date == end_date:
                context['timeframe'] = f"for {start_date}"
            else:
                context['timeframe'] = f"from {start_date} to {end_date}"
        else:
            context['timeframe'] = "for Today"

        # Calculate total amount
        payments = context['payments']
        context['total_amount'] = sum(payment.amount for payment in payments)

        return context


def print_receipt(request, pk):
    """Generate printable POS receipt"""
    payment = get_object_or_404(RegistrationPaymentModel, pk=pk)

    # Check permission
    if not request.user.has_perm('patient.view_registrationpaymentmodel'):
        messages.error(request, "You don't have permission to view this receipt.")
        return redirect('registration_payment_index')

    context = {
        'payment': payment,
        'site_info': SiteInfoModel.objects.first(),
        'current_user': request.user,
        'print_time': now(),
    }

    html = render_to_string('finance/registration_payment/receipt.html', context)

    # Return as HTML for printing
    response = HttpResponse(html)
    response['Content-Type'] = 'text/html'
    return response


@login_required
def patient_wallet_funding(request):
    """Initial page for patient wallet funding"""
    return render(request, 'finance/wallet/funding.html')


@login_required
def verify_patient_ajax(request):
    """Verify patient by card number and return wallet details with pending payments"""
    card_number = request.GET.get('card_number', '').strip()

    if not card_number:
        return JsonResponse({'error': 'Card number required'}, status=400)

    try:
        # Look up patient by card number
        patient = PatientModel.objects.get(card_number__iexact=card_number)

        # Get or create wallet
        wallet, created = PatientWalletModel.objects.get_or_create(
            patient=patient,
            defaults={'amount': Decimal('0.00')}
        )

        # Calculate pending payments for last 30 days
        thirty_days_ago = timezone.now() - timedelta(days=30)

        # Get pending drug orders
        pending_drugs = DrugOrderModel.objects.filter(
            patient=patient,
            status__in=['pending'],
            ordered_at__gte=thirty_days_ago
        ).select_related('drug')

        # Get pending lab orders
        pending_labs = LabTestOrderModel.objects.filter(
            patient=patient,
            status__in=['pending'],
            ordered_at__gte=thirty_days_ago
        ).select_related('template')

        # Get pending scan orders
        pending_scans = ScanOrderModel.objects.filter(
            patient=patient,
            status__in=['pending'],
            ordered_at__gte=thirty_days_ago
        ).select_related('template')

        # Check for active insurance
        active_insurance = None
        if hasattr(patient, 'insurance_policies'):
            active_insurance = patient.insurance_policies.filter(
                is_active=True,
                valid_to__gte=date.today()
            ).select_related('hmo', 'coverage_plan').first()

        # Calculate totals with insurance consideration
        def calculate_insurance_amount(base_amount, coverage_percentage):
            """Calculate patient's portion after insurance"""
            if coverage_percentage and coverage_percentage > 0:
                covered_amount = base_amount * (coverage_percentage / 100)
                return base_amount - covered_amount
            return base_amount

        # Process drug orders
        drug_items = []
        drug_total = Decimal('0.00')
        for order in pending_drugs:
            base_amount = order.drug.selling_price

            if active_insurance and active_insurance.coverage_plan.is_drug_covered(order.drug):
                patient_amount = calculate_insurance_amount(
                    base_amount,
                    active_insurance.coverage_plan.drug_coverage_percentage
                )
            else:
                patient_amount = base_amount

            drug_items.append({
                'id': order.id,
                'name': f"{order.drug.brand_name or order.drug.generic_name}",
                'quantity': float(order.quantity_ordered),
                'base_amount': float(base_amount),
                'patient_amount': float(patient_amount),
                'order_number': order.order_number,
                'status': order.status,
                'ordered_date': order.ordered_at.strftime('%Y-%m-%d')
            })
            drug_total += patient_amount

        # Process lab orders
        lab_items = []
        lab_total = Decimal('0.00')
        for order in pending_labs:
            base_amount = order.amount_charged or order.template.price

            if active_insurance and active_insurance.coverage_plan.is_lab_covered(order.template):
                patient_amount = calculate_insurance_amount(
                    base_amount,
                    active_insurance.coverage_plan.lab_coverage_percentage
                )
            else:
                patient_amount = base_amount

            lab_items.append({
                'id': order.id,
                'name': order.template.name,
                'base_amount': float(base_amount),
                'patient_amount': float(patient_amount),
                'order_number': order.order_number,
                'status': order.status,
                'ordered_date': order.ordered_at.strftime('%Y-%m-%d')
            })
            lab_total += patient_amount

        # Process scan orders
        scan_items = []
        scan_total = Decimal('0.00')
        for order in pending_scans:
            base_amount = order.amount_charged or order.template.price

            if active_insurance and active_insurance.coverage_plan.is_radiology_covered(order.template):
                patient_amount = calculate_insurance_amount(
                    base_amount,
                    active_insurance.coverage_plan.radiology_coverage_percentage
                )
            else:
                patient_amount = base_amount

            scan_items.append({
                'id': order.id,
                'name': order.template.name,
                'base_amount': float(base_amount),
                'patient_amount': float(patient_amount),
                'order_number': order.order_number,
                'status': order.status,
                'ordered_date': order.ordered_at.strftime('%Y-%m-%d')
            })
            scan_total += patient_amount

        # Calculate grand total
        grand_total = drug_total + lab_total + scan_total

        return JsonResponse({
            'success': True,
            'patient': {
                'id': patient.id,
                'full_name': str(patient),
                'card_number': patient.card_number,
                'phone': getattr(patient, 'mobile', ''),
                'email': getattr(patient, 'email', ''),
                'age': patient.age() if hasattr(patient, 'age') and callable(patient.age) else '',
                'gender': getattr(patient, 'gender', ''),
            },
            'wallet': {
                'balance': float(wallet.amount),
                'formatted_balance': f'₦{wallet.amount:,.2f}'
            },
            'insurance': {
                'has_insurance': bool(active_insurance),
                'hmo_name': active_insurance.hmo.name if active_insurance else None,
                'plan_name': active_insurance.coverage_plan.name if active_insurance else None,
                'policy_number': active_insurance.policy_number if active_insurance else None,
            },
            'pending_payments': {
                'drugs': {
                    'items': drug_items,
                    'total': float(drug_total),
                    'count': len(drug_items)
                },
                'labs': {
                    'items': lab_items,
                    'total': float(lab_total),
                    'count': len(lab_items)
                },
                'scans': {
                    'items': scan_items,
                    'total': float(scan_total),
                    'count': len(scan_items)
                },
                'grand_total': float(grand_total),
                'formatted_grand_total': f'₦{grand_total:,.2f}'
            }
        })

    except PatientModel.DoesNotExist:
        return JsonResponse({
            'error': 'Patient not found with this card number'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'error': f'Error verifying patient: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def process_wallet_funding(request):
    """Process wallet funding and optional payments"""
    try:
        # Get form data
        patient_id = request.POST.get('patient_id')
        funding_amount = Decimal(request.POST.get('funding_amount', '0'))
        action_type = request.POST.get('action_type', 'fund_only')  # 'fund_only' or 'fund_and_pay'

        # Validate inputs
        if not patient_id:
            return JsonResponse({'error': 'Patient ID required'}, status=400)

        if funding_amount <= 0:
            return JsonResponse({'error': 'Funding amount must be greater than 0'}, status=400)

        patient = get_object_or_404(PatientModel, id=patient_id)
        wallet, created = PatientWalletModel.objects.get_or_create(
            patient=patient,
            defaults={'amount': Decimal('0.00')}
        )

        with transaction.atomic():
            # Add funds to wallet
            wallet.amount += funding_amount
            wallet.save()

            # Create wallet transaction record (if you have a transaction model)
            # WalletTransactionModel.objects.create(
            #     wallet=wallet,
            #     transaction_type='credit',
            #     amount=funding_amount,
            #     description=f'Wallet funding by {request.user.get_full_name()}',
            #     created_by=request.user
            # )

            if action_type == 'fund_only':
                messages.success(request, f'Successfully funded wallet with ₦{funding_amount:,.2f}')
                return JsonResponse({
                    'success': True,
                    'message': f'Wallet funded with ₦{funding_amount:,.2f}',
                    'new_balance': float(wallet.amount),
                    'redirect_url': reverse('patient_wallet_dashboard', args=[patient.id])
                })

            elif action_type == 'fund_and_pay':
                payment_type = request.POST.get('payment_type')
                selected_items = request.POST.getlist('selected_items[]')

                if not payment_type or not selected_items:
                    return JsonResponse({
                        'error': 'Payment type and items selection required'
                    }, status=400)

                # Redirect to appropriate payment page
                redirect_urls = {
                    'consultation': reverse('finance_consultation_patient_payment', args=[patient.id]),
                    'lab': reverse('finance_laboratory_patient_payment', args=[patient.id]),
                    'scan': reverse('finance_scan_patient_payment', args=[patient.id]),
                    'drug': reverse('finance_pharmacy_patient_payment', args=[patient.id]),
                }

                redirect_url = redirect_urls.get(payment_type)
                if not redirect_url:
                    return JsonResponse({'error': 'Invalid payment type'}, status=400)

                # Store selected items in session for payment processing
                request.session[f'selected_{payment_type}_items'] = selected_items

                messages.success(request, f'Wallet funded with ₦{funding_amount:,.2f}. Proceeding to payment...')
                return JsonResponse({
                    'success': True,
                    'message': f'Wallet funded. Redirecting to {payment_type} payment...',
                    'new_balance': float(wallet.amount),
                    'redirect_url': redirect_url
                })

    except PatientModel.DoesNotExist:
        return JsonResponse({'error': 'Patient not found'}, status=404)
    except ValueError:
        return JsonResponse({'error': 'Invalid funding amount'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Error processing funding: {str(e)}'}, status=500)


@login_required
def calculate_payment_total_ajax(request):
    """Calculate total based on selected items"""
    try:
        patient_id = request.GET.get('patient_id')
        selected_drugs = request.GET.getlist('drugs[]')
        selected_labs = request.GET.getlist('labs[]')
        selected_scans = request.GET.getlist('scans[]')

        if not patient_id:
            return JsonResponse({'error': 'Patient ID required'}, status=400)

        patient = get_object_or_404(PatientModel, id=patient_id)

        # Get active insurance
        active_insurance = None
        if hasattr(patient, 'insurance_policies'):
            active_insurance = patient.insurance_policies.filter(
                is_active=True,
                valid_to__gte=date.today()
            ).select_related('coverage_plan').first()

        def calculate_insurance_amount(base_amount, coverage_percentage):
            if coverage_percentage and coverage_percentage > 0:
                covered_amount = base_amount * (coverage_percentage / 100)
                return base_amount - covered_amount
            return base_amount

        total_amount = Decimal('0.00')

        # Calculate drug totals
        if selected_drugs:
            drug_orders = DrugOrderModel.objects.filter(
                id__in=selected_drugs,
                patient=patient
            ).select_related('drug')

            for order in drug_orders:
                base_amount = order.amount_charged or order.drug.selling_price
                if active_insurance and active_insurance.coverage_plan.is_drug_covered(order.drug):
                    patient_amount = calculate_insurance_amount(
                        base_amount,
                        active_insurance.coverage_plan.drug_coverage_percentage
                    )
                else:
                    patient_amount = base_amount
                total_amount += patient_amount

        # Calculate lab totals
        if selected_labs:
            lab_orders = LabTestOrderModel.objects.filter(
                id__in=selected_labs,
                patient=patient
            ).select_related('template')

            for order in lab_orders:
                base_amount = order.amount_charged or order.template.price
                if active_insurance and active_insurance.coverage_plan.is_lab_covered(order.template):
                    patient_amount = calculate_insurance_amount(
                        base_amount,
                        active_insurance.coverage_plan.lab_coverage_percentage
                    )
                else:
                    patient_amount = base_amount
                total_amount += patient_amount

        # Calculate scan totals
        if selected_scans:
            scan_orders = ScanOrderModel.objects.filter(
                id__in=selected_scans,
                patient=patient
            ).select_related('template')

            for order in scan_orders:
                base_amount = order.amount_charged or order.template.price
                if active_insurance and active_insurance.coverage_plan.is_radiology_covered(order.template):
                    patient_amount = calculate_insurance_amount(
                        base_amount,
                        active_insurance.coverage_plan.radiology_coverage_percentage
                    )
                else:
                    patient_amount = base_amount
                total_amount += patient_amount

        return JsonResponse({
            'success': True,
            'total_amount': float(total_amount),
            'formatted_total': f'₦{total_amount:,.2f}'
        })

    except PatientModel.DoesNotExist:
        return JsonResponse({'error': 'Patient not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': f'Error calculating total: {str(e)}'}, status=500)


@login_required
def patient_wallet_dashboard(request, patient_id):
    """Patient wallet dashboard showing balance and recent transactions"""
    patient = get_object_or_404(PatientModel, id=patient_id)
    wallet, created = PatientWalletModel.objects.get_or_create(
        patient=patient,
        defaults={'amount': Decimal('0.00')}
    )

    # Get recent transactions (if you have a transaction model)
    # recent_transactions = WalletTransactionModel.objects.filter(
    #     wallet=wallet
    # ).order_by('-created_at')[:20]

    context = {
        'patient': patient,
        'wallet': wallet,
        'wallet_balance': wallet.amount,
        # 'recent_transactions': recent_transactions,
    }

    return render(request, 'finance/wallet/dashboard.html', context)


@login_required
@require_http_methods(["POST"])
def process_wallet_payment(request):
    """Process payment from wallet for selected services"""
    try:
        patient_id = request.POST.get('patient_id')
        payment_type = request.POST.get('payment_type')
        selected_items = request.POST.getlist('selected_items[]')

        if not all([patient_id, payment_type, selected_items]):
            return JsonResponse({
                'error': 'Missing required payment information'
            }, status=400)

        patient = get_object_or_404(PatientModel, id=patient_id)
        wallet = get_object_or_404(PatientWalletModel, patient=patient)

        # Get active insurance
        active_insurance = patient.insurance_policies.filter(
            is_active=True,
            valid_to__gte=date.today()
        ).select_related('coverage_plan').first()

        def calculate_patient_amount(base_amount, coverage_percentage):
            if coverage_percentage and coverage_percentage > 0:
                covered_amount = base_amount * (coverage_percentage / 100)
                return base_amount - covered_amount
            return base_amount

        total_to_pay = Decimal('0.00')
        payment_items = []

        with transaction.atomic():
            # Process based on payment type
            if payment_type == 'drug':
                orders = DrugOrderModel.objects.filter(
                    id__in=selected_items,
                    patient=patient,
                    status='pending'
                ).select_related('drug')

                for order in orders:
                    base_amount = order.amount_charged or order.drug.selling_price

                    if active_insurance and active_insurance.coverage_plan.is_drug_covered(order.drug):
                        patient_amount = calculate_patient_amount(
                            base_amount,
                            active_insurance.coverage_plan.drug_coverage_percentage
                        )
                    else:
                        patient_amount = base_amount

                    total_to_pay += patient_amount
                    payment_items.append({
                        'order': order,
                        'amount': patient_amount
                    })

            elif payment_type == 'lab':
                orders = LabTestOrderModel.objects.filter(
                    id__in=selected_items,
                    patient=patient,
                    status='pending'
                ).select_related('template')

                for order in orders:
                    base_amount = order.amount_charged or order.template.price

                    if active_insurance and active_insurance.coverage_plan.is_lab_covered(order.template):
                        patient_amount = calculate_patient_amount(
                            base_amount,
                            active_insurance.coverage_plan.lab_coverage_percentage
                        )
                    else:
                        patient_amount = base_amount

                    total_to_pay += patient_amount
                    payment_items.append({
                        'order': order,
                        'amount': patient_amount
                    })

            elif payment_type == 'scan':
                orders = ScanOrderModel.objects.filter(
                    id__in=selected_items,
                    patient=patient,
                    status='pending'
                ).select_related('template')

                for order in orders:
                    base_amount = order.amount_charged or order.template.price

                    if active_insurance and active_insurance.coverage_plan.is_radiology_covered(order.template):
                        patient_amount = calculate_patient_amount(
                            base_amount,
                            active_insurance.coverage_plan.radiology_coverage_percentage
                        )
                    else:
                        patient_amount = base_amount

                    total_to_pay += patient_amount
                    payment_items.append({
                        'order': order,
                        'amount': patient_amount
                    })

            # Check if wallet has sufficient funds
            if wallet.amount < total_to_pay:
                return JsonResponse({
                    'error': f'Insufficient wallet balance. Available: ₦{wallet.amount:,.2f}, Required: ₦{total_to_pay:,.2f}'
                }, status=400)

            # Process payment
            wallet.amount -= total_to_pay
            wallet.save()

            # Update order statuses
            for item in payment_items:
                order = item['order']
                order.payment_status = True
                order.payment_date = timezone.now()
                order.payment_by = request.user

                if payment_type in ['lab', 'scan']:
                    order.status = 'paid'
                elif payment_type == 'drug':
                    order.status = 'paid'

                order.save()

            # Create payment record (if you have a payment model)
            # PaymentModel.objects.create(
            #     patient=patient,
            #     payment_type=payment_type,
            #     amount=total_to_pay,
            #     payment_method='wallet',
            #     processed_by=request.user,
            #     items_paid=selected_items
            # )

        messages.success(
            request,
            f'Payment of ₦{total_to_pay:,.2f} processed successfully from wallet. '
            f'New balance: ₦{wallet.amount:,.2f}'
        )

        return JsonResponse({
            'success': True,
            'message': f'Payment of ₦{total_to_pay:,.2f} processed successfully',
            'new_balance': float(wallet.amount),
            'formatted_balance': f'₦{wallet.amount:,.2f}',
            'redirect_url': reverse('wallet:patient_dashboard', args=[patient.id])
        })

    except Exception as e:
        return JsonResponse({
            'error': f'Error processing payment: {str(e)}'
        }, status=500)


@login_required
def finance_payment_select(request):
    """
    Initial payment selection page.
    The patient is verified by AJAX (finance_verify_patient_ajax) and the page
    will show radio options (consultation, drug, lab, scan) with counts & totals.
    """
    # GET only renders the page; verification happens client-side via AJAX.
    return render(request, 'finance/payment/select.html', {})


THIRTY_DAYS = 30

def _to_decimal(v):
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal('0.00')

def _quantize_money(d: Decimal) -> Decimal:
    return d.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


@login_required
@require_http_methods(["GET", "POST"])
def finance_pharmacy_patient_payment(request, patient_id):
    """
    Pharmacy (drug) payment UI + processing:
    - GET: render list of pending drug orders (last 30 days)
    - POST: process selected orders, deduct wallet, mark orders paid
    """
    patient = get_object_or_404(PatientModel, id=patient_id)
    thirty_days_ago = timezone.now() - timedelta(days=THIRTY_DAYS)

    if request.method == 'GET':
        # choose statuses that represent unpaid/pending in your app
        pending_drugs = DrugOrderModel.objects.filter(
            patient=patient,
            status__in=['pending'],
            ordered_at__gte=thirty_days_ago
        ).select_related('drug')

        # compute patient_amount for each order using the same logic you used in verify_patient_ajax
        # We'll attempt to detect active insurance similarly if you use the same related name
        active_insurance = None
        try:
            policies_qs = patient.insurance_policies.all()
        except Exception:
            policies_qs = patient.insurancepolicy_set.all()
        active_insurance = policies_qs.filter(is_active=True, valid_to__gte=timezone.now().date()).select_related('hmo', 'coverage_plan').first()

        items = []
        total = Decimal('0.00')
        for o in pending_drugs:
            base_amount = _to_decimal(o.drug.selling_price)
            # insurance logic, protection if coverage_plan missing methods
            patient_amount = base_amount
            if active_insurance and hasattr(active_insurance.coverage_plan, 'is_drug_covered'):
                try:
                    if active_insurance.coverage_plan.is_drug_covered(o.drug):
                        pct = _to_decimal(getattr(active_insurance.coverage_plan, 'drug_coverage_percentage', 0))
                        covered = (base_amount * (pct / Decimal('100')))
                        patient_amount = base_amount - covered
                except Exception:
                    patient_amount = base_amount
            patient_amount = _quantize_money(patient_amount)
            items.append({
                'id': o.id,
                'order_number': getattr(o, 'order_number', ''),
                'name': f"{getattr(o.drug, 'brand_name', '') or getattr(o.drug, 'generic_name', '')}",
                'quantity': getattr(o, 'quantity_ordered', 1),
                'base_amount': float(base_amount),
                'patient_amount': float(patient_amount),
                'formatted_patient_amount': f'₦{patient_amount:,.2f}',
                'status': o.status,
                'ordered_date': getattr(o, 'ordered_at').date().isoformat() if getattr(o, 'ordered_at', None) else ''
            })
            total += patient_amount

        context = {
            'patient': patient,
            'items': items,
            'total': _quantize_money(total),
        }
        return render(request, 'finance/payment/pharmacy.html', context)

    # POST - process payment
    selected_ids = request.POST.getlist('selected_items[]') or request.POST.getlist('selected_items')
    if not selected_ids:
        return JsonResponse({'success': False, 'error': 'No items selected for payment.'}, status=400)

    try:
        # re-fetch the selected orders and compute final sum (server-side authority)
        selected_orders = list(DrugOrderModel.objects.filter(id__in=selected_ids, patient=patient).select_related('drug'))
        if not selected_orders:
            return JsonResponse({'success': False, 'error': 'Selected orders not found.'}, status=404)

        total_amount = Decimal('0.00')
        thirty_days_ago = timezone.now() - timedelta(days=THIRTY_DAYS)
        # compute patient portion for each (same insurance logic as above)
        try:
            policies_qs = patient.insurance_policies.all()
        except Exception:
            policies_qs = patient.insurancepolicy_set.all()
        active_insurance = policies_qs.filter(is_active=True, valid_to__gte=timezone.now().date()).select_related('hmo', 'coverage_plan').first()

        for o in selected_orders:
            if getattr(o, 'ordered_at', timezone.now()) < thirty_days_ago:
                return JsonResponse({'success': False, 'error': 'One or more selected orders are older than 30 days and cannot be paid here.'}, status=400)
            base_amount = _to_decimal(o.drug.selling_price)
            patient_amount = base_amount
            if active_insurance and hasattr(active_insurance.coverage_plan, 'is_drug_covered'):
                try:
                    if active_insurance.coverage_plan.is_drug_covered(o.drug):
                        pct = _to_decimal(getattr(active_insurance.coverage_plan, 'drug_coverage_percentage', 0))
                        covered = (base_amount * (pct / Decimal('100')))
                        patient_amount = base_amount - covered
                except Exception:
                    patient_amount = base_amount
            total_amount += _quantize_money(patient_amount)

        # process wallet deduction inside a transaction with row lock
        with transaction.atomic():
            wallet_qs = PatientWalletModel.objects.select_for_update().filter(patient=patient)
            if wallet_qs.exists():
                wallet = wallet_qs.first()
            else:
                # create if missing
                wallet = PatientWalletModel.objects.create(patient=patient, amount=Decimal('0.00'))

            if wallet.amount < total_amount:
                shortfall = _quantize_money(total_amount - wallet.amount)
                return JsonResponse({
                    'success': False,
                    'error': 'Insufficient wallet balance.',
                    'shortfall': float(shortfall),
                    'formatted_shortfall': f'₦{shortfall:,.2f}'
                }, status=400)

            # deduct
            wallet.amount = _quantize_money(wallet.amount - total_amount)
            wallet.save()

            # mark orders as paid (update status field). Adjust status value to suit your app
            for o in selected_orders:
                o.status = 'paid'
                o.save(update_fields=['status'])

            # optionally create a wallet transaction record if you have such a model
            # try:
            #     WalletTransactionModel.objects.create(wallet=wallet, transaction_type='debit',
            #                                           amount=total_amount, created_by=request.user,
            #                                           description=f'Payment for drug orders: {",".join(selected_ids)}')
            # except Exception:
            #     pass

        # success
        return JsonResponse({
            'success': True,
            'message': f'Payment successful. ₦{total_amount:,.2f} deducted from wallet.',
            'new_balance': float(wallet.amount),
            'formatted_new_balance': f'₦{wallet.amount:,.2f}'
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error processing payment: {str(e)}'}, status=500)


# Lab and Scan views are very similar — we create a generic handler to reduce duplication

@login_required
@require_http_methods(["GET", "POST"])
def finance_generic_order_payment(request, patient_id, order_type):
    """
    Generic handler used for lab/scan payments.
    order_type: 'lab' or 'scan'
    """
    patient = get_object_or_404(PatientModel, id=patient_id)
    thirty_days_ago = timezone.now() - timedelta(days=THIRTY_DAYS)

    if order_type == 'lab':
        Model = LabTestOrderModel
        template = 'finance/payment/lab.html'
        coverage_fn_name = 'is_lab_covered'
        coverage_pct_attr = 'lab_coverage_percentage'
    elif order_type == 'scan':
        Model = ScanOrderModel
        template = 'finance/scan_payment.html'
        coverage_fn_name = 'is_radiology_covered'
        coverage_pct_attr = 'radiology_coverage_percentage'
    else:
        return HttpResponseBadRequest('Invalid order type')

    if request.method == 'GET':
        pending = Model.objects.filter(
            patient=patient,
            status__in=['pending', 'unpaid', 'awaiting_payment'],
            ordered_at__gte=thirty_days_ago
        ).select_related('template')

        # insurance lookup
        try:
            policies_qs = patient.insurance_policies.all()
        except Exception:
            policies_qs = patient.insurancepolicy_set.all()
        active_insurance = policies_qs.filter(is_active=True, valid_to__gte=timezone.now().date()).select_related('hmo', 'coverage_plan').first()

        items = []
        total = Decimal('0.00')
        for o in pending:
            base_amount = _to_decimal(getattr(o, 'amount_charged', None) or getattr(o, 'template').price)
            patient_amount = base_amount
            if active_insurance and hasattr(active_insurance.coverage_plan, coverage_fn_name):
                try:
                    coverage_fn = getattr(active_insurance.coverage_plan, coverage_fn_name)
                    if coverage_fn(o.template):
                        pct = _to_decimal(getattr(active_insurance.coverage_plan, coverage_pct_attr, 0))
                        covered = (base_amount * (pct / Decimal('100')))
                        patient_amount = base_amount - covered
                except Exception:
                    patient_amount = base_amount
            patient_amount = _quantize_money(patient_amount)
            items.append({
                'id': o.id,
                'order_number': getattr(o, 'order_number', ''),
                'name': getattr(o.template, 'name', ''),
                'base_amount': float(base_amount),
                'patient_amount': float(patient_amount),
                'formatted_patient_amount': f'₦{patient_amount:,.2f}',
                'status': o.status,
                'ordered_date': getattr(o, 'ordered_at').date().isoformat() if getattr(o, 'ordered_at', None) else ''
            })
            total += patient_amount

        context = {
            'patient': patient,
            'items': items,
            'total': _quantize_money(total),
            'order_type': order_type
        }
        return render(request, template, context)

    # POST - process payment for lab/scan
    selected_ids = request.POST.getlist('selected_items[]') or request.POST.getlist('selected_items')
    if not selected_ids:
        return JsonResponse({'success': False, 'error': 'No items selected for payment.'}, status=400)

    try:
        selected_orders = list(Model.objects.filter(id__in=selected_ids, patient=patient).select_related('template'))
        if not selected_orders:
            return JsonResponse({'success': False, 'error': 'Selected orders not found.'}, status=404)

        total_amount = Decimal('0.00')
        for o in selected_orders:
            if getattr(o, 'ordered_at', timezone.now()) < thirty_days_ago:
                return JsonResponse({'success': False, 'error': 'One or more selected orders are older than 30 days.'}, status=400)
            base_amount = _to_decimal(getattr(o, 'amount_charged', None) or getattr(o, 'template').price)
            patient_amount = base_amount
            # insurance
            try:
                policies_qs = patient.insurance_policies.all()
            except Exception:
                policies_qs = patient.insurancepolicy_set.all()
            active_insurance = policies_qs.filter(is_active=True, valid_to__gte=timezone.now().date()).select_related('hmo', 'coverage_plan').first()
            if active_insurance and hasattr(active_insurance.coverage_plan, coverage_fn_name):
                try:
                    coverage_fn = getattr(active_insurance.coverage_plan, coverage_fn_name)
                    if coverage_fn(o.template):
                        pct = _to_decimal(getattr(active_insurance.coverage_plan, coverage_pct_attr, 0))
                        covered = (base_amount * (pct / Decimal('100')))
                        patient_amount = base_amount - covered
                except Exception:
                    patient_amount = base_amount
            total_amount += _quantize_money(patient_amount)

        # process payment with wallet locking
        with transaction.atomic():
            wallet_qs = PatientWalletModel.objects.select_for_update().filter(patient=patient)
            if wallet_qs.exists():
                wallet = wallet_qs.first()
            else:
                wallet = PatientWalletModel.objects.create(patient=patient, amount=Decimal('0.00'))

            if wallet.amount < total_amount:
                shortfall = _quantize_money(total_amount - wallet.amount)
                return JsonResponse({
                    'success': False,
                    'error': 'Insufficient wallet balance.',
                    'shortfall': float(shortfall),
                    'formatted_shortfall': f'₦{shortfall:,.2f}'
                }, status=400)

            wallet.amount = _quantize_money(wallet.amount - total_amount)
            wallet.save()

            for o in selected_orders:
                o.status = 'paid'
                o.save(update_fields=['status'])

        return JsonResponse({
            'success': True,
            'message': 'Payment successful',
            'new_balance': float(wallet.amount),
            'formatted_new_balance': f'₦{wallet.amount:,.2f}'
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error processing payment: {str(e)}'}, status=500)


# convenience wrappers
@login_required
def finance_laboratory_patient_payment(request, patient_id):
    return finance_generic_order_payment(request, patient_id, 'lab')


@login_required
def finance_scan_patient_payment(request, patient_id):
    return finance_generic_order_payment(request, patient_id, 'scan')


@login_required
@require_http_methods(["GET", "POST"])
def finance_consultation_patient_payment(request, patient_id):
    """
    Consultation payment - this follows the consultation flow in create.html (consultation type -> fee -> pay).
    GET: Render consultation payment page (reusing your existing create.html flow)
    POST: Deduct wallet and mark fee/consultation as paid (server-side minimal handling)
    """
    patient = get_object_or_404(PatientModel, id=patient_id)

    if request.method == 'GET':
        # pass specializations (if you have Specialization model), else empty list
        try:
            from human_resource.models import SpecializationModel  # adjust import path
            specializations = SpecializationModel.objects.all()
        except Exception:
            specializations = []

        return render(request, 'finance/consultation_payment.html', {
            'patient': patient,
            'specializations': specializations
        })

    # POST: process consultation payment
    fee_id = request.POST.get('fee_structure') or request.POST.get('fee_structure_id')
    amount_paid = _to_decimal(request.POST.get('amount_paid') or request.POST.get('amount_due') or '0')

    if amount_paid <= 0:
        return JsonResponse({'success': False, 'error': 'Invalid payment amount.'}, status=400)

    try:
        with transaction.atomic():
            wallet_qs = PatientWalletModel.objects.select_for_update().filter(patient=patient)
            if wallet_qs.exists():
                wallet = wallet_qs.first()
            else:
                return JsonResponse({'success': False, 'error': 'Patient wallet not found.'}, status=404)

            if wallet.amount < amount_paid:
                shortfall = _quantize_money(amount_paid - wallet.amount)
                return JsonResponse({
                    'success': False,
                    'error': 'Insufficient wallet balance.',
                    'shortfall': float(shortfall),
                    'formatted_shortfall': f'₦{shortfall:,.2f}'
                }, status=400)

            wallet.amount = _quantize_money(wallet.amount - amount_paid)
            wallet.save()

            # here, mark fee/consultation as paid in your domain models (if you have a ConsultationAppointment model etc).
            # We'll try to mark a ConsultationFeeModel if it exists:
            try:
                from consultation.models import ConsultationFeeModel
                fee = ConsultationFeeModel.objects.get(id=fee_id)
                fee.status = 'paid'
                fee.save(update_fields=['status'])
            except Exception:
                # If there's no model or not found, we still consider the wallet deducted.
                fee = None

        return JsonResponse({
            'success': True,
            'message': 'Consultation payment successful.',
            'new_balance': float(wallet.amount),
            'formatted_new_balance': f'₦{wallet.amount:,.2f}'
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error processing payment: {str(e)}'}, status=500)
