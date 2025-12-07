"""
Flexible dashboard assignment system for custom roles.
"""
from typing import Iterable, List, Dict, Set

# 1. Map dashboard names to sets of module IDs (future-proof)
DASHBOARD_MODULE_MAP: Dict[str, Set[int]] = {
    "Admin Dashboard": {1, 5, 6, 9, 10, 15, 16},  # Main Menu, Staff, Finance, Settings, Dashboard, Role Management, Accounting
    "Sales Dashboard": {4, 7, 11, 13},            # Sales, User Management, Batch Management, Customer Management
    "Stores Dashboard": {2, 3, 12},               # Inventory, Stock, Supplier Management
    # Add new dashboards here as needed
}

# Map dashboard display names to template paths used in the UI.
# Update paths to match your templates if they differ.
DASHBOARD_TEMPLATE_MAP: Dict[str, str] = {
    # Use the actual templates under `app/templates/basic/dashboards/`
    "Admin Dashboard": "basic/dashboards/admin.html",
    "Sales Dashboard": "basic/dashboards/sales.html",
    "Stores Dashboard": "basic/dashboards/stores.html",
}

# 2. Function to get dashboards for a given module set

def get_dashboards_for_modules(module_ids: Iterable[int], dashboard_map: Dict[str, Set[int]] = None) -> List[str]:
    """
    Returns a list of dashboards assigned to a role based on its module IDs.
    :param module_ids: Iterable of module IDs assigned to the role
    :param dashboard_map: Optional custom dashboard-module mapping
    :return: List of dashboard names
    """
    if dashboard_map is None:
        dashboard_map = DASHBOARD_MODULE_MAP
    module_set = set(module_ids)
    assigned_dashboards = [
        dashboard
        for dashboard, modules in dashboard_map.items()
        if module_set & modules  # intersection: at least one module matches
    ]
    return assigned_dashboards


def get_dashboard_info_for_modules(module_ids: Iterable[int], dashboard_map: Dict[str, Set[int]] = None, template_map: Dict[str, str] = None) -> List[Dict[str, str]]:
    """
    Returns list of dicts with 'name' and 'template' for dashboards matching the provided module IDs.
    This is suitable for templates that need both display name and template path.
    """
    if dashboard_map is None:
        dashboard_map = DASHBOARD_MODULE_MAP
    if template_map is None:
        template_map = DASHBOARD_TEMPLATE_MAP

    module_set = set(module_ids)
    info = []
    for name, modules in dashboard_map.items():
        if module_set & modules:
            tmpl = template_map.get(name, "dashboards/default.html")
            info.append({"name": name, "template": tmpl})
    return info


def get_dashboard_templates_for_modules(module_ids: Iterable[int], dashboard_map: Dict[str, Set[int]] = None, template_map: Dict[str, str] = None) -> List[str]:
    """Return only the template paths for dashboards matching module_ids."""
    info = get_dashboard_info_for_modules(module_ids, dashboard_map=dashboard_map, template_map=template_map)
    return [i["template"] for i in info]


# Backwards-compatible alias
get_dashboard_templates_for_modules = get_dashboard_templates_for_modules


# 3. Example usage (for integration/testing)
if __name__ == "__main__":
    # Example: role with modules 1 (Main Menu), 2 (Inventory), 4 (Sales)
    role_modules = [1, 2, 4]
    dashboards = get_dashboards_for_modules(role_modules)
    print("Dashboards assigned:", dashboards)
    # Output: ['Admin Dashboard', 'Sales Dashboard', 'Stores Dashboard']
