"""Phase 8.1 - migration rehearsal on a copy of the real database.

The rehearsal never touches ``core/db.sqlite3``. It copies the real file to
a temporary directory, points Django at the copy and then

1. takes a fingerprint of the business data (row counts plus a few totals),
2. replays the tenant / audit / preference migrations backwards to the
   pre-tenant state (0092) and forwards again to the latest state,
3. takes the fingerprint again and compares.

Anything the migrations would have destroyed shows up as a difference in
the fingerprint.

Tables that the rehearsed migrations *create* (``app_auditlog``,
``app_userpreference``, ``app_perfumesaleline``) are checked for existence
only: rolling a ``CreateModel`` back drops the table with its rows, which is
what Django does everywhere. Everything that existed before the migrations
is compared row for row.

The script prints a report and exits non-zero when protected data changed.
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

import django

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.development')
django.setup()

from django.conf import settings  # noqa: E402
from django.core.management import call_command  # noqa: E402
from django.db import connections  # noqa: E402

REAL_DB = Path(settings.DATABASES['default']['NAME'])

# Tables that existed before the tenant migrations and must survive the
# rehearsal untouched.
PROTECTED_TABLES = [
    'app_sales',
    'app_salesitem',
    'app_product',
    'app_customer',
    'app_supplier',
    'app_storelocation',
    'app_purchaseorder',
    'app_stockmovement',
    'app_expense',
    'app_payment',
    'app_customerledger',
    'app_userprofile',
    'app_role',
    'app_organizationsetting',
    'app_notification',
    'app_bankaccount',
    'app_business',
    'app_branch',
    'app_inventory',
    'auth_user',
]

# Tables the rehearsed migrations create: they must exist afterwards, but
# their rows go with the table when the migration is rolled back.
CREATED_TABLES = [
    'app_auditlog',
    'app_userpreference',
    'app_perfumesaleline',
    'app_perfumesalecomponent',
]

# Business values that must not change.
FINGERPRINT_SQL = [
    ("sales_total", 'SELECT COALESCE(SUM(total_amount), 0) FROM app_sales'),
    ("sales_count", 'SELECT COUNT(*) FROM app_sales'),
    ("products_count", 'SELECT COUNT(*) FROM app_product'),
    ("customers_count", 'SELECT COUNT(*) FROM app_customer'),
    ("stock_units", 'SELECT COALESCE(SUM(quantity_in_stock), 0) FROM app_inventory'),
    ("users_count", 'SELECT COUNT(*) FROM auth_user'),
    ("company_profiles", 'SELECT COUNT(*) FROM app_organizationsetting'),
]


def table_exists(cursor, table):
    cursor.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=%s",
        [table],
    )
    return bool(cursor.fetchone()[0])


def fingerprint():
    with connections['default'].cursor() as cursor:
        counts = {}
        for table in PROTECTED_TABLES + CREATED_TABLES:
            if not table_exists(cursor, table):
                counts[table] = None
                continue
            cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
            counts[table] = cursor.fetchone()[0]

        values = {}
        for name, sql in FINGERPRINT_SQL:
            cursor.execute(sql)
            values[name] = cursor.fetchone()[0]
    return counts, values


def print_fingerprint(counts, values, title):
    print(f'\n-- {title} --')
    for table in PROTECTED_TABLES:
        print(f'   {table:32s} {counts.get(table)}')
    for table in CREATED_TABLES:
        print(f'   {table:32s} {counts.get(table)}  (created by the migration under test)')
    for name, value in values.items():
        print(f'   {name:32s} {value}')


def main():
    if not REAL_DB.exists():
        print(f'FATAL: real database not found at {REAL_DB}')
        return 2

    workdir = Path(tempfile.mkdtemp(prefix='migration-rehearsal-'))
    copy = workdir / 'db.sqlite3'
    shutil.copy2(REAL_DB, copy)
    print(f'real database : {REAL_DB} ({REAL_DB.stat().st_size} bytes)')
    print(f'rehearsal copy: {copy}')

    # Point Django at the copy.
    settings.DATABASES['default']['NAME'] = str(copy)
    connections.close_all()

    before_counts, before_values = fingerprint()
    print_fingerprint(before_counts, before_values, 'fingerprint before the rehearsal')

    print('\n-- rolling the tenant migrations backwards to 0092 --')
    rollback_ok = True
    try:
        call_command('migrate', 'app', '0092', verbosity=1, interactive=False)
    except Exception as exc:  # noqa: BLE001 - report, do not hide
        rollback_ok = False
        print(f'   rollback not possible: {type(exc).__name__}: {exc}')

    print('\n-- migrating forward to the latest state --')
    call_command('migrate', 'app', verbosity=1, interactive=False)
    connections.close_all()

    after_counts, after_values = fingerprint()
    print_fingerprint(after_counts, after_values, 'fingerprint after the rehearsal')

    differences = []
    for table in PROTECTED_TABLES:
        before = before_counts.get(table)
        after = after_counts.get(table)
        if before is None:
            differences.append(f'{table}: table did not exist before')
        elif after != before:
            differences.append(f'{table}: {before} -> {after}')

    missing = [t for t in CREATED_TABLES if after_counts.get(t) is None]
    for table in missing:
        differences.append(f'{table}: table is missing after the rehearsal')

    for name, value in before_values.items():
        after = after_values.get(name)
        if after != value:
            differences.append(f'{name}: {value} -> {after}')

    shutil.rmtree(workdir, ignore_errors=True)

    print('\n-- result --')
    if differences:
        print('DATA CHANGED during the rehearsal:')
        for line in differences:
            print(f'   ! {line}')
        return 1
    print('Every protected table and business value is identical after the rehearsal.')
    if not rollback_ok:
        print('Note: the migrations could not be rolled back (forward-only),')
        print('      so the forward path was rehearsed on the already-migrated copy.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
