from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from app.models.notification import Notification


@login_required
def notifications_list_view(request):
    """Full notification center page"""
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    unread_count = notifications.filter(is_read=False).count()
    return render(request, 'notifications/notification_center.html', {
        'notifications': notifications,
        'unread_count': unread_count,
    })


@login_required
def notifications_api(request):
    """API endpoint to get recent notifications (for bell icon dropdown)"""
    notifications = Notification.get_recent(request.user, limit=10)
    unread_count = Notification.get_unread_count(request.user)
    data = {
        'unread_count': unread_count,
        'notifications': [
            {
                'id': n.id,
                'title': n.title,
                'message': n.message,
                'type': n.notification_type,
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
