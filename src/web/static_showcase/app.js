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
      const benchmark = demo.quality_benchmark || {};
      if (benchmark.status) {
        meta.appendChild(element('span', 'status-pill', '结构质量 ' + text(benchmark.package_quality_score || 0) + '/100'));
        meta.appendChild(element(
          'span',
          'status-pill',
          benchmark.production_quality_verified ? '真实画质已验证' : '未宣称真实画质'
        ));
      }
      const inventory = (showcase.portfolio_embed || {}).handoff_inventory || {};
      if (demo.office_id === 'comic_production' && inventory.uri) {
        meta.appendChild(element(
          'span',
          'status-pill',
          '交付盘点 ' + text(inventory.manifest_count || 0) + ' 份'
        ));
        meta.appendChild(element(
          'span',
          'status-pill',
          '真实通过 ' + text(inventory.production_verified_count || 0) + ' 份'
        ));
      }
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

  function renderClaimBoundary() {
    const portfolio = showcase.portfolio_embed || {};
    const claim = portfolio.real_production_claim || {};
    const grid = document.getElementById('claim-grid');
    const level = document.getElementById('claim-level');
    if (!grid || !level) return;
    level.textContent = text(claim.claim_level || 'demo_structure_only');

    function claimCard(title, items, fallback) {
      const card = element('article', 'card claim-card');
      card.appendChild(element('h3', '', title));
      const list = element('ul', 'proof-list');
      const values = Array.isArray(items) && items.length ? items : [fallback];
      values.forEach(function (item) {
        list.appendChild(element('li', '', item));
      });
      card.appendChild(list);
      return card;
    }

    grid.appendChild(claimCard('可以公开说明', claim.allowed_public_claims, '固定样例验证了结构、下载和证据链。'));
    grid.appendChild(claimCard('不能公开宣称', claim.forbidden_public_claims, '不能宣称真实模型画质已验证。'));

    const status = element('article', 'card claim-card');
    status.appendChild(element('h3', '', '下一步'));
    addTextRow(status, '质量声明', claim.quality_claim);
    addTextRow(status, '下游状态', claim.downstream_status);
    addTextRow(status, '真实画质', claim.can_claim_real_quality ? '已验证' : '未验证');
    const next = element('p', '', text(claim.next_action || '需要真实模型跑通后再更新生产质量声明。'));
    status.appendChild(next);
    if (claim.uri) {
      const link = element('a', 'button secondary', '查看声明数据');
      link.href = text(claim.uri);
      status.appendChild(link);
    }
    grid.appendChild(status);
  }

  function renderReleaseBadge() {
    const portfolio = showcase.portfolio_embed || {};
    const badge = portfolio.release_badge || {};
    const target = document.getElementById('release-badge');
    if (!target || !badge.status) return;
    const head = element('div', 'release-badge-head');
    head.appendChild(element('strong', '', badge.label || '可公开展示'));
    head.appendChild(element('span', '', text(badge.mode || 'demo_only') + ' · ' + text(badge.status)));
    target.appendChild(head);
    target.appendChild(element('p', '', badge.summary || '固定样例可以公开展示，真实生产仍需本地配置自己的模型 Key。'));
    const signals = element('div', 'release-badge-signals');
    (badge.signals || []).forEach(function (item) {
      signals.appendChild(element(
        'span',
        'status-pill ' + text(item.status || 'passed'),
        text(item.label) + '：' + text(item.value)
      ));
    });
    target.appendChild(signals);
    addTextRow(target, '总门禁', badge.primary_gate);
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

  function renderDownstreamQuickStart() {
    const portfolio = showcase.portfolio_embed || {};
    const steps = Array.isArray(portfolio.downstream_quick_start) ? portfolio.downstream_quick_start : [];
    const count = document.getElementById('downstream-count');
    const list = document.getElementById('downstream-quick-start');
    if (!count || !list) return;
    count.textContent = steps.length + ' 步';
    steps.forEach(function (item) {
      const row = element('li', 'script-item');
      row.appendChild(element('span', 'script-order', item.step));
      const copy = element('div', 'script-copy');
      copy.appendChild(element('h3', '', item.title));
      addTextRow(copy, '负责人', item.owner);
      addTextRow(copy, '输入', (item.input_refs || []).join(' / '));
      addTextRow(copy, '动作', item.action);
      addTextRow(copy, '产出', item.output);
      addTextRow(copy, '验收', item.acceptance);
      row.appendChild(copy);
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

  function renderReproducibilityChecklist() {
    const portfolio = showcase.portfolio_embed || {};
    const checklist = Array.isArray(portfolio.reproducibility_checklist) ? portfolio.reproducibility_checklist : [];
    document.getElementById('repro-count').textContent = checklist.length + ' 条命令';
    const list = document.getElementById('repro-checklist');
    checklist.forEach(function (item) {
      const row = element('li', 'repro-item');
      row.appendChild(element('span', 'repro-order', item.order));
      const copy = element('div', 'repro-copy');
      copy.appendChild(element('h3', '', item.title));
      copy.appendChild(element('code', '', item.command));
      addTextRow(copy, '通过时', item.expected);
      addTextRow(copy, '失败时', item.if_fails);
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
  renderReleaseBadge();
  renderClaimBoundary();
  renderOffices();
  renderReadingGuide();
  renderDownstreamQuickStart();
  renderInterviewScript();
  renderReproducibilityChecklist();
  renderSafety();
})();
