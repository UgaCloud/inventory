/* ==========================================================================
   App UI — shared client-side behaviour
   --------------------------------------------------------------------------
   Loaded after bootstrap.bundle.min.js. It powers the primitives that the
   shared design system (assets/css/app-ui.css) defines:

     1. Client-side tab bars      (.app-tabs + [data-tab-target])
     2. Slide-up detail panels    (.app-panel + [data-panel-open])
     3. Panel focus management    (focus in, Escape, focus out)

   Everything is opt-in through data attributes, so a template only needs
   the markup — no per-page JavaScript.
   ========================================================================== */
(function () {
  'use strict';

  var FOCUSABLE = [
    'a[href]',
    'button:not([disabled])',
    'input:not([disabled]):not([type="hidden"])',
    'select:not([disabled])',
    'textarea:not([disabled])',
    '[tabindex]:not([tabindex="-1"])'
  ].join(',');

  function focusableWithin(container) {
    if (!container) return [];
    return Array.prototype.filter.call(
      container.querySelectorAll(FOCUSABLE),
      function (node) {
        return node.offsetParent !== null || node.getClientRects().length > 0;
      }
    );
  }

  /* ------------------------------------------------------------------ tabs */
  function initTabs(root) {
    var tabs = root.querySelectorAll('[data-tab-target]');
    if (!tabs.length) return;

    var panels = root.parentElement
      ? root.parentElement.querySelectorAll('[data-tab-panel]')
      : document.querySelectorAll('[data-tab-panel]');

    function activate(target, push) {
      var found = false;
      tabs.forEach(function (tab) {
        var isActive = tab.getAttribute('data-tab-target') === target;
        if (isActive) found = true;
        tab.classList.toggle('is-active', isActive);
        tab.setAttribute('aria-selected', isActive ? 'true' : 'false');
        /* Roving tab index: only the open tab is in the tab order. */
        tab.setAttribute('tabindex', isActive ? '0' : '-1');
      });
      if (!found) return;

      panels.forEach(function (panel) {
        var isActive = panel.getAttribute('data-tab-panel') === target;
        panel.hidden = !isActive;
        panel.classList.toggle('is-active', isActive);
      });

      if (push && window.history && window.history.replaceState) {
        try {
          window.history.replaceState(null, '', '#' + target);
        } catch (error) {
          /* ignore — hash updates are a nicety, not a requirement */
        }
      }
    }

    tabs.forEach(function (tab, index) {
      tab.addEventListener('click', function (event) {
        event.preventDefault();
        activate(tab.getAttribute('data-tab-target'), true);
      });

      /* Arrow keys move between tabs, as the tab pattern expects. */
      tab.addEventListener('keydown', function (event) {
        var next = null;
        if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
          next = tabs[(index + 1) % tabs.length];
        } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
          next = tabs[(index - 1 + tabs.length) % tabs.length];
        } else if (event.key === 'Home') {
          next = tabs[0];
        } else if (event.key === 'End') {
          next = tabs[tabs.length - 1];
        }
        if (!next) return;
        event.preventDefault();
        activate(next.getAttribute('data-tab-target'), true);
        next.focus();
      });
    });

    var hash = (window.location.hash || '').replace('#', '');
    if (hash) {
      activate(hash, false);
    } else {
      /* No deep link: open the first tab so the bar always shows which
         panel is on screen. */
      activate(tabs[0].getAttribute('data-tab-target'), false);
    }
  }

  /* ---------------------------------------------------------------- panels */
  var openPanels = [];

  /* Every page shares one backdrop: the sheet slides up over it and the
     backdrop closes whatever sheet is currently on top. */
  function sharedBackdrop() {
    return document.querySelector('.app-panel-backdrop');
  }

  function openPanel(panel) {
    if (!panel || panel.classList.contains('is-open')) return;

    var backdrop = sharedBackdrop();

    panel.classList.add('is-open');
    panel.setAttribute('aria-hidden', 'false');
    if (backdrop) backdrop.classList.add('is-open');
    document.body.classList.add('app-panel-open');

    panel._previousFocus = document.activeElement;

    var focusable = focusableWithin(panel);
    if (focusable.length) focusable[0].focus();
    else panel.focus();

    if (openPanels.indexOf(panel) === -1) openPanels.push(panel);
  }

  function closePanel(panel) {
    if (!panel) return;

    panel.classList.remove('is-open');
    panel.setAttribute('aria-hidden', 'true');

    var index = openPanels.indexOf(panel);
    if (index > -1) openPanels.splice(index, 1);

    if (!document.querySelector('.app-panel.is-open')) {
      var backdrop = sharedBackdrop();
      if (backdrop) backdrop.classList.remove('is-open');
      document.body.classList.remove('app-panel-open');
    }

    if (panel._previousFocus && typeof panel._previousFocus.focus === 'function') {
      panel._previousFocus.focus();
    }
  }

  function topPanel() {
    return openPanels.length ? openPanels[openPanels.length - 1] : null;
  }

  function initPanels() {
    document.querySelectorAll('[data-panel-open]').forEach(function (trigger) {
      trigger.addEventListener('click', function (event) {
        event.preventDefault();
        var panel = document.getElementById(trigger.getAttribute('data-panel-open'));
        openPanel(panel);
      });
    });

    document.querySelectorAll('[data-panel-close]').forEach(function (trigger) {
      trigger.addEventListener('click', function (event) {
        event.preventDefault();
        var panel = trigger.closest('.app-panel');
        closePanel(panel || topPanel());
      });
    });

    document.querySelectorAll('.app-panel-backdrop').forEach(function (backdrop) {
      backdrop.addEventListener('click', function () {
        closePanel(topPanel());
      });
    });

    document.addEventListener('keydown', function (event) {
      if (event.key !== 'Escape' || !openPanels.length) return;
      closePanel(topPanel());
    });

    /* Keep the tab focus inside an open panel (simple focus trap). */
    document.addEventListener('keydown', function (event) {
      if (event.key !== 'Tab' || !openPanels.length) return;
      var panel = topPanel();
      var focusable = focusableWithin(panel);
      if (!focusable.length) return;
      var first = focusable[0];
      var last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    });
  }

  /* ------------------------------------------------------- list behaviour */
  var SEARCH_DEBOUNCE_MS = 400;

  function submitForm(form) {
    // Always start from page 1 when the query changes.
    var page = form.querySelector('[name="page"]');
    if (page) page.value = '';
    if (typeof form.requestSubmit === 'function') form.requestSubmit();
    else form.submit();
  }

  function attachSearchBehaviour(form, input) {
    if (!form || form._appSearchBound) return;
    form._appSearchBound = true;

    var timer = null;

    function submit() {
      if (timer) clearTimeout(timer);
      timer = null;
      submitForm(form);
    }

    if (input) {
      input.addEventListener('input', function () {
        if (timer) clearTimeout(timer);
        timer = setTimeout(submit, SEARCH_DEBOUNCE_MS);
      });
      input.addEventListener('keydown', function (event) {
        if (event.key === 'Enter') {
          event.preventDefault();
          submit();
        }
      });
    }

    form.querySelectorAll('[data-filter-select], [data-auto-submit]').forEach(function (control) {
      if (control._appAutoBound) return;
      control._appAutoBound = true;
      control.addEventListener('change', submit);
    });
  }

  function initSearchToolbars() {
    // Shared toolbar: <form data-search-form> with <input data-search-input>.
    document.querySelectorAll('[data-search-form]').forEach(function (form) {
      attachSearchBehaviour(form, form.querySelector('[data-search-input]'));
    });

    // Richer filter bars: <input data-live-search="#form-id">.
    document.querySelectorAll('[data-live-search]').forEach(function (input) {
      var selector = input.getAttribute('data-live-search');
      var form = selector ? document.querySelector(selector) : null;
      attachSearchBehaviour(form, input);
    });

    // Standalone controls that submit their own form when changed.
    document.querySelectorAll('[data-auto-submit]').forEach(function (control) {
      if (control._appAutoBound) return;
      var form = control.closest('form');
      if (!form) return;
      control._appAutoBound = true;
      control.addEventListener('change', function () {
        submitForm(form);
      });
    });
  }

  function initListRows() {
    document.querySelectorAll('.app-list-row[data-href]').forEach(function (row) {
      row.addEventListener('click', function (event) {
        // Let links and buttons inside the row do their own thing.
        if (event.target.closest('a, button, input, select, textarea, label')) return;
        window.location.href = row.getAttribute('data-href');
      });
      row.addEventListener('keydown', function (event) {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        event.preventDefault();
        window.location.href = row.getAttribute('data-href');
      });
    });
  }

  function init() {
    document.querySelectorAll('[data-tabs]').forEach(initTabs);
    initPanels();
    initSearchToolbars();
    initListRows();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
