from app.models.organization import OrganizationSetting, Branch, Currency 

def organization_setting(request):
  
    settings = OrganizationSetting.load()
    return {
        'organization': settings,
    }
