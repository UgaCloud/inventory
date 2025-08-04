from django.core.management.base import BaseCommand
from django.utils import timezone
from app.models.finance import CashFlow, DailyCashSummary
from app.models.products import StoreLocation
from django.db.models import Sum

class Command(BaseCommand):
    help = 'Generate daily cash summaries for all stores.'

    def handle(self, *args, **options):
        today = timezone.now().date()
        stores = StoreLocation.objects.filter(is_active=True)
        for store in stores:
            # Opening balance: closing balance of previous day, or 0 if none
            prev_summary = DailyCashSummary.objects.filter(store=store, date=today - timezone.timedelta(days=1)).first()
            opening_balance = prev_summary.closing_balance if prev_summary else 0
            # Sum all cash flows for today
            cashflows = CashFlow.objects.filter(store=store, date=today)
            total_flow = cashflows.aggregate(total=Sum('amount'))['total'] or 0
            calculated_balance = opening_balance + total_flow
            # Closing balance: can be set to calculated_balance, or allow manual entry later
            closing_balance = calculated_balance
            summary, created = DailyCashSummary.objects.update_or_create(
                store=store, date=today,
                defaults={
                    'opening_balance': opening_balance,
                    'closing_balance': closing_balance,
                    'calculated_balance': calculated_balance,
                    'note': '',
                }
            )
            self.stdout.write(self.style.SUCCESS(
                f"Daily summary for {store} on {today}: Opening {opening_balance}, Total Flow {total_flow}, Closing {closing_balance}"
            ))
