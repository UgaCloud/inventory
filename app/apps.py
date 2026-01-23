from django.apps import AppConfig


class AppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'

    def ready(self):
        import app.signals.stock_signals
        import app.signals.sales_signals
        import app.signals.transfer_signals
        import app.signals.finance_signals
        import app.signals.bank_signals
        import app.signals.expense_signals
        import app.signals.transaction_signals
        import app.signals.human_resource_signals
        import app.signals.user_signals
        import app.signals.customers_signals

