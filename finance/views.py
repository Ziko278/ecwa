# views.py
from datetime import timedelta, date, datetime
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User
from django.contrib.messages.views import SuccessMessageMixin
from django.db import transaction
from django.forms import forms
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import now
from django.views.decorators.http import require_http_methods
from django.views.generic import CreateView, ListView, DetailView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q, Sum
from django.contrib import messages
from django.http import HttpResponse, JsonResponse, HttpResponseBadRequest
from django.template.loader import render_to_string

from admin_site.models import SiteInfoModel
from consultation.models import ConsultationFeeModel, SpecializationModel, PatientQueueModel
from finance.forms import FinanceSettingForm, ExpenseCategoryForm, QuotationReviewForm, QuotationItemForm, \
    SalaryStructureForm, StaffBankDetailForm, SalaryRecordForm, IncomeForm, IncomeCategoryForm, QuotationForm, \
    ExpenseForm
from finance.models import PatientTransactionModel, FinanceSettingModel, ExpenseCategory, Quotation, SalaryStructure, \
    StaffBankDetail, SalaryRecord, Income, IncomeCategory, QuotationItem, Expense
from human_resource.models import DepartmentModel, StaffModel
from human_resource.views import FlashFormErrorsMixin
from insurance.models import PatientInsuranceModel
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
    context = {
        'finance_setting': FinanceSettingModel.objects.first()
    }

    return render(request, 'finance/wallet/funding.html', context)


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
        payment_method = request.POST.get('payment_method', 'cash')
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

        patient_old_balance = wallet.amount

        with transaction.atomic():
            # Add funds to wallet
            wallet.amount += funding_amount
            wallet.save()

            patient_new_balance = wallet.amount

            PatientTransactionModel.objects.create(
                patient=patient,
                transaction_type='wallet_funding',
                transaction_direction='in',
                amount=funding_amount,
                old_balance=patient_old_balance,
                new_balance=patient_new_balance,
                payment_method=payment_method,
                received_by=request.user,
                status='completed',
                date=timezone.now().date()
            )

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

                if not payment_type:
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

    # Filter transactions for the patient
    patient_transactions = PatientTransactionModel.objects.filter(patient=patient)

    # Get the current month and year
    current_month = timezone.now().month
    current_year = timezone.now().year

    # Aggregate funded (IN) and spent (OUT) amounts for the current month
    monthly_summary = patient_transactions.filter(
        created_at__year=current_year,
        created_at__month=current_month
    ).aggregate(
        funded_amount=Sum('amount', filter=Q(transaction_direction='in')),
        spent_amount=Sum('amount', filter=Q(transaction_direction='out'))
    )

    # Use 0 if the sum is None (no transactions found)
    funded_amount = monthly_summary.get('funded_amount', Decimal('0.00')) or Decimal('0.00')
    spent_amount = monthly_summary.get('spent_amount', Decimal('0.00')) or Decimal('0.00')

    # Get recent transactions (e.g., last 20) for the patient
    recent_transactions = patient_transactions.order_by('-created_at')[:20]

    context = {
        'patient': patient,
        'wallet': wallet,
        'wallet_balance': wallet.amount,
        'recent_transactions': recent_transactions,
        'funded_amount': funded_amount,
        'spent_amount': spent_amount,
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
def finance_payment_select(request):
    """
    Initial payment selection page.
    The patient is verified by AJAX (finance_verify_patient_ajax) and the page
    will show radio options (consultation, drug, lab, scan) with counts & totals.
    """
    return render(request, 'finance/payment/select.html', {})


@login_required
def finance_verify_patient_ajax(request):
    """
    AJAX endpoint to verify patient and return pending payments summary
    """
    card_number = request.GET.get('card_number', '').strip()
    if not card_number:
        return JsonResponse({'success': False, 'error': 'Card number is required'})

    try:
        # Find patient by card number
        patient = PatientModel.objects.get(card_number=card_number)
    except PatientModel.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Patient not found with this card number'})

    # Get or create wallet
    try:
        wallet = patient.wallet
        has_wallet = True
        balance = float(wallet.amount)
        formatted_balance = f'₦{wallet.amount:,.2f}'
    except:
        # Create wallet if it doesn't exist
        from patient.models import PatientWalletModel
        wallet = PatientWalletModel.objects.create(patient=patient, amount=Decimal('0.00'))
        has_wallet = True
        balance = 0.00
        formatted_balance = '₦0.00'

    # Get active insurance
    active_insurance = None
    try:
        policies_qs = patient.insurance_policies.all()
    except:
        try:
            policies_qs = patient.insurancepolicy_set.all()
        except:
            policies_qs = PatientInsuranceModel.objects.none()

    active_insurance = policies_qs.filter(
        is_active=True,
        valid_to__gte=timezone.now().date()
    ).select_related('hmo', 'coverage_plan').first()

    # Calculate pending payments for last 30 days
    thirty_days_ago = timezone.now() - timedelta(days=THIRTY_DAYS)

    # Drugs
    pending_drugs = DrugOrderModel.objects.filter(
        patient=patient,
        status__in=['pending'],
        ordered_at__gte=thirty_days_ago
    ).select_related('drug')

    drug_total = Decimal('0.00')
    drug_count = 0
    for order in pending_drugs:
        base_amount = _to_decimal(order.drug.selling_price)
        patient_amount = base_amount

        if active_insurance and hasattr(active_insurance.coverage_plan, 'is_drug_covered'):
            try:
                if active_insurance.coverage_plan.is_drug_covered(order.drug):
                    pct = _to_decimal(getattr(active_insurance.coverage_plan, 'drug_coverage_percentage', 0))
                    covered = (base_amount * (pct / Decimal('100')))
                    patient_amount = base_amount - covered
            except Exception:
                patient_amount = base_amount

        drug_total += _quantize_money(patient_amount)
        drug_count += 1

    # Labs
    pending_labs = LabTestOrderModel.objects.filter(
        patient=patient,
        status__in=['pending', 'unpaid', 'awaiting_payment'],
        ordered_at__gte=thirty_days_ago
    ).select_related('template')

    lab_total = Decimal('0.00')
    lab_count = 0
    for order in pending_labs:
        base_amount = _to_decimal(getattr(order, 'amount_charged', None) or order.template.price)
        patient_amount = base_amount

        if active_insurance and hasattr(active_insurance.coverage_plan, 'is_lab_covered'):
            try:
                if active_insurance.coverage_plan.is_lab_covered(order.template):
                    pct = _to_decimal(getattr(active_insurance.coverage_plan, 'lab_coverage_percentage', 0))
                    covered = (base_amount * (pct / Decimal('100')))
                    patient_amount = base_amount - covered
            except Exception:
                patient_amount = base_amount

        lab_total += _quantize_money(patient_amount)
        lab_count += 1

    # Scans
    pending_scans = ScanOrderModel.objects.filter(
        patient=patient,
        status__in=['pending', 'unpaid', 'awaiting_payment'],
        ordered_at__gte=thirty_days_ago
    ).select_related('template')

    scan_total = Decimal('0.00')
    scan_count = 0
    for order in pending_scans:
        base_amount = _to_decimal(getattr(order, 'amount_charged', None) or order.template.price)
        patient_amount = base_amount

        if active_insurance and hasattr(active_insurance.coverage_plan, 'is_radiology_covered'):
            try:
                if active_insurance.coverage_plan.is_radiology_covered(order.template):
                    pct = _to_decimal(getattr(active_insurance.coverage_plan, 'radiology_coverage_percentage', 0))
                    covered = (base_amount * (pct / Decimal('100')))
                    patient_amount = base_amount - covered
            except Exception:
                patient_amount = base_amount

        scan_total += _quantize_money(patient_amount)
        scan_count += 1

    grand_total = drug_total + lab_total + scan_total

    return JsonResponse({
        'success': True,
        'patient': {
            'id': patient.id,
            'full_name': f'{patient.first_name} {patient.last_name}',
            'card_number': patient.card_number,
            'phone': getattr(patient, 'phone', ''),
            'age': getattr(patient, 'age', None),
            'patient_id': patient.card_number
        },
        'wallet': {
            'has_wallet': has_wallet,
            'balance': balance,
            'formatted_balance': formatted_balance
        },
        'insurance': {
            'has_insurance': active_insurance is not None,
            'hmo_name': active_insurance.hmo.name if active_insurance else None,
            'plan_name': active_insurance.coverage_plan.name if active_insurance else None
        },
        'pending_payments': {
            'drugs': {'count': drug_count, 'total': float(drug_total)},
            'labs': {'count': lab_count, 'total': float(lab_total)},
            'scans': {'count': scan_count, 'total': float(scan_total)},
            'grand_total': float(grand_total)
        }
    })


@login_required
def get_consultation_fees_ajax(request):
    """
    AJAX endpoint to get consultation fees for a specialization and patient
    """
    specialization_id = request.GET.get('specialization_id')
    patient_id = request.GET.get('patient_id')

    if not specialization_id or not patient_id:
        return JsonResponse({'success': False, 'error': 'Missing required parameters'})

    try:
        patient = PatientModel.objects.get(id=patient_id)
        specialization = SpecializationModel.objects.get(id=specialization_id)
    except (PatientModel.DoesNotExist, SpecializationModel.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'Patient or specialization not found'})

    # Check if patient has active insurance
    try:
        policies_qs = patient.insurance_policies.all()
    except:
        try:
            policies_qs = patient.insurancepolicy_set.all()
        except:
            policies_qs = PatientInsuranceModel.objects.none()

    active_insurance = policies_qs.filter(
        is_active=True,
        valid_to__gte=timezone.now().date()
    ).select_related('hmo', 'coverage_plan').first()

    # Get appropriate fee
    try:
        if active_insurance and active_insurance.coverage_plan.consultation_covered:
            # Try to get insurance-specific fee first
            fee = ConsultationFeeModel.objects.filter(
                specialization=specialization,
                patient_category='insurance',
                insurance=active_insurance.coverage_plan,
                is_active=True
            ).first()

            if not fee:
                # Fall back to regular insurance fee
                fee = ConsultationFeeModel.objects.filter(
                    specialization=specialization,
                    patient_category='insurance',
                    insurance__isnull=True,
                    is_active=True
                ).first()
        else:
            fee = None

        if not fee:
            # Get regular patient fee
            fee = ConsultationFeeModel.objects.filter(
                specialization=specialization,
                patient_category='regular',
                is_active=True
            ).first()

        if not fee:
            return JsonResponse({'success': False, 'error': 'No fee structure found for this specialization'})

        # Calculate patient amount after insurance
        base_amount = fee.amount
        patient_amount = base_amount

        if (active_insurance and
                active_insurance.coverage_plan.consultation_covered and
                fee.patient_category == 'insurance'):
            pct = _to_decimal(active_insurance.coverage_plan.consultation_coverage_percentage)
            covered = (base_amount * (pct / Decimal('100')))
            patient_amount = base_amount - covered

        return JsonResponse({
            'success': True,
            'fee': {
                'id': fee.id,
                'amount': float(patient_amount),
                'base_amount': float(base_amount),
                'formatted_amount': f'₦{patient_amount:,.2f}',
                'patient_category': fee.patient_category,
                'duration_minutes': 30,  # Default or from fee model
                'coverage_applied': patient_amount < base_amount
            }
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error retrieving fees: {str(e)}'})


@login_required
@require_http_methods(["GET", "POST"])
def finance_consultation_patient_payment(request, patient_id):
    """
    Consultation payment - handles both verification and payment processing
    """
    patient = get_object_or_404(PatientModel, id=patient_id)

    if request.method == 'GET':
        # Get specializations
        specializations = SpecializationModel.objects.all().order_by('name')

        return render(request, 'finance/payment/consultation.html', {
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
            # Get wallet with lock
            wallet_qs = PatientWalletModel.objects.select_for_update().filter(patient=patient)
            if wallet_qs.exists():
                wallet = wallet_qs.first()
            else:
                wallet = PatientWalletModel.objects.create(patient=patient, amount=Decimal('0.00'))

            if wallet.amount < amount_paid:
                shortfall = _quantize_money(amount_paid - wallet.amount)
                return JsonResponse({
                    'success': False,
                    'error': 'Insufficient wallet balance.',
                    'shortfall': float(shortfall),
                    'formatted_shortfall': f'₦{shortfall:,.2f}'
                }, status=400)

            # Deduct from wallet
            wallet.amount = _quantize_money(wallet.amount - amount_paid)
            wallet.save()

            payment = PatientTransactionModel.objects.create(
                patient=patient,
                transaction_type='consultation_payment',
                transaction_direction='out',
                amount=amount_paid,
                old_balance=wallet.amount + amount_paid,
                new_balance=wallet.amount,
                date=timezone.now().date(),
                received_by=request.user,
                payment_method='wallet',
                status='completed'
            )

            PatientQueueModel.objects.create(
                patient=patient,
                payment=payment,
                status='waiting_vitals'
            )

        return JsonResponse({
            'success': True,
            'message': 'Consultation payment successful.',
            'new_balance': float(wallet.amount),
            'formatted_new_balance': f'₦{wallet.amount:,.2f}',
            'redirect_url': reverse('patient_transaction_detail', kwargs={'pk': payment.id})
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error processing payment: {str(e)}'}, status=500)


# The existing pharmacy, lab, and scan payment views remain the same
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
            try:
                policies_qs = patient.insurancepolicy_set.all()
            except:
                policies_qs = PatientInsuranceModel.objects.none()
        active_insurance = policies_qs.filter(is_active=True, valid_to__gte=timezone.now().date()).select_related('hmo',
                                                                                                                  'coverage_plan').first()

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
                'ordered_date': getattr(o, 'ordered_at').date().isoformat() if getattr(o, 'ordered_at', None) else '',
                'insurance_covered': patient_amount < base_amount
            })
            total += patient_amount

        context = {
            'patient': patient,
            'items': items,
            'total': _quantize_money(total),
            'insurance': active_insurance
        }
        return render(request, 'finance/payment/pharmacy.html', context)

    # POST - process payment (existing logic remains the same)
    selected_ids = request.POST.getlist('selected_items[]') or request.POST.getlist('selected_items')
    if not selected_ids:
        return JsonResponse({'success': False, 'error': 'No items selected for payment.'}, status=400)

    try:
        # re-fetch the selected orders and compute final sum (server-side authority)
        selected_orders = list(
            DrugOrderModel.objects.filter(id__in=selected_ids, patient=patient).select_related('drug'))
        if not selected_orders:
            return JsonResponse({'success': False, 'error': 'Selected orders not found.'}, status=404)

        total_amount = Decimal('0.00')
        thirty_days_ago = timezone.now() - timedelta(days=THIRTY_DAYS)
        # compute patient portion for each (same insurance logic as above)
        try:
            policies_qs = patient.insurance_policies.all()
        except Exception:
            try:
                policies_qs = patient.insurancepolicy_set.all()
            except:
                policies_qs = PatientInsuranceModel.objects.none()
        active_insurance = policies_qs.filter(is_active=True, valid_to__gte=timezone.now().date()).select_related('hmo',
                                                                                                                  'coverage_plan').first()

        for o in selected_orders:
            if getattr(o, 'ordered_at', timezone.now()) < thirty_days_ago:
                return JsonResponse({'success': False,
                                     'error': 'One or more selected orders are older than 30 days and cannot be paid here.'},
                                    status=400)
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

            # Create transaction record
            try:

                payment = PatientTransactionModel.objects.create(
                    patient=patient,
                    transaction_type='drug_payment',
                    transaction_direction='out',
                    amount=total_amount,
                    old_balance=wallet.amount + total_amount,
                    new_balance=wallet.amount,
                    date=timezone.now().date(),
                    received_by=request.user,
                    payment_method='wallet',
                    status='completed'
                )
            except Exception:
                pass

        # success
        return JsonResponse({
            'success': True,
            'message': f'Payment successful. ₦{total_amount:,.2f} deducted from wallet.',
            'new_balance': float(wallet.amount),
            'formatted_new_balance': f'₦{wallet.amount:,.2f}',
            'redirect_url': reverse('patient_transaction_detail', kwargs={'pk': payment.pk}),
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error processing payment: {str(e)}'}, status=500)


# Lab and Scan views remain the same as in your original code
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
        transaction_type = 'lab_payment'
    elif order_type == 'scan':
        Model = ScanOrderModel
        template = 'finance/payment/scan.html'
        coverage_fn_name = 'is_radiology_covered'
        coverage_pct_attr = 'radiology_coverage_percentage'
        transaction_type = 'scan_payment'
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
            try:
                policies_qs = patient.insurancepolicy_set.all()
            except:
                policies_qs = PatientInsuranceModel.objects.none()
        active_insurance = policies_qs.filter(is_active=True, valid_to__gte=timezone.now().date()).select_related('hmo',
                                                                                                                  'coverage_plan').first()

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
                'ordered_date': getattr(o, 'ordered_at').date().isoformat() if getattr(o, 'ordered_at', None) else '',
                'insurance_covered': patient_amount < base_amount
            })
            total += patient_amount

        context = {
            'patient': patient,
            'items': items,
            'total': _quantize_money(total),
            'order_type': order_type,
            'insurance': active_insurance
        }
        return render(request, template, context)

    # POST - process payment for lab/scan (existing logic with transaction record)
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
                return JsonResponse({'success': False, 'error': 'One or more selected orders are older than 30 days.'},
                                    status=400)
            base_amount = _to_decimal(getattr(o, 'amount_charged', None) or getattr(o, 'template').price)
            patient_amount = base_amount
            # insurance
            try:
                policies_qs = patient.insurance_policies.all()
            except Exception:
                try:
                    policies_qs = patient.insurancepolicy_set.all()
                except:
                    policies_qs = PatientInsuranceModel.objects.none()
            active_insurance = policies_qs.filter(is_active=True, valid_to__gte=timezone.now().date()).select_related(
                'hmo', 'coverage_plan').first()
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

            # Create transaction record
            try:

                payment = PatientTransactionModel.objects.create(
                    patient=patient,
                    transaction_type=transaction_type,
                    transaction_direction='out',
                    amount=total_amount,
                    old_balance=wallet.amount + total_amount,
                    new_balance=wallet.amount,
                    date=timezone.now().date(),
                    received_by=request.user,
                    payment_method='wallet',
                    status='completed',
                )
            except Exception:
                pass

        return JsonResponse({
            'success': True,
            'message': 'Payment successful',
            'new_balance': float(wallet.amount),
            'formatted_new_balance': f'₦{wallet.amount:,.2f}',
            'redirect_url': reverse('patient_transaction_detail', kwargs={'pk': payment.pk})
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


class PatientTransactionListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = PatientTransactionModel
    template_name = "finance/payment/index.html"  # Assumed template path
    context_object_name = "transactions"
    permission_required = "finance.view_patienttransactionmodel"  # Replace 'app_name'
    paginate_by = 20  # Optional: Adds pagination

    def get_queryset(self):
        """
        Filters the queryset based on GET parameters from the URL.
        """
        # Eager load related models to prevent N+1 query issues
        qs = PatientTransactionModel.objects.select_related('patient', 'received_by')

        # Get filter parameters from the request
        start_date = self.request.GET.get("start_date")
        end_date = self.request.GET.get("end_date")
        search = self.request.GET.get("search")
        transaction_type = self.request.GET.get("transaction_type")
        transaction_direction = self.request.GET.get("transaction_direction")

        # Default to today's transactions if no date range is provided
        if not start_date and not end_date:
            today = now().date()
            qs = qs.filter(date=today)
        elif start_date and end_date:
            qs = qs.filter(date__range=[start_date, end_date])

        # Apply search filter for patient name or transaction ID
        if search:
            qs = qs.filter(
                Q(patient__full_name__icontains=search) |
                Q(transaction_id__icontains=search)
            )

        # Apply choice filters
        if transaction_type:
            qs = qs.filter(transaction_type=transaction_type)
        if transaction_direction:
            qs = qs.filter(transaction_direction=transaction_direction)

        return qs.order_by("-created_at")

    def get_context_data(self, **kwargs):
        """
        Adds summary data and filter choices to the template context.
        """
        context = super().get_context_data(**kwargs)
        queryset = context['object_list']  # Use the paginated queryset from the context

        # Determine timeframe for the page title
        start_date = self.request.GET.get("start_date")
        end_date = self.request.GET.get("end_date")

        if start_date and end_date:
            context['timeframe'] = f"from {start_date} to {end_date}"
        else:
            context['timeframe'] = "for Today"

        # Calculate total inflow and outflow using database aggregation for efficiency
        totals = queryset.aggregate(
            total_inflow=Sum('amount', filter=Q(transaction_direction='in')),
            total_outflow=Sum('amount', filter=Q(transaction_direction='out'))
        )
        context['total_inflow'] = totals['total_inflow'] or Decimal('0.00')
        context['total_outflow'] = totals['total_outflow'] or Decimal('0.00')

        # Pass transaction type choices to the template for the filter dropdown
        context['transaction_types'] = PatientTransactionModel.TRANSACTION_TYPE

        return context


class PatientTransactionDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    # Specifies the model this view will operate on.
    model = PatientTransactionModel

    # Points to the template file that will render the data.
    template_name = "finance/payment/detail.html"

    # Sets the variable name to be used in the template (e.g., {{ transaction }}).
    context_object_name = "transaction"

    # Defines the permission required to access this view.
    # Remember to replace 'app_name' with your actual Django app's name.
    permission_required = "app_name.view_patienttransactionmodel"

    def get_queryset(self):
        """
        Overrides the default queryset to optimize database queries.

        By using `select_related`, we fetch the related 'patient' and 'received_by'
        objects in the same database query as the transaction itself. This prevents
        additional database hits when the template accesses `{{ transaction.patient }}`
        or `{{ transaction.received_by }}`.
        """
        return super().get_queryset().select_related('patient', 'received_by')


def get_finance_setting_instance():
    """
    Helper function to load the singleton FinanceSettingModel instance.
    This uses the .load() classmethod defined on the model.
    """
    return FinanceSettingModel.objects.first()


# -------------------------
# Finance Setting Views
# -------------------------
class FinanceSettingCreateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    model = FinanceSettingModel
    form_class = FinanceSettingForm
    permission_required = 'finance.change_financesettingmodel'
    success_message = 'Finance Setting Created Successfully'
    template_name = 'finance/setting/create.html'

    def dispatch(self, request, *args, **kwargs):
        """
        If a setting object already exists, redirect to the edit page.
        This enforces the singleton pattern.
        """
        setting = get_finance_setting_instance()
        # The .load() method creates a default if none exists, so we check if its pk is not None.
        # If it has a pk other than the default 1, or has been saved before, it exists.
        # A simpler check might just be to see if we can find an object with pk=1.
        if FinanceSettingModel.objects.filter(pk=1).exists():
            return redirect('finance_setting_edit', pk=1)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('finance_setting_detail', kwargs={'pk': self.object.pk})


class FinanceSettingDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = FinanceSettingModel
    permission_required = 'finance.view_financesettingmodel'
    template_name = 'finance/setting/detail.html'
    context_object_name = "finance_setting"

    def get_object(self, queryset=None):
        """
        Always return the single, global instance of the finance settings.
        """
        return get_finance_setting_instance()


class FinanceSettingUpdateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    model = FinanceSettingModel
    form_class = FinanceSettingForm
    permission_required = 'finance.change_financesettingmodel'
    success_message = 'Finance Setting Updated Successfully'
    template_name = 'finance/setting/create.html' # Reuse the create template for editing

    def get_object(self, queryset=None):
        """
        Always return the single, global instance to be edited.
        """
        return get_finance_setting_instance()

    def get_success_url(self):
        return reverse('finance_setting_detail', kwargs={'pk': self.object.pk})


# -------------------------
# Expense Category Views (Simple - Same HTML Pattern)
# -------------------------
class ExpenseCategoryCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, CreateView
):
    model = ExpenseCategory
    permission_required = 'finance.add_expensecategory'
    form_class = ExpenseCategoryForm
    template_name = 'finance/expense_category/index.html'
    success_message = 'Expense Category Successfully Created'

    def get_success_url(self):
        return reverse('expense_category_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('expense_category_index'))
        return super().dispatch(request, *args, **kwargs)


class ExpenseCategoryListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ExpenseCategory
    permission_required = 'finance.view_expensecategory'
    template_name = 'finance/expense_category/index.html'
    context_object_name = "category_list"

    def get_queryset(self):
        return ExpenseCategory.objects.all().order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = ExpenseCategoryForm()
        return context


class ExpenseCategoryUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
):
    model = ExpenseCategory
    permission_required = 'finance.change_expensecategory'
    form_class = ExpenseCategoryForm
    template_name = 'finance/expense_category/index.html'
    success_message = 'Expense Category Successfully Updated'

    def get_success_url(self):
        return reverse('expense_category_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('expense_category_index'))
        return super().dispatch(request, *args, **kwargs)


class ExpenseCategoryDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = ExpenseCategory
    permission_required = 'finance.delete_expensecategory'
    template_name = 'finance/expense_category/delete.html'
    context_object_name = "category"
    success_message = 'Expense Category Successfully Deleted'

    def get_success_url(self):
        return reverse('expense_category_index')


# -------------------------
# Quotation Views
# -------------------------
class QuotationListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Quotation
    permission_required = 'finance.view_quotation'
    template_name = 'finance/quotation/index.html'
    context_object_name = "quotation_list"
    paginate_by = 20

    def get_queryset(self):
        queryset = Quotation.objects.select_related(
            'category', 'department', 'requested_by'
        ).prefetch_related('items').order_by('-created_at')

        # Filter by status if provided
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)

        # Search functionality
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(quotation_number__icontains=search) |
                Q(title__icontains=search) |
                Q(requested_by__first_name__icontains=search) |
                Q(requested_by__last_name__icontains=search)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = Quotation.STATUS_CHOICES
        context['current_status'] = self.request.GET.get('status', '')
        context['search_query'] = self.request.GET.get('search', '')
        return context


class QuotationCreateSelfView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Quotation
    permission_required = 'finance.add_quotation_self'
    form_class = QuotationForm
    template_name = 'finance/quotation/create_self.html'
    success_message = 'Quotation Successfully Created'

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Hide requested_by field and set to current user's staff
        if 'requested_by' in form.fields:
            form.fields['requested_by'].widget = forms.HiddenInput()
            try:
                staff = self.request.user.staffmodel
                form.fields['requested_by'].initial = staff
            except:
                messages.error(self.request, 'Staff profile not found for current user')
        return form

    def form_valid(self, form):
        try:
            form.instance.requested_by = self.request.user.staffmodel
            form.instance.created_by = self.request.user  # Track who created it
        except:
            messages.error(self.request, 'Staff profile not found for current user')
            return self.form_invalid(form)

        response = super().form_valid(form)

        # Handle continue editing
        if 'save_and_continue' in self.request.POST:
            return redirect('quotation_edit_self', pk=self.object.pk)

        return response

    def get_success_url(self):
        return reverse('quotation_detail', kwargs={'pk': self.object.pk})


class QuotationCreateOthersView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Quotation
    permission_required = 'finance.add_quotation_others'
    form_class = QuotationForm
    template_name = 'finance/quotation/create_others.html'
    success_message = 'Quotation Successfully Created'

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Filter requested_by to staff in current user's department
        if 'requested_by' in form.fields:
            try:
                user_dept = self.request.user.staffmodel.department
                form.fields['requested_by'].queryset = StaffModel.objects.filter(
                    department=user_dept, is_active=True
                )
            except:
                form.fields['requested_by'].queryset = StaffModel.objects.filter(is_active=True)
        return form

    def form_valid(self, form):
        form.instance.created_by = self.request.user  # Track who created it
        response = super().form_valid(form)

        # Handle continue editing
        if 'save_and_continue' in self.request.POST:
            return redirect('quotation_edit_others', pk=self.object.pk)

        return response

    def get_success_url(self):
        return reverse('quotation_detail', kwargs={'pk': self.object.pk})


class QuotationUpdateSelfView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Quotation
    permission_required = 'finance.change_quotation_self'
    form_class = QuotationForm
    template_name = 'finance/quotation/edit_self.html'
    success_message = 'Quotation Successfully Updated'

    def get_queryset(self):
        # Only allow editing own quotations
        try:
            return Quotation.objects.filter(requested_by=self.request.user.staffmodel)
        except:
            return Quotation.objects.none()

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Hide requested_by field
        if 'requested_by' in form.fields:
            form.fields['requested_by'].widget = forms.HiddenInput()
        return form

    def form_valid(self, form):
        response = super().form_valid(form)

        if 'save_and_continue' in self.request.POST:
            return redirect('quotation_edit_self', pk=self.object.pk)

        return response

    def get_success_url(self):
        return reverse('quotation_detail', kwargs={'pk': self.object.pk})


class QuotationUpdateOthersView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Quotation
    permission_required = 'finance.change_quotation_others'
    form_class = QuotationForm
    template_name = 'finance/quotation/edit_others.html'
    success_message = 'Quotation Successfully Updated'

    def form_valid(self, form):
        response = super().form_valid(form)

        if 'save_and_continue' in self.request.POST:
            return redirect('quotation_edit_others', pk=self.object.pk)

        return response

    def get_success_url(self):
        return reverse('quotation_detail', kwargs={'pk': self.object.pk})


class QuotationDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Quotation
    permission_required = 'finance.view_quotation'
    template_name = 'finance/quotation/detail.html'
    context_object_name = "quotation"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['items'] = self.object.items.all()
        context['review_form'] = QuotationReviewForm()
        context['can_dept_review'] = (
                self.request.user.has_perm('finance.review_quotation_dept') and
                self.object.status in ['DRAFT', 'DEPT_QUERY']
        )
        context['can_general_review'] = (
                self.request.user.has_perm('finance.review_quotation_general') and
                self.object.status in ['DEPT_APPROVED', 'GENERAL_QUERY']
        )
        context['can_collect_money'] = (
                self.request.user.has_perm('finance.collect_quotation_money') and
                self.object.status == 'GENERAL_APPROVED'
        )
        return context


# -------------------------
# Quotation Approval Views
# -------------------------
class QuotationDeptReviewView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Quotation
    permission_required = 'finance.review_quotation_dept'
    form_class = QuotationReviewForm
    template_name = 'finance/quotation/dept_review.html'

    def get_queryset(self):
        return Quotation.objects.filter(status__in=['DRAFT', 'DEPT_QUERY'])

    def form_valid(self, form):
        action = form.cleaned_data.get('action')
        comments = form.cleaned_data.get('comments')

        if action == 'approve':
            self.object.status = 'GENERAL_PENDING'
        elif action == 'reject':
            self.object.status = 'DEPT_REJECTED'
        else:  # query
            self.object.status = 'DEPT_QUERY'

        self.object.dept_reviewed_by = self.request.user
        self.object.dept_reviewed_at = timezone.now()
        self.object.dept_comments = comments
        self.object.save()

        messages.success(self.request, f'Quotation {action}d successfully')
        return redirect('quotation_detail', pk=self.object.pk)


class QuotationGeneralReviewView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Quotation
    permission_required = 'finance.review_quotation_general'
    form_class = QuotationReviewForm
    template_name = 'finance/quotation/general_review.html'

    def get_queryset(self):
        return Quotation.objects.filter(status__in=['GENERAL_PENDING', 'GENERAL_QUERY'])

    def form_valid(self, form):
        action = form.cleaned_data.get('action')
        comments = form.cleaned_data.get('comments')

        if action == 'approve':
            self.object.status = 'GENERAL_APPROVED'
        elif action == 'reject':
            self.object.status = 'GENERAL_REJECTED'
        else:  # query
            self.object.status = 'GENERAL_QUERY'

        self.object.general_reviewed_by = self.request.user
        self.object.general_reviewed_at = timezone.now()
        self.object.general_comments = comments
        self.object.save()

        messages.success(self.request, f'Quotation {action}d successfully')
        return redirect('quotation_detail', pk=self.object.pk)


@login_required
@permission_required('finance.collect_quotation_money')
def quotation_collect_money(request, pk):
    quotation = get_object_or_404(Quotation, pk=pk)

    if quotation.status != 'GENERAL_APPROVED':
        messages.error(request, 'Only approved quotations can have money collected')
        return redirect('quotation_detail', pk=pk)

    if request.method == 'POST':
        quotation.status = 'MONEY_COLLECTED'
        quotation.collected_by = request.user
        quotation.collected_at = timezone.now()
        quotation.save()

        messages.success(request, 'Money collection recorded successfully')
        return redirect('quotation_detail', pk=pk)

    return render(request, 'finance/quotation/collect_money.html', {'quotation': quotation})


# -------------------------
# AJAX Views for Quotation Items
# -------------------------
@login_required
@permission_required('finance.add_quotationitem')
def quotation_item_create_ajax(request, quotation_pk):
    if request.method == 'POST':
        quotation = get_object_or_404(Quotation, pk=quotation_pk)
        form = QuotationItemForm(request.POST)

        if form.is_valid():
            item = form.save(commit=False)
            item.quotation = quotation
            item.save()

            return JsonResponse({
                'success': True,
                'item': {
                    'id': item.id,
                    'description': item.description,
                    'quantity': item.quantity,
                    'unit_price': str(item.unit_price),
                    'total_price': str(item.total_price)
                }
            })
        else:
            return JsonResponse({'success': False, 'errors': form.errors})

    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
@permission_required('finance.change_quotationitem')
def quotation_item_update_ajax(request, item_pk):
    if request.method == 'POST':
        item = get_object_or_404(QuotationItem, pk=item_pk)
        form = QuotationItemForm(request.POST, instance=item)

        if form.is_valid():
            item = form.save()
            return JsonResponse({
                'success': True,
                'item': {
                    'id': item.id,
                    'description': item.description,
                    'quantity': item.quantity,
                    'unit_price': str(item.unit_price),
                    'total_price': str(item.total_price)
                }
            })
        else:
            return JsonResponse({'success': False, 'errors': form.errors})

    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
@permission_required('finance.delete_quotationitem')
def quotation_item_delete_ajax(request, item_pk):
    if request.method == 'POST':
        item = get_object_or_404(QuotationItem, pk=item_pk)
        item.delete()
        return JsonResponse({'success': True})

    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
def quotation_items_get_ajax(request, quotation_pk):
    quotation = get_object_or_404(Quotation, pk=quotation_pk)
    items = quotation.items.all()

    items_data = [{
        'id': item.id,
        'description': item.description,
        'quantity': item.quantity,
        'unit_price': str(item.unit_price),
        'total_price': str(item.total_price)
    } for item in items]

    return JsonResponse({'items': items_data})


# -------------------------
# Expense Views
# -------------------------
class ExpenseListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Expense
    permission_required = 'finance.view_expense'
    template_name = 'finance/expense/index.html'
    context_object_name = "expense_list"
    paginate_by = 20

    def get_queryset(self):
        queryset = Expense.objects.select_related(
            'category', 'department', 'paid_by', 'quotation'
        ).order_by('-date')

        # Filter functionality
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category_id=category)

        department = self.request.GET.get('department')
        if department:
            queryset = queryset.filter(department_id=department)

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(expense_number__icontains=search) |
                Q(title__icontains=search)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = ExpenseCategory.objects.all()
        context['departments'] = DepartmentModel.objects.all()
        context['total_amount'] = self.get_queryset().aggregate(Sum('amount'))['amount__sum'] or 0
        return context


class ExpenseCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Expense
    permission_required = 'finance.add_expense'
    form_class = ExpenseForm
    template_name = 'finance/expense/create.html'
    success_message = 'Expense Successfully Created'

    def get_success_url(self):
        return reverse('expense_detail', kwargs={'pk': self.object.pk})


class ExpenseUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Expense
    permission_required = 'finance.change_expense'
    form_class = ExpenseForm
    template_name = 'finance/expense/edit.html'
    success_message = 'Expense Successfully Updated'

    def get_success_url(self):
        return reverse('expense_detail', kwargs={'pk': self.object.pk})


class ExpenseDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Expense
    permission_required = 'finance.view_expense'
    template_name = 'finance/expense/detail.html'
    context_object_name = "expense"


# -------------------------
# Income Category Views (Simple - Same HTML Pattern)
# -------------------------
class IncomeCategoryCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, CreateView
):
    model = IncomeCategory
    permission_required = 'finance.add_incomecategory'
    form_class = IncomeCategoryForm
    template_name = 'finance/income_category/index.html'
    success_message = 'Income Category Successfully Created'

    def get_success_url(self):
        return reverse('income_category_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('income_category_index'))
        return super().dispatch(request, *args, **kwargs)


class IncomeCategoryListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = IncomeCategory
    permission_required = 'finance.view_incomecategory'
    template_name = 'finance/income_category/index.html'
    context_object_name = "category_list"

    def get_queryset(self):
        return IncomeCategory.objects.all().order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = IncomeCategoryForm()
        return context


class IncomeCategoryUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
):
    model = IncomeCategory
    permission_required = 'finance.change_incomecategory'
    form_class = IncomeCategoryForm
    template_name = 'finance/income_category/index.html'
    success_message = 'Income Category Successfully Updated'

    def get_success_url(self):
        return reverse('income_category_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('income_category_index'))
        return super().dispatch(request, *args, **kwargs)


class IncomeCategoryDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = IncomeCategory
    permission_required = 'finance.delete_incomecategory'
    template_name = 'finance/income_category/delete.html'
    context_object_name = "category"
    success_message = 'Income Category Successfully Deleted'

    def get_success_url(self):
        return reverse('income_category_index')


# -------------------------
# Income Views
# -------------------------
class IncomeListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Income
    permission_required = 'finance.view_income'
    template_name = 'finance/income/index.html'
    context_object_name = "income_list"
    paginate_by = 20

    def get_queryset(self):
        queryset = Income.objects.select_related(
            'category', 'department', 'received_by'
        ).order_by('-date')

        # Filter functionality
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category_id=category)

        department = self.request.GET.get('department')
        if department:
            queryset = queryset.filter(department_id=department)

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(income_number__icontains=search) |
                Q(title__icontains=search) |
                Q(source__icontains=search)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = IncomeCategory.objects.all()
        context['departments'] = DepartmentModel.objects.all()
        context['total_amount'] = self.get_queryset().aggregate(Sum('amount'))['amount__sum'] or 0
        return context


class IncomeCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Income
    permission_required = 'finance.add_income'
    form_class = IncomeForm
    template_name = 'finance/income/create.html'
    success_message = 'Income Successfully Created'

    def get_success_url(self):
        return reverse('income_detail', kwargs={'pk': self.object.pk})


class IncomeUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Income
    permission_required = 'finance.change_income'
    form_class = IncomeForm
    template_name = 'finance/income/edit.html'
    success_message = 'Income Successfully Updated'

    def get_success_url(self):
        return reverse('income_detail', kwargs={'pk': self.object.pk})


class IncomeDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Income
    permission_required = 'finance.view_income'
    template_name = 'finance/income/detail.html'
    context_object_name = "income"


# -------------------------
# Staff Bank Detail Views (Simple - Same HTML Pattern)
# -------------------------
class StaffBankDetailCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, CreateView
):
    model = StaffBankDetail
    permission_required = 'finance.add_staffbankdetail'
    form_class = StaffBankDetailForm
    template_name = 'finance/staff_bank/index.html'
    success_message = 'Bank Detail Successfully Created'

    def get_success_url(self):
        return reverse('staff_bank_detail_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('staff_bank_detail_index'))
        return super().dispatch(request, *args, **kwargs)


class StaffBankDetailListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = StaffBankDetail
    permission_required = 'finance.view_staffbankdetail'
    template_name = 'finance/staff_bank/index.html'
    context_object_name = "bank_detail_list"

    def get_queryset(self):
        return StaffBankDetail.objects.select_related('staff').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = StaffBankDetailForm()
        return context


class StaffBankDetailUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
):
    model = StaffBankDetail
    permission_required = 'finance.change_staffbankdetail'
    form_class = StaffBankDetailForm
    template_name = 'finance/staff_bank/index.html'
    success_message = 'Bank Detail Successfully Updated'

    def get_success_url(self):
        return reverse('staff_bank_detail_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('staff_bank_detail_index'))
        return super().dispatch(request, *args, **kwargs)


class StaffBankDetailDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = StaffBankDetail
    permission_required = 'finance.delete_staffbankdetail'
    template_name = 'finance/staff_bank/delete.html'
    context_object_name = "bank_detail"
    success_message = 'Bank Detail Successfully Deleted'

    def get_success_url(self):
        return reverse('staff_bank_detail_index')


# -------------------------
# Salary Structure Views
# -------------------------
class SalaryStructureListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = SalaryStructure
    permission_required = 'finance.view_salarystructure'
    template_name = 'finance/salary_structure/index.html'
    context_object_name = "salary_structure_list"

    def get_queryset(self):
        return SalaryStructure.objects.select_related('staff').order_by('-created_at')


class SalaryStructureCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = SalaryStructure
    permission_required = 'finance.add_salarystructure'
    form_class = SalaryStructureForm
    template_name = 'finance/salary_structure/create.html'
    success_message = 'Salary Structure Successfully Created'

    def get_success_url(self):
        return reverse('salary_structure_detail', kwargs={'pk': self.object.pk})


class SalaryStructureUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = SalaryStructure
    permission_required = 'finance.change_salarystructure'
    form_class = SalaryStructureForm
    template_name = 'finance/salary_structure/edit.html'
    success_message = 'Salary Structure Successfully Updated'

    def get_success_url(self):
        return reverse('salary_structure_detail', kwargs={'pk': self.object.pk})


class SalaryStructureDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = SalaryStructure
    permission_required = 'finance.view_salarystructure'
    template_name = 'finance/salary_structure/detail.html'
    context_object_name = "salary_structure"


# -------------------------
# Salary Record Views
# -------------------------
class SalaryRecordListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = SalaryRecord
    permission_required = 'finance.view_salaryrecord'
    template_name = 'finance/salary_record/index.html'
    context_object_name = "salary_record_list"
    paginate_by = 20

    def get_queryset(self):
        queryset = SalaryRecord.objects.select_related('staff').order_by('-year', '-month')

        # Filter by year/month
        year = self.request.GET.get('year')
        month = self.request.GET.get('month')
        if year:
            queryset = queryset.filter(year=year)
        if month:
            queryset = queryset.filter(month=month)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['years'] = range(2020, 2031)
        context['months'] = [(i, f'{i:02d}') for i in range(1, 13)]
        context['current_year'] = datetime.now().year
        context['current_month'] = datetime.now().month
        return context


class SalaryRecordCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = SalaryRecord
    permission_required = 'finance.add_salaryrecord'
    form_class = SalaryRecordForm
    template_name = 'finance/salary_record/create.html'
    success_message = 'Salary Record Successfully Created'

    def form_valid(self, form):
        # Auto-populate from salary structure
        staff = form.cleaned_data['staff']
        try:
            salary_structure = SalaryStructure.objects.get(staff=staff, is_active=True)
            form.instance.basic_salary = salary_structure.basic_salary
            form.instance.housing_allowance = salary_structure.housing_allowance
            form.instance.transport_allowance = salary_structure.transport_allowance
            form.instance.medical_allowance = salary_structure.medical_allowance
            form.instance.other_allowances = salary_structure.other_allowances

            # Calculate tax and pension if not provided
            if not form.instance.tax_amount:
                form.instance.tax_amount = salary_structure.tax_amount
            if not form.instance.pension_amount:
                form.instance.pension_amount = salary_structure.pension_amount

        except SalaryStructure.DoesNotExist:
            messages.error(self.request, 'No active salary structure found for this staff member')
            return self.form_invalid(form)

        return super().form_valid(form)

    def get_success_url(self):
        return reverse('salary_record_detail', kwargs={'pk': self.object.pk})


class SalaryRecordUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = SalaryRecord
    permission_required = 'finance.change_salaryrecord'
    form_class = SalaryRecordForm
    template_name = 'finance/salary_record/edit.html'
    success_message = 'Salary Record Successfully Updated'

    def get_success_url(self):
        return reverse('salary_record_detail', kwargs={'pk': self.object.pk})


class SalaryRecordDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = SalaryRecord
    permission_required = 'finance.view_salaryrecord'
    template_name = 'finance/salary_record/detail.html'
    context_object_name = "salary_record"


@login_required
@permission_required('finance.change_salaryrecord')
def salary_record_pay(request, pk):
    """Mark a salary record as paid"""
    salary_record = get_object_or_404(SalaryRecord, pk=pk)

    if salary_record.is_paid:
        messages.warning(request, 'This salary record is already marked as paid')
        return redirect('salary_record_detail', pk=pk)

    if request.method == 'POST':
        salary_record.is_paid = True
        salary_record.paid_date = date.today()
        salary_record.paid_by = request.user
        salary_record.save()

        messages.success(request, f'Salary payment recorded for {salary_record.staff.get_full_name()}')
        return redirect('salary_record_detail', pk=pk)

    return render(request, 'finance/salary_record/pay.html', {'salary_record': salary_record})


@login_required
@permission_required('finance.add_salaryrecord')
def bulk_salary_generation(request):
    """Generate salary records for all staff for a specific month/year"""
    if request.method == 'POST':
        month = int(request.POST.get('month'))
        year = int(request.POST.get('year'))

        # Get all staff with active salary structures
        active_structures = SalaryStructure.objects.filter(is_active=True).select_related('staff')

        created_count = 0
        errors = []

        with transaction.atomic():
            for structure in active_structures:
                # Check if salary record already exists
                existing = SalaryRecord.objects.filter(
                    staff=structure.staff, month=month, year=year
                ).exists()

                if existing:
                    errors.append(f'Record already exists for {structure.staff.get_full_name()}')
                    continue

                # Create salary record
                SalaryRecord.objects.create(
                    staff=structure.staff,
                    month=month,
                    year=year,
                    basic_salary=structure.basic_salary,
                    housing_allowance=structure.housing_allowance,
                    transport_allowance=structure.transport_allowance,
                    medical_allowance=structure.medical_allowance,
                    other_allowances=structure.other_allowances,
                    tax_amount=structure.tax_amount,
                    pension_amount=structure.pension_amount,
                    gross_salary=structure.gross_salary,
                    net_salary=structure.net_salary,
                )
                created_count += 1

        if created_count > 0:
            messages.success(request, f'Successfully generated {created_count} salary records')

        for error in errors:
            messages.warning(request, error)

        return redirect('salary_record_index')

    context = {
        'years': range(2020, 2031),
        'months': [(i, f'{i:02d}') for i in range(1, 13)],
        'current_year': datetime.now().year,
        'current_month': datetime.now().month,
        'staff_count': SalaryStructure.objects.filter(is_active=True).count()
    }

    return render(request, 'finance/salary_record/bulk_generate.html', context)


# -------------------------
# AJAX Helper Views
# -------------------------
@login_required
def get_staff_salary_structure_ajax(request, staff_id):
    """Get salary structure details for a staff member"""
    try:
        staff = User.objects.get(id=staff_id)
        salary_structure = SalaryStructure.objects.get(staff=staff, is_active=True)

        return JsonResponse({
            'success': True,
            'data': {
                'basic_salary': str(salary_structure.basic_salary),
                'housing_allowance': str(salary_structure.housing_allowance),
                'transport_allowance': str(salary_structure.transport_allowance),
                'medical_allowance': str(salary_structure.medical_allowance),
                'other_allowances': str(salary_structure.other_allowances),
                'gross_salary': str(salary_structure.gross_salary),
                'tax_amount': str(salary_structure.tax_amount),
                'pension_amount': str(salary_structure.pension_amount),
                'net_salary': str(salary_structure.net_salary),
            }
        })
    except (User.DoesNotExist, SalaryStructure.DoesNotExist):
        return JsonResponse({
            'success': False,
            'error': 'No active salary structure found for this staff member'
        })