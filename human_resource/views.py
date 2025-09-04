import logging
import random
import string

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.models import Permission, Group, User
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models.functions import Lower
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.timezone import now
from django.views.generic import (
    CreateView, ListView, UpdateView, DeleteView, DetailView, TemplateView
)

from admin_site.utility import state_list
from human_resource.forms import (
    DepartmentForm, PositionForm, StaffForm, HRSettingForm, GroupForm, StaffDocumentForm, StaffLeaveForm, HODForm
)
from human_resource.models import (
    DepartmentModel, PositionModel, StaffModel, HRSettingModel, StaffProfileModel, StaffDocumentModel, StaffLeaveModel,
    HODModel
)

logger = logging.getLogger(__name__)


# -------------------------
# Utility helpers
# -------------------------
def get_hr_setting_instance():
    """Return the singleton HRSettingModel instance (or None)."""
    return HRSettingModel.objects.first()


def _send_credentials_email(staff, username, password):
    """
    Renders an HTML template and sends credentials email.
    Returns True on success, False on failure.
    """
    try:
        # Prepare the context for rendering the email template
        context = {
            'staff_name': staff.__str__(),
            'username': username,
            'password': password,
            'login_url': 'https://ecwa.name.ng/portal/sign-in',  # Your actual login URL
        }

        # Render the HTML version of the email from the template
        html_content = render_to_string('human_resource/email/staff_credential_email.html', context)

        # Create a simple plain text message as a fallback for email clients that don't support HTML
        text_content = (f"Hello {staff.__str__()},\n\nYour staff portal account has been created/updated.\n"
                        f"Username: {username}\nPassword: {password}\n\n"
                        f"Please login at {context['login_url']} and change your password immediately.")

        # Send the email using send_mail with the html_message parameter
        send_mail(
            subject="Staff Portal Credentials Update",
            message=text_content,  # Plain text fallback
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[staff.email],
            fail_silently=False,
            html_message=html_content  # The HTML version
        )
        return True
    except Exception:
        logger.exception("Failed to send credentials email to %s", staff.email)
        return False


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
                label = form.fields.get(field).label if form.fields.get(field) else field
                for error in errors:
                    messages.error(self.request, f"{label}: {error}")
        except Exception:
            logger.exception("Error while processing form_invalid errors.")
            messages.error(self.request, "There was an error processing the form. Please try again.")
        return redirect(self.get_success_url())


class StaffContextMixin:
    """Mixin to ensure HR settings exist and add common staff context."""
    def dispatch(self, request, *args, **kwargs):
        hr_setting = get_hr_setting_instance()
        if not hr_setting:
            messages.error(request, 'Update staff setting before creating a staff')
            return redirect(reverse('human_resource_setting_create'))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['department_list'] = DepartmentModel.objects.all().order_by('name')
        context['staff_setting'] = get_hr_setting_instance()
        context['state_list'] = state_list
        return context


# -------------------------
# Department Views
# -------------------------
class DepartmentCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    CreateView
):
    model = DepartmentModel
    permission_required = 'human_resource.add_departmentmodel'
    form_class = DepartmentForm
    template_name = 'human_resource/department/index.html'
    success_message = 'Department Successfully Registered'

    def get_success_url(self):
        return reverse('department_index')

    def dispatch(self, request, *args, **kwargs):
        # Keep original behavior: redirect GET to index
        if request.method == 'GET':
            return redirect(reverse('department_index'))
        return super().dispatch(request, *args, **kwargs)


class DepartmentListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = DepartmentModel
    permission_required = 'human_resource.view_departmentmodel'
    template_name = 'human_resource/department/index.html'
    context_object_name = "department_list"

    def get_queryset(self):
        return DepartmentModel.objects.all().order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = DepartmentForm()
        return context


class DepartmentUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
):
    model = DepartmentModel
    permission_required = 'human_resource.change_departmentmodel'
    form_class = DepartmentForm
    template_name = 'human_resource/department/index.html'
    success_message = 'Department Successfully Updated'

    def get_success_url(self):
        return reverse('department_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('department_index'))
        return super().dispatch(request, *args, **kwargs)


class DepartmentDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = DepartmentModel
    permission_required = 'human_resource.view_departmentmodel'
    template_name = 'human_resource/department/detail.html'
    context_object_name = "department"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        department = self.object

        # Staff list in this department
        staff_qs = StaffModel.objects.filter(
            department=department
        ).select_related(
            "position", "group"
        ).order_by("position__name", "first_name")

        # Current and past HOD assignments
        hod_history = HODModel.objects.filter(
            department=department
        ).select_related("hod", "deputy_hod").order_by("-start_date")

        # Add all context pieces
        context.update({
            "hod_form": HODForm(),
            "staff_list": staff_qs,
            "active_hod": hod_history.filter(status="active").first(),
            "past_hod_list": hod_history.filter(status="past"),
            "total_staff": staff_qs.count(),
            "positions": PositionModel.objects.filter(department=department).order_by("name"),
        })
        return context


class DepartmentDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = DepartmentModel
    permission_required = 'human_resource.delete_departmentmodel'
    template_name = 'human_resource/department/delete.html'
    context_object_name = "department"
    success_message = 'Department Successfully Deleted'

    def get_success_url(self):
        return reverse('department_index')


def multi_department_action(request):
    """
    Handle bulk actions on departments (e.g., delete).
    Uses transaction.atomic to avoid partial deletes.
    """
    if request.method == 'POST':
        department_ids = request.POST.getlist('department')
        action = request.POST.get('action')

        if not department_ids:
            messages.error(request, 'No department selected.')
            return redirect(reverse('department_index'))

        try:
            with transaction.atomic():
                departments = DepartmentModel.objects.filter(id__in=department_ids)
                if action == 'delete':
                    # count is number of deleted objects (including related)
                    count, _ = departments.delete()
                    messages.success(request, f'Successfully deleted {count} department(s).')
                else:
                    messages.error(request, 'Invalid request.')
        except Exception:
            logger.exception("Bulk department action failed for ids=%s action=%s", department_ids, action)
            messages.error(request, "An error occurred performing that action. Try again or contact admin.")
        return redirect(reverse('department_index'))

    # GET - confirm action
    department_ids = request.GET.getlist('department')
    if not department_ids:
        messages.error(request, 'No department selected.')
        return redirect(reverse('department_index'))

    action = request.GET.get('action')
    context = {'department_list': DepartmentModel.objects.filter(id__in=department_ids)}

    if action == 'delete':
        return render(request, 'human_resource/department/multi_delete.html', context)

    messages.error(request, 'Invalid request.')
    return redirect(reverse('department_index'))


def assign_hod(request, pk):
    department = get_object_or_404(DepartmentModel, pk=pk)

    if request.method == "POST":
        form = HODForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # End current active HOD before assigning new one
                    current_hod = HODModel.objects.filter(
                        department=department, status="active"
                    ).last()

                    if current_hod:
                        current_hod.status = "past"
                        current_hod.end_date = now().date()
                        current_hod.save()

                    new_hod = form.save(commit=False)
                    new_hod.department = department
                    new_hod.save()

                messages.success(request, "HOD successfully assigned.")
            except Exception as e:
                messages.error(request, f"Error assigning HOD: {str(e)}")
        else:
            first_error = next(iter(form.errors.values()))[0]
            messages.error(request, f"Error assigning HOD: {first_error}")

    return redirect("department_detail", pk=department.id)


# -------------------------
# Position Views
# -------------------------
class PositionCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, CreateView
):
    model = PositionModel
    permission_required = 'human_resource.add_positionmodel'
    form_class = PositionForm
    template_name = 'human_resource/position/index.html'
    success_message = 'Position Successfully Created'

    def get_success_url(self):
        return reverse('position_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('position_index'))
        return super().dispatch(request, *args, **kwargs)


class PositionListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = PositionModel
    permission_required = 'human_resource.view_positionmodel'
    template_name = 'human_resource/position/index.html'
    context_object_name = 'position_list'

    def get_queryset(self):
        return PositionModel.objects.all().order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = PositionForm()
        context['department_list'] = DepartmentModel.objects.all().order_by('name')
        return context


class PositionUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
):
    model = PositionModel
    permission_required = 'human_resource.change_positionmodel'
    form_class = PositionForm
    template_name = 'human_resource/position/index.html'
    success_message = 'Position Successfully Updated'

    def get_success_url(self):
        return reverse('position_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('position_index'))
        return super().dispatch(request, *args, **kwargs)


class PositionDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = PositionModel
    permission_required = 'human_resource.delete_positionmodel'
    template_name = 'human_resource/position/delete.html'
    context_object_name = 'position'
    success_message = 'Position Successfully Deleted'

    def get_success_url(self):
        return reverse('position_index')


# -------------------------
# Staff Views
# -------------------------
class StaffCreateView(
    LoginRequiredMixin, PermissionRequiredMixin,
    StaffContextMixin, CreateView
):
    model = StaffModel
    permission_required = 'human_resource.add_staffmodel'
    form_class = StaffForm
    template_name = 'human_resource/staff/create.html'
    success_message = 'Staff Successfully Registered'

    def get_success_url(self):
        return reverse('staff_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        # Set created_by field defensively
        try:
            form.instance.created_by = getattr(self.request, 'user', None)
        except Exception:
            logger.exception("Failed to set created_by on staff form_valid")
        return super().form_valid(form)


class StaffListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = StaffModel
    permission_required = 'human_resource.view_staffmodel'
    template_name = 'human_resource/staff/index.html'
    context_object_name = "staff_list"

    def get_queryset(self):
        return StaffModel.objects.all().order_by(Lower('first_name'))


class StaffDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = StaffModel
    permission_required = 'human_resource.view_staffmodel'
    template_name = 'human_resource/staff/detail.html'
    context_object_name = "staff"


class StaffUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    StaffContextMixin, UpdateView
):
    model = StaffModel
    permission_required = 'human_resource.change_staffmodel'
    form_class = StaffForm
    template_name = 'human_resource/staff/edit.html'
    success_message = 'Staff Information Successfully Updated'

    def get_success_url(self):
        return reverse('staff_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['staff'] = self.object
        return context


class StaffDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = StaffModel
    permission_required = 'human_resource.delete_staffmodel'
    template_name = 'human_resource/staff/delete.html'
    context_object_name = "staff"
    success_message = 'Staff Successfully Deleted'

    def get_success_url(self):
        return reverse('staff_index')


def get_position_levels(request):
    position_id = request.GET.get('position_id')
    if not position_id:
        return JsonResponse({'error': 'position_id is required'}, status=400)

    try:
        position = PositionModel.objects.get(id=position_id)
    except PositionModel.DoesNotExist:
        return JsonResponse({'error': 'Position not found'}, status=404)
    except Exception:
        logger.exception("Failed fetching position in get_position_levels for id=%s", position_id)
        return JsonResponse({'error': 'Internal error'}, status=500)

    # Safely handle if position has no 'levels' relation
    if hasattr(position, 'levels'):
        levels = position.levels.all().values('id', 'name')
    else:
        levels = []

    return JsonResponse({'levels': list(levels)})


class StaffFingerPrintCaptureView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    model = StaffModel
    permission_required = 'human_resource.change_staffmodel'
    template_name = 'human_resource/staff/finger_print.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['staff'] = get_object_or_404(StaffModel, pk=self.kwargs.get('pk'))
        return context


# -------------------------
# HR Setting Views
# -------------------------
class HRSettingCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = HRSettingModel
    form_class = HRSettingForm
    permission_required = 'human_resource.change_hrsettingmodel'
    success_message = 'Human Resource Setting Created Successfully'
    template_name = 'human_resource/setting/create.html'

    def dispatch(self, request, *args, **kwargs):
        setting = get_hr_setting_instance()
        if setting:
            return redirect('human_resource_setting_edit', pk=setting.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('human_resource_setting_detail', kwargs={'pk': self.object.pk})


class HRSettingDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = HRSettingModel
    permission_required = 'human_resource.view_hrsettingmodel'
    template_name = 'human_resource/setting/detail.html'
    context_object_name = "human_resource_setting"

    def get_object(self):
        return get_hr_setting_instance()


class HRSettingUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
):
    model = HRSettingModel
    form_class = HRSettingForm
    permission_required = 'human_resource.change_hrsettingmodel'
    success_message = 'Human Resource Setting Updated Successfully'
    template_name = 'human_resource/setting/create.html'

    def get_object(self):
        return get_hr_setting_instance()

    def get_success_url(self):
        return reverse('human_resource_setting_detail', kwargs={'pk': self.object.pk})


# -------------------------
# Group Views & Permissions
# -------------------------
class GroupCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, CreateView
):
    model = Group
    permission_required = 'auth.add_group'
    form_class = GroupForm
    template_name = 'human_resource/group/list.html'
    success_message = 'Group Added Successfully'

    def get_success_url(self):
        return reverse('group_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('group_index'))
        return super().dispatch(request, *args, **kwargs)


class GroupListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Group
    permission_required = 'auth.add_group'
    template_name = 'human_resource/group/index.html'
    context_object_name = "group_list"

    def get_queryset(self):
        return Group.objects.all().order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = GroupForm
        return context


class GroupDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Group
    permission_required = 'auth.add_group'
    template_name = 'human_resource/group/detail.html'
    context_object_name = "group"


class GroupUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
):
    model = Group
    permission_required = 'auth.add_group'
    form_class = GroupForm
    template_name = 'human_resource/group/index.html'
    success_message = 'Group Successfully Updated'

    def get_success_url(self):
        return reverse('group_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('group_index'))
        return super().dispatch(request, *args, **kwargs)


class GroupPermissionView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Group
    permission_required = 'auth.add_group'
    form_class = GroupForm
    template_name = 'human_resource/group/permission.html'
    success_message = 'Group Permission Successfully Updated'

    def get_success_url(self):
        return reverse('group_index')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['group'] = self.object
        context['permission_list'] = Permission.objects.all()
        return context


@login_required
@permission_required("auth.add_group", raise_exception=True)
def group_permission_view(request, pk):
    group = get_object_or_404(Group, pk=pk)
    if request.method == 'POST':
        permissions = request.POST.getlist('permissions[]')
        permission_list = []
        for permission_code in permissions:
            permission = Permission.objects.filter(codename=permission_code).first()
            if permission:
                permission_list.append(permission.id)
        try:
            group.permissions.set(permission_list)
            messages.success(request, 'Group Permission Successfully Updated')
        except Exception:
            logger.exception("Failed updating group permissions for group id=%s", pk)
            messages.error(request, "Failed to update group permissions. Contact admin.")
        return redirect(reverse('group_index'))

    context = {
        'group': group,
        'permission_codenames': group.permissions.all().values_list('codename', flat=True),
        'permission_list': Permission.objects.all(),
    }
    return render(request, 'human_resource/group/permission.html', context)


class GroupDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Group
    permission_required = 'auth.add_group'
    template_name = 'human_resource/group/delete.html'
    context_object_name = "group"

    def get_success_url(self):
        return reverse('group_index')

    def dispatch(self, request, *args, **kwargs):
        # Prevent deleting protected groups by name (e.g., superadmin)
        try:
            if request.POST.get('name') in ['superadmin']:
                messages.error(request, 'Restricted Group, Permission Denied')
                return redirect(reverse('group_index'))
        except Exception:
            # If we can't read POST safely, log and continue to default dispatch
            logger.exception("Error checking protected group during GroupDeleteView.dispatch")
        return super().dispatch(request, *args, **kwargs)


# -------------------------
# Enable/Disable Staff and Credentials
# -------------------------
def disable_staff(request, staff_id):
    try:
        staff = get_object_or_404(StaffModel, id=staff_id)

        if staff.status == 'inactive':
            messages.info(request, f"{staff} is already disabled.")
        else:
            staff.status = 'inactive'
            staff.save(update_fields=['status'])

            profile = getattr(staff, 'staff_profile', None)
            if profile and getattr(profile, 'user', None):
                profile.user.is_active = False
                profile.user.save(update_fields=['is_active'])

            messages.success(request, f"{staff} has been disabled successfully.")
    except Exception:
        logger.exception("Error disabling staff id=%s", staff_id)
        messages.error(request, "An error occurred while disabling staff. Contact administrator.")
    return redirect(reverse('staff_detail', kwargs={'pk': staff_id}))


def enable_staff(request, staff_id):
    try:
        staff = get_object_or_404(StaffModel, id=staff_id)

        if staff.status == 'active':
            messages.info(request, f"{staff} is already active.")
        else:
            staff.status = 'active'
            staff.save(update_fields=['status'])

            profile = getattr(staff, 'staff_profile', None)
            if profile and getattr(profile, 'user', None):
                profile.user.is_active = True
                profile.user.save(update_fields=['is_active'])

            messages.success(request, f"{staff} has been enabled successfully.")
    except Exception:
        logger.exception("Error enabling staff id=%s", staff_id)
        messages.error(request, "An error occurred while enabling staff. Contact administrator.")
    return redirect(reverse('staff_detail', kwargs={'pk': staff_id}))


def generate_staff_login(request, staff_id):
    staff = get_object_or_404(StaffModel, id=staff_id)
    try:
        if hasattr(staff, 'staff_profile') and getattr(staff.staff_profile, 'user', None):
            messages.warning(request, f"{staff} already has login credentials.")
            return redirect(reverse('staff_detail', kwargs={'pk': staff_id}))

        if not staff.email:
            messages.error(request, "Staff has no email on record; cannot create login.")
            return redirect(reverse('staff_detail', kwargs={'pk': staff_id}))

        username = staff.staff_id or (staff.first_name.lower() + str(staff.id))
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))

        with transaction.atomic():
            try:
                user = User.objects.create_user(username=username, email=staff.email, password=password)
            except IntegrityError:
                # username conflict: try fallback
                username = f"{username}_{random.randint(1000,9999)}"
                user = User.objects.create_user(username=username, email=staff.email, password=password)

            StaffProfileModel.objects.create(user=user, staff=staff)

        sent = _send_credentials_email(staff.email, username, password)
        if sent:
            messages.success(request, f"Login created and credentials emailed to {staff.email}.")
        else:
            messages.success(request, f"Login created. Credentials could not be emailed; contact admin to view credentials.")
    except Exception:
        logger.exception("Error generating login for staff id=%s", staff_id)
        messages.error(request, "Error generating login. Contact administrator.")
    return redirect(reverse('staff_detail', kwargs={'pk': staff_id}))


def update_staff_login(request, staff_id):
    staff = get_object_or_404(StaffModel, id=staff_id)
    try:
        profile = getattr(staff, 'staff_profile', None)
        if not profile or not getattr(profile, 'user', None):
            messages.error(request, f"{staff} has no login to update.")
            return redirect(reverse('staff_detail', kwargs={'pk': staff_id}))

        if not staff.email:
            messages.error(request, "Staff has no email on record; cannot update credentials.")
            return redirect(reverse('staff_detail', kwargs={'pk': staff_id}))

        new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        user = profile.user
        user.set_password(new_password)
        user.save(update_fields=['password'])

        sent = _send_credentials_email(staff.email, user.username, new_password)
        if sent:
            messages.success(request, f"New credentials sent to {staff.email}.")
        else:
            messages.success(request, "Password updated. Credentials could not be emailed; contact admin to view credentials.")
    except Exception:
        logger.exception("Error updating credentials for staff id=%s", staff_id)
        messages.error(request, "Error updating credentials. Contact administrator.")
    return redirect(reverse('staff_detail', kwargs={'pk': staff_id}))


# ---------------------------------------------------------------------
# Staff Document Views
# ---------------------------------------------------------------------
class StaffDocumentCreateView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    FlashFormErrorsMixin,
    CreateView
):
    model = StaffDocumentModel
    form_class = StaffDocumentForm
    template_name = "human_resource/staff/document_form.html"  # create a small modal/partial if desired
    permission_required = "human_resource.add_staffdocumentmodel"

    def get_success_url(self):
        # Redirect back to staff detail where documents are listed
        return reverse("staff_detail", kwargs={"pk": self.object.staff.pk})

    def form_valid(self, form):
        """
        - If the logged-in user has an associated staff profile and is NOT a privileged user,
          force the document to be attached to their staff record (so users without rights can't
          upload documents for other staff).
        - Privileged users (with add permission anyway) may upload for any staff by selecting staff in the form.
        """
        try:
            profile = getattr(self.request.user, "user_staff_profile", None)
            # If the user has a staff profile and the request doesn't indicate admin intent, lock to self.staff
            if profile and not self.request.user.has_perm("human_resource.change_staffmodel"):
                form.instance.staff = profile.staff

            # set uploader
            form.instance.uploaded_by = getattr(self.request.user, "id", None) and self.request.user

            # Save inside transaction to avoid partial writes
            with transaction.atomic():
                return super().form_valid(form)
        except Exception:
            logger.exception("Error saving staff document")
            messages.error(self.request, "An error occurred while uploading the document. Try again or contact admin.")
            return redirect(self.get_success_url())


class StaffDocumentUpdateView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    FlashFormErrorsMixin,
    UpdateView
):
    model = StaffDocumentModel
    form_class = StaffDocumentForm
    template_name = "human_resource/staff/document_form.html"
    permission_required = "human_resource.change_staffdocumentmodel"

    def get_success_url(self):
        return reverse("staff_detail", kwargs={"pk": self.object.staff.pk})

    def dispatch(self, request, *args, **kwargs):
        """
        Ownership check: allow update if:
        - request.user is uploader OR
        - request.user is the staff owner OR
        - request.user has staff change permission (privileged)
        """
        self.object = self.get_object()
        try:
            profile = getattr(request.user, "user_staff_profile", None)
            is_owner_staff = profile and profile.staff.pk == self.object.staff.pk
            is_uploader = getattr(self.object.uploaded_by, "pk", None) == getattr(request.user, "pk", None)
            is_privileged = request.user.has_perm("human_resource.change_staffdocumentmodel") or request.user.has_perm("human_resource.change_staffmodel")

            if not (is_owner_staff or is_uploader or is_privileged):
                messages.error(request, "You do not have permission to edit this document.")
                return redirect(self.get_success_url())
        except Exception:
            logger.exception("Error checking document update permissions")
            messages.error(request, "Permission check failed. Contact admin.")
            return redirect(self.get_success_url())

        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        # update uploaded_by when privileged user modifies the document
        try:
            form.instance.uploaded_by = getattr(self.request.user, "id", None) and self.request.user
            with transaction.atomic():
                return super().form_valid(form)
        except Exception:
            logger.exception("Error updating staff document")
            messages.error(self.request, "An error occurred while updating the document. Contact admin.")
            return redirect(self.get_success_url())


class StaffDocumentDeleteView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    DeleteView
):
    model = StaffDocumentModel
    permission_required = "human_resource.delete_staffdocumentmodel"
    template_name = "human_resource/staff/document_confirm_delete.html"  # small confirm modal

    def get_success_url(self):
        # Redirect back to staff detail page
        # self.object is available in DeleteView only after get_object; override delete to capture pk
        return reverse("staff_detail", kwargs={"pk": self.kwargs.get("staff_pk")})

    def dispatch(self, request, *args, **kwargs):
        # Accept staff_pk in URL for redirect safety; ensure object.staff.pk matches passed staff_pk
        try:
            self.object = self.get_object()
            # ownership check similar to update
            profile = getattr(request.user, "user_staff_profile", None)
            is_owner_staff = profile and profile.staff.pk == self.object.staff.pk
            is_uploader = getattr(self.object.uploaded_by, "pk", None) == getattr(request.user, "pk", None)
            is_privileged = request.user.has_perm("human_resource.delete_staffdocumentmodel") or request.user.has_perm("human_resource.change_staffmodel")

            if not (is_owner_staff or is_uploader or is_privileged):
                messages.error(request, "You do not have permission to delete this document.")
                return redirect(reverse("staff_detail", kwargs={"pk": self.object.staff.pk}))
        except Exception:
            logger.exception("Error checking document delete permissions")
            messages.error(request, "Permission check failed. Contact admin.")
            return redirect(reverse("staff_index"))

        return super().dispatch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        try:
            self.object = self.get_object()
            staff_pk = self.object.staff.pk
            # Optionally remove file from storage: self.object.document.delete(save=False)
            self.object.delete()
            messages.success(request, "Document deleted successfully.")
            return redirect(reverse("staff_detail", kwargs={"pk": staff_pk}))
        except Exception:
            logger.exception("Error deleting staff document")
            messages.error(request, "An error occurred while deleting the document. Contact admin.")
            return redirect(reverse("staff_detail", kwargs={"pk": self.object.staff.pk if getattr(self, 'object', None) else kwargs.get('staff_pk')}))


# ---------------------------------------------------------------------
# Staff Leave Views
# ---------------------------------------------------------------------
class StaffLeaveCreateView(LoginRequiredMixin, FlashFormErrorsMixin, CreateView):
    model = StaffLeaveModel
    form_class = StaffLeaveForm
    template_name = "human_resource/leave/form.html"
    # permission: any logged-in user can apply for leave (self). privileged users can apply for others if they have permission.
    # To restrict applying for others, we check change_staffmodel perm below.

    def get_success_url(self):
        # Redirect to staff detail for the staff the leave belongs to (or to leave list for admin)
        return reverse("staff_detail", kwargs={"pk": self.object.staff.pk})

    def get_initial(self):
        initial = super().get_initial()
        # If the requester has a staff_profile and is not privileged, preselect staff
        profile = getattr(self.request.user, "user_staff_profile", None)
        if profile and not self.request.user.has_perm("human_resource.change_staffmodel"):
            initial["staff"] = profile.staff.pk
        return initial

    def form_valid(self, form):
        try:
            profile = getattr(self.request.user, "user_staff_profile", None)

            # If user has staff_profile and is NOT privileged, force "staff" to their staff record
            if profile and not self.request.user.has_perm("human_resource.change_staffmodel"):
                form.instance.staff = profile.staff

            # applied_by is the current user (if available)
            form.instance.applied_by = getattr(self.request.user, "id", None) and self.request.user

            # Ensure initial status/approval_status are consistent
            form.instance.status = "pending"
            form.instance.approval_status = "pending"

            with transaction.atomic():
                return super().form_valid(form)
        except Exception:
            logger.exception("Error creating leave application")
            messages.error(self.request, "An error occurred while applying for leave. Contact admin.")
            # If form invalid or exception, redirect safely back to the staff list or staff detail
            # Try to redirect back to staff detail if staff provided
            staff_pk = form.cleaned_data.get("staff").pk if form.cleaned_data.get("staff") else None
            if staff_pk:
                return redirect(reverse("staff_detail", kwargs={"pk": staff_pk}))
            return redirect(reverse("staff_index"))


class StaffLeaveUpdateView(LoginRequiredMixin, FlashFormErrorsMixin, UpdateView):
    model = StaffLeaveModel
    form_class = StaffLeaveForm
    template_name = "human_resource/leave/form.html"

    def get_success_url(self):
        return reverse("staff_detail", kwargs={"pk": self.object.staff.pk})

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        # Only allow update if leave is not yet approved and not declined/rejected.
        try:
            profile = getattr(request.user, "user_staff_profile", None)
            is_staff_owner = profile and profile.staff.pk == self.object.staff.pk
            is_applier = getattr(self.object.applied_by, "pk", None) == getattr(request.user, "pk", None)
            is_privileged = request.user.has_perm("human_resource.change_staffleavemodel") or request.user.has_perm("human_resource.change_staffmodel")

            # Allowed to edit if privilege OR (owner/applier AND not declined)
            if not is_privileged:
                if not (is_staff_owner or is_applier):
                    messages.error(request, "You do not have permission to edit this leave.")
                    return redirect(self.get_success_url())

                # If leave is declined/rejected, disallow edits
                if self.object.status.lower() in ("rejected", "declined"):
                    messages.error(request, "Cannot edit a declined leave. Please create a fresh application.")
                    return redirect(self.get_success_url())

            return super().dispatch(request, *args, **kwargs)
        except Exception:
            logger.exception("Error during leave update permission check")
            messages.error(request, "Permission check failed. Contact admin.")
            return redirect(self.get_success_url())

    def form_valid(self, form):
        try:
            # After an update by the owner, set it back to pending so approvers re-evaluate
            form.instance.status = "pending"
            form.instance.approval_status = "pending"
            # preserve applied_by if already set else set to current user
            if not form.instance.applied_by:
                form.instance.applied_by = getattr(self.request.user, "id", None) and self.request.user

            with transaction.atomic():
                return super().form_valid(form)
        except Exception:
            logger.exception("Error updating leave")
            messages.error(self.request, "An error occurred while updating this leave. Contact admin.")
            return redirect(self.get_success_url())


class StaffLeaveListView(LoginRequiredMixin, ListView):
    """
    List leaves for the currently logged-in staff (their own leaves).
    If the user has no staff profile, show empty list and a helpful message.
    """
    model = StaffLeaveModel
    template_name = "human_resource/leave/my_leaves.html"
    context_object_name = "leave_list"

    def get_queryset(self):
        profile = getattr(self.request.user, "user_staff_profile", None)
        if not profile:
            return StaffLeaveModel.objects.none()
        return StaffLeaveModel.objects.filter(staff=profile.staff).order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Provide a form to quickly create a leave if desired
        context["form"] = StaffLeaveForm(initial={"staff": getattr(self.request.user.user_staff_profile, "staff", None)})
        return context


class LeaveApprovalListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    List pending leaves for approvers (HR/admin staff).
    """
    model = StaffLeaveModel
    template_name = "human_resource/leave/pending_list.html"
    context_object_name = "pending_leaves"
    permission_required = "human_resource.change_staffleavemodel"

    def get_queryset(self):
        return StaffLeaveModel.objects.filter(status="pending").order_by("start_date")


class AllLeaveListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    Admin view to see all leaves.
    """
    model = StaffLeaveModel
    template_name = "human_resource/leave/all_leaves.html"
    context_object_name = "all_leaves"
    permission_required = "human_resource.view_staffleavemodel"

    def get_queryset(self):
        return StaffLeaveModel.objects.all().order_by("-created_at")


# Approve / Decline actions (POST)
@login_required
@permission_required("human_resource.change_staffleavemodel", raise_exception=True)
def approve_leave(request, pk):
    leave = get_object_or_404(StaffLeaveModel, pk=pk)
    try:
        if leave.status == "approved":
            messages.info(request, "Leave is already approved.")
            return redirect(reverse("leave_approval_list"))

        # approve
        leave.status = "approved"
        leave.approval_status = "approved"
        leave.approved_by = request.user
        # set approved_days if not set
        if not leave.approved_days:
            leave.approved_days = leave.applied_days
        leave.save(update_fields=["status", "approval_status", "approved_by", "approved_days"])
        messages.success(request, f"Leave for {leave.staff} approved.")
    except Exception:
        logger.exception("Error approving leave id=%s", pk)
        messages.error(request, "An error occurred while approving the leave. Contact admin.")
    return redirect(reverse("leave_approval_list"))


@login_required
@permission_required("human_resource.change_staffleavemodel", raise_exception=True)
def decline_leave(request, pk):
    leave = get_object_or_404(StaffLeaveModel, pk=pk)
    try:
        if leave.status == "rejected":
            messages.info(request, "Leave is already declined.")
            return redirect(reverse("leave_approval_list"))

        leave.status = "rejected"
        leave.approval_status = "rejected"
        leave.approved_by = request.user
        leave.save(update_fields=["status", "approval_status", "approved_by"])
        messages.success(request, f"Leave for {leave.staff} has been declined.")
    except Exception:
        logger.exception("Error declining leave id=%s", pk)
        messages.error(request, "An error occurred while declining the leave. Contact admin.")
    return redirect(reverse("leave_approval_list"))
