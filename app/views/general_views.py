from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages


def index_view(request):
    return render(request, 'index.html')

def login_view(request):

    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)

        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect(index_view)

    else:
        form = AuthenticationForm()

    context = {
        'form':form
    }

    return render(request, 'registration/login.html', context)