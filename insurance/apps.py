from django.apps import AppConfig


class InsuranceConfig(AppConfig):
    name = "insurance"  # your app label, adjust if different

    def ready(self):
        from . import signals
        signals.connect_signals()
