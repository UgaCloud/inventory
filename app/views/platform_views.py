"""
Platform Super Administrator area.

These views manage the platform itself: registered businesses, their initial
Business Administrators, and platform-wide statistics. They are guarded by
`require_platform_admin`, so business administrators can never reach them
(indistinguishable 404).

Business Administrators manage their own business through the ordinary
settings/users pages; nothing here is reachable for them.
"""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import render, get_object_or_404, redirect

from app.models.tenancy import Business, user_is_platform_admin
from app.models.human_resource import Role, RoleModule, UserProfile
from app.utils.decorators import require_platform_admin
from app.utils.module_mapping import get_module_name_by_id
from app.utils.list_helpers import list_context, panel_action
from django.urls import reverse

User = get_user_model()

ALL_MODULE_IDS = list(range(1, 17))


def ensure_business_admin_role(business):
    """
    Get or create the per-business "Business Administrator" system role with
    access to every module. Role names are globally unique in the current
    schema, so collisions are disambiguated with the business name.
    """
    base = 'Business Administrator'
    candidates = [base, f'{base} — {business.name}']
    role = Role.objects.filter(business=business, name__in=candidates).first()
    if role:
        return role

    name = base
    if Role.objects.filter(name=name).exists():
        name = f'{base} — {business.name}'
        n = 2
        while Role.objects.filter(name=name).exists():
            name = f'{base} — {business.name} ({n})'
            n += 1

    role = Role.objects.create(
        business=business,
        name=name,
        description=f'Administrator role for {business.name}',
        is_system_role=True,
        is_staff=False,
    )
    role.set_modules(ALL_MODULE_IDS)
    return role


@require_platform_admin
def platform_dashboard(request):
    """Platform-wide health: businesses, users, recent onboarding."""
    businesses = Business.objects.all()
    stats = {
        'businesses_total': businesses.count(),
        'businesses_active': businesses.filter(status=Business.STATUS_ACTIVE).count(),
        'businesses_suspended': businesses.filter(status=Business.STATUS_SUSPENDED).count(),
        'users_total': User.objects.count(),
        # Mirror `user_is_platform_admin`: a Django superuser is a platform
        # administrator as well, so the counter must not ignore them.
        'platform_admins': User.objects.filter(
            Q(is_superuser=True) | Q(profile__is_platform_admin=True)
        ).distinct().count(),
        'recent_businesses': businesses.order_by('-created_at')[:5],
        'recent_users': User.objects.select_related('profile').order_by('-date_joined')[:8],
    }
    return render(request, 'platform/dashboard.html', {'stats': stats})


@require_platform_admin
def platform_business_list(request):
    businesses = Business.objects.annotate(
        user_count=Count('user_profiles', distinct=True),
        product_count=Count('products', distinct=True),
        store_count=Count('store_locations', distinct=True),
    ).order_by('name')

    status = request.GET.get('status', '')
    if status in (Business.STATUS_ACTIVE, Business.STATUS_SUSPENDED):
        businesses = businesses.filter(status=status)

    context = list_context(
        request,
        businesses,
        search_fields=('name', 'slug', 'contact_email'),
        filters=[
            {
                'name': 'status',
                'label': 'All statuses',
                'options': [
                    {'value': Business.STATUS_ACTIVE, 'label': 'Active'},
                    {'value': Business.STATUS_SUSPENDED, 'label': 'Suspended'},
                ],
            },
        ],
    )
    context.update({
        'businesses': context['page_obj'].object_list,
        'selected_status': status,
        'search_placeholder': 'Name, slug or contact email',
        'toolbar_label': 'businesses',
        'empty_title': 'No businesses found',
        'empty_text': 'Register the first business to start onboarding it on the platform.',
        'empty_action_href': reverse('platform_business_create'),
        'empty_action_label': 'Register business',
        'empty_icon': 'building',
    })

    rows = []
    for business in context['businesses']:
        detail_url = reverse('platform_business_detail', args=[business.pk])
        panel_id = f'app-panel-business-{business.pk}'
        rows.append({
            'icon': 'building',
            'category': 'platform',
            'title': business.name,
            'meta': ' · '.join(
                part for part in [business.contact_email, business.slug] if part
            ),
            'href': detail_url,
            'badges': [
                {
                    'label': 'Active' if business.is_active else 'Suspended',
                    'tone': 'success' if business.is_active else 'danger',
                },
            ],
            'fields': [
                {'label': 'Users', 'value': business.user_count},
                {'label': 'Products', 'value': business.product_count},
                {'label': 'Stores', 'value': business.store_count},
            ],
            'actions': [
                panel_action(panel_id),
                {'label': 'Manage business', 'icon': 'settings', 'href': detail_url},
            ],
            'panel_id': panel_id,
            'panel': {
                'title': business.name,
                'subtitle': business.contact_email or business.slug,
                'fields': [
                    {'label': 'Slug', 'value': business.slug or '—'},
                    {'label': 'Contact email', 'value': business.contact_email or '—'},
                    {'label': 'Users', 'value': business.user_count},
                    {'label': 'Products', 'value': business.product_count},
                    {'label': 'Stores', 'value': business.store_count},
                    {'label': 'Registered', 'value': business.created_at.strftime('%d %b %Y') if business.created_at else '—'},
                ],
                'href': detail_url,
            },
        })
    context['rows'] = rows

    return render(request, 'platform/business_list.html', context)


@require_platform_admin
def platform_business_create(request):
    """Register a business and provision its initial Business Administrator."""
    if request.method == 'POST':
        name = (request.POST.get('name') or '').strip()
        contact_email = (request.POST.get('contact_email') or '').strip()
        admin_username = (request.POST.get('admin_username') or '').strip()
        admin_email = (request.POST.get('admin_email') or '').strip()
        admin_password = request.POST.get('admin_password') or ''

        errors = []
        if not name:
            errors.append('Business name is required.')
        if not admin_username:
            errors.append('Administrator username is required.')
        if len(admin_password) < 8:
            errors.append('Administrator password must be at least 8 characters.')
        if User.objects.filter(username=admin_username).exists():
            errors.append('That username is already taken.')
        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'platform/business_form.html', {
                'form_values': request.POST,
            })

        try:
            with transaction.atomic():
                business = Business.objects.create(
                    name=name,
                    contact_email=contact_email,
                    created_by=request.user,
                )
                admin_user = User.objects.create_user(
                    username=admin_username,
                    email=admin_email,
                    password=admin_password,
                )
                profile, _ = UserProfile.objects.get_or_create(user=admin_user)
                profile.business = business
                profile.is_platform_admin = False
                profile.save(update_fields=['business', 'is_platform_admin'])

                admin_role = ensure_business_admin_role(business)
                profile.roles.add(admin_role)
        except Exception as exc:  # pragma: no cover - defensive
            messages.error(request, f'Could not create business: {exc}')
            return render(request, 'platform/business_form.html', {
                'form_values': request.POST,
            })

        messages.success(
            request,
            f'Business “{business.name}” registered and administrator '
            f'“{admin_user.username}” provisioned.',
        )
        return redirect('platform_business_detail', business_id=business.pk)

    return render(request, 'platform/business_form.html', {'form_values': {}})


@require_platform_admin
def platform_business_detail(request, business_id):
    business = get_object_or_404(Business, pk=business_id)
    business_users = User.objects.filter(profile__business=business).select_related(
        'profile'
    ).order_by('username')
    # NOTE: Role.user_count is a model property, so it must not be shadowed
    # by an annotation of the same name (Django would try to assign to it).
    roles = Role.objects.filter(business=business).order_by('name')

    return render(request, 'platform/business_detail.html', {
        'business': business,
        'business_users': business_users,
        'roles': roles,
    })


@require_platform_admin
def platform_business_set_status(request, business_id):
    """Activate or suspend a business (POST only)."""
    business = get_object_or_404(Business, pk=business_id)
    if request.method != 'POST':
        return redirect('platform_business_detail', business_id=business.pk)

    action = request.POST.get('action')
    if action == 'suspend':
        business.suspend()
        messages.warning(request, f'Business “{business.name}” suspended.')
    elif action == 'activate':
        business.activate()
        messages.success(request, f'Business “{business.name}” activated.')
    else:
        messages.error(request, 'Unknown action.')
    return redirect('platform_business_detail', business_id=business.pk)


@require_platform_admin
def platform_provision_admin(request, business_id):
    """Create an additional administrator for an existing business."""
    business = get_object_or_404(Business, pk=business_id)
    if request.method != 'POST':
        return redirect('platform_business_detail', business_id=business.pk)

    username = (request.POST.get('admin_username') or '').strip()
    email = (request.POST.get('admin_email') or '').strip()
    password = request.POST.get('admin_password') or ''

    if not username or len(password) < 8:
        messages.error(request, 'Username and a password of 8+ characters are required.')
        return redirect('platform_business_detail', business_id=business.pk)
    if User.objects.filter(username=username).exists():
        messages.error(request, 'That username is already taken.')
        return redirect('platform_business_detail', business_id=business.pk)

    with transaction.atomic():
        new_admin = User.objects.create_user(username=username, email=email, password=password)
        profile, _ = UserProfile.objects.get_or_create(user=new_admin)
        profile.business = business
        profile.is_platform_admin = False
        profile.save(update_fields=['business', 'is_platform_admin'])
        profile.roles.add(ensure_business_admin_role(business))

    messages.success(request, f'Administrator “{username}” provisioned for {business.name}.')
    return redirect('platform_business_detail', business_id=business.pk)
