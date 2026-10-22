"""
The centralized settings workspace.

One page holds every setting of the application, grouped into ten tabs. The
tabs a user may open depend on the modules they hold, so a sales clerk sees
their personal preferences while a business administrator also sees the
audit trail and the user management shortcuts.

The workspace never duplicates an existing screen: tabs that have no form of
their own (structure, users, inventory, commerce, data) collect the record
counts of the business and link to the pages that already do the work.
"""
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.sessions.models import Session
from django.db.models import Count
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.module_loading import import_string

from app.forms.settings_forms import (
    AppearancePreferenceForm, NotificationPreferenceForm,
)
from app.models.audit import AuditLog
from app.models.customers import Customer
from app.models.human_resource import Department, Designation, Employee, Role, UserProfile
from app.models.organization import Branch, OrganizationSetting
from app.models.preferences import UserPreference
from app.models.products import Category, Product, StoreLocation, UnitOfMeasure
from app.models.suppliers import Supplier
from app.models.tenancy import user_is_platform_admin
from app.models.transactions import Inventory, PurchaseOrder, Sales
from app.utils.module_mapping import user_has_module_access, user_has_url_access

# Module ids of the RBAC model (see app/models/human_resource.py).
MODULE_INVENTORY = 2
MODULE_STOCK = 3
MODULE_SALES = 4
MODULE_USERS = 7
MODULE_SETTINGS = 9
MODULE_ROLES = 15


SETTINGS_TABS = (
    {
        'slug': 'profile',
        'label': 'Business profile',
        'icon': 'ti ti-building-store',
        'description': 'Company name, logo, contacts and currency',
        'modules': (MODULE_SETTINGS,),
    },
    {
        'slug': 'structure',
        'label': 'Structure',
        'icon': 'ti ti-sitemap',
        'description': 'Branches, stores, categories and units',
        'modules': (MODULE_INVENTORY, MODULE_SETTINGS),
    },
    {
        'slug': 'users',
        'label': 'Users & roles',
        'icon': 'ti ti-users',
        'description': 'Accounts, roles and the people behind them',
        'modules': (MODULE_USERS, MODULE_ROLES),
    },
    {
        'slug': 'inventory',
        'label': 'Inventory',
        'icon': 'ti ti-package',
        'description': 'Catalogue, stock locations and pricing',
        'modules': (MODULE_INVENTORY,),
    },
    {
        'slug': 'commerce',
        'label': 'Sales & purchasing',
        'icon': 'ti ti-receipt',
        'description': 'Customers, suppliers and trading defaults',
        'modules': (MODULE_STOCK, MODULE_SALES),
    },
    {
        'slug': 'notifications',
        'label': 'Notifications',
        'icon': 'ti ti-bell',
        'description': 'Choose the events that notify you',
        'modules': None,  # personal setting, open to everybody
    },
    {
        'slug': 'security',
        'label': 'Security & sessions',
        'icon': 'ti ti-shield-lock',
        'description': 'Password, active sessions and sign-in history',
        'modules': None,  # personal setting, open to everybody
    },
    {
        'slug': 'audit',
        'label': 'Audit',
        'icon': 'ti ti-history',
        'description': 'What happened in this business, and who did it',
        'modules': (MODULE_SETTINGS, MODULE_ROLES),
    },
    {
        'slug': 'appearance',
        'label': 'Appearance',
        'icon': 'ti ti-palette',
        'description': 'Theme and density of the interface',
        'modules': None,  # personal setting, open to everybody
    },
    {
        'slug': 'data',
        'label': 'Data management',
        'icon': 'ti ti-database',
        'description': 'Exports and the records of this business',
        'modules': (MODULE_SETTINGS,),
    },
)

TABS_BY_SLUG = {tab['slug']: tab for tab in SETTINGS_TABS}


def can_open_tab(user, tab):
    """True when the user may open the given tab."""
    modules = tab.get('modules')
    if modules is None:
        return True
    if not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser or user_is_platform_admin(user):
        return True
    return any(user_has_module_access(user, module_id) for module_id in modules)


def visible_tabs(user):
    """The tabs the user may open, in the order of the workspace."""
    return [tab for tab in SETTINGS_TABS if can_open_tab(user, tab)]


def _business(request):
    return getattr(request, 'business', None)


def _visible(user, items):
    """Drop the links the user is not allowed to follow."""
    return [item for item in items if user_has_url_access(user, item['url_name'])]


# ---------------------------------------------------------------------------
# Tab content
# ---------------------------------------------------------------------------

def _context_profile(request, tab):
    organization = OrganizationSetting.load_for(_business(request))
    return {
        'organization': organization,
        'is_platform_admin': user_is_platform_admin(request.user),
    }


def _context_structure(request, tab):
    cards = [
        {'label': 'Branches', 'icon': 'ti ti-home', 'count': Branch.objects.count(),
         'url_name': 'manage_branch_page'},
        {'label': 'Stores', 'icon': 'ti ti-shopping-cart', 'count': StoreLocation.objects.count(),
         'url_name': 'all_stores_inventory'},
        {'label': 'Categories', 'icon': 'ti ti-apps', 'count': Category.objects.count(),
         'url_name': 'add_category_page'},
        {'label': 'Units of measure', 'icon': 'ti ti-ruler-measure',
         'count': UnitOfMeasure.objects.count(), 'url_name': 'unit_of_measure_page'},
    ]
    links = [
        {'label': 'Manage branches', 'url_name': 'manage_branch_page', 'icon': 'ti ti-home'},
        {'label': 'Stock locations', 'url_name': 'all_stores_inventory', 'icon': 'ti ti-shopping-cart'},
        {'label': 'Product categories', 'url_name': 'add_category_page', 'icon': 'ti ti-apps'},
        {'label': 'Units of measure', 'url_name': 'unit_of_measure_page', 'icon': 'ti ti-ruler-measure'},
    ]
    return {
        'cards': _visible(request.user, cards),
        'links': _visible(request.user, links),
    }


def _context_users(request, tab):
    business = _business(request)
    users = UserProfile.objects.all()
    if business is not None:
        users = users.filter(business=business)
    cards = [
        {'label': 'Users', 'icon': 'ti ti-user', 'count': users.count(),
         'url_name': 'users_list_page'},
        {'label': 'Roles', 'icon': 'ti ti-shield', 'count': Role.objects.count(),
         'url_name': 'roles_list_page'},
        {'label': 'Employees', 'icon': 'ti ti-id-badge', 'count': Employee.objects.count(),
         'url_name': 'employee_page'},
        {'label': 'Departments', 'icon': 'ti ti-building', 'count': Department.objects.count(),
         'url_name': 'department_page'},
    ]
    links = [
        {'label': 'Manage users', 'url_name': 'users_list_page', 'icon': 'ti ti-user'},
        {'label': 'Roles & permissions', 'url_name': 'roles_list_page', 'icon': 'ti ti-shield'},
        {'label': 'Employees', 'url_name': 'employee_page', 'icon': 'ti ti-id-badge'},
        {'label': 'Departments', 'url_name': 'department_page', 'icon': 'ti ti-building'},
        {'label': 'Designations', 'url_name': 'designation_page', 'icon': 'ti ti-id-badge-2'},
    ]
    return {
        'cards': _visible(request.user, cards),
        'links': _visible(request.user, links),
    }


def _context_inventory(request, tab):
    cards = [
        {'label': 'Products', 'icon': 'ti ti-package', 'count': Product.objects.count(),
         'url_name': 'products_page'},
        {'label': 'Stock locations', 'icon': 'ti ti-shopping-cart',
         'count': StoreLocation.objects.count(), 'url_name': 'all_stores_inventory'},
        {'label': 'Stock records', 'icon': 'ti ti-layers', 'count': Inventory.objects.count(),
         'url_name': 'all_stores_inventory'},
        {'label': 'Categories', 'icon': 'ti ti-apps', 'count': Category.objects.count(),
         'url_name': 'add_category_page'},
    ]
    links = [
        {'label': 'Product catalogue', 'url_name': 'products_page', 'icon': 'ti ti-package'},
        {'label': 'Stock overview', 'url_name': 'all_stores_inventory', 'icon': 'ti ti-layers'},
        {'label': 'Categories', 'url_name': 'add_category_page', 'icon': 'ti ti-apps'},
        {'label': 'Units of measure', 'url_name': 'unit_of_measure_page', 'icon': 'ti ti-ruler-measure'},
        {'label': 'Stock adjustments', 'url_name': 'stock_adjustment_list',
         'icon': 'ti ti-switch-horizontal'},
    ]
    return {
        'cards': _visible(request.user, cards),
        'links': _visible(request.user, links),
    }


def _context_commerce(request, tab):
    organization = OrganizationSetting.load_for(_business(request))
    cards = [
        {'label': 'Sales', 'icon': 'ti ti-receipt', 'count': Sales.objects.count(),
         'url_name': 'sales_list'},
        {'label': 'Purchase orders', 'icon': 'ti ti-truck-delivery',
         'count': PurchaseOrder.objects.count(), 'url_name': 'purchase_order_list'},
        {'label': 'Customers', 'icon': 'ti ti-users', 'count': Customer.objects.count(),
         'url_name': 'customer_list'},
        {'label': 'Suppliers', 'icon': 'ti ti-truck', 'count': Supplier.objects.count(),
         'url_name': 'supplier_page'},
    ]
    links = [
        {'label': 'Sales list', 'url_name': 'sales_list', 'icon': 'ti ti-receipt'},
        {'label': 'Purchase orders', 'url_name': 'purchase_order_list', 'icon': 'ti ti-truck-delivery'},
        {'label': 'Customers', 'url_name': 'customer_list', 'icon': 'ti ti-users'},
        {'label': 'Suppliers', 'url_name': 'supplier_page', 'icon': 'ti ti-truck'},
        {'label': 'Sales returns', 'url_name': 'sales_returns_list', 'icon': 'ti ti-zoom-out'},
    ]
    return {
        'organization': organization,
        'cards': _visible(request.user, cards),
        'links': _visible(request.user, links),
    }


def _context_notifications(request, tab):
    preference = UserPreference.for_user(request.user)
    return {
        'preference': preference,
        'preference_form': NotificationPreferenceForm(instance=preference),
    }


def _context_security(request, tab):
    sign_ins = AuditLog.objects.filter(
        actor=request.user, action__in=['login', 'login_failed'],
    )[:10]
    return {
        'password_form': PasswordChangeForm(user=request.user),
        'sessions': _active_sessions(request),
        'sign_ins': sign_ins,
    }


def _context_audit(request, tab):
    entries = AuditLog.objects.all()[:10]
    by_category = list(
        AuditLog.objects.values('category')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    return {
        'entries': entries,
        'by_category': by_category,
        'total_entries': AuditLog.objects.count(),
    }


def _context_appearance(request, tab):
    preference = UserPreference.for_user(request.user)
    return {
        'preference': preference,
        'preference_form': AppearancePreferenceForm(instance=preference),
    }


def _context_data(request, tab):
    cards = [
        {'label': 'Products', 'icon': 'ti ti-package', 'count': Product.objects.count(),
         'url_name': 'products_page'},
        {'label': 'Sales', 'icon': 'ti ti-receipt', 'count': Sales.objects.count(),
         'url_name': 'sales_list'},
        {'label': 'Customers', 'icon': 'ti ti-users', 'count': Customer.objects.count(),
         'url_name': 'customer_list'},
        {'label': 'Audit entries', 'icon': 'ti ti-history', 'count': AuditLog.objects.count(),
         'url_name': 'audit_log_page'},
    ]
    exports = [
        {'label': 'Sales (CSV)', 'url_name': 'export_sales_csv', 'icon': 'ti ti-download'},
        {'label': 'Purchases (CSV)', 'url_name': 'export_purchase_csv', 'icon': 'ti ti-download'},
        {'label': 'Audit trail (CSV)', 'url_name': 'audit_log_export', 'icon': 'ti ti-download'},
    ]
    return {
        'cards': _visible(request.user, cards),
        'exports': _visible(request.user, exports),
    }


TAB_CONTEXTS = {
    'profile': _context_profile,
    'structure': _context_structure,
    'users': _context_users,
    'inventory': _context_inventory,
    'commerce': _context_commerce,
    'notifications': _context_notifications,
    'security': _context_security,
    'audit': _context_audit,
    'appearance': _context_appearance,
    'data': _context_data,
}


def _active_sessions(request):
    """The sign-in sessions of the current user."""
    store_class = import_string(settings.SESSION_ENGINE)
    current_key = request.session.session_key
    rows = []
    for session in Session.objects.filter(expire_date__gt=timezone.now()).order_by('-expire_date')[:50]:
        try:
            data = store_class().decode(session.session_data)
        except Exception:
            continue
        if not data.get('_auth_user_id'):
            continue
        if str(data.get('_auth_user_id')) != str(request.user.pk):
            continue
        last_activity = data.get('last_activity')
        rows.append({
            'key': session.session_key,
            'is_current': session.session_key == current_key,
            'last_activity': (
                timezone.datetime.fromtimestamp(last_activity, tz=timezone.utc)
                if last_activity else None
            ),
            'ip_address': data.get('REMOTE_ADDR') or '',
            'user_agent': (data.get('HTTP_USER_AGENT') or '')[:200],
        })
    return rows


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@login_required
def settings_home(request):
    """Open the first tab the user may see."""
    tabs = visible_tabs(request.user)
    if not tabs:
        raise Http404('No settings available')
    return redirect('settings_tab', slug=tabs[0]['slug'])


@login_required
def settings_tab(request, slug):
    """One tab of the settings workspace."""
    tab = TABS_BY_SLUG.get(slug)
    if tab is None or not can_open_tab(request.user, tab):
        raise Http404('Unknown settings tab')

    context = {
        'tab': tab,
        'active_tab': dict(tab, template=f'settings/_tab_{slug}.html'),
        'active_slug': slug,
        'tabs': visible_tabs(request.user),
        'business': _business(request),
    }

    if request.method == 'POST':
        return _save_tab(request, tab)

    context.update(TAB_CONTEXTS[slug](request, tab))
    return render(request, 'settings/workspace.html', context)


def _save_tab(request, tab):
    """Store what the form of a tab submitted."""
    slug = tab['slug']

    if slug == 'appearance':
        form = AppearancePreferenceForm(
            request.POST, instance=UserPreference.for_user(request.user)
        )
        if form.is_valid():
            form.save()
            messages.success(request, 'Your appearance settings have been saved.')
        else:
            messages.error(request, 'The appearance settings could not be saved.')
        return redirect('settings_tab', slug=slug)

    if slug == 'notifications':
        form = NotificationPreferenceForm(
            request.POST, instance=UserPreference.for_user(request.user)
        )
        if form.is_valid():
            form.save()
            messages.success(request, 'Your notification preferences have been saved.')
        else:
            messages.error(request, 'The notification preferences could not be saved.')
        return redirect('settings_tab', slug=slug)

    if slug == 'security':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Your password has been changed.')
        else:
            errors = form.errors.get('new_password2') or form.errors.get('__all__') or []
            for error in errors:
                messages.error(request, error)
            if not errors:
                messages.error(request, 'The password could not be changed.')
        return redirect('settings_tab', slug=slug)

    # The remaining tabs hold no form of their own.
    return redirect('settings_tab', slug=slug)
