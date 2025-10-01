from datetime import timedelta
import json
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.views.decorators.http import require_http_methods
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
from django.views.decorators.cache import never_cache
import logging

logger = logging.getLogger(__name__)


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


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def change_password_view(request):
    """
    View to handle password change for authenticated users.
    Validates current password and updates to new password.
    """

    if request.method == 'POST':
        # Get form data
        current_password = request.POST.get('current_password', '').strip()
        new_password1 = request.POST.get('new_password1', '').strip()
        new_password2 = request.POST.get('new_password2', '').strip()

        # Validation
        errors = []

        # Check if all fields are provided
        if not current_password:
            errors.append("Current password is required.")

        if not new_password1:
            errors.append("New password is required.")

        if not new_password2:
            errors.append("Password confirmation is required.")

        # Check if new passwords match
        if new_password1 and new_password2 and new_password1 != new_password2:
            errors.append("New passwords do not match.")

        # Check password length and complexity
        if new_password1 and len(new_password1) < 8:
            errors.append("New password must be at least 8 characters long.")

        # Check if new password is different from current
        if current_password and new_password1 and current_password == new_password1:
            errors.append("New password must be different from current password.")

        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'admin_site/user/change_password.html')

        # Verify current password
        user = authenticate(username=request.user.username, password=current_password)
        if user is None:
            messages.error(request, "Current password is incorrect.")
            logger.warning(
                f"Failed password change attempt for user {request.user.username} - incorrect current password")
            return render(request, 'admin_site/user/change_password.html')

        try:
            # Change password
            user.set_password(new_password1)
            user.save()

            # Keep user logged in after password change
            update_session_auth_hash(request, user)

            messages.success(request, "Your password has been successfully changed!")
            logger.info(f"Password successfully changed for user {request.user.username}")

            # Redirect to dashboard or profile page
            return redirect('admin_dashboard')  # Change this to your desired redirect URL

        except Exception as e:
            logger.exception(f"Error changing password for user {request.user.username}: {str(e)}")
            messages.error(request, "An error occurred while changing your password. Please try again.")
            return render(request, 'admin_site/user/change_password.html')

    # GET request - show the form
    return render(request, 'admin_site/user/change_password.html')


def custom_404_view(request, exception):
    """
    Handles Page Not Found errors (404).

    It checks if the URL path contains 'portal' to decide whether to show
    the admin error page or the public website error page.
    """
    # Get the path of the URL that could not be found
    path = request.path

    # Check if the path starts with '/portal/'. This is more specific
    # than just checking if 'portal' is in the path.
    if path.startswith('/portal/'):
        # If it's a portal URL, render the admin-themed 404 page
        template_name = 'admin_site/errors/404.html'
    else:
        # Otherwise, render the public website's 404 page
        template_name = 'website/errors/404.html'

    return render(request, template_name, status=404)


def custom_500_view(request):
    """
    Handles Server Errors (500).
    Django calls this view when there's a server-side crash.
    """
    return render(request, 'errors/500.html', status=500)


def custom_403_view(request, exception):
    """
    Handles Permission Denied errors (403).
    This is triggered when a user tries to access a resource they don't have permission for.
    """
    return render(request, 'admin_site/errors/403.html', status=403)


def custom_csrf_failure_view(request, reason=""):
    """
    Handles CSRF verification failures.
    This is a special case handled via settings.py.
    """
    return render(request, 'admin_site/errors/403_csrf.html', status=403)

