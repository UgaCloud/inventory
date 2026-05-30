from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.db.models import Q
from app.models.products import Automotive
from app.forms.automotive_forms import AutomotiveForm


@login_required
def automotive_list_view(request):
    """List all automotives with search/filter and pagination"""
    queryset = Automotive.objects.all().order_by('-id')

    search = request.GET.get('search', '')
    if search:
        queryset = queryset.filter(
            Q(brand__icontains=search) |
            Q(model__icontains=search) |
            Q(engine_type__icontains=search)
        )

    paginator = Paginator(queryset, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    form = AutomotiveForm()

    context = {
        'automotives': page_obj,
        'page_obj': page_obj,
        'search': search,
        'form': form,
        'total_count': queryset.count(),
    }
    return render(request, 'automotives/automotive_list.html', context)


@login_required
def automotive_create_view(request):
    """Create a new automotive"""
    if request.method == 'POST':
        form = AutomotiveForm(request.POST)
        if form.is_valid():
            automotive = form.save()
            messages.success(request, f'Automotive "{automotive}" has been created successfully.')
            return redirect('automotive_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = AutomotiveForm()

    return render(request, 'automotives/automotive_form.html', {
        'form': form,
        'title': 'Add New Automotive',
        'action': 'create',
    })


@login_required
def automotive_edit_view(request, automotive_id):
    """Edit an existing automotive"""
    automotive = get_object_or_404(Automotive, id=automotive_id)

    if request.method == 'POST':
        form = AutomotiveForm(request.POST, instance=automotive)
        if form.is_valid():
            automotive = form.save()
            messages.success(request, f'Automotive "{automotive}" has been updated successfully.')
            return redirect('automotive_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = AutomotiveForm(instance=automotive)

    return render(request, 'automotives/automotive_form.html', {
        'form': form,
        'automotive': automotive,
        'title': 'Edit Automotive',
        'action': 'edit',
    })


@login_required
def automotive_delete_view(request, automotive_id):
    """Delete an automotive"""
    automotive = get_object_or_404(Automotive, id=automotive_id)

    if request.method == 'POST':
        name = str(automotive)
        automotive.delete()
        messages.success(request, f'Automotive "{name}" has been deleted successfully.')
        return redirect('automotive_list')

    return render(request, 'automotives/automotive_confirm_delete.html', {
        'automotive': automotive,
    })
