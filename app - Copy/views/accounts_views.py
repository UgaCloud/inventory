from django.shortcuts import render

def manage_accounts_view(request):
    return render(request, 'accounts.html')