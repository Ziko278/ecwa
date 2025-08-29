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
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, CreateView
):
    model = ScanTemplateModel
    permission_required = 'scan.add_scantemplatemodel'
    form_class = ScanTemplateForm
    template_name = 'scan/template/create.html'
    success_message = 'Scan Template Successfully Created'

    def get_success_url(self):
        return reverse('scan_template_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category_list'] = ScanCategoryModel.objects.all().order_by('name')
        return context


class ScanTemplateListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ScanTemplateModel
    permission_required = 'scan.view_scantemplatemodel'
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
    permission_required = 'scan.view_scantemplatemodel'
    template_name = 'scan/template/detail.html'
    context_object_name = "template"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        template = self.object

        # Get recent orders for this template
        orders = ScanOrderModel.objects.filter(template=template).select_related('patient').order_by('-ordered_at')[:10]

        # Equipment that supports this template
        equipment = template.equipment.filter(status='active')

        context.update({
            'recent_orders': orders,
            'equipment_list': equipment,
            'total_orders': ScanOrderModel.objects.filter(template=template).count(),
        })
        return context


class ScanTemplateUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
):
    model = ScanTemplateModel
    permission_required = 'scan.change_scantemplatemodel'
    form_class = ScanTemplateForm
    template_name = 'scan/template/edit.html'
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
    permission_required = 'scan.delete_scantemplatemodel'
    template_name = 'scan/template/delete.html'
    context_object_name = "template"
    success_message = 'Scan Template Successfully Deleted'

    def get_success_url(self):
        return reverse('scan_template_index')


# -------------------------
# Scan Order Views
# -------------------------
class ScanOrderCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, CreateView
):
    model = ScanOrderModel
    permission_required = 'scan.add_scanordermodel'
    form_class = ScanOrderForm
    template_name = 'scan/order/create.html'
    success_message = 'Scan Order Successfully Created'

    def get_success_url(self):
        return reverse('scan_order_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['patient_list'] = PatientModel.objects.filter(is_active=True).order_by('first_name')
        context['template_list'] = ScanTemplateModel.objects.filter(is_active=True).select_related('category').order_by('category__name', 'name')
        return context

    def form_valid(self, form):
        form.instance.ordered_by = self.request.user
        return super().form_valid(form)


class ScanOrderListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ScanOrderModel
    permission_required = 'scan.view_scanordermodel'
    template_name = 'scan/order/index.html'
    context_object_name = "order_list"
    paginate_by = 20

    def get_queryset(self):
        queryset = ScanOrderModel.objects.select_related('patient', 'template', 'ordered_by').order_by('-ordered_at')

        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)

        patient = self.request.GET.get('patient')
        if patient:
            queryset = queryset.filter(patient__id=patient)

        template = self.request.GET.get('template')
        if template:
            queryset = queryset.filter(template__id=template)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = ScanOrderModel.STATUS_CHOICES
        context['patient_list'] = PatientModel.objects.filter(is_active=True).order_by('first_name')
        context['template_list'] = ScanTemplateModel.objects.filter(is_active=True).order_by('name')

        context['status_counts'] = {
            'pending': ScanOrderModel.objects.filter(status='pending').count(),
            'paid': ScanOrderModel.objects.filter(status='paid').count(),
            'scheduled': ScanOrderModel.objects.filter(status='scheduled').count(),
            'in_progress': ScanOrderModel.objects.filter(status='in_progress').count(),
            'completed': ScanOrderModel.objects.filter(status='completed').count(),
        }
        return context


class ScanOrderDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = ScanOrderModel
    permission_required = 'scan.view_scanordermodel'
    template_name = 'scan/order/detail.html'
    context_object_name = "order"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = self.object

        has_results = hasattr(order, 'result')

        context.update({
            'has_results': has_results,
            'can_process_payment': order.status == 'pending' and self.request.user.has_perm('scan.change_scanordermodel'),
            'can_schedule': order.status == 'paid' and self.request.user.has_perm('scan.change_scanordermodel'),
            'can_start_scan': order.status == 'scheduled' and self.request.user.has_perm('scan.change_scanordermodel'),
            'can_complete_scan': order.status == 'in_progress' and self.request.user.has_perm('scan.change_scanordermodel'),
        })
        return context


class ScanOrderUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
):
    model = ScanOrderModel
    permission_required = 'scan.change_scanordermodel'
    form_class = ScanOrderForm
    template_name = 'scan/order/edit.html'
    success_message = 'Scan Order Successfully Updated'

    def get_success_url(self):
        return reverse('scan_order_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['order'] = self.object
        context['patient_list'] = PatientModel.objects.filter(is_active=True).order_by('first_name')
        context['template_list'] = ScanTemplateModel.objects.filter(is_active=True).order_by('name')
        return context


# -------------------------
# Scan Result Views
# -------------------------
class ScanResultCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, CreateView
):
    model = ScanResultModel
    permission_required = 'scan.add_scanresultmodel'
    form_class = ScanResultForm
    template_name = 'scan/result/create.html'
    success_message = 'Scan Result Successfully Created'

    def get_success_url(self):
        return reverse('scan_result_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Only show orders that are in progress or scheduled/completed (depending on workflow)
        context['order_list'] = ScanOrderModel.objects.filter(
            status__in=['in_progress', 'scheduled']
        ).exclude(result__isnull=False).select_related('patient', 'template')
        return context


class ScanResultDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = ScanResultModel
    permission_required = 'scan.view_scanresultmodel'
    template_name = 'scan/result/detail.html'
    context_object_name = "result"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        result = self.object

        context.update({
            'can_verify': not result.is_verified and self.request.user.has_perm('scan.change_scanresultmodel'),
            'order': result.order,
            'patient': result.order.patient,
            'template': result.order.template,
        })
        return context


class ScanResultUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
):
    model = ScanResultModel
    permission_required = 'scan.change_scanresultmodel'
    form_class = ScanResultForm
    template_name = 'scan/result/edit.html'
    success_message = 'Scan Result Successfully Updated'

    def get_success_url(self):
        return reverse('scan_result_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['result'] = self.object
        return context


class ScanResultListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ScanResultModel
    permission_required = 'scan.view_scanresultmodel'
    template_name = 'scan/result/index.html'
    context_object_name = "result_list"
    paginate_by = 20

    def get_queryset(self):
        return ScanResultModel.objects.select_related('order__patient', 'order__template', 'verified_by').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['pending_verification'] = ScanResultModel.objects.filter(is_verified=False).count()
        # abnormal findings count using property
        context['abnormal_results'] = ScanResultModel.objects.filter(is_verified=True).count()
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
        context['order_list'] = ScanOrderModel.objects.filter(status__in=['paid', 'scheduled']).select_related('patient', 'template')
        context['equipment_list'] = ScanEquipmentModel.objects.filter(status='active')
        return context


class ScanAppointmentListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ScanAppointmentModel
    permission_required = 'scan.view_scanappointmentmodel'
    template_name = 'scan/appointment/index.html'
    context_object_name = "appointment_list"
    paginate_by = 20

    def get_queryset(self):
        return ScanAppointmentModel.objects.select_related('scan_order', 'equipment', 'technician').order_by('appointment_date')


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
        orders = ScanOrderModel.objects.filter(patient_id=patient_id).select_related('template').order_by('-ordered_at')[:10]

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

        context['recent_orders'] = ScanOrderModel.objects.select_related('patient', 'template').order_by('-ordered_at')[:10]

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
