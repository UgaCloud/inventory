from django.utils import timezone
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings
from datetime import timedelta
import time


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
            session_timeout = getattr(settings, 'SESSION_COOKIE_AGE', 300)
            
            # Check if session has expired
            if time_since_last_activity > session_timeout:
                # Log out the user
                logout(request)
                # Redirect to login page with timeout message
                return redirect(f"{reverse('login')}?timeout=1")
            
            # Update last activity time
            request.session['last_activity'] = current_time
            
            # Add timeout warning if close to expiry (5 minutes before)
            warning_threshold = 180  # 3 minutes in seconds
            if (session_timeout - time_since_last_activity) <= warning_threshold:
                request.session['timeout_warning'] = True
            else:
                request.session.pop('timeout_warning', None)

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
                    max_inactive_time = timedelta(seconds=getattr(settings, 'SESSION_COOKIE_AGE', 300))
                    
                    # Check if user has been inactive too long
                    if inactive_duration > max_inactive_time:
                        logout(request)
                        return redirect(f"{reverse('login')}?timeout=1")
            
            # Update last activity time
            request.session['last_activity_time'] = now.isoformat()

        response = self.get_response(request)
        return response
