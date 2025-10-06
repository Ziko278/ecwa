from django.db.models.signals import post_save
from django.dispatch import receiver
from pharmacy.models import DrugStockModel


@receiver(post_save, sender=DrugStockModel)
def update_drug_selling_price_on_stock_creation(sender, instance, created, **kwargs):
    """
    Listens for a new DrugStockModel creation and updates the parent DrugModel's
    selling price if it's different.
    """
    # This logic only runs when a new record is created.
    if created:
        # Assuming the ForeignKey from DrugStockModel to DrugModel is named 'drug'
        drug = instance.drug

        # Using Decimal is safer for currency comparisons than float
        stock_selling_price = instance.selling_price
        drug_selling_price = drug.selling_price

        # Check if the prices are different
        if stock_selling_price != drug_selling_price:
            drug.selling_price = stock_selling_price

            # Use update_fields to be more efficient and to avoid triggering
            # other potential signals on the DrugModel unnecessarily.
            drug.save(update_fields=['selling_price'])