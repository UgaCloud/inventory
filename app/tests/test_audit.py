"""
Audit trail tests.

Covers the acceptance criteria of the audit phase:

* a sign-in, a sign-out and a failed sign-in are recorded;
* record changes (create / update / delete) are recorded automatically with
  the previous values of the changed fields;
* entries carry the actor and the tenant of the acting user;
* the trail is tenant scoped: a business administrator only sees the entries
  of their own business, a platform administrator sees every entry;
* entries are append-only - they can be neither updated nor deleted;
* the audit UI renders, filters, paginates and exports.
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from app.managers import clear_tenant_actor, set_tenant_actor
from app.models.audit import AuditLog
from app.models.human_resource import Role, UserProfile
from app.models.products import Category, Product
from app.models.tenancy import Business
from app.services.audit_service import log_event, sanitize_changes

User = get_user_model()

ALL_MODULES = list(range(1, 17))


class AuditTestBase(TestCase):
    """Two businesses with one administrator each."""

    def setUp(self):
        self.business_a = Business.objects.create(name='Alpha Traders')
        self.business_b = Business.objects.create(name='Beta Supplies')

        self.user_a = self.make_user('alpha_admin', self.business_a)
        self.user_b = self.make_user('beta_admin', self.business_b)

        self.category = Category.objects.create(name='General')

    def make_user(self, username, business, password='pw12345678', platform=False):
        user = User.objects.create_user(
            username=username, password=password, email=f'{username}@example.com',
        )
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.business = business
        profile.is_platform_admin = platform
        profile.save()
        if not platform:
            role = Role.objects.create(
                name=f'{username} role', business=business, is_system_role=True,
            )
            role.set_modules(ALL_MODULES)
            profile.roles.add(role)
            profile.refresh_from_db()
        return user

    def tearDown(self):
        clear_tenant_actor()


class AuditServiceTests(AuditTestBase):
    """The service itself: attribution, redaction and append-only behaviour."""

    def test_event_is_attributed_to_the_acting_user_and_tenant(self):
        set_tenant_actor(self.user_a)
        entry = log_event(
            'update', category='settings', description='Changed the company name',
        )
        self.assertIsNotNone(entry)
        self.assertEqual(entry.actor, self.user_a)
        self.assertEqual(entry.business, self.business_a)
        self.assertEqual(entry.actor_name, 'alpha_admin')

    def test_platform_admin_events_stay_platform_wide(self):
        platform = self.make_user('platform_admin', self.business_a, platform=True)
        set_tenant_actor(platform)
        entry = log_event('create', category='platform', description='Registered a business')
        self.assertIsNone(entry.business)

    def test_sensitive_values_are_redacted(self):
        clean = sanitize_changes({
            'password': 'hunter2',
            'api_key': 'abc',
            'name': 'Visible',
        })
        self.assertEqual(clean['password'], '[redacted]')
        self.assertEqual(clean['api_key'], '[redacted]')
        self.assertEqual(clean['name'], 'Visible')

    def test_long_values_are_truncated(self):
        clean = sanitize_changes({'note': 'x' * 5000})
        self.assertEqual(len(clean['note']), 300)

    def test_entries_cannot_be_updated(self):
        entry = log_event('create', description='Original')
        entry.description = 'Tampered'
        with self.assertRaises(ValidationError):
            entry.save()

    def test_entries_cannot_be_deleted(self):
        entry = log_event('create', description='Original')
        with self.assertRaises(ValidationError):
            entry.delete()
        with self.assertRaises(ValidationError):
            AuditLog.objects.filter(pk=entry.pk).delete()


class AuditSignalTests(AuditTestBase):
    """Automatic capture of record changes."""

    def test_creating_a_record_is_recorded(self):
        set_tenant_actor(self.user_a)
        product = Product.objects.create(
            name='Alpha Widget', sku='ALPHA-1',
            category=self.category, business=self.business_a,
        )
        entry = AuditLog.objects.filter(
            model_name='product', object_id=str(product.pk),
            action='create',
        ).first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.actor, self.user_a)
        self.assertEqual(entry.business, self.business_a)
        self.assertEqual(entry.category, 'product')

    def test_updating_a_record_stores_the_previous_values(self):
        set_tenant_actor(self.user_a)
        product = Product.objects.create(
            name='Alpha Widget', sku='ALPHA-1',
            category=self.category, business=self.business_a,
        )
        product.name = 'Alpha Widget Renamed'
        product.save()

        entry = AuditLog.objects.filter(
            model_name='product', object_id=str(product.pk), action='update',
        ).first()
        self.assertIsNotNone(entry, 'the update was not audited')
        self.assertIn('name', entry.changes)
        self.assertEqual(entry.changes['name']['from'], 'Alpha Widget')
        self.assertEqual(entry.changes['name']['to'], 'Alpha Widget Renamed')

    def test_a_save_without_changes_is_not_recorded(self):
        set_tenant_actor(self.user_a)
        product = Product.objects.create(
            name='Alpha Widget', sku='ALPHA-1',
            category=self.category, business=self.business_a,
        )
        before = AuditLog.objects.count()
        product.save()
        self.assertEqual(AuditLog.objects.count(), before)

    def test_an_untouched_image_is_not_reported_as_a_change(self):
        """A file field holds a path in the database but a wrapper in memory."""
        set_tenant_actor(self.user_a)
        product = Product.objects.create(
            name='Alpha Widget', sku='ALPHA-1',
            category=self.category, business=self.business_a,
        )
        product.save()
        entry = AuditLog.objects.filter(
            model_name='product', object_id=str(product.pk), action='update',
        ).first()
        self.assertIsNone(entry, 'an unchanged image was reported as a change')

    def test_deleting_a_record_is_recorded(self):
        set_tenant_actor(self.user_a)
        product = Product.objects.create(
            name='Alpha Widget', sku='ALPHA-1',
            category=self.category, business=self.business_a,
        )
        pk = product.pk
        product.delete()
        entry = AuditLog.objects.filter(
            model_name='product', object_id=str(pk), action='delete',
        ).first()
        self.assertIsNotNone(entry)

    def test_authentication_events_are_recorded(self):
        self.client.login(username='alpha_admin', password='pw12345678')
        self.client.post(reverse('logout'))

        actions = list(AuditLog.objects.values_list('action', flat=True))
        self.assertIn('login', actions)
        self.assertIn('logout', actions)

    def test_failed_sign_in_is_recorded(self):
        self.client.post(
            reverse('login_page'),
            {'username': 'alpha_admin', 'password': 'wrong-password'},
        )
        entry = AuditLog.objects.filter(action='login_failed').first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.outcome, AuditLog.Outcome.FAILURE)


class AuditTenantScopingTests(AuditTestBase):
    """The trail never leaks across businesses."""

    def test_business_user_only_sees_own_entries(self):
        set_tenant_actor(self.user_a)
        log_event('update', description='Alpha private event')
        set_tenant_actor(self.user_b)
        log_event('update', description='Beta private event')
        clear_tenant_actor()

        self.client.login(username='alpha_admin', password='pw12345678')
        response = self.client.get(reverse('audit_log_page'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alpha private event')
        self.assertNotContains(response, 'Beta private event')

    def test_platform_admin_sees_every_entry(self):
        set_tenant_actor(self.user_a)
        log_event('update', description='Alpha private event')
        set_tenant_actor(self.user_b)
        log_event('update', description='Beta private event')
        clear_tenant_actor()

        platform = self.make_user('platform_admin', self.business_a, platform=True)
        self.client.login(username='platform_admin', password='pw12345678')
        response = self.client.get(reverse('audit_log_page'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alpha private event')
        self.assertContains(response, 'Beta private event')

    def test_foreign_entry_detail_is_not_found(self):
        set_tenant_actor(self.user_b)
        entry = log_event('update', description='Beta private event')
        clear_tenant_actor()

        self.client.login(username='alpha_admin', password='pw12345678')
        response = self.client.get(
            reverse('audit_log_detail', kwargs={'pk': entry.pk})
        )
        self.assertEqual(response.status_code, 404)


class AuditUiTests(AuditTestBase):
    """The audit page: permissions, filters, pagination and export."""

    def setUp(self):
        super().setUp()
        for i in range(30):
            set_tenant_actor(self.user_a)
            log_event('update', category='settings', description=f'Alpha event {i}')
        set_tenant_actor(self.user_b)
        log_event('update', category='sales', description='Beta event')
        clear_tenant_actor()

    def test_page_renders_with_pagination(self):
        self.client.login(username='alpha_admin', password='pw12345678')
        response = self.client.get(reverse('audit_log_page'))
        self.assertEqual(response.status_code, 200)
        # The sign-in of the reader is part of the trail as well.
        expected = AuditLog.objects.filter(business=self.business_a).count()
        self.assertEqual(response.context['total_logs'], expected)
        self.assertEqual(len(response.context['logs']), 25)
        self.assertTrue(response.context['page_obj'].has_next())

    def test_pagination_covers_every_entry_exactly_once(self):
        """The window may not shift while the pages are being read."""
        self.client.login(username='alpha_admin', password='pw12345678')
        total = AuditLog.objects.filter(business=self.business_a).count()

        seen = []
        page = 1
        while True:
            response = self.client.get(reverse('audit_log_page'), {'page': page})
            seen.extend(entry.pk for entry in response.context['logs'])
            if not response.context['page_obj'].has_next():
                break
            page += 1

        self.assertEqual(len(seen), total)
        self.assertEqual(len(set(seen)), total)

    def test_search_filter_narrows_the_result(self):
        self.client.login(username='alpha_admin', password='pw12345678')
        response = self.client.get(reverse('audit_log_page'), {'q': 'Alpha event 7'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_logs'], 1)

    def test_category_filter_narrows_the_result(self):
        self.client.login(username='alpha_admin', password='pw12345678')
        response = self.client.get(reverse('audit_log_page'), {'category': 'sales'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_logs'], 0)

    def test_export_returns_csv(self):
        self.client.login(username='alpha_admin', password='pw12345678')
        response = self.client.get(reverse('audit_log_export'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response['Content-Type'])
        body = response.content.decode()
        self.assertIn('Timestamp,Actor,Business', body)
        self.assertIn('Alpha event', body)
        self.assertNotIn('Beta event', body)

    def test_export_honours_the_active_filters(self):
        self.client.login(username='alpha_admin', password='pw12345678')
        response = self.client.get(reverse('audit_log_export'), {'category': 'sales'})
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('Timestamp,Actor,Business', body)
        self.assertNotIn('Alpha event', body)

    def test_user_without_permission_gets_404(self):
        user = User.objects.create_user(
            username='clerk', password='pw12345678', email='clerk@example.com',
        )
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.business = self.business_a
        profile.save()
        role = Role.objects.create(
            name='Clerk', business=self.business_a, is_system_role=True,
        )
        role.set_modules([4])
        profile.roles.add(role)

        self.client.login(username='clerk', password='pw12345678')
        response = self.client.get(reverse('audit_log_page'))
        self.assertEqual(response.status_code, 404)

    def test_business_admin_cannot_purge_the_trail(self):
        self.client.login(username='alpha_admin', password='pw12345678')
        before = AuditLog.objects.count()
        response = self.client.post(reverse('audit_log_purge'), {'category': 'settings'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(AuditLog.objects.count(), before)

    def test_platform_admin_can_purge_the_trail(self):
        platform = self.make_user('platform_admin', self.business_a, platform=True)
        self.client.login(username='platform_admin', password='pw12345678')
        response = self.client.post(reverse('audit_log_purge'), {'category': 'settings'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(AuditLog.objects.filter(category='settings').exists())
