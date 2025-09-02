import logging
import json
from datetime import datetime, date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q, Count, Sum, Case, When, IntegerField
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.timezone import now
from django.views.generic import (
    CreateView, ListView, UpdateView, DeleteView, DetailView, TemplateView
)

from insurance.models import InsuranceClaimModel
from patient.models import PatientModel, PatientWalletModel
from .models import *
from .forms import *

logger = logging.getLogger(__name__)


# -------------------------
# Mixins
# -------------------------
class FlashFormErrorsMixin:
    """
    Mixin for CreateView/UpdateView to flash form errors and redirect safely.
    Use before SuccessMessageMixin in MRO so messages appear before redirect.
    """

    def form_invalid(self, form):
        try:
            for field, errors in form.errors.items():
                field_name = form.fields.get(field).label if form.fields.get(field) else field
                for error in errors:
                    messages.error(self.request, f"{field_name}: {error}")
        except Exception:
            logger.exception("Error while processing form_invalid errors.")
            messages.error(self.request, "There was an error processing the form. Please try again.")
        return redirect(self.get_success_url())


# -------------------------
# Scan Category Views
# -------------------------
class ScanCategoryCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, CreateView
):
    model = ScanCategoryModel
    permission_required = 'scan.add_scancategorymodel'
    form_class = ScanCategoryForm
    template_name = 'scan/category/index.html'
    success_message = 'Scan Category Successfully Created'

    def get_success_url(self):
        return reverse('scan_category_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('scan_category_index'))
        return super().dispatch(request, *args, **kwargs)


class ScanCategoryListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ScanCategoryModel
    permission_required = 'scan.view_scancategorymodel'
    template_name = 'scan/category/index.html'
    context_object_name = "category_list"

    def get_queryset(self):
        return ScanCategoryModel.objects.all().order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = ScanCategoryForm()
        return context


class ScanCategoryUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
):
    model = ScanCategoryModel
    permission_required = 'scan.change_scancategorymodel'
    form_class = ScanCategoryForm
    template_name = 'scan/category/index.html'
    success_message = 'Scan Category Successfully Updated'

    def get_success_url(self):
        return reverse('scan_category_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('scan_category_index'))
        return super().dispatch(request, *args, **kwargs)


class ScanCategoryDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = ScanCategoryModel
    permission_required = 'scan.delete_scancategorymodel'
    template_name = 'scan/category/delete.html'
    context_object_name = "category"
    success_message = 'Scan Category Successfully Deleted'

    def get_success_url(self):
        return reverse('scan_category_index')


# -------------------------
# Scan Template Views
# -------------------------
class ScanTemplateCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    CreateView
):
    model = ScanTemplateModel
    permission_required = 'radiology.add_scantemplatemodel'
    form_class = ScanTemplateForm
    template_name = 'radiology/template/create.html'
    success_message = 'Scan Template Successfully Created'

    def get_success_url(self):
        return reverse('scan_template_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category_list'] = ScanCategoryModel.objects.all().order_by('name')
        return context


class ScanTemplateListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ScanTemplateModel
    permission_required = 'radiology.view_scantemplatemodel'
    template_name = 'scan/template/index.html'
    context_object_name = "template_list"

    def get_queryset(self):
        return ScanTemplateModel.objects.select_related('category').order_by('category__name', 'name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category_list'] = ScanCategoryModel.objects.all().order_by('name')
        return context


class ScanTemplateDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = ScanTemplateModel
    permission_required = 'radiology.view_scantemplatemodel'
    template_name = 'radiology/template/detail.html'
    context_object_name = "template"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        template = self.object

        # Get orders for this template
        orders = ScanOrderModel.objects.filter(template=template).select_related('patient').order_by('-ordered_at')[:10]

        context.update({
            'recent_orders': orders,
            'total_orders': ScanOrderModel.objects.filter(template=template).count(),
            'expected_images': template.expected_images,
            'scan_parameters': template.scan_parameters,
        })
        return context


# -------------------------
# Scan Entry Point - Patient Verification
# -------------------------
class ScanEntryView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Entry point for scan operations - patient verification"""
    permission_required = 'radiology.view_scanordermodel'
    template_name = 'radiology/order/entry.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Radiology - Patient Verification'
        return context


def verify_scan_patient_ajax(request):
    """AJAX view to verify patient by card number for scans"""
    if not request.user.has_perm('radiology.view_scanordermodel'):
        return JsonResponse({'success': False, 'error': 'Permission denied'})

    card_number = request.GET.get('card_number', '').strip()
    if not card_number:
        return JsonResponse({'success': False, 'error': 'Please enter a card number'})

    try:
        patient = PatientModel.objects.get(card_number=card_number, status='active')

        # Get scan counts
        scan_counts = {
            'total': ScanOrderModel.objects.filter(patient=patient).count(),
            'pending': ScanOrderModel.objects.filter(patient=patient, status='pending').count(),
            'paid': ScanOrderModel.objects.filter(patient=patient, status='paid').count(),
            'in_progress': ScanOrderModel.objects.filter(patient=patient, status='in_progress').count(),
            'completed': ScanOrderModel.objects.filter(patient=patient, status='completed').count(),
        }

        return JsonResponse({
            'success': True,
            'patient': {
                'id': patient.id,
                'full_name': patient.__str__(),
                'patient_id': patient.card_number,
                'phone': patient.mobile,
                'email': getattr(patient, 'email', ''),
                'age': patient.age() if hasattr(patient, 'age') and callable(patient.age) else '',
                'gender': getattr(patient, 'gender', ''),
                'address': patient.address or 'Not provided',
            },
            'scan_counts': scan_counts
        })

    except PatientModel.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': f'No patient found with card number: {card_number}'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'An error occurred while verifying patient: {str(e)}'
        })


# -------------------------
# Missing Scan Category Views
# -------------------------
class ScanCategoryUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
):
    model = ScanCategoryModel
    permission_required = 'radiology.change_scancategorymodel'
    form_class = ScanCategoryForm
    template_name = 'radiology/category/index.html'
    success_message = 'Scan Category Successfully Updated'

    def get_success_url(self):
        return reverse('scan_category_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('scan_category_index'))
        return super().dispatch(request, *args, **kwargs)


class ScanCategoryDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = ScanCategoryModel
    permission_required = 'radiology.delete_scancategorymodel'
    template_name = 'radiology/category/delete.html'
    context_object_name = "category"
    success_message = 'Scan Category Successfully Deleted'

    def get_success_url(self):
        return reverse('scan_category_index')


# -------------------------
# Missing Scan Template Views
# -------------------------
class ScanTemplateUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
):
    model = ScanTemplateModel
    permission_required = 'radiology.change_scantemplatemodel'
    form_class = ScanTemplateForm
    template_name = 'radiology/template/edit.html'
    success_message = 'Scan Template Successfully Updated'

    def get_success_url(self):
        return reverse('scan_template_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category_list'] = ScanCategoryModel.objects.all().order_by('name')
        context['template'] = self.object
        return context


class ScanTemplateDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = ScanTemplateModel
    permission_required = 'radiology.delete_scantemplatemodel'
    template_name = 'radiology/template/delete.html'
    context_object_name = "template"
    success_message = 'Scan Template Successfully Deleted'

    def get_success_url(self):
        return reverse('scan_template_index')


# -------------------------
# Missing Scan Order Views
# -------------------------
class ScanOrderListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ScanOrderModel
    permission_required = 'radiology.view_scanordermodel'
    template_name = 'radiology/order/index.html'
    context_object_name = "order_list"
    paginate_by = 20

    def get_queryset(self):
        queryset = ScanOrderModel.objects.select_related(
            'patient', 'template', 'ordered_by'
        ).order_by('-ordered_at')

        # Filter by status if provided
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)

        # Filter by patient if provided
        patient = self.request.GET.get('patient')
        if patient:
            queryset = queryset.filter(patient__id=patient)

        # Filter by template if provided
        template = self.request.GET.get('template')
        if template:
            queryset = queryset.filter(template__id=template)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = ScanOrderModel.STATUS_CHOICES
        context['patient_list'] = PatientModel.objects.filter(status='active').order_by('first_name')
        context['template_list'] = ScanTemplateModel.objects.filter(is_active=True).order_by('name')

        # Add counts for dashboard
        context['status_counts'] = {
            'pending': ScanOrderModel.objects.filter(status='pending').count(),
            'paid': ScanOrderModel.objects.filter(status='paid').count(),
            'scheduled': ScanOrderModel.objects.filter(status='scheduled').count(),
            'in_progress': ScanOrderModel.objects.filter(status='in_progress').count(),
            'completed': ScanOrderModel.objects.filter(status='completed').count(),
        }

        return context


class ScanOrderUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, UpdateView
):
    model = ScanOrderModel
    permission_required = 'radiology.change_scanordermodel'
    form_class = ScanOrderForm
    template_name = 'radiology/order/edit.html'

    def get_success_url(self):
        return reverse('scan_order_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['order'] = self.object
        context['patient_list'] = PatientModel.objects.filter(status='active').order_by('first_name')
        context['template_list'] = ScanTemplateModel.objects.filter(is_active=True).order_by('name')
        return context


# -------------------------
# Missing Scan Result Views
# -------------------------
class ScanResultUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Update scan results (only if not verified)"""
    model = ScanResultModel
    permission_required = 'radiology.change_scanresultmodel'
    template_name = 'radiology/result/edit.html'
    fields = ['findings', 'impression', 'recommendations', 'technician_notes']

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.is_verified:
            messages.error(request, 'Cannot edit verified results.')
            return redirect('scan_result_detail', pk=self.object.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'result': self.object,
            'order': self.object.order,
            'patient': self.object.order.patient,
            'template': self.object.order.template,
            'expected_images': self.object.order.template.expected_images,
            'measurements': self.object.order.template.scan_parameters.get('measurements', []),
            'existing_measurements': {r['parameter_code']: r for r in
                                      self.object.measurements_data.get('measurements', [])},
            'scan_images': self.object.images.all().order_by('sequence_number')
        })
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        # Process updated measurements (for scans like ECG)
        measurements = self.object.order.template.scan_parameters.get('measurements', [])
        measurements_results = []

        for measurement in measurements:
            param_code = measurement.get('code', '')
            value = request.POST.get(f'measurement_{param_code}', '').strip()

            if value:
                result_entry = {
                    'parameter_code': param_code,
                    'parameter_name': measurement.get('name', ''),
                    'value': value,
                    'unit': measurement.get('unit', ''),
                    'type': measurement.get('type', 'numeric')
                }

                # Add normal range and status logic
                if 'normal_range' in measurement:
                    result_entry['normal_range'] = measurement['normal_range']
                    if measurement.get('type') == 'numeric' and measurement['normal_range'].get('min') and measurement[
                        'normal_range'].get('max'):
                        try:
                            numeric_value = float(value)
                            min_val = float(measurement['normal_range']['min'])
                            max_val = float(measurement['normal_range']['max'])

                            if numeric_value < min_val:
                                result_entry['status'] = 'low'
                            elif numeric_value > max_val:
                                result_entry['status'] = 'high'
                            else:
                                result_entry['status'] = 'normal'
                        except (ValueError, TypeError):
                            result_entry['status'] = 'normal'

                measurements_results.append(result_entry)

        # Update the result
        findings = request.POST.get('findings', '').strip()
        impression = request.POST.get('impression', '').strip()
        recommendations = request.POST.get('recommendations', '').strip()
        technician_notes = request.POST.get('technician_notes', '').strip()

        try:
            self.object.measurements_data = {'measurements': measurements_results} if measurements_results else {}
            self.object.findings = findings
            self.object.impression = impression
            self.object.recommendations = recommendations
            self.object.technician_notes = technician_notes
            self.object.save(
                update_fields=['measurements_data', 'findings', 'impression', 'recommendations', 'technician_notes'])

            messages.success(request, 'Scan results updated successfully')
            return redirect('scan_result_detail', pk=self.object.pk)

        except Exception as e:
            logger.exception("Error updating scan result %s", self.object.id)
            messages.error(request, 'An error occurred while updating results. Please try again.')
            return self.get(request, *args, **kwargs)


class ScanResultListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """List all scan results with filtering options"""
    model = ScanResultModel
    permission_required = 'radiology.view_scanresultmodel'
    template_name = 'radiology/result/index.html'
    context_object_name = 'results'
    paginate_by = 20

    def get_queryset(self):
        verified_filter = self.request.GET.get('verified', '')
        search_query = self.request.GET.get('search', '')

        queryset = ScanResultModel.objects.select_related(
            'order__patient', 'order__template', 'verified_by'
        ).order_by('-created_at')

        if verified_filter == 'verified':
            queryset = queryset.filter(is_verified=True)
        elif verified_filter == 'unverified':
            queryset = queryset.filter(is_verified=False)

        if search_query:
            queryset = queryset.filter(
                Q(order__patient__first_name__icontains=search_query) |
                Q(order__patient__last_name__icontains=search_query) |
                Q(order__order_number__icontains=search_query) |
                Q(order__template__name__icontains=search_query)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Summary stats
        context['pending_verification'] = ScanResultModel.objects.filter(is_verified=False).count()
        context['total_results'] = ScanResultModel.objects.count()
        context['verified_results'] = ScanResultModel.objects.filter(is_verified=True).count()

        # Filter options
        context['verified_choices'] = [
            ('', 'All Results'),
            ('verified', 'Verified Only'),
            ('unverified', 'Unverified Only')
        ]
        context['current_verified'] = self.request.GET.get('verified', '')
        context['search_query'] = self.request.GET.get('search', '')

        return context


# -------------------------
# Patient Scan Management
# -------------------------
class PatientScansView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """View patient's scans with grouping by date"""
    model = ScanOrderModel
    permission_required = 'radiology.view_scanordermodel'
    template_name = 'radiology/order/patient_scans.html'
    context_object_name = 'orders'
    paginate_by = 30

    def get_queryset(self):
        patient_id = self.kwargs.get('patient_id')
        self.patient = get_object_or_404(PatientModel, id=patient_id, status='active')

        queryset = ScanOrderModel.objects.filter(
            patient=self.patient
        ).select_related(
            'template', 'template__category', 'ordered_by', 'payment_by'
        ).order_by('-ordered_at')

        # Filter by status if provided
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['patient'] = self.patient
        context['status_choices'] = ScanOrderModel.STATUS_CHOICES

        # Group orders by date
        orders_by_date = {}
        for order in context['orders']:
            order_date = order.ordered_at.date()
            if order_date not in orders_by_date:
                orders_by_date[order_date] = []
            orders_by_date[order_date].append(order)

        context['orders_by_date'] = orders_by_date

        # Get scan counts for summary
        context['scan_counts'] = {
            'total': ScanOrderModel.objects.filter(patient=self.patient).count(),
            'pending': ScanOrderModel.objects.filter(patient=self.patient, status='pending').count(),
            'paid': ScanOrderModel.objects.filter(patient=self.patient, status='paid').count(),
            'scheduled': ScanOrderModel.objects.filter(patient=self.patient, status='scheduled').count(),
            'in_progress': ScanOrderModel.objects.filter(patient=self.patient, status='in_progress').count(),
            'completed': ScanOrderModel.objects.filter(patient=self.patient, status='completed').count(),
        }

        # Get available scan templates for new order
        context['template_list'] = ScanTemplateModel.objects.filter(
            is_active=True
        ).select_related('category').order_by('category__name', 'name')

        return context


# -------------------------
# Scan Order CRUD Views
# -------------------------
class ScanOrderCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = ScanOrderModel
    permission_required = 'radiology.add_scanordermodel'
    form_class = ScanOrderForm
    template_name = 'radiology/order/create.html'

    def get_initial(self):
        initial = super().get_initial()
        patient_id = self.kwargs.get('patient_id')
        if patient_id:
            initial['patient'] = patient_id
        initial['ordered_by'] = self.request.user
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        patient_id = self.kwargs.get('patient_id')
        if patient_id:
            context['patient'] = get_object_or_404(PatientModel, id=patient_id)
        context['template_list'] = ScanTemplateModel.objects.filter(is_active=True).select_related('category').order_by(
            'category__name', 'name')
        return context

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        scan_ids = request.POST.getlist('scans')

        if not scan_ids:
            messages.error(request, "Please select at least one scan.")
            return redirect(request.path)

        if not form.is_valid():
            for field, errs in form.errors.items():
                for e in errs:
                    messages.error(request, f"{field}: {e}")
            return redirect(request.path)

        created_orders = []
        try:
            with transaction.atomic():
                patient = get_object_or_404(PatientModel, id=self.kwargs.get('patient_id'))
                for sid in scan_ids:
                    try:
                        template = ScanTemplateModel.objects.get(pk=int(sid))
                    except (ValueError, ScanTemplateModel.DoesNotExist):
                        messages.warning(request, f"Scan id {sid} not found - skipped.")
                        continue

                    order = ScanOrderModel(
                        patient=patient,
                        template=template,
                        ordered_by=request.user,
                        status='pending',
                        amount_charged=template.price,
                        clinical_indication=form.cleaned_data.get('clinical_indication', ''),
                        special_instructions=form.cleaned_data.get('special_instructions', ''),
                    )
                    order.save()
                    created_orders.append(order)
        except Exception:
            logger.exception("Error creating scan orders")
            messages.error(request, "An error occurred creating orders. Contact admin.")
            return redirect(request.path)

        if created_orders:
            messages.success(request, f"Created {len(created_orders)} scan order(s).")
            return redirect(reverse('patient_scans', kwargs={'patient_id': created_orders[0].patient.id}))
        else:
            messages.error(request, "No valid scans selected.")
            return redirect(request.path)


class ScanOrderDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = ScanOrderModel
    permission_required = 'radiology.view_scanordermodel'
    template_name = 'radiology/order/detail.html'
    context_object_name = "order"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = self.object

        # Check if results exist
        has_results = hasattr(order, 'result')

        context.update({
            'has_results': has_results,
            'can_process_payment': order.status == 'pending' and self.request.user.has_perm(
                'radiology.change_scanordermodel'),
            'can_schedule': order.status == 'paid' and self.request.user.has_perm('radiology.change_scanordermodel'),
            'can_start_scan': order.status == 'scheduled' and self.request.user.has_perm(
                'radiology.change_scanordermodel'),
            'can_complete_scan': order.status == 'in_progress' and self.request.user.has_perm(
                'radiology.change_scanordermodel'),
            'expected_images': order.template.expected_images,
        })

        # If has results, get images
        if has_results:
            context['scan_images'] = order.result.images.all().order_by('sequence_number')

        return context


# -------------------------
# Scan Payment Processing
# -------------------------
def process_scan_payments(request):
    """Process payments for selected scans with wallet balance and insurance validation"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})

    if not request.user.has_perm('radiology.change_scanordermodel'):
        return JsonResponse({'success': False, 'error': 'Permission denied'})

    selected_orders = request.POST.getlist('selected_orders')
    if not selected_orders:
        return JsonResponse({'success': False, 'error': 'No scans selected'})

    try:
        with transaction.atomic():
            # Get all selected orders
            orders = ScanOrderModel.objects.filter(
                id__in=selected_orders,
                status='pending'
            ).select_related('template', 'patient')

            if not orders.exists():
                return JsonResponse({'success': False, 'error': 'No valid pending scans found'})

            # Get patient (assuming all orders are for the same patient)
            patient = orders.first().patient

            # Get or create patient wallet
            wallet, created = PatientWalletModel.objects.get_or_create(
                patient=patient,
                defaults={'amount': Decimal('0.00')}
            )

            # Check for active insurance
            active_insurance = None
            if hasattr(patient, 'insurance_policies'):
                active_insurance = patient.insurance_policies.filter(
                    is_active=True,
                    valid_to__gte=date.today()
                ).select_related('hmo', 'coverage_plan').first()

            # Calculate insurance amount helper function
            def calculate_patient_amount(base_amount, coverage_percentage):
                """Calculate patient's portion after insurance"""
                if coverage_percentage and coverage_percentage > 0:
                    covered_amount = base_amount * (coverage_percentage / 100)
                    return base_amount - covered_amount
                return base_amount

            # Calculate total amounts considering insurance
            total_base_amount = Decimal('0.00')
            total_patient_amount = Decimal('0.00')
            total_insurance_covered = Decimal('0.00')
            order_details = []

            for order in orders:
                # Get base amount
                base_amount = order.amount_charged or order.template.price

                # Apply insurance if applicable (assuming scan coverage)
                if active_insurance and hasattr(active_insurance.coverage_plan,
                                                'is_scan_covered') and active_insurance.coverage_plan.is_scan_covered(
                    order.template):
                    patient_amount = calculate_patient_amount(
                        base_amount,
                        getattr(active_insurance.coverage_plan, 'scan_coverage_percentage', 0)
                    )
                    insurance_covered = base_amount - patient_amount
                else:
                    patient_amount = base_amount
                    insurance_covered = Decimal('0.00')

                total_base_amount += base_amount
                total_patient_amount += patient_amount
                total_insurance_covered += insurance_covered

                order_details.append({
                    'order': order,
                    'base_amount': base_amount,
                    'patient_amount': patient_amount,
                    'insurance_covered': insurance_covered
                })

            # Check wallet balance
            if wallet.amount < total_patient_amount:
                return JsonResponse({
                    'success': False,
                    'error': f'Insufficient wallet balance. Required: ₦{total_patient_amount:,.2f}, Available: ₦{wallet.amount:,.2f}. Please visit Finance to fund wallet.',
                    'required_amount': float(total_patient_amount),
                    'available_amount': float(wallet.amount),
                    'shortage': float(total_patient_amount - wallet.amount)
                })

            # Create insurance claim if insurance is active and covers any amount
            insurance_claim = None
            if active_insurance and total_insurance_covered > 0:
                claim_type = 'radiology' if len(orders) == 1 else 'multiple'

                insurance_claim = InsuranceClaimModel.objects.create(
                    patient_insurance=active_insurance,
                    claim_type=claim_type,
                    total_amount=total_base_amount,
                    covered_amount=total_insurance_covered,
                    patient_amount=total_patient_amount,
                    service_date=now(),
                    created_by=request.user,
                    notes=f'Auto-generated claim for {len(orders)} scan(s)'
                )

            # Process payments and update orders
            updated_count = 0

            for detail in order_details:
                order = detail['order']
                patient_amount = detail['patient_amount']

                # Deduct patient amount from wallet
                wallet.amount -= patient_amount

                # Update order
                order.status = 'paid'
                order.payment_status = True
                order.payment_date = now()
                order.payment_by = request.user

                if not order.amount_charged:
                    order.amount_charged = detail['base_amount']

                # Link to insurance claim if created
                if insurance_claim:
                    order.insurance_claim = insurance_claim

                order.save()
                updated_count += 1

            # Save wallet
            wallet.save()

            # Prepare response message
            message_parts = [
                f'Successfully processed payment for {updated_count} scan(s)',
                f'Patient paid: ₦{total_patient_amount:,.2f}'
            ]

            if insurance_claim:
                message_parts.append(
                    f'Insurance claim {insurance_claim.claim_number} created for ₦{total_insurance_covered:,.2f}')

            return JsonResponse({
                'success': True,
                'message': '. '.join(message_parts),
                'details': {
                    'processed_count': updated_count,
                    'patient_amount_paid': float(total_patient_amount),
                    'insurance_amount_covered': float(total_insurance_covered),
                    'new_wallet_balance': float(wallet.amount),
                    'formatted_wallet_balance': f'₦{wallet.amount:,.2f}',
                    'insurance_claim_number': insurance_claim.claim_number if insurance_claim else None
                }
            })

    except PatientWalletModel.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Patient wallet not found. Please contact Finance to create wallet.'
        })
    except Exception as e:
        logger.exception("Error processing scan payments")
        return JsonResponse({
            'success': False,
            'error': f'Error processing payment: {str(e)}'
        })


# -------------------------
# Scan Scheduling
# -------------------------
@login_required
@permission_required('radiology.change_scanordermodel', raise_exception=True)
def schedule_scan(request, order_id):
    """Schedule a paid scan"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})

    try:
        order = get_object_or_404(ScanOrderModel, id=order_id, status='paid')

        scheduled_date_str = request.POST.get('scheduled_date', '').strip()
        if not scheduled_date_str:
            return JsonResponse({'success': False, 'error': 'Scheduled date is required'})

        try:
            scheduled_date = datetime.fromisoformat(scheduled_date_str)
        except ValueError:
            return JsonResponse({'success': False, 'error': 'Invalid date format'})

        # Update order
        order.status = 'scheduled'
        order.scheduled_date = scheduled_date
        order.scheduled_by = request.user
        order.save()

        return JsonResponse({
            'success': True,
            'message': f'Scan scheduled for {order.template.name}',
            'scheduled_date': scheduled_date.strftime('%Y-%m-%d %H:%M')
        })

    except Exception as e:
        logger.exception("Error scheduling scan")
        return JsonResponse({'success': False, 'error': f'Error scheduling scan: {str(e)}'})


# -------------------------
# Scan Result Views
# -------------------------
class ScanResultDashboardView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """Main dashboard for scan results - shows orders ready for scanning"""
    model = ScanOrderModel
    permission_required = 'radiology.view_scanordermodel'
    template_name = 'radiology/result/dashboard.html'
    context_object_name = 'orders'
    paginate_by = 20

    def get_queryset(self):
        status_filter = self.request.GET.get('status', '')
        search_query = self.request.GET.get('search', '')

        # Base queryset - orders that can have scans performed
        queryset = ScanOrderModel.objects.filter(
            status__in=['scheduled', 'in_progress', 'completed']
        ).select_related('patient', 'template', 'scheduled_by').order_by('-scheduled_date')

        # Apply filters
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        if search_query:
            queryset = queryset.filter(
                Q(patient__first_name__icontains=search_query) |
                Q(patient__last_name__icontains=search_query) |
                Q(order_number__icontains=search_query) |
                Q(template__name__icontains=search_query)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Status counts for dashboard
        status_counts = ScanOrderModel.objects.filter(
            status__in=['scheduled', 'in_progress', 'completed']
        ).aggregate(
            scheduled=Count(Case(When(status='scheduled', then=1), output_field=IntegerField())),
            in_progress=Count(Case(When(status='in_progress', then=1), output_field=IntegerField())),
            completed=Count(Case(When(status='completed', then=1), output_field=IntegerField())),
        )

        # Results needing verification
        unverified_count = ScanResultModel.objects.filter(is_verified=False).count()

        context.update({
            'status_counts': status_counts,
            'unverified_count': unverified_count,
            'status_choices': ScanOrderModel.STATUS_CHOICES,
            'current_status': self.request.GET.get('status', ''),
            'search_query': self.request.GET.get('search', ''),
        })

        return context


class ScanResultCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Create scan results"""
    model = ScanResultModel
    permission_required = 'radiology.add_scanresultmodel'
    template_name = 'radiology/result/create.html'
    fields = ['findings', 'impression', 'recommendations', 'technician_notes']

    def dispatch(self, request, *args, **kwargs):
        # Get the order from URL
        order_id = kwargs.get('order_id')
        if order_id:
            self.order = get_object_or_404(ScanOrderModel, pk=order_id)
            # Check if result already exists
            if hasattr(self.order, 'result'):
                messages.warning(request, 'Results already exist for this order. Redirecting to edit.')
                return redirect('scan_result_edit', pk=self.order.result.pk)
            # Check if order is ready for results
            if self.order.status not in ['in_progress', 'scheduled']:
                messages.error(request, 'This order is not ready for result entry.')
                return redirect('scan_result_dashboard')
        else:
            self.order = None
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.order:
            context.update({
                'order': self.order,
                'patient': self.order.patient,
                'template': self.order.template,
                'expected_images': self.order.template.expected_images,
                'measurements': self.order.template.scan_parameters.get('measurements', [])
            })
        return context

    def post(self, request, *args, **kwargs):
        if not self.order:
            messages.error(request, 'Invalid order selected.')
            return redirect('scan_result_dashboard')

        # Process measurements data if scan has measurements (like ECG)
        measurements = self.order.template.scan_parameters.get('measurements', [])
        measurements_results = []

        for measurement in measurements:
            param_code = measurement.get('code', '')
            value = request.POST.get(f'measurement_{param_code}', '').strip()

            if value:
                result_entry = {
                    'parameter_code': param_code,
                    'parameter_name': measurement.get('name', ''),
                    'value': value,
                    'unit': measurement.get('unit', ''),
                    'type': measurement.get('type', 'numeric')
                }

                # Add normal range if available
                if 'normal_range' in measurement:
                    result_entry['normal_range'] = measurement['normal_range']
                    # Determine status for numeric values
                    if measurement.get('type') == 'numeric' and measurement['normal_range'].get('min') and measurement[
                        'normal_range'].get('max'):
                        try:
                            numeric_value = float(value)
                            min_val = float(measurement['normal_range']['min'])
                            max_val = float(measurement['normal_range']['max'])

                            if numeric_value < min_val:
                                result_entry['status'] = 'low'
                            elif numeric_value > max_val:
                                result_entry['status'] = 'high'
                            else:
                                result_entry['status'] = 'normal'
                        except (ValueError, TypeError):
                            result_entry['status'] = 'normal'

                measurements_results.append(result_entry)

        # Get form data
        findings = request.POST.get('findings', '').strip()
        impression = request.POST.get('impression', '').strip()
        recommendations = request.POST.get('recommendations', '').strip()
        technician_notes = request.POST.get('technician_notes', '').strip()

        try:
            with transaction.atomic():
                result = ScanResultModel.objects.create(
                    order=self.order,
                    measurements_data={'measurements': measurements_results} if measurements_results else {},
                    findings=findings,
                    impression=impression,
                    recommendations=recommendations,
                    technician_notes=technician_notes
                )

                # Update order status
                self.order.status = 'completed'
                self.order.scan_completed_at = now()
                self.order.performed_by = request.user
                self.order.save(update_fields=['status', 'scan_completed_at', 'performed_by'])

            messages.success(request, f'Results entered successfully for {self.order.template.name}')
            return redirect('scan_result_detail', pk=result.pk)

        except Exception as e:
            logger.exception("Error creating scan result for order %s", self.order.id)
            messages.error(request, 'An error occurred while saving results. Please try again.')
            return self.get(request, *args, **kwargs)


class ScanResultDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = ScanResultModel
    permission_required = 'radiology.view_scanresultmodel'
    template_name = 'radiology/result/detail.html'
    context_object_name = 'result'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        result = self.object

        context.update({
            'can_verify': not result.is_verified and self.request.user.has_perm('radiology.change_scanresultmodel'),
            'can_edit': not result.is_verified and self.request.user.has_perm('radiology.change_scanresultmodel'),
            'can_upload_images': self.request.user.has_perm('radiology.add_scanimagemodel'),
            'order': result.order,
            'patient': result.order.patient,
            'template': result.order.template,
            'expected_images': result.order.template.expected_images,
            'measurements': result.measurements_data.get('measurements', []),
            'scan_images': result.images.all().order_by('sequence_number')
        })

        return context


# -------------------------
# Scan Image Management
# -------------------------
class ScanImageUploadView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Upload individual scan images"""
    model = ScanImageModel
    permission_required = 'radiology.add_scanimagemodel'
    form_class = ScanImageForm
    template_name = 'radiology/image/upload.html'

    def get_initial(self):
        initial = super().get_initial()
        result_id = self.kwargs.get('result_id')
        if result_id:
            initial['scan_result'] = result_id
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        result_id = self.kwargs.get('result_id')
        if result_id:
            scan_result = get_object_or_404(ScanResultModel, id=result_id)
            context['scan_result'] = scan_result
            context['expected_images'] = scan_result.order.template.expected_images
            context['existing_images'] = scan_result.images.all().order_by('sequence_number')
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Image uploaded successfully')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('scan_result_detail', kwargs={'pk': self.object.scan_result.pk})


class MultipleImageUploadView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Upload multiple scan images at once"""
    permission_required = 'radiology.add_scanimagemodel'
    template_name = 'radiology/image/multiple_upload.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        result_id = self.kwargs.get('result_id')
        if result_id:
            scan_result = get_object_or_404(ScanResultModel, id=result_id)
            context['scan_result'] = scan_result
            context['expected_images'] = scan_result.order.template.expected_images
            context['form'] = MultipleImageUploadForm(initial={'scan_result': scan_result})
        return context

    def post(self, request, *args, **kwargs):
        result_id = self.kwargs.get('result_id')
        scan_result = get_object_or_404(ScanResultModel, id=result_id)

        files = request.FILES.getlist('images')
        if not files:
            messages.error(request, 'Please select at least one image')
            return redirect(request.path)

        try:
            with transaction.atomic():
                # Get next sequence number
                last_image = scan_result.images.order_by('-sequence_number').first()
                next_seq = (last_image.sequence_number + 1) if last_image else 1

                uploaded_count = 0
                for file in files:
                    ScanImageModel.objects.create(
                        scan_result=scan_result,
                        image=file,
                        description=f"Image {next_seq}",
                        sequence_number=next_seq
                    )
                    next_seq += 1
                    uploaded_count += 1

            messages.success(request, f'Successfully uploaded {uploaded_count} image(s)')
            return redirect('scan_result_detail', pk=scan_result.pk)

        except Exception as e:
            logger.exception("Error uploading multiple images")
            messages.error(request, 'Error uploading images. Please try again.')
            return redirect(request.path)


# -------------------------
# Scan Status Update Actions
# -------------------------
@login_required
@permission_required('radiology.change_scanordermodel', raise_exception=True)
def start_scan(request, order_id):
    """Start scan procedure - AJAX endpoint"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    try:
        order = get_object_or_404(ScanOrderModel, pk=order_id)

        if order.status != 'scheduled':
            return JsonResponse({
                'success': False,
                'error': 'Scan can only be started for scheduled orders.'
            }, status=400)

        with transaction.atomic():
            order.status = 'in_progress'
            order.scan_started_at = now()
            order.performed_by = request.user
            order.save(update_fields=['status', 'scan_started_at', 'performed_by'])

        return JsonResponse({
            'success': True,
            'message': f'Scan started for order {order.order_number}',
            'redirect_url': reverse('scan_result_create_for_order', kwargs={'order_id': order.id})
        })

    except Exception as e:
        logger.exception("Error starting scan for order id=%s", order_id)
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while starting scan. Please contact administrator.'
        }, status=500)


@login_required
@permission_required('radiology.change_scanresultmodel', raise_exception=True)
def verify_scan_result(request, result_id):
    """AJAX endpoint to verify a scan result"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    try:
        result = get_object_or_404(ScanResultModel, pk=result_id)

        if result.is_verified:
            return JsonResponse({
                'success': False,
                'error': 'Result is already verified.'
            }, status=400)

        # Optional radiologist comments
        radiologist_comments = request.POST.get('doctor_interpretation', '').strip()

        with transaction.atomic():
            result.is_verified = True
            result.verified_by = request.user
            result.verified_at = now()
            if radiologist_comments:
                result.doctor_interpretation = radiologist_comments
            result.save(update_fields=['is_verified', 'verified_by', 'verified_at', 'doctor_interpretation'])

        return JsonResponse({
            'success': True,
            'message': f'Scan result verified successfully',
            'verified_by': result.verified_by.get_full_name() or result.verified_by.username,
            'verified_at': result.verified_at.strftime('%B %d, %Y at %I:%M %p')
        })

    except Exception as e:
        logger.exception("Error verifying scan result id=%s", result_id)
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while verifying result. Please contact administrator.'
        }, status=500)


# -------------------------
# AJAX/API Views
# -------------------------
@login_required
def get_scan_template_details(request):
    """Get scan template details for AJAX requests."""
    template_id = request.GET.get('template_id')
    if not template_id:
        return JsonResponse({'error': 'template_id is required'}, status=400)

    try:
        template = ScanTemplateModel.objects.get(id=template_id)
        data = {
            'id': template.id,
            'name': template.name,
            'code': template.code,
            'price': str(template.price),
            'estimated_duration': template.estimated_duration,
            'preparation_required': template.preparation_required,
            'fasting_required': template.fasting_required,
            'equipment_required': template.equipment_required,
            'expected_images': template.expected_images,
            'scan_parameters': template.scan_parameters
        }
        return JsonResponse(data)
    except ScanTemplateModel.DoesNotExist:
        return JsonResponse({'error': 'Template not found'}, status=404)
    except Exception:
        logger.exception("Failed fetching scan template details for id=%s", template_id)
        return JsonResponse({'error': 'Internal error'}, status=500)


@login_required
def get_patient_scans(request):
    """Get scan orders for a specific patient."""
    patient_id = request.GET.get('patient_id')
    if not patient_id:
        return JsonResponse({'error': 'patient_id is required'}, status=400)

    try:
        orders = ScanOrderModel.objects.filter(
            patient_id=patient_id
        ).select_related('template').order_by('-ordered_at')[:10]

        data = {
            'orders': [
                {
                    'id': order.id,
                    'order_number': order.order_number,
                    'template_name': order.template.name,
                    'status': order.status,
                    'ordered_at': order.ordered_at.strftime('%Y-%m-%d %H:%M'),
                    'scheduled_date': order.scheduled_date.strftime('%Y-%m-%d %H:%M') if order.scheduled_date else None,
                }
                for order in orders
            ]
        }
        return JsonResponse(data)
    except Exception:
        logger.exception("Failed fetching patient scans for patient_id=%s", patient_id)
        return JsonResponse({'error': 'Internal error'}, status=500)


@login_required
def scan_dashboard_data(request):
    """Get scan dashboard statistics for AJAX requests."""
    try:
        today = date.today()

        data = {
            'today_orders': ScanOrderModel.objects.filter(ordered_at__date=today).count(),
            'pending_payments': ScanOrderModel.objects.filter(status='pending').count(),
            'scans_to_schedule': ScanOrderModel.objects.filter(status='paid').count(),
            'scheduled_scans': ScanOrderModel.objects.filter(status='scheduled').count(),
            'scans_in_progress': ScanOrderModel.objects.filter(status='in_progress').count(),
            'pending_verification': ScanResultModel.objects.filter(is_verified=False).count(),
            'completed_today': ScanOrderModel.objects.filter(status='completed', ordered_at__date=today).count(),
        }
        return JsonResponse(data)
    except Exception:
        logger.exception("Failed fetching scan dashboard data")
        return JsonResponse({'error': 'Internal error'}, status=500)


# -------------------------
# Dashboard View
# -------------------------
class ScanDashboardView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = 'radiology/dashboard.html'
    permission_required = 'radiology.view_scanordermodel'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = date.today()

        # Basic stats
        context.update({
            'total_categories': ScanCategoryModel.objects.count(),
            'total_templates': ScanTemplateModel.objects.filter(is_active=True).count(),
            'today_orders': ScanOrderModel.objects.filter(ordered_at__date=today).count(),
            'pending_payments': ScanOrderModel.objects.filter(status='pending').count(),
            'scans_to_schedule': ScanOrderModel.objects.filter(status='paid').count(),
            'scheduled_scans': ScanOrderModel.objects.filter(status='scheduled').count(),
            'scans_in_progress': ScanOrderModel.objects.filter(status='in_progress').count(),
            'completed_today': ScanOrderModel.objects.filter(status='completed', ordered_at__date=today).count(),
            'pending_verification': ScanResultModel.objects.filter(is_verified=False).count(),
        })

        # Recent orders
        context['recent_orders'] = ScanOrderModel.objects.select_related(
            'patient', 'template'
        ).order_by('-ordered_at')[:10]

        # Today's scheduled scans
        context['todays_scheduled'] = ScanOrderModel.objects.filter(
            scheduled_date__date=today,
            status__in=['scheduled', 'in_progress']
        ).select_related('patient', 'template').order_by('scheduled_date')

        return context


# -------------------------
# Image Management Actions
# -------------------------
@login_required
@permission_required('radiology.delete_scanimagemodel', raise_exception=True)
def delete_scan_image(request, image_id):
    """Delete a scan image - AJAX endpoint"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    try:
        image = get_object_or_404(ScanImageModel, pk=image_id)
        scan_result = image.scan_result

        # Check if scan is verified (cannot delete images from verified scans)
        if scan_result.is_verified:
            return JsonResponse({
                'success': False,
                'error': 'Cannot delete images from verified scan results.'
            }, status=400)

        # Delete the image
        image.delete()

        return JsonResponse({
            'success': True,
            'message': 'Image deleted successfully'
        })

    except Exception as e:
        logger.exception("Error deleting scan image id=%s", image_id)
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while deleting image. Please contact administrator.'
        }, status=500)


@login_required
@permission_required('radiology.change_scanimagemodel', raise_exception=True)
def update_image_details(request, image_id):
    """Update image description and view type - AJAX endpoint"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)

    try:
        image = get_object_or_404(ScanImageModel, pk=image_id)

        # Check if scan is verified
        if image.scan_result.is_verified:
            return JsonResponse({
                'success': False,
                'error': 'Cannot edit images from verified scan results.'
            }, status=400)

        # Update details
        view_type = request.POST.get('view_type', '').strip()
        description = request.POST.get('description', '').strip()
        image_quality = request.POST.get('image_quality', '')

        image.view_type = view_type
        image.description = description
        if image_quality:
            image.image_quality = image_quality

        image.save(update_fields=['view_type', 'description', 'image_quality'])

        return JsonResponse({
            'success': True,
            'message': 'Image details updated successfully'
        })

    except Exception as e:
        logger.exception("Error updating image details id=%s", image_id)
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while updating image. Please contact administrator.'
        }, status=500)


# -------------------------
# Bulk Actions
# -------------------------
@login_required
@permission_required('radiology.change_scanordermodel', raise_exception=True)
def multi_scan_order_action(request):
    """Handle bulk actions on scan orders"""
    if request.method == 'POST':
        order_ids = request.POST.getlist('order')
        action = request.POST.get('action')

        if not order_ids:
            messages.error(request, 'No order selected.')
            return redirect(reverse('scan_order_index'))

        try:
            with transaction.atomic():
                orders = ScanOrderModel.objects.filter(id__in=order_ids)

                if action == 'mark_paid':
                    paid_count = 0
                    for order in orders.filter(status='pending'):
                        order.status = 'paid'
                        order.payment_status = True
                        order.payment_date = now()
                        order.payment_by = request.user
                        order.save(update_fields=['status', 'payment_status', 'payment_date', 'payment_by'])
                        paid_count += 1
                    messages.success(request, f'Marked {paid_count} scan order(s) as paid.')

                elif action == 'cancel':
                    cancelled_count = 0
                    for order in orders.exclude(status__in=['completed', 'cancelled']):
                        order.status = 'cancelled'
                        order.save(update_fields=['status'])
                        cancelled_count += 1
                    messages.success(request, f'Cancelled {cancelled_count} scan order(s).')
                else:
                    messages.error(request, 'Invalid action.')
        except Exception:
            logger.exception("Bulk scan order action failed for ids=%s action=%s", order_ids, action)
            messages.error(request, "An error occurred performing that action. Try again or contact admin.")
        return redirect(reverse('scan_order_index'))


# -------------------------
# Print Views
# -------------------------
@login_required
@permission_required('radiology.view_scanordermodel', raise_exception=True)
def print_scan_order(request, pk):
    order = get_object_or_404(ScanOrderModel, pk=pk)
    context = {
        'order': order,

    }
    return render(request, 'radiology/print/order.html', context)


@login_required
@permission_required('radiology.view_scanresultmodel', raise_exception=True)
def print_scan_result(request, pk):
    result = get_object_or_404(ScanResultModel, pk=pk)
    context = {
        'result': result,
        'order': result.order,
        'patient': result.order.patient,
        'images': result.images.all().order_by('sequence_number'),

    }
    return render(request, 'radiology/print/result.html', context)


# -------------------------
# Report Views
# -------------------------
class ScanReportView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = 'radiology/reports/index.html'
    permission_required = 'radiology.view_scanordermodel'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Date range from request or default to this month
        from_date = self.request.GET.get('from_date')
        to_date = self.request.GET.get('to_date')

        if not from_date:
            from_date = date.today().replace(day=1)  # First day of current month
        else:
            from_date = datetime.strptime(from_date, '%Y-%m-%d').date()

        if not to_date:
            to_date = date.today()
        else:
            to_date = datetime.strptime(to_date, '%Y-%m-%d').date()

        # Filter orders by date range
        orders = ScanOrderModel.objects.filter(
            ordered_at__date__range=[from_date, to_date]
        )

        # Statistics
        context.update({
            'from_date': from_date,
            'to_date': to_date,
            'total_orders': orders.count(),
            'total_revenue': orders.aggregate(Sum('amount_charged'))['amount_charged__sum'] or 0,
            'completed_scans': orders.filter(status='completed').count(),
            'cancelled_scans': orders.filter(status='cancelled').count(),
        })

        # Scan type breakdown
        context['scan_breakdown'] = orders.values(
            'template__category__name', 'template__name'
        ).annotate(
            count=Count('id'),
            revenue=Sum('amount_charged')
        ).order_by('-count')

        # Daily orders chart data
        context['daily_orders'] = orders.extra(
            select={'day': "date(ordered_at)"}
        ).values('day').annotate(
            count=Count('id'),
            revenue=Sum('amount_charged')
        ).order_by('day')

        return context


# -------------------------
# Scan Equipment Views
# -------------------------
class ScanEquipmentCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, CreateView
):
    model = ScanEquipmentModel
    permission_required = 'scan.add_scanequipmentmodel'
    form_class = ScanEquipmentForm
    template_name = 'scan/equipment/index.html'
    success_message = 'Scan Equipment Successfully Added'

    def get_success_url(self):
        return reverse('scan_equipment_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('scan_equipment_index'))
        return super().dispatch(request, *args, **kwargs)


class ScanEquipmentListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ScanEquipmentModel
    permission_required = 'scan.view_scanequipmentmodel'
    template_name = 'scan/equipment/index.html'
    context_object_name = "equipment_list"

    def get_queryset(self):
        return ScanEquipmentModel.objects.all().order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = ScanEquipmentForm()
        context['template_list'] = ScanTemplateModel.objects.filter(is_active=True).order_by('name')
        return context


class ScanEquipmentUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
):
    model = ScanEquipmentModel
    permission_required = 'scan.change_scanequipmentmodel'
    form_class = ScanEquipmentForm
    template_name = 'scan/equipment/index.html'
    success_message = 'Scan Equipment Successfully Updated'

    def get_success_url(self):
        return reverse('scan_equipment_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('scan_equipment_index'))
        return super().dispatch(request, *args, **kwargs)


class ScanEquipmentDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = ScanEquipmentModel
    permission_required = 'scan.delete_scanequipmentmodel'
    template_name = 'scan/equipment/delete.html'
    context_object_name = "equipment"
    success_message = 'Scan Equipment Successfully Deleted'

    def get_success_url(self):
        return reverse('scan_equipment_index')


# -------------------------
# Scan Appointment Views
# -------------------------
class ScanAppointmentCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, CreateView
):
    model = ScanAppointmentModel
    permission_required = 'scan.add_scanappointmentmodel'
    form_class = ScanAppointmentForm
    template_name = 'scan/appointment/create.html'
    success_message = 'Scan Appointment Successfully Created'

    def get_success_url(self):
        return reverse('scan_appointment_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['order_list'] = ScanOrderModel.objects.filter(status__in=['paid', 'scheduled']).select_related(
            'patient', 'template')
        context['equipment_list'] = ScanEquipmentModel.objects.filter(status='active')
        return context


class ScanAppointmentListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ScanAppointmentModel
    permission_required = 'scan.view_scanappointmentmodel'
    template_name = 'scan/appointment/index.html'
    context_object_name = "appointment_list"
    paginate_by = 20

    def get_queryset(self):
        return ScanAppointmentModel.objects.select_related('scan_order', 'equipment', 'technician').order_by(
            'appointment_date')


class ScanAppointmentDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = ScanAppointmentModel
    permission_required = 'scan.view_scanappointmentmodel'
    template_name = 'scan/appointment/detail.html'
    context_object_name = "appointment"


class ScanAppointmentUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
):
    model = ScanAppointmentModel
    permission_required = 'scan.change_scanappointmentmodel'
    form_class = ScanAppointmentForm
    template_name = 'scan/appointment/edit.html'
    success_message = 'Scan Appointment Successfully Updated'

    def get_success_url(self):
        return reverse('scan_appointment_detail', kwargs={'pk': self.object.pk})


class ScanAppointmentDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = ScanAppointmentModel
    permission_required = 'scan.delete_scanappointmentmodel'
    template_name = 'scan/appointment/delete.html'
    context_object_name = "appointment"
    success_message = 'Scan Appointment Successfully Deleted'

    def get_success_url(self):
        return reverse('scan_appointment_index')


# -------------------------
# Scan Template Builder Views
# -------------------------
class ScanTemplateBuilderCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, CreateView
):
    model = ScanTemplateBuilderModel
    permission_required = 'scan.add_scantemplatebuildermodel'
    form_class = ScanTemplateBuilderForm
    template_name = 'scan/template_builder/create.html'
    success_message = 'Template Builder Successfully Created'

    def get_success_url(self):
        return reverse('scan_template_builder_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category_list'] = ScanCategoryModel.objects.all().order_by('name')
        return context


class ScanTemplateBuilderListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ScanTemplateBuilderModel
    permission_required = 'scan.view_scantemplatebuildermodel'
    template_name = 'scan/template_builder/index.html'
    context_object_name = "builder_list"

    def get_queryset(self):
        return ScanTemplateBuilderModel.objects.select_related('category', 'created_template').order_by('-created_at')


class ScanTemplateBuilderDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = ScanTemplateBuilderModel
    permission_required = 'scan.view_scantemplatebuildermodel'
    template_name = 'scan/template_builder/detail.html'
    context_object_name = "builder"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        builder = self.object

        context.update({
            'can_build': not builder.is_processed and self.request.user.has_perm('scan.add_scantemplatemodel'),
            'preset_parameters': builder._get_preset_parameters() if builder.scan_preset != 'custom' else [],
        })
        return context


# -------------------------
# Scan Settings Views
# -------------------------
class ScanSettingCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = ScanSettingModel
    form_class = ScanSettingForm
    permission_required = 'scan.change_scansettingmodel'
    success_message = 'Scan Setting Created Successfully'
    template_name = 'scan/setting/create.html'

    def dispatch(self, request, *args, **kwargs):
        setting = ScanSettingModel.objects.first()
        if setting:
            return redirect('scan_setting_edit', pk=setting.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('scan_setting_detail', kwargs={'pk': self.object.pk})


class ScanSettingDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = ScanSettingModel
    permission_required = 'scan.view_scansettingmodel'
    template_name = 'scan/setting/detail.html'
    context_object_name = "scan_setting"

    def get_object(self):
        return ScanSettingModel.objects.first()


class ScanSettingUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
):
    model = ScanSettingModel
    form_class = ScanSettingForm
    permission_required = 'scan.change_scansettingmodel'
    success_message = 'Scan Setting Updated Successfully'
    template_name = 'scan/setting/create.html'

    def get_object(self):
        return ScanSettingModel.objects.first()

    def get_success_url(self):
        return reverse('scan_setting_detail', kwargs={'pk': self.object.pk})


# -------------------------
# Action Views (Status Updates)
# -------------------------
@login_required
@permission_required('scan.change_scanresultmodel', raise_exception=True)
def verify_result(request, pk):
    result = get_object_or_404(ScanResultModel, pk=pk)
    try:
        if result.is_verified:
            messages.info(request, "Result is already verified.")
            return redirect(reverse('scan_result_detail', kwargs={'pk': pk}))

        with transaction.atomic():
            result.is_verified = True
            result.verified_by = request.user
            result.verified_at = now()
            result.save(update_fields=['is_verified', 'verified_by', 'verified_at'])

        messages.success(request, f"Result verified for order {result.order.order_number}")
    except Exception:
        logger.exception("Error verifying scan result id=%s", pk)
        messages.error(request, "An error occurred while verifying result. Contact admin.")
    return redirect(reverse('scan_result_detail', kwargs={'pk': pk}))


@login_required
@permission_required('scan.change_scantemplatebuildermodel', raise_exception=True)
def build_template(request, pk):
    builder = get_object_or_404(ScanTemplateBuilderModel, pk=pk)
    try:
        if builder.is_processed:
            messages.info(request, "Template has already been built.")
            return redirect(reverse('scan_template_builder_detail', kwargs={'pk': pk}))

        result = builder.build_template()
        if result.get('error'):
            messages.error(request, result['error'])
        else:
            messages.success(request, f"Template '{builder.name}' successfully built!")
            return redirect(reverse('scan_template_detail', kwargs={'pk': result['template'].pk}))

    except Exception:
        logger.exception("Error building scan template from builder id=%s", pk)
        messages.error(request, "An error occurred while building template. Contact admin.")
    return redirect(reverse('scan_template_builder_detail', kwargs={'pk': pk}))


# -------------------------
# Bulk Actions
# -------------------------
@login_required
@permission_required('scan.delete_scancategorymodel', raise_exception=True)
def multi_category_action(request):
    """Handle bulk actions on categories (e.g., delete)."""
    if request.method == 'POST':
        category_ids = request.POST.getlist('category')
        action = request.POST.get('action')

        if not category_ids:
            messages.error(request, 'No category selected.')
            return redirect(reverse('scan_category_index'))

        try:
            with transaction.atomic():
                categories = ScanCategoryModel.objects.filter(id__in=category_ids)
                if action == 'delete':
                    count, _ = categories.delete()
                    messages.success(request, f'Successfully deleted {count} category(s).')
                else:
                    messages.error(request, 'Invalid action.')
        except Exception:
            logger.exception("Bulk category action failed for ids=%s action=%s", category_ids, action)
            messages.error(request, "An error occurred performing that action. Try again or contact admin.")
        return redirect(reverse('scan_category_index'))

    # GET - confirm action
    category_ids = request.GET.getlist('category')
    if not category_ids:
        messages.error(request, 'No category selected.')
        return redirect(reverse('scan_category_index'))

    action = request.GET.get('action')
    context = {'category_list': ScanCategoryModel.objects.filter(id__in=category_ids)}

    if action == 'delete':
        return render(request, 'scan/category/multi_delete.html', context)

    messages.error(request, 'Invalid action.')
    return redirect(reverse('scan_category_index'))


@login_required
@permission_required('scan.change_scanordermodel', raise_exception=True)
def multi_order_action(request):
    """Handle bulk actions on orders (e.g., update status)."""
    if request.method == 'POST':
        order_ids = request.POST.getlist('order')
        action = request.POST.get('action')

        if not order_ids:
            messages.error(request, 'No order selected.')
            return redirect(reverse('scan_order_index'))

        try:
            with transaction.atomic():
                orders = ScanOrderModel.objects.filter(id__in=order_ids)

                if action == 'mark_paid':
                    paid_count = 0
                    for order in orders.filter(status='pending'):
                        order.status = 'paid'
                        order.payment_status = True
                        order.payment_date = now()
                        order.payment_by = request.user
                        order.save(update_fields=['status', 'payment_status', 'payment_date', 'payment_by'])
                        paid_count += 1
                    messages.success(request, f'Marked {paid_count} order(s) as paid.')

                elif action == 'cancel':
                    cancelled_count = 0
                    for order in orders.exclude(status__in=['completed', 'cancelled']):
                        order.status = 'cancelled'
                        order.save(update_fields=['status'])
                        cancelled_count += 1
                    messages.success(request, f'Cancelled {cancelled_count} order(s).')
                else:
                    messages.error(request, 'Invalid action.')
        except Exception:
            logger.exception("Bulk scan order action failed for ids=%s action=%s", order_ids, action)
            messages.error(request, "An error occurred performing that action. Try again or contact admin.")
        return redirect(reverse('scan_order_index'))

    # GET - confirm action
    order_ids = request.GET.getlist('order')
    if not order_ids:
        messages.error(request, 'No order selected.')
        return redirect(reverse('scan_order_index'))

    action = request.GET.get('action')
    context = {'order_list': ScanOrderModel.objects.filter(id__in=order_ids).select_related('patient', 'template')}

    if action in ['mark_paid', 'cancel']:
        return render(request, 'scan/order/multi_action.html', {
            **context,
            'action': action,
            'action_title': 'Mark as Paid' if action == 'mark_paid' else 'Cancel Orders'
        })

    messages.error(request, 'Invalid action.')
    return redirect(reverse('scan_order_index'))


# -------------------------
# AJAX/API Views
# -------------------------
@login_required
def get_template_details(request):
    """Get scan template details for AJAX requests."""
    template_id = request.GET.get('template_id')
    if not template_id:
        return JsonResponse({'error': 'template_id is required'}, status=400)

    try:
        template = ScanTemplateModel.objects.get(id=template_id)
        data = {
            'id': template.id,
            'name': template.name,
            'code': template.code,
            'price': str(template.price),
            'scan_type': template.scan_type,
            'estimated_duration': template.estimated_duration,
            'parameters': template.measurement_names,
            'scan_parameters': template.scan_parameters
        }
        return JsonResponse(data)
    except ScanTemplateModel.DoesNotExist:
        return JsonResponse({'error': 'Template not found'}, status=404)
    except Exception:
        logger.exception("Failed fetching scan template details for id=%s", template_id)
        return JsonResponse({'error': 'Internal error'}, status=500)


@login_required
def get_patient_orders(request):
    """Get orders for a specific patient."""
    patient_id = request.GET.get('patient_id')
    if not patient_id:
        return JsonResponse({'error': 'patient_id is required'}, status=400)

    try:
        orders = ScanOrderModel.objects.filter(patient_id=patient_id).select_related('template').order_by(
            '-ordered_at')[:10]

        data = {
            'orders': [
                {
                    'id': order.id,
                    'order_number': order.order_number,
                    'template_name': order.template.name,
                    'status': order.status,
                    'ordered_at': order.ordered_at.strftime('%Y-%m-%d %H:%M'),
                }
                for order in orders
            ]
        }
        return JsonResponse(data)
    except Exception:
        logger.exception("Failed fetching scan patient orders for patient_id=%s", patient_id)
        return JsonResponse({'error': 'Internal error'}, status=500)


@login_required
def scan_dashboard_data(request):
    """Get dashboard statistics for AJAX requests."""
    try:
        today = date.today()

        data = {
            'today_orders': ScanOrderModel.objects.filter(ordered_at__date=today).count(),
            'pending_payments': ScanOrderModel.objects.filter(status='pending').count(),
            'scheduled_scans': ScanOrderModel.objects.filter(status='scheduled').count(),
            'scans_in_progress': ScanOrderModel.objects.filter(status='in_progress').count(),
            'pending_results': ScanOrderModel.objects.filter(status='in_progress').count(),
            'pending_verification': ScanResultModel.objects.filter(is_verified=False).count(),
            'inactive_equipment': ScanEquipmentModel.objects.filter(status='inactive').count(),
            'maintenance_due': ScanEquipmentModel.objects.filter(next_maintenance__lte=today, status='active').count(),
        }
        return JsonResponse(data)
    except Exception:
        logger.exception("Failed fetching scan dashboard data")
        return JsonResponse({'error': 'Internal error'}, status=500)


# -------------------------
# Dashboard View
# -------------------------
class ScanDashboardView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = 'scan/dashboard.html'
    permission_required = 'scan.view_scanordermodel'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = date.today()

        context.update({
            'total_categories': ScanCategoryModel.objects.count(),
            'total_templates': ScanTemplateModel.objects.filter(is_active=True).count(),
            'today_orders': ScanOrderModel.objects.filter(ordered_at__date=today).count(),
            'pending_payments': ScanOrderModel.objects.filter(status='pending').count(),
            'scheduled_scans': ScanOrderModel.objects.filter(status='scheduled').count(),
            'scans_in_progress': ScanOrderModel.objects.filter(status='in_progress').count(),
            'completed_today': ScanOrderModel.objects.filter(status='completed', ordered_at__date=today).count(),
            'pending_verification': ScanResultModel.objects.filter(is_verified=False).count(),
        })

        context['recent_orders'] = ScanOrderModel.objects.select_related('patient', 'template').order_by('-ordered_at')[
                                   :10]

        context['maintenance_due'] = ScanEquipmentModel.objects.filter(next_maintenance__lte=today, status='active')[:5]

        return context


# -------------------------
# Report Views
# -------------------------
class ScanReportView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = 'scan/reports/index.html'
    permission_required = 'scan.view_scanordermodel'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        from_date = self.request.GET.get('from_date')
        to_date = self.request.GET.get('to_date')

        if not from_date:
            from_date = date.today().replace(day=1)
        else:
            from_date = datetime.strptime(from_date, '%Y-%m-%d').date()

        if not to_date:
            to_date = date.today()
        else:
            to_date = datetime.strptime(to_date, '%Y-%m-%d').date()

        orders = ScanOrderModel.objects.filter(ordered_at__date__range=[from_date, to_date])

        context.update({
            'from_date': from_date,
            'to_date': to_date,
            'total_orders': orders.count(),
            'total_revenue': orders.aggregate(Sum('amount_charged'))['amount_charged__sum'] or 0,
            'completed_scans': orders.filter(status='completed').count(),
            'cancelled_scans': orders.filter(status='cancelled').count(),
        })

        context['scan_breakdown'] = orders.values('template__category__name', 'template__name').annotate(
            count=Count('id'),
            revenue=Sum('amount_charged')
        ).order_by('-count')

        context['daily_orders'] = orders.extra(select={'day': "date(ordered_at)"}).values('day').annotate(
            count=Count('id'),
            revenue=Sum('amount_charged')
        ).order_by('day')

        return context


# -------------------------
# Print Views
# -------------------------
@login_required
@permission_required('scan.view_scanordermodel', raise_exception=True)
def print_order(request, pk):
    order = get_object_or_404(ScanOrderModel, pk=pk)
    context = {
        'order': order,
        'scan_setting': ScanSettingModel.objects.first(),
    }
    return render(request, 'scan/print/order.html', context)


@login_required
@permission_required('scan.view_scanresultmodel', raise_exception=True)
def print_result(request, pk):
    result = get_object_or_404(ScanResultModel, pk=pk)
    context = {
        'result': result,
        'order': result.order,
        'patient': result.order.patient,
        'scan_setting': ScanSettingModel.objects.first(),
    }
    return render(request, 'scan/print/result.html', context)


# -------------------------
# Order Action Helpers (Payment / Schedule / Start / Complete)
# -------------------------
@login_required
def process_payment(request, pk):
    order = get_object_or_404(ScanOrderModel, pk=pk)
    try:
        if order.status != 'pending':
            messages.info(request, "Order payment has already been processed or order is not pending.")
            return redirect(reverse('scan_order_detail', kwargs={'pk': pk}))

        with transaction.atomic():
            order.status = 'paid'
            order.payment_status = True
            order.payment_date = now()
            order.payment_by = request.user
            order.save(update_fields=['status', 'payment_status', 'payment_date', 'payment_by'])

        messages.success(request, f"Payment processed for order {order.order_number}")
    except Exception:
        logger.exception("Error processing payment for scan order id=%s", pk)
        messages.error(request, "An error occurred while processing payment. Contact admin.")
    return redirect(reverse('scan_order_detail', kwargs={'pk': pk}))


@login_required
@permission_required('scan.change_scanordermodel', raise_exception=True)
def schedule_scan(request, pk):
    order = get_object_or_404(ScanOrderModel, pk=pk)
    try:
        if order.status != 'paid':
            messages.info(request, "Scan can only be scheduled for paid orders.")
            return redirect(reverse('scan_order_detail', kwargs={'pk': pk}))

        # Optionally read scheduled_date from POST if provided
        scheduled_date = None
        if request.method == 'POST':
            sd = request.POST.get('scheduled_date')
            if sd:
                try:
                    scheduled_date = datetime.strptime(sd, '%Y-%m-%dT%H:%M')
                except Exception:
                    scheduled_date = None

        with transaction.atomic():
            order.status = 'scheduled'
            if scheduled_date:
                order.scheduled_date = scheduled_date
            order.scheduled_by = request.user
            order.save(update_fields=['status', 'scheduled_date', 'scheduled_by'])

        messages.success(request, f"Scan scheduled for order {order.order_number}")
    except Exception:
        logger.exception("Error scheduling scan for order id=%s", pk)
        messages.error(request, "An error occurred while scheduling scan. Contact admin.")
    return redirect(reverse('scan_order_detail', kwargs={'pk': pk}))


@login_required
@permission_required('scan.change_scanordermodel', raise_exception=True)
def start_scan(request, pk):
    order = get_object_or_404(ScanOrderModel, pk=pk)
    try:
        if order.status != 'scheduled':
            messages.info(request, "Scan can only be started for scheduled orders.")
            return redirect(reverse('scan_order_detail', kwargs={'pk': pk}))

        with transaction.atomic():
            order.status = 'in_progress'
            order.scan_started_at = now()
            order.performed_by = request.user
            order.save(update_fields=['status', 'scan_started_at', 'performed_by'])

        messages.success(request, f"Scan started for order {order.order_number}")
    except Exception:
        logger.exception("Error starting scan for order id=%s", pk)
        messages.error(request, "An error occurred while starting scan. Contact admin.")
    return redirect(reverse('scan_order_detail', kwargs={'pk': pk}))


@login_required
@permission_required('scan.change_scanordermodel', raise_exception=True)
def complete_scan(request, pk):
    order = get_object_or_404(ScanOrderModel, pk=pk)
    try:
        if order.status != 'in_progress':
            messages.info(request, "Scan can only be completed for in-progress orders.")
            return redirect(reverse('scan_order_detail', kwargs={'pk': pk}))

        if not hasattr(order, 'result'):
            messages.error(request, "Cannot complete scan without results. Please add results first.")
            return redirect(reverse('scan_order_detail', kwargs={'pk': pk}))

        with transaction.atomic():
            order.status = 'completed'
            order.scan_completed_at = now()
            order.save(update_fields=['status', 'scan_completed_at'])

        messages.success(request, f"Scan completed for order {order.order_number}")
    except Exception:
        logger.exception("Error completing scan for order id=%s", pk)
        messages.error(request, "An error occurred while completing scan. Contact admin.")
    return redirect(reverse('scan_order_detail', kwargs={'pk': pk}))
