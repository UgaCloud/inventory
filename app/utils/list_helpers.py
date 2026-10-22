"""Helpers for server-side searchable, filterable and paginated list pages.

Every list page in the app follows the same contract:

* the browser sends ``?q=`` (search term), zero or more filter parameters
  and ``?page=`` / ``?per_page=``;
* the view narrows the queryset with :func:`search_queryset`, narrows it
  further with its own filters and finally calls :func:`paginate`;
* the template renders the shared ``includes/app_list.html`` renderer plus
  the shared toolbar and pagination partials.

The helpers keep the query string intact when the user pages, filters or
clears a search, so no page has to reinvent that logic.
"""
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q

DEFAULT_PER_PAGE = 25
MAX_PER_PAGE = 200
PER_PAGE_CHOICES = (10, 25, 50, 100)

# How many numbered page links to show around the current page.
PAGE_WINDOW = 2


def search_term(request, param='q'):
    """The cleaned-up search term of the current request ('' when absent)."""
    return (request.GET.get(param) or '').strip()


def search_queryset(queryset, request, fields, param='q'):
    """Filter ``queryset`` with a case-insensitive OR search over ``fields``.

    Returns ``(queryset, term)`` so the caller can show the term back in
    the search box.
    """
    term = search_term(request, param)
    if not term or not fields:
        return queryset, term
    condition = Q()
    for field in fields:
        condition |= Q(**{f'{field}__icontains': term})
    return queryset.filter(condition), term


def filter_param(request, name, default=''):
    """The value of a filter parameter ('' when absent)."""
    value = (request.GET.get(name) or '').strip()
    return value if value else default


def query_url(request, **overrides):
    """Rebuild the current URL with some query parameters replaced.

    A value of ``None`` or ``''`` removes the parameter, which keeps
    "clear filter" links simple.
    """
    params = request.GET.copy()
    for key, value in overrides.items():
        if value in (None, ''):
            params.pop(key, None)
        else:
            params[key] = value
    encoded = params.urlencode()
    return f'{request.path}?{encoded}' if encoded else request.path


def paginate(request, queryset, per_page=None, param='page', per_page_param='per_page'):
    """Paginate ``queryset`` and build everything the pagination partial needs.

    Returns a dictionary with the page object, the paginator and a list of
    page links (``{'number', 'url', 'is_current'}``) that preserve the
    current search and filter parameters.
    """
    requested = request.GET.get(per_page_param)
    if requested:
        try:
            per_page = int(requested)
        except (TypeError, ValueError):
            per_page = None
    per_page = per_page or DEFAULT_PER_PAGE
    per_page = max(5, min(per_page, MAX_PER_PAGE))

    # A queryset without a deterministic order can return the same row on two
    # pages and skip another one entirely. Fall back to the primary key so
    # paging is always stable.
    if not queryset.ordered:
        queryset = queryset.order_by('pk')

    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get(param) or 1
    try:
        page_obj = paginator.page(page_number)
    except (PageNotInInteger, EmptyPage):
        page_obj = paginator.page(1)

    current = page_obj.number
    first = max(1, current - PAGE_WINDOW)
    last = min(paginator.num_pages, current + PAGE_WINDOW)

    pages = []
    for number in range(first, last + 1):
        pages.append({
            'number': number,
            'url': query_url(request, **{param: number}),
            'is_current': number == current,
        })

    return {
        'page_obj': page_obj,
        'paginator': paginator,
        'is_paginated': paginator.num_pages > 1,
        'total_count': paginator.count,
        'pages': pages,
        'prev_url': query_url(request, **{param: current - 1}) if page_obj.has_previous() else '',
        'next_url': query_url(request, **{param: current + 1}) if page_obj.has_next() else '',
        'per_page': per_page,
        'per_page_choices': PER_PAGE_CHOICES,
    }


def list_context(request, queryset, search_fields=(), per_page=None, filters=None, param='q'):
    """Build the standard context for a searchable list page.

    ``filters`` is a list of ``{'name', 'label', 'options'}`` dictionaries;
    every option is ``{'value', 'label'}``. The currently selected value of
    every filter is read from the query string so the toolbar can mark it
    as selected.
    """
    queryset, term = search_queryset(queryset, request, search_fields, param=param)
    context = paginate(request, queryset, per_page=per_page)
    context.update({
        'search_term': term,
        'search_param': param,
        'search_placeholder': 'Search…',
        'clear_url': request.path,
        'list_filters': [],
        'has_active_filters': False,
    })

    if filters:
        rendered = []
        for spec in filters:
            current = filter_param(request, spec['name'])
            rendered.append({
                'name': spec['name'],
                'label': spec.get('label', spec['name']),
                'options': spec.get('options', []),
                'current': current,
                'is_active': bool(current),
            })
        context['list_filters'] = rendered
        context['has_active_filters'] = any(item['is_active'] for item in rendered)

    return context


def options_from_queryset(queryset, value_field='pk', label_field='name'):
    """Turn a queryset into filter options for the shared toolbar."""
    return [
        {'value': str(getattr(item, value_field)), 'label': str(getattr(item, label_field))}
        for item in queryset
    ]


def row(
    title,
    *,
    icon='file-text',
    category='data',
    meta='',
    href='',
    badges=None,
    fields=None,
    actions=None,
    panel=None,
    panel_id='',
):
    """Build one row for the shared compact list renderer.

    Keeping the shape in one place means every list page presents the same
    anatomy: an icon, a title with optional meta line and badges, a couple
    of labelled figures and a row of actions.

    ``panel`` turns the row into a slide-up detail sheet on small screens:
    it is a dictionary of ``{'title', 'subtitle', 'fields', 'note', 'href'}``
    and ``panel_id`` is the DOM id the sheet is registered under. The sheet
    is rendered by ``includes/app_list.html`` and opened by the "Details"
    action, which the view adds with ``{'panel': panel_id}``.
    """
    return {
        'icon': icon,
        'category': category,
        'title': title,
        'meta': meta,
        'href': href,
        'badges': badges or [],
        'fields': fields or [],
        'actions': actions or [],
        'panel': panel or None,
        'panel_id': panel_id or '',
    }


def panel_action(panel_id, label='Details', icon='info'):
    """An action that opens the slide-up detail sheet of a row."""
    return {'label': label, 'icon': icon, 'panel': panel_id}
