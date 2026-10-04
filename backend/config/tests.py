import os
import runpy
import secrets
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings
from django.urls import reverse


class HealthTests(SimpleTestCase):
    def test_public_health_route_without_database_access(self):
        self.assertEqual(reverse('health'), '/api/health/')
        response = self.client.get('/api/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})
        self.assertEqual(response['Content-Type'], 'application/json')

    def test_health_rejects_writes(self):
        self.assertEqual(self.client.post('/api/health/').status_code, 405)

    @override_settings(CORS_ALLOWED_ORIGINS=['http://localhost:5173', 'http://127.0.0.1:5173'])
    def test_cors_accepts_both_development_origins(self):
        for origin in ('http://localhost:5173', 'http://127.0.0.1:5173'):
            with self.subTest(origin=origin):
                response = self.client.get('/api/health/', HTTP_ORIGIN=origin)
                self.assertEqual(response['Access-Control-Allow-Origin'], origin)

    def test_cors_rejects_unlisted_origin(self):
        response = self.client.get('/api/health/', HTTP_ORIGIN='https://untrusted.example')
        self.assertNotIn('Access-Control-Allow-Origin', response)

    @override_settings(CORS_ALLOWED_ORIGINS=['http://localhost:5173'])
    def test_cors_preflight(self):
        response = self.client.options('/api/health/', HTTP_ORIGIN='http://localhost:5173',
                                       HTTP_ACCESS_CONTROL_REQUEST_METHOD='GET')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Access-Control-Allow-Origin'], 'http://localhost:5173')


class EnvironmentSettingsTests(SimpleTestCase):
    def load_settings(self, values):
        with patch.dict(os.environ, values, clear=True), patch('environ.Env.read_env'):
            return runpy.run_path(str(Path(__file__).with_name('settings.py')))

    def test_required_secret_is_not_invented(self):
        for values in ({}, {'DJANGO_SECRET_KEY': ''},
                       {'DJANGO_SECRET_KEY': 'replace-with-a-generated-local-secret'}):
            with self.subTest(values=values), self.assertRaises(ImproperlyConfigured):
                self.load_settings(values)

    def test_environment_drives_development_settings(self):
        secret = secrets.token_urlsafe(64)
        config = self.load_settings({
            'DJANGO_SECRET_KEY': secret, 'DJANGO_DEBUG': 'True',
            'DJANGO_ALLOWED_HOSTS': 'localhost,127.0.0.1',
            'FRONTEND_URL': 'http://localhost:5173/',
        })
        self.assertEqual(config['SECRET_KEY'], secret)
        self.assertTrue(config['DEBUG'])
        self.assertEqual(config['ALLOWED_HOSTS'], ['localhost', '127.0.0.1'])
        self.assertEqual(set(config['CORS_ALLOWED_ORIGINS']),
                         {'http://localhost:5173', 'http://127.0.0.1:5173'})
        self.assertFalse(config['CORS_ALLOW_ALL_ORIGINS'])

    def test_debug_false_does_not_add_development_origins(self):
        config = self.load_settings({'DJANGO_SECRET_KEY': secrets.token_urlsafe(64),
                                    'DJANGO_DEBUG': 'False',
                                    'FRONTEND_URL': 'https://frontend.example'})
        self.assertFalse(config['DEBUG'])
        self.assertEqual(config['CORS_ALLOWED_ORIGINS'], ['https://frontend.example'])
        self.assertEqual(config['ALLOWED_HOSTS'], [])

    def test_default_settings_are_closed(self):
        config = self.load_settings({'DJANGO_SECRET_KEY': secrets.token_urlsafe(64)})
        self.assertFalse(config['DEBUG'])
        self.assertEqual(config['CORS_ALLOWED_ORIGINS'], [])
