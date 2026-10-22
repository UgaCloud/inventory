from django.utils import timezone
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings
from datetime import timedelta
import time


class TenantMiddleware:
    """
    Attach the authenticated user's business (tenant) to the request so views,
    context processors and services can scope queries consistently.

    request.business is None for anonymous users and for platform Super
    Administrators viewing platform-wide data; business users always get their
    own business (falling back to the Default Business for legacy accounts).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.business = None
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            from app.models.tenancy import current_business, user_is_platform_admin
            if not user_is_platform_admin(user):
                request.business = current_business(user)
            else:
                # Platform admins act platform-wide unless they explicitly
                # scope themselves to a business in a given view.
                request.business = None

        # Publish the acting user so tenant-aware managers can scope every
        # queryset of this request (views, selectors and services included).
        from app.managers import clear_tenant_actor, set_tenant_actor
        set_tenant_actor(user)
        try:
            return self.get_response(request)
        finally:
            clear_tenant_actor()


class SessionTimeoutMiddleware:
    """
    Middleware to handle session timeout and provide warnings to users.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Get the current time
            current_time = time.time()
            
            # Check if this is the first request in this session
            if 'last_activity' not in request.session:
                request.session['last_activity'] = current_time
            
            # Calculate time since last activity
            last_activity = request.session.get('last_activity', current_time)
            time_since_last_activity = current_time - last_activity
            
            # Get session timeout from settings (default to 1 hour)
            session_timeout = getattr(settings, 'SESSION_COOKIE_AGE', 3600)
            # Warning threshold (seconds before expiry) - default to 5 minutes or a half of session
            warning_threshold = getattr(settings, 'SESSION_WARNING_SECONDS', None)
            if warning_threshold is None:
                # default to half of session timeout or 300 seconds whichever is smaller
                warning_threshold = min(300, int(session_timeout / 2))

            # Check if session has expired
            if time_since_last_activity > session_timeout:
                # Log out the user
                logout(request)
                # Redirect to login page with timeout message
                return redirect(f"{reverse('login')}?timeout=1")
            
            # Update last activity time
            request.session['last_activity'] = current_time
            
            # Add timeout warning if within the configured warning threshold
            seconds_left = int(session_timeout - time_since_last_activity)
            if seconds_left <= warning_threshold:
                request.session['timeout_warning'] = True
                request.session['session_seconds_left'] = seconds_left
            else:
                request.session.pop('timeout_warning', None)
                request.session.pop('session_seconds_left', None)

        response = self.get_response(request)
        return response


class InactivityTimeoutMiddleware:
    """
    Alternative middleware that tracks user inactivity more precisely.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            now = timezone.now()
            
            # Get last activity from session
            last_activity_str = request.session.get('last_activity_time')
            
            if last_activity_str:
                # Convert string back to datetime
                from django.utils.dateparse import parse_datetime
                last_activity = parse_datetime(last_activity_str)
                
                # Calculate inactivity duration
                if last_activity:
                    inactive_duration = now - last_activity
                    max_inactive_time = timedelta(seconds=getattr(settings, 'SESSION_COOKIE_AGE', 600))
                    
                    # Check if user has been inactive too long
                    if inactive_duration > max_inactive_time:
                        logout(request)
                        return redirect(f"{reverse('login')}?timeout=1")
            
            # Update last activity time
            request.session['last_activity_time'] = now.isoformat()

        response = self.get_response(request)
        return response
