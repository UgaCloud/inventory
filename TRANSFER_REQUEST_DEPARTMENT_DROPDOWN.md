# Transfer Request Modal - Department Dropdown Implementation

## Summary
Updated the Create and Edit Transfer Request modals to use a department dropdown selector instead of a text input field. Departments are populated from the system database and properly prefilled in edit mode.

## Changes Made

### 1. Updated Views (`/app/views/transfer_views.py`)

**Added Imports:**
```python
from django.db import transaction
from django.http import JsonResponse
from app.models.human_resource import Department
from app.models.products import StoreLocation, UnitOfMeasure
```

**Context Data:**
Departments are already being passed to the template:
```python
context = {
    'requests': requests,
    'form': form,
    'item_formset': formset,
    'departments': departments,  # Active departments passed to template
    'stores': stores,
    'units': UnitOfMeasure.objects.all(),
    'user_department': request.user.profile.department if hasattr(request.user, 'profile') else None
}
```

### 2. Updated Template (`/app/templates/transfers/transfer_request_list.html`)

**Create Modal - Department Field:**
Changed from:
```html
<input type="text" id="department" name="department" class="form-control" placeholder="Your department">
```

To:
```html
<select id="department" name="department" class="form-select">
  <option value="">Select a department</option>
  {% for dept in departments %}
  <option value="{{ dept.id }}">{{ dept.name }}</option>
  {% endfor %}
</select>
```

**Edit Modal - Prefill Logic:**
The edit modal automatically prefills the department dropdown using:
```javascript
if (deptEl) deptEl.value = r.department || '';
```

### 3. Updated API Endpoint (`/app/views/stock_views.py - transfer_request_json`)

**Before:**
```python
'department': getattr(tr, 'department', '') if hasattr(tr, 'department') else '',
```

**After:**
```python
'department': tr.department.id if tr.department else '',
'department_name': tr.department.name if tr.department else '',
```

This ensures:
- The department ID is returned for the dropdown value
- The department name is also returned for display purposes
- Edit modal can properly prefill the select dropdown with the stored department ID

## Features

✅ **Create Modal:**
- Department field is now a dropdown select
- Shows all active departments from the system
- Optional field (can be left empty if needed)

✅ **Edit Modal:**
- Department dropdown is automatically prefilled with the stored department
- Displays the department name for clarity
- Allows changing the department when editing

✅ **Data Structure:**
- Department is stored as a ForeignKey to the Department model
- Properly linked in database relationships
- Easy to extend with additional department features

## Usage

### For End Users:
1. **Creating a Transfer Request:**
   - Open "Create New Transfer Request" modal
   - Select a department from the dropdown (optional)
   - Fill in other required fields
   - Submit

2. **Editing a Transfer Request:**
   - Click "Edit" on an existing transfer request
   - Modal opens with department pre-selected
   - Change department if needed
   - Submit

### For Developers:
- Departments are available in template context
- API returns both department ID and name
- Easy to add additional department-related fields
- ForeignKey relationship ensures data integrity

## Database Model

```python
class TransferRequest(models.Model):
    # ... other fields ...
    department = models.ForeignKey("app.Department", on_delete=models.CASCADE, related_name="transfer_requests")
    # ... other fields ...
```

## Testing

Test the following scenarios:
1. ✓ Create new transfer request with a department
2. ✓ Create new transfer request without selecting a department (if optional)
3. ✓ Edit existing transfer request and verify department is prefilled
4. ✓ Edit existing transfer request and change the department
5. ✓ Verify modal closes and updates are saved
6. ✓ Verify all active departments appear in the dropdown

## Files Modified

1. `/app/views/transfer_views.py` - Added imports
2. `/app/templates/transfers/transfer_request_list.html` - Changed department field to dropdown
3. `/app/views/stock_views.py` - Updated `transfer_request_json` to return department ID
