from django.core.management.base import BaseCommand
from app.models.finance import CashFlow, DailyCashSummary
from app.models.transactions import StoreLocation
from django.db.models import Sum
from datetime import date, timedelta

class Command(BaseCommand):
    help = 'Generate daily cash summaries for all stores.'

    def handle(self, *args, **kwargs):
        today = date.today()
        for store in StoreLocation.objects.all():
            # Get previous day's closing
            prev_summary = DailyCashSummary.objects.filter(store=store, date=today - timedelta(days=1)).first()
            opening = prev_summary.closing_balance if prev_summary else 0

            # Sum today's cash flows
            inflows = CashFlow.objects.filter(store=store, date=today, amount__gt=0).aggregate(total=Sum('amount'))['total'] or 0
            outflows = CashFlow.objects.filter(store=store, date=today, amount__lt=0).aggregate(total=Sum('amount'))['total'] or 0

            calculated = opening + inflows + outflows  # outflows are negative

            summary, created = DailyCashSummary.objects.update_or_create(
                store=store, date=today,
                defaults={
                    'opening_balance': opening,
                    'calculated_balance': calculated,
                    'closing_balance': calculated,  # or set from manual cash count
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created summary for {store} on {today}"))
            else:
                self.stdout.write(self.style.SUCCESS(f"Updated summary for {store} on {today}"))
