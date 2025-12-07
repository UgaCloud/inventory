"""
Permission decorators for module-based access control.
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.http import Http404
from app.utils.module_mapping import user_has_module_access

def require_module_access(module_id):
    """
    Decorator to require access to a specific module.
    
    Usage:
        @require_module_access(2)  # Requires Inventory module access
        def my_view(request):
            ...
    
    Args:
        module_id: The module ID required to access the view
        
    Returns:
        Decorated view function that checks module access
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            user = request.user
            
            # Superusers have access to everything
            if user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # Check if user is authenticated
            if not user.is_authenticated:
                messages.error(request, 'You must be logged in to access this page.')
                return redirect('login_page')
            
            # Check module access (RBAC 2.0: uses effective_modules)
            if not user_has_module_access(user, module_id):
                messages.error(request, 'You do not have permission to access this module.')
                raise Http404("You do not have permission to access this module.")
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def require_url_access(url_name):
    """
    Decorator to require access to a specific URL based on module mapping.
    
    Usage:
        @require_url_access('products_page')
        def my_view(request):
            ...
    
    Args:
        url_name: The URL name to check access for
        
    Returns:
        Decorated view function that checks URL access
    """
    from app.utils.module_mapping import get_module_id_for_url, user_has_url_access
    
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            user = request.user
            
            # Superusers have access to everything
            if user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # Check if user is authenticated
            if not user.is_authenticated:
                messages.error(request, 'You must be logged in to access this page.')
                return redirect('login_page')
            
            # Check URL access
            if not user_has_url_access(user, url_name):
                messages.error(request, 'You do not have permission to access this page.')
                raise Http404("You do not have permission to access this page.")
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

