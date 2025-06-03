from django.shortcuts import render, redirect
from app.forms.product_forms import CategoryForm
from app.selectors.category_selectors import get_category_by_id
from app.views.product_views import manage_product_view

def add_category_view(request):
    if request.method == "POST":
        form = CategoryForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect(manage_product_view)
    else:
        form = CategoryForm()

    context = {
        'form':form
    }

    return render(request, 'add_category.html', context)

def delete_category_view(request, category_id):
    category = get_category_by_id(category_id)
    category.delete()
    return redirect(manage_product_view)

