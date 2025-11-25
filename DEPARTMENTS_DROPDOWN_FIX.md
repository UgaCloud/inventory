# Transfer Request Departments Dropdown - Fix

## Problem
Departments were not being displayed in the Transfer Request modal dropdown, even though:
- The template had the correct loop code
- The transfer_views.py was passing departments correctly
- Two departments existed in the system

## Root Cause
There were TWO `transfer_request_list` views:
1. `/app/views/transfer_views.py` - ✅ Was passing `departments` to template
2. `/app/views/transfers.py` - ❌ Was NOT passing `departments` to template

**Issue:** The `app/urls.py` imports both files with `*` and since `transfers.py` is imported AFTER `transfer_views.py`, it overwrites the function. The `transfers.py` version was being used, which didn't have departments in the context.

## Solution
Updated `/app/views/transfers.py` to include departments and units in the context:

**Before:**
```python
context = {
    'requests': page_obj,
    'current_status': status_filter,
    'stores': stores,
    'status_counts': status_counts,
}
```

**After:**
```python
# Import necessary models
from app.models.human_resource import Department
from app.models.products import UnitOfMeasure

context = {
    'requests': page_obj,
    'current_status': status_filter,
    'stores': stores,
    'status_counts': status_counts,
    'departments': Department.objects.filter(is_active=True),
    'units': UnitOfMeasure.objects.all(),
}
```

## Files Modified
- `/app/views/transfers.py` (lines 688-703) - Added departments and units to context

## Testing
✅ Navigate to `/transfer_requests/`
✅ Click "New Request" button
✅ Check that the Department dropdown shows all active departments
✅ Create/edit a transfer request and verify the department field works

## Notes
- Both views have similar functionality but serve different purposes
- Consider consolidating these views in the future to avoid this kind of bug
- The fix applies to the main view being used by the URL route
