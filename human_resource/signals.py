import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from human_resource.models import StaffModel, StaffProfileModel
from django.contrib.auth.models import User
# from communication.models import RecentActivityModel

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

            if staff.group:
                staff.group.user_set.add(user)

            category = 'staff_registration'
            subject = "{} just completed staff registration".format(staff.__str__().title())
            # recent_activity = RecentActivityModel.objects.create(category=category, subject=subject,
            #                                                      reference_id=staff.id,
            #                                                      user=staff.created_by)
            # recent_activity.save()
    except Exception:
        logger.exception("create_staff_account signal failed for staff id=%s", getattr(instance, 'id', 'unknown'))
