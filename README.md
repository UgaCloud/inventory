 inventory

 📘 System User Manual

 1. Introduction

This manual explains how to use the organizational management system, including setup, products, inventory, sales, purchases, and accounting workflows.



 2. System Modules Overview

   2.1 Organization Settings  

Stores organization profile, logo, currency, contact details.

   2.2 User & Role Management  

Controls account access, permissions, and user roles.

   2.3 Product & Inventory Management  

Handles product definitions, categories, brands, units, and stock movements.

   2.4 Sales Module  

Manages customers, orders, payments, and receipts.

   2.5 Procurement Module  

Handles suppliers, purchase orders, goods received, and supplier payments.

   2.6 Accounting Module  

Generates financial records and reports.



 3. Getting Started

   3.1 Logging In  

Enter your username and password to access your dashboard.

   3.2 User Interface Overview  

    Sidebar:   Main navigation menu
    Topbar:   Notifications, profile controls
   inventory

   # Inventory — User & Developer Manual

   This document describes how the Inventory system is organized, how to set up and run it for development and production, and how to enter data so that the system's workflows, reports and background jobs work correctly.

   If you are a developer, look for the "Developer Quickstart" section below. If you are a user entering data, start at the "Data entry guide" section.

   

   ## Table of contents

    Overview
    Architecture & key files
    Developer quickstart (install, run, migrate)
    Configuration and environment variables
    Data model highlights (important constraints & rules)
    Data entry guide (stepbystep, in the correct order)
    Bulk import and CSV templates
    Background jobs and scheduling
    Operational notes (sessions, debug toolbar, media/static)
    Troubleshooting & common gotchas

   

   ## Overview

   This app is a Djangobased inventory and sales management system. Major capabilities include:

    Organization settings and branches
    Product catalog (categories, units, SKU generation) and unit pricing
    Store locations and perstore inventory and batches (FIFO expiryaware)
    Purchase orders, purchase order items and inventory batch receiving
    Sales (orders, items), payments and payment allocations
    Stock transfers and transfer requests (FIFO batch transfer)
    Stock adjustments and auditable stock movements
    Expenses, cashflows, bank accounts and bank transactions
    Daily cash summary (management command)

   The codebase places businesslogic in `app/selectors/` and the ORM models live in `app/models/`.

   ## Architecture & key files

    Project entry: `manage.py` (uses `core.settings.development` by default)
    Root URLs: `core/urls.py` (includes `app.urls`)
    Settings: `core/settings/general.py` and `core/settings/development.py`
    Main app: `app/` — contains `models/`, `views/`, `selectors/`, `forms/`, `templates/` and `management/commands/`
    Models: `app/models/` (products.py, transactions.py, finance.py, organization.py, etc.)
    Views & routes: `app/urls.py`; view functions under `app/views/`
    Management commands: `app/management/commands/` (includes daily cash summary commands)

   ## Developer quickstart

   Prereqs: Python 3.11+ (the repo uses modern Django), pip or pipenv, and a virtualenv.

   1. Create a virtual environment and install dependencies (choose one):

   ```bash
   # Using pip & venv
   python3 m venv .venv
   source .venv/bin/activate
   pip install r requirements.txt

   # OR using pipenv (if you prefer):
   pipenv install dev
   pipenv shell
   ```

   2. Set environment variables the project expects (create an `.env` in the project root or export env vars):

   ```bash
   export SECRET_KEY='changemefordev'
   # If you use decouple, also create a .env with SECRET_KEY=...
   ```

   3. Apply migrations and create a superuser:

   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```

   4. Run the development server:

   ```bash
   python manage.py runserver
   ```

   Open `http://127.0.0.1:8000/`.

   Notes:
    Default settings used by `manage.py` point to `core.settings.development` which uses SQLite (`db.sqlite3`) and DEBUG=True.
    `SECRET_KEY` is read from environment/decouple in development; set it before running.

   ## Configuration & environment variables

    `DJANGO_SETTINGS_MODULE` is set in `manage.py` to `core.settings.development`.
    Key settings to check in `core/settings/general.py`:
       `SESSION_COOKIE_AGE` (default in repo: 300 seconds = 5 minutes). The project includes `app.middleware.SessionTimeoutMiddleware` which uses this value — consider increasing it for dev or production.
       `MEDIA_ROOT`, `STATIC_ROOT` and `STATICFILES_DIRS` — update these for production.

   Recommended `.env` entries for development
   ```text
   SECRET_KEY=yourdevsecret
   # Optional: DATABASE_URL, EMAIL settings if you add them later
   ```

   ## Data model highlights (important constraints & business rules)

    Products:
       `Product.sku` is unique and will be autogenerated when missing (based on category prefix).
       `Category.name` is unique.
       `ProductUnitPrice` enforces `unique_together` on `(product, unit)`.

    Inventory:
       The `Inventory` model has `unique_together = ('product','store')` — one inventory row per product+store.
       Stock is tracked via `InventoryBatch` (batches with `remaining_quantity`) and `StockMovement` (audit trail).
       FIFO and expiryaware logic is used in transfer & consumption methods (see `apply_inventory_changes`).

    Purchases & Receipts:
       `PurchaseOrder` → `PurchaseOrderItem` (unique per (order, product, unit)).
       When goods are received, create `InventoryBatch` entries tied to the `PurchaseOrderItem` and update `Inventory.quantity_in_stock`.

    Sales:
       `Sales` autogenerates `receipt_no` on save based on store and year if missing.
       `Sales` → `SalesItem` (unique per (order, product, unit)).
       Payments are recorded in `Payment` and linked to sales via `PaymentAllocation`.

    Cash & banking:
       `CashFlow` records storelevel inflows/outflows and may be linked to `BankTransaction`.
       `DailyCashSummary` is unique per (store, date).

    Transfers & adjustments:
       `TransferRequest` > `TransferRequestItem` > optionally `StockTransfer` > `StockTransferItem`.
       `StockAdjustment` and `StockAdjustmentItem` are used for manual corrections and generate `StockMovement` rows.

   ## Stepbystep data entry guide (recommended order)

   Follow this recommended sequence to create consistent, auditable data. The system assumes some entities exist before others.

   1. Organization & Users
        Add Organization settings (Settings → Organization). This sets currency and logo used in templates.
        Create Branches if you operate multiple physical locations (`app.models.organization.Branch`).
        Create User accounts and assign them to groups/roles (Admin, Manager, Sales, Stores, Accountant). These groups gate menu items via `app/context_processors.app_menu`.

   2. Catalog setup: units, categories, products
        Create `UnitOfMeasure` entries (e.g., Piece, Box, Kilogram).
        Create `Category` entries.
        Add `Product` rows with name and category. SKU will be autogenerated if you leave it blank. If you provide a SKU, ensure uniqueness.
        Add `ProductUnitPrice` rows for each (product, unit) combination you sell — `unique_together` is enforced.

   3. Branches & Stores
        Create `StoreLocation` rows under a `Branch` (a store is where inventory resides).
        Mark a store as `is_default` if you have a primary store.

   4. Suppliers & initial inventory (purchase workflow)
        Create `Supplier` rows.
        Create a `PurchaseOrder` and add `PurchaseOrderItem` rows for products and quantities.
        When goods are received, create `InventoryBatch` entries and call `update_total_cost()` on the `PurchaseOrder` if needed.
        For each batch, update the `Inventory` row for that `product+store` (create it if missing) and increase `quantity_in_stock` accordingly.
        Alternatively, you can use `StockAdjustment` with positive `StockAdjustmentItem` entries to set initial stock, but prefer proper PO + receiving for traceability.

   5. Sales workflow (recording a sale)
        Create a `Sales` record and add `SalesItem` rows. On saving the `Sales` record, `receipt_no` will be generated if missing.
        Record payment by creating a `Payment` and link to `Sales` via `PaymentAllocation` if the payment covers specific sales.
        The sale should decrement inventory using FIFO and create `StockMovement` entries (ensure the code path that performs inventory decrement is triggered in your view or service). If your UI does not automatically create `InventoryBatch` deductions, ensure the `StockMovement` logic is executed.

   6. Transfers & adjustments
        Use `TransferRequest` to request stock moves between stores. Approve and create `StockTransfer` to move stock.
        When applying a Transfer, the system uses FIFO across `InventoryBatch` to deduct and create new batches in the destination store.
        For manual corrections, use `StockAdjustment` with `StockAdjustmentItem` entries; then call `apply()` to update inventory and create `StockMovement` audit records.

   7. Cash, expenses, bank transactions
        Record `CashFlow` entries for cash in/out at store level.
        Record `Expense` entries and optionally attach a file (uses `expense_attachments/` media folder).
        For bank activity, use `BankAccount` and `BankTransaction` and link them to `CashFlow` if applicable.

   8. Daily cash summaries
        Run `python manage.py generate_daily_cash_summaries` (or schedule via cron) to create `DailyCashSummary` rows per store.

   ## How to structure your data practically (best practices)

    Always create categorical/lookup data first: Units → Categories → Payment Methods → Branches → Stores.
    Add products after categories/units exist so unitprices can be added immediately.
    Initialize stock using Purchase Orders and Inventory Batches rather than manual adjustments where possible — this preserves costing and traceability.
    Use consistent units and SKU naming rules (SKU autogeneration uses category prefixes). If you want controlled SKUs, supply them on product creation.
    For expirysensitive stock, ensure `expiry_date` is filled when receiving batches so the system can apply FIFO and expiry logic correctly.

   ## Bulk import and CSV templates

   Several views provide bulk upload + template endpoints. Use the templates to prepare CSVs matching the expected columns.

    Categories bulk template: `products/categories/bulktemplate/`
    Products bulk template: `products/bulktemplate/`
    Product unit price template: `products/unitprices/bulktemplate/`
    PurchaseOrderItem bulktemplate (path in `app.urls` for purchase orders)

   When uploading, follow these rules:
    Use exact column names the templates show (e.g., `name`, `description`, `price`).
    Ensure referenced entities exist (for example `category` string in the product CSV must match an existing Category name).

   ## Background jobs & scheduling

    Daily cash summary command:
       `app/management/commands/generate_daily_cash_summaries.py` computes a store's opening/closing balances and saves `DailyCashSummary` rows.
       You can run it manually:
         ```bash
         python manage.py generate_daily_cash_summaries
         ```
       The repo contains `run_daily_cash_summary.sh`, but it contains developerspecific paths. Update that script to use your venv and project path before using in cron.

   Example cron entry (edit paths to match your server):
   ```cron
   # Run at 23:59 daily
   59 23 * * * cd /path/to/project && /path/to/venv/bin/python manage.py generate_daily_cash_summaries >> /var/log/daily_cash_summary.log 2>&1
   ```

   ## Operational notes

    Session timeout: development settings default to 5 minutes (`SESSION_COOKIE_AGE = 300`) and middleware `app.middleware.SessionTimeoutMiddleware` logs users out after inactivity. Increase this for a production deployment.
    Debug toolbar is enabled in development (`debug_toolbar`) — disable for production.
    Media uploads go to `media/` and static assets are in `static/`.

   ## Troubleshooting & common gotchas

    If you are being unexpectedly logged out, check `SESSION_COOKIE_AGE` in `core/settings/general.py` and the `SessionTimeoutMiddleware` behavior.
    If SKU collisions occur, inspect `Product.save()` SKU autogeneration logic and prefer supplying controlled SKUs if you need a specific numbering.
    If timers or cron jobs aren't running, check your server's cron configuration and the absolute paths inside `run_daily_cash_summary.sh`.
    If product bulk upload skips rows, check CSV columns and ensure `category` values match existing categories (caseinsensitive matching varies by endpoint).

   ## How the database relationships affect data entry

    Unique constraints you must respect while entering data:
       Product.sku must be unique.
       Category.name must be unique.
       ProductUnitPrice unique on `(product, unit)`.
       Inventory unique on `(product, store)`.
       PurchaseOrderItem unique on `(order, product, unit)`.
       SalesItem unique on `(order, product, unit)`.
       StockAdjustmentItem unique on `(adjustment, product, unit)`.

   Failure to follow these unique constraints will cause model save errors.

   ## Where to find more code & to extend

    Views & routes: `app/urls.py` and `app/views/` — add UI endpoints here.
    Business logic & queries: `app/selectors/` — keep selectors thin and welltested.
    Models: `app/models/` — enforce DB constraints here and add helper methods for domain logic.
    Templates: `templates/` and `app/templates/` — UI views reference these.

   ## Next steps we can help with (offered actions)

   1. Produce an ER diagram file (Mermaid, PNG or SVG) and add it to `docs/`.
   2. Generate SQL DDL for PostgreSQL (helpful for production deployment).
   3. Update `run_daily_cash_summary.sh` to a safe, environmentagnostic script and show a recommended cron line.
   4. Add a short "How to record a Sale" tutorial with screenshots or exact UI steps.

   If you'd like, I can now commit this README.md update to the repository. I can also add a `README.dev.md` with stepbystep developer commands and a Mermaid ER diagram under `docs/`.

   

   Last updated: see repo commit history.
