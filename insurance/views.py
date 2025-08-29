import logging
import json
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum, Count, Q, Avg
from django.db.models.functions import Lower
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import get_template
from django.urls import reverse
from django.utils import timezone
from django.views.generic import (
    CreateView, ListView, UpdateView, DeleteView, DetailView, TemplateView
)

from human_resource.views import FlashFormErrorsMixin
from insurance.forms import *
from insurance.models import *

logger = logging.getLogger(__name__)


# -------------------------
# Utility Mixins
# -------------------------



# -------------------------
# Insurance Dashboard
# -------------------------
class InsuranceDashboardView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    permission_required = 'insurance.view_patientinsurancemodel'
    template_name = 'insurance/dashboard/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        try:
            # Basic counts
            total_providers = InsuranceProviderModel.objects.filter(status='active').count()
            total_hmos = HMOModel.objects.count()
            total_coverage_plans = HMOCoveragePlanModel.objects.filter(is_active=True).count()
            total_active_patients = PatientInsuranceModel.objects.filter(is_active=True).count()

            # Claims statistics
            current_month = timezone.now().replace(day=1)
            claims_this_month = InsuranceClaimModel.objects.filter(
                claim_date__gte=current_month
            )

            claims_stats = {
                'total_claims': InsuranceClaimModel.objects.count(),
                'pending_claims': InsuranceClaimModel.objects.filter(status='pending').count(),
                'approved_claims': InsuranceClaimModel.objects.filter(status='approved').count(),
                'claims_this_month': claims_this_month.count(),
                'total_claim_amount': InsuranceClaimModel.objects.aggregate(
                    total=Sum('total_amount')
                )['total'] or Decimal('0'),
                'total_covered_amount': InsuranceClaimModel.objects.aggregate(
                    total=Sum('covered_amount')
                )['total'] or Decimal('0'),
            }

            # Verification statistics
            verification_stats = {
                'pending_verification': PatientInsuranceModel.objects.filter(
                    is_verified=False, is_active=True
                ).count(),
                'verified_today': PatientInsuranceModel.objects.filter(
                    verification_date__date=timezone.now().date()
                ).count(),
            }

            # Top HMOs by patient count
            top_hmos = HMOModel.objects.annotate(
                patient_count=Count('patientinsurancemodel', filter=Q(patientinsurancemodel__is_active=True))
            ).order_by('-patient_count')[:5]

            # Recent activity
            recent_claims = InsuranceClaimModel.objects.select_related(
                'patient_insurance__patient', 'patient_insurance__hmo'
            ).order_by('-claim_date')[:10]

            recent_enrollments = PatientInsuranceModel.objects.select_related(
                'patient', 'hmo', 'coverage_plan'
            ).order_by('-created_at')[:10]

            context.update({
                'total_providers': total_providers,
                'total_hmos': total_hmos,
                'total_coverage_plans': total_coverage_plans,
                'total_active_patients': total_active_patients,
                'claims_stats': claims_stats,
                'verification_stats': verification_stats,
                'top_hmos': top_hmos,
                'recent_claims': recent_claims,
                'recent_enrollments': recent_enrollments,
            })

        except Exception:
            logger.exception("Error loading insurance dashboard data")
            messages.error(self.request, "Error loading dashboard data. Contact admin.")
            # Provide empty context to prevent template errors
            context.update({
                'total_providers': 0, 'total_hmos': 0, 'total_coverage_plans': 0,
                'total_active_patients': 0, 'claims_stats': {}, 'verification_stats': {},
                'top_hmos': [], 'recent_claims': [], 'recent_enrollments': [],
            })

        return context


# -------------------------
# Reports and Printable Views
# -------------------------
class PatientInsuranceSummaryView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = PatientInsuranceModel
    permission_required = 'insurance.view_patientinsurancemodel'
    template_name = 'insurance/reports/patient_summary.html'
    context_object_name = "patient_insurance"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        patient_insurance = self.object

        try:
            # Claims in the last 12 months
            year_ago = timezone.now() - timedelta(days=365)
            claims = InsuranceClaimModel.objects.filter(
                patient_insurance=patient_insurance,
                service_date__gte=year_ago
            ).order_by('-service_date')

            # Monthly breakdown
            monthly_stats = []
            for i in range(12):
                month_start = timezone.now().replace(day=1) - timedelta(days=30 * i)
                month_end = month_start + timedelta(days=30)

                month_claims = claims.filter(
                    service_date__gte=month_start,
                    service_date__lt=month_end
                )

                month_stats = month_claims.aggregate(
                    count=Count('id'),
                    total=Sum('total_amount') or Decimal('0'),
                    covered=Sum('covered_amount') or Decimal('0')
                )

                monthly_stats.append({
                    'month': month_start.strftime('%B %Y'),
                    'claims_count': month_stats['count'],
                    'total_amount': month_stats['total'],
                    'covered_amount': month_stats['covered'],
                })

            # Service utilization
            service_utilization = claims.values('claim_type').annotate(
                count=Count('id'),
                total_amount=Sum('total_amount')
            ).order_by('-count')

            context.update({
                'claims': claims,
                'monthly_stats': monthly_stats,
                'service_utilization': service_utilization,
                'generated_at': timezone.now(),
            })

        except Exception:
            logger.exception("Error generating patient insurance summary")
            messages.error(self.request, "Error generating summary. Contact admin.")

        return context


class InsuranceReportView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    permission_required = 'insurance.view_insuranceclaimmodel'
    template_name = 'insurance/reports/general_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Date filters
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        hmo_id = self.request.GET.get('hmo')

        # Default to last 30 days if no dates provided
        if not start_date:
            start_date = (timezone.now() - timedelta(days=30)).date()
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()

        if not end_date:
            end_date = timezone.now().date()
        else:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

        try:
            # Filter claims
            claims_qs = InsuranceClaimModel.objects.filter(
                service_date__date__gte=start_date,
                service_date__date__lte=end_date
            )

            if hmo_id:
                claims_qs = claims_qs.filter(patient_insurance__hmo_id=hmo_id)

            # Summary statistics
            summary = claims_qs.aggregate(
                total_claims=Count('id'),
                total_amount=Sum('total_amount') or Decimal('0'),
                covered_amount=Sum('covered_amount') or Decimal('0'),
                patient_amount=Sum('patient_amount') or Decimal('0'),
                avg_claim_amount=Avg('total_amount') or Decimal('0')
            )

            # Status breakdown
            status_breakdown = claims_qs.values('status').annotate(
                count=Count('id'),
                amount=Sum('total_amount')
            ).order_by('status')

            # Service type breakdown
            service_breakdown = claims_qs.values('claim_type').annotate(
                count=Count('id'),
                amount=Sum('total_amount')
            ).order_by('-amount')

            # HMO breakdown
            hmo_breakdown = claims_qs.values(
                'patient_insurance__hmo__name'
            ).annotate(
                count=Count('id'),
                amount=Sum('total_amount')
            ).order_by('-amount')

            # Daily trends (last 30 days)
            daily_trends = []
            for i in range(30):
                day = end_date - timedelta(days=i)
                day_claims = claims_qs.filter(service_date__date=day)
                day_stats = day_claims.aggregate(
                    count=Count('id'),
                    amount=Sum('total_amount') or Decimal('0')
                )
                daily_trends.append({
                    'date': day,
                    'claims_count': day_stats['count'],
                    'total_amount': day_stats['amount']
                })
            daily_trends.reverse()

            context.update({
                'start_date': start_date,
                'end_date': end_date,
                'selected_hmo': hmo_id,
                'hmo_list': HMOModel.objects.all().order_by('name'),
                'summary': summary,
                'status_breakdown': status_breakdown,
                'service_breakdown': service_breakdown,
                'hmo_breakdown': hmo_breakdown,
                'daily_trends': daily_trends,
                'claims': claims_qs.select_related(
                    'patient_insurance__patient',
                    'patient_insurance__hmo'
                ).order_by('-service_date')[:50]  # Latest 50 for display
            })

        except Exception:
            logger.exception("Error generating insurance report")
            messages.error(self.request, "Error generating report. Contact admin.")

        return context


# -------------------------
# Printable Views
# -------------------------
class PrintPatientInsuranceSummaryView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = PatientInsuranceModel
    permission_required = 'insurance.view_patientinsurancemodel'
    template_name = 'insurance/reports/print_patient_summary.html'
    context_object_name = "patient_insurance"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        patient_insurance = self.object

        try:
            # Get claims for this insurance
            claims = InsuranceClaimModel.objects.filter(
                patient_insurance=patient_insurance
            ).order_by('-service_date')

            # Summary statistics
            claims_summary = claims.aggregate(
                total_claims=Count('id'),
                total_amount=Sum('total_amount') or Decimal('0'),
                covered_amount=Sum('covered_amount') or Decimal('0'),
                patient_amount=Sum('patient_amount') or Decimal('0')
            )

            # Coverage details
            coverage_plan = patient_insurance.coverage_plan
            coverage_details = {
                'consultation_coverage': f"{coverage_plan.consultation_coverage_percentage}%" if coverage_plan.consultation_covered else "Not Covered",
                'drug_coverage': f"{coverage_plan.drug_coverage_percentage}% ({coverage_plan.get_drug_coverage_display()})",
                'lab_coverage': f"{coverage_plan.lab_coverage_percentage}% ({coverage_plan.get_lab_coverage_display()})",
                'radiology_coverage': f"{coverage_plan.radiology_coverage_percentage}% ({coverage_plan.get_radiology_coverage_display()})",
            }

            context.update({
                'claims': claims,
                'claims_summary': claims_summary,
                'coverage_details': coverage_details,
                'print_date': timezone.now(),
            })

        except Exception:
            logger.exception("Error generating printable summary")
            context.update({
                'claims': [],
                'claims_summary': {},
                'coverage_details': {},
                'print_date': timezone.now(),
            })

        return context


class PrintInsuranceReportView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    permission_required = 'insurance.view_insuranceclaimmodel'
    template_name = 'insurance/reports/print_general_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get same data as regular report view
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        hmo_id = self.request.GET.get('hmo')

        if not start_date:
            start_date = (timezone.now() - timedelta(days=30)).date()
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()

        if not end_date:
            end_date = timezone.now().date()
        else:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

        try:
            claims_qs = InsuranceClaimModel.objects.filter(
                service_date__date__gte=start_date,
                service_date__date__lte=end_date
            )

            if hmo_id:
                claims_qs = claims_qs.filter(patient_insurance__hmo_id=hmo_id)
                selected_hmo = HMOModel.objects.get(id=hmo_id)
            else:
                selected_hmo = None

            summary = claims_qs.aggregate(
                total_claims=Count('id'),
                total_amount=Sum('total_amount') or Decimal('0'),
                covered_amount=Sum('covered_amount') or Decimal('0'),
                patient_amount=Sum('patient_amount') or Decimal('0')
            )

            status_breakdown = claims_qs.values('status').annotate(
                count=Count('id'),
                amount=Sum('total_amount')
            ).order_by('status')

            service_breakdown = claims_qs.values('claim_type').annotate(
                count=Count('id'),
                amount=Sum('total_amount')
            ).order_by('-amount')

            context.update({
                'start_date': start_date,
                'end_date': end_date,
                'selected_hmo': selected_hmo,
                'summary': summary,
                'status_breakdown': status_breakdown,
                'service_breakdown': service_breakdown,
                'print_date': timezone.now(),
            })

        except Exception:
            logger.exception("Error generating printable report")
            messages.error(self.request, "Error generating printable report.")

        return context


# -------------------------
# AJAX Helper Views
# -------------------------
@login_required
def get_coverage_plans(request):
    """Get coverage plans for a selected HMO"""
    hmo_id = request.GET.get('hmo_id')
    if not hmo_id:
        return JsonResponse({'error': 'HMO ID is required'}, status=400)

    try:
        plans = HMOCoveragePlanModel.objects.filter(
            hmo_id=hmo_id, is_active=True
        ).values('id', 'name', 'require_verification', 'require_referral')
        return JsonResponse({'plans': list(plans)})
    except Exception:
        logger.exception("Failed fetching coverage plans for HMO id=%s", hmo_id)
        return JsonResponse({'error': 'Internal error'}, status=500)


@login_required
@permission_required('insurance.view_patientinsurancemodel', raise_exception=True)
def patient_insurance_status(request, patient_id):
    """Check if patient has active insurance"""
    try:
        from patient.models import PatientModel
        patient = get_object_or_404(PatientModel, pk=patient_id)

        active_insurance = PatientInsuranceModel.objects.filter(
            patient=patient, is_active=True
        ).select_related('hmo', 'coverage_plan').first()

        if active_insurance:
            return JsonResponse({
                'has_insurance': True,
                'hmo_name': active_insurance.hmo.name,
                'plan_name': active_insurance.coverage_plan.name,
                'policy_number': active_insurance.policy_number,
                'is_valid': active_insurance.is_valid,
                'is_verified': active_insurance.is_verified,
            })
        else:
            return JsonResponse({'has_insurance': False})

    except Exception:
        logger.exception("Error checking patient insurance status")
        return JsonResponse({'error': 'Failed to check insurance status'}, status=500)


# -------------------------
# Bulk Actions
# -------------------------
def multi_provider_action(request):
    """Handle bulk actions on insurance providers"""
    if request.method == 'POST':
        provider_ids = request.POST.getlist('provider')
        action = request.POST.get('action')

        if not provider_ids:
            messages.error(request, 'No provider selected.')
            return redirect(reverse('insurance_provider_index'))

        try:
            with transaction.atomic():
                providers = InsuranceProviderModel.objects.filter(id__in=provider_ids)
                if action == 'delete':
                    count, _ = providers.delete()
                    messages.success(request, f'Successfully deleted {count} provider(s).')
                elif action == 'activate':
                    count = providers.update(status='active')
                    messages.success(request, f'Successfully activated {count} provider(s).')
                elif action == 'deactivate':
                    count = providers.update(status='inactive')
                    messages.success(request, f'Successfully deactivated {count} provider(s).')
                else:
                    messages.error(request, 'Invalid action.')
        except Exception:
            logger.exception("Bulk provider action failed")
            messages.error(request, "An error occurred. Contact admin.")
        return redirect(reverse('insurance_provider_index'))

    # GET - confirm action
    provider_ids = request.GET.getlist('provider')
    if not provider_ids:
        messages.error(request, 'No provider selected.')
        return redirect(reverse('insurance_provider_index'))

    action = request.GET.get('action')
    context = {
        'provider_list': InsuranceProviderModel.objects.filter(id__in=provider_ids),
        'action': action
    }

    if action in ['delete', 'activate', 'deactivate']:
        return render(request, 'insurance/provider/multi_action.html', context)

    messages.error(request, 'Invalid action.')
    return redirect(reverse('insurance_provider_index'))


# -------------------------
# Verification Views
# -------------------------
class PendingVerificationListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = PatientInsuranceModel
    permission_required = 'insurance.change_patientinsurancemodel'
    template_name = 'insurance/verification/pending_list.html'
    context_object_name = "pending_list"

    def get_queryset(self):
        return PatientInsuranceModel.objects.filter(
            is_verified=False, is_active=True
        ).select_related('patient', 'hmo', 'coverage_plan').order_by('created_at')


@login_required
@permission_required('insurance.change_patientinsurancemodel', raise_exception=True)
def bulk_verify_insurance(request):
    """Bulk verify multiple patient insurances"""
    if request.method == 'POST':
        insurance_ids = request.POST.getlist('insurance')

        if not insurance_ids:
            messages.error(request, 'No insurance policies selected.')
            return redirect(reverse('pending_verification_list'))

        try:
            with transaction.atomic():
                updated = PatientInsuranceModel.objects.filter(
                    id__in=insurance_ids,
                    is_verified=False
                ).update(
                    is_verified=True,
                    verification_date=timezone.now(),
                    verified_by=request.user
                )

                messages.success(request, f'Successfully verified {updated} insurance policies.')
        except Exception:
            logger.exception("Bulk verification failed")
            messages.error(request, "An error occurred during bulk verification. Contact admin.")

        return redirect(reverse('pending_verification_list'))

    # GET - show confirmation
    insurance_ids = request.GET.getlist('insurance')
    if not insurance_ids:
        messages.error(request, 'No insurance policies selected.')
        return redirect(reverse('pending_verification_list'))

    context = {
        'insurance_list': PatientInsuranceModel.objects.filter(id__in=insurance_ids),
    }
    return render(request, 'insurance/verification/bulk_verify.html', context)


# -------------------------
# Patient Insurance Management
# -------------------------
@login_required
@permission_required('insurance.change_patientinsurancemodel', raise_exception=True)
def deactivate_patient_insurance(request, pk):
    """Deactivate patient insurance (for switching plans)"""
    insurance = get_object_or_404(PatientInsuranceModel, pk=pk)

    try:
        if not insurance.is_active:
            messages.info(request, "Insurance is already inactive.")
        else:
            insurance.is_active = False
            insurance.save(update_fields=['is_active'])
            messages.success(request, f"Insurance for {insurance.patient} has been deactivated.")
    except Exception:
        logger.exception("Error deactivating insurance id=%s", pk)
        messages.error(request, "An error occurred while deactivating insurance. Contact admin.")

    return redirect(reverse('patient_insurance_detail', kwargs={'pk': pk}))


@login_required
@permission_required('insurance.change_patientinsurancemodel', raise_exception=True)
def reactivate_patient_insurance(request, pk):
    """Reactivate patient insurance"""
    insurance = get_object_or_404(PatientInsuranceModel, pk=pk)

    try:
        # Check if patient already has active insurance
        existing = PatientInsuranceModel.objects.filter(
            patient=insurance.patient,
            is_active=True
        ).exclude(pk=pk)

        if existing.exists():
            messages.error(request, f"{insurance.patient} already has an active insurance policy.")
            return redirect(reverse('patient_insurance_detail', kwargs={'pk': pk}))

        insurance.is_active = True
        insurance.save(update_fields=['is_active'])
        messages.success(request, f"Insurance for {insurance.patient} has been reactivated.")

    except Exception:
        logger.exception("Error reactivating insurance id=%s", pk)
        messages.error(request, "An error occurred while reactivating insurance. Contact admin.")

    return redirect(reverse('patient_insurance_detail', kwargs={'pk': pk}))



# -------------------------
# Insurance Provider Views
# -------------------------
class InsuranceProviderCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, CreateView
):
    model = InsuranceProviderModel
    permission_required = 'insurance.add_insuranceprovidermodel'
    form_class = InsuranceProviderForm
    template_name = 'insurance/provider/index.html'
    success_message = 'Insurance Provider Successfully Created'

    def get_success_url(self):
        return reverse('insurance_provider_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('insurance_provider_index'))
        return super().dispatch(request, *args, **kwargs)


class InsuranceProviderDetailView(DetailView):
    model = InsuranceProviderModel
    template_name = "insurance/provider/detail.html"
    context_object_name = "provider"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        provider = self.get_object()
        # All HMOs linked to this provider
        context["hmo_list"] = HMOModel.objects.filter(insurance_provider=provider)
        return context


class InsuranceProviderListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = InsuranceProviderModel
    permission_required = 'insurance.view_insuranceprovidermodel'
    template_name = 'insurance/provider/index.html'
    context_object_name = "provider_list"

    def get_queryset(self):
        return InsuranceProviderModel.objects.all().order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = InsuranceProviderForm()
        return context


class InsuranceProviderUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
):
    model = InsuranceProviderModel
    permission_required = 'insurance.change_insuranceprovidermodel'
    form_class = InsuranceProviderForm
    template_name = 'insurance/provider/index.html'
    success_message = 'Insurance Provider Successfully Updated'

    def get_success_url(self):
        return reverse('insurance_provider_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('insurance_provider_index'))
        return super().dispatch(request, *args, **kwargs)


class InsuranceProviderDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = InsuranceProviderModel
    permission_required = 'insurance.delete_insuranceprovidermodel'
    template_name = 'insurance/provider/delete.html'
    context_object_name = "provider"
    success_message = 'Insurance Provider Successfully Deleted'

    def get_success_url(self):
        return reverse('insurance_provider_index')


# -------------------------
# HMO Views
# -------------------------
class HMOCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, CreateView
):
    model = HMOModel
    permission_required = 'insurance.add_hmomodel'
    form_class = HMOForm
    template_name = 'insurance/hmo/index.html'
    success_message = 'HMO Successfully Created'

    def get_success_url(self):
        return reverse('hmo_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('hmo_index'))
        return super().dispatch(request, *args, **kwargs)


class HMOListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = HMOModel
    permission_required = 'insurance.view_hmomodel'
    template_name = 'insurance/hmo/index.html'
    context_object_name = "hmo_list"

    def get_queryset(self):
        return HMOModel.objects.select_related('insurance_provider').order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = HMOForm()
        context['providers'] = InsuranceProviderModel.objects.filter(status='active').order_by('name')
        return context


class HMOUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
):
    model = HMOModel
    permission_required = 'insurance.change_hmomodel'
    form_class = HMOForm
    template_name = 'insurance/hmo/index.html'
    success_message = 'HMO Successfully Updated'

    def get_success_url(self):
        return reverse('hmo_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('hmo_index'))
        return super().dispatch(request, *args, **kwargs)


class HMODetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = HMOModel
    permission_required = 'insurance.view_hmomodel'
    template_name = 'insurance/hmo/detail.html'
    context_object_name = "hmo"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        hmo = self.object

        context.update({
            'coverage_plans': hmo.coverage_plans.filter(is_active=True).order_by('name'),
            'total_patients': PatientInsuranceModel.objects.filter(hmo=hmo, is_active=True).count(),
            'total_claims': InsuranceClaimModel.objects.filter(patient_insurance__hmo=hmo).count(),
            'providers':  InsuranceProviderModel.objects.filter(status='active').order_by('name')
        })
        return context


class HMODeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = HMOModel
    permission_required = 'insurance.delete_hmomodel'
    template_name = 'insurance/hmo/delete.html'
    context_object_name = "hmo"
    success_message = 'HMO Successfully Deleted'

    def get_success_url(self):
        return reverse('hmo_index')


# -------------------------
# HMO Coverage Plan Views
# -------------------------
class HMOCoveragePlanCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, CreateView
):
    model = HMOCoveragePlanModel
    permission_required = 'insurance.add_hmocoverageplanmodel'
    form_class = HMOCoveragePlanForm
    template_name = 'insurance/coverage_plan/create.html'
    success_message = 'Coverage Plan Successfully Created'

    def get_success_url(self):
        return reverse('coverage_plan_detail', kwargs={'pk': self.object.pk})

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Exclude ManyToMany fields from create form
        exclude_fields = ['selected_drugs', 'selected_lab_tests', 'selected_radiology']
        for field_name in exclude_fields:
            if field_name in form.fields:
                del form.fields[field_name]
        return form


class HMOCoveragePlanListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = HMOCoveragePlanModel
    permission_required = 'insurance.view_hmocoverageplanmodel'
    template_name = 'insurance/coverage_plan/index.html'
    context_object_name = "coverage_plans"

    def get_queryset(self):
        return HMOCoveragePlanModel.objects.select_related('hmo').order_by('hmo__name', 'name')


class HMOCoveragePlanDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = HMOCoveragePlanModel
    permission_required = 'insurance.view_hmocoverageplanmodel'
    template_name = 'insurance/coverage_plan/detail.html'
    context_object_name = "plan"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        plan = self.object

        # Only show ManyToMany management if coverage is not 'all'
        context.update({
            'show_drug_management': plan.drug_coverage != 'all',
            'show_lab_management': plan.lab_coverage != 'all',
            'show_radiology_management': plan.radiology_coverage != 'all',
            'enrolled_patients_count': PatientInsuranceModel.objects.filter(coverage_plan=plan, is_active=True).count(),
        })
        return context


class HMOCoveragePlanUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
):
    model = HMOCoveragePlanModel
    permission_required = 'insurance.change_hmocoverageplanmodel'
    form_class = HMOCoveragePlanForm
    template_name = 'insurance/coverage_plan/update.html'
    success_message = 'Coverage Plan Successfully Updated'

    def get_success_url(self):
        return reverse('coverage_plan_detail', kwargs={'pk': self.object.pk})

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Exclude ManyToMany fields from update form - managed via detail page
        exclude_fields = ['selected_drugs', 'selected_lab_tests', 'selected_radiology']
        for field_name in exclude_fields:
            if field_name in form.fields:
                del form.fields[field_name]
        return form


class HMOCoveragePlanDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = HMOCoveragePlanModel
    permission_required = 'insurance.delete_hmocoverageplanmodel'
    template_name = 'insurance/coverage_plan/delete.html'
    context_object_name = "plan"
    success_message = 'Coverage Plan Successfully Deleted'

    def get_success_url(self):
        return reverse('coverage_plan_index')


# -------------------------
# Coverage Plan Service Management (AJAX)
# -------------------------
@login_required
@permission_required('insurance.change_hmocoverageplanmodel', raise_exception=True)
def add_drug_to_plan(request, pk):
    """
    Adds a selected drug to an HMO coverage plan.
    Requires POST method with 'drug_id'.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    plan = get_object_or_404(HMOCoveragePlanModel, pk=pk)
    drug_id = request.POST.get('drug_id')

    if not drug_id:
        return JsonResponse({'error': 'Drug ID is required'}, status=400)

    try:
        from pharmacy.models import DrugModel
        drug = get_object_or_404(DrugModel, pk=drug_id)

        # Construct a display name for the drug
        # Prioritize brand_name if available, otherwise use the formulation's string representation
        drug_display_name = drug.brand_name if drug.brand_name else str(drug.formulation)

        if plan.selected_drugs.filter(id=drug.id).exists():
            return JsonResponse({'error': f'{drug_display_name} is already in the plan'}, status=400)

        plan.selected_drugs.add(drug)
        return JsonResponse({
            'success': True,
            'message': f'{drug_display_name} added to coverage plan',
            'drug': {'id': drug.id, 'name': drug_display_name} # Use the constructed display name here
        })
    except Exception as e:
        # It's good practice to log the full exception details for debugging
        import logging
        logger = logging.getLogger(__name__) # Ensure logger is imported or defined
        logger.exception("Error adding drug to coverage plan")
        return JsonResponse({'error': 'Failed to add drug'}, status=500)

@login_required
@permission_required('insurance.change_hmocoverageplanmodel', raise_exception=True)
def remove_drug_from_plan(request, pk, drug_id):
    """
    Removes a drug from an HMO coverage plan.
    Requires POST method.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    plan = get_object_or_404(HMOCoveragePlanModel, pk=pk)

    try:
        from pharmacy.models import DrugModel
        drug = get_object_or_404(DrugModel, pk=drug_id)

        # Construct a display name for the drug, similar to add_drug_to_plan
        # Prioritize brand_name if available, otherwise use the formulation's string representation
        drug_display_name = drug.brand_name if drug.brand_name else str(drug.formulation)

        plan.selected_drugs.remove(drug)
        return JsonResponse({
            'success': True,
            'message': f'{drug_display_name} removed from coverage plan' # Use the constructed display name here
        })
    except Exception as e:
        # Ensure logger is imported or defined
        import logging
        logger = logging.getLogger(__name__)
        logger.exception("Error removing drug from coverage plan")
        return JsonResponse({'error': 'Failed to remove drug'}, status=500)


@login_required
@permission_required('insurance.change_hmocoverageplanmodel', raise_exception=True)
def add_lab_to_plan(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    plan = get_object_or_404(HMOCoveragePlanModel, pk=pk)
    lab_id = request.POST.get('lab_id')

    if not lab_id:
        return JsonResponse({'error': 'Lab test ID is required'}, status=400)

    try:
        from laboratory.models import LabTestTemplateModel
        lab_test = get_object_or_404(LabTestTemplateModel, pk=lab_id)

        if plan.selected_lab_tests.filter(id=lab_test.id).exists():
            return JsonResponse({'error': f'{lab_test.name} is already in the plan'}, status=400)

        plan.selected_lab_tests.add(lab_test)
        return JsonResponse({
            'success': True,
            'message': f'{lab_test.name} added to coverage plan',
            'lab_test': {'id': lab_test.id, 'name': lab_test.name}
        })
    except Exception as e:
        logger.exception("Error adding lab test to coverage plan")
        return JsonResponse({'error': 'Failed to add lab test'}, status=500)


@login_required
@permission_required('insurance.change_hmocoverageplanmodel', raise_exception=True)
def remove_lab_from_plan(request, pk, lab_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    plan = get_object_or_404(HMOCoveragePlanModel, pk=pk)

    try:
        from laboratory.models import LabTestTemplateModel
        lab_test = get_object_or_404(LabTestTemplateModel, pk=lab_id)
        plan.selected_lab_tests.remove(lab_test)
        return JsonResponse({
            'success': True,
            'message': f'{lab_test.name} removed from coverage plan'
        })
    except Exception as e:
        logger.exception("Error removing lab test from coverage plan")
        return JsonResponse({'error': 'Failed to remove lab test'}, status=500)


@login_required
@permission_required('insurance.change_hmocoverageplanmodel', raise_exception=True)
def add_radiology_to_plan(request, pk):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    plan = get_object_or_404(HMOCoveragePlanModel, pk=pk)
    scan_id = request.POST.get('scan_id')

    if not scan_id:
        return JsonResponse({'error': 'Scan ID is required'}, status=400)

    try:
        from scan.models import ScanTemplateModel
        scan = get_object_or_404(ScanTemplateModel, pk=scan_id)

        if plan.selected_radiology.filter(id=scan.id).exists():
            return JsonResponse({'error': f'{scan.name} is already in the plan'}, status=400)

        plan.selected_radiology.add(scan)
        return JsonResponse({
            'success': True,
            'message': f'{scan.name} added to coverage plan',
            'scan': {'id': scan.id, 'name': scan.name}
        })
    except Exception as e:
        logger.exception("Error adding scan to coverage plan")
        return JsonResponse({'error': 'Failed to add scan'}, status=500)


@login_required
@permission_required('insurance.change_hmocoverageplanmodel', raise_exception=True)
def remove_radiology_from_plan(request, pk, scan_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    plan = get_object_or_404(HMOCoveragePlanModel, pk=pk)

    try:
        from scan.models import ScanTemplateModel
        scan = get_object_or_404(ScanTemplateModel, pk=scan_id)
        plan.selected_radiology.remove(scan)
        return JsonResponse({
            'success': True,
            'message': f'{scan.name} removed from coverage plan'
        })
    except Exception as e:
        logger.exception("Error removing scan from coverage plan")
        return JsonResponse({'error': 'Failed to remove scan'}, status=500)


# Search endpoints for adding services
@login_required
def search_drugs(request):
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'results': []})

    try:
        from pharmacy.models import DrugModel
        # Fetch full model instances to access the __str__ method
        drugs_queryset = DrugModel.objects.filter(
            Q(brand_name__icontains=query) | Q(formulation__generic_drug__generic_name__icontains=query)
        )[:20]

        # Manually build the results list with the string representation
        results = [
            {
                'id': drug.id,
                'name': str(drug)  # This will use your model's __str__ output
            }
            for drug in drugs_queryset
        ]

        return JsonResponse({'results': results})

    except Exception:
        logger.exception("Error searching drugs")
        return JsonResponse({'error': 'Search failed'}, status=500)


@login_required
def search_lab_tests(request):
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'results': []})

    try:
        from laboratory.models import LabTestTemplateModel
        lab_tests = LabTestTemplateModel.objects.filter(
            name__icontains=query
        ).values('id', 'name')[:20]
        return JsonResponse({'results': list(lab_tests)})
    except Exception:
        logger.exception("Error searching lab tests")
        return JsonResponse({'error': 'Search failed'}, status=500)


@login_required
def search_scans(request):
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'results': []})

    try:
        from scan.models import ScanTemplateModel
        scans = ScanTemplateModel.objects.filter(
            name__icontains=query
        ).values('id', 'name', 'description')[:20]
        return JsonResponse({'results': list(scans)})
    except Exception:
        logger.exception("Error searching scans")
        return JsonResponse({'error': 'Search failed'}, status=500)


# -------------------------
# Patient Insurance Views
# -------------------------
class PatientInsuranceCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, CreateView
):
    model = PatientInsuranceModel
    permission_required = 'insurance.add_patientinsurancemodel'
    form_class = PatientInsuranceForm
    template_name = 'insurance/patient_insurance/create.html'
    success_message = 'Patient Insurance Successfully Created'

    def get_success_url(self):
        return reverse('patient_insurance_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Assuming you pass patients and hmos to the template
        # You'll need to import PatientModel and HMOModel
        from patient.models import PatientModel
        from .models import HMOModel # Assuming HMOModel is in the same app or imported correctly
        context['patients'] = PatientModel.objects.all()
        context['hmos'] = HMOModel.objects.all()
        # If you want to pass system_users for 'verified_by_user' (currently commented out in HTML)
        # from django.contrib.auth import get_user_model
        # User = get_user_model()
        # context['system_users'] = User.objects.all()
        return context


    def form_valid(self, form):
        try:
            with transaction.atomic():
                # Check for existing active insurance for this patient
                existing = PatientInsuranceModel.objects.filter(
                    patient=form.instance.patient,
                    is_active=True
                ).exclude(pk=getattr(self.object, 'pk', None)) # .exclude is fine here, though not strictly needed for CreateView

                if existing.exists():
                    messages.error(self.request,
                                   "Patient already has an active insurance. Please deactivate existing insurance first.")
                    # Return to the form with errors or a different relevant page
                    # Redirecting to success_url on error for creation is usually not ideal UX
                    return self.form_invalid(form) # Re-render form with error
                    # OR if you prefer to redirect away:
                    # return redirect(reverse('patient_insurance_list'))


                # Check uniqueness of enrollee_id within coverage plan
                if form.instance.enrollee_id:
                    existing_enrollee = PatientInsuranceModel.objects.filter(
                        coverage_plan=form.instance.coverage_plan,
                        enrollee_id=form.instance.enrollee_id
                    ).exclude(pk=getattr(self.object, 'pk', None)) # .exclude is fine here

                    if existing_enrollee.exists():
                        messages.error(self.request,
                                       f"Enrollee ID '{form.instance.enrollee_id}' already exists for this coverage plan.")
                        return self.form_invalid(form) # Re-render form with error
                        # OR if you prefer to redirect away:
                        # return redirect(reverse('patient_insurance_list'))


                # Assign the creator
                form.instance.created_by = self.request.user

                # Handle verification requirements based on plan and user input
                coverage_plan = form.instance.coverage_plan
                if coverage_plan.require_verification:
                    # If the plan requires verification, respect the attendant's checkbox selection
                    # The 'is_verified' field from the form should be processed here.
                    # If the checkbox was checked, form.cleaned_data['is_verified'] will be True
                    # If unchecked, it will be False or absent depending on the form field definition
                    if form.cleaned_data.get('is_verified'):
                        form.instance.is_verified = True
                        form.instance.verification_date = timezone.now()
                        form.instance.verified_by = self.request.user
                        messages.success(self.request, "Insurance created and verified as required by the plan.")
                    else:
                        form.instance.is_verified = False
                        form.instance.verification_date = None
                        form.instance.verified_by = None
                        messages.info(self.request, "Insurance created but requires verification before activation.")
                else:
                    # If the plan does NOT require verification, force 'is_verified' to False (unverified)
                    # as per your requirement "if not, the insurance will be created but not verified."
                    form.instance.is_verified = False
                    form.instance.verification_date = None
                    form.instance.verified_by = None
                    messages.info(self.request, "Insurance created. Verification is not required for this plan and it is unverified.")


                return super().form_valid(form)
        except Exception:
            logger.exception("Error creating patient insurance")
            messages.error(self.request, "An error occurred while creating patient insurance. Contact admin.")
            return redirect(reverse('patient_insurance_list'))


@login_required
@permission_required('insurance.view_hmocoverageplanmodel', raise_exception=True)
def get_hmo_coverage_plans_api(request, hmo_id):
    """
    API endpoint to fetch coverage plans for a specific HMO.
    Returns a JSON response with a list of plan IDs and names.
    """
    try:
        hmo = get_object_or_404(HMOModel, pk=hmo_id)
        # Fetch only active plans for the selected HMO
        coverage_plans = HMOCoveragePlanModel.objects.filter(hmo=hmo, is_active=True).order_by('name')

        plans_data = [
            {
                'id': plan.id,
                'name': plan.name,
                # Optionally, if needed for client-side logic, you can include other fields
                # 'require_verification': plan.require_verification
            }
            for plan in coverage_plans
        ]
        return JsonResponse({'plans': plans_data})
    except Exception as e:
        # Log the exception for debugging purposes
        import logging
        logger = logging.getLogger(__name__)
        logger.exception(f"Error fetching coverage plans for HMO ID {hmo_id}")
        return JsonResponse({'error': 'Failed to retrieve coverage plans.'}, status=500)


@login_required
@permission_required('insurance.view_hmocoverageplanmodel', raise_exception=True)
def get_coverage_plan_details_api(request, plan_id):
    """
    API endpoint to fetch details for a specific coverage plan,
    primarily for its 'require_verification' status.
    """
    try:
        plan = get_object_or_404(HMOCoveragePlanModel, pk=plan_id)
        plan_details = {
            'id': plan.id,
            'name': plan.name,
            'require_verification': plan.require_verification,
            # Add any other details the frontend might need instantly
        }
        return JsonResponse(plan_details)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.exception(f"Error fetching details for Coverage Plan ID {plan_id}")
        return JsonResponse({'error': 'Failed to retrieve coverage plan details.'}, status=500)


class PatientInsuranceListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = PatientInsuranceModel
    permission_required = 'insurance.view_patientinsurancemodel'
    template_name = 'insurance/patient_insurance/index.html'
    context_object_name = "policies" # You can keep this, but the template will primarily use 'page_obj'
    paginate_by = 10 # <-- Add this line to enable pagination (e.g., 10 items per page)

    def get_queryset(self):
        # You can add search/filter logic here based on request.GET parameters
        queryset = PatientInsuranceModel.objects.select_related(
            'patient', 'hmo', 'coverage_plan'
        ).order_by('-created_at')

        # Example of basic search (optional)
        # query = self.request.GET.get('q')
        # if query:
        #     queryset = queryset.filter(
        #         Q(patient__first_name__icontains=query) |
        #         Q(patient__last_name__icontains=query) |
        #         Q(policy_number__icontains=query) |
        #         Q(hmo__name__icontains=query)
        #     )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # When `paginate_by` is set, `super().get_context_data` already adds `page_obj` and `paginator`.
        # The objects for the current page are available via `context['page_obj'].object_list`
        # or, if `context_object_name` is set, they'll also be in `context['policies']` (the `object_list` of `page_obj`).

        context.update({
            'pending_verification_count': PatientInsuranceModel.objects.filter(
                is_verified=False, is_active=True, coverage_plan__require_verification=True # Added condition for requiring verification
            ).count()
        })
        return context


class PatientInsuranceDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = PatientInsuranceModel
    permission_required = 'insurance.view_patientinsurancemodel'
    template_name = 'insurance/patient_insurance/detail.html'
    context_object_name = "policy"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        patient_insurance = self.object

        # Recent claims for this insurance
        recent_claims = InsuranceClaimModel.objects.filter(
            patient_insurance=patient_insurance
        ).order_by('-service_date')[:10]

        # Claims summary
        claims_summary = InsuranceClaimModel.objects.filter(
            patient_insurance=patient_insurance
        ).aggregate(
            total_claims=Count('id'),
            total_amount=Sum('total_amount') or Decimal('0'),
            covered_amount=Sum('covered_amount') or Decimal('0'),
            patient_amount=Sum('patient_amount') or Decimal('0')
        )

        context.update({
            'recent_claims': recent_claims,
            'claims_summary': claims_summary,
        })
        return context


@login_required
@permission_required('insurance.change_patientinsurancemodel', raise_exception=True)
def patient_insurance_verify(request, pk):
    """
    View to handle the verification of a PatientInsuranceModel.
    Sets is_verified to True, records verification date and verifier.
    """
    if request.method != 'POST':
        messages.error(request, "Invalid request method.")
        return redirect(reverse('patient_insurance_detail', kwargs={'pk': pk}))

    policy = get_object_or_404(PatientInsuranceModel, pk=pk)

    try:
        with transaction.atomic():
            # Check if policy is already verified
            if policy.is_verified:
                messages.info(request, "This policy is already verified.")
                return redirect(reverse('patient_insurance_detail', kwargs={'pk': pk}))

            # Check if the coverage plan actually requires verification
            # This is a safeguard, as the button should only show if require_verification is True
            if not policy.coverage_plan.require_verification:
                messages.warning(request, "This policy's plan does not require verification.")
                return redirect(reverse('patient_insurance_detail', kwargs={'pk': pk}))

            policy.is_verified = True
            policy.verification_date = timezone.now()
            policy.verified_by = request.user
            policy.save()

            messages.success(request, f"Patient insurance policy {policy.policy_number} successfully verified.")
            return redirect(reverse('patient_insurance_detail', kwargs={'pk': pk}))

    except Exception as e:
        logger.exception(f"Error verifying patient insurance policy {pk}")
        messages.error(request, "An error occurred during verification. Please try again.")
        return redirect(reverse('patient_insurance_detail', kwargs={'pk': pk}))


@login_required
@permission_required('insurance.change_patientinsurancemodel', raise_exception=True)
def patient_insurance_deactivate(request, pk):
    """
    View to handle the deactivation of a PatientInsuranceModel.
    Sets is_active to False.
    """
    if request.method != 'POST':
        messages.error(request, "Invalid request method.")
        return redirect(reverse('patient_insurance_detail', kwargs={'pk': pk}))

    policy = get_object_or_404(PatientInsuranceModel, pk=pk)

    try:
        with transaction.atomic():
            # Check if policy is already inactive
            if not policy.is_active:
                messages.info(request, "This policy is already inactive.")
                return redirect(reverse('patient_insurance_detail', kwargs={'pk': pk}))

            policy.is_active = False
            policy.save()

            messages.success(request, f"Patient insurance policy {policy.policy_number} successfully deactivated.")
            return redirect(reverse('patient_insurance_detail', kwargs={'pk': pk}))

    except Exception as e:
        logger.exception(f"Error deactivating patient insurance policy {pk}")
        messages.error(request, "An error occurred during deactivation. Please try again.")
        return redirect(reverse('patient_insurance_detail', kwargs={'pk': pk}))


@login_required
@permission_required('insurance.change_patientinsurancemodel', raise_exception=True)
def patient_insurance_activate(request, pk):
    """
    View to handle the activation of a PatientInsuranceModel.
    Sets is_active to True.
    """
    if request.method != 'POST':
        messages.error(request, "Invalid request method.")
        return redirect(reverse('patient_insurance_detail', kwargs={'pk': pk}))

    policy = get_object_or_404(PatientInsuranceModel, pk=pk)

    try:
        with transaction.atomic():
            # Check if policy is already active
            if policy.is_active:
                messages.info(request, "This policy is already active.")
                return redirect(reverse('patient_insurance_detail', kwargs={'pk': pk}))

            policy.is_active = True
            policy.save()

            messages.success(request, f"Patient insurance policy {policy.policy_number} successfully activated.")
            return redirect(reverse('patient_insurance_detail', kwargs={'pk': pk}))

    except Exception as e:
        logger.exception(f"Error activating patient insurance policy {pk}")
        messages.error(request, "An error occurred during activation. Please try again.")
        return redirect(reverse('patient_insurance_detail', kwargs={'pk': pk}))


class PatientInsuranceUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
):
    model = PatientInsuranceModel
    permission_required = 'insurance.change_patientinsurancemodel'
    form_class = PatientInsuranceForm
    template_name = 'insurance/patient_insurance/edit.html'
    success_message = 'Patient Insurance Successfully Updated'
    context_object_name = "policy"

    def get_success_url(self):
        return reverse('patient_insurance_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        try:
            with transaction.atomic():
                # Same validation as create
                existing = PatientInsuranceModel.objects.filter(
                    patient=form.instance.patient,
                    is_active=True
                ).exclude(pk=self.object.pk)

                if existing.exists():
                    messages.error(self.request, "Patient already has an active insurance.")
                    return redirect(self.get_success_url())

                # Check enrollee_id uniqueness
                if form.instance.enrollee_id:
                    existing_enrollee = PatientInsuranceModel.objects.filter(
                        coverage_plan=form.instance.coverage_plan,
                        enrollee_id=form.instance.enrollee_id
                    ).exclude(pk=self.object.pk)

                    if existing_enrollee.exists():
                        messages.error(self.request,
                                       f"Enrollee ID '{form.instance.enrollee_id}' already exists for this coverage plan.")
                        return redirect(self.get_success_url())

                return super().form_valid(form)
        except Exception:
            logger.exception("Error updating patient insurance")
            messages.error(self.request, "An error occurred while updating patient insurance. Contact admin.")
            return redirect(self.get_success_url())


@login_required
@permission_required('insurance.change_patientinsurancemodel', raise_exception=True)
def verify_patient_insurance(request, pk):
    insurance = get_object_or_404(PatientInsuranceModel, pk=pk)

    try:
        if insurance.is_verified:
            messages.info(request, "Insurance is already verified.")
        else:
            insurance.is_verified = True
            insurance.verification_date = timezone.now()
            insurance.verified_by = request.user
            insurance.save(update_fields=['is_verified', 'verification_date', 'verified_by'])
            messages.success(request, f"Insurance for {insurance.patient} has been verified.")
    except Exception:
        logger.exception("Error verifying insurance id=%s", pk)
        messages.error(request, "An error occurred while verifying insurance. Contact admin.")

    return redirect(reverse('patient_insurance_detail', kwargs={'pk': pk}))


# -------------------------
# Patient Claims Views
# -------------------------
class PatientClaimsView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    permission_required = 'insurance.view_insuranceclaimmodel'
    template_name = 'insurance/claims/patient_claims.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        patient_id = self.kwargs.get('patient_id')

        # Date filters from request
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        status_filter = self.request.GET.get('status', '')

        try:
            from patient.models import PatientModel
            patient = get_object_or_404(PatientModel, pk=patient_id)

            # Get patient's insurance(s)
            patient_insurances = PatientInsuranceModel.objects.filter(patient=patient)

            # Build claims query
            claims_qs = InsuranceClaimModel.objects.filter(
                patient_insurance__patient=patient
            ).select_related('patient_insurance__hmo', 'patient_insurance__coverage_plan')

            # Apply filters
            if start_date:
                claims_qs = claims_qs.filter(service_date__gte=start_date)
            if end_date:
                claims_qs = claims_qs.filter(service_date__lte=end_date)
            if status_filter:
                claims_qs = claims_qs.filter(status=status_filter)

            claims = claims_qs.order_by('-service_date')

            # Calculate statistics
            stats = claims.aggregate(
                total_claims=Count('id'),
                total_amount=Sum('total_amount') or Decimal('0'),
                covered_amount=Sum('covered_amount') or Decimal('0'),
                patient_amount=Sum('patient_amount') or Decimal('0')
            )

            # Status breakdown
            status_breakdown = claims.values('status').annotate(count=Count('id'))

            context.update({
                'patient': patient,
                'patient_insurances': patient_insurances,
                'claims': claims,
                'stats': stats,
                'status_breakdown': status_breakdown,
                'start_date': start_date,
                'end_date': end_date,
                'status_filter': status_filter,
            })
        except Exception:
            logger.exception("Error loading patient claims for patient_id=%s", patient_id)
            messages.error(self.request, "Error loading patient claims data. Contact admin.")
            context.update({
                'patient': None,
                'claims': [],
                'stats': {'total_claims': 0, 'total_amount': 0, 'covered_amount': 0, 'patient_amount': 0},
                'status_breakdown': [],
            })

        return context


# -------------------------
# Insurance Claim Views
# -------------------------
class InsuranceClaimCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, CreateView
):
    model = InsuranceClaimModel
    permission_required = 'insurance.add_insuranceclaimmodel'
    form_class = InsuranceClaimForm
    template_name = 'insurance/claims/create.html'
    success_message = 'Insurance Claim Successfully Created'

    def get_success_url(self):
        return reverse('insurance_claim_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        try:
            with transaction.atomic():
                form.instance.created_by = self.request.user
                return super().form_valid(form)
        except Exception:
            logger.exception("Error creating insurance claim")
            messages.error(self.request, "An error occurred while creating the claim. Contact admin.")
            return redirect(reverse('insurance_claim_index'))


class InsuranceClaimListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = InsuranceClaimModel
    permission_required = 'insurance.view_insuranceclaimmodel'
    template_name = 'insurance/claims/index.html'
    context_object_name = "claim_list"
    paginate_by = 50

    def get_queryset(self):
        return InsuranceClaimModel.objects.select_related(
            'patient_insurance__patient',
            'patient_insurance__hmo',
            'patient_insurance__coverage_plan'
        ).order_by('-claim_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Summary statistics
        summary_stats = InsuranceClaimModel.objects.aggregate(
            total_claims=Count('id'),
            pending_claims=Count('id', filter=Q(status='pending')),
            approved_claims=Count('id', filter=Q(status='approved')),
            total_amount=Sum('total_amount') or Decimal('0'),
            covered_amount=Sum('covered_amount') or Decimal('0')
        )

        context.update({
            'summary_stats': summary_stats,
        })
        return context


class InsuranceClaimDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = InsuranceClaimModel
    permission_required = 'insurance.view_insuranceclaimmodel'
    template_name = 'insurance/claims/detail.html'
    context_object_name = "claim"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        claim = self.object

        # Calculate coverage percentage
        if claim.total_amount > 0:
            coverage_percentage = (claim.covered_amount / claim.total_amount) * 100
        else:
            coverage_percentage = 0

        context.update({
            'coverage_percentage': round(coverage_percentage, 2),
        })
        return context


class InsuranceClaimUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
):
    model = InsuranceClaimModel
    permission_required = 'insurance.change_insuranceclaimmodel'
    form_class = InsuranceClaimForm
    template_name = 'insurance/claims/edit.html'
    success_message = 'Insurance Claim Successfully Updated'

    def get_success_url(self):
        return reverse('insurance_claim_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        try:
            # Update processed date if status changed to processed/approved/rejected
            if form.instance.status in ['processing', 'approved', 'rejected', 'partially_approved', 'paid']:
                if not form.instance.processed_date:
                    form.instance.processed_date = timezone.now()
                    form.instance.processed_by = self.request.user

            return super().form_valid(form)
        except Exception:
            logger.exception("Error updating insurance claim")
            messages.error(self.request, "An error occurred while updating the claim. Contact admin.")
            return redirect(self.get_success_url())


class InsuranceClaimDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = InsuranceClaimModel
    permission_required = 'insurance.delete_insuranceclaimmodel'
    template_name = 'insurance/claims/delete.html'
    context_object_name = "claim"
    success_message = 'Insurance Claim Successfully Deleted'

    def get_success_url(self):
        return reverse('insurance_claim_index')


# -------------------------
# Claim Processing Actions
# -------------------------
@login_required
@permission_required('insurance.change_insuranceclaimmodel', raise_exception=True)
def approve_claim(request, pk):
    """Approve an insurance claim"""
    claim = get_object_or_404(InsuranceClaimModel, pk=pk)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                if claim.status != 'pending':
                    messages.error(request, "Only pending claims can be approved.")
                    return redirect(reverse('insurance_claim_detail', kwargs={'pk': pk}))

                claim.status = 'approved'
                claim.processed_date = timezone.now()
                claim.processed_by = request.user
                claim.save(update_fields=['status', 'processed_date', 'processed_by'])

                messages.success(request, f"Claim {claim.claim_number} has been approved.")
                return redirect(reverse('insurance_claim_detail', kwargs={'pk': pk}))

        except Exception:
            logger.exception("Error approving claim id=%s", pk)
            messages.error(request, "An error occurred while approving the claim. Contact admin.")
            return redirect(reverse('insurance_claim_detail', kwargs={'pk': pk}))

    return render(request, 'insurance/claims/approve.html', {'claim': claim})


@login_required
@permission_required('insurance.change_insuranceclaimmodel', raise_exception=True)
def reject_claim(request, pk):
    """Reject an insurance claim"""
    claim = get_object_or_404(InsuranceClaimModel, pk=pk)

    if request.method == 'POST':
        rejection_reason = request.POST.get('rejection_reason', '').strip()

        if not rejection_reason:
            messages.error(request, "Rejection reason is required.")
            return render(request, 'insurance/claims/reject.html', {'claim': claim})

        try:
            with transaction.atomic():
                if claim.status != 'pending':
                    messages.error(request, "Only pending claims can be rejected.")
                    return redirect(reverse('insurance_claim_detail', kwargs={'pk': pk}))

                claim.status = 'rejected'
                claim.rejection_reason = rejection_reason
                claim.processed_date = timezone.now()
                claim.processed_by = request.user
                claim.covered_amount = Decimal('0.00')
                claim.patient_amount = claim.total_amount
                claim.save(update_fields=[
                    'status', 'rejection_reason', 'processed_date', 'processed_by',
                    'covered_amount', 'patient_amount'
                ])

                messages.success(request, f"Claim {claim.claim_number} has been rejected.")
                return redirect(reverse('insurance_claim_detail', kwargs={'pk': pk}))

        except Exception:
            logger.exception("Error rejecting claim id=%s", pk)
            messages.error(request, "An error occurred while rejecting the claim. Contact admin.")

    return render(request, 'insurance/claims/reject.html', {'claim': claim})


@login_required
@permission_required('insurance.change_insuranceclaimmodel', raise_exception=True)
def process_claim(request, pk):
    """Process a claim with custom amounts"""
    claim = get_object_or_404(InsuranceClaimModel, pk=pk)

    if request.method == 'POST':
        try:
            covered_amount = Decimal(request.POST.get('covered_amount', '0'))
            patient_amount = Decimal(request.POST.get('patient_amount', '0'))
            notes = request.POST.get('notes', '').strip()

            # Validation
            if covered_amount + patient_amount != claim.total_amount:
                messages.error(request, "Covered amount + Patient amount must equal total amount.")
                return render(request, 'insurance/claims/process.html', {
                    'claim': claim,
                    'covered_amount': covered_amount,
                    'patient_amount': patient_amount,
                    'notes': notes
                })

            if covered_amount < 0 or patient_amount < 0:
                messages.error(request, "Amounts cannot be negative.")
                return render(request, 'insurance/claims/process.html', {
                    'claim': claim,
                    'covered_amount': covered_amount,
                    'patient_amount': patient_amount,
                    'notes': notes
                })

            with transaction.atomic():
                claim.covered_amount = covered_amount
                claim.patient_amount = patient_amount
                claim.status = 'partially_approved' if covered_amount < claim.total_amount else 'approved'
                claim.processed_date = timezone.now()
                claim.processed_by = request.user
                if notes:
                    claim.notes = notes
                claim.save(update_fields=[
                    'covered_amount', 'patient_amount', 'status',
                    'processed_date', 'processed_by', 'notes'
                ])

                messages.success(request, f"Claim {claim.claim_number} has been processed.")
                return redirect(reverse('insurance_claim_detail', kwargs={'pk': pk}))

        except (ValueError, TypeError):
            messages.error(request, "Invalid amount values.")
        except Exception:
            logger.exception("Error processing claim id=%s", pk)
            messages.error(request, "An error occurred while processing the claim. Contact admin.")

    # Calculate suggested amounts based on coverage plan
    coverage_plan = claim.patient_insurance.coverage_plan
    suggested_coverage = Decimal('0')

    # Calculate based on claim type
    if claim.claim_type == 'consultation' and coverage_plan.consultation_covered:
        suggested_coverage = (claim.total_amount * coverage_plan.consultation_coverage_percentage / 100)
    elif claim.claim_type == 'drug':
        suggested_coverage = (claim.total_amount * coverage_plan.drug_coverage_percentage / 100)
    elif claim.claim_type == 'laboratory':
        suggested_coverage = (claim.total_amount * coverage_plan.lab_coverage_percentage / 100)
    elif claim.claim_type == 'radiology':
        suggested_coverage = (claim.total_amount * coverage_plan.radiology_coverage_percentage / 100)

    suggested_patient_amount = claim.total_amount - suggested_coverage

    context = {
        'claim': claim,
        'suggested_covered_amount': suggested_coverage,
        'suggested_patient_amount': suggested_patient_amount,
    }
    return render(request, 'insurance/claims/process.html', context)


# -------------------------
# Bulk Claim Actions
# -------------------------
@login_required
@permission_required('insurance.change_insuranceclaimmodel', raise_exception=True)
def bulk_claim_action(request):
    """Handle bulk actions on insurance claims"""
    if request.method == 'POST':
        claim_ids = request.POST.getlist('claim')
        action = request.POST.get('action')

        if not claim_ids:
            messages.error(request, 'No claims selected.')
            return redirect(reverse('insurance_claim_index'))

        try:
            with transaction.atomic():
                claims = InsuranceClaimModel.objects.filter(id__in=claim_ids)

                if action == 'approve':
                    # Only approve pending claims
                    pending_claims = claims.filter(status='pending')
                    count = pending_claims.update(
                        status='approved',
                        processed_date=timezone.now(),
                        processed_by=request.user
                    )
                    messages.success(request, f'Successfully approved {count} pending claim(s).')

                elif action == 'mark_processing':
                    pending_claims = claims.filter(status='pending')
                    count = pending_claims.update(status='processing')
                    messages.success(request, f'Successfully marked {count} claim(s) as processing.')

                elif action == 'mark_paid':
                    approved_claims = claims.filter(status__in=['approved', 'partially_approved'])
                    count = approved_claims.update(status='paid')
                    messages.success(request, f'Successfully marked {count} claim(s) as paid.')

                elif action == 'delete':
                    count, _ = claims.delete()
                    messages.success(request, f'Successfully deleted {count} claim(s).')

                else:
                    messages.error(request, 'Invalid action.')

        except Exception:
            logger.exception("Bulk claim action failed")
            messages.error(request, "An error occurred during bulk action. Contact admin.")

        return redirect(reverse('insurance_claim_index'))

    # GET - confirm action
    claim_ids = request.GET.getlist('claim')
    if not claim_ids:
        messages.error(request, 'No claims selected.')
        return redirect(reverse('insurance_claim_index'))

    action = request.GET.get('action')
    context = {
        'claim_list': InsuranceClaimModel.objects.filter(id__in=claim_ids).select_related(
            'patient_insurance__patient', 'patient_insurance__hmo'
        ),
        'action': action
    }

    if action in ['approve', 'mark_processing', 'mark_paid', 'delete']:
        return render(request, 'insurance/claims/bulk_action.html', context)

    messages.error(request, 'Invalid action.')
    return redirect(reverse('insurance_claim_index'))


# -------------------------
# Coverage Calculation Helper
# -------------------------
@login_required
def calculate_coverage(request):
    """AJAX endpoint to calculate coverage for a claim"""
    patient_insurance_id = request.GET.get('patient_insurance_id')
    claim_type = request.GET.get('claim_type')
    total_amount = request.GET.get('total_amount')
    service_id = request.GET.get('service_id')  # For specific drug/lab/scan coverage

    if not all([patient_insurance_id, claim_type, total_amount]):
        return JsonResponse({'error': 'Missing required parameters'}, status=400)

    try:
        patient_insurance = get_object_or_404(PatientInsuranceModel, pk=patient_insurance_id)
        coverage_plan = patient_insurance.coverage_plan
        total_amount = Decimal(total_amount)

        covered_amount = Decimal('0')
        is_covered = False

        # Calculate based on claim type
        if claim_type == 'consultation':
            if coverage_plan.consultation_covered:
                covered_amount = (total_amount * coverage_plan.consultation_coverage_percentage / 100)
                is_covered = True

        elif claim_type == 'drug' and service_id:
            from pharmacy.models import DrugModel
            drug = get_object_or_404(DrugModel, pk=service_id)
            if coverage_plan.is_drug_covered(drug):
                covered_amount = (total_amount * coverage_plan.drug_coverage_percentage / 100)
                is_covered = True

        elif claim_type == 'laboratory' and service_id:
            from laboratory.models import LabTestTemplateModel
            lab_test = get_object_or_404(LabTestTemplateModel, pk=service_id)
            if coverage_plan.is_lab_covered(lab_test):
                covered_amount = (total_amount * coverage_plan.lab_coverage_percentage / 100)
                is_covered = True

        elif claim_type == 'radiology' and service_id:
            from scan.models import ScanTemplateModel
            scan = get_object_or_404(ScanTemplateModel, pk=service_id)
            if coverage_plan.is_radiology_covered(scan):
                covered_amount = (total_amount * coverage_plan.radiology_coverage_percentage / 100)
                is_covered = True

        patient_amount = total_amount - covered_amount

        return JsonResponse({
            'is_covered': is_covered,
            'covered_amount': float(covered_amount),
            'patient_amount': float(patient_amount),
            'coverage_percentage': float((covered_amount / total_amount * 100) if total_amount > 0 else 0)
        })

    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid amount value'}, status=400)
    except Exception:
        logger.exception("Error calculating coverage")
        return JsonResponse({'error': 'Coverage calculation failed'}, status=500)


# -------------------------
# Insurance Statistics API
# -------------------------
@login_required
@permission_required('insurance.view_insuranceclaimmodel', raise_exception=True)
def insurance_statistics_api(request):
    """API endpoint for dashboard charts"""
    try:
        # Claims by month (last 12 months)
        months_data = []
        for i in range(12):
            month_start = timezone.now().replace(day=1) - timedelta(days=30 * i)
            month_end = month_start + timedelta(days=30)

            month_claims = InsuranceClaimModel.objects.filter(
                claim_date__gte=month_start,
                claim_date__lt=month_end
            ).aggregate(
                count=Count('id'),
                amount=Sum('total_amount') or 0
            )

            months_data.append({
                'month': month_start.strftime('%b %Y'),
                'claims': month_claims['count'],
                'amount': float(month_claims['amount'])
            })

        months_data.reverse()

        # Claims by HMO
        hmo_data = list(InsuranceClaimModel.objects.values(
            'patient_insurance__hmo__name'
        ).annotate(
            count=Count('id'),
            amount=Sum('total_amount')
        ).order_by('-count')[:10])

        # Claims by status
        status_data = list(InsuranceClaimModel.objects.values(
            'status'
        ).annotate(count=Count('id')))

        # Claims by type
        type_data = list(InsuranceClaimModel.objects.values(
            'claim_type'
        ).annotate(
            count=Count('id'),
            amount=Sum('total_amount')
        ))

        return JsonResponse({
            'monthly_trends': months_data,
            'hmo_breakdown': hmo_data,
            'status_breakdown': status_data,
            'type_breakdown': type_data
        })

    except Exception:
        logger.exception("Error generating insurance statistics")
        return JsonResponse({'error': 'Failed to generate statistics'}, status=500)