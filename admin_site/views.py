from datetime import timedelta
import json
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import HttpResponse
from django.urls import reverse
# from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.messages.views import SuccessMessageMixin, messages
from django.views.generic import TemplateView
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.views.generic.list import ListView
from django.views.generic.detail import DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.utils import timezone
from admin_site.forms import SiteInfoForm
from admin_site.models import SiteInfoModel, ActivityLogModel
from human_resource.models import StaffProfileModel
from patient.models import PatientModel, RegistrationPaymentModel
from patient.views import calculate_growth_percentage, calculate_age_groups, get_monthly_trends, \
    get_registration_chart_data

from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash


def create_activity_log(user, log, category, sub_category, keywords=""):
    ActivityLogModel.objects.create(
        user=user,
        log=log,
        category=category,
        sub_category=sub_category,
        keywords=keywords
    )


def get_patient_dashboard_context(request):
    """
    Get the context data for patient dashboard
    """
    # Get current date and time periods
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    # Basic patient statistics
    total_patients = PatientModel.objects.count()
    male_patients = PatientModel.objects.filter(gender='male').count()
    female_patients = PatientModel.objects.filter(gender='female').count()

    # Registration status statistics
    pending_registrations = RegistrationPaymentModel.objects.filter(
        registration_status='pending'
    ).count()

    # Old vs New patients (based on registration fee type)
    old_patients_total = RegistrationPaymentModel.objects.filter(
        registration_fee__patient_type='old'
    ).count()
    new_patients_total = RegistrationPaymentModel.objects.filter(
        registration_fee__patient_type='new'
    ).count()

    # Time-based statistics for old patients
    old_patients_today = RegistrationPaymentModel.objects.filter(
        registration_fee__patient_type='old',
        date=today
    ).count()

    old_patients_week = RegistrationPaymentModel.objects.filter(
        registration_fee__patient_type='old',
        date__gte=week_start
    ).count()

    old_patients_month = RegistrationPaymentModel.objects.filter(
        registration_fee__patient_type='old',
        date__gte=month_start
    ).count()

    # Time-based statistics for new patients
    new_patients_today = RegistrationPaymentModel.objects.filter(
        registration_fee__patient_type='new',
        date=today
    ).count()

    new_patients_week = RegistrationPaymentModel.objects.filter(
        registration_fee__patient_type='new',
        date__gte=week_start
    ).count()

    new_patients_month = RegistrationPaymentModel.objects.filter(
        registration_fee__patient_type='new',
        date__gte=month_start
    ).count()

    # Calculate growth percentages (comparing this month to last month)
    last_month_start = (month_start - timedelta(days=1)).replace(day=1)
    last_month_end = month_start - timedelta(days=1)

    old_patients_last_month = RegistrationPaymentModel.objects.filter(
        registration_fee__patient_type='old',
        date__gte=last_month_start,
        date__lte=last_month_end
    ).count()

    new_patients_last_month = RegistrationPaymentModel.objects.filter(
        registration_fee__patient_type='new',
        date__gte=last_month_start,
        date__lte=last_month_end
    ).count()

    # Calculate growth percentages
    old_patients_growth = calculate_growth_percentage(old_patients_month, old_patients_last_month)
    new_patients_growth = calculate_growth_percentage(new_patients_month, new_patients_last_month)

    # Age group statistics
    age_groups = calculate_age_groups()

    # Recent registrations for chart data (last 7 days)
    registration_chart_data = get_registration_chart_data()

    # Monthly registration trends (last 12 months)
    monthly_trends = get_monthly_trends()

    # Gender distribution for pie chart
    gender_distribution = [
        {'name': 'Male', 'value': male_patients},
        {'name': 'Female', 'value': female_patients}
    ]

    # Revenue statistics
    total_revenue = RegistrationPaymentModel.objects.filter(
        registration_status='completed'
    ).aggregate(Sum('amount'))['amount__sum'] or 0

    revenue_today = RegistrationPaymentModel.objects.filter(
        registration_status='completed',
        date=today
    ).aggregate(Sum('amount'))['amount__sum'] or 0

    revenue_month = RegistrationPaymentModel.objects.filter(
        registration_status='completed',
        date__gte=month_start
    ).aggregate(Sum('amount'))['amount__sum'] or 0

    return {
        'total_patients': total_patients,
        'male_patients': male_patients,
        'female_patients': female_patients,
        'pending_registrations': pending_registrations,
        'old_patients_total': old_patients_total,
        'new_patients_total': new_patients_total,
        'old_patients_today': old_patients_today,
        'old_patients_week': old_patients_week,
        'old_patients_month': old_patients_month,
        'new_patients_today': new_patients_today,
        'new_patients_week': new_patients_week,
        'new_patients_month': new_patients_month,
        'old_patients_growth': old_patients_growth,
        'new_patients_growth': new_patients_growth,
        'age_groups': age_groups,
        'registration_chart_data': json.dumps(registration_chart_data),
        'monthly_trends': json.dumps(monthly_trends),
        'gender_distribution': json.dumps(gender_distribution),
        'total_revenue': total_revenue,
        'revenue_today': revenue_today,
        'revenue_month': revenue_month,
    }


@login_required
def dashboard(request):
    """
    Comprehensive patient dashboard with statistics and analytics
    """
    context = get_patient_dashboard_context(request)
    return render(request, 'admin_site/dashboard.html', context)


class SiteInfoCreateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, CreateView):
    model = SiteInfoModel
    form_class = SiteInfoForm
    permission_required = 'admin_site.add_siteinfomodel'
    success_message = 'Site Information Created Successfully'
    template_name = 'admin_site/site_info/create.html'

    def dispatch(self, *args, **kwargs):
        site_info = SiteInfoModel.objects.first()
        if not site_info:
            return super().dispatch(*args, **kwargs)
        else:
            return redirect(reverse('site_info_edit', kwargs={'pk': site_info.pk}))

    def get_success_url(self):
        return reverse('site_info_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['mode'] = 'create'
        return context


class SiteInfoDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = SiteInfoModel
    permission_required = 'admin_site.view_siteinfomodel'
    template_name = 'admin_site/site_info/detail.html'
    context_object_name = "site_info"

    def dispatch(self, request, *args, **kwargs):
        site_info = SiteInfoModel.objects.first()
        if site_info:
            if str(self.kwargs.get('pk')) != str(site_info.id):
                return redirect(reverse('site_info_detail', kwargs={'pk': site_info.pk}))
            return super().dispatch(request, *args, **kwargs)
        else:
            messages.info(request, "No site info found. Please create one first.")
            return redirect(reverse('site_info_create'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['mode'] = 'detail'
        return context


class SiteInfoUpdateView(LoginRequiredMixin, PermissionRequiredMixin, SuccessMessageMixin, UpdateView):
    model = SiteInfoModel
    form_class = SiteInfoForm
    permission_required = 'admin_site.change_siteinfomodel'
    success_message = 'Site Information Updated Successfully'
    template_name = 'admin_site/site_info/create.html'

    def get_success_url(self):
        return reverse('site_info_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['site_info'] = self.object
        context['mode'] = 'update'
        return context


def user_sign_in_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(request, username=username, password=password)
        if user is not None:
            intended_route = request.POST.get('next')
            if not intended_route:
                intended_route = request.GET.get('next')

            remember_me = request.POST.get('remember_me')
            if not remember_me:
                remember_me = request.GET.get('remember_me')

            if user.is_superuser:
                login(request, user)
                messages.success(request, 'welcome back {}'.format(user.username.title()))
                if remember_me:
                    request.session.set_expiry(3600 * 24 * 30)
                else:
                    request.session.set_expiry(0)
                if intended_route:
                    return redirect(intended_route)
                return redirect(reverse('admin_dashboard'))
            try:
                user_role = StaffProfileModel.objects.get(user=user)
            except StaffProfileModel.DoesNotExist:
                messages.error(request, 'Unknown Identity, Access Denied')
                return redirect(reverse('login'))

            if user_role.staff:
                login(request, user)
                messages.success(request, 'welcome back {}'.format(user_role.staff))
                if remember_me:
                    request.session.set_expiry(3600 * 24 * 30)
                else:
                    request.session.set_expiry(0)
                if intended_route:
                    return redirect(intended_route)
                return redirect(reverse('admin_dashboard'))

            else:
                messages.error(request, 'Unknown Identity, Access Denied')
                return redirect(reverse('login'))
        else:
            messages.error(request, 'Invalid Credentials')
            return redirect(reverse('login'))

    return render(request, 'admin_site/user/sign_in.html')


def user_sign_out_view(request):
    logout(request)
    return redirect(reverse('login'))
