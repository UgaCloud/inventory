from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from app.models.notification import Notification

PAGE_SIZE = 25


@login_required
def notifications_list_view(request):
    """Full notification center page."""
    only_unread = request.GET.get('unread') == '1'
    search = request.GET.get('q', '').strip()
    everything = Notification.objects.filter(user=request.user)
    unread_count = everything.filter(is_read=False).count()
    total_count = everything.count()

    shown = everything.filter(is_read=False) if only_unread else everything
    if search:
        shown = shown.filter(
            Q(title__icontains=search) | Q(message__icontains=search)
        )
    paginator = Paginator(shown.order_by('-created_at'), PAGE_SIZE)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'notifications/notification_center.html', {
        'notifications': page.object_list,
        'page_obj': page,
        'paginator': paginator,
        'unread_count': unread_count,
        'total_count': total_count,
        'only_unread': only_unread,
        'search_query': search,
    })


@login_required
def notifications_api(request):
    """
    API endpoint to get recent notifications (for the bell icon panel).

    The panel polls this endpoint. Passing ``after_id`` returns only the
    notifications that arrived since that id, which keeps the poll cheap
    when nothing happened.
    """
    try:
        limit = int(request.GET.get('limit', 10))
    except (TypeError, ValueError):
        limit = 10
    limit = max(1, min(limit, 50))

    try:
        after_id = int(request.GET.get('after_id', 0))
    except (TypeError, ValueError):
        after_id = 0

    if after_id:
        notifications = list(
            Notification.objects.filter(user=request.user, id__gt=after_id)
            .order_by('-id')[:limit]
        )
        notifications.reverse()
    else:
        notifications = list(Notification.get_recent(request.user, limit=limit))

    unread_count = Notification.get_unread_count(request.user)
    data = {
        'unread_count': unread_count,
        'last_id': notifications[-1].id if notifications else after_id,
        'notifications': [
            {
                'id': n.id,
                'title': n.title,
                'message': n.message,
                'type': n.notification_type,
                'priority': n.priority,
                'is_read': n.is_read,
                'link': n.link or '',
                'created_at': n.created_at.strftime('%Y-%m-%d %H:%M'),
            }
            for n in notifications
        ],
    }
    return JsonResponse(data)


@login_required
@require_http_methods(["POST"])
def notification_mark_read(request, notification_id):
    """Mark a single notification as read"""
    try:
        notification = Notification.objects.get(id=notification_id, user=request.user)
        notification.mark_as_read()
        return JsonResponse({'success': True})
    except Notification.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Not found'}, status=404)


@login_required
@require_http_methods(["POST"])
def notification_mark_all_read(request):
    """Mark all notifications as read"""
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'success': True})
