"""One-off: add the tenant-aware manager to every tenant-owned model.

Inserts ``objects = TenantManager()`` as the first statement of the listed
model classes (after the class docstring when there is one) and adds the
import at the top of the file. Existing line endings are preserved.
"""
import io
import os

TARGETS = {
    "app/models/products.py": [
        "Product", "ProductUnitPrice", "StoreLocation", "Inventory",
    ],
    "app/models/transactions.py": [
        "PurchaseOrder", "PurchaseOrderItem", "InventoryBatch", "Sales",
        "SalesItem", "TransferRequest", "TransferRequestItem", "StockTransfer",
        "StockTransferItem", "StockAdjustment", "StockMovement",
        "StockAdjustmentItem",
    ],
    "app/models/customers.py": [
        "Customer", "CustomerLedger", "Payment", "PaymentAllocation",
    ],
    "app/models/suppliers.py": ["Supplier"],
    "app/models/organization.py": ["Branch"],
    "app/models/human_resource.py": [
        "Employee", "Role", "RoleModule", "RoleDeletionLog", "UserProfile",
    ],
    "app/models/finance.py": [
        "CashFlow", "DailyCashSummary", "BankAccount", "BankTransaction",
    ],
    "app/models/perfume.py": ["PerfumeSaleLine", "PerfumeSaleComponent"],
}

MANAGER_LINE = "    objects = TenantManager()\n"
IMPORT_LINE = "from app.managers import TenantManager\n"


def insert_manager(text, class_name):
    marker = "class %s(models.Model):" % class_name
    idx = text.find(marker)
    if idx == -1:
        raise SystemExit("class %s not found" % class_name)
    # Skip the class line
    pos = idx + len(marker)
    rest = text[pos:]
    # If the class body starts with a docstring, keep it first.
    stripped = rest.lstrip("\n")
    lead = rest[: len(rest) - len(stripped)]
    if stripped.startswith('"""') or stripped.startswith("'''"):
        quote = stripped[:3]
        end = stripped.find(quote, 3)
        if end == -1:
            raise SystemExit("unterminated docstring in %s" % class_name)
        after = stripped[end + 3:]
        # Insert right after the closing quote of the docstring.
        insert_at = pos + len(lead) + (end + 3)
        prefix = text[:insert_at]
        suffix = text[insert_at:]
        if not prefix.endswith("\n"):
            prefix += "\n"
        return prefix + MANAGER_LINE + suffix
    # No docstring: insert right after the class line.
    if not text[:pos].endswith("\n"):
        pos += 1
        text = text[:pos] + "\n" + text[pos:]
    return text[:pos] + "\n" + MANAGER_LINE + text[pos:]


def add_import(text):
    if IMPORT_LINE in text:
        return text
    lines = text.split("\n")
    # Insert after the last top-level import at the head of the file.
    last_import = 0
    for i, line in enumerate(lines[:60]):
        if line.startswith("import ") or line.startswith("from "):
            last_import = i
    lines.insert(last_import + 1, IMPORT_LINE.rstrip("\n"))
    return "\n".join(lines)


for path, classes in TARGETS.items():
    with io.open(path, "r", encoding="utf-8", newline="") as fh:
        raw = fh.read()
    text = raw.replace("\r\n", "\n")
    for class_name in classes:
        if "objects = TenantManager()" in text.split("class %s(" % class_name, 1)[1][:4000]:
            continue
        text = insert_manager(text, class_name)
    text = add_import(text)
    out = text.replace("\n", "\r\n")
    with io.open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(out)
    print("%s: %d tenant models" % (path, len(classes)))
