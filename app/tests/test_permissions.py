"""
Permission and access-control tests.

Covers the RBAC side of the transformation, next to the tenant isolation
tests in ``test_tenancy.py``:

* the effective modules of a user are the union of the modules of their roles;
* the navigation menu only shows the entries the user may actually open;
* the settings workspace only offers the tabs the user's modules unlock and
  refuses a tab that is not theirs (404, not a redirect);
* the audit trail is readable by the Settings and Role Management modules
  and by platform administrators only;
* the dashboard quick actions are filtered by the same modules;
* the platform area stays closed for business users.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from app.context_processors import app_menu
from app.models.audit import AuditLog
from app.models.human_resource import Role, UserProfile
from app.models.tenancy import Business
from app.utils.decorators import require_module_access, require_url_access
from app.utils.module_mapping import (
    QUICK_ACTIONS, get_quick_actions, user_has_module_access,
    user_has_url_access,
)
from app.views.settings_views import TABS_BY_SLUG, visible_tabs

User = get_user_model()

# Module ids of the RBAC model (see app/models/human_resource.py).
MODULE_INVENTORY = 2
MODULE_STOCK = 3
MODULE_SALES = 4
MODULE_USERS = 7
MODULE_SETTINGS = 9
MODULE_ROLES = 15


class PermissionTestBase(TestCase):
    """A business with one user per interesting role."""

    def setUp(self):
        self.business = Business.objects.create(name='Permission Traders')
        self.sales_user = self.make_user('sales_clerk', [MODULE_SALES])
        self.stock_user = self.make_user('stock_clerk', [MODULE_STOCK])
        self.admin_user = self.make_user('biz_admin', [
            MODULE_INVENTORY, MODULE_STOCK, MODULE_SALES, MODULE_USERS,
            MODULE_SETTINGS, MODULE_ROLES,
        ])

    def make_user(self, username, modules, business=None, is_superuser=False):
        user = User.objects.create_user(
            username=username, password='pw12345678', email=f'{username}@example.com',
        )
        if is_superuser:
            user.is_superuser = True
            user.save(update_fields=['is_superuser'])
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.business = business or self.business
        profile.is_platform_admin = False
        profile.save()
        role = Role.objects.create(
            name=f'{username} role', business=profile.business, is_system_role=True,
        )
        role.set_modules(modules)
        profile.roles.add(role)
        profile.refresh_from_db()
        return user

    def login(self, user):
        self.assertTrue(self.client.login(username=user.username, password='pw12345678'))
        return user


class EffectiveModuleTests(PermissionTestBase):
    """The modules a user holds come from their roles."""

    def test_modules_are_the_union_of_the_roles(self):
        role = Role.objects.create(
            name='Extra role', business=self.business, is_system_role=True,
        )
        role.set_modules([MODULE_USERS])
        self.sales_user.profile.roles.add(role)
        self.sales_user.profile.refresh_from_db()
        self.assertEqual(
            self.sales_user.profile.effective_modules,
            sorted([MODULE_SALES, MODULE_USERS]),
        )

    def test_user_without_a_role_has_no_modules(self):
        user = User.objects.create_user(username='nobody', password='pw12345678')
        UserProfile.objects.get_or_create(user=user)
        self.assertFalse(user_has_module_access(user, MODULE_SALES))

    def test_superuser_bypasses_the_module_check(self):
        superuser = self.make_user('root', [], is_superuser=True)
        self.assertTrue(user_has_module_access(superuser, MODULE_ROLES))
        self.assertTrue(user_has_url_access(superuser, 'roles_list_page'))

    def test_url_access_follows_the_url_to_module_map(self):
        self.assertTrue(user_has_url_access(self.sales_user, 'sales_list'))
        self.assertFalse(user_has_url_access(self.sales_user, 'roles_list_page'))

    def test_anonymous_users_have_no_access(self):
        from django.contrib.auth.models import AnonymousUser
        self.assertFalse(user_has_module_access(AnonymousUser(), MODULE_SALES))


class MenuPermissionTests(PermissionTestBase):
    """The menu is built from the modules of the signed-in user."""

    def menu_labels(self, user):
        request = type('R', (), {})()
        request.user = user
        menu = app_menu(request)['app_menu']
        labels = set()

        def walk(items):
            for item in items:
                labels.add(item['label'])
                walk(item.get('children', []))
        walk(menu)
        return labels

    def test_sales_user_does_not_see_role_management(self):
        labels = self.menu_labels(self.sales_user)
        self.assertIn('Sales List', labels)
        self.assertNotIn('Roles & Permissions', labels)
        self.assertNotIn('Users', labels)

    def test_admin_user_sees_the_whole_menu(self):
        labels = self.menu_labels(self.admin_user)
        self.assertIn('Roles & Permissions', labels)
        self.assertIn('Users', labels)
        self.assertIn('Audit Trail', labels)

    def test_platform_section_is_only_for_platform_admins(self):
        labels = self.menu_labels(self.admin_user)
        self.assertNotIn('Platform', labels)

        profile = self.admin_user.profile
        profile.is_platform_admin = True
        profile.save(update_fields=['is_platform_admin'])
        self.admin_user.refresh_from_db()
        self.assertIn('Platform', self.menu_labels(self.admin_user))


class SettingsWorkspacePermissionTests(PermissionTestBase):
    """The settings workspace only opens the tabs the user's modules unlock."""

    def slugs(self, user):
        return [tab['slug'] for tab in visible_tabs(user)]

    def test_personal_tabs_are_open_to_everybody(self):
        for slug in ('notifications', 'security', 'appearance'):
            self.assertIn(slug, self.slugs(self.sales_user))

    def test_business_tabs_are_hidden_without_the_module(self):
        slugs = self.slugs(self.sales_user)
        for slug in ('profile', 'structure', 'users', 'inventory', 'audit', 'data'):
            self.assertNotIn(slug, slugs)

    def test_the_sales_module_unlocks_the_commerce_tab(self):
        # The commerce tab is shared by Stock and Sales, so a sales clerk
        # opens it - the links inside it stay filtered per module.
        self.assertIn('commerce', self.slugs(self.sales_user))

    def test_settings_module_unlocks_the_company_tabs(self):
        slugs = self.slugs(self.admin_user)
        for slug in ('profile', 'structure', 'inventory', 'audit', 'data'):
            self.assertIn(slug, slugs)

    def test_roles_module_unlocks_the_users_tab(self):
        user = self.make_user('role_manager', [MODULE_ROLES])
        self.assertIn('users', self.slugs(user))
        self.assertIn('audit', self.slugs(user))

    def test_a_forbidden_tab_is_not_found(self):
        self.login(self.sales_user)
        response = self.client.get(reverse('settings_tab', kwargs={'slug': 'profile'}))
        self.assertEqual(response.status_code, 404)

    def test_an_allowed_tab_opens(self):
        self.login(self.admin_user)
        response = self.client.get(reverse('settings_tab', kwargs={'slug': 'profile'}))
        self.assertEqual(response.status_code, 200)

    def test_settings_home_opens_the_first_permitted_tab(self):
        self.login(self.sales_user)
        response = self.client.get(reverse('settings_page'))
        self.assertEqual(response.status_code, 302)
        first = visible_tabs(self.sales_user)[0]['slug']
        self.assertTrue(response['Location'].endswith(
            reverse('settings_tab', kwargs={'slug': first})
        ))

    def test_every_tab_declares_its_modules(self):
        for slug, tab in TABS_BY_SLUG.items():
            self.assertIn('modules', tab, slug)
            self.assertTrue(tab['label'], slug)


class AuditAccessTests(PermissionTestBase):
    """The audit trail is readable by a small, explicit group."""

    def log(self, business=None, actor=None, description='did a thing'):
        return AuditLog.objects.create(
            actor=actor, actor_name=actor.username if actor else 'system',
            business=business or self.business,
            category='data', action='update', description=description,
        )

    def test_a_user_without_the_right_modules_is_refused(self):
        self.login(self.sales_user)
        response = self.client.get(reverse('audit_log_page'))
        self.assertEqual(response.status_code, 404)

    def test_the_settings_module_may_read_the_trail(self):
        self.login(self.admin_user)
        response = self.client.get(reverse('audit_log_page'))
        self.assertEqual(response.status_code, 200)

    def test_the_roles_module_may_read_the_trail(self):
        user = self.make_user('role_manager', [MODULE_ROLES])
        self.login(user)
        response = self.client.get(reverse('audit_log_page'))
        self.assertEqual(response.status_code, 200)

    def test_a_business_admin_only_sees_the_events_of_their_business(self):
        other = Business.objects.create(name='Other Traders')
        self.log(business=self.business, description='our event')
        self.log(business=other, description='their event')

        self.login(self.admin_user)
        response = self.client.get(reverse('audit_log_page'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'our event')
        self.assertNotContains(response, 'their event')

    def test_a_platform_admin_sees_every_event(self):
        other = Business.objects.create(name='Other Traders')
        self.log(business=self.business, description='our event')
        self.log(business=other, description='their event')

        profile = self.admin_user.profile
        profile.is_platform_admin = True
        profile.save(update_fields=['is_platform_admin'])
        self.login(self.admin_user)
        response = self.client.get(reverse('audit_log_page'))
        self.assertContains(response, 'our event')
        self.assertContains(response, 'their event')

    def test_the_export_is_gated_the_same_way(self):
        self.login(self.sales_user)
        response = self.client.get(reverse('audit_log_export'))
        self.assertEqual(response.status_code, 404)

    def test_a_detail_of_a_foreign_event_is_not_found(self):
        other = Business.objects.create(name='Other Traders')
        entry = self.log(business=other, description='their event')
        self.login(self.admin_user)
        response = self.client.get(
            reverse('audit_log_detail', kwargs={'pk': entry.pk})
        )
        self.assertEqual(response.status_code, 404)


class QuickActionTests(PermissionTestBase):
    """The dashboard only offers shortcuts the user may open."""

    def test_actions_are_filtered_by_module(self):
        actions = get_quick_actions(self.sales_user)
        labels = [action['label'] for action in actions]
        self.assertIn('Record a sale', labels)
        self.assertNotIn('Roles & permissions', labels)
        self.assertNotIn('Company settings', labels)

    def test_an_admin_sees_the_administrative_shortcuts(self):
        labels = [action['label'] for action in get_quick_actions(self.admin_user)]
        self.assertIn('Roles & permissions', labels)
        self.assertIn('Company settings', labels)

    def test_every_action_names_a_module_and_a_url(self):
        for action in QUICK_ACTIONS:
            self.assertIn('module', action)
            self.assertIn('url_name', action)

    def test_anonymous_visitors_get_no_shortcuts(self):
        from django.contrib.auth.models import AnonymousUser
        self.assertEqual(get_quick_actions(AnonymousUser()), [])


class DecoratorTests(PermissionTestBase):
    """The access decorators behave the way the pages expect."""

    def test_require_module_access_lets_a_holder_through(self):
        @require_module_access(MODULE_SALES)
        def view(request):
            from django.http import HttpResponse
            return HttpResponse('ok')

        self.login(self.sales_user)
        response = self.client.get('/')
        self.assertEqual(view(response.wsgi_request).status_code, 200)

    def test_require_module_access_refuses_a_stranger(self):
        from django.http import Http404

        @require_module_access(MODULE_ROLES)
        def view(request):
            from django.http import HttpResponse
            return HttpResponse('ok')

        self.login(self.sales_user)
        response = self.client.get('/')
        with self.assertRaises(Http404):
            view(response.wsgi_request)

    def test_require_url_access_uses_the_url_map(self):
        from django.http import Http404

        @require_url_access('roles_list_page')
        def view(request):
            from django.http import HttpResponse
            return HttpResponse('ok')

        self.login(self.sales_user)
        response = self.client.get('/')
        with self.assertRaises(Http404):
            view(response.wsgi_request)


class PlatformAreaPermissionTests(PermissionTestBase):
    """The platform area and its counters."""

    def make_platform_admin(self, username='platform_admin'):
        user = User.objects.create_user(
            username=username, password='pw12345678', email=f'{username}@example.com',
        )
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.is_platform_admin = True
        profile.save()
        return user

    def test_a_business_admin_cannot_reach_the_platform_area(self):
        self.login(self.admin_user)
        for name in ('platform_dashboard', 'platform_business_list',
                     'platform_business_create'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 404, name)

    def test_the_dashboard_counts_superusers_as_platform_admins(self):
        self.make_user('root', [], is_superuser=True)
        self.login(self.make_platform_admin())
        response = self.client.get(reverse('platform_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['stats']['platform_admins'], 2)
