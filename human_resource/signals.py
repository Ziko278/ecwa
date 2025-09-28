import logging
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from human_resource.models import StaffModel, StaffProfileModel
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
import secrets
import string

logger = logging.getLogger(__name__)


@receiver(post_save, sender=StaffModel)
def create_staff_account(sender, instance, created, **kwargs):
    """
    Create user account and send credentials when staff is created.
    Only runs when a new staff is created (not on updates).
    """
    # Only proceed if this is a new staff creation
    if not created:
        return

    staff = instance

    # Check if position allows staff login
    if not (staff.position and staff.position.staff_login):
        logger.info(f"Staff {staff.staff_id} position doesn't require login - skipping user creation")
        return

    # Check if user profile already exists (defensive check)
    if StaffProfileModel.objects.filter(staff=staff).exists():
        logger.warning(f"User profile already exists for staff {staff.staff_id}")
        return

    try:
        # Use atomic transaction to ensure data consistency
        with transaction.atomic():
            # Generate credentials
            username = staff.staff_id
            alphabet = string.ascii_letters + string.digits

            # 2. Generate a cryptographically strong password (e.g., 8 characters).
            password = ''.join(secrets.choice(alphabet) for i in range(8))

            # Handle username conflicts
            original_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{original_username}_{counter}"
                counter += 1
                if counter > 100:  # Safety break
                    username = f"{original_username}_{int(timezone.now().timestamp())}"
                    break

            # Create user
            user = User.objects.create_user(
                username=username,
                password=password,
                email=staff.email or '',
                first_name=staff.first_name,
                last_name=staff.last_name
            )

            # Create staff profile
            StaffProfileModel.objects.create(user=user, staff=staff)

            # Add to group if specified
            if staff.group:
                staff.group.user_set.add(user)

            logger.info(f"Successfully created user account '{username}' for staff {staff.staff_id}")

            # Send credentials email
            if staff.email:
                send_staff_credentials_email(staff, username, password)
            else:
                logger.warning(f"No email for staff {staff.staff_id} - credentials not sent")

    except Exception as e:
        logger.exception(f"Failed to create user account for staff {staff.staff_id}: {str(e)}")
        # Note: In production, you might want to send admin notifications here


def send_staff_credentials_email(staff, username, password):
    """
    Send login credentials to staff email.
    Separated for better error handling and testing.
    """
    try:
        context = {
            'staff_name': str(staff),
            'username': username,
            'password': password,
            'login_url': getattr(settings, 'STAFF_LOGIN_URL', 'https://ecmckaru.com.ng/portal/sign-in'),
            'support_email': getattr(settings, 'SUPPORT_EMAIL', 'info@ecmckaru.com.ng'),
        }

        # Render both HTML and plain text versions
        html_content = render_to_string('human_resource/email/staff_credential_email.html', context)
        text_content = render_to_string('human_resource/email/staff_credential_email.txt', context)

        send_mail(
            subject='Your New Staff Account Credentials - Action Required',
            message=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[staff.email],
            fail_silently=False,
            html_message=html_content
        )

        logger.info(f"Credentials email sent to {staff.email} for staff {staff.staff_id}")

    except Exception as e:
        logger.exception(f"Failed to send credentials email to {staff.email}: {str(e)}")
        # Email failure shouldn't break user creation