import logging
import json
from datetime import datetime, date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q, Count, Sum
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.timezone import now
from django.views.generic import (
    CreateView, ListView, UpdateView, DeleteView, DetailView, TemplateView
)

from patient.models import PatientModel
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
# Lab Test Category Views
# -------------------------
class LabTestCategoryCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    CreateView
):
    model = LabTestCategoryModel
    permission_required = 'laboratory.add_labtestcategorymodel'
    form_class = LabTestCategoryForm
    template_name = 'laboratory/category/index.html'
    success_message = 'Lab Test Category Successfully Created'

    def get_success_url(self):
        return reverse('lab_category_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('lab_category_index'))
        return super().dispatch(request, *args, **kwargs)


class LabTestCategoryListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = LabTestCategoryModel
    permission_required = 'laboratory.view_labtestcategorymodel'
    template_name = 'laboratory/category/index.html'
    context_object_name = "category_list"

    def get_queryset(self):
        return LabTestCategoryModel.objects.all().order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = LabTestCategoryForm()
        return context


class LabTestCategoryUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
):
    model = LabTestCategoryModel
    permission_required = 'laboratory.change_labtestcategorymodel'
    form_class = LabTestCategoryForm
    template_name = 'laboratory/category/index.html'
    success_message = 'Lab Test Category Successfully Updated'

    def get_success_url(self):
        return reverse('lab_category_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('lab_category_index'))
        return super().dispatch(request, *args, **kwargs)


class LabTestCategoryDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = LabTestCategoryModel
    permission_required = 'laboratory.delete_labtestcategorymodel'
    template_name = 'laboratory/category/delete.html'
    context_object_name = "category"
    success_message = 'Lab Test Category Successfully Deleted'

    def get_success_url(self):
        return reverse('lab_category_index')


# -------------------------
# Lab Test Template Views
# -------------------------
class LabTestTemplateCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    CreateView
):
    model = LabTestTemplateModel
    permission_required = 'laboratory.add_labtesttemplatemodel'
    form_class = LabTestTemplateForm
    template_name = 'laboratory/template/create.html'
    success_message = 'Lab Test Template Successfully Created'

    def get_success_url(self):
        return reverse('lab_template_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category_list'] = LabTestCategoryModel.objects.all().order_by('name')
        return context


class LabTestTemplateListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = LabTestTemplateModel
    permission_required = 'laboratory.view_labtesttemplatemodel'
    template_name = 'laboratory/template/index.html'
    context_object_name = "template_list"

    def get_queryset(self):
        return LabTestTemplateModel.objects.select_related('category').order_by('category__name', 'name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category_list'] = LabTestCategoryModel.objects.all().order_by('name')
        return context


class LabTestTemplateDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = LabTestTemplateModel
    permission_required = 'laboratory.view_labtesttemplatemodel'
    template_name = 'laboratory/template/detail.html'
    context_object_name = "template"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        template = self.object

        # Get orders for this template
        orders = LabTestOrderModel.objects.filter(template=template).select_related('patient').order_by('-ordered_at')[
                 :10]

        # Get equipment that supports this template
        equipment = template.equipment.filter(status='active')

        # Get reagents used for this template
        reagents = template.reagents.filter(is_active=True)

        context.update({
            'recent_orders': orders,
            'equipment_list': equipment,
            'reagent_list': reagents,
            'total_orders': LabTestOrderModel.objects.filter(template=template).count(),
        })
        return context


class LabTestTemplateUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
):
    model = LabTestTemplateModel
    permission_required = 'laboratory.change_labtesttemplatemodel'
    form_class = LabTestTemplateForm
    template_name = 'laboratory/template/edit.html'
    success_message = 'Lab Test Template Successfully Updated'

    def get_success_url(self):
        return reverse('lab_template_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category_list'] = LabTestCategoryModel.objects.all().order_by('name')
        context['template'] = self.object
        return context


class LabTestTemplateDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = LabTestTemplateModel
    permission_required = 'laboratory.delete_labtesttemplatemodel'
    template_name = 'laboratory/template/delete.html'
    context_object_name = "template"
    success_message = 'Lab Test Template Successfully Deleted'

    def get_success_url(self):
        return reverse('lab_template_index')


# -------------------------
# Lab Entry Point - Patient Verification
# -------------------------
class LabEntryView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Entry point for lab operations - patient verification"""
    permission_required = 'laboratory.view_labtestordermodel'
    template_name = 'laboratory/order/entry.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Laboratory - Patient Verification'
        return context


def verify_lab_patient_ajax(request):
    """AJAX view to verify patient by card number"""
    if not request.user.has_perm('laboratory.view_labtestordermodel'):
        return JsonResponse({'success': False, 'error': 'Permission denied'})

    card_number = request.GET.get('card_number', '').strip()
    if not card_number:
        return JsonResponse({'success': False, 'error': 'Please enter a card number'})

    try:
        patient = PatientModel.objects.get(card_number=card_number, status='active')

        # Get test counts
        test_counts = {
            'total': LabTestOrderModel.objects.filter(patient=patient).count(),
            'pending': LabTestOrderModel.objects.filter(patient=patient, status='pending').count(),
            'paid': LabTestOrderModel.objects.filter(patient=patient, status='paid').count(),
            'processing': LabTestOrderModel.objects.filter(patient=patient,
                                                           status__in=['collected', 'processing']).count(),
            'completed': LabTestOrderModel.objects.filter(patient=patient, status='completed').count(),
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
            'test_counts': test_counts
        })

    except PatientModel.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': f'No patient found with card number: {card_number}'
        })
    except Exception as e:

        return JsonResponse({
            'success': False,
            'error': f'An error occurred while verifying patient {str(e)}'
        })


# -------------------------
# Patient Lab Tests Management
# -------------------------
class PatientLabTestsView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """View patient's lab tests with grouping by date"""
    model = LabTestOrderModel
    permission_required = 'laboratory.view_labtestordermodel'
    template_name = 'laboratory/order/patient_tests.html'
    context_object_name = 'orders'
    paginate_by = 30

    def get_queryset(self):
        patient_id = self.kwargs.get('patient_id')
        self.patient = get_object_or_404(PatientModel, id=patient_id, status='active')

        queryset = LabTestOrderModel.objects.filter(
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
        context['status_choices'] = LabTestOrderModel.STATUS_CHOICES

        # Group orders by date
        orders_by_date = {}
        for order in context['orders']:
            order_date = order.ordered_at.date()
            if order_date not in orders_by_date:
                orders_by_date[order_date] = []
            orders_by_date[order_date].append(order)

        context['orders_by_date'] = orders_by_date

        # Get test counts for summary
        context['test_counts'] = {
            'total': LabTestOrderModel.objects.filter(patient=self.patient).count(),
            'pending': LabTestOrderModel.objects.filter(patient=self.patient, status='pending').count(),
            'paid': LabTestOrderModel.objects.filter(patient=self.patient, status='paid').count(),
            'collected': LabTestOrderModel.objects.filter(patient=self.patient, status='collected').count(),
            'processing': LabTestOrderModel.objects.filter(patient=self.patient, status='processing').count(),
            'completed': LabTestOrderModel.objects.filter(patient=self.patient, status='completed').count(),
        }

        # Get available test templates for new order
        context['template_list'] = LabTestTemplateModel.objects.filter(
            is_active=True
        ).select_related('category').order_by('category__name', 'name')

        return context


# -------------------------
# Lab Test Order CRUD Views
# -------------------------

class LabTestOrderCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = LabTestOrderModel
    permission_required = 'laboratory.add_labtestordermodel'
    form_class = LabTestOrderCreateForm
    template_name = 'laboratory/order/create.html'

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
        context['template_list'] = LabTestTemplateModel.objects.filter(is_active=True).select_related('category').order_by('category__name', 'name')
        return context

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        # Prefer an array-style field 'tests' (JS change recommended below)
        test_ids = request.POST.getlist('tests')
        # Fallback: capture any test_0, test_1 style
        if not test_ids:
            for k, v in request.POST.items():
                if k.startswith('test_') and v:
                    test_ids.append(v)

        if not test_ids:
            messages.error(request, "Please select at least one test.")
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
                for tid in test_ids:
                    try:
                        template = LabTestTemplateModel.objects.get(pk=int(tid))
                    except (ValueError, LabTestTemplateModel.DoesNotExist):
                        messages.warning(request, f"Test id {tid} not found — skipped.")
                        continue

                    order = LabTestOrderModel(
                        patient = patient,
                        template = template,
                        ordered_by = request.user,
                        status = 'pending',
                        amount_charged = template.price,
                        special_instructions = form.cleaned_data.get('special_instructions', ''),
                        expected_completion = form.cleaned_data.get('expected_completion'),
                    )
                    order.save()
                    created_orders.append(order)
        except Exception:
            logger.exception("Error creating lab orders")
            messages.error(request, "An error occurred creating orders. Contact admin.")
            return redirect(request.path)

        if created_orders:
            messages.success(request, f"Created {len(created_orders)} order(s).")
            return redirect(reverse('patient_lab_tests', kwargs={'patient_id': created_orders[0].patient.id}))
        else:
            messages.error(request, "No valid tests selected.")
            return redirect(request.path)


# -------------------------
# Payment Processing
# -------------------------
def process_lab_payments(request):
    """Process payments for selected lab tests"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})

    if not request.user.has_perm('laboratory.change_labtestordermodel'):
        return JsonResponse({'success': False, 'error': 'Permission denied'})

    selected_orders = request.POST.getlist('selected_orders')
    if not selected_orders:
        return JsonResponse({'success': False, 'error': 'No tests selected'})

    try:
        orders = LabTestOrderModel.objects.filter(
            id__in=selected_orders,
            status='pending'
        )

        if not orders.exists():
            return JsonResponse({'success': False, 'error': 'No valid pending tests found'})

        # Calculate total amount
        total_amount = sum(order.amount_charged or order.template.price for order in orders)

        # Update orders to paid status
        updated_count = 0
        for order in orders:
            order.status = 'paid'
            order.payment_status = True
            order.payment_date = timezone.now()
            order.payment_by = request.user
            if not order.amount_charged:
                order.amount_charged = order.template.price
            order.save()
            updated_count += 1

        return JsonResponse({
            'success': True,
            'message': f'Successfully processed payment for {updated_count} test(s)',
            'total_amount': float(total_amount)
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error processing payment: {str(e)}'})


# -------------------------
# Sample Collection
# -------------------------
def collect_sample(request, order_id):
    """Mark test sample as collected"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})

    if not request.user.has_perm('laboratory.change_labtestordermodel'):
        return JsonResponse({'success': False, 'error': 'Permission denied'})

    try:
        order = get_object_or_404(LabTestOrderModel, id=order_id, status='paid')

        sample_label = request.POST.get('sample_label', '').strip()
        expected_completion_str = request.POST.get('expected_completion', '')

        if not sample_label:
            return JsonResponse({'success': False, 'error': 'Sample label is required'})

        # Update order
        order.status = 'collected'
        order.sample_collected_at = timezone.now()
        order.sample_collected_by = request.user
        order.sample_label = sample_label

        # Set expected completion if provided
        if expected_completion_str:
            try:
                expected_completion = datetime.strptime(expected_completion_str, '%Y-%m-%dT%H:%M')
                order.expected_completion = expected_completion
            except ValueError:
                pass  # Invalid date format, ignore

        order.save()

        return JsonResponse({
            'success': True,
            'message': f'Sample collected for {order.template.name}',
            'sample_label': sample_label
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Error collecting sample: {str(e)}'})


# -------------------------
# Test Results (Dummy Page)
# -------------------------
class LabTestResultCreateView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Dummy page for creating test results - will be implemented later"""
    permission_required = 'laboratory.add_labtestresultmodel'
    template_name = 'laboratory/result/create.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Create Lab Test Results'
        # This will be updated later to handle specific test orders
        return context


# -------------------------
# Other Views (Updated existing ones)
# -------------------------
class LabTestOrderListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = LabTestOrderModel
    permission_required = 'laboratory.view_labtestordermodel'
    template_name = 'laboratory/order/index.html'
    context_object_name = "order_list"
    paginate_by = 20

    def get_queryset(self):
        queryset = LabTestOrderModel.objects.select_related(
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
        context['status_choices'] = LabTestOrderModel.STATUS_CHOICES
        context['patient_list'] = PatientModel.objects.filter(is_active=True).order_by('first_name')
        context['template_list'] = LabTestTemplateModel.objects.filter(is_active=True).order_by('name')

        # Add counts for dashboard
        context['status_counts'] = {
            'pending': LabTestOrderModel.objects.filter(status='pending').count(),
            'paid': LabTestOrderModel.objects.filter(status='paid').count(),
            'collected': LabTestOrderModel.objects.filter(status='collected').count(),
            'processing': LabTestOrderModel.objects.filter(status='processing').count(),
            'completed': LabTestOrderModel.objects.filter(status='completed').count(),
        }

        return context


class LabTestOrderDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = LabTestOrderModel
    permission_required = 'laboratory.view_labtestordermodel'
    template_name = 'laboratory/order/detail.html'
    context_object_name = "order"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = self.object

        # Check if results exist
        has_results = hasattr(order, 'result')

        context.update({
            'has_results': has_results,
            'can_process_payment': order.status == 'pending' and self.request.user.has_perm(
                'laboratory.change_labtestordermodel'),
            'can_collect_sample': order.status == 'paid' and self.request.user.has_perm(
                'laboratory.change_labtestordermodel'),
            'can_process_test': order.status == 'collected' and self.request.user.has_perm(
                'laboratory.change_labtestordermodel'),
            'can_complete_test': order.status == 'processing' and self.request.user.has_perm(
                'laboratory.change_labtestordermodel'),
        })

        return context


class LabTestOrderUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, UpdateView
):
    model = LabTestOrderModel
    permission_required = 'laboratory.change_labtestordermodel'
    form_class = LabTestOrderForm
    template_name = 'laboratory/order/edit.html'

    def get_success_url(self):
        return reverse('lab_order_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['order'] = self.object
        context['patient_list'] = PatientModel.objects.filter(is_active=True).order_by('first_name')
        context['template_list'] = LabTestTemplateModel.objects.filter(is_active=True).order_by('name')
        return context


# -------------------------
# Lab Test Result Views
# -------------------------
class LabTestResultCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    CreateView
):
    model = LabTestResultModel
    permission_required = 'laboratory.add_labtestresultmodel'
    form_class = LabTestResultForm
    template_name = 'laboratory/result/create.html'
    success_message = 'Lab Test Result Successfully Created'

    def get_success_url(self):
        return reverse('lab_result_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Only show orders that don't have results yet
        context['order_list'] = LabTestOrderModel.objects.filter(
            status__in=['processing', 'collected']
        ).exclude(result__isnull=False).select_related('patient', 'template')
        return context


class LabTestResultDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = LabTestResultModel
    permission_required = 'laboratory.view_labtestresultmodel'
    template_name = 'laboratory/result/detail.html'
    context_object_name = "result"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        result = self.object

        context.update({
            'can_verify': not result.is_verified and self.request.user.has_perm('laboratory.change_labtestresultmodel'),
            'order': result.order,
            'patient': result.order.patient,
            'template': result.order.template,
        })

        return context


class LabTestResultUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
):
    model = LabTestResultModel
    permission_required = 'laboratory.change_labtestresultmodel'
    form_class = LabTestResultForm
    template_name = 'laboratory/result/edit.html'
    success_message = 'Lab Test Result Successfully Updated'

    def get_success_url(self):
        return reverse('lab_result_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['result'] = self.object
        return context


class LabTestResultListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = LabTestResultModel
    permission_required = 'laboratory.view_labtestresultmodel'
    template_name = 'laboratory/result/index.html'
    context_object_name = "result_list"
    paginate_by = 20

    def get_queryset(self):
        return LabTestResultModel.objects.select_related(
            'order__patient', 'order__template', 'verified_by'
        ).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['pending_verification'] = LabTestResultModel.objects.filter(is_verified=False).count()
        context['abnormal_results'] = LabTestResultModel.objects.filter(
            is_verified=True).count()  # You'd need to implement has_abnormal_values logic
        return context


# -------------------------
# Lab Equipment Views
# -------------------------
class LabEquipmentCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    CreateView
):
    model = LabEquipmentModel
    permission_required = 'laboratory.add_labequipmentmodel'
    form_class = LabEquipmentForm
    template_name = 'laboratory/equipment/index.html'
    success_message = 'Lab Equipment Successfully Added'

    def get_success_url(self):
        return reverse('lab_equipment_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('lab_equipment_index'))
        return super().dispatch(request, *args, **kwargs)


class LabEquipmentListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = LabEquipmentModel
    permission_required = 'laboratory.view_labequipmentmodel'
    template_name = 'laboratory/equipment/index.html'
    context_object_name = "equipment_list"

    def get_queryset(self):
        return LabEquipmentModel.objects.all().order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = LabEquipmentForm()
        context['template_list'] = LabTestTemplateModel.objects.filter(is_active=True).order_by('name')
        return context


class LabEquipmentUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
):
    model = LabEquipmentModel
    permission_required = 'laboratory.change_labequipmentmodel'
    form_class = LabEquipmentForm
    template_name = 'laboratory/equipment/index.html'
    success_message = 'Lab Equipment Successfully Updated'

    def get_success_url(self):
        return reverse('lab_equipment_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('lab_equipment_index'))
        return super().dispatch(request, *args, **kwargs)


class LabEquipmentDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = LabEquipmentModel
    permission_required = 'laboratory.delete_labequipmentmodel'
    template_name = 'laboratory/equipment/delete.html'
    context_object_name = "equipment"
    success_message = 'Lab Equipment Successfully Deleted'

    def get_success_url(self):
        return reverse('lab_equipment_index')


# -------------------------
# Lab Reagent Views
# -------------------------
class LabReagentCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    CreateView
):
    model = LabReagentModel
    permission_required = 'laboratory.add_labreagentmodel'
    form_class = LabReagentForm
    template_name = 'laboratory/reagent/index.html'
    success_message = 'Lab Reagent Successfully Added'

    def get_success_url(self):
        return reverse('lab_reagent_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('lab_reagent_index'))
        return super().dispatch(request, *args, **kwargs)


class LabReagentListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = LabReagentModel
    permission_required = 'laboratory.view_labreagentmodel'
    template_name = 'laboratory/reagent/index.html'
    context_object_name = "reagent_list"

    def get_queryset(self):
        return LabReagentModel.objects.all().order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = LabReagentForm()
        context['template_list'] = LabTestTemplateModel.objects.filter(is_active=True).order_by('name')

        # Add alerts for low stock and expired reagents
        context['low_stock_reagents'] = LabReagentModel.objects.filter(
            current_stock__lte=models.F('minimum_stock'), is_active=True
        ).count()
        context['expired_reagents'] = LabReagentModel.objects.filter(
            expiry_date__lte=date.today(), is_active=True
        ).count()

        return context


class LabReagentUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
):
    model = LabReagentModel
    permission_required = 'laboratory.change_labreagentmodel'
    form_class = LabReagentForm
    template_name = 'laboratory/reagent/index.html'
    success_message = 'Lab Reagent Successfully Updated'

    def get_success_url(self):
        return reverse('lab_reagent_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('lab_reagent_index'))
        return super().dispatch(request, *args, **kwargs)


class LabReagentDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = LabReagentModel
    permission_required = 'laboratory.delete_labreagentmodel'
    template_name = 'laboratory/reagent/delete.html'
    context_object_name = "reagent"
    success_message = 'Lab Reagent Successfully Deleted'

    def get_success_url(self):
        return reverse('lab_reagent_index')


# -------------------------
# Lab Test Template Builder Views
# -------------------------
class LabTestTemplateBuilderCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    CreateView
):
    model = LabTestTemplateBuilderModel
    permission_required = 'laboratory.add_labtesttemplatebuildermodel'
    form_class = LabTestTemplateBuilderForm
    template_name = 'laboratory/template_builder/create.html'
    success_message = 'Template Builder Successfully Created'

    def get_success_url(self):
        return reverse('lab_template_builder_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category_list'] = LabTestCategoryModel.objects.all().order_by('name')
        return context


class LabTestTemplateBuilderListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = LabTestTemplateBuilderModel
    permission_required = 'laboratory.view_labtesttemplatebuildermodel'
    template_name = 'laboratory/template_builder/index.html'
    context_object_name = "builder_list"

    def get_queryset(self):
        return LabTestTemplateBuilderModel.objects.select_related('category', 'created_template').order_by(
            '-created_at')


class LabTestTemplateBuilderDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = LabTestTemplateBuilderModel
    permission_required = 'laboratory.view_labtesttemplatebuildermodel'
    template_name = 'laboratory/template_builder/detail.html'
    context_object_name = "builder"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        builder = self.object

        context.update({
            'can_build': not builder.is_processed and self.request.user.has_perm('laboratory.add_labtesttemplatemodel'),
            'preset_parameters': builder._get_preset_parameters() if builder.parameter_preset != 'custom' else [],
        })

        return context


# -------------------------
# Lab Settings Views
# -------------------------
class LabSettingCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = LabSettingModel
    form_class = LabSettingForm
    permission_required = 'laboratory.change_labsettingmodel'
    success_message = 'Lab Setting Created Successfully'
    template_name = 'laboratory/setting/create.html'

    def dispatch(self, request, *args, **kwargs):
        setting = LabSettingModel.objects.first()
        if setting:
            return redirect('lab_setting_edit', pk=setting.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('lab_setting_detail', kwargs={'pk': self.object.pk})


class LabSettingDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = LabSettingModel
    permission_required = 'laboratory.view_labsettingmodel'
    template_name = 'laboratory/setting/detail.html'
    context_object_name = "lab_setting"

    def get_object(self):
        return LabSettingModel.objects.first()


class LabSettingUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
):
    model = LabSettingModel
    form_class = LabSettingForm
    permission_required = 'laboratory.change_labsettingmodel'
    success_message = 'Lab Setting Updated Successfully'
    template_name = 'laboratory/setting/create.html'

    def get_object(self):
        return LabSettingModel.objects.first()

    def get_success_url(self):
        return reverse('lab_setting_detail', kwargs={'pk': self.object.pk})


# -------------------------
# Action Views (Status Updates)
# -------------------------
@login_required
@permission_required('laboratory.change_labtestresultmodel', raise_exception=True)
def verify_result(request, pk):
    result = get_object_or_404(LabTestResultModel, pk=pk)
    try:
        if result.is_verified:
            messages.info(request, "Result is already verified.")
            return redirect(reverse('lab_result_detail', kwargs={'pk': pk}))

        with transaction.atomic():
            result.is_verified = True
            result.verified_by = request.user
            result.verified_at = now()
            result.save(update_fields=['is_verified', 'verified_by', 'verified_at'])

        messages.success(request, f"Result verified for order {result.order.order_number}")
    except Exception:
        logger.exception("Error verifying result id=%s", pk)
        messages.error(request, "An error occurred while verifying result. Contact admin.")
    return redirect(reverse('lab_result_detail', kwargs={'pk': pk}))


@login_required
@permission_required('laboratory.change_labtesttemplatebuildermodel', raise_exception=True)
def build_template(request, pk):
    builder = get_object_or_404(LabTestTemplateBuilderModel, pk=pk)
    try:
        if builder.is_processed:
            messages.info(request, "Template has already been built.")
            return redirect(reverse('lab_template_builder_detail', kwargs={'pk': pk}))

        result = builder.build_template()
        if result.get('error'):
            messages.error(request, result['error'])
        else:
            messages.success(request, f"Template '{builder.name}' successfully built!")
            return redirect(reverse('lab_template_detail', kwargs={'pk': result['template'].pk}))

    except Exception:
        logger.exception("Error building template from builder id=%s", pk)
        messages.error(request, "An error occurred while building template. Contact admin.")
    return redirect(reverse('lab_template_builder_detail', kwargs={'pk': pk}))


# -------------------------
# Bulk Actions
# -------------------------
@login_required
@permission_required('laboratory.delete_labtestcategorymodel', raise_exception=True)
def multi_category_action(request):
    """Handle bulk actions on categories (e.g., delete)."""
    if request.method == 'POST':
        category_ids = request.POST.getlist('category')
        action = request.POST.get('action')

        if not category_ids:
            messages.error(request, 'No category selected.')
            return redirect(reverse('lab_category_index'))

        try:
            with transaction.atomic():
                categories = LabTestCategoryModel.objects.filter(id__in=category_ids)
                if action == 'delete':
                    count, _ = categories.delete()
                    messages.success(request, f'Successfully deleted {count} category(s).')
                else:
                    messages.error(request, 'Invalid action.')
        except Exception:
            logger.exception("Bulk category action failed for ids=%s action=%s", category_ids, action)
            messages.error(request, "An error occurred performing that action. Try again or contact admin.")
        return redirect(reverse('lab_category_index'))

    # GET - confirm action
    category_ids = request.GET.getlist('category')
    if not category_ids:
        messages.error(request, 'No category selected.')
        return redirect(reverse('lab_category_index'))

    action = request.GET.get('action')
    context = {'category_list': LabTestCategoryModel.objects.filter(id__in=category_ids)}

    if action == 'delete':
        return render(request, 'laboratory/category/multi_delete.html', context)

    messages.error(request, 'Invalid action.')
    return redirect(reverse('lab_category_index'))


@login_required
@permission_required('laboratory.change_labtestordermodel', raise_exception=True)
def multi_order_action(request):
    """Handle bulk actions on orders (e.g., update status)."""
    if request.method == 'POST':
        order_ids = request.POST.getlist('order')
        action = request.POST.get('action')

        if not order_ids:
            messages.error(request, 'No order selected.')
            return redirect(reverse('lab_order_index'))

        try:
            with transaction.atomic():
                orders = LabTestOrderModel.objects.filter(id__in=order_ids)

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
            logger.exception("Bulk order action failed for ids=%s action=%s", order_ids, action)
            messages.error(request, "An error occurred performing that action. Try again or contact admin.")
        return redirect(reverse('lab_order_index'))

    # GET - confirm action
    order_ids = request.GET.getlist('order')
    if not order_ids:
        messages.error(request, 'No order selected.')
        return redirect(reverse('lab_order_index'))

    action = request.GET.get('action')
    context = {'order_list': LabTestOrderModel.objects.filter(id__in=order_ids).select_related('patient', 'template')}

    if action in ['mark_paid', 'cancel']:
        return render(request, 'laboratory/order/multi_action.html', {
            **context,
            'action': action,
            'action_title': 'Mark as Paid' if action == 'mark_paid' else 'Cancel Orders'
        })

    messages.error(request, 'Invalid action.')
    return redirect(reverse('lab_order_index'))


# -------------------------
# AJAX/API Views
# -------------------------
@login_required
def get_template_details(request):
    """Get template details for AJAX requests."""
    template_id = request.GET.get('template_id')
    if not template_id:
        return JsonResponse({'error': 'template_id is required'}, status=400)

    try:
        template = LabTestTemplateModel.objects.get(id=template_id)
        data = {
            'id': template.id,
            'name': template.name,
            'code': template.code,
            'price': str(template.price),
            'sample_type': template.sample_type,
            'sample_volume': template.sample_volume,
            'parameters': template.parameter_names,
            'test_parameters': template.test_parameters
        }
        return JsonResponse(data)
    except LabTestTemplateModel.DoesNotExist:
        return JsonResponse({'error': 'Template not found'}, status=404)
    except Exception:
        logger.exception("Failed fetching template details for id=%s", template_id)
        return JsonResponse({'error': 'Internal error'}, status=500)


@login_required
def get_patient_orders(request):
    """Get orders for a specific patient."""
    patient_id = request.GET.get('patient_id')
    if not patient_id:
        return JsonResponse({'error': 'patient_id is required'}, status=400)

    try:
        orders = LabTestOrderModel.objects.filter(
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
                }
                for order in orders
            ]
        }
        return JsonResponse(data)
    except Exception:
        logger.exception("Failed fetching patient orders for patient_id=%s", patient_id)
        return JsonResponse({'error': 'Internal error'}, status=500)


@login_required
def lab_dashboard_data(request):
    """Get dashboard statistics for AJAX requests."""
    try:
        today = date.today()

        data = {
            'today_orders': LabTestOrderModel.objects.filter(ordered_at__date=today).count(),
            'pending_payments': LabTestOrderModel.objects.filter(status='pending').count(),
            'samples_to_collect': LabTestOrderModel.objects.filter(status='paid').count(),
            'tests_processing': LabTestOrderModel.objects.filter(status='processing').count(),
            'pending_results': LabTestOrderModel.objects.filter(status='collected').count(),
            'pending_verification': LabTestResultModel.objects.filter(is_verified=False).count(),
            'low_stock_reagents': LabReagentModel.objects.filter(
                current_stock__lte=models.F('minimum_stock'), is_active=True
            ).count(),
            'expired_reagents': LabReagentModel.objects.filter(
                expiry_date__lte=today, is_active=True
            ).count(),
            'inactive_equipment': LabEquipmentModel.objects.filter(status='inactive').count(),
        }
        return JsonResponse(data)
    except Exception:
        logger.exception("Failed fetching lab dashboard data")
        return JsonResponse({'error': 'Internal error'}, status=500)


# -------------------------
# Dashboard View
# -------------------------
class LabDashboardView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = 'laboratory/dashboard.html'
    permission_required = 'laboratory.view_labtestordermodel'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = date.today()

        # Basic stats
        context.update({
            'total_categories': LabTestCategoryModel.objects.count(),
            'total_templates': LabTestTemplateModel.objects.filter(is_active=True).count(),
            'today_orders': LabTestOrderModel.objects.filter(ordered_at__date=today).count(),
            'pending_payments': LabTestOrderModel.objects.filter(status='pending').count(),
            'samples_to_collect': LabTestOrderModel.objects.filter(status='paid').count(),
            'tests_processing': LabTestOrderModel.objects.filter(status='processing').count(),
            'completed_today': LabTestOrderModel.objects.filter(status='completed', ordered_at__date=today).count(),
            'pending_verification': LabTestResultModel.objects.filter(is_verified=False).count(),
        })

        # Recent orders
        context['recent_orders'] = LabTestOrderModel.objects.select_related(
            'patient', 'template'
        ).order_by('-ordered_at')[:10]

        # Alerts
        context['low_stock_reagents'] = LabReagentModel.objects.filter(
            current_stock__lte=models.F('minimum_stock'), is_active=True
        )[:5]

        context['expired_reagents'] = LabReagentModel.objects.filter(
            expiry_date__lte=today, is_active=True
        )[:5]

        context['maintenance_due'] = LabEquipmentModel.objects.filter(
            next_maintenance__lte=today, status='active'
        )[:5]

        return context


# -------------------------
# Report Views
# -------------------------
class LabReportView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = 'laboratory/reports/index.html'
    permission_required = 'laboratory.view_labtestordermodel'

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
        orders = LabTestOrderModel.objects.filter(
            ordered_at__date__range=[from_date, to_date]
        )

        # Statistics
        context.update({
            'from_date': from_date,
            'to_date': to_date,
            'total_orders': orders.count(),
            'total_revenue': orders.aggregate(Sum('amount_charged'))['amount_charged__sum'] or 0,
            'completed_tests': orders.filter(status='completed').count(),
            'cancelled_tests': orders.filter(status='cancelled').count(),
        })

        # Test type breakdown
        context['test_breakdown'] = orders.values(
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
# Print Views
# -------------------------
@login_required
@permission_required('laboratory.view_labtestordermodel', raise_exception=True)
def print_order(request, pk):
    order = get_object_or_404(LabTestOrderModel, pk=pk)
    context = {
        'order': order,
        'lab_setting': LabSettingModel.objects.first(),
    }
    return render(request, 'laboratory/print/order.html', context)


@login_required
@permission_required('laboratory.view_labtestresultmodel', raise_exception=True)
def print_result(request, pk):
    result = get_object_or_404(LabTestResultModel, pk=pk)
    context = {
        'result': result,
        'order': result.order,
        'patient': result.order.patient,
        'lab_setting': LabSettingModel.objects.first(),
    }
    return render(request, 'laboratory/print/result.html', context)


def process_payment(request, pk):
    order = get_object_or_404(LabTestOrderModel, pk=pk)
    try:
        if order.status != 'pending':
            messages.info(request, "Order payment has already been processed or order is not pending.")
            return redirect(reverse('lab_order_detail', kwargs={'pk': pk}))

        with transaction.atomic():
            order.status = 'paid'
            order.payment_status = True
            order.payment_date = now()
            order.payment_by = request.user
            order.save(update_fields=['status', 'payment_status', 'payment_date', 'payment_by'])

        messages.success(request, f"Payment processed for order {order.order_number}")
    except Exception:
        logger.exception("Error processing payment for order id=%s", pk)
        messages.error(request, "An error occurred while processing payment. Contact admin.")
    return redirect(reverse('lab_order_detail', kwargs={'pk': pk}))


@login_required
@permission_required('laboratory.change_labtestordermodel', raise_exception=True)
def collect_sample(request, order_id):
    pk = order_id
    order = get_object_or_404(LabTestOrderModel, pk=pk)
    try:
        if order.status != 'paid':
            messages.info(request, "Sample can only be collected for paid orders.")
            return redirect(reverse('lab_order_detail', kwargs={'pk': pk}))

        with transaction.atomic():
            order.status = 'collected'
            order.sample_collected_at = now()
            order.sample_collected_by = request.user
            if not order.sample_label:
                order.sample_label = f"SAMPLE-{order.order_number}"
            order.save(update_fields=['status', 'sample_collected_at', 'sample_collected_by', 'sample_label'])

        messages.success(request, f"Sample collected for order {order.order_number}")
    except Exception:
        logger.exception("Error collecting sample for order id=%s", pk)
        messages.error(request, "An error occurred while collecting sample. Contact admin.")
    return redirect(reverse('lab_order_detail', kwargs={'pk': pk}))


@login_required
@permission_required('laboratory.change_labtestordermodel', raise_exception=True)
def start_processing(request, pk):
    order = get_object_or_404(LabTestOrderModel, pk=pk)
    try:
        if order.status != 'collected':
            messages.info(request, "Test can only be processed for collected samples.")
            return redirect(reverse('lab_order_detail', kwargs={'pk': pk}))

        with transaction.atomic():
            order.status = 'processing'
            order.processed_at = now()
            order.processed_by = request.user
            order.save(update_fields=['status', 'processed_at', 'processed_by'])

        messages.success(request, f"Processing started for order {order.order_number}")
    except Exception:
        logger.exception("Error starting processing for order id=%s", pk)
        messages.error(request, "An error occurred while starting processing. Contact admin.")
    return redirect(reverse('lab_order_detail', kwargs={'pk': pk}))


@login_required
@permission_required('laboratory.change_labtestordermodel', raise_exception=True)
def complete_test(request, pk):
    order = get_object_or_404(LabTestOrderModel, pk=pk)
    try:
        if order.status != 'processing':
            messages.info(request, "Test can only be completed for processing orders.")
            return redirect(reverse('lab_order_detail', kwargs={'pk': pk}))

        # Check if results exist
        if not hasattr(order, 'result'):
            messages.error(request, "Cannot complete test without results. Please add results first.")
            return redirect(reverse('lab_order_detail', kwargs={'pk': pk}))

        with transaction.atomic():
            order.status = 'completed'
            order.save(update_fields=['status'])

        messages.success(request, f"Test completed for order {order.order_number}")
    except Exception:
        logger.exception("Error completing test for order id=%s", pk)
        messages.error(request, "An error occurred while completing test. Contact admin.")
    return redirect(reverse('lab_order_detail', kwargs={'pk': pk}))


