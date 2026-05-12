/* pipeline_overview.html — vanilla JS.
   Features: outline scroll-spy, glossary hover cards, search-highlight. */
(function () {
  'use strict';

  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  // --- 1. Outline scroll-spy ----------------------------------------------
  const outlineLinks = $$('.outline a[href^="#"]');
  const idsInOrder = outlineLinks
    .map(a => a.getAttribute('href').slice(1))
    .filter(Boolean);
  const headings = idsInOrder
    .map(id => document.getElementById(id))
    .filter(Boolean);

  function setActive(id) {
    outlineLinks.forEach(a => {
      const target = a.getAttribute('href').slice(1);
      a.classList.toggle('is-active', target === id);
    });
  }

  function syncOutline() {
    const top = window.scrollY + 120;
    let activeId = headings[0] ? headings[0].id : null;
    for (const h of headings) {
      if (h.offsetTop <= top) activeId = h.id;
      else break;
    }
    if (activeId) setActive(activeId);
  }
  window.addEventListener('scroll', syncOutline, { passive: true });
  syncOutline();

  // Smooth scroll with header offset
  outlineLinks.forEach(a => {
    a.addEventListener('click', (e) => {
      const id = a.getAttribute('href').slice(1);
      const target = document.getElementById(id);
      if (target) {
        e.preventDefault();
        const y = target.getBoundingClientRect().top + window.scrollY - 90;
        window.scrollTo({ top: y, behavior: 'smooth' });
        history.replaceState(null, '', '#' + id);
      }
    });
  });

  // --- 2. Glossary hover cards --------------------------------------------
  const glossaryData = JSON.parse($('#glossary-data').textContent);
  const glossaryByKey = {};
  for (const t of glossaryData) glossaryByKey[t.term.toLowerCase()] = t;

  const card = document.createElement('div');
  card.id = 'glossary-card';
  document.body.appendChild(card);

  let hideTimer = null;

  function showCard(target) {
    const key = target.dataset.term.toLowerCase();
    const entry = glossaryByKey[key];
    if (!entry) return;
    card.innerHTML =
      '<div class="term-name">' + escapeHtml(entry.term) + '</div>' +
      '<div>' + escapeHtml(entry.definition) + '</div>' +
      (entry.scope ? '<div class="term-scope">' + escapeHtml(entry.scope) + '</div>' : '');
    const r = target.getBoundingClientRect();
    const cardW = 380, gutter = 12;
    let left = window.scrollX + r.left;
    if (left + cardW + gutter > window.innerWidth + window.scrollX) {
      left = window.innerWidth + window.scrollX - cardW - gutter;
    }
    if (left < window.scrollX + gutter) left = window.scrollX + gutter;
    card.style.left = left + 'px';
    card.style.top = (window.scrollY + r.bottom + 6) + 'px';
    card.classList.add('visible');
  }
  function hideCard() {
    card.classList.remove('visible');
  }
  document.addEventListener('mouseover', (e) => {
    const t = e.target.closest('span.term');
    if (t) {
      clearTimeout(hideTimer);
      showCard(t);
    }
  });
  document.addEventListener('mouseout', (e) => {
    const t = e.target.closest('span.term');
    if (t) {
      hideTimer = setTimeout(hideCard, 120);
    }
  });
  card.addEventListener('mouseenter', () => clearTimeout(hideTimer));
  card.addEventListener('mouseleave', hideCard);

  // --- 3. In-page search --------------------------------------------------
  const search = $('#search-input');
  const stats = $('#search-stats');
  const clearBtn = $('#search-clear');

  function clearHighlights() {
    $$('mark.search-hit').forEach(m => {
      const parent = m.parentNode;
      parent.replaceChild(document.createTextNode(m.textContent), m);
      parent.normalize();
    });
  }

  function highlight(query) {
    clearHighlights();
    if (!query || query.length < 2) {
      stats.textContent = '';
      return;
    }
    const re = new RegExp(escapeRegex(query), 'gi');
    const proseRoot = $('.prose');
    let count = 0;
    const walker = document.createTreeWalker(proseRoot, NodeFilter.SHOW_TEXT, {
      acceptNode: (n) => {
        if (!n.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
        const p = n.parentNode;
        if (p.tagName === 'SCRIPT' || p.tagName === 'STYLE') return NodeFilter.FILTER_REJECT;
        if (p.classList && p.classList.contains('search-hit')) return NodeFilter.FILTER_REJECT;
        if (p.closest('pre')) return NodeFilter.FILTER_ACCEPT;
        return NodeFilter.FILTER_ACCEPT;
      },
    });
    const nodes = [];
    let n;
    while ((n = walker.nextNode())) nodes.push(n);
    for (const node of nodes) {
      if (!re.test(node.nodeValue)) { re.lastIndex = 0; continue; }
      re.lastIndex = 0;
      const frag = document.createDocumentFragment();
      let last = 0;
      let m;
      while ((m = re.exec(node.nodeValue))) {
        frag.appendChild(document.createTextNode(node.nodeValue.slice(last, m.index)));
        const mark = document.createElement('mark');
        mark.className = 'search-hit';
        mark.textContent = m[0];
        frag.appendChild(mark);
        last = m.index + m[0].length;
        count++;
      }
      frag.appendChild(document.createTextNode(node.nodeValue.slice(last)));
      node.parentNode.replaceChild(frag, node);
    }
    stats.textContent = count + (count === 1 ? ' match' : ' matches');
    if (count > 0) {
      const first = $('mark.search-hit');
      if (first) {
        const y = first.getBoundingClientRect().top + window.scrollY - 110;
        window.scrollTo({ top: y, behavior: 'smooth' });
      }
    }
  }

  let searchDebounce = null;
  if (search) {
    search.addEventListener('input', () => {
      clearTimeout(searchDebounce);
      searchDebounce = setTimeout(() => highlight(search.value.trim()), 180);
    });
  }
  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      search.value = '';
      clearHighlights();
      stats.textContent = '';
      search.focus();
    });
  }

  // --- helpers ------------------------------------------------------------
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }
  function escapeRegex(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }
})();
