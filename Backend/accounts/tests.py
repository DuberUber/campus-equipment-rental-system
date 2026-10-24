from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase
from rest_framework.throttling import SimpleRateThrottle

User = get_user_model()


class UserModelTests(TestCase):
    def test_email_is_unique(self):
        User.objects.create_user('first', email='same@example.com')

        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user('second', email='same@example.com')

    def test_student_number_is_unique_but_optional(self):
        User.objects.create_user('aoife', email='aoife@example.com', student_number='S100')
        # Staff accounts leave it empty; blank values are stored as NULL so they never collide.
        User.objects.create_user('desk', email='desk@example.com', student_number='', is_staff=True)
        User.objects.create_user('desk2', email='desk2@example.com', is_staff=True)

        self.assertIsNone(User.objects.get(username='desk').student_number)
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user('copy', email='copy@example.com', student_number='S100')

    def test_full_name_and_role(self):
        self.assertEqual(User(username='jdoe').full_name, 'jdoe')
        self.assertEqual(User(username='jdoe', first_name='Jane', last_name='Doe').full_name, 'Jane Doe')
        self.assertTrue(User(username='student').is_student)
        self.assertFalse(User(username='desk', is_staff=True).is_student)

    def test_email_lookups_are_indexed(self):
        indexed = {tuple(index.fields) or index.name for index in User._meta.indexes}
        self.assertIn('user_email_ci_idx', indexed)
        self.assertTrue(User._meta.get_field('email').unique)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AuthenticationTests(APITestCase):
    password = 'correct-horse-battery-staple'

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('desk', email='desk@example.com', password=cls.password, is_staff=True)

    def setUp(self):
        cache.clear()

    def login(self, password=None):
        return self.client.post(
            reverse('auth-token'),
            {'username': 'desk', 'password': password or self.password},
            format='json',
        )

    def test_api_requires_authentication(self):
        for name in ['equipment-list', 'reservation-list', 'student-list', 'category-list', 'my-history', 'auth-me']:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_schema_and_docs_are_public(self):
        self.assertEqual(self.client.get(reverse('schema')).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(reverse('swagger-ui')).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(reverse('redoc')).status_code, status.HTTP_200_OK)

    def test_login_returns_a_working_token(self):
        response = self.login()
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {response.data['token']}")
        me = self.client.get(reverse('auth-me'))

        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertEqual((me.data['username'], me.data['role']), ('desk', 'staff'))

    def test_login_ignores_a_stale_token_header(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token not-a-real-token')

        self.assertEqual(self.login().status_code, status.HTTP_200_OK)

    def test_wrong_password_is_rejected(self):
        self.assertEqual(self.login(password='wrong').status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_revokes_the_token(self):
        token = self.login().data['token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')

        self.assertEqual(self.client.post(reverse('auth-logout')).status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Token.objects.filter(key=token).exists())
        self.assertEqual(self.client.get(reverse('auth-me')).status_code, status.HTTP_401_UNAUTHORIZED)

    @mock.patch.dict(SimpleRateThrottle.THROTTLE_RATES, {'login': '2/minute'})
    def test_login_attempts_are_throttled(self):
        codes = [self.login(password='wrong').status_code for _ in range(3)]

        self.assertEqual(codes, [400, 400, 429])


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class RegistrationTests(APITestCase):
    url = reverse('auth-register')

    def setUp(self):
        cache.clear()

    def register(self, **overrides):
        data = {
            'username': 'aoife', 'email': 'aoife@example.com', 'password': 'correct-horse-battery-staple',
            'first_name': 'Aoife', 'last_name': 'Brennan', 'student_number': 's21000101',
            'course': 'BSc Physics', 'year': 3,
            **overrides,
        }
        return self.client.post(self.url, data, format='json')

    def test_register_creates_a_student_and_returns_a_token(self):
        response = self.register()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        user = User.objects.get(username='aoife')
        self.assertTrue(user.check_password('correct-horse-battery-staple'))
        self.assertFalse(user.is_staff)
        self.assertEqual((user.student_number, user.course, user.year), ('S21000101', 'BSc Physics', 3))
        self.assertEqual(response.data['user']['role'], 'student')
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {response.data['token']}")
        self.assertEqual(self.client.get(reverse('auth-me')).data['username'], 'aoife')

    def test_student_details_are_required(self):
        response = self.register(student_number='', course='', year=None)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(set(response.data), {'student_number', 'course', 'year'})

    def test_year_must_be_in_range(self):
        self.assertIn('year', self.register(year=9).data)

    def test_weak_passwords_are_rejected(self):
        response = self.register(password='password')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.data)
        self.assertFalse(User.objects.exists())

    def test_email_and_student_number_must_be_unique_ignoring_case(self):
        User.objects.create_user('existing', email='Aoife@Example.com', student_number='S21000101')

        response = self.register()

        self.assertIn('email', response.data)
        self.assertIn('student_number', response.data)

    def test_staff_flags_cannot_be_set(self):
        self.register(is_staff=True, is_superuser=True)

        self.assertFalse(User.objects.get(username='aoife').is_staff)

    @mock.patch.dict(SimpleRateThrottle.THROTTLE_RATES, {'register': '1/hour'})
    def test_registration_is_throttled(self):
        self.register()

        response = self.register(username='second', email='second@example.com', student_number='S2')

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


class CurrentUserTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            'liam', email='liam@example.com', first_name='Liam', student_number='S22000202', course='BEng', year=2
        )

    def setUp(self):
        cache.clear()
        self.client.force_authenticate(self.user)

    def test_me_describes_the_role(self):
        data = self.client.get(reverse('auth-me')).data

        self.assertEqual(
            (data['is_staff'], data['role'], data['full_name'], data['student_number']),
            (False, 'student', 'Liam', 'S22000202'),
        )

    def test_users_update_their_profile_but_not_their_role_or_student_number(self):
        response = self.client.patch(
            reverse('auth-me'),
            {'course': 'BEng Mechanical', 'last_name': 'Walsh', 'is_staff': True, 'student_number': 'X1'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(
            (self.user.course, self.user.last_name, self.user.is_staff, self.user.student_number),
            ('BEng Mechanical', 'Walsh', False, 'S22000202'),
        )

    def test_email_change_must_stay_unique(self):
        User.objects.create_user('other', email='other@example.com')

        response = self.client.patch(reverse('auth-me'), {'email': 'OTHER@example.com'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
