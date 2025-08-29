import logging
from datetime import datetime, date, time, timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils.timezone import now
from django.views.generic import (
    CreateView, ListView, UpdateView, DeleteView, DetailView, TemplateView
)
from django.db.models import Q, Count, Sum
from django.contrib.auth.models import User

from consultation.models import *
from consultation.forms import *
from patient.models import PatientModel
from human_resource.models import StaffModel

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
        return context


class SpecializationUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    SuccessMessageMixin, UpdateView
):
    model = SpecializationModel
    permission_required = 'consultation.change_specializationmodel'
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
    permission_required = 'consultation.delete_specializationmodel'
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
            'consultants': ConsultantModel.objects.filter(specialization=specialization),
            'fees': ConsultationFeeModel.objects.filter(specialization=specialization),
            'total_consultants': ConsultantModel.objects.filter(specialization=specialization).count(),
        })
        return context


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
    permission_required = 'consultation.change_consultationblockmodel'
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
    permission_required = 'consultation.delete_consultationblockmodel'
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
    permission_required = 'consultation.add_consultationroommodel'
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
    permission_required = 'consultation.view_consultationroommodel'
    template_name = 'consultation/room/index.html'
    context_object_name = "room_list"

    def get_queryset(self):
        return ConsultationRoomModel.objects.select_related('block', 'specialization').order_by('block__name', 'name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = ConsultationRoomForm()
        context['block_list'] = ConsultationBlockModel.objects.all().order_by('name')
        return context


class ConsultationRoomUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    SuccessMessageMixin, UpdateView
):
    model = ConsultationRoomModel
    permission_required = 'consultation.change_consultationroommodel'
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
    permission_required = 'consultation.delete_consultationroommodel'
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


class ConsultantUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin,
    SuccessMessageMixin, UpdateView
):
    model = ConsultantModel
    permission_required = 'consultation.change_consultantmodel'
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
    permission_required = 'consultation.delete_consultantmodel'
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
    permission_required = 'consultation.change_consultationfeemodel'
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
    permission_required = 'consultation.delete_consultationfeemodel'
    template_name = 'consultation/fee/delete.html'
    context_object_name = "fee"
    success_message = 'Consultation Fee Successfully Deleted'

    def get_success_url(self):
        return reverse('consultation_fee_index')


# -------------------------
# 6. CONSULTATION PAYMENTS (Multi-field)
# -------------------------
class ConsultationPaymentCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, ConsultationContextMixin,
    SuccessMessageMixin, CreateView
):
    model = ConsultationPaymentModel
    permission_required = 'consultation.add_consultationpaymentmodel'
    form_class = ConsultationPaymentForm
    template_name = 'consultation/payment/create.html'
    success_message = 'Payment Successfully Processed and Patient Added to Queue'

    def get_success_url(self):
        return reverse('patient_queue_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'available_consultants': ConsultantModel.objects.filter(
                is_available_for_consultation=True
            ).select_related('staff', 'specialization').order_by('specialization__name', 'staff__first_name'),
            'specializations': SpecializationModel.objects.all().order_by('name'),
        })
        return context

    @transaction.atomic
    def form_valid(self, form):
        try:
            # Set processed_by and payment method
            form.instance.processed_by = self.request.user
            form.instance.payment_method = 'wallet'

            # Get patient and validate wallet balance
            patient = form.instance.patient
            amount_to_pay = form.instance.amount_paid

            if not hasattr(patient, 'wallet'):
                messages.error(self.request, 'Patient does not have a wallet account')
                return super().form_invalid(form)

            if patient.wallet.amount < amount_to_pay:
                messages.error(
                    self.request,
                    f'Insufficient wallet balance. Available: ₦{patient.wallet.balance}, Required: ₦{amount_to_pay}'
                )
                return super().form_invalid(form)

            # Save payment first
            response = super().form_valid(form)

            patient.wallet.amount -= amount_to_pay
            patient.wallet.save()

            # Create queue entry
            is_emergency = form.cleaned_data.get('is_emergency', False)

            queue_entry = PatientQueueModel.objects.create(
                patient=self.object.patient,
                payment=self.object,
                priority_level=2 if is_emergency else 0,
                notes=form.cleaned_data.get('notes', ''),
                is_emergency=is_emergency
            )

            messages.success(
                self.request,
                f'Payment processed successfully! Queue number: {queue_entry.queue_number}. '
            )

            return response

        except Exception as e:
            logger.exception("Error processing consultation payment")
            messages.error(self.request, f"Error processing payment: {str(e)}")
            return super().form_invalid(form)

    def form_invalid(self, form):
        for field, errors in form.errors.items():
            label = form.fields.get(field).label if form.fields.get(field) else field
            for error in errors:
                messages.error(self.request, f"{label}: {error}")
        return super().form_invalid(form)


# AJAX endpoints for the wallet payment flow
@login_required
def verify_patient_ajax(request):
    """Verify patient by card number and return wallet details"""
    card_number = request.GET.get('card_number', '').strip()

    if not card_number:
        return JsonResponse({'error': 'Card number required'}, status=400)

    try:
        # Look up patient by patient_id (card number)
        patient = PatientModel.objects.get(card_number=card_number)

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
                expiry_date__gt=date.today()
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
                'provider': active_insurance.provider if active_insurance else None,
                'coverage_percentage': float(active_insurance.coverage_percentage) if active_insurance else 0,
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

    if not specialization_id:
        return JsonResponse({'error': 'Specialization ID required'}, status=400)

    try:
        # Get patient to check insurance status
        patient_category = 'regular'
        if patient_id:
            patient = PatientModel.objects.get(id=patient_id)
            # Check if patient has active insurance
            if hasattr(patient, 'insurance_policies'):
                active_insurance = patient.insurance_policies.filter(
                    is_active=True,
                    expiry_date__gt=date.today()
                ).exists()
                if active_insurance:
                    patient_category = 'insurance'

        # Get consultation fee
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
    model = ConsultationPaymentModel
    permission_required = 'consultation.view_consultationpaymentmodel'
    template_name = 'consultation/payment/list.html'
    context_object_name = "payment_list"
    paginate_by = 50

    def get_queryset(self):
        today = date.today()
        return ConsultationPaymentModel.objects.select_related(
            'patient', 'fee_structure__specialization'
        ).filter(created_at__date=today).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = date.today()

        context.update({
            'today_stats': self.get_today_stats(),
            'pending_payments': ConsultationPaymentModel.objects.filter(
                created_at__date=today, status='pending'
            ).count(),
        })
        return context

    def get_today_stats(self):
        """Get today's payment statistics"""
        try:
            today = date.today()
            payments_today = ConsultationPaymentModel.objects.filter(created_at__date=today)

            return {
                'total_payments': payments_today.count(),
                'total_amount': payments_today.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0,
                'pending_count': payments_today.filter(status='pending').count(),
                'completed_count': payments_today.filter(status='paid').count(),
            }
        except Exception:
            return {'total_payments': 0, 'total_amount': 0, 'pending_count': 0, 'completed_count': 0}


class ConsultationPaymentDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = ConsultationPaymentModel
    permission_required = 'consultation.view_consultationpaymentmodel'
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


# -------------------------
# 7. PATIENT QUEUE MANAGEMENT
# -------------------------
class PatientQueueCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, ConsultationContextMixin,
    SuccessMessageMixin, CreateView
):
    model = PatientQueueModel
    permission_required = 'consultation.add_patientqueuemodel'
    form_class = PatientQueueForm
    template_name = 'consultation/queue/add_patient.html'
    success_message = 'Patient Successfully Added to Queue'

    def get_success_url(self):
        return reverse('patient_queue_list')

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
    permission_required = 'consultation.view_patientqueuemodel'
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


class VitalsQueueListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """Queue for nurses to take vitals"""
    model = PatientQueueModel
    permission_required = 'consultation.view_patientqueuemodel'
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
@permission_required('consultation.change_patientqueuemodel')
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
    permission_required = 'consultation.view_patientqueuemodel'
    template_name = 'consultation/doctor/queue.html'
    context_object_name = "queue_list"

    def get_queryset(self):
        today = date.today()
        # Get consultant profile for current user if they are a doctor
        try:
            consultant = ConsultantModel.objects.get(staff__user=self.request.user)
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
            consultant = ConsultantModel.objects.get(staff__user=self.request.user)
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
            consultant = ConsultantModel.objects.get(staff__user=self.request.user)
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
@permission_required('consultation.change_patientqueuemodel')
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
@permission_required('consultation.change_patientqueuemodel')
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
@permission_required('consultation.change_patientqueuemodel')
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
    permission_required = 'consultation.change_consultationsessionmodel'
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
@permission_required('consultation.change_consultationsessionmodel')
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

        session.complete_session()
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
                Q(queue_entry__patient__patient_id__icontains=patient_search)
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
    permission_required = 'consultation.view_consultationsessionmodel'
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
    permission_required = 'consultation.add_doctorschedulemodel'
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
    permission_required = 'consultation.view_doctorschedulemodel'
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
    permission_required = 'consultation.change_doctorschedulemodel'
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
    permission_required = 'consultation.view_patientqueuemodel'

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
            'revenue': ConsultationPaymentModel.objects.filter(
                created_at__date=today,
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
                'revenue': ConsultationPaymentModel.objects.filter(
                    created_at__date=today, status='paid'
                ).aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
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
            'today': ConsultationPaymentModel.objects.filter(
                created_at__date=today, status='paid'
            ).aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0,
            'this_week': ConsultationPaymentModel.objects.filter(
                created_at__date__gte=week_start, status='paid'
            ).aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0,
            'this_month': ConsultationPaymentModel.objects.filter(
                created_at__date__gte=month_start, status='paid'
            ).aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0,
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
        return ConsultationPaymentModel.objects.filter(
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
            queryset = ConsultationPaymentModel.objects.filter(
                created_at__date__range=[date_from, date_to],
                status='paid'
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

                revenue = ConsultationPaymentModel.objects.filter(
                    fee_structure__specialization=cons.specialization,
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

                revenue = ConsultationPaymentModel.objects.filter(
                    created_at__date=current_date,
                    status='paid'
                )

                if specialization:
                    revenue = revenue.filter(fee_structure__specialization_id=specialization)

                daily_stats.append({
                    'date': current_date,
                    'consultations': consultations.count(),
                    'revenue': revenue.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0,
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
@permission_required('consultation.view_patientqueuemodel')
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
@permission_required('consultation.view_consultationpaymentmodel')
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
        payments = ConsultationPaymentModel.objects.filter(
            created_at__date__range=[date_from, date_to]
        ).select_related(
            'patient',
            'fee_structure__specialization',
            'processed_by'
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
                return redirect('patient_queue_list')

            # Check if consultation can be cancelled
            if queue_entry.status == 'consultation_completed':
                messages.error(request, 'Cannot cancel completed consultation')
                return redirect('patient_queue_list')

            queue_entry.status = 'cancelled'
            queue_entry.save()

            messages.success(request, f'Queue entry cancelled for {queue_entry.patient}')

        except Exception as e:
            messages.error(request, f'Error cancelling queue entry: {str(e)}')

    return redirect('patient_queue_list')


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