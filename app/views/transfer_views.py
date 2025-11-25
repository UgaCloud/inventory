from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse

from app.models.transactions import TransferRequest, StockTransfer, StockTransferItem
from app.models.human_resource import Department
from app.models.products import StoreLocation, UnitOfMeasure
from app.forms.transaction_forms import (
    TransferRequestForm, StockTransferForm, StockTransferItemForm, StockTransferItemFormSet, TransferRequestItemFormSet, 
    TransferRequestApprovalForm
)
from app.selectors.transfer_selectors import *
from app.selectors.product_selectors import get_stores

@login_required
def transfer_request_list(request):
    requests = get_all_transfer_requests()
    departments = Department.objects.filter(is_active=True)
    stores = StoreLocation.objects.filter(is_active=True)
    
    # Initialize forms with request context
    form = TransferRequestForm(request=request)
    formset = TransferRequestItemFormSet()
    
    context = {
        'requests': requests,
        'form': form,
        'item_formset': formset,
        'departments': departments,
        'stores': stores,
        'units': UnitOfMeasure.objects.all(),
        'user_department': request.user.profile.department if hasattr(request.user, 'profile') else None
    }
    
    return render(request, 'transfers/transfer_request_list.html', context)

@login_required
def add_transfer_request(request):
    if request.method == 'POST':
        form = TransferRequestForm(request.POST, request=request)
        formset = TransferRequestItemFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    transfer_request = form.save(commit=False)
                    transfer_request.requested_by = request.user
                    transfer_request.status = 'pending'
                    transfer_request.save()
                    
                    formset.instance = transfer_request
                    formset.save()
                    
                    messages.success(request, f'Transfer request #{transfer_request.id} created successfully.')
                    
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': True,
                            'request_id': transfer_request.id,
                            'message': 'Transfer request created successfully!'
                        })
                    else:
                        return redirect('transfer_request_list')
                        
            except Exception as e:
                messages.error(request, f'Error creating transfer request: {str(e)}')
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': str(e)
                    })
        else:
            # Handle form errors
            error_messages = []
            if form.errors:
                for field, errors in form.errors.items():
                    for error in errors:
                        error_messages.append(f"{field}: {error}")
            if formset.errors:
                for i, errors in enumerate(formset.errors):
                    for field, error in errors.items():
                        error_messages.append(f"Item {i+1} - {field}: {error}")
            
            error_message = "; ".join(error_messages)
            messages.error(request, f'Please correct the errors: {error_message}')
            
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': error_message
                })
    
    # If not POST or invalid form, return to list with errors
    return redirect('transfer_request_list')

@login_required
def update_transfer_request(request, request_id):
    transfer_request = get_object_or_404(TransferRequest, pk=request_id, requested_by=request.user)
    
    if request.method == 'POST':
        form = TransferRequestForm(request.POST, instance=transfer_request, request=request)
        formset = TransferRequestItemFormSet(request.POST, instance=transfer_request)
        
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    # Only allow editing if status is pending
                    if transfer_request.status != 'pending':
                        messages.error(request, 'Cannot edit transfer request that is not pending.')
                        return redirect('transfer_request_list')
                    
                    form.save()
                    formset.save()
                    
                    messages.success(request, f'Transfer request #{transfer_request.id} updated successfully.')
                    
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': True,
                            'message': 'Transfer request updated successfully!'
                        })
                    else:
                        return redirect('transfer_request_list')
                        
            except Exception as e:
                messages.error(request, f'Error updating transfer request: {str(e)}')
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': str(e)
                    })
        else:
            # Handle form errors
            error_messages = []
            if form.errors:
                for field, errors in form.errors.items():
                    for error in errors:
                        error_messages.append(f"{field}: {error}")
            if formset.errors:
                for i, errors in enumerate(formset.errors):
                    for field, error in errors.items():
                        error_messages.append(f"Item {i+1} - {field}: {error}")
            
            error_message = "; ".join(error_messages)
            messages.error(request, f'Please correct the errors: {error_message}')
            
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': error_message
                })
    
    return redirect('transfer_request_list')



@login_required
def transfer_request_detail(request, request_id):
    transfer_request = get_object_or_404(TransferRequest, pk=request_id)

    form = TransferRequestForm(instance=transfer_request)
    
    request_items = transfer_request.items.all()

    context = {
        'request': transfer_request,
        'form': form, 
        'items':request_items,
    }

    return render(request, 'transfers/transfer_request_details.html', context)


@login_required
def stock_transfer_list(request):
    transfers = get_approved_transfer_requests()

    transfer_request_id = request.GET.get('transfer_request_id') or request.POST.get('transfer_request')

    transfer_request = None
    initial_items = []

    if transfer_request_id:
        transfer_request = get_object_or_404(TransferRequest, id=transfer_request_id)
        
        # Get items from the transfer request
        initial_items = [
            {
                'product': item.product,
                'quantity': item.quantity,
                'transfer_request_item': item.id
            }
            for item in transfer_request.items.all()
        ]

    form = StockTransferForm(initial={'transfer_request': transfer_request_id} if transfer_request_id else None)
        
    formset = StockTransferItemFormSet(initial=initial_items)

    stores = get_stores()

    context = {
        'transfers': transfers,
        'form': form,
        'item_formset': formset,
        'transfer_request': transfer_request,
        'stores': stores
    }

    return render(request, 'transfers/stock_transfer_list.html', context)

@login_required
def stock_transfer_create(request):
    
    if request.method == 'POST':
        form = StockTransferForm(request.POST)
        formset = StockTransferItemFormSet(request.POST)
        print("in post")
        if form.is_valid() and formset.is_valid():
            print("Insave")
            transfer = form.save()
            formset.instance = transfer
            formset.save()
           
            messages.success(request, 'Stock transfer created successfully.')
            
        return redirect(stock_transfer_list)
     

@login_required
def stock_transfer_detail(request, pk):
    print(pk)
    transfer_obj = get_stock_transfer_by_id(pk)
    if not transfer_obj:
        return render(request, '404.html', status=404)
    return render(request, 'transfers/stock_transfer_detail.html', {'transfer_obj': transfer_obj})

@login_required
def stock_transfer_update(request, pk):
    transfer = get_object_or_404(StockTransfer, pk=pk)
    if request.method == 'POST':
        form = StockTransferForm(request.POST, instance=transfer)
        formset = StockTransferItemFormSet(request.POST, instance=transfer)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, 'Stock transfer updated successfully.')
            return redirect('stock_transfer_list')
    else:
        form = StockTransferForm(instance=transfer)
        formset = StockTransferItemFormSet(instance=transfer)
    return render(request, 'stock_transfer_form.html', {'form': form, 'item_formset': formset})

@login_required
def pending_transfer_requests_for_approval(request):
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to view this page.')
        return redirect('index_page')
    
    requests = get_pending_transfer_requests()
    approval_form = TransferRequestApprovalForm()

    context = {
        'requests': requests,
        'approval_form': approval_form
    }
    return render(request, 'transfers/pending_transfer_requests.html', context)

@login_required
def approve_transfer_request(request, request_id):
    """Approve a transfer request with optional comments - handles AJAX from list page"""
    from django.http import JsonResponse
    from django.utils import timezone
    
    try:
        # Only allow POST method
        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'Only POST method allowed'}, status=405)
        
        try:
            transfer_request = TransferRequest.objects.get(pk=request_id)
        except TransferRequest.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Transfer request not found'}, status=404)
        
        # Validate that request is in pending status
        if transfer_request.status != 'pending':
            error_msg = f'Cannot approve request. Current status is: {transfer_request.get_status_display()}'
            return JsonResponse({'success': False, 'error': error_msg}, status=400)
        
        # Update status and approver info
        transfer_request.status = 'approved'
        transfer_request.approved_by = request.user
        transfer_request.approved_date = timezone.now()
        
        # Save comments if provided
        comments = request.POST.get('comments', '').strip()
        if comments:
            existing_note = transfer_request.note or ''
            approval_note = f"[Approved by {request.user.get_full_name() or request.user.username} on {timezone.now().strftime('%Y-%m-%d %H:%M')}]: {comments}"
            transfer_request.note = f"{existing_note}\n{approval_note}".strip() if existing_note else approval_note
        
        transfer_request.save()

        # Always return JSON for POST requests (AJAX from list page)
        return JsonResponse({
            'success': True,
            'request_id': transfer_request.id,
            'message': 'Transfer request approved successfully. It now appears in the Approved Requests list.'
        })
    except Exception as e:
        # Catch any unexpected errors and return JSON
        import traceback
        print(f"Error in approve_transfer_request: {e}")
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'error': f'Server error: {str(e)}'}, status=500)

@login_required
def reject_transfer_request(request, request_id):
    """Reject a transfer request with optional comments - handles AJAX from list page"""
    from django.http import JsonResponse
    from django.utils import timezone
    
    try:
        # Only allow POST method
        if request.method != 'POST':
            return JsonResponse({'success': False, 'error': 'Only POST method allowed'}, status=405)
        
        try:
            transfer_request = TransferRequest.objects.get(pk=request_id)
        except TransferRequest.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Transfer request not found'}, status=404)
        
        # Validate that request is in pending status
        if transfer_request.status != 'pending':
            error_msg = f'Cannot reject request. Current status is: {transfer_request.get_status_display()}'
            return JsonResponse({'success': False, 'error': error_msg}, status=400)
        
        # Update status and approver info
        transfer_request.status = 'rejected'
        transfer_request.approved_by = request.user
        transfer_request.approved_date = timezone.now()
        
        # Save comments if provided
        comments = request.POST.get('comments', '').strip()
        if comments:
            existing_note = transfer_request.note or ''
            rejection_note = f"[Rejected by {request.user.get_full_name() or request.user.username} on {timezone.now().strftime('%Y-%m-%d %H:%M')}]: {comments}"
            transfer_request.note = f"{existing_note}\n{rejection_note}".strip() if existing_note else rejection_note
        
        transfer_request.save()

        # Always return JSON for POST requests (AJAX from list page)
        return JsonResponse({
            'success': True, 
            'request_id': transfer_request.id,
            'message': 'Transfer request rejected.'
        })
    except Exception as e:
        # Catch any unexpected errors and return JSON
        import traceback
        print(f"Error in reject_transfer_request: {e}")
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'error': f'Server error: {str(e)}'}, status=500)
