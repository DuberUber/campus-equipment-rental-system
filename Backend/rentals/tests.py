import os
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.contrib.auth import authenticate, get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.throttling import SimpleRateThrottle

from . import services
from .models import Category, Condition, Equipment, Location, Reservation

User = get_user_model()


def results(response):
    """Return the list payload whether or not the endpoint is paginated."""
    data = response.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


def ids(response):
    return [row['id'] for row in results(response)]


class RentalTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user('desk', email='desk@example.com', is_staff=True)
        cls.aoife = User.objects.create_user(
            'aoife', email='aoife@example.com', first_name='Aoife', last_name='Brennan',
            student_number='S100', course='BSc Physics', year=3,
        )
        cls.liam = User.objects.create_user(
            'liam', email='liam@example.com', first_name='Liam', last_name='Walsh',
            student_number='S200', course='BEng', year=2,
        )
        cls.electronics = Category.objects.create(name='Electronics', slug='electronics', kind=Category.Kind.LAB)
        cls.field = Category.objects.create(name='Field sports', slug='field-sports', kind=Category.Kind.SPORTS)
        cls.lab_desk = Location.objects.create(name='Engineering Desk', building='Engineering')
        cls.sports_desk = Location.objects.create(name='Sports Desk', building='Sports Centre')
        cls.scope = cls.make_item('Oscilloscope', 'OSC-1', cls.electronics, cls.lab_desk, max_loan_days=7)
        cls.meter = cls.make_item('Multimeter', 'MM-1', cls.electronics, cls.lab_desk, max_loan_days=14)
        cls.ball = cls.make_item('Football', 'FB-1', cls.field, cls.sports_desk, max_loan_days=2)
        cls.broken = cls.make_item(
            'Microscope', 'MIC-1', cls.electronics, cls.lab_desk, condition=Condition.NEEDS_REPAIR
        )
        cls.retired = cls.make_item('Old hurley', 'HUR-9', cls.field, cls.sports_desk, is_active=False)

    @staticmethod
    def make_item(name, tag, category, location, **extra):
        return Equipment.objects.create(name=name, asset_tag=tag, category=category, location=location, **extra)

    def setUp(self):
        # Throttle counters live in the cache; start every test with a clean slate.
        cache.clear()
        self.now = timezone.now()
        self.login(self.aoife)

    def login(self, user):
        self.client.force_authenticate(user)

    def at(self, days=0, hours=0):
        return self.now + timedelta(days=days, hours=hours)

    def reserve(self, equipment=None, start=None, due=None, student=None, **extra):
        """Create a reservation directly, bypassing the booking rules (e.g. for history in the past)."""
        return Reservation.objects.create(
            equipment=equipment or self.scope, student=student or self.aoife,
            start_at=start or self.at(days=1), due_at=due or self.at(days=2), **extra,
        )

    def overdue_loan(self, equipment=None, student=None):
        return self.reserve(
            equipment or self.meter, self.at(days=-5), self.at(days=-1), student or self.liam,
            status=Reservation.Status.CHECKED_OUT, checked_out_at=self.at(days=-5),
        )

    def post_reservation(self, equipment=None, start=None, due=None, **extra):
        return self.client.post(reverse('reservation-list'), {
            'equipment': (equipment or self.scope).pk,
            'start_at': (start or self.at(days=1)).isoformat(),
            'due_at': (due or self.at(days=2)).isoformat(),
            **extra,
        }, format='json')


class ReservationModelTests(RentalTestCase):
    def test_due_must_be_after_start(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.reserve(start=self.at(days=2), due=self.at(days=2))

    def test_overdue_and_returned_late_are_annotations(self):
        overdue = self.overdue_loan()
        on_loan = self.reserve(status=Reservation.Status.CHECKED_OUT, start=self.at(days=-1))
        never_collected = self.reserve(self.ball, self.at(days=-3), self.at(days=-2))
        late = self.reserve(
            self.ball, self.at(days=-10), self.at(days=-9), status=Reservation.Status.RETURNED,
            returned_at=self.at(days=-8),
        )
        on_time = self.reserve(
            self.ball, self.at(days=-7), self.at(days=-6), status=Reservation.Status.RETURNED,
            returned_at=self.at(days=-6, hours=-1),
        )

        flags = {r.pk: (r.is_overdue, r.returned_late) for r in Reservation.objects.with_flags()}

        self.assertEqual(flags[overdue.pk], (True, False))
        self.assertEqual(flags[on_loan.pk], (False, False))
        self.assertEqual(flags[never_collected.pk], (False, False))
        self.assertEqual(flags[late.pk], (False, True))
        self.assertEqual(flags[on_time.pk], (False, False))
        self.assertEqual(list(Reservation.objects.overdue()), [overdue])
        self.assertTrue(overdue.compute_overdue() and late.compute_returned_late())
        self.assertFalse('is_overdue' in [field.name for field in Reservation._meta.get_fields()])

    def test_blocking_finds_overlaps_but_not_neighbours_or_finished_reservations(self):
        held = self.reserve(start=self.at(days=1), due=self.at(days=3))
        self.reserve(start=self.at(days=5), due=self.at(days=6), status=Reservation.Status.CANCELLED)
        self.reserve(start=self.at(days=-6), due=self.at(days=-5), status=Reservation.Status.RETURNED)
        blocking = Reservation.objects.filter(equipment=self.scope)

        self.assertEqual(list(blocking.blocking(self.at(days=2), self.at(days=4))), [held])
        self.assertFalse(blocking.blocking(self.at(days=3), self.at(days=4)).exists())  # back to back
        self.assertFalse(blocking.blocking(self.at(days=5), self.at(days=6)).exists())  # cancelled

    def test_an_overdue_item_blocks_every_later_range(self):
        loan = self.overdue_loan()

        self.assertEqual(
            list(Reservation.objects.filter(equipment=self.meter).blocking(self.at(days=30), self.at(days=31))), [loan]
        )

    def test_history_is_protected_from_cascading_deletes(self):
        self.reserve()

        with self.assertRaises(ProtectedError):
            self.scope.delete()
        with self.assertRaises(ProtectedError):
            self.aoife.delete()
        with self.assertRaises(ProtectedError):
            self.electronics.delete()

    def test_reservation_indexes(self):
        indexed = {tuple(index.fields) for index in Reservation._meta.indexes}

        self.assertTrue({('equipment', 'start_at'), ('student', 'start_at'), ('status', 'due_at')} <= indexed)


class BookingRuleTests(RentalTestCase):
    def test_student_reserves_a_free_item(self):
        response = self.post_reservation(notes='Signals lab')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        reservation = Reservation.objects.get(pk=response.data['id'])
        self.assertEqual((reservation.student, reservation.status, reservation.notes), (self.aoife, 'reserved', 'Signals lab'))
        self.assertEqual(
            (response.data['equipment_name'], response.data['location_name'], response.data['is_overdue']),
            ('Oscilloscope', 'Engineering Desk', False),
        )

    def test_overlapping_reservations_are_rejected(self):
        self.reserve(start=self.at(days=1), due=self.at(days=3), student=self.liam)

        for start, due in [(1, 2), (2, 4), (0.5, 5)]:
            with self.subTest(start=start, due=due):
                response = self.post_reservation(start=self.at(days=start), due=self.at(days=due))
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(response.data['equipment'], ['This item is already reserved for part of that time.'])

    def test_back_to_back_and_other_items_are_fine(self):
        self.reserve(start=self.at(days=1), due=self.at(days=3), student=self.liam)

        self.assertEqual(self.post_reservation(start=self.at(days=3), due=self.at(days=4)).status_code, 201)
        self.assertEqual(self.post_reservation(self.meter, self.at(days=1), self.at(days=3)).status_code, 201)

    def test_double_booking_the_same_window(self):
        first = self.post_reservation()
        self.login(self.liam)
        second = self.post_reservation()

        self.assertEqual((first.status_code, second.status_code), (201, 400))
        self.assertEqual(Reservation.objects.filter(equipment=self.scope).count(), 1)

    def test_cancelled_and_returned_reservations_free_the_item(self):
        self.reserve(status=Reservation.Status.CANCELLED)
        self.reserve(status=Reservation.Status.RETURNED, returned_at=self.now)

        self.assertEqual(self.post_reservation().status_code, status.HTTP_201_CREATED)

    def test_the_booking_runs_in_a_transaction_with_the_item_locked(self):
        calls = []

        def spy(equipment_id):
            calls.append((equipment_id, connection.in_atomic_block))
            return Equipment.objects.get(pk=equipment_id)

        with mock.patch.object(services, 'lock_equipment', side_effect=spy):
            self.post_reservation()

        self.assertEqual(calls, [(self.scope.pk, True)])

    def test_bookings_cannot_start_in_the_past(self):
        response = self.post_reservation(start=self.at(hours=-1))

        self.assertEqual(response.data['start_at'], ['Reservations cannot start in the past.'])

    def test_due_must_follow_start(self):
        response = self.post_reservation(start=self.at(days=2), due=self.at(days=1))

        self.assertIn('due_at', response.data)

    def test_loans_are_limited_to_the_items_max_loan_days(self):
        too_long = self.post_reservation(self.ball, self.at(days=1), self.at(days=3, hours=1))
        just_right = self.post_reservation(self.ball, self.at(days=1), self.at(days=3))

        self.assertEqual(too_long.data['due_at'], ['Football can be borrowed for at most 2 days.'])
        self.assertEqual(just_right.status_code, status.HTTP_201_CREATED)

    def test_retired_and_broken_items_cannot_be_reserved(self):
        self.login(self.staff)  # staff can see retired items; the rules still apply to them
        for item, message in [(self.retired, 'retired'), (self.broken, 'repair')]:
            with self.subTest(item=item.name):
                response = self.post_reservation(item, student=self.aoife.pk)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(message, response.data['equipment'][0])

    @override_settings(MAX_ACTIVE_RESERVATIONS=2)
    def test_students_have_a_limit_on_active_reservations(self):
        self.reserve(self.meter, status=Reservation.Status.CHECKED_OUT, start=self.at(days=-1))
        self.reserve(self.ball)
        self.reserve(self.scope, status=Reservation.Status.RETURNED, start=self.at(days=-9), due=self.at(days=-8))

        response = self.post_reservation()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('at most 2 active reservations', response.data['student'][0])

    def test_the_default_limit_is_three(self):
        for item in (self.meter, self.ball, self.scope):
            self.assertEqual(self.post_reservation(item).status_code, status.HTTP_201_CREATED)
        extra = self.make_item('Spare scope', 'OSC-2', self.electronics, self.lab_desk)

        self.assertIn('at most 3', self.post_reservation(extra).data['student'][0])

    def test_students_with_an_overdue_item_cannot_book(self):
        self.overdue_loan(student=self.aoife)

        response = self.post_reservation()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('overdue', response.data['student'][0])

    def test_an_overdue_item_cannot_be_reserved_until_it_comes_back(self):
        self.overdue_loan(self.ball)

        response = self.post_reservation(self.ball, self.at(days=10), self.at(days=11))

        self.assertIn('equipment', response.data)

    def test_students_reserve_only_for_themselves(self):
        response = self.post_reservation(student=self.liam.pk)

        self.assertEqual(response.data['student'], ['You can only reserve equipment for yourself.'])

    def test_staff_reserve_on_behalf_of_a_student(self):
        self.login(self.staff)

        missing = self.post_reservation()
        created = self.post_reservation(student=self.liam.pk)
        for_staff = self.post_reservation(self.meter, student=self.staff.pk)

        self.assertIn('student', missing.data)
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Reservation.objects.get(pk=created.data['id']).student, self.liam)
        self.assertIn('student', for_staff.data)

    def test_services_reject_staff_as_borrowers(self):
        with self.assertRaisesMessage(Exception, 'Only students'):
            services.create_reservation(
                student=self.staff, equipment=self.scope, start_at=self.at(days=1), due_at=self.at(days=2)
            )

    def test_reservations_are_not_edited_or_deleted(self):
        reservation = self.reserve()
        self.login(self.staff)
        url = reverse('reservation-detail', args=[reservation.pk])

        self.assertEqual(self.client.patch(url, {'notes': 'x'}).status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class AvailabilityTests(RentalTestCase):
    def availability(self, item=None, **params):
        return self.client.get(reverse('equipment-availability', args=[(item or self.scope).pk]), params)

    def test_lists_busy_ranges_without_revealing_the_borrower(self):
        first = self.reserve(start=self.at(days=1), due=self.at(days=2), student=self.liam)
        self.reserve(start=self.at(days=3), due=self.at(days=4), status=Reservation.Status.CANCELLED)
        self.reserve(start=self.at(days=40), due=self.at(days=41))  # outside the window

        response = self.availability(**{'from': self.now.isoformat(), 'to': self.at(days=10).isoformat()})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_available'])
        self.assertTrue(response.data['is_reservable'])
        self.assertEqual(len(response.data['busy']), 1)
        busy = response.data['busy'][0]
        self.assertEqual(set(busy), {'start_at', 'end_at', 'status', 'is_overdue'})
        self.assertEqual(busy['end_at'], first.due_at.isoformat().replace('+00:00', 'Z'))

    def test_a_free_item_is_available_and_the_window_defaults_to_four_weeks(self):
        response = self.availability()

        self.assertEqual((response.data['is_available'], response.data['busy']), (True, []))
        self.assertEqual(
            (timezone.datetime.fromisoformat(response.data['to']) - timezone.datetime.fromisoformat(response.data['from'])).days,
            28,
        )

    def test_dates_cover_whole_days(self):
        day = timezone.localdate() + timedelta(days=5)
        self.reserve(start=self.at(days=5), due=self.at(days=5, hours=1))

        response = self.availability(**{'from': day.isoformat(), 'to': day.isoformat()})

        self.assertEqual(len(response.data['busy']), 1)

    def test_an_overdue_item_is_busy_to_the_end_of_the_window(self):
        self.overdue_loan()
        end = self.at(days=10)

        response = self.availability(self.meter, **{'from': self.now.isoformat(), 'to': end.isoformat()})

        busy = response.data['busy'][0]
        self.assertTrue(busy['is_overdue'])
        self.assertEqual(busy['end_at'], end.isoformat().replace('+00:00', 'Z'))

    def test_items_waiting_for_repair_are_never_available(self):
        response = self.availability(self.broken)

        self.assertEqual((response.data['is_reservable'], response.data['is_available']), (False, False))

    def test_bad_windows_are_rejected(self):
        cases = [
            ({'from': 'soon'}, 'from'),
            ({'to': '2026-13-45'}, 'to'),
            ({'from': self.at(days=3).isoformat(), 'to': self.at(days=1).isoformat()}, 'to'),
            ({'from': self.now.isoformat(), 'to': self.at(days=200).isoformat()}, 'to'),
        ]
        for params, field in cases:
            with self.subTest(params=params):
                response = self.availability(**params)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.data)


class EquipmentAPITests(RentalTestCase):
    url = reverse('equipment-list')

    def test_list_shows_details_and_whether_an_item_is_out(self):
        self.reserve(self.ball, start=self.at(days=-1), status=Reservation.Status.CHECKED_OUT)

        rows = {row['asset_tag']: row for row in results(self.client.get(self.url))}

        self.assertTrue(rows['FB-1']['is_checked_out'])
        self.assertFalse(rows['OSC-1']['is_checked_out'])
        self.assertEqual(
            (rows['OSC-1']['kind'], rows['OSC-1']['category_name'], rows['OSC-1']['building']),
            ('lab', 'Electronics', 'Engineering'),
        )

    def test_students_only_see_active_items_and_staff_see_everything(self):
        self.assertNotIn(self.retired.pk, ids(self.client.get(self.url)))
        self.login(self.staff)

        self.assertIn(self.retired.pk, ids(self.client.get(self.url)))
        self.assertEqual(ids(self.client.get(self.url, {'is_active': 'false'})), [self.retired.pk])

    def test_available_from_and_to_list_items_free_for_the_whole_range(self):
        self.reserve(self.scope, self.at(days=2), self.at(days=3))
        self.overdue_loan(self.meter)

        free = ids(self.client.get(self.url, {
            'available_from': self.at(days=1).isoformat(), 'available_to': self.at(days=4).isoformat(),
        }))
        later = ids(self.client.get(self.url, {
            'available_from': self.at(days=5).isoformat(), 'available_to': self.at(days=6).isoformat(),
        }))

        # The broken microscope and retired hurley are never listed as available; the overdue meter neither.
        self.assertEqual(free, [self.ball.pk])
        self.assertEqual(set(later), {self.ball.pk, self.scope.pk})

    def test_available_filter_accepts_dates_and_needs_both_bounds(self):
        day = (timezone.localdate() + timedelta(days=2)).isoformat()
        self.assertEqual(self.client.get(self.url, {'available_from': day, 'available_to': day}).status_code, 200)

        missing = self.client.get(self.url, {'available_from': day})
        invalid = self.client.get(self.url, {'available_from': 'later', 'available_to': day})

        self.assertIn('available_to', missing.data)
        self.assertIn('available_from', invalid.data)

    def test_filters_and_search(self):
        self.assertEqual(ids(self.client.get(self.url, {'kind': 'sports'})), [self.ball.pk])
        self.assertEqual(set(ids(self.client.get(self.url, {'category': self.electronics.pk}))), {self.scope.pk, self.meter.pk, self.broken.pk})
        self.assertEqual(ids(self.client.get(self.url, {'location': self.sports_desk.pk})), [self.ball.pk])
        self.assertEqual(ids(self.client.get(self.url, {'condition': 'needs_repair'})), [self.broken.pk])
        self.assertEqual(ids(self.client.get(self.url, {'search': 'osc-1'})), [self.scope.pk])
        self.assertEqual(ids(self.client.get(self.url, {'search': 'multi'})), [self.meter.pk])

    def test_only_staff_change_the_catalogue(self):
        data = {
            'name': 'Raspberry Pi kit', 'category': self.electronics.pk, 'location': self.lab_desk.pk,
            'asset_tag': ' rpi-1 ', 'max_loan_days': 14,
        }
        self.assertEqual(self.client.post(self.url, data).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.post(reverse('category-list'), {'name': 'X', 'slug': 'x', 'kind': 'lab'}).status_code, 403)

        self.login(self.staff)
        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['asset_tag'], 'RPI-1')
        self.assertIn('asset_tag', self.client.post(self.url, {**data, 'asset_tag': 'rpi-1'}).data)

    def test_deleting_records_with_history_returns_conflict(self):
        self.reserve()
        self.login(self.staff)

        self.assertEqual(self.client.delete(reverse('equipment-detail', args=[self.scope.pk])).status_code, 409)
        self.assertEqual(self.client.delete(reverse('category-detail', args=[self.electronics.pk])).status_code, 409)
        self.assertEqual(self.client.delete(reverse('location-detail', args=[self.lab_desk.pk])).status_code, 409)
        self.assertEqual(self.client.delete(reverse('equipment-detail', args=[self.ball.pk])).status_code, 204)


class CheckoutReturnTests(RentalTestCase):
    def action(self, reservation, name, data=None):
        return self.client.post(reverse(f'reservation-{name}', args=[reservation.pk]), data or {}, format='json')

    def todays_reservation(self, **extra):
        return self.reserve(start=self.at(hours=-1), due=self.at(days=1), **extra)

    def test_staff_check_out_a_reservation_on_its_start_day(self):
        reservation = self.todays_reservation()
        self.login(self.staff)

        response = self.action(reservation, 'checkout')

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual((response.data['status'], response.data['checked_out_by_name']), ('checked_out', 'desk'))
        reservation.refresh_from_db()
        self.assertEqual(reservation.checked_out_by, self.staff)
        self.assertIsNotNone(reservation.checked_out_at)

    def test_students_cannot_check_out_or_return(self):
        reservation = self.todays_reservation()

        self.assertEqual(self.action(reservation, 'checkout').status_code, status.HTTP_403_FORBIDDEN)
        reservation.status = Reservation.Status.CHECKED_OUT
        reservation.save()
        self.assertEqual(self.action(reservation, 'return', {'return_condition': 'good'}).status_code, 403)

    def test_checkout_rules(self):
        self.login(self.staff)
        not_yet = self.reserve(start=self.at(days=2), due=self.at(days=3))
        expired = self.reserve(self.meter, self.at(days=-3), self.at(days=-2))
        cancelled = self.reserve(self.ball, self.at(hours=-1), self.at(days=1), status=Reservation.Status.CANCELLED)

        self.assertIn('start_at', self.action(not_yet, 'checkout').data)
        self.assertIn('due_at', self.action(expired, 'checkout').data)
        self.assertIn('status', self.action(cancelled, 'checkout').data)

    def test_an_item_still_out_cannot_be_checked_out_again(self):
        self.overdue_loan(self.scope)
        waiting = self.todays_reservation(student=self.liam)
        self.login(self.staff)

        response = self.action(waiting, 'checkout')

        self.assertEqual(response.data['equipment'], ['This item has not been returned from its previous loan yet.'])

    def test_returning_records_the_condition_on_the_reservation_and_the_item(self):
        reservation = self.todays_reservation(status=Reservation.Status.CHECKED_OUT)
        self.login(self.staff)

        response = self.action(reservation, 'return', {'return_condition': 'needs_repair', 'notes': 'Probe broken.'})

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(
            (response.data['status'], response.data['return_condition'], response.data['returned_by_name']),
            ('returned', 'needs_repair', 'desk'),
        )
        self.assertFalse(response.data['returned_late'])
        self.scope.refresh_from_db()
        self.assertEqual(self.scope.condition, Condition.NEEDS_REPAIR)
        self.assertIn('Probe broken.', Reservation.objects.get(pk=reservation.pk).notes)

    def test_late_returns_are_flagged(self):
        loan = self.overdue_loan()
        self.login(self.staff)

        response = self.action(loan, 'return', {'return_condition': 'good'})

        self.assertEqual((response.data['is_overdue'], response.data['returned_late']), (False, True))

    def test_return_rules(self):
        reservation = self.todays_reservation()
        self.login(self.staff)

        self.assertIn('return_condition', self.action(reservation, 'return', {'return_condition': 'shiny'}).data)
        self.assertIn('status', self.action(reservation, 'return', {'return_condition': 'good'}).data)

    def test_students_cancel_their_own_reservations_until_checkout(self):
        mine = self.reserve()
        collected = self.reserve(self.meter, self.at(hours=-1), self.at(days=1), status=Reservation.Status.CHECKED_OUT)
        theirs = self.reserve(self.ball, student=self.liam)

        self.assertEqual(self.action(mine, 'cancel').data['status'], 'cancelled')
        self.assertIn('status', self.action(collected, 'cancel').data)
        self.assertEqual(self.action(theirs, 'cancel').status_code, status.HTTP_404_NOT_FOUND)

    def test_staff_cancel_any_reservation(self):
        reservation = self.reserve(student=self.liam)
        self.login(self.staff)

        self.assertEqual(self.action(reservation, 'cancel').data['status'], 'cancelled')


class ReservationListTests(RentalTestCase):
    url = reverse('reservation-list')

    def test_students_see_only_their_own_reservations(self):
        mine = self.reserve()
        theirs = self.reserve(self.ball, student=self.liam)

        self.assertEqual(ids(self.client.get(self.url)), [mine.pk])
        self.assertEqual(self.client.get(reverse('reservation-detail', args=[theirs.pk])).status_code, 404)
        self.login(self.staff)
        self.assertEqual(set(ids(self.client.get(self.url))), {mine.pk, theirs.pk})

    def test_when_filter(self):
        current = self.reserve(self.meter, self.at(days=-1), self.at(days=1), status=Reservation.Status.CHECKED_OUT)
        waiting = self.reserve(self.ball, self.at(hours=-2), self.at(days=1))
        upcoming = self.reserve(self.scope, self.at(days=2), self.at(days=3))
        returned = self.reserve(self.scope, self.at(days=-9), self.at(days=-8), status=Reservation.Status.RETURNED)
        missed = self.reserve(self.scope, self.at(days=-5), self.at(days=-4))

        def when(value):
            return set(ids(self.client.get(self.url, {'when': value})))

        self.assertEqual(when('current'), {current.pk, waiting.pk})
        self.assertEqual(when('upcoming'), {upcoming.pk})
        self.assertEqual(when('past'), {returned.pk, missed.pk})

    def test_filters_by_status_equipment_student_and_kind(self):
        lab = self.reserve(student=self.liam)
        sports = self.reserve(self.ball, status=Reservation.Status.CANCELLED)
        self.login(self.staff)

        self.assertEqual(ids(self.client.get(self.url, {'status': 'cancelled'})), [sports.pk])
        self.assertEqual(ids(self.client.get(self.url, {'equipment': self.scope.pk})), [lab.pk])
        self.assertEqual(ids(self.client.get(self.url, {'student': self.liam.pk})), [lab.pk])
        self.assertEqual(ids(self.client.get(self.url, {'kind': 'sports'})), [sports.pk])

    def test_desk_day_filters(self):
        pickup = self.reserve(start=self.at(hours=1), due=self.at(days=1))
        self.reserve(self.ball, self.at(days=3), self.at(days=4))
        self.login(self.staff)

        response = self.client.get(self.url, {
            'status': 'reserved', 'start_before': self.at(hours=12).isoformat(), 'due_after': self.now.isoformat(),
        })

        self.assertEqual(ids(response), [pickup.pk])


class OverdueTests(RentalTestCase):
    url = reverse('reservation-overdue')

    def test_is_overdue_is_on_every_reservation(self):
        loan = self.overdue_loan(student=self.aoife)
        self.reserve(self.ball)

        rows = {row['id']: row['is_overdue'] for row in results(self.client.get(reverse('reservation-list')))}
        detail = self.client.get(reverse('reservation-detail', args=[loan.pk])).data

        self.assertEqual(sorted(rows.values()), [False, True])
        self.assertTrue(detail['is_overdue'])

    def test_overdue_list_is_staff_only_and_longest_overdue_first(self):
        recent = self.overdue_loan(self.meter)
        oldest = self.reserve(
            self.scope, self.at(days=-9), self.at(days=-7), self.aoife,
            status=Reservation.Status.CHECKED_OUT, checked_out_at=self.at(days=-9),
        )
        self.reserve(self.ball, self.at(days=-1), self.at(days=1), status=Reservation.Status.CHECKED_OUT)

        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_403_FORBIDDEN)
        self.login(self.staff)
        response = self.client.get(self.url)

        self.assertEqual(ids(response), [oldest.pk, recent.pk])
        self.assertEqual(response.data['count'], 2)

    def test_overdue_filter(self):
        loan = self.overdue_loan()
        self.reserve()
        self.login(self.staff)

        self.assertEqual(ids(self.client.get(reverse('reservation-list'), {'overdue': 'true'})), [loan.pk])
        self.assertEqual(len(ids(self.client.get(reverse('reservation-list'), {'overdue': 'false'}))), 1)


class FlagOverdueCommandTests(RentalTestCase):
    def run_command(self, *args):
        out = StringIO()
        call_command('flag_overdue', *args, stdout=out)
        return out.getvalue()

    def test_reports_when_nothing_is_overdue(self):
        self.reserve()

        self.assertIn('No overdue equipment.', self.run_command('--exit-code'))

    def test_lists_overdue_items(self):
        self.overdue_loan()

        output = self.run_command()

        self.assertIn('1 overdue item:', output)
        self.assertIn('MM-1', output)
        self.assertIn('Liam Walsh (S200)', output)
        self.assertIn('return to Engineering Desk', output)

    def test_csv_output(self):
        loan = self.overdue_loan()

        lines = self.run_command('--format', 'csv').strip().splitlines()

        self.assertEqual(lines[0].split(',')[:3], ['reservation', 'asset_tag', 'equipment'])
        self.assertEqual(lines[1].split(',')[:5], [str(loan.pk), 'MM-1', 'Multimeter', 'Liam Walsh', 'S200'])

    def test_exit_code_signals_overdue_items_for_cron(self):
        self.overdue_loan()

        with self.assertRaises(SystemExit) as raised:
            self.run_command('--exit-code')
        self.assertEqual(raised.exception.code, 1)


class StudentAndHistoryTests(RentalTestCase):
    def test_students_see_their_own_history(self):
        mine = self.reserve()
        old = self.reserve(self.ball, self.at(days=-9), self.at(days=-8), status=Reservation.Status.RETURNED)
        self.reserve(self.meter, student=self.liam)

        response = self.client.get(reverse('my-history'))

        self.assertEqual(ids(response), [mine.pk, old.pk])  # newest first
        self.assertEqual(ids(self.client.get(reverse('my-history'), {'when': 'past'})), [old.pk])

    def test_my_history_is_for_students(self):
        self.login(self.staff)

        self.assertEqual(self.client.get(reverse('my-history')).status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_see_any_students_history(self):
        theirs = self.reserve(student=self.liam)
        self.reserve(self.ball)
        url = reverse('student-history', args=[self.liam.pk])

        self.assertEqual(self.client.get(url).status_code, status.HTTP_403_FORBIDDEN)
        self.login(self.staff)
        self.assertEqual(ids(self.client.get(url)), [theirs.pk])
        self.assertEqual(self.client.get(reverse('student-history', args=[self.staff.pk])).status_code, 404)

    def test_student_directory_is_staff_only_with_counts(self):
        self.overdue_loan()
        self.reserve(student=self.liam)
        self.reserve(self.ball, status=Reservation.Status.RETURNED, start=self.at(days=-3), due=self.at(days=-2))

        self.assertEqual(self.client.get(reverse('student-list')).status_code, status.HTTP_403_FORBIDDEN)
        self.login(self.staff)
        rows = {row['username']: row for row in results(self.client.get(reverse('student-list')))}

        self.assertEqual(set(rows), {'aoife', 'liam'})
        self.assertEqual((rows['liam']['active_reservations'], rows['liam']['overdue_reservations']), (2, 1))
        self.assertEqual((rows['aoife']['active_reservations'], rows['aoife']['overdue_reservations']), (0, 0))
        self.assertEqual(ids(self.client.get(reverse('student-list'), {'search': 'S200'})), [self.liam.pk])
        self.assertEqual(self.client.get(reverse('student-detail', args=[self.liam.pk])).data['student_number'], 'S200')


class ScalabilityTests(RentalTestCase):
    def make_reservations(self, count):
        Reservation.objects.bulk_create([
            Reservation(
                equipment=self.scope, student=self.aoife, start_at=self.at(days=-100 + i * 2),
                due_at=self.at(days=-99 + i * 2), status=Reservation.Status.RETURNED,
            )
            for i in range(count)
        ])

    def test_list_endpoints_return_25_rows_per_page(self):
        self.make_reservations(30)

        response = self.client.get(reverse('reservation-list'))

        self.assertEqual((response.data['count'], len(response.data['results'])), (30, 25))
        self.assertIsNotNone(response.data['next'])

    def test_clients_can_request_larger_pages_up_to_a_cap(self):
        self.make_reservations(30)
        self.assertEqual(len(results(self.client.get(reverse('reservation-list'), {'page_size': 30}))), 30)

        self.make_reservations(80)
        self.assertEqual(len(results(self.client.get(reverse('my-history'), {'page_size': 500}))), 100)

    def test_ordering(self):
        self.login(self.staff)

        names = [row['asset_tag'] for row in results(self.client.get(reverse('equipment-list'), {'ordering': '-asset_tag'}))]

        self.assertEqual(names, sorted(names, reverse=True))

    @mock.patch.dict(SimpleRateThrottle.THROTTLE_RATES, {'user': '3/minute'})
    def test_requests_are_throttled_per_user(self):
        codes = [self.client.get(reverse('equipment-list')).status_code for _ in range(4)]

        self.assertEqual(codes, [200, 200, 200, 429])


class QueryCountTests(RentalTestCase):
    def make_rows(self, i):
        item = self.make_item(f'Kit {i}', f'KIT-{i}', self.electronics, self.lab_desk)
        student = User.objects.create_user(f'student{i}', email=f's{i}@example.com', student_number=f'N{i}')
        self.reserve(item, self.at(days=-6), self.at(days=-2), student, status=Reservation.Status.CHECKED_OUT,
                     checked_out_by=self.staff, checked_out_at=self.at(days=-6))
        self.reserve(item, self.at(days=-20), self.at(days=-19), self.liam, status=Reservation.Status.RETURNED,
                     returned_by=self.staff, returned_at=self.at(days=-19), return_condition='good')
        self.reserve(item, self.at(days=3), self.at(days=4), self.liam)

    def count_queries(self, url):
        with CaptureQueriesContext(connection) as context:
            response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return len(context)

    def assert_constant_queries(self, url):
        self.login(self.staff)
        self.make_rows(0)
        few = self.count_queries(url)
        for i in range(1, 6):
            self.make_rows(i)
        many = self.count_queries(url)
        self.assertEqual(few, many, f'{url} issues more queries as rows grow ({few} -> {many})')

    def test_equipment_list(self):
        self.assert_constant_queries(reverse('equipment-list'))

    def test_available_equipment(self):
        self.assert_constant_queries(
            f"{reverse('equipment-list')}?available_from={self.at(days=1).date()}&available_to={self.at(days=5).date()}"
        )

    def test_reservation_list(self):
        self.assert_constant_queries(reverse('reservation-list'))

    def test_overdue_list(self):
        self.assert_constant_queries(reverse('reservation-overdue'))

    def test_student_list(self):
        self.assert_constant_queries(reverse('student-list'))

    def test_student_history(self):
        self.assert_constant_queries(reverse('student-history', args=[self.liam.pk]))

    def test_availability(self):
        self.assert_constant_queries(reverse('equipment-availability', args=[self.scope.pk]))

    def test_my_history_uses_two_queries(self):
        self.make_rows(0)
        self.login(self.liam)

        # One count for pagination, one select with every related row joined.
        self.assertEqual(self.count_queries(reverse('my-history')), 2)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AdminTests(RentalTestCase):
    def test_reservation_admin_shows_the_overdue_flag(self):
        self.overdue_loan()
        admin = User.objects.create_superuser('root', email='root@example.com', password='x')
        self.client.force_login(admin)

        response = self.client.get(reverse('admin:rentals_reservation_changelist'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Overdue')


# The seed command hashes four passwords per run; a fast hasher keeps these tests quick.
@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SeedDemoDataTests(TestCase):
    def seed(self, *args):
        out = StringIO()
        call_command('seed_demo_data', *args, stdout=out)
        return out.getvalue()

    @staticmethod
    def printed_password(output, username):
        line = next(line for line in output.splitlines() if line.strip().startswith(f'{username} '))
        return line.split()[1]

    def test_seeds_accounts_and_sample_records(self):
        output = self.seed()

        for username in ('admin', 'desk', 'aoife', 'liam'):
            with self.subTest(username=username):
                self.assertIsNotNone(authenticate(username=username, password=self.printed_password(output, username)))
        self.assertTrue(User.objects.get(username='admin').is_superuser)
        self.assertTrue(User.objects.get(username='desk').is_staff)
        self.assertEqual(User.objects.get(username='aoife').student_number, 'S21000101')
        self.assertEqual(set(Category.objects.values_list('kind', flat=True)), {'lab', 'sports'})
        self.assertGreaterEqual(Location.objects.count(), 3)
        names = set(Equipment.objects.values_list('name', flat=True))
        for word in ('Oscilloscope', 'multimeter', 'Raspberry Pi', 'microscope', 'DSLR', 'football',
                     'Tennis racket', 'Hurley', 'bibs', 'cones'):
            self.assertTrue(any(word.lower() in name.lower() for name in names), word)

    def test_sample_reservations_cover_every_state(self):
        self.seed()
        reservations = Reservation.objects.with_flags()

        self.assertGreaterEqual(Reservation.objects.overdue().count(), 2)
        self.assertTrue(reservations.filter(status='returned').exists())
        self.assertTrue(reservations.filter(returned_late=True).exists())
        self.assertTrue(reservations.current().filter(is_overdue=False).exists())
        self.assertTrue(reservations.upcoming().exists())
        # aoife can still reserve; liam is blocked by an overdue item.
        self.assertFalse(Reservation.objects.overdue().filter(student__username='aoife').exists())
        self.assertTrue(Reservation.objects.overdue().filter(student__username='liam').exists())

    def test_sample_reservations_never_overlap(self):
        self.seed()

        for reservation in Reservation.objects.active():
            others = Reservation.objects.filter(equipment=reservation.equipment).exclude(pk=reservation.pk)
            self.assertFalse(others.active().filter(
                start_at__lt=reservation.due_at, due_at__gt=reservation.start_at
            ).exists(), reservation)

    def test_rerun_keeps_records_and_rotates_passwords(self):
        first = self.seed()
        counts = (Equipment.objects.count(), Reservation.objects.count(), User.objects.count())

        second = self.seed()

        self.assertIn('skipping sample records', second)
        self.assertEqual((Equipment.objects.count(), Reservation.objects.count(), User.objects.count()), counts)
        self.assertNotEqual(self.printed_password(first, 'aoife'), self.printed_password(second, 'aoife'))

    def test_reset_rebuilds_the_records(self):
        self.seed()
        Reservation.objects.all().delete()
        Equipment.objects.filter(asset_tag='OSC-001').update(name='Renamed')

        self.seed('--reset')

        self.assertEqual(Equipment.objects.get(asset_tag='OSC-001').name, 'Oscilloscope, 100 MHz 2-channel')
        self.assertEqual(Reservation.objects.count(), 12)

    def test_password_can_come_from_the_environment(self):
        with mock.patch.dict(os.environ, {'DEMO_PASSWORD': 'a-fixed-demo-password'}):
            output = self.seed()

        self.assertEqual(self.printed_password(output, 'liam'), 'a-fixed-demo-password')
        self.assertIsNotNone(authenticate(username='desk', password='a-fixed-demo-password'))
