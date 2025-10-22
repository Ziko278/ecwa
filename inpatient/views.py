import json

from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.decorators.http import require_POST
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.http import JsonResponse
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.db.models import Q, Count, Sum, F
from django.utils import timezone
from django.core.paginator import Paginator
from datetime import datetime, date, timedelta
from decimal import Decimal
import logging

from laboratory.models import LabTestOrderModel, LabTestTemplateModel, LabTestCategoryModel
from pharmacy.models import DrugOrderModel, DrugModel, ExternalPrescription
from scan.models import ScanOrderModel, ScanTemplateModel, ScanCategoryModel
from .models import (
    InpatientSettings, Ward, Bed, SurgeryType, SurgeryDrug, SurgeryLab, SurgeryScan,
    Admission, Surgery
)
from .forms import (
    InpatientSettingsForm, WardForm, BedForm, SurgeryTypeForm, AdmissionForm,
    AdmissionUpdateForm, SurgeryForm, SurgeryUpdateForm, SurgeryDrugForm,
    SurgeryLabForm, SurgeryScanForm
)
from patient.models import PatientModel

logger = logging.getLogger(__name__)


def get_inpatient_settings():
    """Get or create inpatient settings instance"""
    settings, created = InpatientSettings.objects.get_or_create(
        id=1,
        defaults={}
    )
    return settings


class FlashFormErrorsMixin:
    """
    Mixin for CreateView/UpdateView to flash form errors and redirect safely.
    Use before SuccessMessageMixin in MRO so messages appear before redirect.
    """

    def form_invalid(self, form):
        try:
            for field, errors in form.errors.items():
                label = form.fields.get(field).label if form.fields.get(field) else field
                for error in errors:
                    messages.error(self.request, f"{label}: {error}")
        except Exception:
            logger.exception("Error while processing form_invalid errors.")
            messages.error(self.request, "There was an error processing the form. Please try again.")
        return redirect(self.get_success_url())


# -------------------------
# Settings Views
# -------------------------
class InpatientSettingsDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = InpatientSettings
    permission_required = 'inpatient.view_inpatientsettings'
    template_name = 'inpatient/settings/detail.html'
    context_object_name = 'settings'

    def get_object(self):
        return get_inpatient_settings()


class InpatientSettingsUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
):
    model = InpatientSettings
    form_class = InpatientSettingsForm
    permission_required = 'inpatient.change_inpatientsettings'
    success_message = 'Inpatient Settings Updated Successfully'
    template_name = 'inpatient/settings/create.html'

    def get_object(self):
        return get_inpatient_settings()

    def get_success_url(self):
        return reverse('inpatient_settings_detail')

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, self.success_message)
        return super().form_valid(form)


# -------------------------
# Ward Views
# -------------------------
class WardCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, CreateView
):
    model = Ward
    permission_required = 'inpatient.add_ward'
    form_class = WardForm
    template_name = 'inpatient/ward/index.html'
    success_message = 'Ward Successfully Created'

    def get_success_url(self):
        return reverse('ward_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('ward_index'))
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, self.success_message)
        return super().form_valid(form)


class WardListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Ward
    permission_required = 'inpatient.view_ward'
    template_name = 'inpatient/ward/index.html'
    context_object_name = 'ward_list'

    def get_queryset(self):
        return Ward.objects.all().annotate(
            total_beds=Count('beds'),
            available_beds_count=Count('beds', filter=Q(beds__status='available')),
            occupied_beds_count=Count('beds', filter=Q(beds__status='occupied'))
        ).order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = WardForm()
        return context


class WardUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
):
    model = Ward
    permission_required = 'inpatient.change_ward'
    form_class = WardForm
    template_name = 'inpatient/ward/index.html'
    success_message = 'Ward Successfully Updated'

    def get_success_url(self):
        return reverse('ward_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('ward_index'))
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, self.success_message)
        return super().form_valid(form)


class WardDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Ward
    permission_required = 'inpatient.view_ward'
    template_name = 'inpatient/ward/detail.html'
    context_object_name = 'ward'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ward = self.object

        beds = ward.beds.all().order_by('bed_number')
        context['beds'] = beds
        context['bed_form'] = BedForm()

        # Statistics
        context['stats'] = {
            'total_beds': beds.count(),
            'available': beds.filter(status='available').count(),
            'occupied': beds.filter(status='occupied').count(),
            'maintenance': beds.filter(status='maintenance').count(),
            'reserved': beds.filter(status='reserved').count(),
        }

        return context


class WardDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Ward
    permission_required = 'inpatient.delete_ward'
    template_name = 'inpatient/ward/delete.html'
    context_object_name = 'ward'
    success_url = reverse_lazy('ward_index')
    success_message = "Ward and all its beds have been successfully deleted."

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, self.success_message)
        return super().delete(request, *args, **kwargs)

# -------------------------
# Bed Views
# -------------------------
class BedCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    model = Bed
    permission_required = 'inpatient.add_bed'
    form_class = BedForm
    template_name = 'inpatient/bed/create.html'
    success_message = 'Bed Successfully Created'

    def get_success_url(self):
        ward_pk = self.object.ward.pk if self.object.ward else None
        if ward_pk:
            return reverse('ward_detail', kwargs={'pk': ward_pk})
        return reverse('ward_index')

    def form_valid(self, form):
        messages.success(self.request, self.success_message)
        return super().form_valid(form)

    def form_invalid(self, form):
        """
        Handle form errors manually, add messages, and redirect
        back to the ward detail page.
        """
        # Add each form error as a separate message
        for field, errors in form.errors.items():
            label = form.fields.get(field).label if form.fields.get(field) else field.capitalize()
            for error in errors:
                messages.error(self.request, f"{label}: {error}")

        # Get the ward_id from the submitted form data to redirect back
        ward_id = self.request.POST.get('ward')
        if ward_id:
            try:
                # Ensure ward_id is a valid integer
                ward_pk = int(ward_id)
                return redirect('ward_detail', pk=ward_pk)
            except (ValueError, TypeError):
                # Fallback if ward_id is invalid
                messages.error(self.request, "An error occurred, returning to the main ward list.")
                return redirect('ward_index')

        # Fallback if ward was not submitted in the form
        messages.error(self.request, "Ward information was missing. Returning to the main ward list.")
        return redirect('ward_index')


class BedUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
):
    model = Bed
    permission_required = 'inpatient.change_bed'
    form_class = BedForm
    template_name = 'inpatient/bed/create.html'
    success_message = 'Bed Successfully Updated'

    def get_success_url(self):
        ward_pk = self.object.ward.pk if self.object.ward else None
        if ward_pk:
            return reverse('ward_detail', kwargs={'pk': ward_pk})
        return reverse('ward_index')

    def form_valid(self, form):
        messages.success(self.request, self.success_message)
        return super().form_valid(form)


class BedDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Bed
    permission_required = 'inpatient.delete_bed'
    template_name = 'inpatient/ward/delete_bed.html'
    context_object_name = 'bed'
    success_message = "Bed has been successfully deleted."

    def get_success_url(self):
        # Redirect back to the ward detail page
        return reverse_lazy('ward_detail', kwargs={'pk': self.object.ward.pk})

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        # Prevent deleting an occupied bed
        if self.object.status == 'occupied':
            messages.error(request, f"Cannot delete Bed {self.object.bed_number} because it is currently occupied.")
            return redirect(self.get_success_url())

        messages.success(self.request, self.success_message)
        return super().delete(request, *args, **kwargs)


# -------------------------
# Surgery Type Views
# -------------------------
class SurgeryTypeListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = SurgeryType
    permission_required = 'inpatient.view_surgerytype'
    template_name = 'inpatient/surgery_type/index.html'
    context_object_name = 'surgery_type_list'
    paginate_by = 20

    def get_queryset(self):
        queryset = SurgeryType.objects.all()

        # Search functionality
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(category__icontains=search)
            )

        # Category filter
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category=category)

        return queryset.order_by('category', 'name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = SurgeryType._meta.get_field('category').choices
        context['search_query'] = self.request.GET.get('search', '')
        context['selected_category'] = self.request.GET.get('category', '')
        return context


class SurgeryTypeCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, CreateView
):
    model = SurgeryType
    permission_required = 'inpatient.add_surgerytype'
    form_class = SurgeryTypeForm
    template_name = 'inpatient/surgery_type/create.html'
    success_message = 'Surgery Type Successfully Created'

    def get_success_url(self):
        return reverse('surgery_type_index')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, self.success_message)
        return super().form_valid(form)


class SurgeryTypeUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, UpdateView
):
    model = SurgeryType
    permission_required = 'inpatient.change_surgerytype'
    form_class = SurgeryTypeForm
    template_name = 'inpatient/surgery_type/create.html'
    success_message = 'Surgery Type Successfully Updated'

    def get_success_url(self):
        return reverse('surgery_type_index')

    def form_valid(self, form):
        messages.success(self.request, self.success_message)
        return super().form_valid(form)


class SurgeryTypeDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = SurgeryType
    permission_required = 'inpatient.view_surgerytype'
    template_name = 'inpatient/surgery_type/detail.html'
    context_object_name = 'surgery_type'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        surgery_type = self.object

        # Get associated items
        # Ensure the 'drug' related name on SurgeryDrug points to your 'DrugModel'
        surgery_drugs = surgery_type.surgerydrug_set.all().select_related('drug')
        surgery_labs = surgery_type.surgerylab_set.all().select_related('lab')
        surgery_scans = surgery_type.surgeryscan_set.all().select_related('scan')

        # Calculate totals
        drugs_with_totals = []
        total_drugs_price = 0
        for item in surgery_drugs:
            try:
                # --- FIX ---
                # Changed item.drug.price to item.drug.selling_price
                item.total_price = item.drug.selling_price * item.quantity
                total_drugs_price += item.total_price
                drugs_with_totals.append(item)
            except (AttributeError, TypeError):
                item.total_price = 0
                drugs_with_totals.append(item)

        try:
            # Assuming lab/scan models use 'price'. Adjust if they also use 'selling_price'
            total_labs_price = sum(item.lab.price for item in surgery_labs if item.lab and item.lab.price)
        except (AttributeError, TypeError):
            total_labs_price = 0

        try:
            total_scans_price = sum(item.scan.price for item in surgery_scans if item.scan and item.scan.price)
        except (AttributeError, TypeError):
            total_scans_price = 0

        total_package_items_price = total_drugs_price + total_labs_price + total_scans_price

        base_fee = surgery_type.total_base_fee or 0
        grand_total = base_fee + total_package_items_price

        # Forms for adding items
        context['drug_form'] = SurgeryDrugForm()
        context['lab_form'] = SurgeryLabForm()
        context['scan_form'] = SurgeryScanForm()

        # Add items and totals to context
        context['surgery_drugs'] = drugs_with_totals  # Use the list with 'total_price'
        context['surgery_labs'] = surgery_labs
        context['surgery_scans'] = surgery_scans

        context['total_drugs_price'] = total_drugs_price
        context['total_labs_price'] = total_labs_price
        context['total_scans_price'] = total_scans_price
        context['total_package_items_price'] = total_package_items_price
        context['grand_total'] = grand_total

        return context


# -------------------------
# Admission Views
# -------------------------
@login_required
@permission_required('inpatient.add_admission')
def admission_search_patient(request):
    """Search for patient to create admission"""
    if request.method == 'POST':
        card_number = request.POST.get('card_number', '').strip()
        if not card_number:
            messages.error(request, 'Please enter patient card number')
            return render(request, 'inpatient/admission/search_patient.html')

        try:
            patient = PatientModel.objects.get(card_number__iexact=card_number)

            # Check for active admission
            active_admission = Admission.objects.filter(
                patient=patient,
                status='active'
            ).first()

            if active_admission:
                messages.info(request, f'Patient already has an active admission: {active_admission.admission_number}')
                return redirect('admission_detail', pk=active_admission.pk)

            # No active admission, proceed to create new one
            return redirect('admission_create_for_patient', patient_id=patient.id)

        except PatientModel.DoesNotExist:
            messages.error(request, 'Patient not found with this card number')

    return render(request, 'inpatient/admission/search_patient.html')


@login_required
@permission_required('inpatient.add_admission')
def admission_create_for_patient(request, patient_id):
    """Create admission for specific patient"""
    patient = get_object_or_404(PatientModel, pk=patient_id)

    if request.method == 'POST':
        form = AdmissionForm(request.POST)
        if form.is_valid():
            admission = form.save(commit=False)
            admission.patient = patient
            admission.admitted_by = request.user
            admission.save()

            messages.success(request, f'Admission {admission.admission_number} created successfully')
            return redirect('admission_detail', pk=admission.pk)
    else:
        form = AdmissionForm()
        form.fields['patient'].initial = patient
        form.fields['patient'].widget.attrs['readonly'] = True

    return render(request, 'inpatient/admission/create.html', {
        'form': form,
        'patient': patient
    })


class AdmissionListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Admission
    permission_required = 'inpatient.view_admission'
    template_name = 'inpatient/admission/index.html'
    context_object_name = 'admission_list'
    paginate_by = 20

    def get_queryset(self):
        queryset = Admission.objects.select_related(
            'patient', 'bed__ward', 'attending_doctor'
        ).all()

        # Status filter
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)

        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(admission_number__icontains=search) |
                Q(patient__first_name__icontains=search) |
                Q(patient__last_name__icontains=search) |
                Q(patient__card_number__icontains=search)
            )

        return queryset.order_by('-admission_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = Admission._meta.get_field('status').choices
        context['search_query'] = self.request.GET.get('search', '')
        context['selected_status'] = self.request.GET.get('status', '')
        return context


class AdmissionDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Admission
    permission_required = 'inpatient.view_admission'
    template_name = 'inpatient/admission/detail.html'
    context_object_name = 'admission'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        admission = self.object

        # Get associated surgeries
        context['surgeries'] = admission.surgeries.all().select_related('surgery_type')

        # Get billing information (placeholder - implement based on your billing system)
        context['billing_summary'] = self.get_billing_summary(admission)

        # Forms for updates
        context['update_form'] = AdmissionUpdateForm(instance=admission)

        return context

    def get_billing_summary(self, admission):
        """Calculate billing summary for admission"""
        # This is a placeholder - implement based on your billing system
        return {
            'admission_fee': Decimal('0.00'),
            'bed_charges': Decimal('0.00'),
            'drug_charges': Decimal('0.00'),
            'lab_charges': Decimal('0.00'),
            'scan_charges': Decimal('0.00'),
            'surgery_charges': Decimal('0.00'),
            'total_charges': Decimal('0.00'),
            'total_paid': Decimal('0.00'),
            'balance': Decimal('0.00'),
        }


class AdmissionUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, UpdateView
):
    model = Admission
    permission_required = 'inpatient.change_admission'
    form_class = AdmissionUpdateForm
    template_name = 'inpatient/admission/update.html'
    success_message = 'Admission Successfully Updated'

    def get_success_url(self):
        return reverse('admission_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, self.success_message)
        return super().form_valid(form)


# -------------------------
# Surgery Views
# -------------------------
@login_required
@permission_required('inpatient.add_surgery')
def surgery_search_patient(request):
    """Search for patient to create surgery"""
    if request.method == 'POST':
        card_number = request.POST.get('card_number', '').strip()
        if not card_number:
            messages.error(request, 'Please enter patient card number')
            return render(request, 'inpatient/surgery/search_patient.html')

        try:
            patient = PatientModel.objects.get(card_number__iexact=card_number)
            return redirect('surgery_create_for_patient', patient_id=patient.id)

        except PatientModel.DoesNotExist:
            messages.error(request, 'Patient not found with this card number')

    return render(request, 'inpatient/surgery/search_patient.html')


@login_required
@permission_required('inpatient.add_surgery')
def surgery_create_for_patient(request, patient_id):
    """Create surgery for specific patient"""
    patient = get_object_or_404(PatientModel, pk=patient_id)

    if request.method == 'POST':
        form = SurgeryForm(request.POST)
        if form.is_valid():
            surgery = form.save(commit=False)
            surgery.patient = patient
            surgery.created_by = request.user
            surgery.save()

            messages.success(request, f'Surgery {surgery.surgery_number} scheduled successfully')
            return redirect('surgery_detail', pk=surgery.pk)
    else:
        form = SurgeryForm()
        form.fields['patient'].initial = patient
        # The line filtering the admission queryset is no longer needed and has been removed.

    return render(request, 'inpatient/surgery/create.html', {
        'form': form,
        'patient': patient
    })


class SurgeryListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Surgery
    permission_required = 'inpatient.view_surgery'
    template_name = 'inpatient/surgery/index.html'
    context_object_name = 'surgery_list'
    paginate_by = 20

    def get_queryset(self):
        queryset = Surgery.objects.select_related(
            'patient', 'surgery_type', 'primary_surgeon', 'admission'
        ).all()

        # Status filter
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)

        # Date filter
        date_filter = self.request.GET.get('date_filter')
        if date_filter == 'today':
            queryset = queryset.filter(scheduled_date__date=date.today())
        elif date_filter == 'week':
            start_week = date.today() - timedelta(days=date.today().weekday())
            end_week = start_week + timedelta(days=6)
            queryset = queryset.filter(scheduled_date__date__range=[start_week, end_week])

        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(surgery_number__icontains=search) |
                Q(patient__first_name__icontains=search) |
                Q(patient__last_name__icontains=search) |
                Q(surgery_type__name__icontains=search)
            )

        return queryset.order_by('-scheduled_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = Surgery._meta.get_field('status').choices
        context['search_query'] = self.request.GET.get('search', '')
        context['selected_status'] = self.request.GET.get('status', '')
        context['selected_date_filter'] = self.request.GET.get('date_filter', '')
        return context


class SurgeryDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Surgery
    permission_required = 'inpatient.view_surgery'
    template_name = 'inpatient/surgery/detail.html'
    context_object_name = 'surgery'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        surgery = self.object

        # Fetch existing orders related to the surgery
        context['drug_orders'] = surgery.drug_orders.all().select_related('drug', 'ordered_by')
        context['lab_orders'] = surgery.lab_test_orders.all().select_related('template', 'ordered_by')
        context['scan_orders'] = surgery.scan_orders.all().select_related('template', 'ordered_by')

        # Form for updating surgery details
        context['update_form'] = SurgeryUpdateForm(instance=surgery)

        # --- START: New context data for modals ---
        # Add the categories needed to populate the filter dropdowns in the order modals.
        context['lab_categories'] = LabTestCategoryModel.objects.all()
        context['scan_categories'] = ScanCategoryModel.objects.all()
        # --- END: New context data ---

        return context


class SurgeryUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, UpdateView
):
    model = Surgery
    permission_required = 'inpatient.change_surgery'
    form_class = SurgeryUpdateForm
    template_name = 'inpatient/surgery/update.html'
    success_message = 'Surgery Successfully Updated'

    def get_success_url(self):
        return reverse('surgery_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, self.success_message)
        return super().form_valid(form)


# -------------------------
# AJAX Views for Surgery Package Management
# -------------------------
@login_required
@permission_required('inpatient.change_surgerytype')
def add_drug_to_surgery(request, pk):
    """Add drug to surgery type package"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    surgery_type = get_object_or_404(SurgeryType, pk=pk)
    drug_id = request.POST.get('drug_id')

    if not drug_id:
        return JsonResponse({'error': 'Drug ID is required'}, status=400)

    try:
        from pharmacy.models import DrugModel
        drug = get_object_or_404(DrugModel, pk=drug_id)

        # Check if already exists
        if SurgeryDrug.objects.filter(surgery=surgery_type, drug=drug).exists():
            drug_name = drug.brand_name if drug.brand_name else str(drug.formulation)
            return JsonResponse({'error': f'{drug_name} is already in the surgery package'}, status=400)

        # Create the association
        quantity = request.POST.get('quantity', 1)
        timing = request.POST.get('timing', '')
        is_optional = request.POST.get('is_optional') == 'on'

        surgery_drug = SurgeryDrug.objects.create(
            surgery=surgery_type,
            drug=drug,
            quantity=int(quantity),
            timing=timing,
            is_optional=is_optional
        )

        drug_name = drug.brand_name if drug.brand_name else str(drug.formulation)
        return JsonResponse({
            'success': True,
            'message': f'{drug_name} added to surgery package',
            'drug': {
                'id': surgery_drug.id,
                'name': drug_name,
                'quantity': surgery_drug.quantity,
                'timing': surgery_drug.timing,
                'is_optional': surgery_drug.is_optional
            }
        })
    except Exception as e:
        logger.exception("Error adding drug to surgery package")
        return JsonResponse({'error': 'Failed to add drug'}, status=500)


@login_required
@permission_required('inpatient.change_surgerytype')
def remove_drug_from_surgery(request, pk, drug_id):
    """Remove drug from surgery type package"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    surgery_type = get_object_or_404(SurgeryType, pk=pk)

    try:
        surgery_drug = get_object_or_404(SurgeryDrug, pk=drug_id, surgery=surgery_type)
        drug_name = surgery_drug.drug.brand_name if surgery_drug.drug.brand_name else str(surgery_drug.drug.formulation)
        surgery_drug.delete()

        return JsonResponse({
            'success': True,
            'message': f'{drug_name} removed from surgery package'
        })
    except Exception as e:
        logger.exception("Error removing drug from surgery package")
        return JsonResponse({'error': 'Failed to remove drug'}, status=500)


@login_required
@permission_required('inpatient.change_surgerytype')
def add_lab_to_surgery(request, pk):
    """Add lab test to surgery type package"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    surgery_type = get_object_or_404(SurgeryType, pk=pk)
    lab_id = request.POST.get('lab_id')

    if not lab_id:
        return JsonResponse({'error': 'Lab test ID is required'}, status=400)

    try:
        from laboratory.models import LabTestTemplateModel
        lab_test = get_object_or_404(LabTestTemplateModel, pk=lab_id)

        # Check if already exists
        if SurgeryLab.objects.filter(surgery=surgery_type, lab=lab_test).exists():
            return JsonResponse({'error': f'{lab_test.name} is already in the surgery package'}, status=400)

        # Create the association
        timing = request.POST.get('timing', '')
        is_optional = request.POST.get('is_optional') == 'on'

        surgery_lab = SurgeryLab.objects.create(
            surgery=surgery_type,
            lab=lab_test,
            timing=timing,
            is_optional=is_optional
        )

        return JsonResponse({
            'success': True,
            'message': f'{lab_test.name} added to surgery package',
            'lab': {
                'id': surgery_lab.id,
                'name': lab_test.name,
                'timing': surgery_lab.timing,
                'is_optional': surgery_lab.is_optional
            }
        })
    except Exception as e:
        logger.exception("Error adding lab test to surgery package")
        return JsonResponse({'error': 'Failed to add lab test'}, status=500)


@login_required
@permission_required('inpatient.change_surgerytype')
def remove_lab_from_surgery(request, pk, lab_id):
    """Remove lab test from surgery type package"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    surgery_type = get_object_or_404(SurgeryType, pk=pk)

    try:
        surgery_lab = get_object_or_404(SurgeryLab, pk=lab_id, surgery=surgery_type)
        lab_name = surgery_lab.lab.name
        surgery_lab.delete()

        return JsonResponse({
            'success': True,
            'message': f'{lab_name} removed from surgery package'
        })
    except Exception as e:
        logger.exception("Error removing lab test from surgery package")
        return JsonResponse({'error': 'Failed to remove lab test'}, status=500)


# -------------------------
# Dashboard View
# -------------------------
@login_required
@permission_required('inpatient.view_admission')
def inpatient_dashboard(request):
    """Dashboard showing inpatient statistics"""
    today = date.today()

    # Basic statistics
    stats = {
        'total_wards': Ward.objects.filter(is_active=True).count(),
        'total_beds': Bed.objects.filter(is_active=True).count(),
        'occupied_beds': Bed.objects.filter(status='occupied').count(),
        'available_beds': Bed.objects.filter(status='available').count(),
        'active_admissions': Admission.objects.filter(status='active').count(),
        'surgeries_today': Surgery.objects.filter(scheduled_date__date=today).count(),
        'surgeries_pending': Surgery.objects.filter(status='scheduled').count(),
    }

    # Calculate occupancy rate
    if stats['total_beds'] > 0:
        stats['occupancy_rate'] = round((stats['occupied_beds'] / stats['total_beds']) * 100, 1)
    else:
        stats['occupancy_rate'] = 0

    # Recent admissions
    recent_admissions = Admission.objects.filter(
        admission_date__gte=today - timedelta(days=7)
    ).select_related('patient', 'bed__ward').order_by('-admission_date')[:10]

    # Upcoming surgeries
    upcoming_surgeries = Surgery.objects.filter(
        scheduled_date__gte=timezone.now(),
        status='scheduled'
    ).select_related('patient', 'surgery_type').order_by('scheduled_date')[:10]

    # Ward occupancy
    ward_occupancy = Ward.objects.filter(is_active=True).annotate(
        total_beds=Count('beds', filter=Q(beds__is_active=True)),
        occupied_beds=Count('beds', filter=Q(beds__status='occupied')),
        available_beds=Count('beds', filter=Q(beds__status='available'))
    ).order_by('name')

    context = {
        'stats': stats,
        'recent_admissions': recent_admissions,
        'upcoming_surgeries': upcoming_surgeries,
        'ward_occupancy': ward_occupancy,
    }

    return render(request, 'inpatient/dashboard.html', context)


# -------------------------
# Surgery Package Management (AJAX)
# -------------------------
@login_required
@permission_required('inpatient.change_surgerytype')
def add_scan_to_surgery(request, pk):
    """Add scan to surgery type package"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    surgery_type = get_object_or_404(SurgeryType, pk=pk)
    scan_id = request.POST.get('scan_id')

    if not scan_id:
        return JsonResponse({'error': 'Scan ID is required'}, status=400)


    try:
        from scan.models import ScanTemplateModel
        scan = get_object_or_404(ScanTemplateModel, pk=scan_id)

        # Check if already exists
        if SurgeryScan.objects.filter(surgery=surgery_type, scan=scan).exists():
            return JsonResponse({'error': f'{scan.name} is already in the surgery package'}, status=400)

        # Create the association
        timing = request.POST.get('timing', '')
        is_optional = request.POST.get('is_optional') == 'on'

        surgery_scan = SurgeryScan.objects.create(
            surgery=surgery_type,
            scan=scan,
            timing=timing,
            is_optional=is_optional
        )

        return JsonResponse({
            'success': True,
            'message': f'{scan.name} added to surgery package',
            'scan': {
                'id': surgery_scan.id,
                'name': scan.name,
                'timing': surgery_scan.timing,
                'is_optional': surgery_scan.is_optional
            }
        })
    except Exception as e:
        logger.exception("Error adding scan to surgery package")
        print(e)
        return JsonResponse({'error': 'Failed to add scan'}, status=500)


@login_required
@permission_required('inpatient.change_surgerytype')
def remove_scan_from_surgery(request, pk, scan_id):
    """Remove scan from surgery type package"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    surgery_type = get_object_or_404(SurgeryType, pk=pk)

    try:
        surgery_scan = get_object_or_404(SurgeryScan, pk=scan_id, surgery=surgery_type)
        scan_name = surgery_scan.scan.name
        surgery_scan.delete()

        return JsonResponse({
            'success': True,
            'message': f'{scan_name} removed from surgery package'
        })
    except Exception as e:
        logger.exception("Error removing scan from surgery package")
        return JsonResponse({'error': 'Failed to remove scan'}, status=500)


# -------------------------
# Admission Services Management (AJAX)
# -------------------------
@login_required
@permission_required('inpatient.change_admission')
def add_drug_to_admission(request, pk):
    """Add drug order to admission"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    admission = get_object_or_404(Admission, pk=pk)
    drug_id = request.POST.get('drug_id')

    if not drug_id:
        return JsonResponse({'error': 'Drug ID is required'}, status=400)

    try:
        from pharmacy.models import DrugModel
        from pharmacy.models import DrugOrderModel  # Assuming this exists

        drug = get_object_or_404(DrugModel, pk=drug_id)

        # Get form data
        quantity = request.POST.get('quantity', 1)
        dosage_instructions = request.POST.get('dosage_instructions', '')
        duration = request.POST.get('duration', '')

        # Create drug order
        drug_order = DrugOrderModel.objects.create(
            patient=admission.patient,
            drug=drug,
            quantity_ordered=float(quantity),
            dosage_instructions=dosage_instructions,
            duration=duration,
            ordered_by=request.user,
            status='pending'
        )

        drug_name = drug.brand_name if drug.brand_name else str(drug.formulation)
        return JsonResponse({
            'success': True,
            'message': f'{drug_name} ordered for patient',
            'drug_order': {
                'id': drug_order.id,
                'name': drug_name,
                'quantity': drug_order.quantity_ordered,
                'order_number': drug_order.order_number,
                'status': drug_order.status
            }
        })
    except Exception as e:
        logger.exception("Error adding drug order to admission")
        return JsonResponse({'error': 'Failed to add drug order'}, status=500)


@login_required
@permission_required('inpatient.change_admission')
def add_lab_to_admission(request, pk):
    """Add lab test order to admission"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    admission = get_object_or_404(Admission, pk=pk)
    lab_id = request.POST.get('lab_id')

    if not lab_id:
        return JsonResponse({'error': 'Lab test ID is required'}, status=400)

    try:
        from laboratory.models import LabTestTemplateModel, LabTestOrderModel

        lab_template = get_object_or_404(LabTestTemplateModel, pk=lab_id)

        # Create lab order
        lab_order = LabTestOrderModel.objects.create(
            patient=admission.patient,
            template=lab_template,
            ordered_by=request.user,
            status='pending',
            source='doctor'
        )

        return JsonResponse({
            'success': True,
            'message': f'{lab_template.name} ordered for patient',
            'lab_order': {
                'id': lab_order.id,
                'name': lab_template.name,
                'order_number': lab_order.order_number,
                'status': lab_order.status
            }
        })
    except Exception as e:
        logger.exception("Error adding lab order to admission")
        return JsonResponse({'error': 'Failed to add lab order'}, status=500)


@login_required
@permission_required('inpatient.change_admission')
def add_scan_to_admission(request, pk):
    """Add scan order to admission"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST method required'}, status=405)

    admission = get_object_or_404(Admission, pk=pk)
    scan_id = request.POST.get('scan_id')

    if not scan_id:
        return JsonResponse({'error': 'Scan ID is required'}, status=400)

    try:
        from scan.models import ScanTemplateModel, ScanOrderModel

        scan_template = get_object_or_404(ScanTemplateModel, pk=scan_id)

        # Get clinical indication
        clinical_indication = request.POST.get('clinical_indication', '')

        # Create scan order
        scan_order = ScanOrderModel.objects.create(
            patient=admission.patient,
            template=scan_template,
            ordered_by=request.user,
            status='pending',
            clinical_indication=clinical_indication
        )

        return JsonResponse({
            'success': True,
            'message': f'{scan_template.name} ordered for patient',
            'scan_order': {
                'id': scan_order.id,
                'name': scan_template.name,
                'order_number': scan_order.order_number,
                'status': scan_order.status
            }
        })
    except Exception as e:
        logger.exception("Error adding scan order to admission")
        return JsonResponse({'error': 'Failed to add scan order'}, status=500)


# -------------------------
# Search endpoints for AJAX
# -------------------------
@login_required
def search_drugs_for_surgery(request):
    """Search drugs for adding to surgery packages"""
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'results': []})

    try:
        from pharmacy.models import DrugModel
        drugs_queryset = DrugModel.objects.filter(
            Q(brand_name__icontains=query) |
            Q(formulation__generic_drug__generic_name__icontains=query)
        )[:20]

        results = [
            {
                'id': drug.id,
                'name': str(drug)
            }
            for drug in drugs_queryset
        ]

        return JsonResponse({'results': results})

    except Exception:
        logger.exception("Error searching drugs")
        return JsonResponse({'error': 'Search failed'}, status=500)


@login_required
def search_lab_tests_for_surgery(request):
    """Search lab tests for adding to surgery packages"""
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
def search_scans_for_surgery(request):
    """Search scans for adding to surgery packages"""
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'results': []})

    try:
        from scan.models import ScanTemplateModel
        scans = ScanTemplateModel.objects.filter(
            name__icontains=query
        ).values('id', 'name')[:20]
        return JsonResponse({'results': list(scans)})
    except Exception:
        logger.exception("Error searching scans")
        return JsonResponse({'error': 'Search failed'}, status=500)


@login_required
def search_surgery_types_ajax(request):
    """AJAX view to search for surgery types for the creation form."""
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'results': []})

    try:
        surgery_types = SurgeryType.objects.filter(
            name__icontains=query, is_active=True
        ).values('id', 'name')[:20]
        return JsonResponse({'results': list(surgery_types)})
    except Exception as e:
        logger.exception("Error searching surgery types")
        return JsonResponse({'error': f'Search failed: {e}'}, status=500)


@login_required
def get_surgery_type_details_ajax(request, pk):
    """AJAX view to get the default fees for a selected surgery type."""
    try:
        surgery_type = SurgeryType.objects.get(pk=pk)
        data = {
            'surgeon_fee': surgery_type.base_surgeon_fee,
            'anesthesia_fee': surgery_type.base_anesthesia_fee,
            'facility_fee': surgery_type.base_facility_fee,
        }
        return JsonResponse({'success': True, 'fees': data})
    except SurgeryType.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Surgery type not found'}, status=404)
    except Exception as e:
        logger.exception("Error fetching surgery type details")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@permission_required('inpatient.change_surgery')
def add_service_order_to_surgery(request, pk):
    """Add a new drug, lab, or scan order to a specific surgery."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST method required'}, status=405)

    surgery = get_object_or_404(Surgery, pk=pk)
    service_type = request.POST.get('service_type')
    service_id = request.POST.get('service_id')

    if not all([service_type, service_id]):
        return JsonResponse({'success': False, 'error': 'Missing required parameters'}, status=400)

    try:
        if service_type == 'drug':
            drug = get_object_or_404(DrugModel, pk=service_id)
            order = DrugOrderModel.objects.create(
                patient=surgery.patient,
                drug=drug,
                surgery=surgery,
                admission=surgery.admission,
                quantity_ordered=request.POST.get('quantity', 1),
                dosage_instructions=request.POST.get('instructions', ''),
                ordered_by=request.user,
                status='pending'
            )
            item_name = str(drug)
        elif service_type == 'lab':
            lab = get_object_or_404(LabTestTemplateModel, pk=service_id)
            order = LabTestOrderModel.objects.create(
                patient=surgery.patient, template=lab, surgery=surgery,
                admission=surgery.admission, ordered_by=request.user, status='pending', source='doctor'
            )
            item_name = lab.name
        elif service_type == 'scan':
            scan = get_object_or_404(ScanTemplateModel, pk=service_id)
            order = ScanOrderModel.objects.create(
                patient=surgery.patient, template=scan, surgery=surgery,
                admission=surgery.admission, ordered_by=request.user, status='pending',
                clinical_indication=request.POST.get('instructions', f"For {surgery.surgery_type.name}")
            )
            item_name = scan.name
        else:
            return JsonResponse({'success': False, 'error': 'Invalid service type'}, status=400)

        return JsonResponse({'success': True, 'message': f'{item_name} has been successfully ordered.'})

    except Exception as e:
        logger.exception("Error adding service order to surgery")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@permission_required('inpatient.change_surgery')
def remove_service_order_from_surgery(request, pk, order_id):
    """Remove a drug, lab, or scan order from a surgery if it is still in a removable state."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST method required'}, status=405)

    surgery = get_object_or_404(Surgery, pk=pk)
    service_type = request.POST.get('service_type')

    try:
        if service_type == 'drug':
            order = get_object_or_404(DrugOrderModel, pk=order_id, surgery=surgery)
            if order.status != 'pending':
                return JsonResponse({'success': False, 'error': 'Cannot remove a drug that has already been processed or dispensed.'})
        elif service_type == 'lab':
            order = get_object_or_404(LabTestOrderModel, pk=order_id, surgery=surgery)
            if order.has_result:
                return JsonResponse({'success': False, 'error': 'Cannot remove a lab test that already has a result.'})
        elif service_type == 'scan':
            order = get_object_or_404(ScanOrderModel, pk=order_id, surgery=surgery)
            if order.has_result:
                return JsonResponse({'success': False, 'error': 'Cannot remove a scan that already has a result.'})
        else:
            return JsonResponse({'success': False, 'error': 'Invalid service type'}, status=400)

        order.delete()
        return JsonResponse({'success': True, 'message': 'The order has been successfully removed.'})

    except Exception as e:
        logger.exception("Error removing service order from surgery")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def surgery_prescribe_multiple(request):
    """Handles multi-drug prescription submissions linked to a surgery."""
    try:
        data = json.loads(request.body)
        patient_id = data.get('patient_id')
        surgery_id = data.get('surgery_id')

        available_drugs = data.get('available_drugs', [])
        external_drugs = data.get('external_drugs', [])

        patient = get_object_or_404(PatientModel, id=patient_id)
        surgery = get_object_or_404(Surgery, id=surgery_id)

        with transaction.atomic():
            # Process drugs from inventory
            for drug_data in available_drugs:
                drug = get_object_or_404(DrugModel, id=drug_data.get('drug_id'))
                DrugOrderModel.objects.create(
                    patient=patient, surgery=surgery, ordered_by=request.user, drug=drug,
                    dosage_instructions=drug_data.get('dosage'), duration=drug_data.get('duration'),
                    quantity_ordered=float(drug_data.get('quantity', 1)), notes=drug_data.get('notes'),
                    status='pending',
                )

            # Process drugs not in inventory
            for drug_data in external_drugs:
                ExternalPrescription.objects.create(
                    patient=patient, surgery=surgery, ordered_by=request.user,
                    drug_name=drug_data.get('drug_name'), dosage_instructions=drug_data.get('dosage'),
                    duration=drug_data.get('duration'), quantity=drug_data.get('quantity'),
                    notes=drug_data.get('notes'),
                )

        return JsonResponse({'success': True, 'message': 'Prescriptions saved successfully.'})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def surgery_order_multiple_labs(request):
    """Handles multi-lab test order submissions linked to a surgery."""
    try:
        data = json.loads(request.body)
        patient_id = data.get('patient_id')
        surgery_id = data.get('surgery_id')
        orders = data.get('orders', [])

        patient = get_object_or_404(PatientModel, id=patient_id)
        surgery = get_object_or_404(Surgery, id=surgery_id)

        with transaction.atomic():
            for order_data in orders:
                template = get_object_or_404(LabTestTemplateModel, id=order_data.get('template_id'))
                LabTestOrderModel.objects.create(
                    patient=patient, surgery=surgery, template=template, ordered_by=request.user,
                    special_instructions=order_data.get('instructions', ''), source='doctor', status='pending',
                )

        return JsonResponse({'success': True, 'message': f'{len(orders)} lab test(s) ordered.'})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_POST
def surgery_order_multiple_imaging(request):
    """Handles multi-imaging order submissions linked to a surgery."""
    try:
        data = json.loads(request.body)
        patient_id = data.get('patient_id')
        surgery_id = data.get('surgery_id')
        orders = data.get('orders', [])

        patient = get_object_or_404(PatientModel, id=patient_id)
        surgery = get_object_or_404(Surgery, id=surgery_id)

        with transaction.atomic():
            for order_data in orders:
                template = get_object_or_404(ScanTemplateModel, id=order_data.get('template_id'))
                ScanOrderModel.objects.create(
                    patient=patient, surgery=surgery, template=template, ordered_by=request.user,
                    clinical_indication=order_data.get('indication', ''), status='pending',
                )

        return JsonResponse({'success': True, 'message': f'{len(orders)} imaging request(s) ordered.'})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)