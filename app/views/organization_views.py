from django.shortcuts import (
    render, redirect, 
    get_object_or_404, HttpResponseRedirect
)
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from app.forms.organization_form import *
from app.selectors.organization_selectors import *
from app.models.organization import *


@login_required
def manage_branches(request):
    if request.method == 'POST':
        form = BranchForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Branch added successfully.")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = BranchForm()
    context = {
        'form': form,
        'branches': get_branches()
    }
    return render(request, 'organization/branches.html', context)

@login_required
def edit_branch(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if request.method == 'POST':
        form = BranchForm(request.POST, instance=branch)
        if form.is_valid():
            form.save()
            messages.success(request, "Branch updated successfully.")
            return redirect(manage_branches)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = BranchForm(instance=branch)
    context = {
        'form': form,
        'branch': branch
    }
    return render(request, 'organization/edit_branch.html', context)

@login_required
def delete_branch(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    branch.delete()
    messages.success(request, "Branch deleted successfully.")
    
    return redirect(manage_branches)

