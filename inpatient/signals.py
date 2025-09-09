from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Surgery
from .views import get_inpatient_settings

# Assuming these are the correct paths to your order models
from pharmacy.models import DrugOrderModel
from laboratory.models import LabTestOrderModel
from scan.models import ScanOrderModel


@receiver(post_save, sender=Surgery)
def create_orders_from_surgery_package(sender, instance, created, **kwargs):
    """
    When a new Surgery is created, automatically create drug, lab, and scan orders
    based on the items in the associated SurgeryType package.
    """
    if created and instance.status == 'scheduled':
        surgery_type = instance.surgery_type
        settings = get_inpatient_settings()

        # Create Drug Orders if enabled
        if settings.compile_surgery_drugs:
            for item in surgery_type.surgerydrug_set.filter(is_optional=False):
                DrugOrderModel.objects.get_or_create(
                    patient=instance.patient,
                    drug=item.drug,
                    surgery=instance,
                    defaults={
                        'quantity_ordered': item.quantity,
                        'dosage_instructions': item.timing,
                        'ordered_by': instance.created_by,
                        'status': 'pending',
                        'admission': instance.admission
                    }
                )

        # Create Lab Test Orders if enabled
        if settings.compile_surgery_labs:
            for item in surgery_type.surgerylab_set.filter(is_optional=False):
                LabTestOrderModel.objects.get_or_create(
                    patient=instance.patient,
                    template=item.lab,
                    surgery=instance,
                    defaults={
                        'ordered_by': instance.created_by,
                        'status': 'pending',
                        'source': 'doctor',
                        'admission': instance.admission
                    }
                )

        # Create Scan Orders if enabled
        if settings.compile_surgery_scans:
            for item in surgery_type.surgeryscan_set.filter(is_optional=False):
                ScanOrderModel.objects.get_or_create(
                    patient=instance.patient,
                    template=item.scan,
                    surgery=instance,
                    defaults={
                        'ordered_by': instance.created_by,
                        'status': 'pending',
                        'clinical_indication': f"For {surgery_type.name}",
                        'admission': instance.admission
                    }
                )
