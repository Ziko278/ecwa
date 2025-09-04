import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from human_resource.models import StaffModel, StaffProfileModel
from django.contrib.auth.models import User
# from communication.models import RecentActivityModel
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

logger = logging.getLogger(__name__)


@receiver(post_save, sender=StaffModel)
def create_staff_account(sender, instance, created, **kwargs):
    try:
        staff = instance
        if created and staff.position and staff.position.staff_login:
            username = staff.staff_id
            password = User.objects.make_random_password(length=8)
            email = staff.email

            user = User.objects.create_user(username=username, password=password)
            if email:
                user.email = email
            user.save()

            user_profile = StaffProfileModel.objects.create(user=user, staff=staff)
            user_profile.save()
            # send the staff their login credential via email
            if email and staff.position.staff_login:
                # Prepare the context for rendering the email template
                context = {
                    'staff_name': staff.__str__(),
                    'username': username,
                    'password': password,
                    'login_url': 'https://ecwa.name.ng/portal/sign-in',
                }

                # Render the HTML version of the email
                html_content = render_to_string('human_resource/email/staff_credential_email.html', context)

                # Create a simple plain text message as a fallback
                text_content = (f"Hello {staff.__str__()}, your new account has been created. "
                                f"Please open this email in an HTML-compatible client to view your credentials.")

                # Send the email using send_mail with the html_message parameter
                send_mail(
                    subject='Your New Staff Account Credentials',
                    message=text_content,  # Plain text fallback
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False,
                    html_message=html_content
                )

            if staff.group:
                staff.group.user_set.add(user)

    except Exception:
        logger.exception("create_staff_account signal failed for staff id=%s", getattr(instance, 'id', 'unknown'))
