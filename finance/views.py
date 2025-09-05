# views.py
from datetime import timedelta, date, datetime
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User
from django.contrib.messages.views import SuccessMessageMixin
from django.db import transaction
from django import forms
from django.db.models.functions import TruncMonth
from django.forms import modelformset_factory
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import now
from django.views.decorators.http import require_http_methods
from django.views.generic import CreateView, ListView, DetailView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q, Sum, Avg, F, Count
from django.contrib import messages
from django.http import HttpResponse, JsonResponse, HttpResponseBadRequest
from django.template.loader import render_to_string
import openpyxl
from openpyxl.styles import Font
from admin_site.models import SiteInfoModel
from consultation.models import ConsultationFeeModel, SpecializationModel, PatientQueueModel
from finance.forms import FinanceSettingForm, ExpenseCategoryForm, QuotationReviewForm, QuotationItemForm, \
    SalaryStructureForm, StaffBankDetailForm, IncomeForm, IncomeCategoryForm, QuotationForm, \
    ExpenseForm, PaysheetRowForm, MoneyRemittanceForm
from finance.models import PatientTransactionModel, FinanceSettingModel, ExpenseCategory, Quotation, SalaryStructure, \
    StaffBankDetail, SalaryRecord, Income, IncomeCategory, QuotationItem, Expense, MoneyRemittance
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
                staff = self.request.user.user_staff_profile.staff
                form.fields['requested_by'].initial = staff
            except:
                messages.error(self.request, 'Staff profile not found for current user')
        return form

    def form_valid(self, form):
        try:
            form.instance.requested_by = self.request.user.user_staff_profile.staff
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
                user_dept = self.request.user.user_staff_profile.staff.department
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
            return Quotation.objects.filter(requested_by=self.request.user.user_staff_profile.staff)
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
            'category', 'department', 'paid_by'
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
@login_required
@permission_required('finance.add_salaryrecord')
def process_payroll_view(request):
    """
    An interactive view to manage the payroll for a specific month and year.
    Lists all staff with active salary structures and allows for inline editing.
    """
    # 1. Determine the period to process from GET parameters or use current month/year
    current_year = datetime.now().year
    current_month = datetime.now().month

    try:
        year = int(request.GET.get('year', current_year))
        month = int(request.GET.get('month', current_month))
    except (ValueError, TypeError):
        year = current_year
        month = current_month

    # 2. Get all staff who should be on the paysheet (i.e., have an active structure)
    staff_with_structures = StaffModel.objects.filter(salary_structure__is_active=True).select_related(
        'salary_structure')

    # 3. For each staff member, ensure a SalaryRecord exists for the period.
    # This automatically creates missing records, replacing the need for bulk generation.
    for staff in staff_with_structures:
        structure = staff.salary_structure
        record, created = SalaryRecord.objects.get_or_create(
            staff=staff,
            year=year,
            month=month,
            # 'defaults' are only used if a new record is being created
            defaults={
                'basic_salary': structure.basic_salary,
                'housing_allowance': structure.housing_allowance,
                'transport_allowance': structure.transport_allowance,
                'medical_allowance': structure.medical_allowance,
                'other_allowances': structure.other_allowances,
                'tax_amount': structure.tax_amount,
                'pension_amount': structure.pension_amount,
            }
        )

    # 4. Create a Formset. This is a collection of forms for our editable table.
    queryset = SalaryRecord.objects.filter(year=year, month=month, staff__in=staff_with_structures).select_related(
        'staff')
    PaysheetFormSet = modelformset_factory(SalaryRecord, form=PaysheetRowForm, extra=0)

    if request.method == 'POST':
        formset = PaysheetFormSet(request.POST, queryset=queryset)
        if formset.is_valid():
            # Save all the inline changes (bonus, deductions, notes, etc.)
            formset.save()

            # Handle the bulk "Mark as Paid" action
            paid_ids = request.POST.getlist('mark_as_paid')
            if paid_ids:
                paid_records = SalaryRecord.objects.filter(id__in=paid_ids)
                for record in paid_records:
                    if not record.is_paid:  # Only update if not already paid
                        record.is_paid = True
                        # If amount_paid is still 0, assume full payment on bulk mark
                        if record.amount_paid == 0:
                            record.amount_paid = record.net_salary
                        record.paid_date = date.today()
                        record.paid_by = request.user
                        record.save()

            messages.success(request, 'Paysheet saved successfully!')
            # Redirect back to the same page with the same filters
            return redirect(reverse('process_payroll') + f'?year={year}&month={month}')
        else:
            messages.error(request, 'Please correct the errors below. Invalid data was submitted.')

    else:
        # For a GET request, just display the formset with the current data
        formset = PaysheetFormSet(queryset=queryset)

    context = {
        'formset': formset,
        'year': year,
        'month': month,
        'years': range(2020, datetime.now().year + 2),
        'months': [(i, datetime(2000, i, 1).strftime('%B')) for i in range(1, 13)],
    }
    return render(request, 'finance/salary_record/process_payroll.html', context)


@login_required
@permission_required('finance.view_salaryrecord')
def export_payroll_to_excel(request, year, month):
    """
    Generates an Excel file with a detailed breakdown of the payroll for a given month and year.
    """
    # 1. Fetch the relevant salary records
    queryset = SalaryRecord.objects.filter(year=year, month=month).select_related('staff')

    # 2. Create an in-memory Excel workbook
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    month_name = datetime(2000, month, 1).strftime('%B')
    worksheet.title = f'Payroll_{year}_{month_name}'

    # 3. Define the detailed header row
    headers = [
        'Staff ID', 'Full Name', 'Basic Salary', 'Housing', 'Transport', 'Medical',
        'Other Allowances', 'Bonus', 'Gross Salary', 'Tax (PAYE)', 'Pension',
        'Other Deductions', 'Total Deductions', 'Net Salary', 'Amount Paid', 'Status', 'Notes'
    ]
    for col_num, header_title in enumerate(headers, 1):
        cell = worksheet.cell(row=1, column=col_num, value=header_title)
        cell.font = Font(bold=True)

    # 4. Write data rows for each salary record
    for row_num, record in enumerate(queryset, 2):
        worksheet.cell(row=row_num, column=1, value=record.staff.staff_id)
        worksheet.cell(row=row_num, column=2, value=record.staff.__str__())
        worksheet.cell(row=row_num, column=3, value=record.basic_salary)
        worksheet.cell(row=row_num, column=4, value=record.housing_allowance)
        worksheet.cell(row=row_num, column=5, value=record.transport_allowance)
        worksheet.cell(row=row_num, column=6, value=record.medical_allowance)
        worksheet.cell(row=row_num, column=7, value=record.other_allowances)
        worksheet.cell(row=row_num, column=8, value=record.bonus)
        worksheet.cell(row=row_num, column=9, value=record.gross_salary)
        worksheet.cell(row=row_num, column=10, value=record.tax_amount)
        worksheet.cell(row=row_num, column=11, value=record.pension_amount)
        worksheet.cell(row=row_num, column=12, value=record.other_deductions)
        worksheet.cell(row=row_num, column=13, value=record.total_deductions)
        worksheet.cell(row=row_num, column=14, value=record.net_salary)
        worksheet.cell(row=row_num, column=15, value=record.amount_paid)
        worksheet.cell(row=row_num, column=16, value=record.payment_status)
        worksheet.cell(row=row_num, column=17, value=record.notes)

    # 5. Create the HttpResponse object with the correct headers
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="payroll_{year}_{month_name}.xlsx"'

    # Save the workbook to the response
    workbook.save(response)

    return response


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


@login_required
@permission_required('finance.view_salaryrecord')
def payroll_dashboard_view(request):
    """
    Provides data for a dashboard with payroll statistics and visualizations.
    Calculates net salary at the database level to fix the FieldError.
    """
    # Define the net salary calculation using F() objects for database-level arithmetic
    net_salary_expression = (
            F('basic_salary') + F('housing_allowance') + F('transport_allowance') +
            F('medical_allowance') + F('other_allowances') + F('bonus') -
            (F('tax_amount') + F('pension_amount') + F('other_deductions'))
    )

    # Get the current period
    today = datetime.now()
    current_year = today.year
    current_month = today.month

    # Get last month's period for comparison
    last_month_date = today.replace(day=1) - timedelta(days=1)
    last_month = last_month_date.month
    last_year = last_month_date.year

    # --- 1. KPI Cards Data ---
    current_month_payroll = SalaryRecord.objects.filter(year=current_year, month=current_month)
    last_month_payroll = SalaryRecord.objects.filter(year=last_year, month=last_month)

    total_payroll_current = current_month_payroll.aggregate(total=Sum(net_salary_expression))['total'] or 0
    total_payroll_last = last_month_payroll.aggregate(total=Sum(net_salary_expression))['total'] or 0

    staff_paid_count = current_month_payroll.count()
    average_net_salary = current_month_payroll.aggregate(avg=Avg(net_salary_expression))['avg'] or 0

    # Calculate percentage change
    if total_payroll_last > 0:
        percent_change = ((total_payroll_current - total_payroll_last) / total_payroll_last) * 100
    else:
        percent_change = 100 if total_payroll_current > 0 else 0

    # --- 2. Charts Data ---

    # Chart 1: Payroll Cost by Department (Bar Chart)
    dept_payroll = SalaryRecord.objects.filter(year=current_year, month=current_month) \
        .values('staff__department__name') \
        .annotate(total_cost=Sum(net_salary_expression)) \
        .order_by('-total_cost')

    dept_payroll_data = [
        {'name': item['staff__department__name'] or 'Unassigned', 'value': float(item['total_cost'])}
        for item in dept_payroll if item['total_cost']
    ]

    # Chart 2: Salary Trend (Line Chart - Last 12 Months)
    twelve_months_ago = today - timedelta(days=365)
    salary_trend = SalaryRecord.objects.filter(paid_date__gte=twelve_months_ago) \
        .annotate(month_year=TruncMonth('paid_date')) \
        .values('month_year') \
        .annotate(total_net=Sum(net_salary_expression)) \
        .order_by('month_year')

    salary_trend_data = [
        {'month': item['month_year'].strftime('%b %Y'), 'total': float(item['total_net'])}
        for item in salary_trend if item['month_year'] and item['total_net']
    ]

    # Chart 3: Average Salary by Position (Bar Chart)
    position_payroll = SalaryRecord.objects.filter(year=current_year, month=current_month) \
        .values('staff__position__name') \
        .annotate(avg_salary=Avg(net_salary_expression)) \
        .order_by('-avg_salary')

    position_payroll_data = [
        {'name': item['staff__position__name'] or 'Unassigned', 'value': float(item['avg_salary'])}
        for item in position_payroll if item['avg_salary']
    ]

    context = {
        # KPI Cards
        'total_payroll_current': total_payroll_current,
        'staff_paid_count': staff_paid_count,
        'average_net_salary': average_net_salary,
        'percent_change': percent_change,

        # Chart Data (passed as JSON)
        'dept_payroll_data': json.dumps(dept_payroll_data),
        'salary_trend_data': json.dumps(salary_trend_data),
        'position_payroll_data': json.dumps(position_payroll_data),
    }

    return render(request, 'finance/salary_record/dashboard.html', context)


# =================================================================================
# NEW & UPDATED MONEY REMITTANCE VIEWS
# =================================================================================

@login_required
@permission_required('finance.view_moneyremittance')
def remittance_dashboard_view(request):
    """
    Shows a dashboard of staff members and the total unremitted funds they are holding,
    as well as overall statistics.
    """
    # Find all staff who have ever received wallet funding payments
    staff_with_transactions = User.objects.filter(
        patienttransactionmodel__transaction_type='wallet_funding'
    ).distinct()

    # Calculate individual balances
    staff_balances = []
    total_outstanding = Decimal('0.00')
    for staff in staff_with_transactions:
        unremitted_txns = PatientTransactionModel.objects.filter(
            received_by=staff,
            transaction_type='wallet_funding',
            remittance__isnull=True
        )
        cash_total = unremitted_txns.filter(payment_method__iexact='cash').aggregate(total=Sum('amount'))['total'] or 0

        if cash_total > 0:
            total_outstanding += cash_total
            staff_balances.append({
                'staff': staff,
                'cash_outstanding': cash_total,
            })

    # Calculate overall remitted totals
    total_remitted = MoneyRemittance.objects.filter(status='APPROVED').aggregate(total=Sum('amount_remitted_cash'))[
                         'total'] or 0

    context = {
        'staff_balances': sorted(staff_balances, key=lambda x: x['cash_outstanding'], reverse=True),
        'total_outstanding': total_outstanding,
        'total_remitted': total_remitted,
    }
    return render(request, 'finance/remittance/dashboard.html', context)


@login_required
@permission_required('finance.add_moneyremittance')
def create_remittance_view(request):
    """
    Allows an admin/accountant to record a remittance from a staff member.
    The staff dropdown only shows users with unremitted funds.
    """
    # Find users who have unremitted cash transactions to populate the dropdown
    owing_staff_ids = PatientTransactionModel.objects.filter(
        transaction_type='wallet_funding',
        remittance__isnull=True,
        payment_method__iexact='cash'
    ).values_list('received_by_id', flat=True).distinct()

    owing_staff = User.objects.filter(id__in=owing_staff_ids)

    if request.method == 'POST':
        form = MoneyRemittanceForm(request.POST)
        # --- THIS IS THE FIX ---
        # We must set the queryset for the field before validation runs.
        # This ensures the submitted choice is considered valid.
        form.fields['remitted_by'].queryset = owing_staff

        if form.is_valid():
            remitted_by_user = form.cleaned_data['remitted_by']

            transactions_to_remit = PatientTransactionModel.objects.filter(
                received_by=remitted_by_user,
                transaction_type='wallet_funding',
                remittance__isnull=True
            )

            with transaction.atomic():
                if not transactions_to_remit.exists():
                    messages.error(request, "This staff member has no pending funds to remit.")
                    return redirect('remittance_create')

                cash_expected = \
                transactions_to_remit.filter(payment_method__iexact='cash').aggregate(total=Sum('amount'))['total'] or 0
                transfer_expected = \
                transactions_to_remit.filter(payment_method__iexact='transfer').aggregate(total=Sum('amount'))[
                    'total'] or 0

                remittance = form.save(commit=False)
                remittance.total_cash_expected = cash_expected
                remittance.total_transfer_expected = transfer_expected
                remittance.save()

                transactions_to_remit.update(remittance=remittance)

                messages.success(request,
                                 f"Remittance batch {remittance.remittance_id} created for {remitted_by_user.get_full_name()} and is awaiting approval.")
                return redirect('remittance_list')
    else:
        form = MoneyRemittanceForm()
        # Limit the 'remitted_by' dropdown to only staff who owe money
        form.fields['remitted_by'].queryset = owing_staff

    context = {
        'form': form,
    }
    return render(request, 'finance/remittance/create.html', context)

@login_required
def get_staff_remittance_details_ajax(request):
    """
    AJAX endpoint to get the unremitted totals for a selected staff member.
    """
    staff_id = request.GET.get('staff_id')
    if not staff_id:
        return JsonResponse({'success': False, 'error': 'Staff ID is required.'})

    try:
        staff = User.objects.get(pk=staff_id)
        unremitted_txns = PatientTransactionModel.objects.filter(
            received_by=staff,
            transaction_type='wallet_funding',
            remittance__isnull=True
        )
        cash_expected = unremitted_txns.filter(payment_method__iexact='cash').aggregate(total=Sum('amount'))[
                            'total'] or 0
        transfer_expected = unremitted_txns.filter(payment_method__iexact='transfer').aggregate(total=Sum('amount'))[
                                'total'] or 0

        return JsonResponse({
            'success': True,
            'cash_expected': f'{cash_expected:,.2f}',
            'transfer_expected': f'{transfer_expected:,.2f}',
            'total_expected': f'{cash_expected + transfer_expected:,.2f}',
        })
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Staff not found.'})


class RemittanceListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = MoneyRemittance
    permission_required = 'finance.view_moneyremittance'
    template_name = 'finance/remittance/list.html'
    context_object_name = "remittance_list"
    paginate_by = 20

    def get_queryset(self):
        queryset = MoneyRemittance.objects.select_related('remitted_by', 'approved_by')

        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        staff_id = self.request.GET.get('staff_id')

        if start_date and end_date:
            queryset = queryset.filter(created_at__date__range=[start_date, end_date])

        if staff_id:
            queryset = queryset.filter(remitted_by_id=staff_id)

        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Provide a list of staff who have ever received funds for the filter dropdown
        staff_ids = PatientTransactionModel.objects.filter(transaction_type='wallet_funding').values_list(
            'received_by_id', flat=True).distinct()
        context['staff_list'] = User.objects.filter(id__in=staff_ids)
        return context


class RemittanceDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = MoneyRemittance
    permission_required = 'finance.change_moneyremittance'  # Permission to approve
    template_name = 'finance/remittance/detail.html'
    context_object_name = "remittance"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['transactions'] = self.object.transactions.select_related('patient').order_by('-created_at')
        return context

    def post(self, request, *args, **kwargs):
        remittance = self.get_object()
        action = request.POST.get('action')

        if action == 'approve' and remittance.status == 'PENDING':
            remittance.status = 'APPROVED'
            remittance.approved_by = request.user
            remittance.approved_at = timezone.now()
            remittance.save()
            messages.success(request, f"Remittance {remittance.remittance_id} has been approved.")

        elif action == 'query' and remittance.status == 'PENDING':
            remittance.status = 'DISCREPANCY'
            remittance.approved_by = request.user  # The user who noted the discrepancy
            remittance.approved_at = timezone.now()
            remittance.save()
            messages.warning(request, f"Discrepancy noted for remittance {remittance.remittance_id}.")

        return redirect('remittance_detail', pk=remittance.pk)


@login_required
def finance_dashboard(request):
    """Main finance dashboard view with comprehensive statistics"""

    # Get date ranges
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    start_of_year = today.replace(month=1, day=1)
    week_start = today - timedelta(days=today.weekday())
    last_month = (start_of_month - timedelta(days=1)).replace(day=1)

    # Transaction Statistics
    total_transactions = PatientTransactionModel.objects.filter(status='completed')
    transactions_today = total_transactions.filter(date=today)
    transactions_week = total_transactions.filter(date__gte=week_start)
    transactions_month = total_transactions.filter(date__gte=start_of_month)

    # Revenue Statistics (all inbound transactions)
    revenue_transactions = total_transactions.filter(transaction_direction='in')
    total_revenue = revenue_transactions.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    revenue_today = transactions_today.filter(transaction_direction='in').aggregate(total=Sum('amount'))[
                        'total'] or Decimal('0.00')
    revenue_week = transactions_week.filter(transaction_direction='in').aggregate(total=Sum('amount'))[
                       'total'] or Decimal('0.00')
    revenue_month = transactions_month.filter(transaction_direction='in').aggregate(total=Sum('amount'))[
                        'total'] or Decimal('0.00')

    # Calculate previous month revenue for growth percentage
    prev_month_revenue = revenue_transactions.filter(
        date__gte=last_month,
        date__lt=start_of_month
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    revenue_growth = 0
    if prev_month_revenue > 0:
        revenue_growth = float(((revenue_month - prev_month_revenue) / prev_month_revenue) * 100)

    # Expense Statistics
    expenses = Expense.objects.all()
    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    expenses_today = expenses.filter(date=today).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    expenses_month = expenses.filter(date__gte=start_of_month).aggregate(total=Sum('amount'))['total'] or Decimal(
        '0.00')

    # Income Statistics (separate from patient transactions)
    incomes = Income.objects.all()
    total_income = incomes.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    income_today = incomes.filter(date=today).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    income_month = incomes.filter(date__gte=start_of_month).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # Net Profit Calculation
    total_inflow = total_revenue + total_income
    net_profit = total_inflow - total_expenses
    net_profit_month = (revenue_month + income_month) - expenses_month

    # Pending Transactions and Remittances
    pending_transactions = PatientTransactionModel.objects.filter(status='pending').count()
    pending_remittances = MoneyRemittance.objects.filter(status='PENDING').count()
    discrepancy_remittances = MoneyRemittance.objects.filter(status='DISCREPANCY').count()

    # Top Transaction Types
    transaction_types = PatientTransactionModel.objects.filter(
        status='completed',
        date__gte=start_of_month
    ).values('transaction_type').annotate(
        count=Count('id'),
        total=Sum('amount')
    ).order_by('-total')[:5]

    # Daily Revenue Trend (Last 30 days)
    thirty_days_ago = today - timedelta(days=30)
    daily_revenue = []

    for i in range(30):
        date_check = thirty_days_ago + timedelta(days=i)
        revenue = revenue_transactions.filter(date=date_check).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        daily_revenue.append({
            'date': date_check.strftime('%Y-%m-%d'),
            'revenue': float(revenue)
        })

    # Monthly Revenue vs Expenses (Last 12 months)
    monthly_comparison = []
    for i in range(12):
        month_date = (today.replace(day=1) - timedelta(days=32 * i)).replace(day=1)
        month_end = (month_date.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

        month_revenue = revenue_transactions.filter(
            date__gte=month_date,
            date__lte=month_end
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        month_income = incomes.filter(
            date__gte=month_date,
            date__lte=month_end
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        month_expenses = expenses.filter(
            date__gte=month_date,
            date__lte=month_end
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        monthly_comparison.append({
            'month': month_date.strftime('%b %Y'),
            'revenue': float(month_revenue),
            'income': float(month_income),
            'expenses': float(month_expenses),
            'profit': float((month_revenue + month_income) - month_expenses)
        })

    monthly_comparison.reverse()  # Show chronologically

    # Expense Categories Distribution
    expense_categories = ExpenseCategory.objects.annotate(
        total_amount=Sum('expense__amount'),
        count=Count('expense')
    ).filter(total_amount__gt=0).order_by('-total_amount')

    expense_category_data = [
        {
            'name': category.name,
            'value': float(category.total_amount or 0)
        }
        for category in expense_categories
    ]

    # Payment Methods Distribution (for completed transactions)
    payment_methods = PatientTransactionModel.objects.filter(
        status='completed',
        date__gte=start_of_month
    ).exclude(payment_method='').values('payment_method').annotate(
        count=Count('id'),
        total=Sum('amount')
    ).order_by('-total')

    # Recent Large Transactions
    recent_large_transactions = PatientTransactionModel.objects.filter(
        status='completed',
        amount__gte=10000  # Transactions above 10,000
    ).select_related('patient').order_by('-created_at')[:10]

    # Salary Payments Statistics
    unpaid_salaries = SalaryRecord.objects.filter(is_paid=False).count()
    partially_paid_salaries = SalaryRecord.objects.filter(
        amount_paid__gt=0,
        is_paid=False
    ).count()

    total_salary_debt = SalaryRecord.objects.filter(
        is_paid=False
    ).aggregate(
        debt=Sum(F('basic_salary') + F('housing_allowance') + F('transport_allowance') +
                 F('medical_allowance') + F('other_allowances') + F('bonus') -
                 F('tax_amount') - F('pension_amount') - F('other_deductions') - F('amount_paid'))
    )['debt'] or Decimal('0.00')

    # Financial Settings
    finance_settings = FinanceSettingModel.objects.first()

    context = {
        # Main Statistics
        'total_transactions_count': total_transactions.count(),
        'transactions_today_count': transactions_today.count(),
        'transactions_month_count': transactions_month.count(),

        # Revenue
        'total_revenue': total_revenue,
        'revenue_today': revenue_today,
        'revenue_week': revenue_week,
        'revenue_month': revenue_month,
        'revenue_growth': round(revenue_growth, 1),

        # Expenses
        'total_expenses': total_expenses,
        'expenses_today': expenses_today,
        'expenses_month': expenses_month,

        # Income
        'total_income': total_income,
        'income_today': income_today,
        'income_month': income_month,

        # Profit
        'net_profit': net_profit,
        'net_profit_month': net_profit_month,
        'total_inflow': total_inflow,

        # Pending Items
        'pending_transactions': pending_transactions,
        'pending_remittances': pending_remittances,
        'discrepancy_remittances': discrepancy_remittances,

        # Salary
        'unpaid_salaries': unpaid_salaries,
        'partially_paid_salaries': partially_paid_salaries,
        'total_salary_debt': total_salary_debt,

        # Charts Data
        'daily_revenue_data': json.dumps(daily_revenue),
        'monthly_comparison_data': json.dumps(monthly_comparison),
        'expense_category_data': json.dumps(expense_category_data),
        'transaction_types': transaction_types,
        'payment_methods': payment_methods,
        'recent_large_transactions': recent_large_transactions,

        # Settings
        'finance_settings': finance_settings,

        # Current date
        'current_date': today,
    }

    return render(request, 'finance/dashboard.html', context)


@login_required
def finance_dashboard_print(request):
    """Printable version of the finance dashboard"""

    # Get simplified data for printing
    today = timezone.now().date()
    start_of_month = today.replace(day=1)

    # Basic statistics
    total_transactions = PatientTransactionModel.objects.filter(status='completed')
    revenue_transactions = total_transactions.filter(transaction_direction='in')

    total_revenue = revenue_transactions.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    revenue_month = revenue_transactions.filter(date__gte=start_of_month).aggregate(total=Sum('amount'))[
                        'total'] or Decimal('0.00')

    total_expenses = Expense.objects.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    expenses_month = Expense.objects.filter(date__gte=start_of_month).aggregate(total=Sum('amount'))[
                         'total'] or Decimal('0.00')

    total_income = Income.objects.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    income_month = Income.objects.filter(date__gte=start_of_month).aggregate(total=Sum('amount'))['total'] or Decimal(
        '0.00')

    # Top categories
    top_expense_categories = ExpenseCategory.objects.annotate(
        total_amount=Sum('expense__amount')
    ).filter(total_amount__gt=0).order_by('-total_amount')[:5]

    top_income_categories = IncomeCategory.objects.annotate(
        total_amount=Sum('income__amount')
    ).filter(total_amount__gt=0).order_by('-total_amount')[:5]

    context = {
        'total_revenue': total_revenue,
        'revenue_month': revenue_month,
        'total_expenses': total_expenses,
        'expenses_month': expenses_month,
        'total_income': total_income,
        'income_month': income_month,
        'net_profit': (total_revenue + total_income) - total_expenses,
        'net_profit_month': (revenue_month + income_month) - expenses_month,
        'top_expense_categories': top_expense_categories,
        'top_income_categories': top_income_categories,
        'current_date': today,
        'total_transactions_count': total_transactions.count(),
    }

    return render(request, 'finance/dashboard_print.html', context)