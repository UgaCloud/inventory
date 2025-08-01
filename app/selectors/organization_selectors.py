from app.models.organization import *

def get_organization_settings():
    return OrganizationSetting.load()

def get_branches():
    return Branch.objects.all()

def get_branch(branch_id):
    return Branch.objects.get(id = branch_id)

def get_branch_by_name(name):
    return Branch.objects.filter(name=name)

def get_active_branches():
    return Branch.objects.filter(is_active=True)

def get_branches_by_city(city):
    return Branch.objects.filter(city=city)

def branch_exists(branch_id):
    return Branch.objects.filter(id=branch_id).exists()

def count_branches():
    return Branch.objects.count()


def get_all_currencies():
    return Currency.objects.all()


def get_currency(currency_id):
    return Currency.objects.get(pk=currency_id)


def get_usd_currency():
    try:
        return Currency.objects.get(code="USD")
    except Currency.DoesNotExist:
        return None


def get_base_currency():
    organization_setting = OrganizationSetting.load()
    country = organization_setting.country
    if country == "UG":
        return get_ugx_currency()

def get_currency_from_code(code):
    try:
        return Currency.objects.get(code=code)
    except Currency.DoesNotExist:
        return None


def get_ugx_currency():
    try:
        return Currency.objects.get(code="UGX")
    except Currency.DoesNotExist:
        return None
