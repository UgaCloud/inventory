from django.apps import AppConfig


class AppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'

    def ready(self):
        import app.signals.stock_signals
        import app.signals.sales_signals
        import app.signals.transfer_signals
