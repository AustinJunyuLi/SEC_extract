/* csv_user_manual.html — vanilla JS.
   Features:
     - in-page search/highlight across manual prose (M1)
     - column chip drilldown: distribution + sample values, click → filter data pane (M2)
     - event_code chip drilldown: definition + worked example + "show rows" → filter (M3)
     - two-pane sync: data pane click on cell → manual scrolls to column def
     - sortable, filterable, virtualized data table
     - row detail card popover
     - glossary hover cards (shared with overview)
*/
(function () {
  'use strict';

  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  // ---------------------------------------------------------------------
  // Boot data
  // ---------------------------------------------------------------------
  const csvData = JSON.parse($('#csv-data').textContent);     // { columns: [...], rows: [...] }
  const columnsMeta = JSON.parse($('#columns-data').textContent); // [{name, kind, description, enum_ref}]
  const codedValues = JSON.parse($('#coded-values-data').textContent); // { row_unit: {description, values:[]}, ... }
  const eventCodes = JSON.parse($('#event-codes-data').textContent);   // { categories: [...] }
  const glossaryData = JSON.parse($('#glossary-data').textContent);

  const allRows = csvData.rows;
  const allColumns = csvData.columns;
  const colToIdx = {};
  allColumns.forEach((c, i) => (colToIdx[c] = i));

  const colMetaByName = {};
  for (const c of columnsMeta) colMetaByName[c.name] = c;

  // ---------------------------------------------------------------------
  // Data pane: filter / sort / virtualized table
  // ---------------------------------------------------------------------

  const tableWrap = $('#data-table-wrap');
  const table = $('#data-table');
  const thead = $('thead', table);
  const tbody = $('tbody', table);
  const dealFilter = $('#filter-deal');
  const codeFilter = $('#filter-code');
  const dataSearch = $('#data-search');
  const dataStats = $('#data-stats');

  const state = {
    sortCol: 'deal_slug',
    sortDir: 'asc',
    deal: '',
    code: '',
    text: '',
    visibleRows: allRows.slice(),
    crossHighlightCol: null, // index of column to highlight (cross-link from manual)
  };

  // Populate filter dropdowns
  const distinctDeals = Array.from(new Set(allRows.map(r => r[colToIdx.deal_slug]))).sort();
  const distinctCodes = Array.from(new Set(allRows.map(r => r[colToIdx.event_code]))).sort();
  function fillSelect(sel, options, allLabel) {
    sel.innerHTML = '';
    const optAll = document.createElement('option');
    optAll.value = '';
    optAll.textContent = allLabel;
    sel.appendChild(optAll);
    for (const v of options) {
      const o = document.createElement('option');
      o.value = v;
      o.textContent = v;
      sel.appendChild(o);
    }
  }
  fillSelect(dealFilter, distinctDeals, 'all deals');
  fillSelect(codeFilter, distinctCodes, 'all codes');

  // Render table head once
  function renderHead() {
    const tr = document.createElement('tr');
    for (const col of allColumns) {
      const th = document.createElement('th');
      th.dataset.col = col;
      th.textContent = col;
      const marker = document.createElement('span');
      marker.className = 'sort-marker';
      marker.textContent = '↕';
      th.appendChild(marker);
      th.addEventListener('click', () => sortBy(col));
      tr.appendChild(th);
    }
    thead.innerHTML = '';
    thead.appendChild(tr);
  }
  renderHead();

  function sortBy(col) {
    if (state.sortCol === col) state.sortDir = state.sortDir === 'asc' ? 'desc' : 'asc';
    else { state.sortCol = col; state.sortDir = 'asc'; }
    applyFilters();
  }

  function applyFilters() {
    const idx = colToIdx;
    const text = state.text.toLowerCase();
    state.visibleRows = allRows.filter(r => {
      if (state.deal && r[idx.deal_slug] !== state.deal) return false;
      if (state.code && r[idx.event_code] !== state.code) return false;
      if (text) {
        let match = false;
        for (const v of r) {
          if (String(v).toLowerCase().indexOf(text) !== -1) { match = true; break; }
        }
        if (!match) return false;
      }
      return true;
    });

    // Sort
    const ci = colToIdx[state.sortCol];
    const dir = state.sortDir === 'asc' ? 1 : -1;
    const meta = colMetaByName[state.sortCol] || {};
    const isNumeric = meta.kind === 'number' || meta.kind === 'int';
    state.visibleRows.sort((a, b) => {
      let av = a[ci], bv = b[ci];
      if (isNumeric) {
        av = av === '' || av == null ? -Infinity : parseFloat(av);
        bv = bv === '' || bv == null ? -Infinity : parseFloat(bv);
        return (av - bv) * dir;
      }
      av = String(av).toLowerCase();
      bv = String(bv).toLowerCase();
      if (av < bv) return -1 * dir;
      if (av > bv) return 1 * dir;
      return 0;
    });

    // Update sort markers
    $$('th', thead).forEach(th => {
      const marker = $('.sort-marker', th);
      const colName = th.dataset.col;
      if (colName === state.sortCol) {
        th.classList.add('sorted');
        marker.textContent = state.sortDir === 'asc' ? '↑' : '↓';
      } else {
        th.classList.remove('sorted');
        marker.textContent = '↕';
      }
    });

    renderRows();
    dataStats.textContent = state.visibleRows.length + ' / ' + allRows.length + ' rows';
  }

  // Virtualized rendering: window of ~150 rows on either side of scroll position.
  // For 419 rows the simpler approach is fine: render a chunk, expand on scroll.
  // Practical virtualization: render up to 200 at a time; show a "show more" sentinel.
  const RENDER_LIMIT = 200;
  let renderedCount = 0;

  function renderRows() {
    tbody.innerHTML = '';
    renderedCount = 0;
    if (state.visibleRows.length === 0) {
      const tr = document.createElement('tr');
      const td = document.createElement('td');
      td.className = 'row-empty';
      td.colSpan = allColumns.length;
      td.textContent = 'No rows match the current filters.';
      tr.appendChild(td);
      tbody.appendChild(tr);
      return;
    }
    appendChunk();
    tableWrap.scrollTop = 0;
  }

  function appendChunk() {
    const remaining = state.visibleRows.length - renderedCount;
    const limit = Math.min(remaining, RENDER_LIMIT);
    const frag = document.createDocumentFragment();
    for (let i = 0; i < limit; i++) {
      const row = state.visibleRows[renderedCount + i];
      const tr = document.createElement('tr');
      for (let c = 0; c < allColumns.length; c++) {
        const td = document.createElement('td');
        td.textContent = String(row[c]);
        td.dataset.col = allColumns[c];
        if (state.crossHighlightCol === c) td.classList.add('cross-highlight');
        tr.appendChild(td);
      }
      tr.dataset.rowIndex = renderedCount + i;
      tr.addEventListener('click', (e) => {
        const tdEl = e.target.closest('td');
        if (tdEl && tdEl.dataset.col) {
          scrollManualToColumn(tdEl.dataset.col);
        }
        showRowDetail(row);
      });
      frag.appendChild(tr);
    }
    tbody.appendChild(frag);
    renderedCount += limit;
  }

  // Scroll-triggered chunk loading
  tableWrap.addEventListener('scroll', () => {
    const nearBottom = tableWrap.scrollTop + tableWrap.clientHeight > tableWrap.scrollHeight - 200;
    if (nearBottom && renderedCount < state.visibleRows.length) appendChunk();
  });

  // Filter handlers
  dealFilter.addEventListener('change', () => { state.deal = dealFilter.value; applyFilters(); });
  codeFilter.addEventListener('change', () => { state.code = codeFilter.value; applyFilters(); });
  let dataSearchTimer = null;
  dataSearch.addEventListener('input', () => {
    clearTimeout(dataSearchTimer);
    dataSearchTimer = setTimeout(() => { state.text = dataSearch.value.trim(); applyFilters(); }, 180);
  });

  // ---------------------------------------------------------------------
  // Row detail card
  // ---------------------------------------------------------------------

  let rowCard = null;
  function showRowDetail(row) {
    if (rowCard) rowCard.remove();
    rowCard = document.createElement('div');
    rowCard.className = 'row-detail-card';
    const close = document.createElement('button');
    close.className = 'close-btn';
    close.textContent = '×';
    close.title = 'close';
    close.addEventListener('click', () => { rowCard.remove(); rowCard = null; });
    rowCard.appendChild(close);

    const title = document.createElement('h4');
    title.textContent = row[colToIdx.deal_slug] + ':' + row[colToIdx.event_order] + ' — ' + row[colToIdx.event_code];
    rowCard.appendChild(title);

    const dl = document.createElement('dl');
    const fieldsToShow = [
      'event_date', 'party_name', 'bidder_class', 'event_family', 'stage',
      'formality', 'bid_value', 'bid_value_unit', 'consideration_type',
      'evidence_page', 'evidence_quote_full', 'confidence', 'source_claim_ids',
    ];
    for (const f of fieldsToShow) {
      const ci = colToIdx[f];
      if (ci == null) continue;
      const v = row[ci];
      if (v === '' || v == null) continue;
      const dt = document.createElement('dt');
      dt.textContent = f;
      const dd = document.createElement('dd');
      if (f === 'evidence_quote_full') dd.classList.add('quote');
      dd.textContent = String(v);
      dl.appendChild(dt);
      dl.appendChild(dd);
    }
    rowCard.appendChild(dl);
    document.body.appendChild(rowCard);
  }

  // ---------------------------------------------------------------------
  // Column chip → drilldown panel (M2)
  // ---------------------------------------------------------------------

  const colReferenceRoot = $('#column-reference');

  function buildColumnChips() {
    const grid = document.createElement('div');
    grid.className = 'col-grid';
    columnsMeta.forEach((c, idx) => {
      const chip = document.createElement('button');
      chip.className = 'col-chip';
      chip.dataset.col = c.name;
      chip.innerHTML =
        '<span class="col-num">' + String(idx + 1).padStart(2, '0') + '</span>' +
        '<span class="col-name">' + escapeHtml(c.name) + '</span>' +
        '<span class="col-type">' + escapeHtml(c.kind) + (c.enum_ref ? ' · ' + c.enum_ref : '') + '</span>';
      chip.addEventListener('click', () => openColumnDetail(c.name));
      grid.appendChild(chip);
    });
    colReferenceRoot.appendChild(grid);

    const detail = document.createElement('div');
    detail.id = 'col-detail-host';
    colReferenceRoot.appendChild(detail);
  }

  function openColumnDetail(colName) {
    $$('.col-chip').forEach(ch => ch.classList.toggle('is-active', ch.dataset.col === colName));
    const meta = colMetaByName[colName];
    const ci = colToIdx[colName];
    if (ci == null) return;

    // distribution
    const counts = {};
    let total = 0;
    let numericValues = [];
    for (const r of allRows) {
      const v = r[ci];
      const k = (v === '' || v == null) ? '∅ (empty)' : String(v);
      counts[k] = (counts[k] || 0) + 1;
      total++;
      if ((meta.kind === 'number' || meta.kind === 'int') && v !== '' && v != null) {
        const n = parseFloat(v);
        if (!isNaN(n)) numericValues.push(n);
      }
    }
    const sortedCounts = Object.entries(counts).sort((a, b) => b[1] - a[1]);

    const detailHost = $('#col-detail-host');
    detailHost.innerHTML = '';

    const card = document.createElement('div');
    card.className = 'col-detail';
    card.innerHTML =
      '<h3>' + escapeHtml(colName) + '</h3>' +
      '<div class="col-desc">' + escapeHtml(meta.description || '') + '</div>';

    if (numericValues.length > 0) {
      numericValues.sort((a, b) => a - b);
      const min = numericValues[0];
      const max = numericValues[numericValues.length - 1];
      const median = numericValues[Math.floor(numericValues.length / 2)];
      const stats = document.createElement('div');
      stats.style.marginBottom = '0.6em';
      stats.innerHTML = '<small><b>n</b>=' + numericValues.length + ' · <b>min</b>=' + min + ' · <b>median</b>=' + median + ' · <b>max</b>=' + max + '</small>';
      card.appendChild(stats);
    }

    // Show top 12 values with bars
    const distTable = document.createElement('table');
    distTable.className = 'dist-table';
    distTable.innerHTML = '<thead><tr><th>value</th><th>count</th><th>share</th></tr></thead>';
    const tb = document.createElement('tbody');
    const maxCount = sortedCounts[0] ? sortedCounts[0][1] : 1;
    sortedCounts.slice(0, 12).forEach(([val, n]) => {
      const tr = document.createElement('tr');
      const w = Math.max(2, Math.round((n / maxCount) * 100));
      tr.innerHTML =
        '<td><code>' + escapeHtml(val) + '</code></td>' +
        '<td>' + n + '</td>' +
        '<td><span class="dist-bar" style="width:' + w + '%"></span> ' + Math.round(n / total * 100) + '%</td>';
      tr.style.cursor = 'pointer';
      tr.title = 'Click to filter the data pane';
      tr.addEventListener('click', () => {
        // Filter data pane to rows where this column equals this value
        if (colName === 'deal_slug') { state.deal = val; dealFilter.value = val; }
        else if (colName === 'event_code') { state.code = val; codeFilter.value = val; }
        else { state.text = val; dataSearch.value = val; }
        state.crossHighlightCol = ci;
        applyFilters();
        scrollDataPaneToTop();
      });
      tb.appendChild(tr);
    });
    if (sortedCounts.length > 12) {
      const tr = document.createElement('tr');
      tr.innerHTML = '<td colspan="3" style="color:var(--muted); font-size:0.8em;">+ ' + (sortedCounts.length - 12) + ' more value' + (sortedCounts.length - 12 === 1 ? '' : 's') + '</td>';
      tb.appendChild(tr);
    }
    distTable.appendChild(tb);
    card.appendChild(distTable);

    // If enum: show meaning lookup from coded_values
    if (meta.enum_ref && codedValues[meta.enum_ref]) {
      const enumDef = codedValues[meta.enum_ref];
      const meaningWrap = document.createElement('div');
      meaningWrap.style.marginTop = '0.6em';
      meaningWrap.innerHTML =
        '<small style="color:var(--muted)">' + escapeHtml(enumDef.description || '') + '</small>';
      const dl = document.createElement('dl');
      dl.style.marginTop = '0.4em';
      enumDef.values.forEach(ev => {
        const dt = document.createElement('dt');
        dt.style.fontFamily = 'var(--font-mono)';
        dt.style.fontSize = '0.78rem';
        dt.style.color = 'var(--blue)';
        dt.style.marginTop = '0.4em';
        dt.textContent = ev.value;
        const dd = document.createElement('dd');
        dd.style.margin = '0 0 0.2em 1em';
        dd.style.fontSize = '0.84rem';
        dd.textContent = ev.meaning;
        dl.appendChild(dt);
        dl.appendChild(dd);
      });
      meaningWrap.appendChild(dl);
      card.appendChild(meaningWrap);
    }

    // Sample rows (3 distinct rows from the embedded CSV)
    const seenSamples = new Set();
    const samples = [];
    for (const r of allRows) {
      const v = r[ci];
      const k = String(v);
      if (seenSamples.has(k)) continue;
      seenSamples.add(k);
      samples.push(r);
      if (samples.length >= 3) break;
    }
    if (samples.length > 0) {
      const sampHead = document.createElement('div');
      sampHead.style.marginTop = '0.7em';
      sampHead.style.fontSize = '0.82rem';
      sampHead.style.color = 'var(--muted)';
      sampHead.textContent = 'Sample row values:';
      card.appendChild(sampHead);
      const list = document.createElement('div');
      list.className = 'sample-list';
      samples.forEach(r => {
        const item = document.createElement('div');
        item.innerHTML = '<code>' + escapeHtml(r[colToIdx.deal_slug] + ':' + r[colToIdx.event_order]) + '</code> — ' + escapeHtml(String(r[ci]));
        list.appendChild(item);
      });
      card.appendChild(list);
    }

    detailHost.appendChild(card);
    detailHost.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  // ---------------------------------------------------------------------
  // Event-code chip → drilldown panel (M3)
  // ---------------------------------------------------------------------

  const codeReferenceRoot = $('#event-code-reference');

  function buildCodeChips() {
    eventCodes.categories.forEach(cat => {
      const wrap = document.createElement('section');
      wrap.className = 'code-cat';
      const h3 = document.createElement('h3');
      h3.textContent = cat.title;
      wrap.appendChild(h3);
      const grid = document.createElement('div');
      grid.className = 'code-grid';
      cat.codes.forEach(c => {
        const chip = document.createElement('button');
        chip.className = 'code-chip';
        chip.dataset.code = c.code;
        chip.innerHTML =
          '<span class="code-name">' + escapeHtml(c.code) + '</span>' +
          '<span class="code-count">' + c.count + '</span>';
        chip.addEventListener('click', () => openCodeDetail(c.code));
        grid.appendChild(chip);
      });
      wrap.appendChild(grid);
      codeReferenceRoot.appendChild(wrap);
    });
    const detail = document.createElement('div');
    detail.id = 'code-detail-host';
    codeReferenceRoot.appendChild(detail);
  }

  function findCodeMeta(codeName) {
    for (const cat of eventCodes.categories) {
      for (const c of cat.codes) if (c.code === codeName) return c;
    }
    return null;
  }

  function openCodeDetail(codeName) {
    $$('.code-chip').forEach(ch => ch.classList.toggle('is-active', ch.dataset.code === codeName));
    const meta = findCodeMeta(codeName);
    const detailHost = $('#code-detail-host');
    detailHost.innerHTML = '';
    if (!meta) return;

    const card = document.createElement('div');
    card.className = 'code-detail';
    let html =
      '<h4>' + escapeHtml(meta.code) + '</h4>' +
      '<div>' + escapeHtml(meta.definition) + '</div>' +
      '<div class="code-meta">';
    if (meta.family) html += '<span><b>family</b>: <code>' + escapeHtml(meta.family) + '</code></span>';
    if (meta.stage) html += '<span><b>stage</b>: <code>' + escapeHtml(meta.stage) + '</code></span>';
    if (meta.formality) html += '<span><b>formality</b>: <code>' + escapeHtml(meta.formality) + '</code></span>';
    if (meta.dropout_side) html += '<span><b>dropout_side</b>: <code>' + escapeHtml(meta.dropout_side) + '</code></span>';
    if (meta.source) html += '<span><b>source</b>: <code>' + escapeHtml(meta.source) + '</code></span>';
    html += '<span><b>count</b>: ' + meta.count + '</span>';
    html += '</div>';
    if (meta.example) {
      html += '<div class="code-quote"><strong>Worked example:</strong> <code>' + escapeHtml(meta.example.row) + '</code>';
      if (meta.example.party) html += ' — party <code>' + escapeHtml(meta.example.party) + '</code>';
      if (meta.example.quote) html += '<blockquote>' + escapeHtml(meta.example.quote) + '</blockquote>';
      if (meta.example.note) html += '<small style="color:var(--muted)">' + escapeHtml(meta.example.note) + '</small>';
      html += '</div>';
    }
    if (meta.secondary_example) {
      html += '<div class="code-quote"><strong>Also see:</strong> <code>' + escapeHtml(meta.secondary_example.row) + '</code>';
      if (meta.secondary_example.note) html += ' — ' + escapeHtml(meta.secondary_example.note);
      html += '</div>';
    }
    html += '<button class="show-rows-btn" data-code="' + escapeHtml(meta.code) + '">Show all ' + meta.count + ' rows in the data pane →</button>';
    card.innerHTML = html;
    $('.show-rows-btn', card).addEventListener('click', () => {
      state.code = meta.code;
      codeFilter.value = meta.code;
      state.crossHighlightCol = colToIdx.event_code;
      applyFilters();
      scrollDataPaneToTop();
    });
    detailHost.appendChild(card);
    detailHost.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function scrollDataPaneToTop() {
    tableWrap.scrollTop = 0;
  }

  function scrollManualToColumn(colName) {
    // If a column chip exists, scroll to it and open its detail panel
    const chip = document.querySelector('.col-chip[data-col="' + cssEscape(colName) + '"]');
    if (chip) {
      chip.scrollIntoView({ behavior: 'smooth', block: 'center' });
      openColumnDetail(colName);
    }
  }

  // ---------------------------------------------------------------------
  // Manual prose search (M1)
  // ---------------------------------------------------------------------

  const manualSearch = $('#search-input');
  const searchStats = $('#search-stats');
  const searchClear = $('#search-clear');

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
      searchStats.textContent = '';
      return;
    }
    const re = new RegExp(escapeRegex(query), 'gi');
    const root = $('#manual-prose');
    let count = 0;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: (n) => {
        if (!n.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
        const p = n.parentNode;
        if (p.tagName === 'SCRIPT' || p.tagName === 'STYLE' || p.tagName === 'BUTTON') return NodeFilter.FILTER_REJECT;
        if (p.classList && p.classList.contains('search-hit')) return NodeFilter.FILTER_REJECT;
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
      let last = 0, m;
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
    searchStats.textContent = count + (count === 1 ? ' match' : ' matches');
    if (count > 0) {
      const first = $('mark.search-hit', root);
      if (first) first.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  let searchTimer = null;
  if (manualSearch) {
    manualSearch.addEventListener('input', () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => highlight(manualSearch.value.trim()), 180);
    });
  }
  if (searchClear) {
    searchClear.addEventListener('click', () => {
      manualSearch.value = '';
      clearHighlights();
      searchStats.textContent = '';
      manualSearch.focus();
    });
  }

  // ---------------------------------------------------------------------
  // Glossary hover cards (shared)
  // ---------------------------------------------------------------------

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
  function hideCard() { card.classList.remove('visible'); }
  document.addEventListener('mouseover', (e) => {
    const t = e.target.closest('span.term');
    if (t) { clearTimeout(hideTimer); showCard(t); }
  });
  document.addEventListener('mouseout', (e) => {
    const t = e.target.closest('span.term');
    if (t) hideTimer = setTimeout(hideCard, 120);
  });
  card.addEventListener('mouseenter', () => clearTimeout(hideTimer));
  card.addEventListener('mouseleave', hideCard);

  // ---------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }
  function escapeRegex(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }
  function cssEscape(s) {
    if (window.CSS && CSS.escape) return CSS.escape(s);
    return String(s).replace(/[^a-zA-Z0-9_-]/g, c => '\\' + c);
  }

  // ---------------------------------------------------------------------
  // Boot
  // ---------------------------------------------------------------------

  buildColumnChips();
  buildCodeChips();
  applyFilters();
})();
