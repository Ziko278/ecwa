import csv
import json
import logging
from datetime import datetime, date, time, timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.timezone import now
from django.views.decorators.http import require_POST
from django.views.generic import (
    CreateView, ListView, UpdateView, DeleteView, DetailView, TemplateView
)
from django.db.models import Q, Count, Sum
from django.contrib.auth.models import User
from consultation.models import *
from consultation.forms import *
from finance.forms import PatientTransactionForm
from consultation.models import PatientTransactionModel
from laboratory.models import LabTestOrderModel, LabTestCategoryModel, LabTestTemplateModel, LabSettingModel, \
    ExternalLabTestOrder
from patient.models import PatientModel
from human_resource.models import StaffModel
from pharmacy.models import DrugOrderModel, DrugModel, ExternalPrescription
from scan.models import ScanOrderModel, ScanCategoryModel, ScanTemplateModel, ExternalScanOrder

logger = logging.getLogger(__name__)


# -------------------------
# Utility Mixins
# -------------------------
class FlashFormErrorsMixin:
    """Mixin to flash form errors and redirect to success_url"""

    def form_invalid(self, form):
        try:
            for field, errors in form.errors.items():
                label = form.fields.get(field).label if form.fields.get(field) else field
                for error in errors:
                    messages.error(self.request, f"{label}: {error}")
        except Exception:
            logger.exception("Error processing form_invalid errors.")
            messages.error(self.request, "There was an error processing the form. Please try again.")
        return redirect(self.get_success_url())


class ConsultationContextMixin:
    """Add common consultation context data"""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context['specializations'] = SpecializationModel.objects.all().order_by('name')
            context['blocks'] = ConsultationBlockModel.objects.all().order_by('name')
            context['active_consultants'] = ConsultantModel.objects.filter(
                is_available_for_consultation=True
            ).select_related('staff', 'specialization')
        except Exception:
            logger.exception("Error loading consultation context")
        return context


# -------------------------
# 1. SPECIALIZATION VIEWS
# -------------------------
class SpecializationCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    SuccessMessageMixin, CreateView
):
    model = SpecializationModel
    permission_required = 'consultation.add_specializationmodel'
    form_class = SpecializationForm
    template_name = 'consultation/specialization/index.html'
    success_message = 'Specialization Successfully Registered'

    def get_success_url(self):
        return reverse('specialization_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('specialization_index'))
        return super().dispatch(request, *args, **kwargs)


class SpecializationListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = SpecializationModel
    permission_required = 'consultation.view_specializationmodel'
    template_name = 'consultation/specialization/index.html'
    context_object_name = "specialization_list"

    def get_queryset(self):
        return SpecializationModel.objects.all().order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = SpecializationForm()
        context['specialization_group_list'] = SpecializationGroupModel.objects.all()

        return context


class SpecializationUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    SuccessMessageMixin, UpdateView
):
    model = SpecializationModel
    permission_required = 'consultation.add_specializationmodel'
    form_class = SpecializationForm
    template_name = 'consultation/specialization/index.html'
    success_message = 'Specialization Successfully Updated'

    def get_success_url(self):
        return reverse('specialization_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('specialization_index'))
        return super().dispatch(request, *args, **kwargs)


class SpecializationDeleteView(
    LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, DeleteView
):
    model = SpecializationModel
    permission_required = 'consultation.add_specializationmodel'
    template_name = 'consultation/specialization/delete.html'
    context_object_name = "specialization"
    success_message = 'Specialization Successfully Deleted'

    def get_success_url(self):
        return reverse('specialization_index')


class SpecializationDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = SpecializationModel
    permission_required = 'consultation.view_specializationmodel'
    template_name = 'consultation/specialization/detail.html'
    context_object_name = "specialization"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        specialization = self.object
        context.update({
            'specialization_group_list': SpecializationGroupModel.objects.all(),
            'doctor_list': ConsultantModel.objects.filter(specialization=specialization),
            'fees': ConsultationFeeModel.objects.filter(specialization=specialization),
            'total_consultants': ConsultantModel.objects.filter(specialization=specialization).count(),
        })
        return context


# -------------------------
# 2. SPECIALIZATION GROUP VIEWS
# -------------------------


class SpecializationGroupCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    SuccessMessageMixin, CreateView
):
    model = SpecializationGroupModel
    permission_required = 'consultation.add_specializationmodel'
    form_class = SpecializationGroupForm
    template_name = 'consultation/specialization_group/index.html'
    success_message = 'Specialization Group Successfully Registered'

    def get_success_url(self):
        return reverse('specialization_group_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('specialization_group_index'))
        return super().dispatch(request, *args, **kwargs)


class SpecializationGroupListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = SpecializationGroupModel
    permission_required = 'consultation.view_specializationmodel'
    template_name = 'consultation/specialization_group/index.html'
    context_object_name = "specialization_group_list"

    def get_queryset(self):
        return SpecializationGroupModel.objects.all().order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = SpecializationGroupForm()
        return context


class SpecializationGroupUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    SuccessMessageMixin, UpdateView
):
    model = SpecializationGroupModel
    permission_required = 'consultation.add_specializationmodel'
    form_class = SpecializationGroupForm
    template_name = 'consultation/specialization_group/index.html'
    success_message = 'Specialization Group Successfully Updated'

    def get_success_url(self):
        return reverse('specialization_group_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('specialization_group_index'))
        return super().dispatch(request, *args, **kwargs)


class SpecializationGroupDeleteView(
    LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, DeleteView
):
    model = SpecializationGroupModel
    permission_required = 'consultation.add_specializationmodel'
    template_name = 'consultation/specialization_group/delete.html'
    context_object_name = "specialization_group"
    success_message = 'Specialization Group Successfully Deleted'

    def get_success_url(self):
        return reverse('specialization_group_index')


# -------------------------
# 2. CONSULTATION BLOCKS
# -------------------------
class ConsultationBlockCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    SuccessMessageMixin, CreateView
):
    model = ConsultationBlockModel
    permission_required = 'consultation.add_consultationblockmodel'
    form_class = ConsultationBlockForm
    template_name = 'consultation/block/index.html'
    success_message = 'Block Successfully Registered'

    def get_success_url(self):
        return reverse('block_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('block_index'))
        return super().dispatch(request, *args, **kwargs)


class ConsultationBlockListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ConsultationBlockModel
    permission_required = 'consultation.view_consultationblockmodel'
    template_name = 'consultation/block/index.html'
    context_object_name = "block_list"

    def get_queryset(self):
        return ConsultationBlockModel.objects.all().order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = ConsultationBlockForm()
        return context


class ConsultationBlockUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    SuccessMessageMixin, UpdateView
):
    model = ConsultationBlockModel
    permission_required = 'consultation.add_consultationblockmodel'
    form_class = ConsultationBlockForm
    template_name = 'consultation/block/index.html'
    success_message = 'Block Successfully Updated'

    def get_success_url(self):
        return reverse('block_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('block_index'))
        return super().dispatch(request, *args, **kwargs)


class ConsultationBlockDeleteView(
    LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, DeleteView
):
    model = ConsultationBlockModel
    permission_required = 'consultation.add_consultationblockmodel'
    template_name = 'consultation/block/delete.html'
    context_object_name = "consultation_block"
    success_message = 'Block Successfully Deleted'

    def get_success_url(self):
        return reverse('block_index')


# -------------------------
# 3. CONSULTATION ROOMS
# -------------------------
class ConsultationRoomCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    SuccessMessageMixin, CreateView
):
    model = ConsultationRoomModel
    permission_required = 'consultation.add_consultationblockmodel'
    form_class = ConsultationRoomForm
    template_name = 'consultation/room/index.html'
    success_message = 'Room Successfully Registered'

    def get_success_url(self):
        return reverse('room_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('room_index'))
        return super().dispatch(request, *args, **kwargs)


class ConsultationRoomListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ConsultationRoomModel
    permission_required = 'consultation.view_consultationblockmodel'
    template_name = 'consultation/room/index.html'
    context_object_name = "room_list"

    def get_queryset(self):
        return ConsultationRoomModel.objects.select_related('block', 'specialization').order_by('block__name', 'name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = ConsultationRoomForm()
        context['block_list'] = ConsultationBlockModel.objects.all().order_by('name')
        context['specialization_list'] = SpecializationModel.objects.all().order_by('name')
        return context


class ConsultationRoomUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    SuccessMessageMixin, UpdateView
):
    model = ConsultationRoomModel
    permission_required = 'consultation.add_consultationblockmodel'
    form_class = ConsultationRoomForm
    template_name = 'consultation/room/index.html'
    success_message = 'Room Successfully Updated'

    def get_success_url(self):
        return reverse('room_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('room_index'))
        return super().dispatch(request, *args, **kwargs)


class ConsultationRoomDeleteView(
    LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, DeleteView
):
    model = ConsultationRoomModel
    permission_required = 'consultation.add_consultationblockmodel'
    template_name = 'consultation/room/delete.html'
    context_object_name = "room"
    success_message = 'Room Successfully Deleted'

    def get_success_url(self):
        return reverse('room_index')


# -------------------------
# 4. CONSULTANTS (Multi-field - separate pages)
# -------------------------
class ConsultantCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, ConsultationContextMixin,
    SuccessMessageMixin, CreateView
):
    model = ConsultantModel
    permission_required = 'consultation.add_consultantmodel'
    form_class = ConsultantForm
    template_name = 'consultation/consultant/create.html'
    success_message = 'Consultant Successfully Registered'

    def get_success_url(self):
        return reverse('consultant_list')

    def form_invalid(self, form):
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f"{field}: {error}")
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get all active staff without prefetching the 'created_by' user
        context['staff_list'] = StaffModel.objects.filter(
            status='active'
        ).order_by('first_name', 'last_name')
        return context


class ConsultantListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ConsultantModel
    permission_required = 'consultation.view_consultantmodel'
    template_name = 'consultation/consultant/index.html'
    context_object_name = "consultant_list"

    def get_queryset(self):
        return ConsultantModel.objects.select_related(
            'staff', 'specialization', 'assigned_room'
        ).order_by('specialization__name', 'staff__first_name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Add active patient counts and transfer data for each consultant
        today = timezone.localdate()
        for consultant in context['consultant_list']:
            # Get active patients (not completed/cancelled)
            active_patients = PatientQueueModel.objects.filter(
                consultant=consultant,
                status__in=['waiting_vitals', 'vitals_done', 'with_doctor', 'consultation_paused'],
                joined_queue_at__date=today
            ).select_related('patient')

            consultant.active_patient_count = active_patients.count()
            consultant.active_patients_list = list(active_patients)

            # Get available doctors in same specialization for transfers
            available_doctors = ConsultantModel.objects.filter(
                specialization=consultant.specialization,
                is_available_for_consultation=True
            ).exclude(id=consultant.id).select_related('staff')

            consultant.transfer_options = list(available_doctors)
            consultant.can_be_disabled = consultant.active_patient_count == 0 or len(consultant.transfer_options) > 0

        return context


class ConsultantQueueView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """View to manage a specific consultant's queue"""
    model = PatientQueueModel
    permission_required = 'consultation.add_consultantmodel'
    template_name = 'consultation/consultant/queue.html'
    context_object_name = "queue_list"

    def get_queryset(self):
        self.consultant = get_object_or_404(ConsultantModel, pk=self.kwargs['pk'])
        today = timezone.localdate()
        return PatientQueueModel.objects.filter(
            consultant=self.consultant,
            status__in=['waiting_vitals', 'vitals_done', 'with_doctor', 'consultation_paused'],
            joined_queue_at__date=today
        ).select_related('patient').order_by('priority_level', 'joined_queue_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['consultant'] = self.consultant

        # Get available doctors in same specialization for transfers
        available_doctors = ConsultantModel.objects.filter(
            specialization=self.consultant.specialization,
            is_available_for_consultation=True
        ).exclude(id=self.consultant.id).select_related('staff')

        context['available_doctors'] = available_doctors
        return context


@login_required
@permission_required('consultation.add_consultantmodel', raise_exception=True)
def toggle_consultant_availability(request, pk):
    """Enhanced toggle that handles patient transfers"""
    if request.method == 'POST':
        consultant = get_object_or_404(ConsultantModel, pk=pk)

        # If making unavailable, check for active patients
        if consultant.is_available_for_consultation:
            today = timezone.localdate()
            active_patients = PatientQueueModel.objects.filter(
                consultant=consultant,
                status__in=['waiting_vitals', 'vitals_done', 'with_doctor', 'consultation_paused'],
                joined_queue_at__date=today
            )

            if active_patients.exists():
                # Get transfer data from form
                transfer_patients = request.POST.get('transfer_patients')

                if transfer_patients:
                    # Get selected doctors for transfer
                    selected_doctors = []
                    for key, value in request.POST.items():
                        if key.startswith('transfer_doctor_') and value == 'on':
                            doctor_id = key.replace('transfer_doctor_', '')
                            selected_doctors.append(doctor_id)

                    if selected_doctors:
                        # Transfer patients to selected doctors in round-robin fashion
                        try:
                            with transaction.atomic():
                                available_doctors = ConsultantModel.objects.filter(
                                    id__in=selected_doctors,
                                    is_available_for_consultation=True
                                )

                                if available_doctors.exists():
                                    doctor_list = list(available_doctors)

                                    for i, patient_queue in enumerate(active_patients):
                                        # Assign to doctor using round-robin
                                        target_doctor = doctor_list[i % len(doctor_list)]
                                        patient_queue.consultant = target_doctor
                                        patient_queue.save()

                                    # Now make consultant unavailable
                                    consultant.is_available_for_consultation = False
                                    consultant.save(update_fields=['is_available_for_consultation'])

                                    messages.success(request,
                                                     f"Dr. {consultant.staff}'s status updated to unavailable. "
                                                     f"{active_patients.count()} patients transferred to other doctors.")
                                else:
                                    messages.error(request, "Selected doctors are no longer available for transfer.")

                        except Exception as e:
                            messages.error(request, f"An error occurred during transfer: {e}")
                    else:
                        messages.error(request, "Please select at least one doctor for patient transfer.")
                else:
                    messages.error(request, "Cannot make consultant unavailable with active patients.")
            else:
                # No active patients, safe to toggle
                consultant.is_available_for_consultation = False
                consultant.save(update_fields=['is_available_for_consultation'])
                messages.success(request, f"Dr. {consultant.staff}'s status updated to unavailable.")
        else:
            # Making available
            consultant.is_available_for_consultation = True
            consultant.save(update_fields=['is_available_for_consultation'])
            messages.success(request, f"Dr. {consultant.staff}'s status updated to available.")

    return redirect('consultant_list')


@require_POST
@login_required
@permission_required('consultation.add_consultantmodel', raise_exception=True)
def transfer_patient_ajax(request, queue_id, new_consultant_id):
    """Transfer a single patient to another consultant via AJAX"""
    try:
        queue_entry = get_object_or_404(PatientQueueModel, pk=queue_id)
        new_consultant = get_object_or_404(ConsultantModel, pk=new_consultant_id)

        # Validation checks
        if queue_entry.status in ['consultation_completed', 'cancelled']:
            return JsonResponse({
                'success': False,
                'error': 'Cannot transfer completed/cancelled patients.'
            }, status=400)

        if not new_consultant.is_available_for_consultation:
            return JsonResponse({
                'success': False,
                'error': 'Target consultant is not available.'
            }, status=400)

        # Check if same specialization
        if queue_entry.specialization != new_consultant.specialization:
            return JsonResponse({
                'success': False,
                'error': 'Cannot transfer to consultant with different specialization.'
            }, status=400)

        with transaction.atomic():
            old_consultant_name = str(queue_entry.consultant) if queue_entry.consultant else "Unassigned"
            queue_entry.consultant = new_consultant
            queue_entry.save()

        return JsonResponse({
            'success': True,
            'message': f'Patient transferred from {old_consultant_name} to Dr. {new_consultant.staff}',
            'new_consultant': {
                'id': new_consultant.id,
                'name': str(new_consultant.staff),
                'specialization': new_consultant.specialization.name
            }
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Transfer failed: {str(e)}'
        }, status=500)


@require_POST
@login_required
@permission_required('consultation.add_consultantmodel', raise_exception=True)
def bulk_transfer_patients_ajax(request):
    """Transfer multiple patients at once"""
    try:
        queue_ids = request.POST.getlist('queue_ids[]')
        target_doctors = request.POST.getlist('target_doctors[]')

        if not queue_ids or not target_doctors:
            return JsonResponse({
                'success': False,
                'error': 'Missing queue IDs or target doctors'
            }, status=400)

        with transaction.atomic():
            queue_entries = PatientQueueModel.objects.filter(
                id__in=queue_ids,
                status__in=['waiting_vitals', 'vitals_done', 'with_doctor', 'consultation_paused']
            )

            target_consultants = list(ConsultantModel.objects.filter(
                id__in=target_doctors,
                is_available_for_consultation=True
            ))

            if not target_consultants:
                return JsonResponse({
                    'success': False,
                    'error': 'No available target consultants found'
                }, status=400)

            transferred_count = 0
            for i, queue_entry in enumerate(queue_entries):
                # Assign using round-robin
                target_consultant = target_consultants[i % len(target_consultants)]
                queue_entry.consultant = target_consultant
                queue_entry.save()
                transferred_count += 1

            return JsonResponse({
                'success': True,
                'message': f'Successfully transferred {transferred_count} patients',
                'transferred_count': transferred_count
            })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Bulk transfer failed: {str(e)}'
        }, status=500)


class ConsultantUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin,
    SuccessMessageMixin, UpdateView
):
    model = ConsultantModel
    permission_required = 'consultation.add_consultantmodel'
    form_class = ConsultantForm
    template_name = 'consultation/consultant/update.html'
    success_message = 'Consultant Successfully Updated'
    context_object_name = "consultant" # Ensure the object is available as 'consultant' in template

    def get_success_url(self):
        return reverse('consultant_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get all active staff for the dropdown, without prefetching 'created_by'
        context['staff_list'] = StaffModel.objects.filter(
            status='active'
        ).order_by('first_name', 'last_name')
        return context

    def form_invalid(self, form):
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f"{field}: {error}")
        return super().form_invalid(form)


class ConsultantDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = ConsultantModel
    permission_required = 'consultation.view_consultantmodel'
    template_name = 'consultation/consultant/detail.html'
    context_object_name = "consultant"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        consultant = self.object
        today = date.today()

        context.update({
            'today_schedule': DoctorScheduleModel.objects.filter(
                consultant=consultant, date=today
            ).first(),
            'upcoming_schedules': DoctorScheduleModel.objects.filter(
                consultant=consultant, date__gte=today
            ).order_by('date')[:10],
            'today_queue': PatientQueueModel.objects.filter(
                consultant=consultant,
                joined_queue_at__date=today
            ).count(),
            'consultation_stats': self.get_consultation_stats(consultant),
        })
        return context

    def get_consultation_stats(self, consultant):
        """Get consultant statistics"""
        try:
            today = date.today()
            this_week = today - timedelta(days=7)
            this_month = today - timedelta(days=30)

            return {
                'today': PatientQueueModel.objects.filter(
                    consultant=consultant,
                    joined_queue_at__date=today
                ).count(),
                'this_week': PatientQueueModel.objects.filter(
                    consultant=consultant,
                    joined_queue_at__date__gte=this_week
                ).count(),
                'this_month': PatientQueueModel.objects.filter(
                    consultant=consultant,
                    joined_queue_at__date__gte=this_month
                ).count(),
            }
        except Exception:
            return {'today': 0, 'this_week': 0, 'this_month': 0}


class ConsultantDeleteView(
    LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, DeleteView
):
    model = ConsultantModel
    permission_required = 'consultation.add_consultantmodel'
    template_name = 'consultation/consultant/delete.html'
    context_object_name = "consultant"
    success_message = 'Consultant Successfully Deleted'

    def get_success_url(self):
        return reverse('consultant_list')



# -------------------------
# 5. CONSULTATION FEES (Simple - index pattern)
# -------------------------
class ConsultationFeeCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    SuccessMessageMixin, CreateView
):
    model = ConsultationFeeModel
    permission_required = 'consultation.add_consultationfeemodel'
    form_class = ConsultationFeeForm
    template_name = 'consultation/fee/create.html'
    success_message = 'Consultation Fee Successfully Registered'

    def get_success_url(self):
        return reverse('consultation_fee_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('consultation_fee_index'))
        return super().dispatch(request, *args, **kwargs)


class ConsultationFeeListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ConsultationFeeModel
    permission_required = 'consultation.view_consultationfeemodel'
    template_name = 'consultation/fee/index.html'
    context_object_name = "fee_list"

    def get_queryset(self):
        return ConsultationFeeModel.objects.select_related('specialization').order_by(
            'specialization__name', 'patient_category'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = ConsultationFeeForm()
        return context


class ConsultationFeeUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    SuccessMessageMixin, UpdateView
):
    model = ConsultationFeeModel
    permission_required = 'consultation.add_consultationfeemodel'
    form_class = ConsultationFeeForm
    template_name = 'consultation/fee/update.html'
    success_message = 'Consultation Fee Successfully Updated'

    def get_success_url(self):
        return reverse('consultation_fee_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('consultation_fee_index'))
        return super().dispatch(request, *args, **kwargs)


class ConsultationFeeDeleteView(
    LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, DeleteView
):
    model = ConsultationFeeModel
    permission_required = 'consultation.add_consultationfeemodel'
    template_name = 'consultation/fee/delete.html'
    context_object_name = "fee"
    success_message = 'Consultation Fee Successfully Deleted'

    def get_success_url(self):
        return reverse('consultation_fee_index')


# -------------------------
# 6. CONSULTATION PAYMENTS (Multi-field)
# -------------------------

class ConsultationPaymentCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = PatientTransactionModel
    permission_required = 'consultation.add_patientvitalsmodel'
    form_class = PatientTransactionForm
    template_name = 'consultation/payment/create.html'

    def get_success_url(self):
        view_queue_perm = 'patient_queue.view_patientqueuemodel'

        if self.request.user.has_perm(view_queue_perm):
            # If the user has permission, redirect to the queue index.
            return reverse('patient_queue_index')

        else:
            # Otherwise, redirect back to the payment page to make another payment.
            return reverse('consultation_payment_create')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['specializations'] = SpecializationModel.objects.all()
        return context

    @transaction.atomic
    def form_valid(self, form):
        try:
            patient = form.cleaned_data.get('patient')
            fee_structure = form.cleaned_data.get('fee_structure')
            amount_to_pay = fee_structure.amount

            # 1. Validate patient's wallet balance
            if not hasattr(patient, 'wallet') or patient.wallet.amount < amount_to_pay:
                messages.error(self.request, 'Insufficient wallet balance.')
                return self.form_invalid(form)

            # 2. Prepare the transaction record
            transaction_record = form.save(commit=False)
            transaction_record.old_balance = patient.wallet.amount
            transaction_record.new_balance = patient.wallet.amount - amount_to_pay
            transaction_record.date = date.today()
            transaction_record.amount = amount_to_pay
            transaction_record.received_by = self.request.user
            transaction_record.payment_method = 'wallet'
            transaction_record.transaction_type = 'consultation_payment'
            transaction_record.transaction_direction = 'out'
            transaction_record.status = 'completed'

            # Calculate 'valid_till' date
            validity_days = fee_structure.validity_in_days
            today = date.today()
            cutoff_time = time(20, 0)  # 8:00 PM
            start_date_for_validity = today if timezone.now().time() < cutoff_time else today + timedelta(days=1)
            transaction_record.valid_till = start_date_for_validity + timedelta(days=validity_days - 1)

            transaction_record.save()
            self.object = transaction_record

            # 3. Update the wallet balance
            patient.wallet.amount -= amount_to_pay
            patient.wallet.save()

            specialization = fee_structure.specialization

            # 4. Create the queue entry using the new helper function
            queue_entry = _create_queue_entry_with_vitals_check(
                patient=patient,
                payment_transaction=self.object,
                specialization=fee_structure.specialization,
                user=self.request.user
            )

            messages.success(
                self.request,
                f'Payment of ₦{amount_to_pay} processed successfully! Patient added to queue with number {queue_entry.queue_number}.'
            )
            return redirect(self.get_success_url())

        except Exception as e:
            messages.error(self.request, f"An unexpected error occurred: {str(e)}")
            return self.form_invalid(form)


# AJAX endpoints for the wallet payment flow
@login_required
def verify_patient_ajax(request):
    """Verify patient by card number and return wallet details"""
    card_number = request.GET.get('card_number', '').strip()

    if not card_number:
        return JsonResponse({'error': 'Card number required'}, status=400)

    try:
        # Look up patient by patient_id (card number)
        patient = PatientModel.objects.get(card_number__iexact=card_number)

        # Get wallet balance
        wallet_balance = 0
        has_wallet = False
        if hasattr(patient, 'wallet'):
            wallet_balance = float(patient.wallet.amount)
            has_wallet = True

        # Check for active insurance
        active_insurance = None
        if hasattr(patient, 'insurance_policies'):
            active_insurance = patient.insurance_policies.filter(
                is_active=True,
                valid_to__gt=date.today()
            ).first()

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
            },
            'wallet': {
                'has_wallet': has_wallet,
                'balance': wallet_balance,
                'formatted_balance': f'₦{wallet_balance:,.2f}'
            },
            'insurance': {
                'has_insurance': bool(active_insurance),
                'provider': active_insurance.coverage_plan.hmo.insurance_provider.__str__() if active_insurance else None,
                'coverage_percentage': float(active_insurance.coverage_plan.consultation_covered) if active_insurance else 0,
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
def get_consultation_fees_ajax(request):
    """Get consultation fees for selected specialization"""
    specialization_id = request.GET.get('specialization_id')
    patient_id = request.GET.get('patient_id')
    today = date.today()

    if not specialization_id:
        return JsonResponse({'error': 'Specialization ID required'}, status=400)

    try:
        specialization = SpecializationModel.objects.get(id=specialization_id)

        # Get patient to check insurance status
        patient_category = 'regular'
        if patient_id:
            patient = PatientModel.objects.get(id=patient_id)

            # NEW: Check for valid, un-used payment for this specialization's group
            if specialization.group:
                valid_payment = PatientTransactionModel.objects.filter(
                    patient=patient,
                    transaction_type='consultation_payment',
                    status='completed',
                    valid_till__gte=today,
                    fee_structure__specialization__group=specialization.group
                ).order_by('-created_at').first()

                if valid_payment:
                    return JsonResponse({
                        'success': True,
                        'has_valid_payment': True,
                        'payment_id': valid_payment.id,
                        'message': f"Patient has a valid payment for the {specialization.group.name} group.",
                        'fee': {
                            'id': valid_payment.fee_structure.id,
                            'amount': float(valid_payment.amount),
                            'formatted_amount': f'₦{valid_payment.amount:,.2f}',
                            'patient_category': valid_payment.fee_structure.get_patient_category_display(),
                        }
                    })

            # Check if patient has active insurance
            if hasattr(patient, 'insurance_policies'):
                active_insurance = patient.insurance_policies.filter(
                    is_active=True,
                    valid_to__gte=today
                ).exists()
                if active_insurance:
                    patient_category = 'insurance'

        # Get consultation fee for new payment
        fee = ConsultationFeeModel.objects.filter(
            specialization_id=specialization_id,
            patient_category=patient_category,
            is_active=True
        ).first()

        if not fee:
            # Try to get regular fee if insurance fee not available
            fee = ConsultationFeeModel.objects.filter(
                specialization_id=specialization_id,
                patient_category='regular',
                is_active=True
            ).first()

        if fee:
            return JsonResponse({
                'success': True,
                'has_valid_payment': False,
                'fee': {
                    'id': fee.id,
                    'amount': float(fee.amount),
                    'formatted_amount': f'₦{fee.amount:,.2f}',
                    'patient_category': fee.get_patient_category_display(),
                }
            })
        else:
            return JsonResponse({
                'error': 'No consultation fee found for this specialization'
            }, status=404)

    except SpecializationModel.DoesNotExist:
        return JsonResponse({
            'error': 'Specialization not found'
        }, status=404)
    except PatientModel.DoesNotExist:
        return JsonResponse({
            'error': 'Patient not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'error': f'Error retrieving consultation fees: {str(e)}'
        }, status=500)


@login_required
def get_specialization_consultants_ajax(request):
    """Get available consultants for selected specialization"""
    specialization_id = request.GET.get('specialization_id')

    if not specialization_id:
        return JsonResponse({'error': 'Specialization ID required'}, status=400)

    try:
        consultants = ConsultantModel.objects.filter(
            specialization_id=specialization_id,
            is_available_for_consultation=True
        ).select_related('staff').values(
            'id',
            'staff__first_name',
            'staff__last_name',
            'staff__title',
            'staff__staff_id',
            'default_consultation_duration',
            'max_daily_patients'
        )

        consultant_list = []
        for consultant in consultants:
            full_name = f"{consultant['staff__first_name']} {consultant['staff__last_name']}"
            if consultant['staff__title']:
                full_name = f"{consultant['staff__title']} {full_name}"

            consultant_list.append({
                'id': consultant['id'],
                'full_name': full_name,
                'staff_id': consultant['staff__staff_id'],
                'duration': consultant['default_consultation_duration'],
                'max_patients': consultant['max_daily_patients']
            })

        return JsonResponse({
            'success': True,
            'consultants': consultant_list
        })

    except Exception as e:
        return JsonResponse({
            'error': f'Error retrieving consultants: {str(e)}'
        }, status=500)


class ConsultationPaymentListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    # 1. Update the model to your transaction model
    model = PatientTransactionModel
    # 2. Update the permission to match the new model
    permission_required = 'consultation.add_patientvitalsmodel'
    template_name = 'consultation/payment/list.html'
    context_object_name = "payment_list"
    paginate_by = 50

    def get_queryset(self):
        today = date.today()
        # Query the transaction model and add an essential filter for transaction type
        return PatientTransactionModel.objects.select_related(
            'patient', 'fee_structure__specialization'
        ).filter(
            created_at__date=today,
            transaction_type='consultation_payment' # <-- This is crucial
        ).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = date.today()

        context.update({
            'today_stats': self.get_today_stats(),
            # This query must also be updated
            'pending_payments': PatientTransactionModel.objects.filter(
                created_at__date=today,
                status='pending',
                transaction_type='consultation_payment'
            ).count(),
        })
        return context

    def get_today_stats(self):
        """Get today's payment statistics from the transaction model."""
        try:
            today = date.today()
            # Create a base queryset for today's consultation payments for efficiency
            payments_today = PatientTransactionModel.objects.filter(
                created_at__date=today,
                transaction_type='consultation_payment'
            )

            # 3. Update field names and status values for calculations
            return {
                'total_payments': payments_today.count(),
                'total_amount': payments_today.filter(status='completed').aggregate(
                    total=Sum('amount')
                )['total'] or 0,
                'pending_count': payments_today.filter(status='pending').count(),
                'completed_count': payments_today.filter(status='completed').count(),
            }
        except Exception:
            return {'total_payments': 0, 'total_amount': 0, 'pending_count': 0, 'completed_count': 0}


class ConsultationPaymentDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = PatientTransactionModel
    permission_required = 'consultation.add_patientvitalsmodel'
    template_name = 'consultation/payment/detail.html'
    context_object_name = "payment"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        payment = self.object

        # Check if patient is in queue
        try:
            queue_entry = PatientQueueModel.objects.filter(
                payment=payment
            ).first()
            context['queue_entry'] = queue_entry
        except Exception:
            context['queue_entry'] = None

        return context


# Add these views to your existing views.py file

@require_POST
@login_required
@permission_required('consultation.add_patientvitalsmodel', raise_exception=True)
def update_patient_vitals_ajax(request, queue_pk):
    """
    AJAX view to update existing patient vitals
    """
    try:
        queue_entry = get_object_or_404(PatientQueueModel, pk=queue_pk)

        # Check if patient has vitals and is in appropriate status
        if not hasattr(queue_entry, 'vitals'):
            return JsonResponse({'success': False, 'error': 'No existing vitals found for this patient'}, status=400)

        if queue_entry.status not in ['waiting_vitals', 'vitals_done', 'consultation_paused']:
            return JsonResponse({'success': False, 'error': 'Cannot update vitals at this stage'}, status=400)

        # Update the existing vitals record
        vitals = queue_entry.vitals
        form = PatientVitalsForm(request.POST, instance=vitals)

        if form.is_valid():
            vitals = form.save(commit=False)
            vitals.recorded_by = request.user
            vitals.save()

            # Update queue status if needed
            if queue_entry.status == 'waiting_vitals':
                queue_entry.complete_vitals()
            messages.success(request, 'Vitals Update Succesfully')
            return JsonResponse({
                'success': True,
                'message': 'Patient vitals successfully updated.'
            }, status=200)

        else:
            first_field = next(iter(form.errors))
            first_error_message = form.errors[first_field][0]
            return JsonResponse({
                'success': False,
                'error': f"{first_field}: {first_error_message}"
            }, status=400)

    except PatientQueueModel.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Queue entry not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f"An unexpected error occurred: {str(e)}"}, status=500)


@require_POST
@login_required
@permission_required('consultation.add_patientvitalsmodel', raise_exception=True)
def change_patient_doctor_ajax(request, queue_pk):
    """
    AJAX view to change the assigned doctor for a patient
    """
    try:
        queue_entry = get_object_or_404(PatientQueueModel, pk=queue_pk)

        # Check if patient is in appropriate status for doctor change
        if queue_entry.status not in ['vitals_done', 'consultation_paused']:
            return JsonResponse({
                'success': False,
                'error': 'Cannot change doctor at this stage. Patient must be ready for consultation or have paused consultation.'
            }, status=400)

        new_consultant_id = request.POST.get('consultant_id')
        if not new_consultant_id:
            return JsonResponse({'success': False, 'error': 'Missing consultant_id.'}, status=400)

        new_consultant = get_object_or_404(ConsultantModel, pk=new_consultant_id)

        # Verify the new consultant is from the same specialization as paid for
        patient_specialization = queue_entry.payment.fee_structure.specialization
        if new_consultant.specialization != patient_specialization:
            return JsonResponse({
                'success': False,
                'error': f'Doctor must be from {patient_specialization.name} specialization as per payment.'
            }, status=400)

        # Check consultant availability
        if not new_consultant.is_available_for_consultation:
            return JsonResponse({'success': False, 'error': 'Selected consultant is not available.'}, status=400)

        with transaction.atomic():
            old_consultant = queue_entry.consultant
            queue_entry.consultant = new_consultant
            queue_entry.save()

            # Update schedule counts if needed
            today = timezone.localdate()

            # Decrease old consultant's count
            if old_consultant:
                old_schedule = DoctorScheduleModel.objects.filter(
                    consultant=old_consultant, date=today
                ).first()
                if old_schedule and old_schedule.current_bookings > 0:
                    old_schedule.current_bookings -= 1
                    old_schedule.save()

            # Increase new consultant's count
            new_schedule = DoctorScheduleModel.objects.filter(
                consultant=new_consultant, date=today
            ).first()
            if new_schedule and new_schedule.current_bookings < new_schedule.max_patients:
                new_schedule.current_bookings += 1
                new_schedule.save()

        return JsonResponse({
            'success': True,
            'message': f'Doctor changed successfully from {old_consultant or "None"} to Dr. {new_consultant.staff}',
            'new_consultant': {
                'id': new_consultant.id,
                'name': str(new_consultant.staff),
                'specialization': new_consultant.specialization.name
            }
        }, status=200)

    except ConsultantModel.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Selected consultant not found.'}, status=404)
    except PatientQueueModel.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Queue entry not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Unexpected error: {str(e)}'}, status=500)


@login_required
def get_patient_queue_data_ajax(request):
    """
    AJAX endpoint to get current queue data for quick actions
    """
    try:
        today = date.today()
        queue_entries = PatientQueueModel.objects.select_related(
            'patient', 'consultant__staff', 'consultant__specialization', 'payment__fee_structure__specialization'
        ).filter(
            joined_queue_at__date=today
        ).exclude(
            status__in=['consultation_completed', 'cancelled']
        ).order_by('priority_level', 'joined_queue_at')

        queue_data = []
        for queue in queue_entries:
            queue_data.append({
                'id': queue.id,
                'patient_name': str(queue.patient),
                'patient_id': queue.patient.card_number,
                'status': queue.status,
                'status_display': queue.get_status_display(),
                'specialization_id': queue.payment.fee_structure.specialization.id,
                'specialization_name': queue.payment.fee_structure.specialization.name,
                'consultant': {
                    'id': queue.consultant.id if queue.consultant else None,
                    'name': str(queue.consultant.staff) if queue.consultant else None,
                } if queue.consultant else None,
                'priority_level': queue.priority_level,
                'has_vitals': hasattr(queue, 'vitals'),
                'can_update_vitals': queue.status in ['waiting_vitals', 'vitals_done', 'consultation_paused'],
                'can_change_doctor': queue.status in ['vitals_done', 'consultation_paused']
            })

        return JsonResponse({
            'success': True,
            'queue_data': queue_data
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@permission_required('consultation.view_consultantmodel')
def get_specialization_consultants_ajax(request):
    """
    AJAX endpoint to get available consultants for a specific specialization
    Enhanced version that includes current queue count and availability
    """
    specialization_id = request.GET.get('specialization_id')

    if not specialization_id:
        return JsonResponse({'error': 'Missing specialization_id'}, status=400)

    try:
        today = date.today()
        consultants = ConsultantModel.objects.filter(
            specialization_id=specialization_id,
            is_available_for_consultation=True
        ).select_related('staff', 'specialization')

        consultant_data = []
        for consultant in consultants:
            # Get current queue count for today
            current_queue = PatientQueueModel.objects.filter(
                consultant=consultant,
                joined_queue_at__date=today,
                status__in=['waiting_vitals', 'vitals_done', 'with_doctor', 'consultation_paused']
            ).count()

            # Get schedule info
            schedule = DoctorScheduleModel.objects.filter(
                consultant=consultant,
                date=today
            ).first()

            max_patients = schedule.max_patients if schedule else 10
            is_available = current_queue < max_patients

            consultant_data.append({
                'id': consultant.id,
                'name': str(consultant.staff),
                'specialization': consultant.specialization.name,
                'current_queue': current_queue,
                'max_patients': max_patients,
                'is_available': is_available,
                'room': consultant.assigned_room.name if consultant.assigned_room else None
            })

        return JsonResponse({
            'success': True,
            'consultants': consultant_data
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# -------------------------
# 7. PATIENT QUEUE MANAGEMENT
# -------------------------
class PatientQueueCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, ConsultationContextMixin,
    SuccessMessageMixin, CreateView
):
    model = PatientQueueModel
    permission_required = 'consultation.add_patientvitalsmodel'
    form_class = PatientQueueForm
    template_name = 'consultation/queue/add_patient.html'
    success_message = 'Patient Successfully Added to Queue'

    def get_success_url(self):
        return reverse('patient_queue_index')

    def form_valid(self, form):
        try:
            # Check if payment is fully paid
            payment = form.instance.payment
            if payment.status != 'paid':
                messages.error(self.request, 'Payment must be completed before joining queue')
                return super().form_invalid(form)

            return super().form_valid(form)
        except Exception as e:
            messages.error(self.request, f"Error adding patient to queue: {str(e)}")
            return super().form_invalid(form)

    def form_invalid(self, form):
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f"{field}: {error}")
        return super().form_invalid(form)


class PatientQueueListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = PatientQueueModel
    permission_required = 'consultation.add_patientvitalsmodel'
    template_name = 'consultation/queue/index.html'
    context_object_name = "queue_list"

    def get_queryset(self):
        today = date.today()
        return PatientQueueModel.objects.select_related(
            'patient', 'consultant__staff', 'consultant__specialization'
        ).filter(
            joined_queue_at__date=today
        ).exclude(
            status='consultation_completed'
        ).order_by('priority_level', 'joined_queue_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'queue_stats': self.get_queue_stats(),
            'consultants_status': self.get_consultants_status(),
        })
        return context

    def get_queue_stats(self):
        """Get queue statistics"""
        try:
            today = date.today()
            queue_today = PatientQueueModel.objects.filter(joined_queue_at__date=today)

            return {
                'waiting_vitals': queue_today.filter(status='waiting_vitals').count(),
                'vitals_done': queue_today.filter(status='vitals_done').count(),
                'with_doctor': queue_today.filter(status='with_doctor').count(),
                'completed': queue_today.filter(status='consultation_completed').count(),
                'total': queue_today.count(),
            }
        except Exception:
            return {'waiting_vitals': 0, 'vitals_done': 0, 'with_doctor': 0, 'completed': 0, 'total': 0}

    def get_consultants_status(self):
        """Get consultant availability status"""
        try:
            return ConsultantModel.objects.filter(
                is_available_for_consultation=True
            ).annotate(
                queue_count=Count('patientqueuemodel', filter=Q(
                    patientqueuemodel__joined_queue_at__date=date.today(),
                    patientqueuemodel__status__in=['waiting_vitals', 'vitals_done', 'with_doctor']
                ))
            ).select_related('staff', 'specialization')
        except Exception:
            return ConsultantModel.objects.none()


# -------------------------
# 8. VITALS MANAGEMENT (Nurses)
# -------------------------
class PatientVitalsCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, CreateView
):
    model = PatientVitalsModel
    permission_required = 'consultation.add_patientvitalsmodel'
    form_class = PatientVitalsForm
    template_name = 'consultation/vitals/create.html'
    success_message = 'Patient Vitals Successfully Recorded'

    def get_success_url(self):
        return reverse('vitals_queue_list')

    def dispatch(self, request, *args, **kwargs):
        # Get queue entry from URL
        try:
            self.queue_entry = get_object_or_404(PatientQueueModel, pk=kwargs.get('queue_pk'))
            if self.queue_entry.status not in ['waiting_vitals']:
                messages.error(request, 'Patient is not ready for vitals')
                return redirect('vitals_queue_list')
        except Exception:
            messages.error(request, 'Invalid queue entry')
            return redirect('vitals_queue_list')

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['queue_entry'] = self.queue_entry
        context['patient'] = self.queue_entry.patient
        return context

    def form_valid(self, form):
        try:
            form.instance.queue_entry = self.queue_entry
            form.instance.recorded_by = self.request.user

            # Start vitals process
            self.queue_entry.start_vitals(self.request.user)

            return super().form_valid(form)
        except Exception as e:
            messages.error(self.request, f"Error recording vitals: {str(e)}")
            return super().form_invalid(form)

    def form_invalid(self, form):
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f"{field}: {error}")
        return super().form_invalid(form)


@require_POST
@login_required
@permission_required('consultation.add_patientvitalsmodel', raise_exception=True)
def create_vitals_view(request, queue_pk):
    """
    Functional view to create or update a PatientVitals record via a POST request.
    It returns a detailed JSON response for success or failure, including form errors.
    """
    try:
        # 1. Retrieve the queue entry
        queue_entry = get_object_or_404(PatientQueueModel, pk=queue_pk)

        # 2. Check if the patient is ready for vitals
        if queue_entry.status not in ['waiting_vitals']:
            return JsonResponse(
                {'success': False, 'error': 'Patient is not ready for vitals.'},
                status=400
            )

        # 3. Check for an existing vitals record to determine if this is a create or update operation
        vitals_instance = None
        try:
            vitals_instance = PatientVitalsModel.objects.get(queue_entry=queue_entry)
        except PatientVitalsModel.DoesNotExist:
            pass  # No existing vitals, so we will create a new one

        # 4. Instantiate the form with the POST data and the existing instance (if found)
        form = PatientVitalsForm(request.POST, instance=vitals_instance)


        if form.is_valid():
            # 5. Save the form. If an instance was provided, it will update; otherwise, it will create.
            vitals = form.save(commit=False)
            vitals.queue_entry = queue_entry
            vitals.recorded_by = request.user
            vitals.save()

            # 6. Update the queue status to indicate vitals have been taken

            queue_entry.start_vitals(request.user)
            queue_entry.complete_vitals()

            message = "Patient vitals successfully recorded."
            if vitals_instance:
                message = "Patient vitals successfully updated."

            return JsonResponse(
                {'success': True, 'message': message},
                status=200
            )
        else:
            first_field = next(iter(form.errors))
            # Get the first error message for that field
            first_error_message = form.errors[first_field][0]
            return JsonResponse(
                {'success': False, 'error': f"{first_field}: {first_error_message}"},
                status=400
            )

    except PatientQueueModel.DoesNotExist:
        return JsonResponse(
            {'success': False, 'error': 'Invalid queue entry.'},
            status=404
        )
    except Exception as e:
        return JsonResponse(
            {'success': False, 'error': f"An unexpected error occurred: {str(e)}"},
            status=500
        )


@require_POST
@login_required
@permission_required('consultation.add_patientvitalsmodel', raise_exception=True)
def assign_consultant_ajax(request, queue_pk):
    """
    Assign a ConsultantModel instance to a PatientQueueModel (AJAX).
    POST params: consultant_id
    Returns JSON:
      { success: True, message: "...", assigned: {...} }
      or { success: False, error: "..." }
    """
    try:
        queue_entry = get_object_or_404(PatientQueueModel, pk=queue_pk)

        # Don't allow assignment for completed/cancelled queues
        if queue_entry.status in ['consultation_completed', 'cancelled']:
            return JsonResponse({'success': False, 'error': 'Cannot assign consultant to a completed/cancelled queue.'}, status=400)

        consultant_id = request.POST.get('consultant_id') or request.POST.get('doctor_id')
        if not consultant_id:
            return JsonResponse({'success': False, 'error': 'Missing consultant_id.'}, status=400)

        consultant = get_object_or_404(ConsultantModel, pk=consultant_id)

        # Basic availability checks
        if not consultant.is_available_for_consultation:
            return JsonResponse({'success': False, 'error': 'Consultant is not available for consultation.'}, status=400)

        # Optional: check today's schedule (if you want to block fully booked consultants)
        today = timezone.localdate()
        schedule = DoctorScheduleModel.objects.filter(consultant=consultant, date=today).first()
        if schedule and schedule.is_fully_booked:
            return JsonResponse({'success': False, 'error': 'Consultant is fully booked for today.'}, status=400)

        with transaction.atomic():
            queue_entry.consultant = consultant

            # If patient was still 'waiting_vitals', we don't forcefully change it.
            # If queue is 'waiting_vitals' but you want to mark as 'vitals_done' once consultant assigned,
            # uncomment the following block:
            # if queue_entry.status == 'waiting_vitals':
            #     queue_entry.status = 'vitals_done'

            # if you want to mark 'assigned' state you could set to 'vitals_done' or similar
            # queue_entry.status = 'vitals_done'

            queue_entry.save()

            # Optionally increment today's schedule bookings (if schedule exists)
            if schedule:
                # increment only if booking won't exceed max
                if schedule.current_bookings < schedule.max_patients:
                    schedule.current_bookings += 1
                    schedule.save()

        # Compute current queue count for this consultant (active queue entries)
        active_statuses = ['waiting_vitals', 'vitals_done', 'with_doctor', 'consultation_paused']
        current_queue = PatientQueueModel.objects.filter(consultant=consultant, status__in=active_statuses).count()

        resp = {
            'success': True,
            'message': 'Consultant assigned successfully.',
            'assigned': {
                'consultant_id': consultant.pk,
                'consultant_name': str(consultant),  # your __str__ returns "Dr. <staff> (<specialization>)"
                'specialization': consultant.specialization.name if consultant.specialization else None,
                'current_queue': current_queue,
            }
        }
        return JsonResponse(resp, status=200)

    except ConsultantModel.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Consultant not found.'}, status=404)
    except PatientQueueModel.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Queue entry not found.'}, status=404)
    except Exception as exc:
        # You may want to log exc here
        return JsonResponse({'success': False, 'error': f'Unexpected error: {str(exc)}'}, status=500)


class VitalsQueueListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """Queue for nurses to take vitals"""
    model = PatientQueueModel
    permission_required = 'consultation.add_patientvitalsmodel'
    template_name = 'consultation/vitals/queue.html'
    context_object_name = "queue_list"

    def get_queryset(self):
        today = date.today()
        return PatientQueueModel.objects.select_related(
            'patient', 'consultant__staff'
        ).filter(
            joined_queue_at__date=today,
            status='waiting_vitals'
        ).order_by('priority_level', 'joined_queue_at')


@login_required
@permission_required('consultation.add_patientvitalsmodel')
def complete_vitals_view(request, queue_pk):
    """Mark vitals as completed and move patient to doctor queue"""
    try:
        queue_entry = get_object_or_404(PatientQueueModel, pk=queue_pk)

        if queue_entry.status != 'waiting_vitals':
            messages.error(request, 'Patient vitals not in progress')
        else:
            queue_entry.complete_vitals()
            messages.success(request, f'Vitals completed for {queue_entry.patient}')

    except Exception as e:
        messages.error(request, f'Error completing vitals: {str(e)}')

    return redirect('vitals_queue_list')


# -------------------------
# 9. DOCTOR QUEUE & CONSULTATION ACTIVITIES
# -------------------------
class DoctorQueueListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """Doctor's queue - patients ready for consultation"""
    model = PatientQueueModel
    permission_required = 'consultation.add_consultationsessionmodel'
    template_name = 'consultation/queue/doctor_index.html'
    context_object_name = "queue_list"

    def get_queryset(self):
        today = date.today()
        # Get consultant profile for current user if they are a doctor
        try:
            consultant = ConsultantModel.objects.filter(staff__staff_profile__user=self.request.user, is_available_for_consultation=True).first()
            return PatientQueueModel.objects.select_related(
                'patient', 'consultant__staff', 'vitals'
            ).filter(
                joined_queue_at__date=today,
                consultant=consultant,
                status__in=['vitals_done', 'consultation_paused']
            ).order_by('priority_level', 'joined_queue_at')
        except ConsultantModel.DoesNotExist:
            # If user is not a consultant, show all patients (for admin/nurses)
            return PatientQueueModel.objects.select_related(
                'patient', 'consultant__staff', 'vitals'
            ).filter(
                joined_queue_at__date=today,
                status__in=['vitals_done', 'consultation_paused', 'with_doctor']
            ).order_by('priority_level', 'joined_queue_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            consultant = ConsultantModel.objects.filter(staff__staff_profile__user=self.request.user,
                                                        is_available_for_consultation=True).first()

            context['is_consultant'] = True
            context['consultant'] = consultant
        except ConsultantModel.DoesNotExist:
            context['is_consultant'] = False

        context['queue_stats'] = self.get_doctor_queue_stats()
        return context

    def get_doctor_queue_stats(self):
        """Get doctor-specific queue statistics"""
        try:
            today = date.today()
            consultant = ConsultantModel.objects.filter(staff__staff_profile__user=self.request.user,
                                                        is_available_for_consultation=True).first()

            queue_today = PatientQueueModel.objects.filter(
                joined_queue_at__date=today,
                consultant=consultant
            )

            return {
                'waiting_for_me': queue_today.filter(status='vitals_done').count(),
                'currently_with_me': queue_today.filter(status='with_doctor').count(),
                'paused': queue_today.filter(status='consultation_paused').count(),
                'completed_today': queue_today.filter(status='consultation_completed').count(),
                'total_today': queue_today.count(),
            }
        except ConsultantModel.DoesNotExist:
            # For non-consultants (admin/nurses)
            today = date.today()
            queue_today = PatientQueueModel.objects.filter(joined_queue_at__date=today)
            return {
                'waiting_for_doctor': queue_today.filter(status='vitals_done').count(),
                'with_doctors': queue_today.filter(status='with_doctor').count(),
                'paused': queue_today.filter(status='consultation_paused').count(),
                'completed_today': queue_today.filter(status='consultation_completed').count(),
                'total_today': queue_today.count(),
            }


@login_required
@permission_required('consultation.add_consultationsessionmodel')
def start_consultation_view(request, queue_pk):
    """Start consultation with patient"""
    try:
        queue_entry = get_object_or_404(PatientQueueModel, pk=queue_pk)

        # Check if user is the assigned consultant or has admin rights
        try:
            consultant = ConsultantModel.objects.get(staff__user=request.user)
            if queue_entry.consultant != consultant:
                messages.error(request, 'You are not assigned to this patient')
                return redirect('doctor_queue_list')
        except ConsultantModel.DoesNotExist:
            # Allow admin/superusers
            if not request.user.is_superuser:
                messages.error(request, 'Access denied')
                return redirect('doctor_queue_list')

        if queue_entry.status not in ['vitals_done', 'consultation_paused']:
            messages.error(request, 'Patient is not ready for consultation')
        else:
            queue_entry.start_consultation()
            messages.success(request, f'Consultation started with {queue_entry.patient}')
            return redirect('consultation_session_create', queue_pk=queue_pk)

    except Exception as e:
        messages.error(request, f'Error starting consultation: {str(e)}')

    return redirect('doctor_queue_list')


@login_required
@permission_required('consultation.add_consultationsessionmodel')
def pause_consultation_view(request, queue_pk):
    """Pause consultation (patient stepped out)"""
    try:
        queue_entry = get_object_or_404(PatientQueueModel, pk=queue_pk)

        if queue_entry.status != 'with_doctor':
            messages.error(request, 'Consultation is not in progress')
        else:
            queue_entry.pause_consultation()
            messages.success(request, f'Consultation paused for {queue_entry.patient}')

    except Exception as e:
        messages.error(request, f'Error pausing consultation: {str(e)}')

    return redirect('doctor_queue_list')


@login_required
@permission_required('consultation.add_consultationsessionmodel')
def resume_consultation_view(request, queue_pk):
    """Resume paused consultation"""
    try:
        queue_entry = get_object_or_404(PatientQueueModel, pk=queue_pk)

        if queue_entry.status != 'consultation_paused':
            messages.error(request, 'Consultation is not paused')
        else:
            queue_entry.resume_consultation()
            messages.success(request, f'Consultation resumed with {queue_entry.patient}')

    except Exception as e:
        messages.error(request, f'Error resuming consultation: {str(e)}')

    return redirect('doctor_queue_list')


# -------------------------
# 10. CONSULTATION SESSIONS (The actual consultation)
# -------------------------
class ConsultationSessionCreateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    model = ConsultationSessionModel
    permission_required = 'consultation.add_consultationsessionmodel'
    form_class = ConsultationSessionForm
    template_name = 'consultation/session/create.html'
    success_message = 'Consultation Session Successfully Created'

    def dispatch(self, request, *args, **kwargs):
        try:
            self.queue_entry = get_object_or_404(PatientQueueModel, pk=kwargs.get('queue_pk'))

            # Check if session already exists
            if hasattr(self.queue_entry, 'consultation'):
                return redirect('consultation_session_update', pk=self.queue_entry.consultation.pk)

            # Check if consultation is in progress
            if self.queue_entry.status != 'with_doctor':
                messages.error(request, 'Consultation is not in progress')
                return redirect('doctor_queue_list')

            # Check consultant permissions
            try:
                consultant = ConsultantModel.objects.get(staff__user=request.user)
                if self.queue_entry.consultant != consultant and not request.user.is_superuser:
                    messages.error(request, 'Access denied')
                    return redirect('doctor_queue_list')
            except ConsultantModel.DoesNotExist:
                if not request.user.is_superuser:
                    messages.error(request, 'Access denied')
                    return redirect('doctor_queue_list')

        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
            return redirect('doctor_queue_list')

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'queue_entry': self.queue_entry,
            'patient': self.queue_entry.patient,
            'vitals': getattr(self.queue_entry, 'vitals', None),
            'consultant': self.queue_entry.consultant,
        })
        return context

    def form_valid(self, form):
        try:
            form.instance.queue_entry = self.queue_entry
            return super().form_valid(form)
        except Exception as e:
            messages.error(self.request, f"Error creating consultation session: {str(e)}")
            return super().form_invalid(form)

    def get_success_url(self):
        return reverse('consultation_session_update', kwargs={'pk': self.object.pk})


class ConsultationSessionUpdateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    model = ConsultationSessionModel
    permission_required = 'consultation.add_consultationsessionmodel'
    form_class = ConsultationSessionForm
    template_name = 'consultation/session/update.html'
    success_message = 'Consultation Session Successfully Updated'

    def dispatch(self, request, *args, **kwargs):
        session = self.get_object()

        # Check consultant permissions
        try:
            consultant = ConsultantModel.objects.get(staff__user=request.user)
            if session.queue_entry.consultant != consultant and not request.user.is_superuser:
                messages.error(request, 'Access denied')
                return redirect('doctor_queue_list')
        except ConsultantModel.DoesNotExist:
            if not request.user.is_superuser:
                messages.error(request, 'Access denied')
                return redirect('doctor_queue_list')

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session = self.object
        context.update({
            'queue_entry': session.queue_entry,
            'patient': session.queue_entry.patient,
            'vitals': getattr(session.queue_entry, 'vitals', None),
            'consultant': session.queue_entry.consultant,
        })
        return context

    def get_success_url(self):
        return reverse('consultation_session_update', kwargs={'pk': self.object.pk})


@login_required
@permission_required('consultation.add_consultationsessionmodel')
def complete_consultation_session_view(request, pk):
    """Complete consultation session"""
    try:
        session = get_object_or_404(ConsultationSessionModel, pk=pk)

        # Check permissions
        try:
            consultant = ConsultantModel.objects.get(staff__user=request.user)
            if session.queue_entry.consultant != consultant and not request.user.is_superuser:
                messages.error(request, 'Access denied')
                return redirect('doctor_queue_list')
        except ConsultantModel.DoesNotExist:
            if not request.user.is_superuser:
                messages.error(request, 'Access denied')
                return redirect('doctor_queue_list')

        # Validate required fields before completing
        if not session.chief_complaint or not session.assessment:
            messages.error(request, 'Please fill in Chief Complaint and Assessment before completing')
            return redirect('consultation_session_update', pk=pk)

        session.complete_consultation()
        messages.success(request, f'Consultation completed for {session.queue_entry.patient}')
        return redirect('doctor_queue_list')

    except Exception as e:
        messages.error(request, f'Error completing consultation: {str(e)}')
        return redirect('consultation_session_update', pk=pk)


# -------------------------
# 11. CONSULTATION RECORDS & HISTORY
# -------------------------
class ConsultationRecordsListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ConsultationSessionModel
    permission_required = 'consultation.view_consultationsessionmodel'
    template_name = 'consultation/records/list.html'
    context_object_name = "consultation_list"
    paginate_by = 50

    def get_queryset(self):
        queryset = ConsultationSessionModel.objects.select_related(
            'queue_entry__patient',
            'queue_entry__consultant__staff',
            'queue_entry__consultant__specialization'
        ).filter(status='completed').order_by('-completed_at')

        # Filter by search parameters
        patient_search = self.request.GET.get('patient_search')
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        specialization = self.request.GET.get('specialization')
        consultant = self.request.GET.get('consultant')

        if patient_search:
            queryset = queryset.filter(
                Q(queue_entry__patient__first_name__icontains=patient_search) |
                Q(queue_entry__patient__last_name__icontains=patient_search) |
                Q(queue_entry__patient__card_number__icontains=patient_search)
            )

        if date_from:
            queryset = queryset.filter(completed_at__date__gte=date_from)

        if date_to:
            queryset = queryset.filter(completed_at__date__lte=date_to)

        if specialization:
            queryset = queryset.filter(queue_entry__consultant__specialization_id=specialization)

        if consultant:
            queryset = queryset.filter(queue_entry__consultant_id=consultant)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'specializations': SpecializationModel.objects.all().order_by('name'),
            'consultants': ConsultantModel.objects.select_related('staff', 'specialization').order_by(
                'staff__first_name'),
            'search_params': {
                'patient_search': self.request.GET.get('patient_search', ''),
                'date_from': self.request.GET.get('date_from', ''),
                'date_to': self.request.GET.get('date_to', ''),
                'specialization': self.request.GET.get('specialization', ''),
                'consultant': self.request.GET.get('consultant', ''),
            }
        })
        return context


class ConsultationRecordDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = ConsultationSessionModel
    permission_required = 'consultation.view_consultationsessionmodel'
    template_name = 'consultation/records/detail.html'
    context_object_name = "consultation"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        consultation = self.object
        patient = consultation.queue_entry.patient

        context.update({
            'patient': patient,
            'queue_entry': consultation.queue_entry,
            'vitals': getattr(consultation.queue_entry, 'vitals', None),
            'consultant': consultation.queue_entry.consultant,
            'payment': consultation.queue_entry.payment,
            'previous_consultations': self.get_previous_consultations(patient, consultation),
        })
        return context

    def get_previous_consultations(self, patient, current_consultation):
        """Get patient's previous consultations"""
        return ConsultationSessionModel.objects.filter(
            queue_entry__patient=patient,
            status='completed'
        ).exclude(
            pk=current_consultation.pk
        ).order_by('-completed_at')[:5]


class PatientConsultationHistoryView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ConsultationSessionModel
    permission_required = 'consultation.add_consultationsessionmodel'
    template_name = 'consultation/records/patient_history.html'
    context_object_name = "consultation_list"
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        try:
            self.patient = get_object_or_404(PatientModel, pk=kwargs.get('patient_pk'))
        except Exception:
            messages.error(request, 'Patient not found')
            return redirect('consultation_records_list')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return ConsultationSessionModel.objects.select_related(
            'queue_entry__consultant__staff',
            'queue_entry__consultant__specialization'
        ).filter(
            queue_entry__patient=self.patient,
            status='completed'
        ).order_by('-completed_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'patient': self.patient,
            'total_consultations': self.get_queryset().count(),
            'recent_vitals': self.get_recent_vitals(),
        })
        return context

    def get_recent_vitals(self):
        """Get patient's most recent vitals"""
        try:
            recent_queue = PatientQueueModel.objects.filter(
                patient=self.patient
            ).order_by('-joined_queue_at').first()

            if recent_queue and hasattr(recent_queue, 'vitals'):
                return recent_queue.vitals
        except Exception:
            pass
        return None


# -------------------------
# 12. DOCTOR SCHEDULE MANAGEMENT
# -------------------------
class DoctorScheduleCreateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    model = DoctorScheduleModel
    permission_required = 'consultation.add_consultationsessionmodel'
    form_class = DoctorScheduleForm
    template_name = 'consultation/schedule/create.html'
    success_message = 'Schedule Successfully Created'

    def get_success_url(self):
        return reverse('doctor_schedule_list')

    def form_valid(self, form):
        # Set consultant if user is a consultant
        try:
            consultant = ConsultantModel.objects.get(staff__user=self.request.user)
            form.instance.consultant = consultant
        except ConsultantModel.DoesNotExist:
            if not self.request.user.is_superuser:
                messages.error(self.request, 'Only consultants can create schedules')
                return super().form_invalid(form)

        return super().form_valid(form)

    def form_invalid(self, form):
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f"{field}: {error}")
        return super().form_invalid(form)


class DoctorScheduleListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = DoctorScheduleModel
    permission_required = 'consultation.view_consultationsessionmodel'
    template_name = 'consultation/schedule/list.html'
    context_object_name = "schedule_list"

    def get_queryset(self):
        # Show only consultant's own schedules unless admin
        try:
            consultant = ConsultantModel.objects.get(staff__user=self.request.user)
            return DoctorScheduleModel.objects.filter(
                consultant=consultant
            ).order_by('-date', '-start_time')
        except ConsultantModel.DoesNotExist:
            if self.request.user.is_superuser:
                return DoctorScheduleModel.objects.select_related(
                    'consultant__staff', 'consultant__specialization'
                ).order_by('-date', '-start_time')
            return DoctorScheduleModel.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            consultant = ConsultantModel.objects.get(staff__user=self.request.user)
            context['is_consultant'] = True
            context['consultant'] = consultant
        except ConsultantModel.DoesNotExist:
            context['is_consultant'] = False
        return context


class DoctorScheduleUpdateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    model = DoctorScheduleModel
    permission_required = 'consultation.add_consultationsessionmodel'
    form_class = DoctorScheduleForm
    template_name = 'consultation/schedule/update.html'
    success_message = 'Schedule Successfully Updated'

    def get_success_url(self):
        return reverse('doctor_schedule_list')

    def dispatch(self, request, *args, **kwargs):
        schedule = self.get_object()

        # Check if user owns this schedule
        try:
            consultant = ConsultantModel.objects.get(staff__user=request.user)
            if schedule.consultant != consultant and not request.user.is_superuser:
                messages.error(request, 'Access denied')
                return redirect('doctor_schedule_list')
        except ConsultantModel.DoesNotExist:
            if not request.user.is_superuser:
                messages.error(request, 'Access denied')
                return redirect('doctor_schedule_list')

        return super().dispatch(request, *args, **kwargs)


# -------------------------
# 13. REPORTS & ANALYTICS
# -------------------------
class ConsultationDashboardView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = 'consultation/dashboard/index.html'
    permission_required = 'consultation.view_consultationsessionmodel'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = date.today()

        # Get consultant-specific data if user is a consultant
        try:
            consultant = ConsultantModel.objects.get(staff__user=self.request.user)
            context.update({
                'is_consultant': True,
                'consultant': consultant,
                'today_stats': self.get_consultant_today_stats(consultant),
                'this_week_stats': self.get_consultant_week_stats(consultant),
                'recent_consultations': self.get_recent_consultations(consultant),
            })
        except ConsultantModel.DoesNotExist:
            # Admin/general dashboard
            context.update({
                'is_consultant': False,
                'overall_stats': self.get_overall_stats(),
                'consultant_performance': self.get_consultant_performance(),
                'revenue_stats': self.get_revenue_stats(),
            })

        context.update({
            'queue_overview': self.get_queue_overview(),
            'pending_payments': self.get_pending_payments_count(),
        })

        return context

    def get_consultant_today_stats(self, consultant):
        """Get today's statistics for a specific consultant"""
        today = date.today()
        queue_today = PatientQueueModel.objects.filter(
            consultant=consultant,
            joined_queue_at__date=today
        )

        return {
            'total_patients': queue_today.count(),
            'completed': queue_today.filter(status='consultation_completed').count(),
            'in_progress': queue_today.filter(status='with_doctor').count(),
            'waiting': queue_today.filter(status='vitals_done').count(),
            'revenue': PatientTransactionModel.objects.filter(
                created_at__date=today,
                transaction_type='consultation_payment',
                fee_structure__specialization=consultant.specialization,
                status='paid'
            ).aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
        }

    def get_consultant_week_stats(self, consultant):
        """Get this week's statistics for a specific consultant"""
        week_start = date.today() - timedelta(days=7)
        queue_week = PatientQueueModel.objects.filter(
            consultant=consultant,
            joined_queue_at__date__gte=week_start
        )

        return {
            'total_patients': queue_week.count(),
            'completed': queue_week.filter(status='consultation_completed').count(),
            'average_per_day': queue_week.count() / 7,
        }

    def get_recent_consultations(self, consultant):
        """Get recent consultations for consultant"""
        return ConsultationSessionModel.objects.filter(
            queue_entry__consultant=consultant,
            status='completed'
        ).select_related('queue_entry__patient').order_by('-completed_at')[:5]

    def get_overall_stats(self):
        """Get overall hospital consultation statistics"""
        today = date.today()
        week_start = today - timedelta(days=7)

        return {
            'today': {
                'total_patients': PatientQueueModel.objects.filter(joined_queue_at__date=today).count(),
                'completed': PatientQueueModel.objects.filter(
                    joined_queue_at__date=today, status='consultation_completed'
                ).count(),
                'revenue': PatientTransactionModel.objects.filter(
                    created_at__date=today,
                    status='completed',
                    transaction_type='consultation_payment'
                ).aggregate(total=Sum('amount'))['total'] or 0
            },
            'this_week': {
                'total_patients': PatientQueueModel.objects.filter(joined_queue_at__date__gte=week_start).count(),
                'completed': PatientQueueModel.objects.filter(
                    joined_queue_at__date__gte=week_start, status='consultation_completed'
                ).count(),
            }
        }

    def get_consultant_performance(self):
        """Get consultant performance metrics"""
        today = date.today()
        return ConsultantModel.objects.annotate(
            today_patients=Count('patientqueuemodel', filter=Q(
                patientqueuemodel__joined_queue_at__date=today
            )),
            today_completed=Count('patientqueuemodel', filter=Q(
                patientqueuemodel__joined_queue_at__date=today,
                patientqueuemodel__status='consultation_completed'
            ))
        ).select_related('staff', 'specialization')[:10]

    def get_revenue_stats(self):
        """Get revenue statistics"""
        today = date.today()
        week_start = today - timedelta(days=7)
        month_start = today - timedelta(days=30)

        return {
            'today': PatientTransactionModel.objects.filter(
                created_at__date=today,
                transaction_type='consultation_payment',
                status='completed'  # Use 'completed' for successful transactions
            ).aggregate(total=Sum('amount'))['total'] or 0,

            'this_week': PatientTransactionModel.objects.filter(
                created_at__date__gte=week_start,
                transaction_type='consultation_payment',
                status='completed'
            ).aggregate(total=Sum('amount'))['total'] or 0,

            'this_month': PatientTransactionModel.objects.filter(
                created_at__date__gte=month_start,
                transaction_type='consultation_payment',
                status='completed'
            ).aggregate(total=Sum('amount'))['total'] or 0,
        }

    def get_queue_overview(self):
        """Get current queue overview"""
        today = date.today()
        queue_today = PatientQueueModel.objects.filter(joined_queue_at__date=today)

        return {
            'waiting_vitals': queue_today.filter(status='waiting_vitals').count(),
            'vitals_done': queue_today.filter(status='vitals_done').count(),
            'with_doctor': queue_today.filter(status='with_doctor').count(),
            'completed': queue_today.filter(status='consultation_completed').count(),
        }

    def get_pending_payments_count(self):
        """Get pending payments count"""
        today = date.today()
        return PatientTransactionModel.objects.filter(
            transaction_type='consultation_payment',
            created_at__date=today,
            status__in=['pending', 'partial']
        ).count()


# -------------------------
# 14. AJAX/API ENDPOINTS
# -------------------------
@login_required
def get_consultant_schedule_ajax(request):
    """AJAX endpoint to get consultant schedules"""
    consultant_id = request.GET.get('consultant_id')
    date_str = request.GET.get('date')

    if not consultant_id or not date_str:
        return JsonResponse({'error': 'Missing parameters'}, status=400)

    try:
        consultant = ConsultantModel.objects.get(pk=consultant_id)
        schedule_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        schedule = DoctorScheduleModel.objects.filter(
            consultant=consultant,
            date=schedule_date
        ).first()

        if schedule:
            return JsonResponse({
                'available': schedule.is_available,
                'available_slots': schedule.available_slots,
                'max_patients': schedule.max_patients,
                'current_bookings': schedule.current_bookings,
                'start_time': schedule.start_time.strftime('%H:%M'),
                'end_time': schedule.end_time.strftime('%H:%M'),
            })
        else:
            return JsonResponse({
                'available': False,
                'message': 'No schedule found for this date'
            })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def get_patient_vitals_ajax(request, queue_pk):
    """AJAX endpoint to get patient vitals"""
    try:
        queue_entry = get_object_or_404(PatientQueueModel, pk=queue_pk)

        if hasattr(queue_entry, 'vitals'):
            vitals = queue_entry.vitals
            return JsonResponse({
                'has_vitals': True,
                'temperature': str(vitals.temperature) if vitals.temperature else None,
                'blood_pressure': vitals.blood_pressure,
                'pulse_rate': vitals.pulse_rate,
                'respiratory_rate': vitals.respiratory_rate,
                'oxygen_saturation': vitals.oxygen_saturation,
                'height': str(vitals.height) if vitals.height else None,
                'weight': str(vitals.weight) if vitals.weight else None,
                'bmi': str(vitals.bmi) if vitals.bmi else None,
                'chief_complaint': vitals.chief_complaint,
                'general_appearance': vitals.general_appearance,
                'extra_note': vitals.extra_note,
                'recorded_at': vitals.recorded_at.strftime('%Y-%m-%d %H:%M'),
            })
        else:
            return JsonResponse({'has_vitals': False})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@permission_required('consultation.view_patientqueuemodel')
def queue_status_ajax(request):
    """AJAX endpoint for live queue status updates"""
    try:
        today = date.today()
        queue_stats = {
            'waiting_vitals': PatientQueueModel.objects.filter(
                joined_queue_at__date=today, status='waiting_vitals'
            ).count(),
            'vitals_done': PatientQueueModel.objects.filter(
                joined_queue_at__date=today, status='vitals_done'
            ).count(),
            'with_doctor': PatientQueueModel.objects.filter(
                joined_queue_at__date=today, status='with_doctor'
            ).count(),
            'completed': PatientQueueModel.objects.filter(
                joined_queue_at__date=today, status='consultation_completed'
            ).count(),
        }

        # Get consultant-specific stats if user is a consultant
        try:
            consultant = ConsultantModel.objects.get(staff__user=request.user)
            consultant_stats = {
                'my_waiting': PatientQueueModel.objects.filter(
                    joined_queue_at__date=today,
                    consultant=consultant,
                    status='vitals_done'
                ).count(),
                'my_current': PatientQueueModel.objects.filter(
                    joined_queue_at__date=today,
                    consultant=consultant,
                    status='with_doctor'
                ).count(),
                'my_completed': PatientQueueModel.objects.filter(
                    joined_queue_at__date=today,
                    consultant=consultant,
                    status='consultation_completed'
                ).count(),
            }
            queue_stats.update(consultant_stats)
        except ConsultantModel.DoesNotExist:
            pass

        return JsonResponse(queue_stats)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def get_specialization_fee_ajax(request):
    """AJAX endpoint to get consultation fee by specialization"""
    specialization_id = request.GET.get('specialization_id')
    patient_category = request.GET.get('patient_category', 'regular')

    if not specialization_id:
        return JsonResponse({'error': 'Missing specialization ID'}, status=400)

    try:
        fee = ConsultationFeeModel.objects.filter(
            specialization_id=specialization_id,
            patient_category=patient_category,
            is_active=True
        ).first()

        if fee:
            return JsonResponse({
                'fee_found': True,
                'amount': str(fee.amount),
                'duration_minutes': fee.duration_minutes,
                'patient_category': fee.get_patient_category_display(),
            })
        else:
            # Try to get base fee from specialization
            specialization = SpecializationModel.objects.get(pk=specialization_id)
            return JsonResponse({
                'fee_found': False,
                'base_amount': str(specialization.base_consultation_fee),
                'message': 'Using base consultation fee'
            })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# -------------------------
# 15. REPORTS VIEWS
# -------------------------
class ConsultationReportsView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = 'consultation/reports/index.html'
    permission_required = 'consultation.view_consultationsessionmodel'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get date filters
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        specialization = self.request.GET.get('specialization')
        consultant = self.request.GET.get('consultant')

        # Default to last 30 days if no dates provided
        if not date_from:
            date_from = (date.today() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not date_to:
            date_to = date.today().strftime('%Y-%m-%d')

        context.update({
            'date_from': date_from,
            'date_to': date_to,
            'specialization_filter': specialization,
            'consultant_filter': consultant,
            'specializations': SpecializationModel.objects.all().order_by('name'),
            'consultants': ConsultantModel.objects.select_related('staff', 'specialization').order_by(
                'staff__first_name'),
            'consultation_summary': self.get_consultation_summary(date_from, date_to, specialization, consultant),
            'revenue_summary': self.get_revenue_summary(date_from, date_to, specialization, consultant),
            'consultant_performance': self.get_consultant_performance_report(date_from, date_to, specialization,
                                                                             consultant),
            'daily_stats': self.get_daily_statistics(date_from, date_to, specialization, consultant),
        })

        return context

    def get_consultation_summary(self, date_from, date_to, specialization=None, consultant=None):
        """Get consultation summary for the period"""
        try:
            queryset = ConsultationSessionModel.objects.filter(
                completed_at__date__range=[date_from, date_to],
                status='completed'
            )

            if specialization:
                queryset = queryset.filter(queue_entry__consultant__specialization_id=specialization)
            if consultant:
                queryset = queryset.filter(queue_entry__consultant_id=consultant)

            total_consultations = queryset.count()

            # Group by specialization
            by_specialization = queryset.values(
                'queue_entry__consultant__specialization__name'
            ).annotate(
                count=Count('id')
            ).order_by('-count')

            return {
                'total_consultations': total_consultations,
                'by_specialization': by_specialization,
                'average_per_day': total_consultations / max(1, (
                            datetime.strptime(date_to, '%Y-%m-%d') - datetime.strptime(date_from, '%Y-%m-%d')).days + 1)
            }
        except Exception:
            return {'total_consultations': 0, 'by_specialization': [], 'average_per_day': 0}

    def get_revenue_summary(self, date_from, date_to, specialization=None, consultant=None):
        """Get revenue summary for the period"""
        try:
            queryset = PatientTransactionModel.objects.filter(
                created_at__date__range=[date_from, date_to],
                status='completed',
                transaction_type='consultation_payment'
            )

            if specialization:
                queryset = queryset.filter(fee_structure__specialization_id=specialization)

            total_revenue = queryset.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
            total_transactions = queryset.count()

            # Revenue by payment method
            by_payment_method = queryset.values('payment_method').annotate(
                amount=Sum('amount_paid'),
                count=Count('id')
            ).order_by('-amount')

            # Revenue by specialization
            by_specialization = queryset.values(
                'fee_structure__specialization__name'
            ).annotate(
                amount=Sum('amount_paid'),
                count=Count('id')
            ).order_by('-amount')

            return {
                'total_revenue': total_revenue,
                'total_transactions': total_transactions,
                'average_per_transaction': total_revenue / max(1, total_transactions),
                'by_payment_method': by_payment_method,
                'by_specialization': by_specialization,
            }
        except Exception:
            return {
                'total_revenue': 0, 'total_transactions': 0, 'average_per_transaction': 0,
                'by_payment_method': [], 'by_specialization': []
            }

    def get_consultant_performance_report(self, date_from, date_to, specialization=None, consultant=None):
        """Get consultant performance metrics"""
        try:
            consultants = ConsultantModel.objects.filter(is_available_for_consultation=True)

            if specialization:
                consultants = consultants.filter(specialization_id=specialization)
            if consultant:
                consultants = consultants.filter(id=consultant)

            performance_data = []

            for cons in consultants.select_related('staff', 'specialization'):
                consultations = ConsultationSessionModel.objects.filter(
                    queue_entry__consultant=cons,
                    completed_at__date__range=[date_from, date_to],
                    status='completed'
                ).count()

                revenue = PatientTransactionModel.objects.filter(
                    fee_structure__specialization=cons.specialization,
                    transaction_type='consultation_payment',
                    created_at__date__range=[date_from, date_to],
                    status='paid'
                ).aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0

                performance_data.append({
                    'consultant': cons,
                    'consultations': consultations,
                    'revenue': revenue,
                })

            # Sort by consultations descending
            performance_data.sort(key=lambda x: x['consultations'], reverse=True)
            return performance_data[:10]  # Top 10

        except Exception:
            return []

    def get_daily_statistics(self, date_from, date_to, specialization=None, consultant=None):
        """Get daily consultation statistics"""
        try:
            start_date = datetime.strptime(date_from, '%Y-%m-%d').date()
            end_date = datetime.strptime(date_to, '%Y-%m-%d').date()

            daily_stats = []
            current_date = start_date

            while current_date <= end_date:
                consultations = ConsultationSessionModel.objects.filter(
                    completed_at__date=current_date,
                    status='completed'
                )

                if specialization:
                    consultations = consultations.filter(queue_entry__consultant__specialization_id=specialization)
                if consultant:
                    consultations = consultations.filter(queue_entry__consultant_id=consultant)

                # Start with the base query on the transaction model.
                revenue_query = PatientTransactionModel.objects.filter(
                    created_at__date=current_date,
                    status='completed',
                    transaction_type='consultation_payment'
                )

                # If a specialization is provided, filter directly using the fee_structure link.
                if specialization:
                    revenue_query = revenue_query.filter(fee_structure__specialization_id=specialization)

                # Execute the aggregation on the final queryset.
                total_revenue = revenue_query.aggregate(total=Sum('amount'))['total'] or 0

                daily_stats.append({
                    'date': current_date,
                    'consultations': consultations.count(),
                    'revenue': total_revenue,
                })

                current_date += timedelta(days=1)

            return daily_stats

        except Exception:
            return []


# -------------------------
# 16. SETTINGS MANAGEMENT
# -------------------------
class ConsultationSettingsView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    model = ConsultationSettingsModel
    permission_required = 'consultation.change_consultationsettingsmodel'
    form_class = ConsultationSettingsForm
    template_name = 'consultation/settings/index.html'
    success_message = 'Settings Successfully Updated'

    def get_object(self):
        """Get or create settings object"""
        obj, created = ConsultationSettingsModel.objects.get_or_create(pk=1)
        return obj

    def get_success_url(self):
        return reverse('consultation_settings')

    def form_invalid(self, form):
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f"{field}: {error}")
        return super().form_invalid(form)


# -------------------------
# 17. BULK OPERATIONS & UTILITIES
# -------------------------
@login_required
@permission_required('consultation.change_patientqueuemodel')
def bulk_complete_vitals_view(request):
    """Bulk complete vitals for multiple patients"""
    if request.method == 'POST':
        queue_ids = request.POST.getlist('queue_ids')

        if not queue_ids:
            messages.error(request, 'No patients selected')
            return redirect('vitals_queue_list')

        try:
            with transaction.atomic():
                updated_count = 0
                for queue_id in queue_ids:
                    try:
                        queue_entry = PatientQueueModel.objects.get(
                            pk=queue_id,
                            status='waiting_vitals'
                        )
                        queue_entry.complete_vitals()
                        updated_count += 1
                    except PatientQueueModel.DoesNotExist:
                        continue

                messages.success(request, f'Vitals completed for {updated_count} patients')

        except Exception as e:
            messages.error(request, f'Error completing bulk vitals: {str(e)}')

    return redirect('vitals_queue_list')


@login_required
def export_consultation_data_view(request):
    """Export consultation data to CSV"""
    try:
        import csv
        from django.http import HttpResponse

        # Get filter parameters
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        specialization = request.GET.get('specialization')

        # Default to last 30 days
        if not date_from:
            date_from = (date.today() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not date_to:
            date_to = date.today().strftime('%Y-%m-%d')

        # Query data
        consultations = ConsultationSessionModel.objects.filter(
            completed_at__date__range=[date_from, date_to],
            status='completed'
        ).select_related(
            'queue_entry__patient',
            'queue_entry__consultant__staff',
            'queue_entry__consultant__specialization'
        )

        if specialization:
            consultations = consultations.filter(
                queue_entry__consultant__specialization_id=specialization
            )

        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="consultations_{date_from}_to_{date_to}.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Date', 'Patient Name', 'Patient ID', 'Consultant', 'Specialization',
            'Chief Complaint', 'Diagnosis', 'Queue Number', 'Consultation Duration'
        ])

        for consultation in consultations:
            duration = ''
            if consultation.queue_entry.consultation_started_at and consultation.completed_at:
                duration_delta = consultation.completed_at - consultation.queue_entry.consultation_started_at
                duration = str(duration_delta).split('.')[0]  # Remove microseconds

            writer.writerow([
                consultation.completed_at.strftime('%Y-%m-%d'),
                consultation.queue_entry.patient.full_name(),
                consultation.queue_entry.patient.patient_id,
                consultation.queue_entry.consultant.staff.full_name(),
                consultation.queue_entry.consultant.specialization.name,
                consultation.chief_complaint[:100] + '...' if len(
                    consultation.chief_complaint) > 100 else consultation.chief_complaint,
                consultation.diagnosis[:100] + '...' if len(consultation.diagnosis) > 100 else consultation.diagnosis,
                consultation.queue_entry.queue_number,
                duration
            ])

        return response

    except Exception as e:
        messages.error(request, f'Error exporting data: {str(e)}')
        return redirect('consultation_reports')


@login_required
def export_payment_data_view(request):
    """Export payment data to CSV"""
    try:
        import csv
        from django.http import HttpResponse

        # Get filter parameters
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')

        # Default to today
        if not date_from:
            date_from = date.today().strftime('%Y-%m-%d')
        if not date_to:
            date_to = date.today().strftime('%Y-%m-%d')

        # Query payments
        payments = PatientTransactionModel.objects.filter(
            created_at__date__range=[date_from, date_to],
            transaction_type='consultation_payment'  # <-- Essential filter added
        ).select_related(
            'patient',
            'fee_structure__specialization',
            'received_by'  # <-- Field name updated
        )

        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="payments_{date_from}_to_{date_to}.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Date', 'Transaction ID', 'Patient Name', 'Patient ID', 'Specialization',
            'Amount Due', 'Amount Paid', 'Balance', 'Payment Method', 'Status',
            'Insurance Coverage', 'Processed By'
        ])

        for payment in payments:
            writer.writerow([
                payment.created_at.strftime('%Y-%m-%d %H:%M'),
                payment.transaction_id,
                payment.patient.full_name(),
                payment.patient.patient_id,
                payment.fee_structure.specialization.name,
                payment.amount_due,
                payment.amount_paid,
                payment.balance,
                payment.get_payment_method_display(),
                payment.get_status_display(),
                payment.insurance_coverage,
                payment.processed_by.get_full_name() if payment.processed_by else ''
            ])

        return response

    except Exception as e:
        messages.error(request, f'Error exporting payment data: {str(e)}')
        return redirect('consultation_payment_list')


# -------------------------
# 18. ERROR HANDLERS & UTILITIES
# -------------------------
@login_required
def cancel_queue_entry_view(request, queue_pk):
    """Cancel a queue entry"""
    if request.method == 'POST':
        try:
            queue_entry = get_object_or_404(PatientQueueModel, pk=queue_pk)

            # Check permissions
            if not request.user.has_perm('consultation.change_patientqueuemodel'):
                messages.error(request, 'Permission denied')
                return redirect('patient_queue_index')

            # Check if consultation can be cancelled
            if queue_entry.status == 'consultation_completed':
                messages.error(request, 'Cannot cancel completed consultation')
                return redirect('patient_queue_index')

            queue_entry.status = 'cancelled'
            queue_entry.save()

            messages.success(request, f'Queue entry cancelled for {queue_entry.patient}')

        except Exception as e:
            messages.error(request, f'Error cancelling queue entry: {str(e)}')

    return redirect('patient_queue_index')


@login_required
def search_patients_ajax(request):
    """AJAX endpoint to search patients for queue"""
    query = request.GET.get('q', '').strip()

    if len(query) < 2:
        return JsonResponse({'patients': []})

    try:
        patients = PatientModel.objects.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(patient_id__icontains=query) |
            Q(phone__icontains=query)
        )[:10]

        patient_data = []
        for patient in patients:
            patient_data.append({
                'id': patient.id,
                'patient_id': patient.patient_id,
                'full_name': patient.full_name(),
                'phone': patient.phone,
                'age': patient.age if hasattr(patient, 'age') else '',
            })

        return JsonResponse({'patients': patient_data})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# consultation/views.py

@login_required
@permission_required('consultation.add_consultationsessionmodel', raise_exception=True)
def doctor_dashboard(request):
    """Doctor's main dashboard view"""

    try:
        # Get the consultant profile for the logged-in user
        consultant = get_object_or_404(ConsultantModel, staff__staff_profile__user=request.user)
    except Exception:
        messages.error(request, "You are not authorized to access the doctor dashboard.")
        fallback_url = reverse('admin_dashboard')
        redirect_url = request.META.get('HTTP_REFERER', fallback_url)
        return redirect(redirect_url)

    # Get today's statistics
    today = date.today()

    # MODIFIED QUERY: Added prefetch_related for the consultation
    my_queue = PatientQueueModel.objects.filter(
        consultant=consultant,
        joined_queue_at__date=today
    ).exclude(status='cancelled').select_related(
        'patient', 'vitals', 'consultant'
    ).prefetch_related(
        'consultation'  # <-- THIS IS THE FIX
    ).order_by('priority_level', 'joined_queue_at')

    today_stats = {
        'total_queue': my_queue.count(),
        'completed': my_queue.filter(status='consultation_completed').count(),
        'waiting': my_queue.filter(status='vitals_done').count(),
        'in_consultation': my_queue.filter(status='with_doctor').count(),
    }

    # Get current consultation (if any)
    current_consultation = ConsultationSessionModel.objects.filter(
        queue_entry__consultant=consultant,
        status='in_progress',
        queue_entry__joined_queue_at__date=today
    ).select_related('queue_entry__patient').first() # Added select_related for efficiency

    # Recent consultations (last 7 days)
    week_ago = today - timedelta(days=7)
    recent_consultations = ConsultationSessionModel.objects.filter(
        queue_entry__consultant=consultant,
        created_at__date=today, status='completed'
    ).select_related('queue_entry__patient').order_by('-created_at')[:10]

    context = {
        'consultant': consultant,
        'my_queue': my_queue,
        'today_stats': today_stats,
        'current_consultation': current_consultation,
        'recent_consultations': recent_consultations,
    }

    return render(request, 'consultation/doctor/index.html', context)


@login_required
@permission_required('consultation.add_consultationsessionmodel', raise_exception=True)
def consultation_page(request, consultation_id):
    """Individual consultation management page"""
    try:
        consultant = get_object_or_404(ConsultantModel, staff__staff_profile__user=request.user)
        consultation = get_object_or_404(
            ConsultationSessionModel,
            id=consultation_id,
            queue_entry__consultant=consultant
        )
    except (ConsultantModel.DoesNotExist, ConsultationSessionModel.DoesNotExist):
        messages.error(request, "Consultation not found or access denied.")
        return redirect('doctor_dashboard')

    if consultation.status == 'completed':
        consultation.status = 'in_progress'
        consultation.completed_at = None  # Clear the completion timestamp
        consultation.save()

        # Also update the related queue entry status
        if consultation.queue_entry:
            consultation.queue_entry.status = 'with_doctor'
            consultation.queue_entry.save()

        messages.info(request,
                      f"Consultation has been reopened for editing.")

    # Get related data
    patient = consultation.queue_entry.patient

    # MODIFIED: Filter directly by the consultation object
    prescriptions = DrugOrderModel.objects.filter(
        consultation=consultation
    ).select_related('drug')

    # MODIFIED: Filter directly by the consultation object
    lab_tests = LabTestOrderModel.objects.filter(
        consultation=consultation
    ).select_related('template')

    # MODIFIED: Filter directly by the consultation object
    scans = ScanOrderModel.objects.filter(
        consultation=consultation
    ).select_related('template')

    # Get patient's recent consultation history (last 6 months)
    six_months_ago = consultation.created_at.date() - timedelta(days=180)
    recent_consultations = ConsultationSessionModel.objects.filter(
        queue_entry__patient=patient,
        created_at__date__gte=six_months_ago,
        status='completed'
    ).exclude(id=consultation_id).order_by('-created_at')[:5]

    # Get categories for dropdowns
    lab_categories = LabTestCategoryModel.objects.filter()
    scan_categories = ScanCategoryModel.objects.filter()
    external_prescriptions = ExternalPrescription.objects.filter(consultation=consultation)
    external_lab_tests = consultation.external_lab_orders.all()
    external_scans = consultation.external_scan_orders.all()

    context = {
        'consultant': consultant,
        'consultation': consultation,
        'prescriptions': prescriptions,
        'lab_tests': lab_tests,
        'scans': scans,
        'recent_consultations': recent_consultations,
        'external_prescriptions': external_prescriptions,
        'lab_categories': lab_categories,
        'scan_categories': scan_categories,
        'external_lab_tests': external_lab_tests,
        'external_scans': external_scans,
    }

    return render(request, 'consultation/doctor/consultation.html', context)


@login_required
@permission_required('consultation.view_consultationsessionmodel', raise_exception=True)
def consultation_history(request):
    """View consultation history with filters"""
    try:
        consultant = get_object_or_404(ConsultantModel, staff__staff_profile__user=request.user)
    except ConsultantModel.DoesNotExist:
        messages.error(request, "Access denied.")
        return redirect('admin_dashboard')

    # Get filter parameters
    date_range = request.GET.get('date_range', 'this_month')
    status = request.GET.get('status', '')
    patient_search = request.GET.get('patient_search', '')

    # Build base query
    consultations = ConsultationSessionModel.objects.filter(
        queue_entry__consultant=consultant
    ).select_related(
        'queue_entry__patient', 'queue_entry'
    ).order_by('-created_at')

    # Apply date filter
    today = date.today()
    if date_range == 'today':
        consultations = consultations.filter(created_at__date=today)
    elif date_range == 'yesterday':
        yesterday = today - timedelta(days=1)
        consultations = consultations.filter(created_at__date=yesterday)
    elif date_range == 'this_week':
        week_start = today - timedelta(days=today.weekday())
        consultations = consultations.filter(created_at__date__gte=week_start)
    elif date_range == 'last_week':
        week_start = today - timedelta(days=today.weekday() + 7)
        week_end = week_start + timedelta(days=6)
        consultations = consultations.filter(
            created_at__date__gte=week_start,
            created_at__date__lte=week_end
        )
    elif date_range == 'this_month':
        month_start = today.replace(day=1)
        consultations = consultations.filter(created_at__date__gte=month_start)
    elif date_range == 'last_month':
        if today.month == 1:
            last_month = today.replace(year=today.year - 1, month=12, day=1)
        else:
            last_month = today.replace(month=today.month - 1, day=1)

        # Get the last day of previous month
        if last_month.month == 12:
            next_month = last_month.replace(year=last_month.year + 1, month=1, day=1)
        else:
            next_month = last_month.replace(month=last_month.month + 1, day=1)

        last_day = next_month - timedelta(days=1)
        consultations = consultations.filter(
            created_at__date__gte=last_month,
            created_at__date__lte=last_day
        )

    # Apply status filter
    if status:
        consultations = consultations.filter(status=status)

    # Apply patient search
    if patient_search:
        consultations = consultations.filter(
            Q(queue_entry__patient__first_name__icontains=patient_search) |
            Q(queue_entry__patient__last_name__icontains=patient_search) |
            Q(queue_entry__patient__card_number__icontains=patient_search)
        )

    # Handle CSV export
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="consultation_history.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Date', 'Patient Name', 'Patient ID', 'Queue Number',
            'Diagnosis', 'Duration', 'Status'
        ])

        for consultation in consultations:
            duration = ''
            if consultation.completed_at:
                delta = consultation.completed_at - consultation.created_at
                duration = f"{delta.seconds // 3600}h {(delta.seconds % 3600) // 60}m"

            writer.writerow([
                consultation.created_at.strftime('%Y-%m-%d %H:%M'),
                f"{consultation.queue_entry.patient.first_name} {consultation.queue_entry.patient.last_name}",
                consultation.queue_entry.patient.card_number,
                consultation.queue_entry.queue_number,
                consultation.diagnosis or 'Not recorded',
                duration,
                consultation.get_status_display()
            ])

        return response

    # Pagination
    paginator = Paginator(consultations, 20)
    page = request.GET.get('page')
    consultations = paginator.get_page(page)

    # Calculate statistics
    all_consultations = ConsultationSessionModel.objects.filter(
        queue_entry__consultant=consultant
    )
    stats = {
        'total_consultations': all_consultations.count(),
        'completed': all_consultations.filter(status='completed').count(),
        'avg_duration': '45m',  # You can calculate this properly
        'prescriptions': DrugOrderModel.objects.filter(
            ordered_by=request.user
        ).count(),
        'tests_ordered': LabTestOrderModel.objects.filter(
            ordered_by=request.user
        ).count(),
    }

    context = {
        'consultant': consultant,
        'consultations': consultations,
        'stats': stats,
    }

    return render(request, 'consultation/doctor/history.html', context)


@login_required
@permission_required('consultation.add_consultationsessionmodel', raise_exception=True)
def patient_history_view(request, patient_id):
    """Renders the initial patient history page."""
    patient = get_object_or_404(PatientModel, id=patient_id)

    # Get all completed consultations for the patient, ordered by most recent
    all_consultations = ConsultationSessionModel.objects.filter(
        queue_entry__patient=patient,
        status='completed'
    ).order_by('-created_at').prefetch_related(
        'drug_consultation_order',  # Renamed from drug_orders in DrugOrderModel
        'external_prescriptions',
        'lab_consultation_order',  # Renamed from lab_test_orders in LabTestOrderModel
        'scan_consultation_order'  # Renamed from scan_orders in ScanOrderModel
    )

    # Paginate the results, 3 per page
    paginator = Paginator(all_consultations, 3)
    page_obj = paginator.get_page(1)  # Get the first page

    context = {
        'patient': patient,
        'consultations_page': page_obj,
    }
    return render(request, 'consultation/history/patient_history.html', context)


def patient_history_ajax(request, patient_id):
    """Handles AJAX requests for subsequent pages of patient history."""
    patient = get_object_or_404(PatientModel, id=patient_id)
    page_number = request.GET.get('page', 1)

    all_consultations = ConsultationSessionModel.objects.filter(
        queue_entry__patient=patient,
        status='completed'
    ).order_by('-created_at').prefetch_related(
        'drug_consultation_order',
        'external_prescriptions',
        'lab_consultation_order',
        'scan_consultation_order'
    )

    paginator = Paginator(all_consultations, 3)
    page_obj = paginator.get_page(page_number)

    # Render just the partial template with the new consultations
    html = render_to_string(
        'consultation/history/partials/consultation_block.html',
        {'consultations_page': page_obj},
        request=request
    )

    return JsonResponse({
        'html': html,
        'has_next': page_obj.has_next()
    })



# AJAX Views
@login_required
@require_POST
def ajax_call_next_patient(request):
    """Call the next patient in queue"""
    try:
        consultant = get_object_or_404(ConsultantModel, staff__staff_profile__user=request.user)

        # Check if doctor has an active consultation

        active_consultation = ConsultationSessionModel.objects.filter(
            queue_entry__consultant=consultant,
            status='in_progress',
            created_at__date=timezone.now().date()  # <-- This is the addition
        ).first()

        if active_consultation:
            return JsonResponse({
                'success': False,
                'error': 'You have an active consultation. Please complete or pause it first.'
            })

        # Get next patient in queue
        next_patient = PatientQueueModel.objects.filter(
            consultant=consultant,
            status='vitals_done',
            joined_queue_at__date=date.today()
        ).order_by('priority_level', 'joined_queue_at').first()

        if not next_patient:
            return JsonResponse({
                'success': False,
                'error': 'No patients waiting in your queue.'
            })

        # Start consultation
        with transaction.atomic():
            # Update queue status
            next_patient.start_consultation()

            # Create consultation session
            consultation = ConsultationSessionModel.objects.create(
                queue_entry=next_patient,
                status='in_progress'
            )

        return JsonResponse({
            'success': True,
            'message': f'Started consultation with {next_patient.patient.first_name} {next_patient.patient.last_name}',
            'consultation_id': consultation.id,
            'patient_name': f"{next_patient.patient.first_name} {next_patient.patient.last_name}"
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'System error: {str(e)}'
        })


@login_required
@require_POST
def ajax_start_consultation(request, queue_id):
    """Start consultation for specific queue entry"""
    try:
        consultant = get_object_or_404(ConsultantModel, staff__staff_profile__user=request.user)
        queue_entry = get_object_or_404(
            PatientQueueModel,
            id=queue_id,
            consultant=consultant,
            status='vitals_done'
        )

        # Check for active consultation
        active_consultation = ConsultationSessionModel.objects.filter(
            queue_entry__consultant=consultant,
            status='in_progress',
            created_at__date=timezone.now().date()  # <-- This is the addition
        ).first()

        if active_consultation:
            return JsonResponse({
                'success': False,
                'error': 'You have an active consultation. Please complete or pause it first.'
            })

        with transaction.atomic():
            # Update queue status
            queue_entry.start_consultation()

            # Create consultation session
            consultation = ConsultationSessionModel.objects.create(
                queue_entry=queue_entry,
                status='in_progress'
            )

        return JsonResponse({
            'success': True,
            'message': 'Consultation started successfully',
            'consultation_id': consultation.id
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Failed to start consultation: {str(e)}'
        })


@login_required
@require_POST
def ajax_pause_consultation(request, consultation_id):
    """Pause an active consultation"""
    try:
        consultant = get_object_or_404(ConsultantModel, staff__staff_profile__user=request.user)
        consultation = get_object_or_404(
            ConsultationSessionModel,
            id=consultation_id,
            queue_entry__consultant=consultant,
            status='in_progress'
        )

        with transaction.atomic():
            consultation.status = 'paused'
            consultation.save()

            consultation.queue_entry.pause_consultation()

        return JsonResponse({
            'success': True,
            'message': 'Consultation paused successfully'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Failed to pause consultation: {str(e)}'
        })


@login_required
@require_POST
def ajax_resume_consultation(request, consultation_id):
    """Resume a paused consultation"""
    try:
        consultant = get_object_or_404(ConsultantModel, staff__staff_profile__user=request.user)
        consultation = get_object_or_404(
            ConsultationSessionModel,
            id=consultation_id,
            queue_entry__consultant=consultant,
            status='paused'
        )
        today = timezone.localdate()
        # Check for other active consultations
        active_consultation = ConsultationSessionModel.objects.filter(
            queue_entry__consultant=consultant,
            status='in_progress', created_at__date=today
        ).first()

        if active_consultation:
            return JsonResponse({
                'success': False,
                'error': 'You have another active consultation. Please complete it first.'
            })

        with transaction.atomic():
            consultation.status = 'in_progress'
            consultation.save()

            consultation.queue_entry.resume_consultation()

        return JsonResponse({
            'success': True,
            'message': 'Consultation resumed successfully'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Failed to resume consultation: {str(e)}'
        })


@login_required
@require_POST
def ajax_complete_consultation(request, consultation_id):
    """Complete a consultation"""
    try:
        consultant = get_object_or_404(ConsultantModel, staff__staff_profile__user=request.user)
        consultation = get_object_or_404(
            ConsultationSessionModel,
            id=consultation_id,
            queue_entry__consultant=consultant,
            status__in=['in_progress', 'paused']
        )

        with transaction.atomic():
            consultation.complete_consultation()

        return JsonResponse({
            'success': True,
            'message': 'Consultation completed successfully'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Failed to complete consultation: {str(e)}'
        })


@login_required
@require_POST
def ajax_save_consultation(request, consultation_id):
    """Save consultation notes"""
    try:
        consultant = get_object_or_404(ConsultantModel, staff__staff_profile__user=request.user)
        consultation = get_object_or_404(
            ConsultationSessionModel,
            id=consultation_id,
            queue_entry__consultant=consultant
        )

        # Update consultation fields
        consultation.chief_complaint = request.POST.get('chief_complaint', '')
        consultation.history_of_present_illness = request.POST.get('history_of_present_illness', '')
        consultation.past_medical_history = request.POST.get('past_medical_history', '')
        consultation.physical_examination = request.POST.get('physical_examination', '')
        consultation.assessment = request.POST.get('assessment', '')
        consultation.diagnosis = request.POST.get('diagnosis', '')
        consultation.treatment_plan = request.POST.get('treatment_plan', '')
        consultation.follow_up_instructions = request.POST.get('follow_up_instructions', '')

        consultation.save()

        return JsonResponse({
            'success': True,
            'message': 'Consultation notes saved successfully'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Failed to save consultation: {str(e)}'
        })


@login_required
def ajax_search_drugs(request):
    """Search for drugs to prescribe"""
    try:
        query = request.GET.get('q', '').strip()

        if len(query) < 2:
            return JsonResponse({'drugs': []})

        # Ensure you select related all the way to the generic drug
        drugs = DrugModel.objects.filter(
            Q(brand_name__icontains=query) |
            Q(formulation__generic_drug__generic_name__icontains=query),
            is_active=True
        ).select_related('formulation__generic_drug', 'manufacturer')[:20]

        drugs_data = []
        for drug in drugs:

            drugs_data.append({
                'id': drug.id,
                'brand_name': drug.brand_name,
                'generic_name': drug.formulation.generic_drug.generic_name,
                'pharmacy_quantity': drug.pharmacy_quantity,
                'formulation': str(drug.formulation),
                'manufacturer': drug.manufacturer.name if drug.manufacturer else '',
                'last_cost_price': drug.last_cost_price if drug.last_cost_price else 0,
                'pack_size': drug.pack_size,
                'unit': drug.formulation.form_type,
                'price': float(drug.selling_price),
                'is_prescription_only': drug.formulation.generic_drug.is_prescription_only
            })

        return JsonResponse({'drugs': drugs_data})

    except Exception as e:
        # It's good practice to log the exception for debugging purposes
        # import logging
        # logging.error(f"Drug search failed: {e}")
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred during drug search.'
        })


@login_required
@require_POST
def ajax_prescribe_drug(request):
    """Prescribe a drug to patient"""
    try:
        patient_id = request.POST.get('patient_id')
        consultation_id = request.POST.get('consultation_id') # NEW: Get the consultation ID
        drug_id = request.POST.get('drug_id')
        quantity = request.POST.get('quantity_ordered')
        dosage_instructions = request.POST.get('dosage_instructions', '')
        duration = request.POST.get('duration', '')
        notes = request.POST.get('notes', '')

        # NEW: Add consultation_id to the validation
        if not all([patient_id, drug_id, quantity, consultation_id]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required fields (patient, drug, quantity, or consultation)'
            })

        patient = get_object_or_404(PatientModel, id=patient_id)
        drug = get_object_or_404(DrugModel, id=drug_id)
        consultation = get_object_or_404(ConsultationSessionModel, id=consultation_id) # NEW: Get the consultation object

        # Create drug order
        drug_order = DrugOrderModel.objects.create(
            patient=patient,
            consultation=consultation, # NEW: Link the consultation to the order
            drug=drug,
            quantity_ordered=float(quantity),
            dosage_instructions=dosage_instructions,
            duration=duration,
            ordered_by=request.user,
            notes=notes
        )

        return JsonResponse({
            'success': True,
            'message': f'{drug.brand_name or drug.generic_name} prescribed successfully',
            'order_id': drug_order.id
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Failed to prescribe drug: {str(e)}'
        })


@login_required
def ajax_lab_templates(request):
    """Get lab test templates by category"""
    try:
        category_id = request.GET.get('category_id')

        if not category_id:
            return JsonResponse({'templates': []})

        templates = LabTestTemplateModel.objects.filter(
            category_id=category_id,
            is_active=True
        ).order_by('name')

        templates_data = []
        for template in templates:
            templates_data.append({
                'id': template.id,
                'name': template.name,
                'code': template.code,
                'price': float(template.price),
                'sample_type': template.sample_type
            })

        return JsonResponse({'templates': templates_data})

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Failed to load templates: {str(e)}'
        })


@login_required
@require_POST
def ajax_order_lab_test(request):
    """Order a lab test for a patient during a consultation"""
    try:
        patient_id = request.POST.get('patient_id')
        consultation_id = request.POST.get('consultation_id') # NEW: Get the consultation ID
        template_id = request.POST.get('template_id')
        special_instructions = request.POST.get('special_instructions', '')

        # NEW: Add consultation_id to validation
        if not all([patient_id, template_id, consultation_id]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required fields (patient, test, or consultation).'
            })

        patient = get_object_or_404(PatientModel, id=patient_id)
        template = get_object_or_404(LabTestTemplateModel, id=template_id)
        consultation = get_object_or_404(ConsultationSessionModel, id=consultation_id) # NEW: Get the consultation object

        # Create lab test order
        lab_order = LabTestOrderModel.objects.create(
            patient=patient,
            consultation=consultation, # NEW: Link the consultation to the order
            template=template,
            ordered_by=request.user,
            special_instructions=special_instructions,
            source='doctor'
        )

        return JsonResponse({
            'success': True,
            'message': f'{template.name} ordered successfully',
            'order_id': lab_order.id
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Failed to order lab test: {str(e)}'
        })


@login_required
def ajax_scan_templates(request):
    """Get scan templates by category"""
    try:
        category_id = request.GET.get('category_id')

        if not category_id:
            return JsonResponse({'templates': []})

        templates = ScanTemplateModel.objects.filter(
            category_id=category_id,
            is_active=True
        ).order_by('name')

        templates_data = []
        for template in templates:
            templates_data.append({
                'id': template.id,
                'name': template.name,
                'code': template.code,
                'price': float(template.price),
                'scan_type': template.scan_type,
                'estimated_duration': template.estimated_duration
            })

        return JsonResponse({'templates': templates_data})

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Failed to load scan templates: {str(e)}'
        })


@login_required
@require_POST
def ajax_order_scan(request):
    """Order a scan for patient"""
    try:
        patient_id = request.POST.get('patient_id')
        template_id = request.POST.get('template_id')
        clinical_indication = request.POST.get('clinical_indication', '')
        special_instructions = request.POST.get('special_instructions', '')

        if not all([patient_id, template_id]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required fields'
            })

        patient = get_object_or_404(PatientModel, id=patient_id)
        template = get_object_or_404(ScanTemplateModel, id=template_id)

        # Create scan order
        scan_order = ScanOrderModel.objects.create(
            patient=patient,
            template=template,
            ordered_by=request.user,
            clinical_indication=clinical_indication,
            special_instructions=special_instructions
        )

        return JsonResponse({
            'success': True,
            'message': f'{template.name} ordered successfully',
            'order_id': scan_order.id
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Failed to order scan: {str(e)}'
        })


@login_required
def ajax_lab_templates_search(request):
    """Search for lab test templates by name, optionally filtered by category."""
    try:
        query = request.GET.get('q', '')
        category_id = request.GET.get('category_id')

        # CHANGED: Remove is_active filter - show ALL templates
        templates = LabTestTemplateModel.objects.all()

        if category_id:
            templates = templates.filter(category_id=category_id)

        if len(query) >= 2:
            templates = templates.filter(name__icontains=query)

        templates = templates.order_by('name')[:15]

        templates_data = [{
            'id': t.id,
            'name': t.name,
            'price': float(t.price),
            'is_active': t.is_active,  # NEW: Add is_active status
        } for t in templates]

        return JsonResponse({'templates': templates_data})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def ajax_imaging_templates_search(request):
    """Search for imaging (scan) templates by name, optionally filtered by category."""
    try:
        query = request.GET.get('q', '')
        category_id = request.GET.get('category_id')

        # CHANGED: Remove is_active filter - show ALL templates
        templates = ScanTemplateModel.objects.all()

        if category_id:
            templates = templates.filter(category_id=category_id)

        if len(query) >= 2:
            templates = templates.filter(name__icontains=query)

        templates = templates.order_by('name')[:15]

        templates_data = [{
            'id': t.id,
            'name': t.name,
            'price': float(t.price),
            'is_active': t.is_active,  # NEW: Add is_active status
        } for t in templates]

        return JsonResponse({'templates': templates_data})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# --- NEW MULTI-ORDER VIEWS ---

@login_required
@require_POST
def ajax_order_multiple_lab_tests(request):
    """Order multiple lab tests for a patient in a single transaction."""
    try:
        data = json.loads(request.body)
        patient_id = data.get('patient_id')
        consultation_id = data.get('consultation_id')
        orders = data.get('orders', [])

        if not all([patient_id, consultation_id, orders]):
            return JsonResponse({'success': False, 'error': 'Missing required data.'}, status=400)

        patient = get_object_or_404(PatientModel, id=patient_id)
        consultation = get_object_or_404(ConsultationSessionModel, id=consultation_id)

        internal_count = 0
        external_count = 0

        with transaction.atomic():
            for order_data in orders:
                template = get_object_or_404(LabTestTemplateModel, id=order_data.get('template_id'))

                # NEW: Route based on is_active
                if template.is_active:
                    # Internal order
                    LabTestOrderModel.objects.create(
                        patient=patient,
                        consultation=consultation,
                        template=template,
                        ordered_by=request.user,
                        special_instructions=order_data.get('instructions', ''),
                        source='doctor',
                    )
                    internal_count += 1
                else:
                    # External order
                    ExternalLabTestOrder.objects.create(
                        patient=patient,
                        consultation=consultation,
                        ordered_by=request.user,
                        test_name=template.name,
                        test_code=template.code,
                        category_name=template.category.name if template.category else '',
                        special_instructions=order_data.get('instructions', ''),
                    )
                    external_count += 1

        # NEW: Build message showing internal vs external
        message_parts = []
        if internal_count > 0:
            message_parts.append(f'{internal_count} internal lab test(s)')
        if external_count > 0:
            message_parts.append(f'{external_count} external lab test(s)')

        message = ' and '.join(message_parts) + ' ordered successfully.'

        return JsonResponse({'success': True, 'message': message})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def ajax_order_multiple_imaging(request):
    """Order multiple imaging (scans) for a patient in a single transaction."""
    try:
        data = json.loads(request.body)
        patient_id = data.get('patient_id')
        consultation_id = data.get('consultation_id')
        orders = data.get('orders', [])

        if not all([patient_id, consultation_id, orders]):
            return JsonResponse({'success': False, 'error': 'Missing required data.'}, status=400)

        patient = get_object_or_404(PatientModel, id=patient_id)
        consultation = get_object_or_404(ConsultationSessionModel, id=consultation_id)

        internal_count = 0
        external_count = 0

        with transaction.atomic():
            for order_data in orders:
                template = get_object_or_404(ScanTemplateModel, id=order_data.get('template_id'))

                # NEW: Route based on is_active
                if template.is_active:
                    # Internal order
                    ScanOrderModel.objects.create(
                        patient=patient,
                        consultation=consultation,
                        template=template,
                        ordered_by=request.user,
                        clinical_indication=order_data.get('indication', ''),
                        special_instructions=order_data.get('instructions', ''),
                    )
                    internal_count += 1
                else:
                    # External order
                    ExternalScanOrder.objects.create(
                        patient=patient,
                        consultation=consultation,
                        ordered_by=request.user,
                        scan_name=template.name,
                        scan_code=template.code,
                        category_name=template.category.name if template.category else '',
                        clinical_indication=order_data.get('indication', ''),
                        special_instructions=order_data.get('instructions', ''),
                    )
                    external_count += 1

        # NEW: Build message showing internal vs external
        message_parts = []
        if internal_count > 0:
            message_parts.append(f'{internal_count} internal scan(s)')
        if external_count > 0:
            message_parts.append(f'{external_count} external scan(s)')

        message = ' and '.join(message_parts) + ' ordered successfully.'

        return JsonResponse({'success': True, 'message': message})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def ajax_consultation_details(request, consultation_id):
    """Get detailed consultation information for modal view"""
    try:
        consultant = get_object_or_404(ConsultantModel, staff__staff_profile__user=request.user)
        consultation = get_object_or_404(
            ConsultationSessionModel,
            id=consultation_id,
            queue_entry__consultant=consultant
        )

        # Generate HTML content for the modal
        html_content = f"""
        <div class="row">
            <div class="col-md-6">
                <h6 class="text-primary">Patient Information</h6>
                <table class="table table-sm">
                    <tr><td><strong>Name:</strong></td><td>{consultation.queue_entry.patient.first_name} {consultation.queue_entry.patient.last_name}</td></tr>
                    <tr><td><strong>ID:</strong></td><td>{consultation.queue_entry.patient.card_number}</td></tr>
                    <tr><td><strong>Age:</strong></td><td>{consultation.queue_entry.patient.age} years</td></tr>
                    <tr><td><strong>Gender:</strong></td><td>{consultation.queue_entry.patient.gender.title()}</td></tr>
                    <tr><td><strong>Queue #:</strong></td><td>{consultation.queue_entry.queue_number}</td></tr>
                </table>

                <h6 class="text-primary mt-3">Vital Signs</h6>
                {f'''
                <table class="table table-sm">
                    <tr><td><strong>BP:</strong></td><td>{consultation.queue_entry.vitals.blood_pressure}</td></tr>
                    <tr><td><strong>Pulse:</strong></td><td>{consultation.queue_entry.vitals.pulse_rate or 'N/A'} BPM</td></tr>
                    <tr><td><strong>Temperature:</strong></td><td>{consultation.queue_entry.vitals.temperature or 'N/A'}°C</td></tr>
                    <tr><td><strong>SpO2:</strong></td><td>{consultation.queue_entry.vitals.oxygen_saturation or 'N/A'}%</td></tr>
                </table>
                ''' if hasattr(consultation.queue_entry, 'vitals') and consultation.queue_entry.vitals else '<p class="text-muted">No vitals recorded</p>'}
            </div>

            <div class="col-md-6">
                <h6 class="text-primary">Consultation Notes</h6>
                <div class="mb-2">
                    <strong>Chief Complaint:</strong>
                    <p class="text-muted">{consultation.chief_complaint or 'Not recorded'}</p>
                </div>
                <div class="mb-2">
                    <strong>Assessment:</strong>
                    <p class="text-muted">{consultation.assessment or 'Not recorded'}</p>
                </div>
                <div class="mb-2">
                    <strong>Diagnosis:</strong>
                    <p class="text-muted">{consultation.diagnosis or 'Not recorded'}</p>
                </div>
                
                
            </div>
        </div>

        <div class="row mt-3">
            <div class="col-12">
                <h6 class="text-primary">Session Information</h6>
                <table class="table table-sm">
                    <tr><td><strong>Started:</strong></td><td>{consultation.created_at.strftime('%B %d, %Y at %I:%M %p')}</td></tr>
                    <tr><td><strong>Status:</strong></td><td><span class="badge bg-{'success' if consultation.status == 'completed' else 'info'}">{consultation.get_status_display()}</span></td></tr>
                    {f'<tr><td><strong>Completed:</strong></td><td>{consultation.completed_at.strftime("%B %d, %Y at %I:%M %p")}</td></tr>' if consultation.completed_at else ''}
                </table>
            </div>
        </div>
        """

        return JsonResponse({
            'success': True,
            'html': html_content
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Failed to load consultation details: {str(e)}'
        })


@login_required
def patient_history(request, patient_id):
    """View complete patient history"""
    try:
        consultant = get_object_or_404(ConsultantModel, staff__user_staff_profile__user=request.user)
        patient = get_object_or_404(PatientModel, id=patient_id)

        # Get all consultations for this patient
        consultations = ConsultationSessionModel.objects.filter(
            queue_entry__patient=patient,
            status='completed'
        ).select_related('queue_entry').order_by('-created_at')

        # Get prescriptions
        prescriptions = DrugOrderModel.objects.filter(
            patient=patient
        ).select_related('drug').order_by('-ordered_at')[:20]

        # Get lab tests
        lab_tests = LabTestOrderModel.objects.filter(
            patient=patient
        ).select_related('template').order_by('-ordered_at')[:20]

        # Get scans
        scans = ScanOrderModel.objects.filter(
            patient=patient
        ).select_related('template').order_by('-ordered_at')[:20]

        context = {
            'consultant': consultant,
            'patient': patient,
            'consultations': consultations,
            'prescriptions': prescriptions,
            'lab_tests': lab_tests,
            'scans': scans,
        }

        return render(request, 'doctor/patient_history.html', context)

    except Exception as e:
        messages.error(request, f"Error loading patient history: {str(e)}")
        return redirect('doctor_dashboard')


@login_required
def patient_prescriptions(request, patient_id):
    """View patient prescription history"""
    try:
        consultant = get_object_or_404(ConsultantModel, staff__staff_profile__user=request.user)
        patient = get_object_or_404(PatientModel, id=patient_id)

        prescriptions = DrugOrderModel.objects.filter(
            patient=patient
        ).select_related('drug', 'ordered_by').order_by('-ordered_at')

        context = {
            'consultant': consultant,
            'patient': patient,
            'prescriptions': prescriptions,
        }

        return render(request, 'consultation/doctor/patient_prescriptions.html', context)

    except Exception as e:
        messages.error(request, f"Error loading prescriptions: {str(e)}")
        return redirect('doctor_dashboard')


@login_required
@permission_required('consultation.add_consultationsessionmodel', raise_exception=True)
def patient_test_results(request, patient_id):
    """View patient test results"""
    try:
        consultant = get_object_or_404(ConsultantModel, staff__user=request.user)
        patient = get_object_or_404(PatientModel, id=patient_id)

        # Get lab tests with results
        lab_tests = LabTestOrderModel.objects.filter(
            patient=patient
        ).select_related('template').prefetch_related('result').order_by('-ordered_at')

        # Get scans with results
        scans = ScanOrderModel.objects.filter(
            patient=patient
        ).select_related('template').prefetch_related('result').order_by('-ordered_at')

        context = {
            'consultant': consultant,
            'patient': patient,
            'lab_tests': lab_tests,
            'scans': scans,
        }

        return render(request, 'doctor/patient_test_results.html', context)

    except Exception as e:
        messages.error(request, f"Error loading test results: {str(e)}")
        return redirect('doctor_dashboard')


@login_required
def prescription_detail(request, prescription_id):
    """View prescription details"""
    try:
        prescription = get_object_or_404(DrugOrderModel, id=prescription_id)
        context = {
            'prescription': prescription,
        }
        return render(request, 'doctor/prescription_detail.html', context)

    except Exception as e:
        messages.error(request, f"Error loading prescription: {str(e)}")
        return redirect('doctor_dashboard')


@login_required
def lab_test_result(request, test_id):
    """View lab test result"""
    try:
        order = get_object_or_404(LabTestOrderModel, id=test_id)
        result = order.result
        context = {
            'order': order,
            'result': result,
            'patient': result.order.patient,
            'lab_setting': LabSettingModel.objects.first(),
            'template': result.order.template,
            'parameters': result.order.template.test_parameters.get('parameters', []),
            'results': result.results_data.get('results', [])
        }

        return render(request, 'consultation/doctor/lab_test_result.html', context)

    except Exception as e:
        messages.error(request, f"Error loading test result: {str(e)}")
        return redirect('doctor_dashboard')


@login_required
@permission_required('consultation.add_consultationsessionmodel', raise_exception=True)
def scan_result(request, scan_id):
    """View scan result"""
    try:
        scan = get_object_or_404(ScanOrderModel, id=scan_id)
        context = {
            'scan': scan,
        }
        return render(request, 'doctor/scan_result.html', context)

    except Exception as e:
        messages.error(request, f"Error loading scan result: {str(e)}")
        return redirect('doctor_dashboard')


@login_required
@permission_required('consultation.add_consultationsessionmodel', raise_exception=True)
def print_consultation(request, consultation_id):
    """Print consultation report"""
    try:
        consultant = get_object_or_404(ConsultantModel, staff__user=request.user)
        consultation = get_object_or_404(
            ConsultationSessionModel,
            id=consultation_id,
            queue_entry__consultant=consultant
        )

        context = {
            'consultation': consultation,
            'consultant': consultant,
        }

        return render(request, 'doctor/print_consultation.html', context)

    except Exception as e:
        messages.error(request, f"Error loading consultation: {str(e)}")
        return redirect('doctor_dashboard')


@login_required
@permission_required('consultation.add_consultationsessionmodel', raise_exception=True)
def view_consultation_detail(request, consultation_id):
    """View detailed consultation (read-only)"""
    try:
        consultant = get_object_or_404(ConsultantModel, staff__staff_profile__user=request.user)
        consultation = get_object_or_404(
            ConsultationSessionModel,
            id=consultation_id,
            queue_entry__consultant=consultant
        )

        # Get related data
        prescriptions = DrugOrderModel.objects.filter(
            patient=consultation.queue_entry.patient,
            ordered_at__date=consultation.created_at.date()
        ).select_related('drug')

        lab_tests = LabTestOrderModel.objects.filter(
            patient=consultation.queue_entry.patient,
            ordered_at__date=consultation.created_at.date()
        ).select_related('template')

        scans = ScanOrderModel.objects.filter(
            patient=consultation.queue_entry.patient,
            ordered_at__date=consultation.created_at.date()
        ).select_related('template')

        context = {
            'consultation': consultation,
            'consultant': consultant,
            'prescriptions': prescriptions,
            'lab_tests': lab_tests,
            'scans': scans,
            'read_only': True,
        }

        return render(request, 'consultation/doctor/consultation_detail.html', context)

    except Exception as e:
        messages.error(request, f"Error loading consultation: {str(e)}")
        return redirect('doctor_dashboard')


@login_required
@permission_required('consultation.add_consultationsessionmodel', raise_exception=True)
def new_consultation(request):
    """Create a new consultation (for walk-ins or special cases)"""
    try:
        consultant = get_object_or_404(ConsultantModel, staff__user=request.user)

        # Get all active patients for selection
        patients = PatientModel.objects.filter(
            is_active=True
        ).order_by('first_name', 'last_name')

        context = {
            'consultant': consultant,
            'patients': patients,
        }

        return render(request, 'doctor/new_consultation.html', context)

    except Exception as e:
        messages.error(request, f"Error: {str(e)}")
        return redirect('doctor_dashboard')


@login_required
@require_POST
def ajax_create_consultation(request):
    """Create a new consultation via AJAX"""
    try:
        consultant = get_object_or_404(ConsultantModel, staff__user=request.user)
        patient_id = request.POST.get('patient_id')
        chief_complaint = request.POST.get('chief_complaint', '')
        is_emergency = request.POST.get('is_emergency') == 'true'

        if not patient_id:
            return JsonResponse({
                'success': False,
                'error': 'Patient is required'
            })

        patient = get_object_or_404(PatientModel, id=patient_id)

        # Check if doctor has an active consultation
        active_consultation = ConsultationSessionModel.objects.filter(
            queue_entry__consultant=consultant,
            status='in_progress',
            created_at__date=timezone.now().date()  # <-- This is the addition
        ).first()

        if active_consultation:
            return JsonResponse({
                'success': False,
                'error': 'You have an active consultation. Please complete it first.'
            })

        with transaction.atomic():
            # Create a queue entry (bypass normal queue process)
            queue_entry = PatientQueueModel.objects.create(
                patient=patient,
                consultant=consultant,
                status='with_doctor',
                is_emergency=is_emergency,
                priority_level=2 if is_emergency else 0,
                notes=f"Direct consultation created by {request.user.get_full_name()}"
            )

            # Create consultation session
            consultation = ConsultationSessionModel.objects.create(
                queue_entry=queue_entry,
                chief_complaint=chief_complaint,
                status='in_progress'
            )

        return JsonResponse({
            'success': True,
            'message': f'New consultation started with {patient.first_name} {patient.last_name}',
            'consultation_id': consultation.id
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Failed to create consultation: {str(e)}'
        })


# --- Start: New Helper Function ---
# In your views.py

def _create_queue_entry_with_vitals_check(patient, payment_transaction, specialization, user):
    """
    Creates a PatientQueueModel entry.
    Checks for the most recent queue entry on the same day to copy vitals
    and set the queue status accordingly.
    """
    queue_status = 'waiting_vitals'
    new_vitals_data = None

    # --- Start: Updated Logic ---
    # Find the most recent queue entry for this patient from today that has vitals recorded.
    last_queue_entry_today = PatientQueueModel.objects.filter(
        patient=patient,
        joined_queue_at__date=date.today(),
        vitals__isnull=False  # Check that vitals exist for this queue entry
    ).order_by('-joined_queue_at').first()
    # --- End: Updated Logic ---

    if last_queue_entry_today:
        queue_status = 'vitals_done'  # Skip vitals queue
        old_vitals = last_queue_entry_today.vitals

        new_vitals_data = {
            'temperature': old_vitals.temperature,
            'blood_pressure_systolic': old_vitals.blood_pressure_systolic,
            'blood_pressure_diastolic': old_vitals.blood_pressure_diastolic,
            'pulse_rate': old_vitals.pulse_rate,
            'respiratory_rate': old_vitals.respiratory_rate,
            'oxygen_saturation': old_vitals.oxygen_saturation,
            'height': old_vitals.height,
            'weight': old_vitals.weight,
            'bmi': old_vitals.bmi,
            'general_appearance': old_vitals.general_appearance,
            'chief_complaint': f"{old_vitals.chief_complaint}",
            'notes': old_vitals.notes,
            'recorded_by': user,
        }

    # Create the new queue entry
    new_queue_entry = PatientQueueModel.objects.create(
        patient=patient,
        payment=payment_transaction,
        specialization=specialization,
        status=queue_status
    )

    # If there's vitals data to copy, create the new vitals record
    if new_vitals_data:
        PatientVitalsModel.objects.create(
            queue_entry=new_queue_entry,
            **new_vitals_data
        )

    return new_queue_entry


# --- Start: New AJAX Views ---
@login_required
def get_consultation_status_ajax(request):
    """
    A powerful single-point checker for consultation status.
    1. Checks if patient is already in an active queue (BLOCK).
    2. Checks for valid, un-used payments (RE-USE).
    3. Fetches the fee for a new payment (NEW).
    """
    patient_id = request.GET.get('patient_id')
    specialization_id = request.GET.get('specialization_id')
    today = date.today()

    patient = get_object_or_404(PatientModel, pk=patient_id)
    specialization = get_object_or_404(SpecializationModel, pk=specialization_id)

    # --- Start: New, More Robust Check ---
    # 1. Check if patient is already in an active queue for this specialization today.
    # An active queue is one not marked as completed or cancelled.
    active_queue_entry = PatientQueueModel.objects.filter(
        patient=patient,
        specialization=specialization,  # <-- The corrected line
        joined_queue_at__date=today
    ).exclude(
        status__in=['consultation_completed', 'cancelled']
    ).first()

    if active_queue_entry:
        return JsonResponse({
            'status': 'block',
            'reason': 'ACTIVE_QUEUE',
            'message': f"Patient is already in the queue for {specialization.name}. Current status: '{active_queue_entry.get_status_display()}'."
        })
    # --- End: New Check ---

    # 2. Check for a valid, un-used payment for this specialization's group
    if specialization.group:
        valid_payment = PatientTransactionModel.objects.filter(
            patient=patient,
            transaction_type='consultation_payment',
            status='completed',
            valid_till__gte=today,
            fee_structure__specialization__group=specialization.group
        ).order_by('-created_at').first()

        if valid_payment:
            return JsonResponse({
                'status': 'reuse_payment',
                'reason': 'EXISTING_PAYMENT',
                'message': f"Patient has a valid payment for the {specialization.group.name} group. You can add them to the queue directly.",
                'payment_id': valid_payment.id
            })

    # 3. If neither of the above, fetch the fee for a new payment
    fee = ConsultationFeeModel.objects.filter(
        specialization=specialization,
        patient_category='regular', # Adapt this as needed
        is_active=True
    ).first()

    if not fee:
        return JsonResponse({'status': 'block', 'reason': 'NO_FEE', 'message': f"No active consultation fee found for {specialization.name}."})

    return JsonResponse({
        'status': 'new_payment',
        'fee': {
            'id': fee.id,
            'amount': float(fee.amount),
            'formatted_amount': f'₦{fee.amount:,.2f}',
            'patient_category': fee.get_patient_category_display(),
        }
    })


@login_required
@require_POST
def create_queue_from_payment_ajax(request):
    """Creates a queue entry using an existing valid payment."""
    patient_id = request.POST.get('patient_id')
    payment_id = request.POST.get('payment_id')
    specialization_id = request.POST.get('specialization_id')

    patient = get_object_or_404(PatientModel, pk=patient_id)
    payment = get_object_or_404(PatientTransactionModel, pk=payment_id)
    specialization = get_object_or_404(SpecializationModel, pk=specialization_id)

    try:
        with transaction.atomic():
            # Use our helper function to create the queue entry
            queue_entry = _create_queue_entry_with_vitals_check(patient, payment, specialization, request.user)

        return JsonResponse({
            'success': True,
            'message': f"Patient added to queue successfully! Queue number is {queue_entry.queue_number}.",
            'queue_number': queue_entry.queue_number,
            'redirect_url': reverse('patient_queue_index')
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'An unexpected error occurred: {str(e)}'}, status=500)


@login_required
def update_patient_allergy(request, patient_id):
    patient = get_object_or_404(PatientModel, id=patient_id)

    # Try to get the existing allergy profile, or None if it doesn't exist
    allergy_instance = Allergy.objects.filter(patient=patient).first()

    if request.method == 'POST':
        # The form needs an instance if we are updating, or no instance for creation
        form = AllergyForm(request.POST, instance=allergy_instance)

        if form.is_valid():
            allergy = form.save(commit=False)
            allergy.patient = patient
            allergy.updated_by = request.user
            allergy.save()

            return JsonResponse({
                'success': True,
                'details': allergy.details,
                'updated_by': allergy.updated_by.get_full_name() or allergy.updated_by.username,
                'updated_at': allergy.updated_at.strftime('%b %d, %Y, %I:%M %p'),
            })
        else:
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)


@login_required
@require_POST
def prescribe_multiple_view(request):
    try:
        data = json.loads(request.body)
        patient_id = data.get('patient_id')
        consultation_id = data.get('consultation_id')

        available_drugs = data.get('available_drugs', [])
        external_drugs = data.get('external_drugs', [])

        patient = PatientModel.objects.get(id=patient_id)
        consultation = ConsultationSessionModel.objects.get(id=consultation_id)

        with transaction.atomic():
            # Process drugs from inventory
            for drug_data in available_drugs:
                drug = DrugModel.objects.get(id=drug_data.get('drug_id'))
                DrugOrderModel.objects.create(
                    patient=patient,
                    consultation=consultation,
                    ordered_by=request.user,
                    drug=drug,
                    dosage_instructions=drug_data.get('dosage'),
                    duration=drug_data.get('duration'),
                    quantity_ordered=float(drug_data.get('quantity', 0)),
                    notes=drug_data.get('notes'),
                    status='pending',  # Default status
                )

            # Process drugs not in inventory
            for drug_data in external_drugs:
                ExternalPrescription.objects.create(
                    patient=patient,
                    consultation=consultation,
                    ordered_by=request.user,
                    drug_name=drug_data.get('drug_name'),
                    dosage_instructions=drug_data.get('dosage'),
                    duration=drug_data.get('duration'),
                    quantity=drug_data.get('quantity'),
                    notes=drug_data.get('notes'),
                )

        return JsonResponse({'success': True, 'message': 'Prescriptions saved successfully.'})

    except Exception as e:
        # Log the error e for debugging
        return JsonResponse({'success': False, 'error': f'An error occurred: {str(e)}'}, status=500)


# --- End: New AJAX Views ---
# -------------------------
# END OF CONSULTATION VIEWS
# -------------------------

"""
CONSULTATION WORKFLOW SUMMARY:
=============================

1. SETUP PHASE:
   - Create Specializations (Cardiology, Pediatrics, etc.)
   - Create Consultation Blocks (Building A, Building B, etc.) 
   - Create Consultation Rooms within blocks
   - Assign Staff to Consultant roles with specializations
   - Set Consultation Fees by specialization and patient type

2. DAILY OPERATIONS:
   - Patient pays consultation fee (ConsultationPayment)
   - Patient joins queue (PatientQueue) 
   - Nurse takes vitals (PatientVitals)
   - Doctor conducts consultation (ConsultationSession)
   - Consultation completed and recorded

3. MANAGEMENT & REPORTING:
   - View consultation records and history
   - Generate reports and analytics
   - Export data for external analysis
   - Manage doctor schedules and availability

4. REAL-TIME MONITORING:
   - Live queue status updates
   - Dashboard with key metrics
   - Mobile-friendly interfaces
   - AJAX endpoints for dynamic updates

The system handles the complete consultation lifecycle from setup to reporting,
with proper permission controls and audit trails throughout.
"""