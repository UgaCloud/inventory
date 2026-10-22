"""One-off structural edit: record_sales.html -> grid-2 sale items + payment summary.

Reads the template preserving CRLF, swaps well-anchored regions, writes it back
with the original line endings so the diff stays reviewable.
"""
import io
import sys

PATH = "app/templates/sales/record_sales.html"

with io.open(PATH, "r", encoding="utf-8", newline="") as fh:
    raw = fh.read()

text = raw.replace("\r\n", "\n")

# ---------------------------------------------------------------------------
# 1. Sale items: table -> grid-2 cards
# ---------------------------------------------------------------------------
ITEMS_NEW = """                <!-- Sale Items (grid-2) -->
                <div id="saleitem-formset" class="sale-items">
                    {{ formset.management_form }}
                    <div id="formset-body" class="sale-items-grid">
                        {% for form in formset.forms %}
                        <div class="formset-row" id="row-{{ forloop.counter0 }}">
                            <div class="formset-row-head">
                                <span class="formset-row-index">{{ forloop.counter }}</span>
                                <span class="formset-row-title">Sale item</span>
                            </div>
                            <div class="grid-2">
                                <div class="form-field">
                                    <label class="form-label" for="id_items-{{ forloop.counter0 }}-product">Product <span class="text-danger">*</span></label>
                                    <select name="items-{{ forloop.counter0 }}-product" class="form-select select2 product-select" id="id_items-{{ forloop.counter0 }}-product" style="width: 100%;">
                                        <option value="">Select Product</option>
                                        {% for product in products %}
                                        <option value="{{ product.id }}" {% if form.product.value|stringformat:"s" == product.id|stringformat:"s" %}selected{% endif %}>
                                            {{ product.name }} ({{ product.sku }})
                                        </option>
                                        {% endfor %}
                                    </select>
                                    {{ form.id }}
                                </div>
                                <div class="form-field">
                                    <label class="form-label" for="id_items-{{ forloop.counter0 }}-unit">Unit <span class="text-danger">*</span></label>
                                    <select name="items-{{ forloop.counter0 }}-unit" class="form-select select2 unit-select" id="id_items-{{ forloop.counter0 }}-unit" style="width: 100%;">
                                        <option value="">Select Unit</option>
                                        {% for unit in units %}
                                        <option value="{{ unit.id }}" {% if form.unit.value|stringformat:"s" == unit.id|stringformat:"s" %}selected{% endif %}>
                                            {{ unit.name }}
                                        </option>
                                        {% endfor %}
                                    </select>
                                </div>
                                <div class="form-field">
                                    <label class="form-label">Available Stock</label>
                                    <div class="available-stock-container">
                                        <span class="badge bg-info available-stock fw-semibold" id="available-stock-{{ forloop.counter0 }}">0</span>
                                        <input type="hidden" class="original-stock-input" id="original-stock-{{ forloop.counter0 }}" value="0">
                                    </div>
                                </div>
                                <div class="form-field">
                                    <label class="form-label" for="id_items-{{ forloop.counter0 }}-quantity">Quantity</label>
                                    <input type="number" name="items-{{ forloop.counter0 }}-quantity" min="1" class="form-control quantity-input"
                                           id="id_items-{{ forloop.counter0 }}-quantity" value="{{ form.quantity.value|default:1 }}">
                                    <div class="error-message stock-error-message small text-danger mt-1" id="stock-error-{{ forloop.counter0 }}" style="display: none;"></div>
                                </div>
                                <div class="form-field">
                                    <label class="form-label" for="id_items-{{ forloop.counter0 }}-sale_price">Sale Price</label>
                                    <input type="number" name="items-{{ forloop.counter0 }}-sale_price" min="0" step="0.01"
                                           class="form-control price-input" id="id_items-{{ forloop.counter0 }}-sale_price"
                                           value="{{ form.sale_price.value|default:0 }}">
                                </div>
                                <div class="form-field">
                                    <label class="form-label">Unit Price</label>
                                    <div class="form-value unit-price fw-semibold" id="unit-price-{{ forloop.counter0 }}">0</div>
                                </div>
                                <div class="form-field">
                                    <label class="form-label">Subtotal</label>
                                    <div class="form-value subtotal fw-bold text-primary" id="subtotal-{{ forloop.counter0 }}">0</div>
                                </div>
                                <div class="form-field form-field-actions">
                                    <label class="form-label">Actions</label>
                                    <button type="button" class="btn btn-sm btn-outline-danger rounded-circle p-1 remove-form-row" title="Remove item">
                                        <i class="ti ti-trash fs-6"></i>
                                    </button>
                                </div>
                            </div>
                        </div>
                        {% endfor %}
                    </div>

                    <div class="app-empty-state" id="sale-items-empty" style="display: none;">
                        <span class="app-empty-icon"><i class="ti ti-package"></i></span>
                        <span class="app-empty-title">No items added yet</span>
                        <span class="app-empty-text">Add the products you are selling, or scan a barcode to add an item automatically.</span>
                        <button type="button" class="btn btn-primary btn-sm mt-2" id="add-form-row-empty">
                            <i class="ti ti-plus me-1"></i> Add Item
                        </button>
                    </div>

                    <div class="sale-items-footer">
                        <button type="button" class="btn btn-primary btn-sm" id="add-form-row">
                            <i class="ti ti-plus me-1"></i> Add Item
                        </button>
                        <div class="sale-items-total">
                            <span class="fw-semibold">Total Amount</span>
                            <span id="grand-total" class="fw-bold text-primary">0</span>
                        </div>
                    </div>
                    <div id="validation-summary-row" class="sale-items-validation" style="display: none;">
                        <i class="ti ti-alert-circle me-1"></i> <span id="validation-summary-text"></span>
                    </div>
                    {% if formset.non_form_errors %}
                        <div class="alert alert-danger mt-3">{{ formset.non_form_errors }}</div>
                    {% endif %}
                </div>
            </div>

"""

items_start = text.index("                <!-- Items Table -->\n")
items_end = text.index("            <!-- Payment Summary Card -->\n")
text = text[:items_start] + ITEMS_NEW + text[items_end:]

# ---------------------------------------------------------------------------
# 2. Payment summary: list-group -> grid-2
# ---------------------------------------------------------------------------
PAYMENT_NEW = """            <!-- Payment Summary Card -->
            <div class="row mt-5">
                <div class="col-12">
                    <div class="card border shadow-sm">
                        <div class="card-header bg-white border-bottom">
                            <h6 class="fw-semibold mb-0">Payment Summary</h6>
                        </div>
                        <div class="card-body p-0">
                            <div class="grid-2 payment-summary">
                                <div class="payment-summary-item">
                                    <span class="payment-summary-label">Total Amount</span>
                                    <input type="text" id="total-amount" name="total_amount" class="form-control-plaintext fw-bold text-end"
                                           value="0" readonly>
                                </div>
                                <div class="payment-summary-item">
                                    <span class="payment-summary-label">Amount Paid</span>
                                    <input type="number" name="amount_paid" id="amount-paid" class="form-control text-end"
                                           value="0" min="0" step="1">
                                </div>
                                <div class="payment-summary-item">
                                    <span class="payment-summary-label">Balance Due</span>
                                    <input type="text" name="balance" id="balance" class="form-control-plaintext fw-bold text-end text-danger"
                                           value="0" readonly>
                                </div>
                                <div class="payment-summary-item">
                                    <span class="payment-summary-label">Payment Method</span>
                                    {{ form.payment_method|add_class:"form-select select2 payment-method-select" }}
                                </div>
                                <div class="payment-summary-item">
                                    <span class="payment-summary-label">Amount Received</span>
                                    <input type="number" name="amount_received" id="amount-received" class="form-control text-end"
                                           value="0" min="0" step="1">
                                </div>
                                <div class="payment-summary-item">
                                    <span class="payment-summary-label">Change</span>
                                    <input type="text" name="change" id="change" class="form-control-plaintext fw-bold text-end text-success"
                                           value="0" readonly>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

"""

pay_start = text.index("            <!-- Payment Summary Card -->\n")
pay_end = text.index("            <!-- Form Actions -->\n")
text = text[:pay_start] + PAYMENT_NEW + text[pay_end:]

# ---------------------------------------------------------------------------
# 3. JS: new-row template now renders the grid markup
# ---------------------------------------------------------------------------
OLD_ROW_TEMPLATE_START = "        const emptyRowTemplate = (index) => `\n"
OLD_ROW_TEMPLATE_END = "        </tr>`;\n"

NEW_ROW_TEMPLATE = """        const emptyRowTemplate = (index) => `
        <div class="formset-row" id="row-${index}">
            <div class="formset-row-head">
                <span class="formset-row-index">${parseInt(index, 10) + 1}</span>
                <span class="formset-row-title">Sale item</span>
            </div>
            <div class="grid-2">
                <div class="form-field">
                    <label class="form-label" for="id_items-${index}-product">Product <span class="text-danger">*</span></label>
                    <select name="items-${index}-product" class="form-select select2 product-select" id="id_items-${index}-product" style="width: 100%;">
                        <option value="">Select Product</option>
                        {% for product in products %}
                        <option value="{{ product.id }}">{{ product.name }} ({{ product.sku }})</option>
                        {% endfor %}
                    </select>
                    <input type="hidden" name="items-${index}-id" id="id_items-${index}-id">
                </div>
                <div class="form-field">
                    <label class="form-label" for="id_items-${index}-unit">Unit <span class="text-danger">*</span></label>
                    <select name="items-${index}-unit" class="form-select select2 unit-select" id="id_items-${index}-unit" style="width: 100%;">
                        <option value="">Select Unit</option>
                        {% for unit in units %}
                        <option value="{{ unit.id }}">{{ unit.name }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="form-field">
                    <label class="form-label">Available Stock</label>
                    <div class="available-stock-container">
                        <span class="badge bg-secondary available-stock fw-semibold" id="available-stock-${index}">0</span>
                        <input type="hidden" class="original-stock-input" id="original-stock-${index}" value="0">
                    </div>
                </div>
                <div class="form-field">
                    <label class="form-label" for="id_items-${index}-quantity">Quantity</label>
                    <input type="number" name="items-${index}-quantity" min="1" class="form-control quantity-input"
                           id="id_items-${index}-quantity" value="1">
                    <div class="error-message stock-error-message small text-danger mt-1" id="stock-error-${index}" style="display: none;"></div>
                </div>
                <div class="form-field">
                    <label class="form-label" for="id_items-${index}-sale_price">Sale Price</label>
                    <input type="number" name="items-${index}-sale_price" min="0" step="0.01"
                           class="form-control price-input" id="id_items-${index}-sale_price" value="0">
                </div>
                <div class="form-field">
                    <label class="form-label">Unit Price</label>
                    <div class="form-value unit-price fw-semibold" id="unit-price-${index}">0</div>
                </div>
                <div class="form-field">
                    <label class="form-label">Subtotal</label>
                    <div class="form-value subtotal fw-bold text-primary" id="subtotal-${index}">0</div>
                </div>
                <div class="form-field form-field-actions">
                    <label class="form-label">Actions</label>
                    <button type="button" class="btn btn-sm btn-outline-danger rounded-circle p-1 remove-form-row" title="Remove item">
                        <i class="ti ti-trash fs-6"></i>
                    </button>
                </div>
            </div>
        </div>`;
"""

tpl_start = text.index(OLD_ROW_TEMPLATE_START)
tpl_end = text.index(OLD_ROW_TEMPLATE_END, tpl_start) + len(OLD_ROW_TEMPLATE_END)
text = text[:tpl_start] + NEW_ROW_TEMPLATE + text[tpl_end:]

# ---------------------------------------------------------------------------
# 4. JS: empty-state syncing
# ---------------------------------------------------------------------------
OLD_GRAND_TOTAL = """    // Update grand total and all related calculations
    function updateGrandTotal() {"""
NEW_GRAND_TOTAL = """    // Show a helpful empty state while the sale has no line items
    function syncItemsEmptyState() {
        const empty = document.getElementById('sale-items-empty');
        const addBtn = document.getElementById('add-form-row');
        const hasRows = document.querySelectorAll('#formset-body .formset-row').length > 0;
        if (empty) empty.style.display = hasRows ? 'none' : '';
        if (addBtn) addBtn.classList.toggle('d-none', !hasRows);
    }

    // Update grand total and all related calculations
    function updateGrandTotal() {"""
assert OLD_GRAND_TOTAL in text
text = text.replace(OLD_GRAND_TOTAL, NEW_GRAND_TOTAL, 1)

# call sync after removing a row
OLD_REMOVE = """            if (row && confirm('Are you sure you want to remove this item?')) {
                productStockMap.delete(row);
                row.remove();
                updateGrandTotal();
                validateAllRows();
            }"""
NEW_REMOVE = """            if (row && confirm('Are you sure you want to remove this item?')) {
                productStockMap.delete(row);
                row.remove();
                updateGrandTotal();
                validateAllRows();
                syncItemsEmptyState();
            }"""
assert OLD_REMOVE in text
text = text.replace(OLD_REMOVE, NEW_REMOVE, 1)

# call sync after adding a row
OLD_ADD = """                const productSelect = lastRow.querySelector('.product-select');
                if (productSelect) setTimeout(() => $(productSelect).select2('open'), 100);
            });
        }"""
NEW_ADD = """                const productSelect = lastRow.querySelector('.product-select');
                if (productSelect) setTimeout(() => $(productSelect).select2('open'), 100);

                syncItemsEmptyState();
            });
        }

        // The empty state carries its own "Add Item" action
        const addBtnEmpty = document.getElementById('add-form-row-empty');
        if (addBtnEmpty && addBtn) {
            addBtnEmpty.addEventListener('click', () => addBtn.click());
        }"""
assert OLD_ADD in text
text = text.replace(OLD_ADD, NEW_ADD, 1)

# select2 placeholders must not treat the payment method as a product
OLD_SELECT2 = """        if (window.jQuery && jQuery().select2) {
            $('.select2').select2({ width: '100%', placeholder: function() {
                return $(this).hasClass('product-select') ? 'Select product' : 'Select unit';
            } });
        }"""
NEW_SELECT2 = """        if (window.jQuery && jQuery().select2) {
            $('.select2').select2({ width: '100%', placeholder: function() {
                if ($(this).hasClass('product-select')) return 'Select product';
                if ($(this).hasClass('unit-select')) return 'Select unit';
                return 'Select';
            } });
        }"""
assert OLD_SELECT2 in text
text = text.replace(OLD_SELECT2, NEW_SELECT2, 1)

# initial empty-state sync
OLD_INIT = """        // Initialize calculations
        setTimeout(() => {
            document.querySelectorAll('.formset-row').forEach(row => updateRowSubtotal(row));"""
NEW_INIT = """        // Initialize calculations
        syncItemsEmptyState();
        setTimeout(() => {
            document.querySelectorAll('.formset-row').forEach(row => updateRowSubtotal(row));"""
assert OLD_INIT in text
text = text.replace(OLD_INIT, NEW_INIT, 1)

# ---------------------------------------------------------------------------
# 5. Template CSS: retarget rules at the grid markup
# ---------------------------------------------------------------------------
OLD_VALUE_CSS = """    /* Specifically target the columns for larger text */
    .table tbody td:nth-child(3) .badge,  /* Available Stock column */
    .table tbody td:nth-child(6) .unit-price,  /* Unit Price column */
    .table tbody td:nth-child(7) .subtotal {  /* Subtotal column */
        font-size: 1rem;
        font-weight: 700;
    }"""
NEW_VALUE_CSS = """    /* Sale-item values inside the grid layout */
    .formset-row .available-stock,
    .formset-row .unit-price,
    .formset-row .subtotal {
        font-size: 1rem;
        font-weight: 700;
    }"""
assert OLD_VALUE_CSS in text
text = text.replace(OLD_VALUE_CSS, NEW_VALUE_CSS, 1)

OLD_HOVER_CSS = """    .formset-row {
        transition: all 0.2s ease;
    }
    
    .formset-row:hover {
        background-color: #f8fafc;
    }
    """
NEW_HOVER_CSS = """    .formset-row {
        transition: all 0.2s ease;
    }
    """
assert OLD_HOVER_CSS in text
text = text.replace(OLD_HOVER_CSS, NEW_HOVER_CSS, 1)

OLD_MOBILE_CSS = """        .formset-row td {
            padding: 0.75rem;
        }"""
NEW_MOBILE_CSS = """        .formset-row {
            padding: 0.85rem;
        }"""
assert OLD_MOBILE_CSS in text
text = text.replace(OLD_MOBILE_CSS, NEW_MOBILE_CSS, 1)

OLD_MOBILE_FONT_CSS = """        .unit-price, .subtotal {
            font-size: 2rem;
        }"""
NEW_MOBILE_FONT_CSS = """        .unit-price, .subtotal {
            font-size: 1rem;
        }"""
assert OLD_MOBILE_FONT_CSS in text
text = text.replace(OLD_MOBILE_FONT_CSS, NEW_MOBILE_FONT_CSS, 1)

# The wide-viewport rules referenced the old items table; the grid needs none
OLD_WIDE_CSS = """        /* Sale-items table: fixed columns so nothing is squeezed or pushed
           into horizontal scroll inside the half-width card (header text
           wraps instead of forcing the column wider). */
        #saleitem-formset table {
            table-layout: fixed;
            width: 100%;
        }

        #saleitem-formset th {
            min-width: 0 !important;
            width: auto !important;
            white-space: normal;
        }

        #saleitem-formset th:nth-child(1) { width: 23% !important; }
        #saleitem-formset th:nth-child(2) { width: 12% !important; }
        #saleitem-formset th:nth-child(3) { width: 10% !important; }
        #saleitem-formset th:nth-child(4) { width: 11% !important; }
        #saleitem-formset th:nth-child(5) { width: 11% !important; }
        #saleitem-formset th:nth-child(6) { width: 11% !important; }
        #saleitem-formset th:nth-child(7) { width: 13% !important; }
        #saleitem-formset th:nth-child(8) { width: 9% !important; }

        #saleitem-formset td {
            overflow: hidden;
        }

        .sale-form-col #saleitem-formset .select2-container {
            max-width: 100% !important;
        }

        .sale-form-col .available-stock {
            padding: 6px 8px !important;
        }"""
NEW_WIDE_CSS = """        /* Sale items are a 2-column grid inside each card, so they stay
           readable even in a half-width column. */
        .sale-form-col .sale-items {
            gap: 0.75rem;
        }

        .sale-form-col .formset-row {
            padding: 0.85rem 0.95rem 0.95rem;
        }

        .sale-form-col .formset-row .grid-2 {
            gap: 0.75rem 0.9rem;
        }

        .sale-form-col #saleitem-formset .select2-container {
            max-width: 100% !important;
        }

        .sale-form-col .available-stock {
            padding: 6px 8px !important;
        }"""
assert OLD_WIDE_CSS in text
text = text.replace(OLD_WIDE_CSS, NEW_WIDE_CSS, 1)

# ---------------------------------------------------------------------------
# Write back with the original line endings
# ---------------------------------------------------------------------------
out = text.replace("\n", "\r\n")
with io.open(PATH, "w", encoding="utf-8", newline="") as fh:
    fh.write(out)

print("record_sales.html updated: %d -> %d bytes" % (len(raw), len(out)))
