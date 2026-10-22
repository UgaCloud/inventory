"""Seed the inventory system with realistic demo data.

Run with:      python manage.py seed_data
Wipe & reseed: python manage.py seed_data --reset

Stock, batches, stock movements and cash flows are created through the
app's own signals (PurchaseOrderItem / SalesItem / Sales / Expense), so the
seeded data is internally consistent with what the UI produces.
"""
import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Min, Sum
from django.utils import timezone

from app.models.customers import Customer, CustomerLedger, Payment, PaymentAllocation
from app.models.expense import Expense, ExpenseCategory
from app.models.finance import (
    BankAccount,
    BankTransaction,
    CashFlow,
    DailyCashSummary,
    PaymentMethod,
)
from app.models.human_resource import Department, Designation, Employee, Role
from app.models.notification import Notification
from app.models.organization import Branch, Currency
from app.models.products import (
    Automotive,
    Category,
    Inventory,
    Product,
    ProductUnitPrice,
    StoreLocation,
    UnitOfMeasure,
)
from app.models.suppliers import Supplier
from app.models.perfume import PerfumeSaleLine
from app.models.sales_return import SalesReturn
from app.models.transactions import (
    InventoryBatch,
    PurchaseOrder,
    PurchaseOrderItem,
    Sales,
    SalesItem,
    StockAdjustment,
    StockMovement,
    StockTransfer,
    TransferRequest,
)
from app.services.perfume_service import record_perfume_sale
from app.services.transfer_service import (
    approve_transfer_request,
    complete_stock_transfer,
    create_transfer_request,
    start_stock_transfer,
)

BRANCHES = [
    ("Kampala Main", "Plot 12, Kampala Road, Kampala", "Grace Nakato", "0772100200"),
    ("Jinja Road Spares", "Plot 45, Jinja Road, Kampala", "Peter Okello", "0772100300"),
    ("Entebbe Hub", "Plot 8, Entebbe Road, Entebbe", "Sarah Achieng", "0772100400"),
]

STORES = [
    ("Main Warehouse", 0, True, "Central bonded warehouse"),
    ("Retail Showroom", 1, False, "Walk-in retail counter"),
    ("Spares Store", 2, False, "Slow-moving spares store"),
]

UNITS = [
    ("Piece", "pc"),
    ("Box", "bx"),
    ("Carton", "ctn"),
    ("Litre", "L"),
    ("Kit", "kit"),
]

CATEGORIES = [
    "Engine Filters",
    "Oil & Lubricants",
    "Brake System",
    "Electrical",
    "Suspension & Steering",
    "Body Parts",
    "Accessories",
    "Coolant & Fluids",
]

VEHICLES = [
    ("Toyota", "Corolla", 2015, 2023, "1.8L Petrol"),
    ("Toyota", "Hilux", 2016, 2024, "2.8L Diesel"),
    ("Toyota", "RAV4", 2013, 2023, "2.0L Petrol"),
    ("Nissan", "X-Trail", 2014, 2021, "2.0L Petrol"),
    ("Honda", "Civic", 2016, 2023, "1.5L Turbo"),
    ("Honda", "Fit", 2012, 2020, "1.3L Petrol"),
    ("Suzuki", "Escudo", 2015, 2023, "1.6L Petrol"),
    ("Mitsubishi", "L200", 2016, 2023, "2.4L Diesel"),
]

PAYMENT_METHODS = [
    ("Cash", True),
    ("Mobile Money", False),
    ("Bank Transfer", False),
    ("Card", False),
]

SUPPLIERS = [
    ("Bosch Uganda Ltd", "sales@bosch-ug.com", "0772555001", "Michael Brenner", "Net 30"),
    ("AutoSpares East Africa", "orders@autospares.co.ke", "0772555002", "Jane Wanjiku", "Net 15"),
    ("Motor World Agencies", "info@motorworld.ug", "0772555003", "Samuel Kato", "Net 30"),
    ("Uganda Oil Distributors", "sales@uod.co.ug", "0772555004", "Rita Nalwoga", "COD"),
    ("Denso Parts Kampala", "denso@parts.ug", "0772555005", "Alex Mugisha", "Net 30"),
    ("Tyre & Brake Centre", "contact@tbc.ug", "0772555006", "Daniel Opio", "Net 15"),
]

CUSTOMERS = [
    ("City Taxi Services", "fleet@citytaxi.ug", "0773111001", "City Taxi Services Ltd"),
    ("Boda Boda Association", "info@bodaassoc.ug", "0773111002", None),
    ("Kampala Tours Ltd", "bookings@kampalatours.ug", "0773111003", "Kampala Tours Ltd"),
    ("John Mukasa", "jmukasa@gmail.com", "0773111004", None),
    ("Express Cargo Ltd", "ops@expresscargo.ug", "0773111005", "Express Cargo Ltd"),
    ("Fitness Garage", "hello@fitnessgarage.ug", "0773111006", "Fitness Garage"),
    ("Alice Namutebi", "anamutebi@gmail.com", "0773111007", None),
    ("National Transport Co", "transport@ntc.ug", "0773111008", "National Transport Co"),
]

# (name, brand, category, price UGX, box_cf|None, [vehicle idxs]|None, perishable)
PRODUCTS = [
    ("Oil Filter OF-100", "Bosch", "Engine Filters", 18000, 10, [0, 1, 2, 7], False),
    ("Air Filter AF-220", "Mann-Filter", "Engine Filters", 45000, 10, [0, 2, 3, 4], False),
    ("Fuel Filter FF-330", "Denso", "Engine Filters", 65000, 10, [0, 3, 7], False),
    ("Cabin Air Filter CF-440", "Bosch", "Engine Filters", 55000, 10, [0, 2, 4, 5], False),
    ("Engine Oil 5W-30 Semi Synthetic 1L", "Castrol", "Oil & Lubricants", 9500, 12, None, True),
    ("Engine Oil 10W-40 Mineral 1L", "Total Energies", "Oil & Lubricants", 7500, 12, None, True),
    ("Gear Oil 75W-90 1L", "Castrol", "Oil & Lubricants", 32000, 12, None, True),
    ("Brake Fluid DOT 4 500ml", "Bosch", "Oil & Lubricants", 15000, 20, None, True),
    ("ATF Dexron VI 1L", "Castrol", "Oil & Lubricants", 28000, 12, None, True),
    ("Brake Pads Front Set", "Bosch", "Brake System", 120000, 4, [0, 2, 4], False),
    ("Brake Pads Rear Set", "Bosch", "Brake System", 110000, 4, [0, 2, 4], False),
    ("Brake Disc Front", "TP Automotive", "Brake System", 180000, None, [0, 2, 3], False),
    ("Brake Shoe Set", "Akito", "Brake System", 85000, None, [1, 5, 7], False),
    ("Spark Plug NGK", "NGK", "Electrical", 25000, 10, [0, 2, 3, 4, 5], False),
    ("Battery 12V 45Ah", "Amaron", "Electrical", 480000, None, None, False),
    ("Alternator Belt", "Gates", "Electrical", 35000, None, [0, 1, 3, 7], False),
    ("Wiper Blade 22 inch", "Bosch", "Electrical", 40000, None, [0, 2, 4, 5], False),
    ("Front Shock Absorber", "KYB", "Suspension & Steering", 250000, None, [0, 2, 3], False),
    ("Lower Control Arm", "555", "Suspension & Steering", 180000, None, [0, 4, 5], False),
    ("Steering Rack Boot", "Febest", "Suspension & Steering", 60000, None, [0, 3, 6], False),
    ("Front Bumper", "Reproduction", "Body Parts", 320000, None, [0, 2], False),
    ("Side Mirror Left", "Reproduction", "Body Parts", 140000, None, [0, 5, 6], False),
    ("Headlight Assembly Right", "Depo", "Body Parts", 380000, None, [3, 4], False),
    ("Rubber Floor Mat Set", "Auto Comfort", "Accessories", 95000, None, None, False),
    ("Car Vacuum 12V", "Baseus", "Accessories", 130000, None, None, False),
    ("Coolant Concentrate 1L", "Prestone", "Coolant & Fluids", 22000, 12, None, True),
]

EXPENSE_CATEGORIES = [
    "Rent",
    "Salaries & Wages",
    "Utilities",
    "Transport & Fuel",
    "Maintenance",
    "Office Supplies",
    "Internet & Airtime",
]

EXPENSES = [
    # (category, amount, description)
    ("Rent", 1200000, "Monthly shop rent - Retail Showroom"),
    ("Rent", 800000, "Monthly warehouse rent"),
    ("Salaries & Wages", 1450000, "Shop staff salaries"),
    ("Salaries & Wages", 1100000, "Warehouse staff salaries"),
    ("Utilities", 240000, "Electricity bill (UEDCL)"),
    ("Utilities", 180000, "Water and waste collection"),
    ("Transport & Fuel", 320000, "Delivery van fuel"),
    ("Transport & Fuel", 150000, "Boda deliveries to customers"),
    ("Maintenance", 275000, "Shelving and racking repair"),
    ("Maintenance", 410000, "Forklift servicing"),
    ("Office Supplies", 95000, "Receipt books and stationery"),
    ("Office Supplies", 60000, "Printer toner"),
    ("Internet & Airtime", 220000, "Office internet subscription"),
    ("Internet & Airtime", 130000, "Staff airtime allowances"),
    ("Transport & Fuel", 85000, "Customer pickup fuel"),
    ("Utilities", 165000, "Generator diesel"),
    ("Maintenance", 190000, "Air compressor repair"),
    ("Office Supplies", 120000, "POS thermal rolls"),
]

# (username, full name, email, is_staff, is_superuser)
SEED_USERS = [
    ("cashier", "Cashier Seed", "cashier@localhost", True, True),
    ("clerk", "Stock Clerk Seed", "clerk@localhost", True, False),
]

SEED_PASSWORD = "seed1234"

NOTIFICATIONS = [
    ("warning", "Low stock alert", "Brake Pads Front Set at Retail Showroom is below its reorder level.", "/products/"),
    ("success", "Purchase order received", "Stock from Bosch Uganda Ltd has been received and added to inventory.", "/purchase_orders/"),
    ("info", "Daily cash summary ready", "Yesterday's cash summary has been generated for all stores.", "/expenses-report/"),
]


class Command(BaseCommand):
    help = "Seed the database with demo data (branches, products, stock, sales, expenses)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete all existing data first, then seed from scratch.",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            self.stdout.write("Wiping existing data (--reset)...")
            self.reset()
        elif Product.objects.exists():
            # Existing database: only fill the areas that were never seeded
            # (roles, HR, adjustments, transfers, returns, banks, perfume
            # sales). Every filler guards on its own table, so this is safe
            # to run repeatedly and never modifies existing rows.
            self.stdout.write(
                "Data already present - filling unseeded areas only. "
                "Use --reset to wipe and reseed."
            )
            self.rng = random.Random(42)
            with transaction.atomic():
                self.seed_gap_fillers()
                self.seed_cash_summaries(list(StoreLocation.objects.all()))
            self.report()
            return

        self.rng = random.Random(42)
        with transaction.atomic():
            users = self.seed_users()
            stores, warehouse, showroom, spares = self.seed_org()
            catalog = self.seed_catalog()
            self.seed_partners()
            products = self.seed_products(catalog)
            self.seed_product_images(products)
            self.seed_perfumes(stores)
            stock = self.seed_purchases(products, stores, users)
            self.seed_sales(products, stock, stores, users)
            self.seed_payments()
            self.seed_expenses(stores, users)
            self.seed_notifications(users)
            self.seed_gap_fillers()
            # Derive summaries last so cash created by any filler (perfume
            # sales) is included in the day's totals.
            self.seed_cash_summaries(stores)

        self.report()

    # ------------------------------------------------------------------ #
    def reset(self):
        PaymentAllocation.objects.all().delete()
        Payment.objects.all().delete()
        Notification.objects.all().delete()
        SalesReturn.objects.all().delete()
        StockAdjustment.objects.all().delete()      # items cascade
        StockTransfer.objects.all().delete()        # items cascade
        TransferRequest.objects.all().delete()      # items cascade
        BankTransaction.objects.all().delete()
        BankAccount.objects.all().delete()
        employee_user_ids = [
            uid
            for uid in Employee.objects.values_list("user_id", flat=True)
            if uid
        ]
        Employee.objects.all().delete()
        Department.objects.all().delete()           # designations cascade
        Role.objects.all().delete()                 # role modules cascade
        User.objects.filter(pk__in=employee_user_ids).delete()
        Group.objects.all().delete()
        Sales.objects.all().delete()          # cascades SalesItems
        Expense.objects.all().delete()        # detaches/deletes cashflows
        CashFlow.objects.all().delete()
        DailyCashSummary.objects.all().delete()
        StockMovement.objects.all().delete()
        InventoryBatch.objects.all().delete()
        PurchaseOrderItem.objects.all().delete()
        PurchaseOrder.objects.all().delete()
        Inventory.objects.all().delete()
        Product.objects.all().delete()
        Customer.objects.all().delete()
        Supplier.objects.all().delete()
        StoreLocation.objects.all().delete()
        Branch.objects.all().delete()
        Automotive.objects.all().delete()
        Category.objects.all().delete()
        UnitOfMeasure.objects.all().delete()
        ExpenseCategory.objects.all().delete()
        PaymentMethod.objects.all().delete()
        Currency.objects.all().delete()
        User.objects.filter(username__in=[u[0] for u in SEED_USERS]).delete()

    # ------------------------------------------------------------------ #
    def seed_users(self):
        existing = list(
            User.objects.filter(is_superuser=True).order_by("id")
        ) or [User.objects.create_superuser("admin", "admin@localhost", "admin1234")]
        for username, fullname, email, is_staff, is_superuser in SEED_USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": fullname.split()[0],
                    "last_name": " ".join(fullname.split()[1:]),
                    "email": email,
                    "is_staff": is_staff,
                    "is_superuser": is_superuser,
                    "is_active": True,
                },
            )
            if created:
                user.set_password(SEED_PASSWORD)
                user.save(update_fields=["password"])
            if user not in existing:
                existing.append(user)
        return existing

    def seed_org(self):
        for code, desc, cost in [
            ("UGX", "Ugandan Shillings", "1"),
            ("USD", "US Dollar", "3750"),
            ("KES", "Kenyan Shilling", "29"),
        ]:
            Currency.objects.get_or_create(
                code=code, defaults={"desc": desc, "cost": cost}
            )

        branches = []
        for name, location, contact_person, contact in BRANCHES:
            branch, _ = Branch.objects.get_or_create(
                name=name,
                defaults={
                    "location": location,
                    "contact_person": contact_person,
                    "contact": contact,
                },
            )
            branches.append(branch)

        stores = []
        for name, branch_idx, is_default, address in STORES:
            store, _ = StoreLocation.objects.get_or_create(
                name=name,
                defaults={
                    "branch": branches[branch_idx],
                    "address": address,
                    "is_default": is_default,
                    "is_active": True,
                },
            )
            stores.append(store)
        return stores, stores[0], stores[1], stores[2]

    def seed_catalog(self):
        units = {}
        for name, abbr in UNITS:
            unit, _ = UnitOfMeasure.objects.get_or_create(
                name=name, defaults={"abbreviation": abbr}
            )
            units[name] = unit

        categories = {}
        for name in CATEGORIES:
            category, _ = Category.objects.get_or_create(
                name=name,
                defaults={"description": f"{name} for passenger and commercial vehicles"},
            )
            categories[name] = category

        vehicles = {}
        for brand, model, year_from, year_to, engine in VEHICLES:
            vehicle, _ = Automotive.objects.get_or_create(
                brand=brand,
                model=model,
                year_from=year_from,
                defaults={"year_to": year_to, "engine_type": engine},
            )
            vehicles[(brand, model)] = vehicle

        for name, is_default in PAYMENT_METHODS:
            PaymentMethod.objects.get_or_create(
                name=name,
                defaults={"is_default": is_default, "is_active": True},
            )
        return {"units": units, "categories": categories, "vehicles": vehicles}

    def seed_partners(self):
        for name, email, phone, contact_person, terms in SUPPLIERS:
            Supplier.objects.get_or_create(
                name=name,
                defaults={
                    "email": email,
                    "phone": phone,
                    "contact_person": contact_person,
                    "payment_terms": terms,
                    "is_active": True,
                },
            )
        for name, email, phone, company in CUSTOMERS:
            Customer.objects.get_or_create(
                name=name,
                defaults={"email": email, "phone": phone, "company": company},
            )

    # ------------------------------------------------------------------ #
    def seed_products(self, catalog):
        units, categories, vehicles = (
            catalog["units"],
            catalog["categories"],
            catalog["vehicles"],
        )
        pc, box = units["Piece"], units["Box"]
        created = []
        for name, brand, category_name, price, box_cf, vehicle_idx, _perish in PRODUCTS:
            product = Product.objects.create(
                name=name,
                brand=brand,
                category=categories[category_name],
                description=f"{brand} {name} - genuine quality spare part.",
            )
            ProductUnitPrice.objects.create(
                product=product, unit=pc, conversion_factor=1, price=price
            )
            if box_cf:
                ProductUnitPrice.objects.create(
                    product=product,
                    unit=box,
                    conversion_factor=box_cf,
                    price=(price * box_cf * 95) // 100,
                )
            if vehicle_idx:
                product.compatible_vehicles.set(
                    [vehicles[VEHICLES[i][0], VEHICLES[i][1]] for i in vehicle_idx]
                )
            created.append(
                {
                    "product": product,
                    "unit": pc,
                    "price": price,
                    "box_cf": box_cf,
                    "perishable": _perish,
                }
            )
        return created

    def seed_product_images(self, products):
        """Generate placeholder product images (Pillow) so product list and
        POS thumbnails render. Skips products that already have an image."""
        try:
            from PIL import Image as PILImage, ImageDraw, ImageFont
        except ImportError:
            self.stdout.write("  pillow not installed - skipping product images")
            return
        import os
        from django.conf import settings

        media_dir = os.path.join(settings.MEDIA_ROOT, "products")
        os.makedirs(media_dir, exist_ok=True)
        palette = [
            (38, 166, 154), (255, 152, 0), (63, 81, 181), (156, 39, 176),
            (233, 30, 99), (76, 175, 80), (0, 150, 136), (57, 73, 171),
        ]
        made = 0
        for entry in products:
            product = entry["product"] if isinstance(entry, dict) else entry
            if product.image:
                continue
            rgb = palette[product.id % len(palette)]
            img = PILImage.new("RGB", (200, 200), rgb)
            draw = ImageDraw.Draw(img)
            initials = (
                "".join(w[0].upper() for w in (product.name or "").split()[:2])
                or "PR"
            )
            try:
                font = ImageFont.load_default(size=64)
            except TypeError:  # older Pillow without size argument
                font = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), initials, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text(
                ((200 - tw) / 2 - bbox[0], (200 - th) / 2 - bbox[1]),
                initials,
                fill="white",
                font=font,
            )
            filename = f"{product.sku or product.id}.png"
            img.save(os.path.join(media_dir, filename))
            product.image = f"products/{filename}"
            product.save(update_fields=["image"])
            made += 1
        self.stdout.write(f"  product images generated: {made}")

    def seed_perfumes(self, stores):
        """Perfume products sold by the millilitre (base unit = ml, CF 1),
        so the perfume/mixture panel has demoable data."""
        warehouse, showroom, spares = stores
        ml, _ = UnitOfMeasure.objects.get_or_create(
            name="Millilitre", defaults={"abbreviation": "ml"}
        )
        cat, _ = Category.objects.get_or_create(name="Perfumes")
        # (name, brand, selling price per ml, cost per ml, opening stock ml, store)
        perfumes = [
            ("Oud Royale", "Amir", 3000, 1800, 500, warehouse),
            ("Vanilla Musk", "Essence", 1200, 700, 800, showroom),
            ("Jasmine Bloom", "Essence", 1500, 900, 650, warehouse),
            ("Sandal Cream", "Attar House", 900, 500, 400, showroom),
        ]
        for name, brand, sell_ml, cost_ml, stock_ml, store in perfumes:
            if Product.objects.filter(name=name).exists():
                continue
            product = Product.objects.create(
                name=name,
                brand=brand,
                category=cat,
                description=f"{brand} {name} perfume, sold by the millilitre.",
            )
            ProductUnitPrice.objects.create(
                product=product, unit=ml, conversion_factor=1, price=sell_ml
            )
            Inventory.objects.create(
                product=product, store=store, quantity_in_stock=stock_ml,
                reorder_level=50,
            )
            InventoryBatch.objects.create(
                product=product, store=store, quantity=stock_ml,
                remaining_quantity=stock_ml, unit_cost=cost_ml,
            )
        self.stdout.write(
            f"  perfumes with ml pricing: {Product.objects.filter(category=cat).count()}"
        )

    def seed_purchases(self, products, stores, users):
        """One purchase order per store; signals create stock + batches."""
        warehouse, showroom, spares = stores
        plans = [
            # (store, supplier_idx, [(product entry, qty ratio)])
            (warehouse, 0, 1.0),
            (showroom, 2, 0.5),
            (spares, 4, 0.3),
        ]
        po_dates = {}
        po_days_ago = [75, 60, 0]  # last restock lands today so "today's
                                   # purchases" KPIs are populated
        for idx, (store, supplier_idx, ratio) in enumerate(plans):
            supplier = Supplier.objects.all().order_by("id")[supplier_idx]
            po = PurchaseOrder.objects.create(
                supplier=supplier,
                store=store,
                status="RECEIVED",
                recorded_by=self.rng.choice(users).username,
                note=f"Seed restock for {store.name}",
            )
            po_dates[po.pk] = date.today() - timedelta(days=po_days_ago[idx])
            for entry in products:
                base_qty = max(6, min(150, 900_000 // entry["price"]))
                qty = max(3, int(base_qty * ratio))
                if ratio == 0.5 and self.rng.random() < 0.35:
                    continue  # showroom does not carry everything
                if ratio == 0.3 and self.rng.random() < 0.55:
                    continue
                expiry = None
                if entry["perishable"]:
                    expiry = date.today() + timedelta(days=self.rng.randint(650, 1200))
                PurchaseOrderItem.objects.create(
                    order=po,
                    product=entry["product"],
                    unit=entry["unit"],
                    quantity=qty,
                    unit_cost=Decimal(max(1, (entry["price"] * 65) // 100)),
                    expiry_date=expiry,
                )

        # Backdate purchases and fix their dependent records (created "today"
        # by auto_now_add fields and by the creation-time signals).
        for po in PurchaseOrder.objects.all():
            d = po_dates.get(po.pk, date.today() - timedelta(days=45))
            dt = timezone.make_aware(datetime.combine(d, time(10, 30)))
            PurchaseOrder.objects.filter(pk=po.pk).update(purchase_date=d)
            CashFlow.objects.filter(
                transaction_type="PURCHASE", reference=f"PO-{po.pk}"
            ).update(amount=-po.total_cost, date=d)
            InventoryBatch.objects.filter(purchase_order_item__order=po).update(
                received_date=dt
            )
            StockMovement.objects.filter(
                transaction_type="IN", note="Purchase Order", transaction_id=po.pk
            ).update(timestamp=dt)
            StockMovement.objects.filter(
                transaction_type="Initial Stock",
                store=po.store,
                timestamp__date=date.today(),
            ).update(timestamp=dt)

        return self.snapshot_stock()

    def snapshot_stock(self):
        stock = {}
        for inv in Inventory.objects.all():
            stock[(inv.product_id, inv.store_id)] = inv.quantity_in_stock
        return stock

    # ------------------------------------------------------------------ #
    def seed_sales(self, products, stock, stores, users):
        warehouse, showroom, spares = stores
        store_weights = [(warehouse, 0.25), (showroom, 0.45), (spares, 0.30)]
        customers = list(Customer.objects.all().order_by("id"))
        methods = list(PaymentMethod.objects.all().order_by("id"))
        targets = 45
        created = 0
        attempts = 0
        while created < targets and attempts < 400:
            attempts += 1
            store = self.rng.choices(
                [s for s, _ in store_weights], [w for _, w in store_weights]
            )[0]

            available = [
                e
                for e in products
                if stock.get((e["product"].pk, store.pk), 0) > 0
            ]
            if not available:
                continue

            n_items = self.rng.randint(1, min(4, len(available)))
            chosen = self.rng.sample(available, n_items)
            lines = []
            possible = True
            for entry in chosen:
                in_stock = stock[(entry["product"].pk, store.pk)]
                want = (
                    1
                    if entry["price"] > 150000
                    else self.rng.randint(1, 5)
                )
                qty = min(want, in_stock)
                if qty < 1:
                    possible = False
                    break
                lines.append((entry, qty))
            if not possible or not lines:
                continue

            total = sum(e["price"] * q for e, q in lines)
            roll = self.rng.random()
            if roll < 0.70:                       # fully paid
                paid, received = total, total
            elif roll < 0.90:                     # partial payment
                paid = max(1000, (total * self.rng.randint(30, 70)) // 100)
                paid = (paid // 1000) * 1000
                received = paid
            else:                                 # unpaid
                paid, received = 0, 0
            balance = total - paid

            customer = None
            if self.rng.random() < 0.35:
                customer = self.rng.choice(customers)

            sale = Sales.objects.create(
                customer=customer,
                store=store,
                recorded_by=self.rng.choice(users),
                amount_paid=paid,
                balance=balance,
                amount_received=received,
                change=0,
                total_amount=total,
                payment_method=self.rng.choice(methods),
                note=self.rng.choice(
                    ["", "Walk-in sale", "Fleet service", "Garage account", ""]
                ),
            )
            for entry, qty in lines:
                SalesItem.objects.create(
                    order=sale,
                    product=entry["product"],
                    unit=entry["unit"],
                    quantity=qty,
                    sale_price=entry["price"],
                )
                stock[(entry["product"].pk, store.pk)] -= qty

            # Mirror record_sales_view: a customer sale with money paid gets a
            # Payment row so the customer ledger (and balance) stays aligned.
            if sale.customer and paid > 0 and sale.payment_method:
                Payment.objects.create(
                    customer=sale.customer,
                    amount=paid,
                    payment_method=sale.payment_method,
                    reference=sale.receipt_no,
                    note=f"Payment for sale {sale.receipt_no}",
                )

            d = date.today() - timedelta(days=self.rng.randint(0, 59))
            dt = timezone.make_aware(
                datetime.combine(
                    d, time(self.rng.randint(8, 17), self.rng.randint(0, 59))
                )
            )
            Sales.objects.filter(pk=sale.pk).update(sale_date=d)
            CashFlow.objects.filter(
                transaction_type="SALE", reference=sale.receipt_no
            ).update(date=d)
            StockMovement.objects.filter(
                transaction_type="OUT", note="Sale", transaction_id=sale.pk
            ).update(timestamp=dt)
            if sale.customer:
                CustomerLedger.objects.filter(
                    transaction_type="SALE",
                    description__contains=sale.receipt_no,
                ).update(date=dt)
            created += 1

        self.stdout.write(f"  sales created: {created}")

    # ------------------------------------------------------------------ #
    def seed_payments(self):
        methods = {
            m.name: m for m in PaymentMethod.objects.all().order_by("id")
        }
        n = 0
        for customer in Customer.objects.filter(balance__gt=0).order_by("id"):
            owed = customer.balance
            if owed <= 0:
                continue
            pay = owed if self.rng.random() < 0.6 else max(
                1000, (owed * self.rng.randint(40, 80)) // 100
            )
            pay = min(pay, owed)
            method = methods[self.rng.choice(["Cash", "Mobile Money", "Bank Transfer"])]
            n += 1
            payment = Payment.objects.create(
                customer=customer,
                amount=pay,
                payment_method=method,
                reference=f"PAY-{n:04d}",
                note="Seed payment",
            )
            d = date.today() - timedelta(days=self.rng.randint(1, 15))
            dt = timezone.make_aware(datetime.combine(d, time(12, 0)))
            Payment.objects.filter(pk=payment.pk).update(payment_date=dt)
            CustomerLedger.objects.filter(
                transaction_type="PAYMENT",
                description__contains=f"Ref: {payment.reference}",
            ).update(date=dt)

            # Allocate against this customer's outstanding sales, oldest first
            remaining = pay
            for sale in (
                Sales.objects.filter(customer=customer, balance__gt=0)
                .exclude(is_cancelled=True)
                .order_by("sale_date", "id")
            ):
                if remaining <= 0:
                    break
                alloc = min(remaining, sale.balance)
                PaymentAllocation.objects.create(
                    payment=payment, sale=sale, amount=alloc
                )
                new_paid = sale.amount_paid + int(alloc)
                new_balance = sale.total_amount - new_paid
                if new_balance <= 0:
                    status = "FULFILLED"
                    new_balance = 0
                else:
                    status = "PARTIALLY_PAID"
                Sales.objects.filter(pk=sale.pk).update(
                    amount_paid=new_paid,
                    balance=new_balance,
                    status=status,
                )
                remaining -= alloc

        # Recompute customer balances from their ledgers
        from app.signals.customers_signals import update_customer_balance

        for customer in Customer.objects.all():
            update_customer_balance(customer)
        self.stdout.write(f"  payments created: {n}")

    # ------------------------------------------------------------------ #
    def seed_expenses(self, stores, users):
        cats = {}
        for name in EXPENSE_CATEGORIES:
            cat, _ = ExpenseCategory.objects.get_or_create(
                name=name, defaults={"description": f"{name} expenses"}
            )
            cats[name] = cat
        methods = list(PaymentMethod.objects.all().order_by("id"))
        for i, (category, amount, description) in enumerate(EXPENSES, start=1):
            expense = Expense.objects.create(
                store=self.rng.choice(stores),
                category=cats[category],
                amount=Decimal(amount),
                description=description,
                reference=f"EXP-{i:03d}",
                user=self.rng.choice(users).username,
                payment_method=self.rng.choice(methods),
            )
            d = date.today() - timedelta(days=self.rng.randint(1, 55))
            Expense.objects.filter(pk=expense.pk).update(date=d)
            if expense.related_cashflow_id:
                CashFlow.objects.filter(pk=expense.related_cashflow_id).update(
                    date=d
                )

    def seed_cash_summaries(self, stores):
        """Derive DailyCashSummary rows from the actual seeded CashFlow
        rows (same derivation as the generate_daily_cash_summaries
        command), day by day in chronological order per store."""
        flows = CashFlow.objects.filter(date__isnull=False)
        if not flows.exists():
            return
        d0 = flows.aggregate(m=Min("date"))["m"]
        d0 = d0.date() if hasattr(d0, "date") else d0
        d1 = date.today()
        created = 0
        for store in stores:
            closing = Decimal("0")
            day = d0
            while day <= d1:
                opening = closing
                flow = (
                    flows.filter(store=store, date=day)
                    .aggregate(t=Sum("amount"))["t"]
                    or Decimal("0")
                )
                closing = opening + Decimal(flow)
                DailyCashSummary.objects.update_or_create(
                    store=store,
                    date=day,
                    defaults={
                        "opening_balance": opening,
                        "closing_balance": closing,
                        "calculated_balance": closing,
                        "note": "Seeded from actual cash flows",
                    },
                )
                created += 1
                day += timedelta(days=1)
        self.stdout.write(f"  daily cash summaries derived: {created}")

    def seed_notifications(self, users):
        for user in users:
            for i, (ntype, title, message, link) in enumerate(NOTIFICATIONS, start=1):
                Notification.objects.create(
                    user=user,
                    title=title,
                    message=message,
                    notification_type=ntype,
                    link=link,
                )
                Notification.objects.filter(
                    user=user, title=title, created_at__date=date.today()
                ).update(
                    created_at=timezone.now() - timedelta(days=i, hours=i)
                )

    # ------------------------------------------------------------------ #
    # Fillers for areas the original seed never covered. Each method guards
    # on its own table, so they are idempotent and safe on both a fresh
    # --reset run and an already-seeded database.

    ROLE_PLANS = {
        # name: (description, is_superuser, module ids)
        "Admin": ("Full access to every module", True, []),
        "Manager": ("Branch and inventory oversight", False,
                    [1, 2, 3, 4, 8, 10, 13, 14, 16]),
        "Sales": ("Point of sale and customer handling", False,
                  [1, 4, 8, 10, 13]),
        "Stores": ("Stock, purchases and transfers", False,
                   [1, 2, 3, 10, 11, 12]),
        "Accountant": ("Finance, expenses and accounting", False,
                       [1, 6, 8, 10, 14, 16]),
    }
    PROFILE_ROLES = {
        "user": "Admin",
        "pryce": "Manager",
        "cashier": "Sales",
        "clerk": "Stores",
    }

    def seed_gap_fillers(self):
        self.seed_roles()
        self.seed_hr()
        self.seed_adjustments()
        self.seed_transfers()
        self.seed_returns()
        self.seed_banks()
        self.seed_perfume_sales()

    def seed_roles(self):
        """RBAC roles with navigation modules, assigned to the demo users
        so menus and module access work out of the box."""
        if Role.objects.exists():
            return
        for name, (desc, is_super, modules) in self.ROLE_PLANS.items():
            role = Role.objects.create(
                name=name, description=desc, is_staff=True,
                is_superuser=is_super, business=None,
            )
            if not is_super and modules:
                role.set_modules(modules)
        assigned = 0
        for username, role_name in self.PROFILE_ROLES.items():
            user = User.objects.filter(username=username).first()
            profile = getattr(user, "profile", None) if user else None
            if profile:
                role = Role.objects.filter(name=role_name, business__isnull=True).first()
                if role:
                    profile.roles.add(role)
                assigned += 1
        self.stdout.write(
            f"  roles: {Role.objects.count()} "
            f"(assigned to {assigned} users)"
        )

    def seed_hr(self):
        """Departments, designations and employees (a login user is
        auto-created per employee by the existing post_save signal)."""
        if Department.objects.exists():
            return
        branch = Branch.objects.order_by("id").first()
        if branch is None:
            return
        plans = [
            ("Operations", [
                ("Operations Manager", "M", "0772100501"),
                ("Store Assistant", "F", "0772100502"),
            ]),
            ("Sales", [
                ("Sales Executive", "F", "0772100503"),
                ("Sales Assistant", "M", "0772100504"),
            ]),
            ("Finance", [("Accountant", "F", "0772100505")]),
            ("Logistics", [("Driver", "M", "0772100506")]),
        ]
        employees = 0
        for dept_name, titles in plans:
            dept = Department.objects.create(
                name=dept_name, description=f"{dept_name} department"
            )
            for title, gender, contact in titles:
                desig = Designation.objects.create(
                    title=title, department=dept
                )
                Employee.objects.create(
                    gender=gender,
                    contact=contact,
                    branch=branch,
                    department=dept,
                    designation=desig,
                    date_joined=date.today() - timedelta(days=365),
                    address="Kampala, Uganda",
                )
                employees += 1
        self.stdout.write(
            f"  departments: {Department.objects.count()}  "
            f"designations: {Designation.objects.count()}  "
            f"employees: {employees}"
        )

    def seed_adjustments(self):
        """A mix of applied (positive) and pending (shrinkage) stock
        adjustments; applying goes through the model's own apply() so
        inventory, batches and stock movements stay aligned."""
        if StockAdjustment.objects.exists():
            return
        users = list(User.objects.order_by("id"))
        candidates = [
            inv for inv in
            Inventory.objects.select_related("product", "store")
            if inv.quantity_in_stock >= 30
        ]
        if not candidates or not users:
            return
        picks = self.rng.sample(candidates, min(4, len(candidates)))
        applied = 0
        for i, inv in enumerate(picks):
            positive = i % 2 == 0
            change = self.rng.randint(5, 10) * (1 if positive else -1)
            unit = inv.product.default_unit
            if not hasattr(unit, "pk"):
                unit = UnitOfMeasure.objects.order_by("id").first()
            adj = StockAdjustment.objects.create(
                store=inv.store,
                reference=f"ADJ-SEED-{i+1:04d}",
                created_by=self.rng.choice(users),
                product=inv.product,
                unit=unit,
                quantity_change=change,
                reason=(
                    "Cycle count surplus" if positive
                    else "Damaged units written off"
                ),
            )
            if positive and adj.apply(applied_by="seed"):
                applied += 1
            StockAdjustment.objects.filter(pk=adj.pk).update(
                created_at=timezone.now()
                - timedelta(days=self.rng.randint(3, 21))
            )
        self.stdout.write(
            f"  stock adjustments: {StockAdjustment.objects.count()} "
            f"({applied} applied)"
        )

    def seed_transfers(self):
        """A transfer-request/transfer lifecycle: one completed (stock
        actually moved), one in transit, one approved, one pending."""
        if TransferRequest.objects.exists():
            return
        stores = list(StoreLocation.objects.order_by("id"))
        users = list(User.objects.order_by("id"))
        if len(stores) < 2 or not users:
            return
        src, dst = stores[0], stores[1]

        batch_sum = {}
        for b in InventoryBatch.objects.filter(
            store=src, remaining_quantity__gt=0
        ):
            batch_sum[b.product_id] = (
                batch_sum.get(b.product_id, 0) + b.remaining_quantity
            )
        avail = [
            inv for inv in
            Inventory.objects.select_related("product").filter(store=src)
            if inv.quantity_in_stock >= 15
            and batch_sum.get(inv.product_id, 0) >= 10
        ]
        if not avail:
            return

        def base_unit(product):
            pup = ProductUnitPrice.objects.filter(
                product=product, conversion_factor=1
            ).order_by("id").first()
            return pup.unit if pup else None

        made = {"completed": 0, "in_transit": 0, "approved": 0,
                "pending": 0}
        for kind in ("completed", "in_transit", "approved", "pending"):
            if not avail:
                break
            inv = avail.pop(0)
            try:
                tr = create_transfer_request(
                    requested_by=self.rng.choice(users),
                    from_store=src,
                    to_store=dst,
                    items=[{
                        "product": inv.product,
                        "quantity": 3,
                        "units": base_unit(inv.product),
                    }],
                )
                if kind == "pending":
                    made["pending"] += 1
                    continue
                st = approve_transfer_request(
                    tr.pk, self.rng.choice(users)
                )
                if kind == "approved":
                    made["approved"] += 1
                    continue
                start_stock_transfer(st.pk, self.rng.choice(users))
                if kind == "in_transit":
                    made["in_transit"] += 1
                    continue
                complete_stock_transfer(st.pk, self.rng.choice(users))
                made["completed"] += 1
            except ValidationError:
                continue
        self.stdout.write(
            f"  transfer requests: {TransferRequest.objects.count()}  "
            f"stock transfers: {StockTransfer.objects.count()} "
            f"(completed {made['completed']}, "
            f"in transit {made['in_transit']}, "
            f"approved {made['approved']}, pending {made['pending']})"
        )

    def seed_returns(self):
        """Sales-return records against fully paid sales (the model is a
        record only; no stock or cash side effects)."""
        if SalesReturn.objects.exists():
            return
        sales = list(
            Sales.objects.filter(balance=0, total_amount__gt=0)
            .order_by("-sale_date", "-id")[:6]
        )
        plans = [
            ("pending", "Damaged packaging reported by the customer."),
            ("approved", "Wrong part supplied; returned to the store."),
            ("approved", "Customer changed mind, product still sealed."),
            ("rejected", "Return outside the 7-day window."),
        ]
        created = 0
        for sale, (status, reason) in zip(sales, plans):
            amount = Decimal(max(1000, int(int(sale.total_amount) * 0.4)))
            ret = SalesReturn.objects.create(
                sale=sale, amount=amount, reason=reason, status=status
            )
            SalesReturn.objects.filter(pk=ret.pk).update(
                created_at=timezone.now()
                - timedelta(days=self.rng.randint(3, 30))
            )
            created += 1
        self.stdout.write(f"  sales returns: {created}")

    def seed_banks(self):
        """Bank accounts with signed transactions (deposits positive,
        withdrawals negative), so get_bank_balance maths add up."""
        if BankAccount.objects.exists():
            return
        stores = list(StoreLocation.objects.order_by("id"))
        users = list(User.objects.order_by("id"))
        if not stores:
            return
        acc1 = BankAccount.objects.create(
            name="Operations Account",
            account_number="1000123456",
            bank_name="Centenary Bank",
            opening_balance=2_500_000,
            note="Main operating account",
        )
        acc2 = BankAccount.objects.create(
            name="Savings Account",
            account_number="2000654321",
            bank_name="Stanbic Bank",
            opening_balance=900_000,
            note="Reserve funds",
        )
        plans = [
            (acc1, 0, 500_000, "DEPOSIT", "Weekend takings", 10),
            (acc1, 0, -220_000, "WITHDRAWAL", "Supplier payment", 8),
            (acc1, 1, 350_000, "DEPOSIT", "Showroom float transfer", 6),
            (acc1, 0, -150_000, "WITHDRAWAL", "Petty cash top-up", 4),
            (acc2, 0, 400_000, "DEPOSIT", "Monthly savings sweep", 2),
            (acc2, 1, -90_000, "WITHDRAWAL", "Bank charges", 1),
        ]
        for account, store_idx, amount, ttype, ref, days_ago in plans:
            txn = BankTransaction.objects.create(
                bank_account=account,
                store=stores[min(store_idx, len(stores) - 1)],
                amount=amount,
                transaction_type=ttype,
                reference=ref,
                user=(users[0].username if users else "admin"),
                note=ref,
            )
            BankTransaction.objects.filter(pk=txn.pk).update(
                date=date.today() - timedelta(days=days_ago)
            )
        self.stdout.write(
            f"  bank accounts: {BankAccount.objects.count()} "
            f"({BankTransaction.objects.count()} transactions)"
        )

    def seed_perfume_sales(self):
        """Demo perfume sales (one mixture, one single) through the real
        service, so FIFO costing, movements and cash flows all fire."""
        if PerfumeSaleLine.objects.exists():
            return
        method = (
            PaymentMethod.objects.filter(is_default=True).first()
            or PaymentMethod.objects.order_by("id").first()
        )
        users = list(User.objects.order_by("id"))
        if method is None or not users:
            return

        def price_ml(product):
            pup = ProductUnitPrice.objects.filter(
                product=product, conversion_factor=1
            ).order_by("id").first()
            return int(pup.price) if pup else 0

        plans = [
            ("Main Warehouse",
             [("Oud Royale", 6), ("Jasmine Bloom", 4)],
             "Custom blend: 6 ml Oud + 4 ml Jasmine"),
            ("Retail Showroom", [("Vanilla Musk", 10)], ""),
        ]
        created = 0
        for store_name, comps, note in plans:
            store = StoreLocation.objects.filter(name=store_name).first()
            if store is None:
                continue
            resolved, total = [], 0
            ok = True
            for pname, ml in comps:
                p = Product.objects.filter(name=pname).first()
                if p is None:
                    ok = False
                    break
                resolved.append((p, ml))
                total += price_ml(p) * ml
            if not ok or not resolved or total <= 0:
                continue
            try:
                record_perfume_sale(
                    store=store,
                    components=resolved,
                    selling_price=total,
                    user=self.rng.choice(users),
                    customer=None,
                    amount_paid=total,
                    amount_received=total,
                    payment_method=method,
                    note=note,
                )
                created += 1
            except ValidationError:
                continue
        self.stdout.write(f"  perfume sales created: {created}")

    # ------------------------------------------------------------------ #
    def report(self):
        lines = [
            "Seed complete:",
            f"  branches: {Branch.objects.count()}  stores: {StoreLocation.objects.count()}",
            f"  categories: {Category.objects.count()}  units: {UnitOfMeasure.objects.count()}",
            f"  vehicles: {Automotive.objects.count()}  products: {Product.objects.count()}",
            f"  suppliers: {Supplier.objects.count()}  customers: {Customer.objects.count()}",
            f"  purchase orders: {PurchaseOrder.objects.count()} "
            f"({PurchaseOrderItem.objects.count()} items)",
            f"  sales: {Sales.objects.count()} ({SalesItem.objects.count()} items)  "
            f"revenue: {Sales.objects.aggregate(t=Sum('total_amount'))['t'] or 0:,}",
            f"  payments: {Payment.objects.count()}  allocations: {PaymentAllocation.objects.count()}",
            f"  inventory rows: {Inventory.objects.count()}  "
            f"units in stock: {Inventory.objects.aggregate(t=Sum('quantity_in_stock'))['t'] or 0:,}",
            f"  batches: {InventoryBatch.objects.count()}  movements: {StockMovement.objects.count()}",
            f"  expenses: {Expense.objects.count()}  cashflows: {CashFlow.objects.count()}",
            f"  daily cash summaries: {DailyCashSummary.objects.count()}",
            f"  notifications: {Notification.objects.count()}  users: {User.objects.count()}",
            f"  roles: {Role.objects.count()}  "
            f"departments: {Department.objects.count()}  "
            f"employees: {Employee.objects.count()}",
            f"  adjustments: {StockAdjustment.objects.count()}  "
            f"transfers: {StockTransfer.objects.count()}  "
            f"transfer requests: {TransferRequest.objects.count()}",
            f"  sales returns: {SalesReturn.objects.count()}  "
            f"bank accounts: {BankAccount.objects.count()} "
            f"({BankTransaction.objects.count()} transactions)",
            f"  perfume sale lines: {PerfumeSaleLine.objects.count()}",
        ]
        for line in lines:
            self.stdout.write(line)
