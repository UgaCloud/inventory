"""Render authenticated pages to static HTML files for visual review.

The dev server keeps the pages behind a login, so a plain headless browser
cannot reach them. This script asks Django itself for the rendered HTML with
an authenticated session, writes the result to ``screenshots/_render/*.html``
and injects a ``<base>`` tag so the static assets are pulled from the running
dev server. Chrome can then screenshot the file without a login.

Usage:
    python tools/render_pages.py
"""
import os
import sys
from pathlib import Path

import django

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings.development')
django.setup()

from django.conf import settings  # noqa: E402
from django.test import Client  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402

settings.DEBUG = False
settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + ['testserver', '127.0.0.1', 'localhost']

OUT_DIR = BASE_DIR / 'screenshots' / '_render'
OUT_DIR.mkdir(parents=True, exist_ok=True)

PAGES = [
    ('index_dashboards', '/'),
    ('settings', '/settings/tab/profile/'),
    ('settings_company', '/settings/company/'),
    ('audit_log', '/audit/'),
    ('platform_dashboard', '/platform/'),
    ('platform_businesses', '/platform/businesses/'),
    ('notifications', '/notifications/'),
    ('users', '/users/'),
    ('roles', '/roles/'),
    ('sales_list', '/sales/'),
    ('products', '/products/'),
    ('customers', '/customers/'),
]


def main():
    User = get_user_model()
    user = (User.objects.filter(username='zz_ui_verify').first()
            or User.objects.filter(is_superuser=True).first()
            or User.objects.order_by('id').first())
    if user is None:
        print('FATAL: no user to log in as')
        return 2

    client = Client()
    client.force_login(user)

    for name, url in PAGES:
        try:
            response = client.get(url, follow=False)
        except Exception as exc:  # noqa: BLE001
            print(f'{name:24s} {url:26s} EXCEPTION {type(exc).__name__}: {exc}')
            continue
        status = response.status_code
        content_type = response.get('Content-Type', '')
        if status == 200 and 'html' in content_type:
            html = response.content.decode('utf-8', 'ignore')
            base = '<base href="http://127.0.0.1:8000/">'
            if '<head>' in html:
                html = html.replace('<head>', '<head>' + base, 1)
            target = OUT_DIR / f'{name}.html'
            target.write_text(html, encoding='utf-8')
            print(f'{name:24s} {url:26s} {status} -> {target.name} ({len(html)} bytes)')
        else:
            print(f'{name:24s} {url:26s} {status} (not captured)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
