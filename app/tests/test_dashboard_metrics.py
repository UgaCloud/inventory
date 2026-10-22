"""
Dashboard metric tests.

The dashboards used to render placeholder numbers: fixed percentages on the
badges, empty chart series and labels that did not describe the figure they
sat next to. These tests pin the real behaviour:

* every headline number is computed from the tenant's own rows;
* the month-over-month badges compare against real history, and say so when
  there is no baseline to compare against;
* the chart series are aligned and derived from real sales/purchases;
* the quick actions only offer shortcuts the signed-in user may open;
* the dashboard tabs carry their icon as metadata instead of the template
  guessing it from the dashboard name.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from app.managers import clear_tenant_actor, set_tenant_actor
from app.models.customers import Customer
from app.models.expense import Expense
from app.models.human_resource import Role, UserProfile
from app.models.products import (
    Category, Inventory, Product, ProductUnitPrice, StoreLocation, UnitOfMeasure,
)
from app.models.sales_return import SalesReturn
from app.models.suppliers import Supplier
from app.models.tenancy import Business
from app.models.transactions import (
    InventoryBatch, PurchaseOrder, Sales, SalesItem, StockMovement,
)
from app.selectors import dashboard_selectors as metrics
from app.utils.dashboard_assignment import get_dashboard_info_for_modules
from app.utils.module_mapping import get_quick_actions, user_has_module_access

User = get_user_model()

ALL_MODULES = list(range(1, 17))


def month_bounds(anchor):
    first = anchor.replace(day=1)
    if first.month == 12:
        nxt = first.replace(year=first.year + 1, month=1)
    else:
        nxt = first.replace(month=first.month + 1)
    return first, nxt - timedelta(days=1)


class DashboardTestBase(TestCase):
    """One business with a store, a product, a customer and a user."""

    def setUp(self):
        self.today = date.today()
        self.month_start, self.month_end = month_bounds(self.today)
        self.last_month_anchor = self.month_start - timedelta(days=1)
        self.last_month_start, self.last_month_end = month_bounds(
            self.last_month_anchor
        )

        self.business = Business.objects.create(name='Dashboard Traders')
        self.store = StoreLocation.objects.create(
            name='Main Store', business=self.business, is_default=True,
        )
        self.category = Category.objects.create(name='General')
        self.product = Product.objects.create(
            name='Widget', sku='WID-1', category=self.category,
            business=self.business,
        )
        self.unit = UnitOfMeasure.objects.create(name='Piece', abbreviation='pc')
        ProductUnitPrice.objects.create(
            product=self.product, unit=self.unit, conversion_factor=1, price=100,
        )
        self.customer = Customer.objects.create(
            name='Jane Buyer', phone='0700', business=self.business,
        )
        self.supplier = Supplier.objects.create(name='Acme Supplies')

        self.user = self.make_user('dash_admin', ALL_MODULES)

    def tearDown(self):
        clear_tenant_actor()

    def make_user(self, username, module_ids):
        user = User.objects.create_user(
            username=username, password='pw12345678',
            email=f'{username}@example.com',
        )
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.business = self.business
        profile.is_platform_admin = False
        profile.save()

        role = Role.objects.create(
            name=f'{username} role', business=self.business, is_system_role=True,
        )
        role.set_modules(module_ids)
        profile.roles.add(role)
        profile.refresh_from_db()
        return user

    # -- helpers ---------------------------------------------------------
    def make_sale(self, receipt_no, total, received=0, sale_date=None,
                  customer=None, recorded_by=None, cancelled=False):
        sale = Sales.objects.create(
            receipt_no=receipt_no,
            store=self.store,
            status='FULFILLED',
            recorded_by=recorded_by or self.user,
            total_amount=total,
            amount_received=received,
            amount_paid=received,
            balance=total - received,
            customer=customer,
            is_cancelled=cancelled,
        )
        if sale_date is not None:
            Sales.objects.filter(pk=sale.pk).update(sale_date=sale_date)
            sale.refresh_from_db()
        return sale

    def make_expense(self, amount, expense_date=None, description='Expense'):
        expense = Expense.objects.create(
            store=self.store,
            amount=Decimal(str(amount)),
            description=description,
            user=self.user.username,
        )
        if expense_date is not None:
            Expense.objects.filter(pk=expense.pk).update(date=expense_date)
            expense.refresh_from_db()
        return expense

    def make_purchase(self, total, purchase_date=None):
        order = PurchaseOrder.objects.create(
            supplier=self.supplier,
            store=self.store,
            status='COMPLETED',
            recorded_by=self.user.username,
            total_cost=Decimal(str(total)),
        )
        if purchase_date is not None:
            PurchaseOrder.objects.filter(pk=order.pk).update(
                purchase_date=purchase_date
            )
            order.refresh_from_db()
        return order

    def ensure_stock(self, units=100, reorder_level=5):
        """Put stock on the shelf so a sale does not go negative."""
        inventory, _ = Inventory.objects.get_or_create(
            product=self.product, store=self.store,
            defaults={'quantity_in_stock': units, 'reorder_level': reorder_level},
        )
        return inventory

    def make_sale_item(self, sale, quantity, price=100):
        self.ensure_stock()
        return SalesItem.objects.create(
            order=sale, product=self.product, unit=self.unit,
            quantity=quantity, sale_price=price,
        )


class SalesDashboardMetricTests(DashboardTestBase):
    """The sales dashboard numbers come from the sales ledger."""

    def test_totals_match_the_rows_that_exist(self):
        self.make_sale('S-1', 100_000, received=100_000, sale_date=self.today)
        self.make_sale('S-2', 50_000, received=0, sale_date=self.today)

        data = metrics.get_sales_dashboard_metrics(self.user, today=self.today)

        self.assertEqual(data['total_outstanding_balances'], 50_000)
        self.assertEqual(data['today_credit_count'], 1)
        self.assertEqual(data['todays_credit_sales'], 50_000)
        self.assertEqual(data['today_payment_percentage'], 66.7)
        self.assertEqual(data['todays_unpaid_sales']['count'], 1)
        self.assertEqual(data['todays_unpaid_sales']['total_amount'], 50_000)

    def test_cancelled_sales_are_excluded(self):
        self.make_sale('S-CANCELLED', 999_999, received=999_999,
                       sale_date=self.today, cancelled=True)

        data = metrics.get_sales_dashboard_metrics(self.user, today=self.today)

        self.assertEqual(data['total_outstanding_balances'], 0)
        self.assertEqual(data['monthly_sales'], 0)

    def test_todays_cards_only_count_the_signed_in_users_own_sales(self):
        other = self.make_user('dash_other', ALL_MODULES)
        self.make_sale('S-MINE', 10_000, received=10_000, sale_date=self.today)
        self.make_sale('S-THEIRS', 90_000, received=90_000, sale_date=self.today,
                       recorded_by=other)

        data = metrics.get_sales_dashboard_metrics(self.user, today=self.today)

        # "Today" is personal, business-wide figures stay business-wide.
        self.assertEqual(data['today_payment_percentage'], 100.0)
        self.assertEqual(data['monthly_sales'], 100_000)

    def test_overdue_payments_are_listed_with_their_age(self):
        old = self.today - timedelta(days=45)
        self.make_sale('S-OLD', 30_000, received=0, sale_date=old,
                       customer=self.customer)

        data = metrics.get_sales_dashboard_metrics(self.user, today=self.today)

        self.assertEqual(len(data['overdue_payments']), 1)
        self.assertEqual(data['total_overdue_amount'], 30_000)
        self.assertEqual(data['overdue_payments'][0]['days_overdue'], 45)
        self.assertEqual(data['overdue_payments'][0]['customer'], 'Jane Buyer')

    def test_recent_sales_are_not_overdue(self):
        self.make_sale('S-NEW', 30_000, received=0, sale_date=self.today)

        data = metrics.get_sales_dashboard_metrics(self.user, today=self.today)

        self.assertEqual(data['overdue_payments'], [])
        self.assertEqual(data['total_overdue_amount'], 0)

    def test_collection_rate_is_the_real_ratio_not_a_goal(self):
        self.make_sale('S-M', 200_000, received=50_000, sale_date=self.today)

        data = metrics.get_sales_dashboard_metrics(self.user, today=self.today)

        self.assertEqual(data['monthly_sales'], 200_000)
        self.assertEqual(data['monthly_payments'], 50_000)
        self.assertEqual(data['collection_target_percentage'], 25.0)
        self.assertEqual(data['collection_progress'], 25.0)

    def test_payment_efficiency_counts_fully_paid_sales(self):
        self.make_sale('S-PAID', 10_000, received=10_000, sale_date=self.today)
        self.make_sale('S-PART', 10_000, received=4_000, sale_date=self.today)

        data = metrics.get_sales_dashboard_metrics(self.user, today=self.today)

        self.assertEqual(data['payment_efficiency'], 50.0)

    def test_empty_business_reports_zeroes_not_placeholders(self):
        data = metrics.get_sales_dashboard_metrics(self.user, today=self.today)

        self.assertEqual(data['total_outstanding_balances'], 0)
        self.assertEqual(data['monthly_sales'], 0)
        self.assertEqual(data['collection_target_percentage'], 0)
        self.assertEqual(data['payment_efficiency'], 0)
        self.assertEqual(data['average_days_outstanding'], 0)
        self.assertEqual(data['top_outstanding_customers'], [])

    def test_top_outstanding_customers_are_ordered_by_balance(self):
        rich = Customer.objects.create(name='Wealthy', business=self.business)
        rich.balance = Decimal('9000')
        rich.save()
        self.customer.balance = Decimal('500')
        self.customer.save()

        data = metrics.get_sales_dashboard_metrics(self.user, today=self.today)

        self.assertEqual(data['top_outstanding_customers'][0]['name'], 'Wealthy')
        self.assertEqual(data['customers_with_balance'], 2)


class StoresDashboardMetricTests(DashboardTestBase):
    """The stores dashboard numbers come from the stock ledger."""

    def test_low_stock_counts_inventory_at_or_below_reorder_level(self):
        Inventory.objects.create(
            product=self.product, store=self.store,
            quantity_in_stock=5, reorder_level=10,
        )

        data = metrics.get_stores_dashboard_metrics(self.user, today=self.today)

        self.assertEqual(data['low_stock_count'], 1)

    def test_stock_sold_today_counts_the_sale_lines(self):
        sale = self.make_sale('S-1', 100_000, received=100_000,
                              sale_date=self.today)
        # Adding the line recalculates the sale total from its items, so the
        # line price is chosen to keep the receipt at 100,000.
        self.make_sale_item(sale, quantity=4, price=25_000)

        data = metrics.get_stores_dashboard_metrics(self.user, today=self.today)

        self.assertEqual(data['stock_sold_today'], 4)
        self.assertEqual(data['sales_count_today'], 1)
        self.assertEqual(data['today_sales'], 100_000)
        self.assertEqual(data['top_moving_products'][0]['product__name'], 'Widget')
        self.assertEqual(data['top_moving_products'][0]['total_sold'], 4)

    def test_stock_received_today_counts_inbound_movements(self):
        StockMovement.objects.create(
            product=self.product, store=self.store, transaction_type='In',
            quantity=25, units_in_stock=25, user=self.user.username,
        )

        data = metrics.get_stores_dashboard_metrics(self.user, today=self.today)

        self.assertEqual(data['stock_received_today'], 25)

    def test_outbound_movements_are_not_counted_as_received(self):
        StockMovement.objects.create(
            product=self.product, store=self.store, transaction_type='Out',
            quantity=-25, units_in_stock=0, user=self.user.username,
        )

        data = metrics.get_stores_dashboard_metrics(self.user, today=self.today)

        self.assertEqual(data['stock_received_today'], 0)

    def test_inventory_value_uses_the_remaining_batch_quantity(self):
        InventoryBatch.objects.create(
            product=self.product, store=self.store, quantity=10, unit_cost=500,
            remaining_quantity=4,
        )

        data = metrics.get_stores_dashboard_metrics(self.user, today=self.today)

        self.assertEqual(data['total_inventory_value'], 2000)

    def test_turnover_is_units_sold_over_units_in_stock(self):
        self.ensure_stock(units=20, reorder_level=2)
        sale = self.make_sale('S-1', 100_000, received=100_000,
                              sale_date=self.today)
        self.make_sale_item(sale, quantity=5)

        data = metrics.get_stores_dashboard_metrics(self.user, today=self.today)

        # Five units sold against the fifteen left on the shelf.
        self.assertEqual(data['stock_turnover_rate'], 0.33)

    def test_low_stock_raises_a_critical_alert(self):
        Inventory.objects.create(
            product=self.product, store=self.store,
            quantity_in_stock=1, reorder_level=10,
        )

        data = metrics.get_stores_dashboard_metrics(self.user, today=self.today)

        titles = [alert['title'] for alert in data['critical_alerts']]
        self.assertIn('Low stock', titles)

    def test_a_store_without_any_movement_raises_an_alert(self):
        data = metrics.get_stores_dashboard_metrics(self.user, today=self.today)

        titles = [alert['title'] for alert in data['critical_alerts']]
        self.assertIn('No stock movement today', titles)

    def test_default_store_is_reported(self):
        data = metrics.get_stores_dashboard_metrics(self.user, today=self.today)

        self.assertEqual(data['current_store'], self.store)

    def test_recent_activities_merge_sales_and_stock_movements(self):
        self.make_sale('S-1', 100_000, received=100_000, sale_date=self.today)
        StockMovement.objects.create(
            product=self.product, store=self.store, transaction_type='In',
            quantity=3, units_in_stock=3, user=self.user.username,
        )

        activities = metrics.get_recent_activities()
        types = {activity['type'] for activity in activities}

        self.assertTrue(activities)
        self.assertIn('sale', types)
        self.assertIn('transfer', types)


class ChartSeriesTests(DashboardTestBase):
    """The charts are fed by real series, not by empty placeholder arrays."""

    def test_sales_vs_purchases_series_has_one_point_per_day(self):
        self.make_sale('S-1', 100_000, received=100_000, sale_date=self.today)
        self.make_purchase(50_000, purchase_date=self.today)

        series = metrics.get_sales_vs_purchases_series(days=30, today=self.today)

        self.assertEqual(len(series['labels']), 30)
        self.assertEqual(len(series['sales']), 30)
        self.assertEqual(len(series['purchases']), 30)
        self.assertEqual(series['sales'][-1], 100_000)
        self.assertEqual(series['purchases'][-1], 50_000)

    def test_days_without_activity_are_zero(self):
        series = metrics.get_sales_vs_purchases_series(days=7, today=self.today)

        self.assertEqual(set(series['sales']), {0})
        self.assertEqual(set(series['purchases']), {0})

    def test_revenue_vs_expenses_series_covers_the_last_twelve_months(self):
        self.make_sale('S-1', 100_000, received=100_000, sale_date=self.today)
        self.make_expense(25_000, expense_date=self.today)

        series = metrics.get_revenue_vs_expenses_series(months=12,
                                                        today=self.today)

        self.assertEqual(len(series['labels']), 12)
        self.assertEqual(series['revenue'][-1], 100_000)
        self.assertEqual(series['expenses'][-1], 25_000)

    def test_customer_split_separates_first_time_from_returning(self):
        self.make_sale('S-1', 100_000, received=100_000, sale_date=self.today,
                       customer=self.customer)
        self.make_sale('S-2', 50_000, received=50_000, sale_date=self.today,
                       customer=self.customer)

        split = metrics.get_customer_split(today=self.today)

        self.assertEqual(split['labels'], ['First Time', 'Return'])
        self.assertEqual(split['data'], [100_000, 50_000])


class MonthOverMonthTests(DashboardTestBase):
    """The change badges compare against real history."""

    def test_growth_is_reported_as_a_percentage(self):
        self.make_sale('S-THIS', 150_000, received=150_000,
                       sale_date=self.today)
        self.make_sale('S-LAST', 100_000, received=100_000,
                       sale_date=self.last_month_start)

        data = metrics.get_month_over_month(today=self.today)

        self.assertEqual(data['sales'], 150_000)
        self.assertEqual(data['prev_sales'], 100_000)
        self.assertEqual(data['sales_change_pct'], 50.0)

    def test_no_baseline_reports_none_instead_of_a_fake_percentage(self):
        self.make_sale('S-THIS', 150_000, received=150_000,
                       sale_date=self.today)

        data = metrics.get_month_over_month(today=self.today)

        self.assertEqual(data['prev_sales'], 0)
        self.assertIsNone(data['sales_change_pct'])

    def test_expenses_and_profit_use_the_same_windows(self):
        self.make_sale('S-THIS', 150_000, received=150_000,
                       sale_date=self.today)
        self.make_expense(50_000, expense_date=self.today)
        self.make_sale('S-LAST', 100_000, received=100_000,
                       sale_date=self.last_month_start)
        self.make_expense(20_000, expense_date=self.last_month_start)

        data = metrics.get_month_over_month(today=self.today)

        self.assertEqual(data['expenses'], 50_000)
        self.assertEqual(data['prev_expenses'], 20_000)
        self.assertEqual(data['profit'], 100_000)
        self.assertEqual(data['prev_profit'], 80_000)
        self.assertEqual(data['profit_change_pct'], 25.0)

    def test_returns_are_counted(self):
        sale = self.make_sale('S-1', 100_000, received=100_000,
                              sale_date=self.today)
        SalesReturn.objects.create(sale=sale, amount=Decimal('5000'))

        data = metrics.get_month_over_month(today=self.today)

        self.assertEqual(data['returns_total'], 5000)


class QuickActionTests(DashboardTestBase):
    """Quick actions are permission aware."""

    def test_only_actions_the_user_may_open_are_offered(self):
        sales_only = self.make_user('dash_sales', [4])

        actions = get_quick_actions(sales_only)

        self.assertTrue(actions)
        self.assertEqual([a['label'] for a in actions], ['Record a sale'])
        self.assertTrue(actions[0]['url'])

    def test_superuser_sees_every_action(self):
        superuser = User.objects.create_superuser(
            username='dash_root', password='pw12345678',
            email='root@example.com',
        )

        actions = get_quick_actions(superuser, limit=50)

        self.assertGreater(len(actions), 8)

    def test_anonymous_user_gets_no_actions(self):
        from django.contrib.auth.models import AnonymousUser

        self.assertEqual(get_quick_actions(AnonymousUser()), [])
        self.assertEqual(get_quick_actions(None), [])

    def test_actions_without_a_known_url_are_skipped(self):
        user = self.make_user('dash_min', [4])
        broken = [
            {'label': 'Ghost', 'icon': 'ti-x', 'url_name': 'no_such_url',
             'module': 4},
        ]

        self.assertEqual(get_quick_actions(user, actions=broken), [])

    def test_module_access_matches_the_role_modules(self):
        user = self.make_user('dash_min', [4])

        self.assertTrue(user_has_module_access(user, 4))
        self.assertFalse(user_has_module_access(user, 15))


class DashboardShellTests(DashboardTestBase):
    """The dashboard shell renders the real numbers for the signed-in user."""

    def test_tabs_carry_an_icon_instead_of_a_name_lookup(self):
        info = get_dashboard_info_for_modules(ALL_MODULES)

        self.assertTrue(info)
        for entry in info:
            self.assertTrue(entry['icon'])
            self.assertTrue(entry['template'])

    def test_index_view_renders_with_the_real_metrics(self):
        self.make_sale('S-1', 100_000, received=100_000, sale_date=self.today)
        self.client.login(username=self.user.username, password='pw12345678')

        response = self.client.get(reverse('index_page'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['monthly_sales'], 100_000)
        self.assertEqual(response.context['collection_target_percentage'], 100.0)
        self.assertIn('quick_actions', response.context)
        self.assertTrue(response.context['quick_actions'])

    def test_index_view_of_a_user_without_modules_has_no_dashboards(self):
        # Module 8 (Reports) is not part of any dashboard, so the user sees
        # the honest empty state instead of a dashboard they cannot use.
        limited = self.make_user('dash_none', [8])
        self.client.login(username=limited.username, password='pw12345678')

        response = self.client.get(reverse('index_page'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['dashboard_templates'], [])

    def test_business_users_never_receive_the_admin_dashboard(self):
        limited = self.make_user('dash_sales', [4])
        self.client.login(username=limited.username, password='pw12345678')

        response = self.client.get(reverse('index_page'))

        for template in response.context['dashboard_templates']:
            self.assertNotIn('dashboards/admin.html', template)

    def test_quick_actions_on_the_page_only_link_to_reachable_pages(self):
        limited = self.make_user('dash_sales', [4])
        self.client.login(username=limited.username, password='pw12345678')

        response = self.client.get(reverse('index_page'))

        labels = [action['label'] for action in response.context['quick_actions']]
        self.assertEqual(labels, ['Record a sale'])
