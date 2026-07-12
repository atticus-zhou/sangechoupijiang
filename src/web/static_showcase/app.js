(function () {
  'use strict';

  const showcase = window.__PUBLIC_SHOWCASE__;
  if (!showcase) {
    document.body.insertAdjacentHTML('afterbegin', '<p class="load-error">公开样例数据没有随页面导出，请重新运行导出命令。</p>');
    return;
  }

  function text(value) {
    return value == null ? '' : String(value);
  }

  function element(tag, className, content) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (content !== undefined) node.textContent = text(content);
    return node;
  }

  function addTextRow(parent, label, value) {
    if (!value) return;
    const row = element('p');
    const strong = element('strong', '', label + '：');
    row.append(strong, document.createTextNode(text(value)));
    parent.appendChild(row);
  }

  function downloadButton(item, label) {
    const link = element('a', 'button secondary', label || '下载样例');
    link.href = text(item.uri);
    link.setAttribute('download', '');
    return link;
  }

  function renderAudiencePaths() {
    const paths = Array.isArray(showcase.audience_paths) ? showcase.audience_paths : [];
    document.getElementById('audience-count').textContent = paths.length + ' 类访客';
    const grid = document.getElementById('audience-grid');
    paths.forEach(function (path, index) {
      const card = element('article', 'card');
      card.appendChild(element('span', 'number-label', String(index + 1).padStart(2, '0')));
      card.appendChild(element('h3', '', path.label));
      card.appendChild(element('p', '', path.takeaway));
      const list = element('ol', 'steps');
      (path.steps || []).forEach(function (step) {
        list.appendChild(element('li', '', step));
      });
      card.appendChild(list);
      grid.appendChild(card);
    });
  }

  function renderOffices() {
    const demos = Array.isArray(showcase.featured_demos) ? showcase.featured_demos : [];
    document.getElementById('office-count').textContent = demos.length + ' 个固定样例';
    const grid = document.getElementById('office-grid');
    demos.forEach(function (demo) {
      const card = element('article', 'office-card');
      card.id = 'office-' + text(demo.office_id);
      card.appendChild(element('p', 'section-kicker', demo.office_name));
      card.appendChild(element('h3', '', demo.title));
      card.appendChild(element('p', '', demo.summary));

      const meta = element('div', 'office-meta');
      meta.appendChild(element('span', 'status-pill', '无 Key 固定样例'));
      meta.appendChild(element('span', 'status-pill', (demo.downloads || []).length + ' 个下载物'));
      card.appendChild(meta);

      const proof = element('ul', 'proof-list');
      (demo.proof_points || []).slice(0, 4).forEach(function (item) {
        proof.appendChild(element('li', '', item));
      });
      card.appendChild(proof);

      const downloads = element('div', 'download-row');
      (demo.downloads || []).forEach(function (item) {
        downloads.appendChild(downloadButton(item, item.title));
      });
      card.appendChild(downloads);
      grid.appendChild(card);
    });
  }

  function renderReadingGuide() {
    const portfolio = showcase.portfolio_embed || {};
    const guide = Array.isArray(portfolio.deliverable_reading_guide) ? portfolio.deliverable_reading_guide : [];
    document.getElementById('deliverable-count').textContent = guide.length + ' 份交付物';
    const list = document.getElementById('reading-guide');
    guide.forEach(function (item) {
      const row = element('li', 'reading-item');
      row.appendChild(element('span', 'reading-order', item.order));
      const copy = element('div', 'reading-copy');
      copy.appendChild(element('h3', '', item.title));
      addTextRow(copy, '重点检查', item.look_for);
      addTextRow(copy, '它能证明', item.proves);
      row.append(copy, downloadButton(item, '下载文件'));
      list.appendChild(row);
    });
  }

  function renderInterviewScript() {
    const portfolio = showcase.portfolio_embed || {};
    const script = Array.isArray(portfolio.interview_demo_script) ? portfolio.interview_demo_script : [];
    document.getElementById('script-count').textContent = script.length + ' 步';
    const list = document.getElementById('interview-script');
    script.forEach(function (item) {
      const row = element('li', 'script-item');
      row.appendChild(element('span', 'script-order', item.order));
      const copy = element('div', 'script-copy');
      copy.appendChild(element('h3', '', item.title));
      addTextRow(copy, '访客操作', item.visitor_action);
      addTextRow(copy, '产品反馈', item.product_response);
      addTextRow(copy, '证明', item.proof);
      addTextRow(copy, '边界', item.boundary);
      row.appendChild(copy);
      list.appendChild(row);
    });
  }

  function renderSafety() {
    const list = document.getElementById('safety-list');
    (showcase.safety_boundaries || []).forEach(function (boundary) {
      list.appendChild(element('li', '', boundary));
    });
  }

  document.getElementById('showcase-tagline').textContent = text(showcase.tagline);
  document.getElementById('product-positioning').textContent = text(showcase.positioning);
  const repository = (showcase.portfolio_embed || {}).repository_url;
  if (repository) document.getElementById('repository-link').href = repository;

  renderAudiencePaths();
  renderOffices();
  renderReadingGuide();
  renderInterviewScript();
  renderSafety();
})();
