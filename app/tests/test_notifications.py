"""
Notification tests.

Covers the acceptance criteria of the notification phase:

* every event goes through the central service, which respects the switch the
  user left for that kind of event;
* a sale tells the sales team, but never the person who made the sale;
* stock that falls below its reorder level is reported once, not on every
  save;
* a role change and a business registration reach the right people;
* the notification centre filters, paginates and marks as read.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from app.models.human_resource import Role, UserProfile
from app.models.notification import Notification
from app.models.preferences import UserPreference
from app.models.products import Inventory, Product, StoreLocation
from app.models.tenancy import Business
from app.models.transactions import Sales
from app.services import notification_service as notify_service

User = get_user_model()

ALL_MODULES = list(range(1, 17))


class NotificationTestBase(TestCase):
    def setUp(self):
        self.business = Business.objects.create(name='Alpha Traders')
        self.salesperson = self.make_user('alpha_sales', modules=[1, 4])
        self.stockkeeper = self.make_user('alpha_stock', modules=[1, 2, 3])
        self.platform_admin = self.make_user('platform', platform=True)
        # Giving a user a role is itself an event, so start from a clean slate.
        Notification.objects.all().delete()

    def make_user(self, username, modules=ALL_MODULES, platform=False):
        user = User.objects.create_user(
            username=username, password='pw12345678', email=f'{username}@example.com',
        )
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.business = None if platform else self.business
        profile.is_platform_admin = platform
        profile.save()
        if not platform:
            role = Role.objects.create(
                name=f'{username} role', business=self.business, is_system_role=True,
            )
            role.set_modules(modules)
            profile.roles.add(role)
            profile.refresh_from_db()
        return user

    def make_store(self):
        return StoreLocation.objects.create(
            business=self.business, name='Main Store',
        )


class NotificationServiceTests(NotificationTestBase):
    def test_a_user_who_wants_the_event_is_notified(self):
        notification = notify_service.notify(
            self.salesperson, notify_service.EVENT_SALES, 'Title', 'Message',
        )

        self.assertIsNotNone(notification)
        self.assertEqual(notification.user, self.salesperson)
        self.assertEqual(Notification.objects.count(), 1)

    def test_a_user_who_switched_the_event_off_is_not_notified(self):
        preference = UserPreference.for_user(self.salesperson)
        preference.notify_sales = False
        preference.save()

        notification = notify_service.notify(
            self.salesperson, notify_service.EVENT_SALES, 'Title', 'Message',
        )

        self.assertIsNone(notification)
        self.assertEqual(Notification.objects.count(), 0)

    def test_only_the_recipients_of_the_event_are_notified(self):
        notify_service.notify(
            self.salesperson, notify_service.EVENT_SALES, 'Title', 'Message',
        )

        self.assertEqual(
            list(Notification.objects.values_list('user__username', flat=True)),
            ['alpha_sales'],
        )

    def test_an_anonymous_user_is_never_notified(self):
        self.assertIsNone(
            notify_service.notify(None, notify_service.EVENT_SALES, 'Title', 'Message'),
        )


class SaleNotificationTests(NotificationTestBase):
    def test_a_sale_notifies_the_sales_team_but_not_its_author(self):
        store = self.make_store()
        colleague = self.make_user('alpha_colleague', modules=[1, 4])

        Sales.objects.create(
            receipt_no='R-1', store=store, status='sale',
            recorded_by=self.salesperson, total_amount=1000,
        )

        recipients = set(Notification.objects.values_list('user__username', flat=True))
        self.assertIn('alpha_colleague', recipients)
        self.assertNotIn('alpha_sales', recipients)

    def test_a_sale_does_not_reach_the_stock_team(self):
        store = self.make_store()

        Sales.objects.create(
            receipt_no='R-2', store=store, status='sale',
            recorded_by=self.salesperson, total_amount=1000,
        )

        recipients = set(Notification.objects.values_list('user__username', flat=True))
        self.assertNotIn('alpha_stock', recipients)


class LowStockNotificationTests(NotificationTestBase):
    def make_inventory(self, quantity, reorder_level=10):
        product = Product.objects.create(name='Brake pad', business=self.business)
        store = self.make_store()
        return Inventory.objects.create(
            product=product, store=store,
            quantity_in_stock=quantity, reorder_level=reorder_level,
        )

    def test_stock_below_the_reorder_level_is_reported(self):
        self.make_inventory(quantity=3)

        recipients = set(Notification.objects.values_list('user__username', flat=True))
        self.assertIn('alpha_stock', recipients)

    def test_stock_that_is_still_low_is_not_reported_again(self):
        inventory = self.make_inventory(quantity=3)
        Notification.objects.all().delete()

        inventory.quantity_in_stock = 2
        inventory.save()

        self.assertEqual(Notification.objects.count(), 0)

    def test_stock_above_the_reorder_level_is_not_reported(self):
        self.make_inventory(quantity=50)

        self.assertEqual(Notification.objects.count(), 0)


class RoleNotificationTests(NotificationTestBase):
    def test_the_user_is_told_about_a_new_role(self):
        role = Role.objects.create(
            name='Cashier', business=self.business, is_system_role=True,
        )
        profile = self.salesperson.profile

        profile.roles.add(role)

        notification = Notification.objects.filter(user=self.salesperson).first()
        self.assertIsNotNone(notification)
        self.assertIn('Cashier', notification.message)

    def test_the_user_is_told_about_a_removed_role(self):
        profile = self.salesperson.profile
        profile.roles.clear()

        notification = Notification.objects.filter(user=self.salesperson).first()
        self.assertIsNotNone(notification)
        self.assertIn('removed', notification.message)


class BusinessNotificationTests(NotificationTestBase):
    def test_the_platform_is_told_about_a_new_business(self):
        Business.objects.create(name='Gamma Supplies')

        recipients = set(Notification.objects.values_list('user__username', flat=True))
        self.assertIn('platform', recipients)

    def test_the_administrators_are_told_when_a_business_is_suspended(self):
        administrator = self.make_user('alpha_admin', modules=[1, 7, 9])
        business = self.business
        business.status = Business.STATUS_SUSPENDED
        business.save()

        notification = Notification.objects.filter(user=administrator).first()
        self.assertIsNotNone(notification)
        self.assertIn('suspended', notification.message)


class NotificationCentreTests(NotificationTestBase):
    def setUp(self):
        super().setUp()
        for index in range(30):
            Notification.objects.create(
                user=self.salesperson,
                title=f'Event {index}',
                message='Something happened',
                is_read=index % 2 == 0,
            )
        self.client.force_login(self.salesperson)

    def test_the_centre_paginates(self):
        response = self.client.get(reverse('notifications_list'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['notifications']), 25)
        self.assertTrue(response.context['page_obj'].has_next())

    def test_the_centre_can_show_the_unread_notifications_only(self):
        response = self.client.get(reverse('notifications_list'), {'unread': '1'})

        self.assertEqual(len(response.context['notifications']), 15)
        self.assertTrue(
            all(not n.is_read for n in response.context['notifications']),
        )

    def test_the_api_reports_the_unread_count(self):
        response = self.client.get(reverse('notifications_api'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['unread_count'], 15)

    def test_a_notification_can_be_marked_as_read(self):
        notification = Notification.objects.filter(
            user=self.salesperson, is_read=False,
        ).first()

        response = self.client.post(
            reverse('notification_mark_read', kwargs={'notification_id': notification.pk}),
        )

        self.assertEqual(response.status_code, 200)
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_all_notifications_can_be_marked_as_read(self):
        response = self.client.post(reverse('notification_mark_all_read'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Notification.objects.filter(user=self.salesperson, is_read=False).count(), 0,
        )

    def test_a_user_cannot_read_the_notifications_of_somebody_else(self):
        other = self.make_user('alpha_other', modules=[1, 4])
        notification = Notification.objects.filter(user=other).first()

        response = self.client.post(
            reverse('notification_mark_read', kwargs={'notification_id': notification.pk}),
        )

        self.assertEqual(response.status_code, 404)
        notification.refresh_from_db()
        self.assertFalse(notification.is_read)

    def test_the_centre_searches_the_notifications(self):
        Notification.objects.filter(user=self.salesperson).delete()
        Notification.objects.create(
            user=self.salesperson, title='Stock ran out', message='Brake pads are gone',
        )
        Notification.objects.create(
            user=self.salesperson, title='A sale', message='Receipt R-1 was recorded',
        )

        response = self.client.get(reverse('notifications_list'), {'q': 'Brake'})

        self.assertEqual(len(response.context['notifications']), 1)
        self.assertEqual(response.context['notifications'][0].title, 'Stock ran out')

    def test_the_api_returns_only_what_arrived_after_the_cursor(self):
        first = Notification.objects.filter(user=self.salesperson).order_by('id').first()
        response = self.client.get(reverse('notifications_api'), {'after_id': first.pk})

        self.assertEqual(response.status_code, 200)
        ids = [n['id'] for n in response.json()['notifications']]
        self.assertTrue(all(notification_id > first.pk for notification_id in ids))
        self.assertEqual(response.json()['unread_count'], 15)


class NotificationPriorityAndDedupeTests(NotificationTestBase):
    """The service knows how urgent an event is and when it is the same event."""

    def test_the_priority_of_an_event_is_stored(self):
        notification = notify_service.notify(
            self.salesperson, notify_service.EVENT_SALES, 'Title', 'Message',
            priority=notify_service.PRIORITY_HIGH,
        )

        self.assertEqual(notification.priority, 'high')

    def test_the_same_event_is_not_delivered_twice(self):
        first = notify_service.notify(
            self.salesperson, notify_service.EVENT_SALES, 'Title', 'Message',
            dedupe_key='sale:1',
        )
        second = notify_service.notify(
            self.salesperson, notify_service.EVENT_SALES, 'Title', 'Message',
            dedupe_key='sale:1',
        )

        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(first.pk, second.pk)

    def test_a_different_event_is_still_delivered(self):
        notify_service.notify(
            self.salesperson, notify_service.EVENT_SALES, 'Title', 'Message',
            dedupe_key='sale:1',
        )
        notify_service.notify(
            self.salesperson, notify_service.EVENT_SALES, 'Title', 'Message',
            dedupe_key='sale:2',
        )

        self.assertEqual(Notification.objects.count(), 2)

    def test_the_same_event_is_delivered_to_two_people(self):
        colleague = self.make_user('alpha_colleague2', modules=[1, 4])
        # Giving a colleague a role is itself an event; start from a clean slate.
        Notification.objects.all().delete()

        notify_service.notify(
            self.salesperson, notify_service.EVENT_SALES, 'Title', 'Message',
            dedupe_key='sale:1',
        )
        notify_service.notify(
            colleague, notify_service.EVENT_SALES, 'Title', 'Message',
            dedupe_key='sale:1',
        )

        self.assertEqual(Notification.objects.count(), 2)
