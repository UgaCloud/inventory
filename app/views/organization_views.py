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
def settings_page(request):
    all_currencies = get_all_currencies()
    organization_settings = OrganizationSetting.load()   
    
    organization_settings_form = OrganizationSettingForm(instance=organization_settings)
    
    context = {
        "currencies": all_currencies,
        "organization_settings": organization_settings,
        "organization_settings_form": organization_settings_form,
    }
    return render(request, 'organization/settings_page.html', context)

@login_required
def update_organization_settings(request):
    organization_settings = OrganizationSetting.load()
    count = OrganizationSetting.objects.count()
    
    if request.method == 'POST':
        organization_settings_form = OrganizationSettingForm(request.POST, request.FILES, instance=organization_settings)
        
        if organization_settings_form.is_valid():
            organization_settings_form.save()
            messages.success(request, SUCCESS_EDIT_MESSAGE)
        else:
            messages.error(request, FAILURE_MESSAGE)
    
    return HttpResponseRedirect(reverse('settings_page'))


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
    
@login_required
def add_currency(request):
    if request.POST:
        code = request.POST.get('code')
        desc = request.POST.get('desc')
        cost = request.POST.get('cost')

        school_settings_services.create_currency(code, desc, cost)
        messages.success(request, SUCCESS_ADD_MESSAGE)

        return HttpResponseRedirect(reverse('settings_page'))
    messages.error(request, 'You sent a get request')
    return HttpResponseRedirect(reverse('settings_page'))

@login_required
def edit_currency_page(request, currency_id):
    currency = school_settings_selectors.get_currency(currency_id)
    if request.POST:
        code = request.POST.get('code')
        desc = request.POST.get('desc')
        cost = request.POST.get('cost')
        school_settings_services.update_currency(currency, code, desc, cost)
        messages.success(request, SUCCESS_EDIT_MESSAGE)
        return HttpResponseRedirect(reverse('settings_page'))
    context = {
        "currency": currency
    }
    return render(request, 'settings/edit_currency.html', context)


def delete_currency(request, currency_id):
    currency = school_settings_selectors.get_currency(currency_id)
    currency.delete()
    messages.success(request, DELETE_MESSAGE)
    return HttpResponseRedirect(reverse('settings_page'))
