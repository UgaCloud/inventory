"""
Audit log views.

The list is tenant scoped: a business administrator only sees the events of
their own business, a platform administrator sees every event including the
platform-wide ones (business = NULL).
"""
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Max, Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from app.models.audit import AuditLog
from app.models.tenancy import user_is_platform_admin
from app.utils.decorators import require_audit_access

PER_PAGE = 25


def _scoped_logs(request):
    """Audit entries the request is allowed to see."""
    if user_is_platform_admin(request.user):
        return AuditLog.objects.select_related('actor', 'business').all()
    business = getattr(request, 'business', None)
    if business is None:
        return AuditLog.objects.none()
    return AuditLog.objects.select_related('actor', 'business').filter(business=business)


def _snapshot_boundary(scoped):
    """
    Highest id the reader may see.

    A page is rendered after its query was built, and rendering is not a
    read-only operation: another user can record something in the meantime
    and the page itself can trigger a write (a settings row being
    bootstrapped, for example). Such a row would push the previous entries
    one slot down and make the page lose the last row of the window it
    counted. Pinning the result set to the ids that existed when the page
    was requested keeps count and content in sync.
    """
    return scoped.aggregate(highest=Max('pk'))['highest']


def _query_prefix(**params):
    """URL encoded query string that keeps the active filters."""
    clean = {key: value for key, value in params.items() if value}
    if not clean:
        return ''
    return urlencode(clean) + '&'


def _filtered_logs(request):
    """
    The entries matching the filters of the request.

    Returns the queryset and the filter values, so the page and the CSV
    export always work on exactly the same set.
    """
    scoped = _scoped_logs(request)

    boundary = _snapshot_boundary(scoped)
    if boundary is not None:
        scoped = scoped.filter(pk__lte=boundary)

    search = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()
    action = request.GET.get('action', '').strip()
    actor_id = request.GET.get('actor', '').strip()
    date_from = request.GET.get('from', '').strip()
    date_to = request.GET.get('to', '').strip()

    logs = scoped
    if search:
        logs = logs.filter(
            Q(description__icontains=search)
            | Q(actor_name__icontains=search)
            | Q(model_name__icontains=search)
            | Q(object_id__icontains=search)
        )
    if category:
        logs = logs.filter(category=category)
    if action:
        logs = logs.filter(action=action)
    if actor_id:
        logs = logs.filter(actor_id=actor_id)
    if date_from:
        logs = logs.filter(timestamp__date__gte=date_from)
    if date_to:
        logs = logs.filter(timestamp__date__lte=date_to)

    filters = {
        'search_query': search,
        'selected_category': category,
        'selected_action': action,
        'selected_actor': actor_id,
        'date_from': date_from,
        'date_to': date_to,
    }
    return logs, filters


@require_audit_access
@login_required
def audit_log_view(request):
    """Audit trail with search, filters and pagination."""
    logs, filters = _filtered_logs(request)

    total = logs.count()
    paginator = Paginator(logs, PER_PAGE)
    page_obj = paginator.get_page(request.GET.get('page'))

    actors = (
        _scoped_logs(request)
        .exclude(actor=None)
        .values('actor_id', 'actor_name')
        .distinct()
        .order_by('actor_name')
    )

    context = {
        'logs': page_obj,
        'page_obj': page_obj,
        'total_logs': total,
        **filters,
        'categories': AuditLog.Category.choices,
        'actions': AuditLog.Action.choices,
        'actors': actors,
        'is_platform_admin': user_is_platform_admin(request.user),
        'audit_query_prefix': _query_prefix(
            q=filters['search_query'],
            category=filters['selected_category'],
            action=filters['selected_action'],
            actor=filters['selected_actor'],
            **{'from': filters['date_from'], 'to': filters['date_to']},
        ),
    }
    return render(request, 'audit/audit_log.html', context)


@require_audit_access
@login_required
def audit_log_export(request):
    """Export the (filtered) audit trail as CSV."""
    from app.services.audit_service import log_event

    logs, filters = _filtered_logs(request)
    response = _csv_response(logs)
    log_event(
        'export',
        category='data',
        description=f'Exported the audit trail ({logs.count()} entries)',
        request=request,
    )
    return response


def _csv_response(logs):
    import csv
    from django.http import HttpResponse

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="audit-log.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'Timestamp', 'Actor', 'Business', 'Category', 'Action', 'Record',
        'Description', 'Outcome', 'IP address',
    ])
    for entry in logs.iterator():
        writer.writerow([
            entry.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            entry.actor_name,
            entry.business.name if entry.business_id else 'Platform',
            entry.get_category_display(),
            entry.get_action_display(),
            entry.target,
            entry.description,
            entry.get_outcome_display(),
            entry.ip_address or '',
        ])
    return response


@require_audit_access
@login_required
def audit_log_detail(request, pk):
    """Detail of a single audit entry."""
    entry = _scoped_logs(request).filter(pk=pk).first()
    if entry is None:
        from django.http import Http404
        raise Http404('Audit entry not found')
    return render(request, 'audit/audit_detail.html', {'entry': entry})


@login_required
@require_http_methods(['POST'])
def audit_log_purge(request):
    """Only a platform administrator may purge the trail (rare, deliberate)."""
    from app.utils.decorators import require_platform_admin

    if not user_is_platform_admin(request.user):
        messages.error(request, 'Only a platform administrator can purge the audit trail.')
        return redirect('audit_log_page')

    category = request.POST.get('category', '').strip()
    cutoff = request.POST.get('cutoff', '').strip()
    queryset = AuditLog.objects.all()
    if category:
        queryset = queryset.filter(category=category)
    if cutoff:
        queryset = queryset.filter(timestamp__lt=cutoff)

    from app.services.audit_service import log_event

    count = queryset.count()
    log_event(
        'delete',
        category='platform',
        description=f'Purged {count} audit entries',
        request=request,
    )
    # The audit model is append-only for ordinary users; a deliberate purge by
    # a platform administrator is the only way to remove entries.
    queryset._raw_delete(queryset.db)
    messages.success(request, f'Purged {count} audit entries.')
    return redirect('audit_log_page')
