# Multi-Tenant Platform Transformation — Implementation Checklist

> Persistent checklist. Update status on every session. Do NOT redo completed phases.
> Last updated: 2026-10-22 (session 3) — all phases complete, see `HANDOVER.md`.

## Phase 1 — Audit & consolidation ✅ (session 1)

### Discovered existing infrastructure (REUSE, do not duplicate)
- **RBAC 2.0**: `Role` (backed by Django `Group`, `is_system_role`, `is_superuser`) + `RoleModule`
  (module IDs 1–16, name via `get_module_name_by_id`) + `UserProfile` (M2M `roles`,
  `effective_modules` property, `employee` link, `department` string).
- **Module access enforcement**: `app/utils/module_mapping.py` (`MENU_MODULE_MAP` URL→module,
  `user_has_module_access`, `user_has_url_access`) + `app/utils/decorators.py`
  (`require_module_access`, `require_url_access`).
- **Menus**: `app/context_processors.py::app_menu` already filters menu per effective modules.
- **Dashboards per role**: `app/utils/dashboard_assignment.py`
  (module sets → Admin/Sales/Stores dashboards, templates under `basic/dashboards/`).
- **Notifications**: `Notification` model (per-user, type, is_read, link) + views
  (`notifications_list_view`, `notifications_api`, mark-read / mark-all-read).
- **Settings**: `OrganizationSetting` **SingletonModel** (name, logo, currency, country, …)
  + `settings_page` / `update_organization_settings` + `Branch`, `Currency` models.
- **Profile**: `profile_views.profile_view` + `profile-details` URL.
- **Auth**: `login_view` (`login_page`), Django `auth.urls`, `sign_up_view`, `logout_view`.
- **Audit-ish**: `RoleDeletionLog` exists (role-scoped only). **No generic audit log.**
- **Signals**: user profile auto-create + role permission sync (`user_signals.py`),
  employee sync, HR signals, sales/expense/finance/stock signals.
- **Tests**: `app/tests/` (33 tests, all passing as of session 1).
- **DB**: `core/db.sqlite3`; settings `core/settings/{general,development,production}.py`.

### Gaps identified (genuinely missing)
1. Multi-tenancy: no `Business`/tenant model; `OrganizationSetting` is a site-wide singleton;
   no tenant scoping on any queryset; no platform-operator concept.
2. No generic `AuditLog` model/service/UI (only `RoleDeletionLog`).
3. Notification event coverage ad-hoc (seeded constants; not driven by a central event service).
4. Public landing page: none. Login page: legacy single-column. Profile page: legacy.
5. Many tables still raw `<table>` with horizontal scroll; search is mostly full-page form GET.
6. Detail navigation: many full-page redirects; no slide-up panels.
7. No animation token system.
8. Dashboards: admin.html rich; sales/stores dashboards exist but static-ish; visibility partly
   hard-coded (`is_admin`/`is_manager` group-name checks in context_processors — legacy).

### Existing behavior that MUST remain unchanged
- All 33 tests keep passing; all 188 pages keep rendering (see session-1 smoke_test.py/verify_math.py).
- Existing URLs stay valid; existing data preserved by additive migrations only.
- RBAC module model (IDs 1–16) and menu mapping preserved (extend, don't replace).

---

## Phase 2 — Tenant administration & access control ✅ (session 1)

- [x] 2.1 `Business` model (name, slug, status: active/suspended, timestamps) + helpers.
- [x] 2.2 Tenant FK strategy: `OrganizationSetting.business` (nullable→default business),
      `Branch.business`, `StoreLocation.business`, `UserProfile.business` — additive
      migrations; data migration auto-provisions "Default Business" and adopts existing rows.
- [x] 2.3 `UserProfile.is_platform_admin` flag + `user_is_platform_admin()` helper +
      `require_platform_admin` decorator.
- [x] 2.4 Platform Super Admin area: `/platform/` — business list, create business, create/
      assign initial Business Administrator, activate/suspend, platform stats dashboard.
- [x] 2.5 Tenant middleware: `request.business` from authenticated user's profile.
- [x] 2.6 Server-side tenant scoping via **tenant-aware managers** (`app/managers.py`:
      `TenantManager` + `TENANT_PATHS`) applied to every tenant-owned model, so all
      views/selectors/services are scoped without touching each queryset; plus
      `business_scope(user, queryset)` helper for explicit call sites.
- [x] 2.7 Platform-vs-business separation: platform admin is NOT auto business staff.
- [x] 2.8 Tests: cross-tenant URL/ID access rejected; platform admin can manage businesses.
- [x] 2.9 Custom roles per business: `Role.name` unique **per business** (migration 0098),
      Django groups renamed `<tenant>:<role>` so permissions cannot leak between tenants;
      business admins cannot create superuser roles or edit platform roles.
- [x] 2.10 `UserProfileManager` keeps `user.profile` relation cache consistent (stale-cache
      bug that could resolve the wrong tenant).

## Phase 3 — Centralized settings & audit logs ✅ (session 3, verified)
- [x] 3.1 AuditLog model (timestamp, actor, business, action, model, record id, description,
      before/after, request id, outcome) + `app/services/audit_service.py` + append-only.
- [x] 3.2 Wire audit: auth events, settings changes, user/role changes, product CRUD,
      inventory ops, sales create/cancel/return, purchases, payments, exports.
- [x] 3.3 Audit log UI (business-scoped; platform-wide for platform admin) w/ filters+pagination.
- [x] 3.4 Tabbed settings workspace consolidating: business profile, structure, users/roles,
      inventory config, sales/purchasing, notifications, security & sessions, audit, appearance,
      data management. Reuse existing pages/models; permission-aware tabs.

## Phase 4 — Notifications ✅ (session 3, verified)
- [x] 4.1 Central event service: `app/services/notification_service.py` (preferences, dedupe
      key, priority) + `app/signals/notification_signals.py`.
      **Deviation:** the checklist said `event_service.py`; the service is named
      `notification_service.py` and the checklist wording was updated, not the code.
- [x] 4.2 Event coverage: sale completed, purchase recorded, low stock, transfer lifecycle
      (raised/approved/rejected/cancelled), role changed, business status change.
- [x] 4.3 Real-time delivery: polling via `notifications_api` with an `after_id` cursor.
- [x] 4.4 Unread count widget, panel w/ mark-read (single + batch), history page w/ search.
- [x] 4.5 Recipient selection by role/module relevance + tenant scoping.

## Phase 5 — Landing, login & profile ✅ (session 3, verified)
- [x] 5.1 Public landing page (`app/templates/public/landing.html`, `/landing/`): no private
      data, honest CTAs (contact the platform administrator).
- [x] 5.2 Two-column login (visual left / form right; mobile stack; auth logic unchanged).
- [x] 5.3 Profile page modernization (personal info, password, security, preferences,
      recent sign-ins) preserving the existing rules.

## Phase 6 — Lists & contextual navigation ✅ (session 3, verified)
- [x] 6.1 Convert horizontal-scrolling tables → compact responsive lists w/ empty states
      (customers, expenses, sales, suppliers, users, roles, platform businesses).
- [x] 6.2 Debounced server-side search + filters + pagination on key lists
      (`app/utils/list_helpers.py`; the query string is preserved across pages).
- [x] 6.3 Slide-up detail panels (bottom sheet, navbar visible, internal tabs, focus mgmt).
- [x] 6.4 Keep full pages for complex workflows (record sale, products, reports).

## Phase 7 — Dashboards & visual consistency ✅ (session 2)
- [x] 7.1 Permission-aware dashboard tabs (dynamic, from effective modules; no name hard-coding).
      `app/utils/dashboard_assignment.py` now returns `{name, template, icon}` per dashboard
      (`DASHBOARD_ICON_MAP`); the tab bar in `basic/index.html` uses the shared accessible
      `.app-tabs` primitive (role=tablist/tab/tabpanel, hash deep-link, arrow-key support).
      Business users never receive the admin dashboard; the shell renders an honest
      empty state when a role unlocks no dashboard.
- [x] 7.2 Operational metrics (real data only) + quick actions per permission.
      New `app/selectors/dashboard_selectors.py` computes every headline number from the
      tenant's own rows (sales, stores, charts, month-over-month). The fixed "+22% / -22% /
      +35%" badges were replaced by `includes/app_change_badge.html`, which renders the real
      month-over-month change and says "No baseline" when there is nothing to compare
      against. Quick actions live in `app/utils/module_mapping.py::get_quick_actions` and
      only offer shortcuts whose module the signed-in user actually holds.
- [x] 7.3 Platform dashboard for platform admin (businesses, users, onboarding). — built in
      Phase 2 (`/platform/`, `app/views/platform_views.py`, `templates/platform/`).
- [x] 7.4 Animation tokens/utilities (fade/slide/hover; prefers-reduced-motion).
      `core/static/assets/css/app-ui.css` + `assets/js/app-ui.js` hold the tokens; the
      `prefers-reduced-motion: reduce` block disables animation and transitions.

## Phase 8 — Verification & handover ✅ (session 3)
- [x] 8.1 Migrations verified on a copy of real data; no destructive ops.
      `tools/migration_rehearsal.py`: rolled 0093–0102 back to 0092 and forward again on a
      **copy** of `core/db.sqlite3`; every protected table and business total was identical
      afterwards (sales 47 / UGX 18,456,000, products 30, customers 8, inventory 56 /
      3,050 units, users 11). Exit 0. The real database was never touched.
- [x] 8.2 Full regression: tests + page smoke + math verifier.
      **193 tests OK**; page smoke **200 URLs OK / 0 failures**; math verifier **0 issues**;
      `manage.py check` clean (1 dev-only debug-toolbar warning); 111 migrations applied,
      0 pending.
- [x] 8.3 Tenant isolation + permission tests green.
      `app/tests/test_tenancy.py` (29) + the new `app/tests/test_permissions.py` (33):
      effective modules, menu filtering, settings-tab gating, audit access (module 9/15 +
      platform only), quick-action filtering, platform area closed to business users.
- [x] 8.4 Final handover report: `HANDOVER.md`.

---

## Session log
- **Session 1 (2026-10-21)**: Phase 1 audit complete. Session-1 prior work (record-sales grid,
  seed gap-fill, 20+ bug fixes, math verification) merged and green.
- **Session 1 (cont.)**: Phase 2 complete — tenant managers, platform area, per-business roles,
  29 new tenancy tests. Full suite: **62 tests, all passing**. Next: Phase 3 (audit log +
  tabbed settings workspace).
- **Session 2 (2026-10-22)**: Phase 7 complete and verified — dashboard tabs are permission-aware
  and carry their own icon, dashboard numbers come from `app/selectors/dashboard_selectors.py`,
  the month-over-month badges compare against real history, and quick actions respect the user's
  modules. 37 new dashboard tests in `app/tests/test_dashboard_metrics.py`.
  Full suite: **154 tests, all passing**; page smoke: **200 URLs OK, 0 failures**;
  math verifier: **0 issues**; `manage.py check`: no issues.
  Note: Phases 3–6 have implementations in the tree (audit log + service + UI, notification
  service/center, `public/landing.html`, modernized login/profile, `includes/app_list*` list
  primitives and the `.app-panel` sheet), but their boxes were never ticked — verify them
  item-by-item before Phase 8 so they are not silently redone. Next: Phase 8 (final regression
  + handover report).
- **Session 3 (2026-10-22)**: Phases 3–6 verified item-by-item against the code and ticked
  (not redone); Phase 8 completed. Migration rehearsal on a copy of the real database
  (`tools/migration_rehearsal.py`) — no data change. New permission test module
  (  `app/tests/test_permissions.py`, 33 tests). Fixes found during verification: unordered
  pagination in `list_helpers.paginate()`, the "Platform Admins" counter ignoring
  superusers, a duplicated `require_audit_access` definition, and a rollback that could
  cascade the company profile away. Full suite: **193 tests, all passing**; page smoke:
  **200 URLs OK, 0 failures**; math verifier: **0 issues**; handover report: `HANDOVER.md`.
- **Session 4 (2026-10-22)**: Work published on a dedicated branch
  `feature/multi-tenant-platform` (branched off `Automotive_filters`; **not** merged into
  `main` — the merge is left to the owner). Re-verified before pushing: **193 tests OK**
  (run in three module groups), page smoke **200 URLs OK / 0 failures**, math verifier
  **0 issues**, `manage.py check` with the one known dev-only `debug_toolbar.W001`
  warning. The generated product placeholder images (`core/media/products/`) are now
  ignored — `manage.py seed_data` recreates them.
