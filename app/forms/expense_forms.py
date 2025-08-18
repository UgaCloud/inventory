from django import forms
from app.models.expense import Expense, ExpenseCategory

class ExpenseCategoryForm(forms.ModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ['name', 'description']

class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = [
            'store', 'category', 'amount', 'description', 'reference', 'user',
            'related_purchase', 'related_sale', 'related_cashflow', 'attachment'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is not None and amount <= 0:
            raise forms.ValidationError('Amount must be greater than zero.')
        return amount
