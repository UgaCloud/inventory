from app.models.organization import OrganizationSettings, Branch, Currency 

def organization_settings(request):
  
    settings = OrganizationSettings.load()
    return {
        'organization_settings': settings,
    }
