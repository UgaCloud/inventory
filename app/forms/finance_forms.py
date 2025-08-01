from django import forms
from app.models.finance import BankAccount, BankTransaction

class BankAccountForm(forms.ModelForm):
    class Meta:
        model = BankAccount
        fields = ['name', 'account_number', 'bank_name', 'opening_balance', 'is_active', 'note']

class BankTransactionForm(forms.ModelForm):
    class Meta:
        model = BankTransaction
        fields = [
            'bank_account', 'store', 'amount', 'transaction_type',
            'reference', 'user', 'note', 'related_cashflow'
        ]
        
