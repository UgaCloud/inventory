"""
Tenant isolation and platform administration tests.

Covers the acceptance criteria of the multi-tenant phase:

* a business user only ever sees rows of their own business — on list pages,
  on detail URLs (record id in the URL) and on API-style requests;
* a business user cannot reach the platform Super Administrator area;
* the platform Super Administrator can register a business, provision its
  first Business Administrator and suspend/activate it;
* rows created by a business user are stamped with their business;
* platform administrators keep platform-wide visibility.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from app.managers import clear_tenant_actor, set_tenant_actor
from app.models.customers import Customer
from app.models.human_resource import Role, UserProfile
from app.models.organization import Branch
from app.models.products import Category, Product, StoreLocation
from app.models.tenancy import (
    Business, business_scope, current_business, user_is_platform_admin,
)
from app.models.transactions import Sales

User = get_user_model()

ALL_MODULES = list(range(1, 17))


class TenantTestBase(TestCase):
    """Two businesses, each with a store, a product, a customer and a user."""

    def setUp(self):
        self.business_a = Business.objects.create(name='Alpha Traders')
        self.business_b = Business.objects.create(name='Beta Supplies')

        self.branch_a = Branch.objects.create(
            name='Alpha Kampala', business=self.business_a,
            contact_person='Alpha', contact='000',
        )
        self.branch_b = Branch.objects.create(
            name='Beta Jinja', business=self.business_b,
            contact_person='Beta', contact='111',
        )
        self.store_a = StoreLocation.objects.create(
            name='Alpha Store', branch=self.branch_a, business=self.business_a,
        )
        self.store_b = StoreLocation.objects.create(
            name='Beta Store', branch=self.branch_b, business=self.business_b,
        )

        self.category = Category.objects.create(name='General')

        self.product_a = Product.objects.create(
            name='Alpha Product', sku='ALPHA-1', category=self.category,
            business=self.business_a,
        )
        self.product_b = Product.objects.create(
            name='Beta Product', sku='BETA-1', category=self.category,
            business=self.business_b,
        )
        self.customer_a = Customer.objects.create(
            name='Alpha Customer', business=self.business_a,
        )
        self.customer_b = Customer.objects.create(
            name='Beta Customer', business=self.business_b,
        )

        self.user_a = self.make_user('alpha_admin', self.business_a)
        self.user_b = self.make_user('beta_admin', self.business_b)

        self.sale_a = Sales.objects.create(
            receipt_no='ALPHA-SALE-1', store=self.store_a,
            status='FULFILLED', recorded_by=self.user_a, total_amount=100,
        )
        self.sale_b = Sales.objects.create(
            receipt_no='BETA-SALE-1', store=self.store_b,
            status='FULFILLED', recorded_by=self.user_b, total_amount=200,
        )

    def make_user(self, username, business, password='pw12345678'):
        """Create a business user with full module access (not platform)."""
        user = User.objects.create_user(
            username=username, password=password, email=f'{username}@example.com',
        )
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.business = business
        profile.is_platform_admin = False
        profile.save()

        role = Role.objects.create(
            name=f'{username} role', business=business, is_system_role=True,
        )
        role.set_modules(ALL_MODULES)
        profile.roles.add(role)
        profile.refresh_from_db()
        return user

    def make_platform_admin(self, username='platform_admin'):
        user = User.objects.create_user(
            username=username, password='pw12345678', email=f'{username}@example.com',
        )
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.is_platform_admin = True
        profile.save()
        return user

    def tearDown(self):
        clear_tenant_actor()


class QuerysetScopingTests(TenantTestBase):
    """The manager scopes every queryset of the acting user."""

    def test_business_user_sees_only_own_products(self):
        set_tenant_actor(self.user_a)
        self.assertEqual(
            list(Product.objects.values_list('name', flat=True)), ['Alpha Product']
        )

    def test_business_user_sees_only_own_sales(self):
        set_tenant_actor(self.user_a)
        self.assertEqual(
            list(Sales.objects.values_list('receipt_no', flat=True)), ['ALPHA-SALE-1']
        )

    def test_business_user_sees_only_own_customers(self):
        set_tenant_actor(self.user_a)
        self.assertEqual(
            list(Customer.objects.values_list('name', flat=True)), ['Alpha Customer']
        )

    def test_platform_admin_sees_every_business(self):
        platform_admin = self.make_platform_admin()
        set_tenant_actor(platform_admin)
        self.assertEqual(Product.objects.count(), 2)
        self.assertEqual(Sales.objects.count(), 2)
        self.assertEqual(Customer.objects.count(), 2)

    def test_no_actor_means_no_scoping(self):
        """Maintenance code (commands, imports) keeps working."""
        clear_tenant_actor()
        self.assertEqual(Product.objects.count(), 2)

    def test_business_scope_helper_matches_the_manager(self):
        scoped = business_scope(self.user_a, Product.objects.all())
        self.assertEqual(list(scoped.values_list('name', flat=True)), ['Alpha Product'])

    def test_current_business_resolves_the_tenant(self):
        self.assertEqual(current_business(self.user_a), self.business_a)
        self.assertEqual(current_business(self.user_b), self.business_b)

    def test_platform_admin_flag(self):
        self.assertFalse(user_is_platform_admin(self.user_a))
        self.assertTrue(user_is_platform_admin(self.make_platform_admin()))

    def test_created_rows_are_stamped_with_the_acting_business(self):
        set_tenant_actor(self.user_a)
        product = Product.objects.create(name='Alpha New', sku='ALPHA-2')
        self.assertEqual(product.business, self.business_a)

    def test_rows_created_outside_a_request_stay_unassigned(self):
        product = Product.objects.create(name='Unassigned', sku='NONE-1')
        self.assertIsNone(product.business)


class UrlIsolationTests(TenantTestBase):
    """Cross-tenant access through the URL bar is rejected server-side."""

    def login(self, user):
        self.assertTrue(self.client.login(username=user.username, password='pw12345678'))
        return user

    def test_product_list_only_shows_own_products(self):
        self.login(self.user_a)
        response = self.client.get(reverse('products_page'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alpha Product')
        self.assertNotContains(response, 'Beta Product')

    def test_foreign_product_detail_is_not_found(self):
        self.login(self.user_a)
        response = self.client.get(
            reverse('product_details_page', kwargs={'_product_id': self.product_b.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_foreign_sales_detail_is_not_found(self):
        self.login(self.user_a)
        response = self.client.get(
            reverse('sales_detail', kwargs={'pk': self.sale_b.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_own_sales_detail_is_reachable(self):
        self.login(self.user_a)
        response = self.client.get(
            reverse('sales_detail', kwargs={'pk': self.sale_a.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_sales_list_only_shows_own_sales(self):
        self.login(self.user_a)
        response = self.client.get(reverse('sales_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ALPHA-SALE-1')
        self.assertNotContains(response, 'BETA-SALE-1')

    def test_customer_list_only_shows_own_customers(self):
        self.login(self.user_a)
        response = self.client.get(reverse('customer_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alpha Customer')
        self.assertNotContains(response, 'Beta Customer')

    def test_foreign_customer_detail_is_not_found(self):
        self.login(self.user_a)
        response = self.client.get(
            reverse('customer_detail', kwargs={'pk': self.customer_b.pk})
        )
        self.assertEqual(response.status_code, 404)


class RoleTenantIsolationTests(TenantTestBase):
    """Custom roles are per business and cannot escalate privileges."""

    def login(self, user):
        self.assertTrue(self.client.login(username=user.username, password='pw12345678'))
        return user

    def test_two_businesses_may_use_the_same_role_name(self):
        role_a = Role.objects.create(name='Sales Officer', business=self.business_a)
        role_b = Role.objects.create(name='Sales Officer', business=self.business_b)
        self.assertNotEqual(role_a.pk, role_b.pk)
        self.assertEqual(Role.objects.filter(name='Sales Officer').count(), 2)

    def test_role_groups_are_scoped_per_business(self):
        """Django groups are global, so they must carry the tenant prefix."""
        role_a = Role.objects.create(name='Sales Officer', business=self.business_a)
        role_b = Role.objects.create(name='Sales Officer', business=self.business_b)
        self.assertNotEqual(role_a.group.name, role_b.group.name)
        self.assertTrue(role_a.group.name.startswith(self.business_a.slug))
        self.assertTrue(role_b.group.name.startswith(self.business_b.slug))

    def test_platform_role_name_stays_unique(self):
        Role.objects.create(name='Platform Template', business=None)
        with self.assertRaises(Exception):
            Role.objects.create(name='Platform Template', business=None)

    def test_business_admin_cannot_create_a_superuser_role(self):
        self.login(self.user_a)
        response = self.client.post(reverse('role_create_page'), {
            'name': 'Escalation',
            'description': 'should not be superuser',
            'modules': ['2', '4'],
        })
        self.assertIn(response.status_code, (200, 302))
        role = Role.objects.filter(name='Escalation').first()
        self.assertIsNotNone(role)
        self.assertFalse(role.is_superuser)
        self.assertEqual(role.business, self.business_a)

    def test_business_admin_cannot_edit_a_platform_role(self):
        platform_role = Role.objects.create(
            name='Shared Template', business=None, is_system_role=True,
        )
        self.login(self.user_a)
        response = self.client.get(
            reverse('role_edit_page', kwargs={'role_id': platform_role.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_roles_of_another_business_are_not_listed(self):
        Role.objects.create(name='Beta Only', business=self.business_b)
        self.login(self.user_a)
        response = self.client.get(reverse('roles_list_page'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Beta Only')

    def test_business_admin_cannot_assign_a_role_to_a_foreign_user(self):
        role = Role.objects.create(name='Alpha Role', business=self.business_a)
        self.login(self.user_a)
        response = self.client.post(
            reverse('role_assign_to_user_page', kwargs={
                'role_id': role.pk, 'user_id': self.user_b.pk,
            })
        )
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(role, self.user_b.profile.roles.all())


class PlatformAdministrationTests(TenantTestBase):
    """The platform Super Administrator area and its separation of powers."""

    def login(self, user):
        self.assertTrue(self.client.login(username=user.username, password='pw12345678'))
        return user

    def test_business_admin_cannot_reach_the_platform_area(self):
        self.login(self.user_a)
        for name in ('platform_dashboard', 'platform_business_list',
                     'platform_business_create'):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 404, name)

    def test_platform_admin_can_see_every_business(self):
        self.login(self.make_platform_admin())
        response = self.client.get(reverse('platform_business_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alpha Traders')
        self.assertContains(response, 'Beta Supplies')

    def test_platform_admin_can_register_a_business_with_its_admin(self):
        self.login(self.make_platform_admin())
        response = self.client.post(reverse('platform_business_create'), {
            'name': 'Gamma Stores',
            'contact_email': 'gamma@example.com',
            'admin_username': 'gamma_admin',
            'admin_email': 'gamma_admin@example.com',
            'admin_password': 'strongpass123',
        })
        self.assertEqual(response.status_code, 302)

        business = Business.objects.get(name='Gamma Stores')
        self.assertTrue(business.is_active)

        admin = User.objects.get(username='gamma_admin')
        profile = admin.profile
        self.assertEqual(profile.business, business)
        self.assertFalse(profile.is_platform_admin)
        self.assertTrue(profile.roles.exists())
        # The provisioned administrator is a business admin, not platform staff.
        self.assertFalse(user_is_platform_admin(admin))

    def test_platform_admin_can_suspend_and_activate_a_business(self):
        self.login(self.make_platform_admin())
        self.client.post(
            reverse('platform_business_set_status',
                    kwargs={'business_id': self.business_b.pk}),
            {'action': 'suspend'},
        )
        self.business_b.refresh_from_db()
        self.assertEqual(self.business_b.status, Business.STATUS_SUSPENDED)

        self.client.post(
            reverse('platform_business_set_status',
                    kwargs={'business_id': self.business_b.pk}),
            {'action': 'activate'},
        )
        self.business_b.refresh_from_db()
        self.assertEqual(self.business_b.status, Business.STATUS_ACTIVE)

    def test_platform_dashboard_reports_business_and_user_counts(self):
        self.login(self.make_platform_admin())
        response = self.client.get(reverse('platform_dashboard'))
        self.assertEqual(response.status_code, 200)
        # Every registered business is counted (the migrated "Default
        # Business" included) and both test businesses are listed.
        self.assertEqual(
            response.context['stats']['businesses_total'],
            Business.objects.count(),
        )
        self.assertGreaterEqual(response.context['stats']['users_total'], 3)
        self.assertContains(response, 'Alpha Traders')
        self.assertContains(response, 'Beta Supplies')
