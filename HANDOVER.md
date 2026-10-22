# Multi-Tenant Platform Transformation — Handover Report

**Project:** Inventory Platform (`C:\Users\x\Desktop\inventory`)
**Branch:** `feature/multi-tenant-platform` (branched off `Automotive_filters`; not merged into `main`)
**Report date:** 2026-10-22 (session 3)
**Status:** Phases 1–8 complete and verified.

---

## 1. What was delivered

| Phase | Scope | State |
|---|---|---|
| 1 | Audit & consolidation of the existing code base | ✅ |
| 2 | Tenant administration & access control (`Business` model, tenant managers, platform area, per-business roles) | ✅ |
| 3 | Centralized settings workspace & generic append-only audit trail | ✅ (verified in session 3) |
| 4 | Notification service, event coverage, notification center | ✅ (verified in session 3) |
| 5 | Public landing page, two-column sign-in, modernized profile | ✅ (verified in session 3) |
| 6 | Compact lists, server-side search/filter/pagination, slide-up detail panels | ✅ (verified in session 3) |
| 7 | Permission-aware dashboard tabs, real operational metrics, animation tokens | ✅ |
| 8 | Verification & handover | ✅ (this report) |

Phases 3–6 were implemented in earlier sessions but their boxes were never ticked. Session 3
verified them item by item against the code instead of redoing them — the details are in
§4 below.

---

## 2. Architecture at a glance

### 2.1 The tenant

`app/models/tenancy.py` holds the `Business` model (name, slug, status, contact details,
`created_by`). Every tenant-owned row carries a `business` FK, either directly
(`Product`, `StoreLocation`, `Customer`, `Supplier`, `Role`, `BankAccount`, `AuditLog`,
`UserProfile`, `Branch`) or through a related row (`Sales → store → business`,
`Payment → customer → business`, `Inventory → store → business`, …).

### 2.2 How scoping is enforced

Instead of remembering to scope every queryset by hand, tenant-owned models use
`app/managers.py::TenantManager`. The acting user is published for the duration of a
request by `app/middleware.py::TenantMiddleware` through a thread-local
(`asgiref.local.Local`, so it follows async workers), and the manager filters every
queryset of that request:

* platform Super Administrators (`is_superuser` **or** `profile.is_platform_admin`) see everything;
* business users only see rows that belong to their own business;
* rows whose tenant link is optional (a `Payment` without a customer) stay visible to
  every business instead of disappearing for everyone;
* outside a request (management commands, imports) nothing is scoped, so maintenance
  code keeps working unchanged.

`TENANT_PATHS` in `app/managers.py` is the single place that says how a model reaches its
tenant. `business_scope(user, queryset, field)` is the explicit helper for call sites
that need to scope a queryset by hand.

### 2.3 The platform area

`/platform/` (`app/views/platform_views.py`) manages the platform itself: register a
business, provision its first Business Administrator, suspend/activate a business, and
platform-wide statistics. It is guarded by `require_platform_admin`, which answers **404**
(not 403) to business users, so the area is indistinguishable from a missing page.
Business administrators are *not* platform staff: `user_is_platform_admin()` is the only
thing that opens this area.

### 2.4 Roles

`Role` is unique **per business** (migration 0098). Django groups — which are global —
are renamed `<tenant-slug>:<role>` so permissions cannot leak between tenants. A business
administrator can neither create a superuser role nor edit a platform role, and cannot
assign a role to a user of another business.

### 2.5 Audit trail

`app/models/audit.py` + `app/services/audit_service.py`. The model refuses updates and
deletes, so the trail is append-only for ordinary users; only a platform administrator
can purge it (deliberate, POST-only, and it records the purge itself).

Two complementary sources feed it:

* `app/signals/audit_signals.py` — authentication events from Django's own auth signals
  (sign-in, sign-out, failed sign-in) plus a generic `pre_save`/`post_save`/`post_delete`
  trio for 21 audited models, with a real before/after diff;
* explicit `audit_service.log_event(...)` calls in the views that need extra context
  (company-profile changes, sale cancellation, report exports, audit export/purge).

`app/views/audit_views.py` renders the trail with search, filters and pagination. It is
readable by platform administrators, and inside a business by the holders of the
**Settings (9)** or **Role Management (15)** module. The list is tenant scoped: a
business administrator only sees the events of their own business.

### 2.6 Settings workspace

`/settings/` (`app/views/settings_views.py`) is one page with ten tabs: business profile,
structure, users & roles, inventory, sales & purchasing, notifications, security &
sessions, audit, appearance, data management. Three tabs are personal (notifications,
security, appearance) and open to everybody; the others are module-gated. Opening a tab
the user may not see is a **404**. The workspace never duplicates an existing screen —
tabs without a form of their own show the record counts of the business and link to the
pages that do the work.

The company profile itself is per business: `OrganizationSetting` keeps one platform-wide
row (id 1) plus one row per business, and `OrganizationSetting.load_for(business)` copies
the platform values the first time a business asks for its profile.

### 2.7 Notifications

`app/services/notification_service.py` is the only place that raises a notification. It
respects the personal switch of every recipient (`UserPreference`), never notifies the
person who caused the event, and dedupes repeated events inside a 24 h window.

`app/signals/notification_signals.py` covers the events: sale recorded, purchase order
raised, stock below the reorder level, transfer request raised / approved / rejected /
cancelled, roles granted or revoked, business registered or suspended.

Recipients are selected by module (`notify_module`) or by role
(`notify_admins`), always inside one business. The bell polls `notifications_api` with an
`after_id` cursor, so a poll that finds nothing new is cheap.

### 2.8 Dashboards

`app/utils/dashboard_assignment.py` derives the dashboard tabs from the user's effective
modules — no name is hard-coded, and a business user never receives the admin dashboard.
`app/selectors/dashboard_selectors.py` computes every headline number from the tenant's
own rows. The old fixed "+22% / -35%" badges were replaced by
`includes/app_change_badge.html`, which renders the real month-over-month change and says
"No baseline" when there is nothing to compare against. Quick actions
(`app/utils/module_mapping.py::get_quick_actions`) only offer shortcuts whose module the
signed-in user actually holds.

---

## 3. Data safety — the migration story

### 3.1 Migrations added (0093 → 0102)

| Migration | Content |
|---|---|
| 0093 | `PerfumeSaleLine`, `PerfumeSaleComponent` |
| 0094 | `Product.image` |
| 0095 | `UserProfile.is_platform_admin`, `UserProfile.business`, `Business` |
| 0096 | **Data migration**: provision "Default Business" and adopt every pre-existing row |
| 0097 | `BankAccount.business` |
| 0098 | `Role.name` unique per business |
| 0099 | `AuditLog` |
| 0100 | `UserPreference` |
| 0101 | `OrganizationSetting` field changes |
| 0102 | `Notification.priority` + dedupe key |

Every one of them is **additive**: a nullable column, a new table, or a data migration
that only writes values. Nothing drops or rewrites a business record.

### 3.2 The rehearsal (`tools/migration_rehearsal.py`)

The real database is never touched. The script copies `core/db.sqlite3` to a temporary
directory, points Django at the copy, fingerprints the business data (row counts of 20
protected tables plus six business totals), rolls the migrations back to 0092, migrates
forward again, and compares the fingerprints.

**Result (2026-10-22):** rollback and forward both succeeded, and every protected table
and business total was identical afterwards — `app_sales` 47 rows / UGX 18,456,000,
`app_salesitem` 114, `app_product` 30, `app_customer` 8, `app_inventory` 56 rows / 3,050
units, `auth_user` 11, `app_organizationsetting` 2, and so on. Exit code 0.

The four tables the migrations *create* (`app_auditlog`, `app_userpreference`,
`app_perfumesaleline`, `app_perfumesalecomponent`) are checked for existence only:
rolling a `CreateModel` back drops the table with its rows, which is what Django does
everywhere. This is the one thing a rollback would lose, and it is inherent to Django's
migration semantics, not to this project.

### 3.3 The data migration is reversible on purpose

`0096_adopt_existing_data_to_default_business.py` has an `unadopt` counterpart that
detaches the rows again instead of deleting them, and that detaches the
`OrganizationSetting` row *before* removing the tenant — otherwise the cascade would
take the company profile with it.

---

## 4. Verification evidence (session 3)

| Check | Command | Result |
|---|---|---|
| Test suite | `manage.py test app.tests` | **193 tests, OK** (502 s) |
| Page smoke | `manage.py shell -c "exec(open('smoke_test.py'))"` | **200 URLs OK, 0 failures** |
| Math invariants | `manage.py shell -c "exec(open('verify_math.py'))"` | **0 issues**; inventory == batch sums for all 56 rows |
| Migration rehearsal | `python tools/migration_rehearsal.py` | **exit 0**, no data change |
| Django system check | `manage.py check` | 1 warning (`debug_toolbar.W001`, development-only) |
| Migration state | `manage.py showmigrations app` | 111 applied, **0 pending** |
| Visual review | `tools/render_pages.py` + headless Chrome | Admin dashboard, settings workspace, audit trail, platform overview, notification center all render correctly |

### 4.1 Test suite composition (193 tests)

| File | Tests | Covers |
|---|---|---|
| `app/tests/test_tenancy.py` | 29 | query scoping, cross-tenant URLs, per-business roles, platform administration |
| `app/tests/test_audit.py` | 34 | audit model, service, signals, UI, append-only behaviour |
| `app/tests/test_notifications.py` | 27 | notification model, service, signals, centre, preferences |
| `app/tests/test_dashboard_metrics.py` | 37 | dashboard selectors, change badges, quick actions, tab assignment |
| `app/tests/test_perfume_sales.py` | 27 | perfume sale lines and components |
| `app/tests/test_settings_workspace.py` | 6 | settings workspace tabs and forms |
| `app/tests/test_permissions.py` | **33 (new in session 3)** | effective modules, menu filtering, settings tab gating, audit access, quick actions, platform area |

### 4.2 Phase-by-phase verification of the earlier sessions

| Item | Where it lives | Verdict |
|---|---|---|
| 3.1 AuditLog model + service, append-only | `app/models/audit.py`, `app/services/audit_service.py` | ✅ model raises on update/delete |
| 3.2 Event coverage | `app/signals/audit_signals.py` (21 models + auth) + 6 explicit `log_event` calls in views | ✅ |
| 3.3 Audit UI, business scoped | `app/views/audit_views.py`, `templates/audit/` | ✅ |
| 3.4 Ten-tab settings workspace | `app/views/settings_views.py` | ✅ permission-aware, no duplicated screens |
| 4.1 Central event service | `app/services/notification_service.py` + `app/signals/notification_signals.py` | ✅ (see §6 for the naming deviation) |
| 4.2 Event coverage | `app/signals/notification_signals.py` | ✅ sale, purchase, low stock, transfer lifecycle, role change, business status |
| 4.3 Polling with cursor | `notifications_api?after_id=` | ✅ |
| 4.4 Unread widget, panel, history page | `templates/notifications/notification_center.html`, `notification_views.py` | ✅ |
| 4.5 Recipient selection | `notify_module`, `notify_admins`, `notify_platform_admins` | ✅ tenant scoped |
| 5.1 Public landing page | `app/templates/public/landing.html`, `/landing/` | ✅ no private data, honest CTAs |
| 5.2 Two-column sign-in | `app/templates/registration/login.html` | ✅ auth logic unchanged |
| 5.3 Modernized profile | `app/templates/users/profile.html` | ✅ personal info, password, security, preferences, sign-ins |
| 6.1 Compact lists + empty states | `templates/includes/app_list.html` | ✅ 7 list pages converted |
| 6.2 Search, filters, pagination | `app/utils/list_helpers.py` | ✅ server-side, query string preserved |
| 6.3 Slide-up detail panels | `.app-panel` sheet in `app_list.html` | ✅ focus-managed, navbar visible |
| 6.4 Full pages kept for complex flows | record sale, products, reports | ✅ |

---

## 5. Changes made in session 3

| File | Change |
|---|---|
| `app/utils/list_helpers.py` | `paginate()` now orders by primary key when the queryset is unordered. An unordered queryset can return the same row on two pages and skip another one entirely (Django warned about this in the smoke run). |
| `app/views/platform_views.py` | The "Platform Admins" counter now counts superusers as well as `profile.is_platform_admin` users, matching `user_is_platform_admin()`. It previously reported 0 while a superuser was signed in. |
| `app/utils/decorators.py` | Removed a duplicated, stale `require_audit_access` definition that was shadowed by the live one. |
| `app/tests/test_permissions.py` | **New** — 33 permission tests (see §4.1). |
| `tools/migration_rehearsal.py` | **New** — migration rehearsal on a copy of the real database. |
| `tools/render_pages.py` | **New** — renders authenticated pages to static HTML so a headless browser can screenshot them without a login. |
| `app/migrations/0096_adopt_existing_data_to_default_business.py` | The reverse migration now detaches the `OrganizationSetting` row before removing the tenant, so a rollback can never cascade the company profile away. |
| `IMPLEMENTATION_CHECKLIST.md` | Phases 3–8 ticked, session log updated. |

---

## 6. Known limitations and deviations

1. **`event_service.py` is called `notification_service.py`.** The checklist named the
   Phase 4 service `event_service.py`; the implementation is
   `app/services/notification_service.py` with the signals in
   `app/signals/notification_signals.py`. Same responsibility, different name — the
   checklist wording was updated rather than the code renamed.

2. **Module access gates the navigation, the settings workspace, the audit trail and the
   quick actions — not every data page.** The data pages themselves (products, sales,
   users, roles) are tenant scoped but not module gated: a user without the Sales module
   can still reach `/sales/` by typing the URL. The decorators that would close this
   (`require_module_access`, `require_url_access` in `app/utils/decorators.py`) exist and
   work, but are not applied to those views. Wiring them up is the single biggest
   remaining hardening step; it changes navigation behaviour, so it wants its own
   session.

3. **The audit trail is not a legal record.** It lives in the same SQLite database as the
   business data, and a platform administrator can purge it. A business that needs
   tamper-proof history has to move the trail to a separate store.

4. **`debug_toolbar.W001`** is reported by `manage.py check` because the debug toolbar
   middleware is not installed in the settings the check runs against. It is a
   development-only warning.

5. **A rollback of migrations 0093–0102 drops the four tables those migrations create**
   (with their rows). Everything that existed before is preserved — the rehearsal proved
   it — but a rollback is not a no-op.

6. **SQLite is still the database.** The multi-tenant design (shared database, nullable
   tenant FKs, tenant managers) works on SQLite and moves to PostgreSQL without a schema
   change, but the concurrency characteristics of SQLite will not suit a busy
   multi-tenant deployment.

---

## 7. How to run and verify it

```bash
# Development server
./virt/Scripts/python.exe manage.py runserver 8000

# Full test suite
./virt/Scripts/python.exe manage.py test app.tests

# Page smoke (200 URLs)
./virt/Scripts/python.exe manage.py shell -c "exec(open('smoke_test.py', encoding='utf-8').read())"

# Math invariants
./virt/Scripts/python.exe manage.py shell -c "exec(open('verify_math.py', encoding='utf-8').read())"

# Migration rehearsal on a copy of the real database (never touches core/db.sqlite3)
./virt/Scripts/python.exe tools/migration_rehearsal.py

# Render authenticated pages for visual review
./virt/Scripts/python.exe tools/render_pages.py
```

Seed data: `./virt/Scripts/python.exe manage.py seed_data` (password `seed1234`).

---

## 8. Recommended next steps

1. **Apply module gating to the data pages** (limitation 2) — the last real gap in the
   permission model.
2. **Move the audit trail to its own store** before the platform carries real tenants.
3. **Move to PostgreSQL** before the second business is onboarded.
4. **Add a CI job** that runs the three checks in §7 on every push — they take about ten
   minutes together, which is affordable.
