"""
Tests for perfume sales measured in millilitres, including mixtures.

Covers: single-perfume ml sales, mixtures of 2+ perfumes, quantity totals,
per-store inventory deduction, atomic rollback on insufficient stock,
validation of invalid quantities/prices, FIFO cost and gross profit,
cancellation restoring stock exactly once, partial-return behavior,
historical cost snapshots, ordinary sales regression, branch/store isolation,
and concurrent overselling.
"""
import threading
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TransactionTestCase

from app.models.customers import Customer, CustomerLedger
from app.models.finance import CashFlow, PaymentMethod
from app.models.products import (
    Category, Inventory, Product, ProductUnitPrice, StoreLocation, UnitOfMeasure,
)
from app.models.sales_return import SalesReturn
from app.models.transactions import InventoryBatch, Sales, SalesItem, StockMovement
from app.services.perfume_service import (
    estimate_stock_cost, get_perfume_products, record_perfume_sale,
)
from app.models.organization import Branch
from app.models.perfume import PerfumeSaleLine


class PerfumeSaleTestBase(TransactionTestCase):
    """Shared fixtures: a store, an ml unit, and product helpers."""

    def setUp(self):
        self.user = User.objects.create_user('perfumer', password='pw')
        self.store = StoreLocation.objects.create(name='Perfume Shop', is_default=True)
        self.ml = UnitOfMeasure.objects.create(name='Millilitre', abbreviation='ml')
        self.category = Category.objects.create(name='Perfumes')
        self.payment_method = PaymentMethod.objects.create(name='Cash', is_default=True)
        self.customer = Customer.objects.create(name='Walk-in Customer')

    def make_perfume(self, name, stock_ml, cost_per_ml, store=None, price_per_ml=500):
        """A perfume whose base unit is ml (CF=1) with stock and one FIFO batch."""
        store = store or self.store
        product = Product.objects.create(name=name, category=self.category)
        ProductUnitPrice.objects.create(
            product=product, unit=self.ml, conversion_factor=1, price=price_per_ml
        )
        Inventory.objects.create(
            product=product, store=store, quantity_in_stock=stock_ml, reorder_level=0
        )
        InventoryBatch.objects.create(
            product=product, store=store, quantity=stock_ml,
            remaining_quantity=stock_ml, unit_cost=cost_per_ml,
        )
        return product

    def stock_of(self, product, store=None):
        store = store or self.store
        inv = Inventory.objects.filter(product=product, store=store).first()
        return inv.quantity_in_stock if inv else 0

    def sell(self, components, price=8000, **kwargs):
        """Record a cash sale paid in full unless the test overrides it.
        (The system requires a customer whenever a balance remains, so the
        default walk-in flow pays the full price with a payment method.)
        """
        kwargs.setdefault('store', self.store)
        kwargs.setdefault('user', self.user)
        kwargs.setdefault('selling_price', price)
        kwargs.setdefault('amount_paid', int(Decimal(str(price))))
        kwargs.setdefault('payment_method', self.payment_method)
        return record_perfume_sale(components=components, **kwargs)


class SinglePerfumeSaleTests(PerfumeSaleTestBase):
    def test_single_perfume_sale_by_ml(self):
        """Scenario 1: selling one perfume by ml deducts stock and records the sale."""
        a = self.make_perfume('Oud Royale', stock_ml=100, cost_per_ml=100)

        sale = self.sell([(a, 10)], price=5000)

        self.assertEqual(self.stock_of(a), 90)
        self.assertEqual(sale.total_amount, 5000)
        line = sale.perfume_lines.get()
        self.assertEqual(line.total_quantity_ml, Decimal('10'))
        self.assertEqual(line.components.count(), 1)
        comp = line.components.get()
        self.assertEqual(comp.product, a)
        self.assertEqual(comp.quantity_ml, Decimal('10'))
        self.assertEqual(comp.base_quantity, 10)
        # Stock movement recorded for the component product
        movement = StockMovement.objects.get(product=a, transaction_id=sale.id)
        self.assertEqual(movement.transaction_type, 'OUT')
        self.assertEqual(movement.quantity, -10)
        # Financial signals still fire: cashflow exists for the sale
        self.assertTrue(CashFlow.objects.filter(reference=sale.receipt_no).exists())

    def test_perfume_products_selector(self):
        """Only active products with an ml unit are offered as perfumes."""
        a = self.make_perfume('Oud Royale', stock_ml=100, cost_per_ml=100)
        b = Product.objects.create(name='Not A Perfume')
        self.assertIn(a, list(get_perfume_products()))
        self.assertNotIn(b, list(get_perfume_products()))


class MixtureSaleTests(PerfumeSaleTestBase):
    def test_mixture_of_two_perfumes(self):
        """Scenario 2: the doc example — A 6ml + B 4ml sold for UGX 8,000."""
        a = self.make_perfume('Perfume A', stock_ml=50, cost_per_ml=200)
        b = self.make_perfume('Perfume B', stock_ml=40, cost_per_ml=250)

        sale = self.sell([(a, 6), (b, 4)], price=8000)

        self.assertEqual(self.stock_of(a), 44)
        self.assertEqual(self.stock_of(b), 36)
        line = sale.perfume_lines.get()
        self.assertTrue(line.is_mixture)
        self.assertEqual(line.total_quantity_ml, Decimal('10'))
        self.assertEqual(line.selling_price, Decimal('8000'))
        self.assertEqual(line.components.count(), 2)
        # One OUT movement per component product
        self.assertEqual(
            StockMovement.objects.filter(transaction_id=sale.id, transaction_type='OUT').count(), 2
        )
        # The mixture itself is NOT a stock item: no Inventory row, no SalesItem
        self.assertFalse(SalesItem.objects.filter(order=sale).exists())

    def test_mixture_of_three_perfumes(self):
        """Scenario 3: mixtures of 3+ perfumes work the same way."""
        a = self.make_perfume('A', stock_ml=30, cost_per_ml=100)
        b = self.make_perfume('B', stock_ml=30, cost_per_ml=100)
        c = self.make_perfume('C', stock_ml=30, cost_per_ml=100)

        sale = self.sell([(a, 5), (b, 5), (c, 5)], price=9000)

        line = sale.perfume_lines.get()
        self.assertEqual(line.components.count(), 3)
        self.assertEqual(line.total_quantity_ml, Decimal('15'))
        for p in (a, b, c):
            self.assertEqual(self.stock_of(p), 25)

    def test_total_quantity_equals_sum_of_components(self):
        """Scenario 4: the line total always equals the sum of components."""
        a = self.make_perfume('A', stock_ml=30, cost_per_ml=100)
        b = self.make_perfume('B', stock_ml=30, cost_per_ml=100)

        sale = self.sell([(a, 7), (b, 3)], price=4000)
        line = sale.perfume_lines.get()
        comp_sum = sum(comp.quantity_ml for comp in line.components.all())
        self.assertEqual(line.total_quantity_ml, comp_sum)
        self.assertEqual(line.total_quantity_ml, Decimal('10'))


class InventoryDeductionTests(PerfumeSaleTestBase):
    def test_component_deduction_uses_store_inventory(self):
        """Scenario 5: each component is deducted from the sale's store."""
        a = self.make_perfume('A', stock_ml=50, cost_per_ml=100)
        b = self.make_perfume('B', stock_ml=50, cost_per_ml=100)

        self.sell([(a, 6), (b, 4)], price=8000)

        a_inv = Inventory.objects.get(product=a, store=self.store)
        b_inv = Inventory.objects.get(product=b, store=self.store)
        self.assertEqual(a_inv.quantity_in_stock, 44)
        self.assertEqual(b_inv.quantity_in_stock, 46)
        # FIFO batches consumed too
        self.assertEqual(InventoryBatch.objects.get(product=a).remaining_quantity, 44)

    def test_insufficient_stock_rolls_back_entire_transaction(self):
        """Scenario 6: if one component is short, nothing is saved."""
        a = self.make_perfume('A', stock_ml=50, cost_per_ml=100)
        b = self.make_perfume('B', stock_ml=3, cost_per_ml=100)  # only 3 ml!
        sales_before = Sales.objects.count()

        with self.assertRaises(ValidationError) as ctx:
            self.sell([(a, 6), (b, 4)], price=8000)

        self.assertIn('Insufficient stock', str(ctx.exception))
        # Entire transaction unchanged
        self.assertEqual(Sales.objects.count(), sales_before)
        self.assertEqual(self.stock_of(a), 50)
        self.assertEqual(self.stock_of(b), 3)
        self.assertEqual(PerfumeSaleLine.objects.count(), 0)
        # No movement from the failed sale (fixture setup creates its own
        # 'Initial Stock' movements via an existing signal).
        self.assertFalse(
            StockMovement.objects.filter(note='Perfume sale').exists()
        )

    def test_no_inventory_record_is_rejected(self):
        """A perfume without inventory in the sale's store is rejected clearly."""
        orphan = Product.objects.create(name='Orphan', category=self.category)
        ProductUnitPrice.objects.create(
            product=orphan, unit=self.ml, conversion_factor=1, price=100
        )
        with self.assertRaises(ValidationError) as ctx:
            self.sell([(orphan, 5)], price=1000)
        self.assertIn('no inventory record', str(ctx.exception))

    def test_branch_store_isolation(self):
        """Scenario 13: stock is deducted only from the sale's store/branch."""
        other_branch = Branch.objects.create(name='Other Branch')
        other_store = StoreLocation.objects.create(name='Branch Shop', branch=other_branch)
        product = Product.objects.create(name='Shared', category=self.category)
        ProductUnitPrice.objects.create(
            product=product, unit=self.ml, conversion_factor=1, price=500
        )
        Inventory.objects.create(product=product, store=self.store, quantity_in_stock=50)
        Inventory.objects.create(product=product, store=other_store, quantity_in_stock=80)
        InventoryBatch.objects.create(
            product=product, store=self.store, quantity=50, remaining_quantity=50, unit_cost=100
        )
        InventoryBatch.objects.create(
            product=product, store=other_store, quantity=80, remaining_quantity=80, unit_cost=100
        )

        self.sell([(product, 10)], price=5000)

        self.assertEqual(self.stock_of(product, self.store), 40)
        self.assertEqual(self.stock_of(product, other_store), 80)


class ValidationTests(PerfumeSaleTestBase):
    """Scenario 7: invalid component quantities and prices are rejected."""

    def setUp(self):
        super().setUp()
        self.a = self.make_perfume('A', stock_ml=50, cost_per_ml=100)

    def assertRejected(self, components, price=1000, **kwargs):
        with self.assertRaises(ValidationError):
            self.sell(components, price=price, **kwargs)

    def test_empty_components_rejected(self):
        self.assertRejected([])

    def test_zero_quantity_rejected(self):
        self.assertRejected([(self.a, 0)])

    def test_negative_quantity_rejected(self):
        self.assertRejected([(self.a, -5)])

    def test_fractional_ml_rejected(self):
        self.assertRejected([(self.a, Decimal('2.5'))])

    def test_duplicate_product_rejected(self):
        self.assertRejected([(self.a, 3), (self.a, 4)])

    def test_inactive_product_rejected(self):
        self.a.is_active = False
        self.a.save()
        self.assertRejected([(self.a, 3)])

    def test_zero_price_rejected(self):
        self.assertRejected([(self.a, 3)], price=0)

    def test_negative_price_rejected(self):
        self.assertRejected([(self.a, 3)], price=-100)

    def test_fractional_price_rejected(self):
        self.assertRejected([(self.a, 3)], price=Decimal('100.5'))

    def test_balance_without_customer_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            self.sell([(self.a, 3)], price=1000, amount_paid=400)
        self.assertIn('customer', str(ctx.exception).lower())

    def test_amount_paid_exceeding_price_rejected(self):
        self.assertRejected(
            [(self.a, 3)], price=1000, amount_paid=2000, customer=self.customer,
            payment_method=self.payment_method,
        )

    def test_paid_sale_requires_payment_method(self):
        with self.assertRaises(ValidationError):
            self.sell(
                [(self.a, 3)], price=1000, amount_paid=1000,
                customer=self.customer, payment_method=None,
            )

    def test_paid_sale_with_customer_succeeds(self):
        sale = self.sell(
            [(self.a, 3)], price=1000, amount_paid=1000, customer=self.customer,
            payment_method=self.payment_method,
        )
        self.assertEqual(sale.balance, 0)


class CostingTests(PerfumeSaleTestBase):
    def test_mixture_cost_and_gross_profit(self):
        """Scenario 8: 6ml@200 + 4ml@250 = 2200 cost; 8000 price -> 5800 profit."""
        a = self.make_perfume('Perfume A', stock_ml=50, cost_per_ml=200)
        b = self.make_perfume('Perfume B', stock_ml=40, cost_per_ml=250)

        sale = self.sell([(a, 6), (b, 4)], price=8000)
        line = sale.perfume_lines.get()

        self.assertEqual(line.total_cost, Decimal('2200'))
        self.assertEqual(line.gross_profit, Decimal('5800'))
        comp_a = line.components.get(product=a)
        comp_b = line.components.get(product=b)
        self.assertEqual(comp_a.component_cost, Decimal('1200'))
        self.assertEqual(comp_b.component_cost, Decimal('1000'))
        self.assertEqual(comp_a.unit_cost, Decimal('200.0000'))

    def test_fifo_costing_across_batches(self):
        """Cost follows FIFO over batches, skipping expired ones."""
        product = Product.objects.create(name='Layered', category=self.category)
        ProductUnitPrice.objects.create(
            product=product, unit=self.ml, conversion_factor=1, price=500
        )
        Inventory.objects.create(product=product, store=self.store, quantity_in_stock=30)
        b1 = InventoryBatch.objects.create(
            product=product, store=self.store, quantity=10, remaining_quantity=10, unit_cost=100
        )
        b2 = InventoryBatch.objects.create(
            product=product, store=self.store, quantity=20, remaining_quantity=20, unit_cost=300
        )

        sale = self.sell([(product, 15)], price=9000)
        line = sale.perfume_lines.get()
        # 10 @100 + 5 @300 = 2500
        self.assertEqual(line.total_cost, Decimal('2500'))
        b1.refresh_from_db()
        b2.refresh_from_db()
        self.assertEqual(b1.remaining_quantity, 0)
        self.assertEqual(b2.remaining_quantity, 15)

    def test_historical_cost_unchanged_after_cost_change(self):
        """Scenario 11: cost/profit snapshots survive later cost changes."""
        a = self.make_perfume('A', stock_ml=50, cost_per_ml=200)
        b = self.make_perfume('B', stock_ml=40, cost_per_ml=250)

        sale = self.sell([(a, 6), (b, 4)], price=8000)
        line = sale.perfume_lines.get()

        # Change costs everywhere after the sale
        InventoryBatch.objects.filter(product=a).update(unit_cost=999)
        InventoryBatch.objects.filter(product=b).update(unit_cost=888)
        ProductUnitPrice.objects.filter(product=a).update(price=1)

        line.refresh_from_db()
        self.assertEqual(line.total_cost, Decimal('2200'))
        self.assertEqual(line.gross_profit, Decimal('5800'))
        comp = line.components.get(product=a)
        self.assertEqual(comp.unit_cost, Decimal('200.0000'))
        self.assertEqual(comp.component_cost, Decimal('1200'))


class CancellationTests(PerfumeSaleTestBase):
    def test_cancellation_restores_component_stock_exactly_once(self):
        """Scenario 9: cancel restores every component once; double cancel is safe."""
        a = self.make_perfume('A', stock_ml=50, cost_per_ml=200)
        b = self.make_perfume('B', stock_ml=40, cost_per_ml=250)

        sale = self.sell([(a, 6), (b, 4)], price=8000)
        self.assertEqual(self.stock_of(a), 44)
        self.assertEqual(self.stock_of(b), 36)

        ok, msg = sale.cancel_sale(self.user, reason='customer changed mind')
        self.assertTrue(ok, msg)

        sale.refresh_from_db()
        self.assertTrue(sale.is_cancelled)
        self.assertEqual(self.stock_of(a), 50)
        self.assertEqual(self.stock_of(b), 40)
        line = sale.perfume_lines.get()
        self.assertTrue(line.is_cancelled)
        # Cancellation movements recorded per component
        cancellations = StockMovement.objects.filter(
            transaction_id=sale.id, transaction_type='CANCELLATION'
        )
        self.assertEqual(cancellations.count(), 2)
        # Restored batches carry the historical cost snapshot (the newest
        # batch for the product is the cancellation restoration).
        restored = InventoryBatch.objects.filter(product=a).order_by('-id').first()
        self.assertEqual(restored.unit_cost, Decimal('200.0000'))
        self.assertEqual(restored.remaining_quantity, 6)

        # Second cancellation: rejected and stock NOT restored again
        ok2, msg2 = sale.cancel_sale(self.user, reason='again')
        self.assertFalse(ok2)
        self.assertEqual(self.stock_of(a), 50)
        self.assertEqual(self.stock_of(b), 40)
        self.assertEqual(cancellations.count(), 2)

    def test_cancelled_sale_excluded_from_active_ledger_debit(self):
        """Cancellation flag propagates like ordinary sales (status CANCELLED)."""
        a = self.make_perfume('A', stock_ml=50, cost_per_ml=100)
        sale = self.sell([(a, 5)], price=2500, customer=self.customer)
        sale.cancel_sale(self.user, reason='test')
        sale.refresh_from_db()
        self.assertEqual(sale.status, 'CANCELLED')

    def test_partial_returns_do_not_restore_stock(self):
        """Scenario 10: the existing system records returns without touching
        stock (SalesReturn is a record only), so no partial restoration is
        implemented. Documented behavior: creating a return changes nothing."""
        a = self.make_perfume('A', stock_ml=50, cost_per_ml=100)
        sale = self.sell([(a, 10)], price=5000)

        SalesReturn.objects.create(sale=sale, amount=Decimal('2000'), reason='partial')

        self.assertEqual(self.stock_of(a), 40)
        self.assertFalse(sale.perfume_lines.get().is_cancelled)


class RegressionTests(PerfumeSaleTestBase):
    def test_ordinary_product_sales_still_work(self):
        """Scenario 12: the existing SalesItem flow keeps deducting stock."""
        a = self.make_perfume('A', stock_ml=50, cost_per_ml=100)

        sale = Sales.objects.create(
            store=self.store, total_amount=1500, amount_paid=1500,
            balance=0, payment_method=self.payment_method, recorded_by=self.user,
        )
        SalesItem.objects.create(
            order=sale, product=a, unit=self.ml, quantity=10, sale_price=150
        )

        self.assertEqual(self.stock_of(a), 40)
        sale.refresh_from_db()
        # update_total_amount (signal) still totals items only when no perfume lines
        self.assertEqual(sale.total_amount, 1500)
        self.assertEqual(sale.perfume_total_ml, 0)

    def test_update_total_amount_includes_perfume_lines(self):
        """A sale later edited in the POS keeps its mixture amount."""
        a = self.make_perfume('A', stock_ml=50, cost_per_ml=100)
        sale = self.sell([(a, 10)], price=5000)
        # Adding an ordinary item to the same sale must not wipe the mixture
        SalesItem.objects.create(
            order=sale, product=a, unit=self.ml, quantity=2, sale_price=150
        )
        sale.refresh_from_db()
        self.assertEqual(sale.total_amount, 5000 + 2 * 150)

    def test_sales_detail_list_properties(self):
        """List/detail helpers expose total ml and line counts."""
        a = self.make_perfume('A', stock_ml=50, cost_per_ml=100)
        b = self.make_perfume('B', stock_ml=50, cost_per_ml=100)
        sale = self.sell([(a, 6), (b, 4)], price=8000)
        self.assertEqual(sale.perfume_total_ml, Decimal('10'))
        self.assertEqual(sale.perfume_line_count, 1)

    def test_estimate_stock_cost_reflects_fifo(self):
        product = Product.objects.create(name='Est', category=self.category)
        ProductUnitPrice.objects.create(
            product=product, unit=self.ml, conversion_factor=1, price=500
        )
        Inventory.objects.create(product=product, store=self.store, quantity_in_stock=30)
        InventoryBatch.objects.create(
            product=product, store=self.store, quantity=10, remaining_quantity=10, unit_cost=100
        )
        InventoryBatch.objects.create(
            product=product, store=self.store, quantity=20, remaining_quantity=20, unit_cost=300
        )
        available, cost = estimate_stock_cost(product, self.store)
        self.assertEqual(available, 30)
        # (10*100 + 20*300) / 30 = 233.3333
        self.assertEqual(cost, Decimal('233.3333'))

class ConcurrencyTests(PerfumeSaleTestBase):
    """Scenario 14: concurrent mixture sales cannot silently oversell."""

    def test_concurrent_sales_cannot_oversell(self):
        product = self.make_perfume('Contended', stock_ml=10, cost_per_ml=100)
        initial = self.stock_of(product)
        barrier = threading.Barrier(2)
        results = []

        def sell():
            try:
                barrier.wait(timeout=10)
                self.sell([(product, 8)], price=4000)
                results.append('ok')
            except ValidationError:
                results.append('rejected')
            except Exception as e:  # e.g. SQLite 'database is locked'
                results.append(f'error:{type(e).__name__}')
            finally:
                connection.close()

        threads = [threading.Thread(target=sell) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        success_count = results.count('ok')
        lock_errors = [r for r in results if r.startswith('error:')]
        final = self.stock_of(product)
        # Invariant: no overselling and no negative stock, ever.
        self.assertGreaterEqual(final, 0)
        self.assertEqual(final, initial - 8 * success_count)
        self.assertLessEqual(8 * success_count, initial)
        # A concurrent sale must go through, unless SQLite's table-level
        # locking aborted every attempt with OperationalError (all sales
        # rolled back and stock untouched -- still no overselling).
        if success_count == 0:
            self.assertTrue(lock_errors)
            self.assertEqual(final, initial)
