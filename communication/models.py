from django.db import models
from django.conf import settings


# -------------------- INTERNAL MESSAGING --------------------

class Message(models.Model):
    subject = models.CharField(max_length=200)
    content = models.TextField()
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='sent_messages', on_delete=models.CASCADE)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='received_messages', on_delete=models.CASCADE)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    is_deleted_by_sender = models.BooleanField(default=False)
    is_deleted_by_recipient = models.BooleanField(default=False)
    parent_message = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)  # For replies
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender.username} to {self.recipient.username}: {self.subject}"

    class Meta:
        ordering = ['-created_at']


class GroupMessage(models.Model):
    """Messages to multiple recipients (departments, groups)"""
    subject = models.CharField(max_length=200)
    content = models.TextField()
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='sent_group_messages', on_delete=models.CASCADE)
    recipients = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='received_group_messages')
    department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True,
                                   blank=True)  # Send to whole department
    is_urgent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Group: {self.subject} by {self.sender.username}"

    class Meta:
        ordering = ['-created_at']


class GroupMessageRead(models.Model):
    """Track who read group messages"""
    group_message = models.ForeignKey(GroupMessage, related_name='read_by', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['group_message', 'user']


# -------------------- EXTERNAL EMAIL --------------------

class EmailTemplate(models.Model):
    """Email templates for common communications"""
    name = models.CharField(max_length=100)
    subject = models.CharField(max_length=200)
    content = models.TextField()
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class EmailLog(models.Model):
    """Log of all emails sent to external recipients"""
    STATUS_CHOICES = [
        ('SENT', 'Sent'),
        ('FAILED', 'Failed'),
        ('PENDING', 'Pending'),
    ]

    to_email = models.EmailField()
    to_name = models.CharField(max_length=200, blank=True)
    subject = models.CharField(max_length=200)
    content = models.TextField()
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    department = models.ForeignKey('Department', on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    template_used = models.ForeignKey(EmailTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Email to {self.to_email}: {self.subject}"

    class Meta:
        ordering = ['-created_at']


# -------------------- NOTIFICATION SYSTEM --------------------

class Notification(models.Model):
    """System notifications for users"""
    NOTIFICATION_TYPES = [
        ('INFO', 'Information'),
        ('WARNING', 'Warning'),
        ('ALERT', 'Alert'),
        ('REMINDER', 'Reminder'),
        ('APPROVAL', 'Approval Required'),
        ('SYSTEM', 'System'),
    ]

    PRIORITY_LEVELS = [
        ('LOW', 'Low'),
        ('NORMAL', 'Normal'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]

    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='INFO')
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='NORMAL')
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='notifications', on_delete=models.CASCADE)
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='sent_notifications',
                               on_delete=models.SET_NULL, null=True, blank=True)
    department = models.ForeignKey('Department', on_delete=models.CASCADE, null=True, blank=True)

    # Action links (optional)
    action_url = models.CharField(max_length=500, blank=True)  # Link to related page
    action_text = models.CharField(max_length=100, blank=True)  # Button text

    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.recipient.username}"

    class Meta:
        ordering = ['-created_at']


class NotificationSettings(models.Model):
    """User preferences for notifications"""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, related_name='notification_settings',
                                on_delete=models.CASCADE)
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    browser_notifications = models.BooleanField(default=True)

    # Specific notification preferences
    low_stock_alerts = models.BooleanField(default=True)
    maintenance_reminders = models.BooleanField(default=True)
    approval_requests = models.BooleanField(default=True)
    system_announcements = models.BooleanField(default=True)

    def __str__(self):
        return f"Settings for {self.user.username}"


# -------------------- ANNOUNCEMENTS --------------------

class Announcement(models.Model):
    """Hospital-wide or department announcements"""
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    department = models.ForeignKey('Department', on_delete=models.CASCADE, null=True,
                                   blank=True)  # Null = hospital-wide
    is_urgent = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        scope = self.department.name if self.department else "Hospital-wide"
        return f"{scope}: {self.title}"

    class Meta:
        ordering = ['-created_at']


class AnnouncementRead(models.Model):
    """Track who read announcements"""
    announcement = models.ForeignKey(Announcement, related_name='read_by', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['announcement', 'user']


# -------------------- REFERENCE MODEL --------------------

class Department(models.Model):
    """Department model (should match your HR app)"""
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    head = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


# -------------------- SIGNALS FOR AUTO-NOTIFICATIONS --------------------

from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=Message)
def create_message_notification(sender, instance, created, **kwargs):
    """Auto-create notification when new message is received"""
    if created:
        Notification.objects.create(
            title=f"New Message: {instance.subject}",
            message=f"You have a new message from {instance.sender.get_full_name()}",
            notification_type='INFO',
            recipient=instance.recipient,
            sender=instance.sender,
            action_url=f"/messages/{instance.id}/",
            action_text="Read Message"
        )


@receiver(post_save, sender=GroupMessage)
def create_group_message_notifications(sender, instance, created, **kwargs):
    """Auto-create notifications for group message recipients"""
    if created:
        # Create notifications for all recipients
        notifications = []
        for recipient in instance.recipients.all():
            notifications.append(
                Notification(
                    title=f"Group Message: {instance.subject}",
                    message=f"New group message from {instance.sender.get_full_name()}",
                    notification_type='INFO' if not instance.is_urgent else 'ALERT',
                    priority='URGENT' if instance.is_urgent else 'NORMAL',
                    recipient=recipient,
                    sender=instance.sender,
                    department=instance.department,
                    action_url=f"/group-messages/{instance.id}/",
                    action_text="Read Message"
                )
            )
        Notification.objects.bulk_create(notifications)


@receiver(post_save, sender=Announcement)
def create_announcement_notifications(sender, instance, created, **kwargs):
    """Auto-create notifications for announcements"""
    if created and instance.is_active:
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # Get target users
        if instance.department:
            # Department-specific announcement
            users = User.objects.filter(profile__department=instance.department, is_active=True)
        else:
            # Hospital-wide announcement
            users = User.objects.filter(is_active=True)

        notifications = []
        for user in users:
            notifications.append(
                Notification(
                    title=f"Announcement: {instance.title}",
                    message=instance.content[:200] + "..." if len(instance.content) > 200 else instance.content,
                    notification_type='ALERT' if instance.is_urgent else 'INFO',
                    priority='HIGH' if instance.is_urgent else 'NORMAL',
                    recipient=user,
                    sender=instance.created_by,
                    department=instance.department,
                    action_url=f"/announcements/{instance.id}/",
                    action_text="Read Announcement"
                )
            )
        Notification.objects.bulk_create(notifications)