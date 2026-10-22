"""
Settings workspace tests.

The settings workspace is one page with ten tabs. The tests below cover the
acceptance criteria of that phase:

* the workspace opens on the first tab the user is allowed to see;
* a tab the user has no module for is a 404, not a hidden link only;
* the personal tabs (notifications, security, appearance) are open to every
  signed in user;
* the appearance, notification and password forms store what was submitted.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from app.models.human_resource import Role, UserProfile
from app.models.preferences import UserPreference
from app.models.tenancy import Business

User = get_user_model()

ALL_MODULES = list(range(1, 17))
SALES_MODULES = [1, 4]


class SettingsWorkspaceTestBase(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name='Alpha Traders')

    def make_user(self, username, modules=ALL_MODULES, password='pw12345678'):
        user = User.objects.create_user(
            username=username, password=password, email=f'{username}@example.com',
        )
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.business = self.business
        profile.save()
        role = Role.objects.create(
            name=f'{username} role', business=self.business, is_system_role=True,
        )
        role.set_modules(modules)
        profile.roles.add(role)
        profile.refresh_from_db()
        return user


class WorkspaceAccessTests(SettingsWorkspaceTestBase):
    def test_workspace_opens_on_the_first_permitted_tab(self):
        user = self.make_user('clerk', modules=SALES_MODULES)
        self.client.force_login(user)

        response = self.client.get(reverse('settings_page'))

        # A sales clerk may open the commerce tab and the personal tabs, but
        # not the administrative ones, so the workspace lands on commerce.
        self.assertRedirects(response, reverse('settings_tab', kwargs={'slug': 'commerce'}))

    def test_tab_without_the_module_is_not_found(self):
        user = self.make_user('clerk', modules=SALES_MODULES)
        self.client.force_login(user)

        response = self.client.get(reverse('settings_tab', kwargs={'slug': 'profile'}))

        self.assertEqual(response.status_code, 404)

    def test_administrator_may_open_every_tab(self):
        user = self.make_user('admin')
        self.client.force_login(user)

        for slug in ('profile', 'structure', 'users', 'inventory', 'commerce',
                     'notifications', 'security', 'audit', 'appearance', 'data'):
            with self.subTest(tab=slug):
                response = self.client.get(reverse('settings_tab', kwargs={'slug': slug}))
                self.assertEqual(response.status_code, 200)

    def test_personal_tabs_are_open_to_everybody(self):
        user = self.make_user('clerk', modules=SALES_MODULES)
        self.client.force_login(user)

        for slug in ('notifications', 'security', 'appearance'):
            with self.subTest(tab=slug):
                response = self.client.get(reverse('settings_tab', kwargs={'slug': slug}))
                self.assertEqual(response.status_code, 200)

    def test_the_tab_bar_only_shows_permitted_tabs(self):
        user = self.make_user('clerk', modules=SALES_MODULES)
        self.client.force_login(user)

        response = self.client.get(reverse('settings_tab', kwargs={'slug': 'appearance'}))

        slugs = [tab['slug'] for tab in response.context['tabs']]
        self.assertIn('appearance', slugs)
        self.assertNotIn('profile', slugs)
        self.assertNotIn('audit', slugs)

    def test_anonymous_users_are_sent_to_the_login_page(self):
        response = self.client.get(reverse('settings_page'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)


class PreferenceFormTests(SettingsWorkspaceTestBase):
    def test_appearance_preferences_are_stored(self):
        user = self.make_user('admin')
        self.client.force_login(user)

        response = self.client.post(
            reverse('settings_tab', kwargs={'slug': 'appearance'}),
            {'theme': 'dark', 'density': 'compact', 'sidebar_collapsed': 'on'},
        )

        self.assertRedirects(
            response, reverse('settings_tab', kwargs={'slug': 'appearance'}), target_status_code=200,
        )
        preference = UserPreference.for_user(user)
        self.assertEqual(preference.theme, 'dark')
        self.assertEqual(preference.density, 'compact')
        self.assertTrue(preference.sidebar_collapsed)

    def test_notification_preferences_are_stored(self):
        user = self.make_user('admin')
        self.client.force_login(user)

        response = self.client.post(
            reverse('settings_tab', kwargs={'slug': 'notifications'}),
            {'notify_sales': 'on', 'notify_low_stock': 'on'},
        )

        self.assertRedirects(
            response, reverse('settings_tab', kwargs={'slug': 'notifications'}), target_status_code=200,
        )
        preference = UserPreference.for_user(user)
        self.assertTrue(preference.notify_sales)
        self.assertFalse(preference.notify_purchasing)
        self.assertFalse(preference.notify_roles)

    def test_the_password_can_be_changed(self):
        user = self.make_user('admin')
        self.client.force_login(user)

        response = self.client.post(
            reverse('settings_tab', kwargs={'slug': 'security'}),
            {
                'old_password': 'pw12345678',
                'new_password1': 'brandnewpass99',
                'new_password2': 'brandnewpass99',
            },
        )

        self.assertRedirects(
            response, reverse('settings_tab', kwargs={'slug': 'security'}), target_status_code=200,
        )
        user.refresh_from_db()
        self.assertTrue(user.check_password('brandnewpass99'))

    def test_a_wrong_password_does_not_change_it(self):
        user = self.make_user('admin')
        self.client.force_login(user)

        self.client.post(
            reverse('settings_tab', kwargs={'slug': 'security'}),
            {
                'old_password': 'wrongpassword',
                'new_password1': 'brandnewpass99',
                'new_password2': 'brandnewpass99',
            },
        )

        user.refresh_from_db()
        self.assertTrue(user.check_password('pw12345678'))


class CompanyProfileTests(SettingsWorkspaceTestBase):
    def test_the_company_profile_is_edited_from_the_workspace(self):
        user = self.make_user('admin')
        self.client.force_login(user)

        response = self.client.get(reverse('settings_tab', kwargs={'slug': 'profile'}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'orgSettingsForm')

        response = self.client.post(
            reverse('update_settings_page'),
            {
                'organization_name': 'Alpha Traders Ltd',
                'app_name': 'Alpha',
                'country': 'Uganda',
                'city': 'Kampala',
                'currency': 'UGX',
            },
        )

        self.assertEqual(response.status_code, 302)
        from app.models.organization import OrganizationSetting
        profile = OrganizationSetting.load_for(self.business)
        self.assertEqual(profile.organization_name, 'Alpha Traders Ltd')
