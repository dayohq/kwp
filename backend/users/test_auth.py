from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.db import IntegrityError, connection
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .serializers import RegistrationSerializer

User = get_user_model()
PASSWORD = 'Packet5-test-only-password!42'
ORIGIN = 'http://localhost:5173'


@override_settings(ALLOWED_HOSTS=['testserver', 'localhost'],
                   CORS_ALLOWED_ORIGINS=[ORIGIN], CSRF_TRUSTED_ORIGINS=[ORIGIN],
                   SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False)
class AuthenticationTests(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.data = {'email': 'Owner@EXAMPLE.COM', 'password': PASSWORD,
                     'password_confirmation': PASSWORD, 'base_currency': 'USD'}

    def post(self, route, data=None, client=None, origin=ORIGIN):
        client = client or self.client
        token = client.get('/api/auth/csrf/').json()['csrfToken']
        return client.post(f'/api/auth/{route}/', data or {}, format='json',
                           HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN=origin)

    def user(self, **fields):
        return User.objects.create_user('owner@example.com', PASSWORD, base_currency='USD', **fields)

    def login(self, client=None, email='owner@example.com', password=PASSWORD):
        return self.post('login', {'email': email, 'password': password}, client=client)

    def test_registration_normalizes_hashes_and_returns_only_profile(self):
        response = self.post('register', self.data)
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email='owner@example.com')
        self.assertEqual(set(response.json()), {'id', 'email', 'base_currency', 'timezone'})
        self.assertEqual(response.json()['base_currency'], 'USD')
        self.assertEqual(response.json()['timezone'], 'Africa/Lagos')
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 403)
        self.assertNotIn(settings.SESSION_COOKIE_NAME, response.cookies)

    def test_duplicate_email_both_casings_rejected(self):
        self.user()
        for email in ('owner@example.com', 'OWNER@EXAMPLE.COM'):
            response = self.post('register', self.data | {'email': email})
            self.assertEqual(response.status_code, 400)
            self.assertIn('email', response.json())
        self.assertEqual(User.objects.count(), 1)

    def test_registration_race_returns_controlled_error(self):
        serializer = RegistrationSerializer(data=self.data)
        self.assertTrue(serializer.is_valid())
        with patch.object(User.objects, 'create_user', side_effect=IntegrityError):
            from rest_framework.exceptions import ValidationError
            with self.assertRaises(ValidationError) as error:
                serializer.save()
        self.assertIn('email', error.exception.detail)

    def test_invalid_email_currency_and_timezone(self):
        for fields, expected in [({'email': 'bad'}, 'email'),
                                 ({'base_currency': 'usd'}, 'base_currency'),
                                 ({'base_currency': 'USD\n'}, 'base_currency'),
                                 ({'timezone': 'Unknown/Place'}, 'timezone')]:
            with self.subTest(fields=fields):
                response = self.post('register', self.data | fields)
                self.assertEqual(response.status_code, 400)
                self.assertIn(expected, response.json())
        self.assertEqual(User.objects.count(), 0)

    def test_every_required_registration_field(self):
        for field in self.data:
            data = self.data.copy()
            del data[field]
            with self.subTest(field=field):
                response = self.post('register', data)
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())
        self.assertEqual(User.objects.count(), 0)

    def test_empty_currency_never_defaults_to_ngn(self):
        for currency in ('', None):
            self.assertEqual(self.post('register', self.data | {'base_currency': currency}).status_code, 400)
        self.assertFalse(User.objects.exists())

    def test_password_policy_and_confirmation(self):
        for password in ('short', 'password', '123456789012', 'owner@example.com'):
            with self.subTest(password=password):
                response = self.post('register', self.data | {
                    'password': password, 'password_confirmation': password})
                self.assertEqual(response.status_code, 400)
                self.assertIn('password', response.json())
                self.assertNotIn(password, response.json()['password'])
        response = self.post('register', self.data | {'password_confirmation': 'different-test-only'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('password_confirmation', response.json())

    def test_configured_password_validators_called_with_candidate(self):
        with patch('users.serializers.validate_password') as validate:
            self.assertEqual(self.post('register', self.data).status_code, 201)
        self.assertEqual(validate.call_args.kwargs['user'].email, 'owner@example.com')
        self.assertEqual(validate.call_args.args, (PASSWORD,))

    def test_login_normalizes_email_and_establishes_session(self):
        user = self.user()
        response = self.login(email=' OWNER@EXAMPLE.COM ')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/api/auth/me/').json()['id'], user.pk)
        cookie = response.cookies[settings.SESSION_COOKIE_NAME]
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'], 'Lax')
        self.assertEqual(cookie['domain'], '')
        self.assertNotIn('password', response.json())
        self.assertIn('no-store', response['Cache-Control'])

    def test_failed_login_is_generic_for_unknown_wrong_and_inactive(self):
        user = self.user()
        wrong = self.login(password='wrong-test-only')
        unknown = self.login(email='absent@example.com')
        user.is_active = False
        user.save(update_fields=['is_active'])
        inactive = self.login()
        for response in (wrong, unknown, inactive):
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json(), {'detail': ['Invalid email or password.']})
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 403)

    def test_me_denies_anonymous_and_returns_only_current_user(self):
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 403)
        first = self.user()
        second = User.objects.create_user('second@example.com', PASSWORD, base_currency='EUR')
        self.login()
        other = APIClient(enforce_csrf_checks=True)
        self.login(client=other, email=second.email)
        for client, user in ((self.client, first), (other, second)):
            response = client.get(f'/api/auth/me/?id={second.pk}')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {'id': user.pk, 'email': user.email,
                                             'base_currency': user.base_currency, 'timezone': user.timezone})

    def test_deactivated_session_is_denied(self):
        user = self.user()
        self.login()
        user.is_active = False
        user.save(update_fields=['is_active'])
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 403)

    def test_logout_deletes_server_session_and_replayed_cookie_fails(self):
        self.user()
        self.login()
        session_key = self.client.cookies[settings.SESSION_COOKIE_NAME].value
        response = self.post('logout')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'detail': 'Logged out.'})
        self.assertFalse(Session.objects.filter(session_key=session_key).exists())
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 403)
        replay = APIClient()
        replay.cookies[settings.SESSION_COOKIE_NAME] = session_key
        self.assertEqual(replay.get('/api/auth/me/').status_code, 403)

    def test_anonymous_registration_and_login_require_csrf(self):
        for route, data in (('register', self.data), ('login', self.data)):
            self.assertEqual(self.client.post(f'/api/auth/{route}/', data, format='json').status_code, 403)
        self.assertFalse(User.objects.exists())

    def test_wrong_csrf_and_untrusted_origin_rejected(self):
        self.client.get('/api/auth/csrf/')
        response = self.client.post('/api/auth/register/', self.data, format='json',
                                    HTTP_X_CSRFTOKEN='x' * 64, HTTP_ORIGIN=ORIGIN)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.post('register', self.data, origin='https://untrusted.example').status_code, 403)
        self.assertFalse(User.objects.exists())

    def test_authenticated_logout_requires_csrf_and_rejects_get(self):
        self.user()
        self.login()
        self.assertEqual(self.client.post('/api/auth/logout/', {}, format='json').status_code, 403)
        self.assertEqual(self.client.get('/api/auth/logout/').status_code, 405)
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 200)

    def test_login_rotates_session_and_csrf(self):
        self.user()
        session = self.client.session
        session['test_marker'] = True
        session.save()
        old_session = session.session_key
        old_token = self.client.get('/api/auth/csrf/').json()['csrfToken']
        self.login()
        self.assertNotEqual(self.client.cookies[settings.SESSION_COOKIE_NAME].value, old_session)
        self.assertFalse(Session.objects.filter(session_key=old_session).exists())
        response = self.client.post('/api/auth/logout/', {}, format='json', HTTP_X_CSRFTOKEN=old_token)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.post('logout').status_code, 200)

    def test_csrf_bootstrap_and_credentialed_cors(self):
        response = self.client.get('/api/auth/csrf/', HTTP_ORIGIN=ORIGIN)
        self.assertIn('csrfToken', response.json())
        self.assertTrue(response.cookies[settings.CSRF_COOKIE_NAME]['httponly'])
        self.assertEqual(response['Access-Control-Allow-Origin'], ORIGIN)
        self.assertEqual(response['Access-Control-Allow-Credentials'], 'true')
        response = self.client.options('/api/auth/login/', HTTP_ORIGIN=ORIGIN,
                                       HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
                                       HTTP_ACCESS_CONTROL_REQUEST_HEADERS='content-type,x-csrftoken')
        self.assertEqual(response.status_code, 200)
        self.assertIn('x-csrftoken', response['Access-Control-Allow-Headers'])
        response = self.client.get('/api/auth/csrf/', HTTP_ORIGIN='https://untrusted.example')
        self.assertNotIn('Access-Control-Allow-Origin', response)

    def test_method_boundaries_and_health_regression(self):
        for route in ('register', 'login'):
            self.assertEqual(self.client.get(f'/api/auth/{route}/').status_code, 405)
        self.user()
        self.login()
        self.assertEqual(self.post('me').status_code, 405)
        self.assertEqual(self.client.get('/api/health/').json(), {'status': 'ok'})
        self.assertEqual(connection.vendor, 'postgresql')

    def test_admin_login_with_custom_email_user(self):
        admin = User.objects.create_superuser('admin@example.com', PASSWORD, base_currency='EUR')
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        client.get('/admin/login/')
        response = client.post('/admin/login/', {'username': admin.email, 'password': PASSWORD,
                               'csrfmiddlewaretoken': client.cookies[settings.CSRF_COOKIE_NAME].value,
                               'next': '/admin/'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(client.get('/admin/').status_code, 200)
