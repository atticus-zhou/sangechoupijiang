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
      const promptQuality = benchmark.prompt_quality_summary || {};
      if (benchmark.status && promptQuality.status) {
        meta.appendChild(element(
          'span',
          'status-pill',
          '提示词 ' + text(promptQuality.clean_asset_prompt_count || 0) + '/'
            + text(promptQuality.asset_prompt_count || 0) + ' 资产，'
            + text(promptQuality.director_prompt_count || 0) + '/'
            + text(promptQuality.shot_prompt_count || 0) + ' 镜头'
        ));
        meta.appendChild(element(
          'span',
          'status-pill',
          '提示词问题 ' + text(promptQuality.issue_count || 0)
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
    const researchClaim = portfolio.research_claim_boundary || {};
    const qualityUpgradePath = portfolio.quality_upgrade_path || {};
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

    if (researchClaim.claim_level) {
      const researchCard = element('article', 'card claim-card research-claim-card');
      researchCard.appendChild(element('h3', '', '\u7814\u7a76\u529e\u516c\u5ba4\u8fb9\u754c'));
      addTextRow(researchCard, '\u58f0\u660e\u7b49\u7ea7', researchClaim.claim_level);
      addTextRow(researchCard, '\u5168\u81ea\u52a8\u91c7\u96c6', researchClaim.can_claim_full_automation ? '\u5df2\u9a8c\u8bc1' : '\u672a\u9a8c\u8bc1');
      addTextRow(researchCard, '\u8bc1\u636e\u4ea4\u63a5\u9879', researchClaim.evidence_handoff_count);
      const forbidden = element('ul', 'proof-list');
      (researchClaim.forbidden_public_claims || []).slice(0, 3).forEach(function (item) {
        forbidden.appendChild(element('li', '', item));
      });
      researchCard.appendChild(forbidden);
      if (researchClaim.uri) {
        const link = element('a', 'button secondary', '\u67e5\u770b\u7814\u7a76\u58f0\u660e');
        link.href = text(researchClaim.uri);
        researchCard.appendChild(link);
      }
      grid.appendChild(researchCard);
    }

    const upgrade = Array.isArray(claim.claim_upgrade_checklist) ? claim.claim_upgrade_checklist : [];
    if (upgrade.length) {
      const upgradeCard = element('article', 'card claim-card claim-upgrade-card');
      upgradeCard.appendChild(element('h3', '', '\u771f\u5b9e\u8d28\u91cf\u5347\u7ea7\u8bc1\u636e'));
      upgrade.forEach(function (item) {
        const block = element('div', 'claim-upgrade-item');
        block.appendChild(element('strong', '', text(item.title || item.id)));
        block.appendChild(element('span', '', text(item.status || '\u5f85\u8865\u9f50')));
        const evidence = Array.isArray(item.required_evidence) ? item.required_evidence.join('\u3001') : '';
        if (evidence) block.appendChild(element('p', '', '\u9700\u8981\uff1a' + evidence));
        if (item.why_it_matters) block.appendChild(element('small', '', text(item.why_it_matters)));
        upgradeCard.appendChild(block);
      });
      grid.appendChild(upgradeCard);
    }

    renderQualityUpgradePath(grid, qualityUpgradePath);
  }

  function renderQualityUpgradePath(grid, path) {
    if (!grid || !path || !path.recovery_action) return;
    const card = element('article', 'card claim-card claim-upgrade-card quality-upgrade-path-card');
    card.appendChild(element('h3', '', text(path.title || '从 demo 升级到真实生产证据')));
    card.appendChild(element('p', '', text(path.summary || '公开展示只证明结构，真实画质需要本地重新生成并质检。')));
    addTextRow(card, '图片证据', path.current_image_evidence || 'fixture_only');
    addTextRow(card, '恢复动作', path.recovery_action);
    addTextRow(card, '追溯接口', path.trace_endpoint);
    const steps = element('ol', 'quality-upgrade-steps');
    (Array.isArray(path.steps) ? path.steps : []).forEach(function (item) {
      const li = element('li', '');
      li.appendChild(element('strong', '', text(item.owner || 'operator')));
      li.appendChild(element('p', '', text(item.action || '')));
      li.appendChild(element('small', '', '证据：' + text(item.evidence || '') + '；预期：' + text(item.expected || '')));
      steps.appendChild(li);
    });
    card.appendChild(steps);
    grid.appendChild(card);
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

  function renderFastReviewRoute() {
    const portfolio = showcase.portfolio_embed || {};
    const route = Array.isArray(portfolio.fast_review_route) ? portfolio.fast_review_route : [];
    const count = document.getElementById('fast-review-count');
    const list = document.getElementById('fast-review-route');
    if (!count || !list) return;
    count.textContent = route.length + ' 步';
    route.forEach(function (item) {
      const row = element('li', 'fast-review-item');
      row.appendChild(element('span', 'fast-review-order', item.order));
      const copy = element('div', 'fast-review-copy');
      copy.appendChild(element('h3', '', item.title));
      addTextRow(copy, '访客动作', item.viewer_action);
      addTextRow(copy, '证明', item.proof);
      row.appendChild(copy);
      if (item.next_anchor) {
        const link = element('a', 'button secondary', '跳到对应部分');
        link.href = text(item.next_anchor);
        row.appendChild(link);
      }
      list.appendChild(row);
    });
  }

  function renderDownloadCatalog() {
    const catalog = Array.isArray(showcase.download_catalog) ? showcase.download_catalog : [];
    const count = document.getElementById('catalog-count');
    const grid = document.getElementById('download-catalog');
    if (!count || !grid) return;
    count.textContent = catalog.length + ' 个文件';
    catalog.forEach(function (item) {
      const card = element('article', 'catalog-card');
      const head = element('div', 'catalog-head');
      head.appendChild(element('h3', '', item.title || item.local_uri));
      head.appendChild(element('span', 'status-pill', item.type || 'artifact'));
      card.appendChild(head);
      addTextRow(card, '文件', item.local_uri);
      addTextRow(card, '来源', item.office_name || item.office_id);
      addTextRow(card, '大小', item.bytes ? Math.ceil(Number(item.bytes) / 1024) + ' KB' : '');
      addTextRow(card, '证明', item.proves || item.reader_guidance || item.look_for);
      if (item.sha256) {
        const hash = element('code', 'hash-code', item.sha256);
        card.appendChild(hash);
      }
      card.appendChild(downloadButton({ uri: item.local_uri }, '下载复核'));
      grid.appendChild(card);
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

  function renderShotContract() {
    const portfolio = showcase.portfolio_embed || {};
    const contract = portfolio.shot_contract || {};
    const fields = Array.isArray(contract.required_fields) ? contract.required_fields : [];
    const count = document.getElementById('shot-contract-count');
    const target = document.getElementById('shot-contract');
    if (!count || !target || !fields.length) return;
    count.textContent = fields.length + ' 项硬门禁';

    const intro = element('article', 'card shot-contract-summary');
    intro.appendChild(element('h3', '', contract.title || '镜头合同可执行性'));
    intro.appendChild(element('p', '', contract.summary || '每个镜头必须保留机器可读引用和导演执行参数。'));
    addTextRow(intro, 'Manifest', contract.manifest_uri);
    addTextRow(intro, '发布门禁', contract.release_gate);
    addTextRow(intro, '失败策略', contract.failure_policy);
    target.appendChild(intro);

    fields.forEach(function (item) {
      const card = element('article', 'card shot-contract-card');
      card.appendChild(element('span', 'status-pill', item.label || item.field));
      card.appendChild(element('h3', '', item.field));
      addTextRow(card, '必须包含', (item.must_include || []).join(' / '));
      addTextRow(card, '证明', item.proves);
      target.appendChild(card);
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

  function renderFirstRunPaths() {
    const portfolio = showcase.portfolio_embed || {};
    const paths = Array.isArray(portfolio.first_run_paths) ? portfolio.first_run_paths : [];
    const grid = document.getElementById('first-run-paths');
    if (!grid || !paths.length) return;
    paths.forEach(function (item) {
      const card = element('article', 'card first-run-card');
      const head = element('div', 'first-run-card-head');
      head.appendChild(element('h3', '', item.title || item.id));
      head.appendChild(element('span', 'status-pill', item.requires_api_key ? '需要自己的 API Key' : '不需要 API Key'));
      card.appendChild(head);
      card.appendChild(element('p', '', item.for_user || ''));
      addTextRow(card, '先做什么', item.start_here);
      const steps = element('ol', 'compact-steps');
      (item.do_first || []).forEach(function (step) {
        steps.appendChild(element('li', '', step));
      });
      card.appendChild(steps);
      card.appendChild(element('code', '', item.verification || ''));
      addTextRow(card, '通过信号', item.success_signal);
      grid.appendChild(card);
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

  function renderPostRunValidation() {
    const portfolio = showcase.portfolio_embed || {};
    const checklist = Array.isArray(portfolio.post_run_validation) ? portfolio.post_run_validation : [];
    const count = document.getElementById('post-run-count');
    const list = document.getElementById('post-run-validation');
    if (!count || !list) return;
    count.textContent = checklist.length + ' 步';
    checklist.forEach(function (item) {
      const row = element('li', 'repro-item post-run-item');
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

  function renderOfficeExtensionStory() {
    const portfolio = showcase.portfolio_embed || {};
    const story = portfolio.office_extension_story || {};
    const target = document.getElementById('office-extension-story');
    const count = document.getElementById('extension-count');
    if (!target || !count || !story.starter_checklist) return;
    const checklist = Array.isArray(story.starter_checklist) ? story.starter_checklist : [];
    count.textContent = text(story.starter_item_count || checklist.length) + ' 项检查';
    const intro = element('article', 'card extension-summary-card');
    intro.appendChild(element('h3', '', story.title || '新办公室扩展路径'));
    intro.appendChild(element('p', '', story.summary || '未来办公室必须先证明隔离、演示、交付物、失败恢复和发布门禁，再进入公开展示。'));
    addTextRow(intro, '检查清单', story.starter_checklist_doc);
    addTextRow(intro, '公开边界', story.public_boundary);
    target.appendChild(intro);

    const grid = element('div', 'extension-check-grid');
    checklist.forEach(function (item) {
      const card = element('article', 'card extension-check-card');
      card.appendChild(element('span', 'status-pill', text(item.phase || 'phase')));
      card.appendChild(element('h3', '', text(item.order || '') + '. ' + text(item.id || 'check')));
      card.appendChild(element('p', '', item.question));
      addTextRow(card, '验收证据', item.evidence);
      grid.appendChild(card);
    });
    target.appendChild(grid);

    const candidates = Array.isArray(story.future_office_candidates) ? story.future_office_candidates : [];
    if (candidates.length) {
      const candidateGrid = element('div', 'extension-check-grid');
      candidates.forEach(function (candidate) {
        const card = element('article', 'card extension-check-card');
        card.appendChild(element('span', 'status-pill', '未来候选'));
        card.appendChild(element('h3', '', candidate.name || candidate.id));
        card.appendChild(element('p', '', candidate.user_job));
        addTextRow(card, '暂不开放原因', candidate.not_ready_reason);
        addTextRow(card, '上线前证据', (candidate.required_before_public || []).join(' / '));
        candidateGrid.appendChild(card);
      });
      target.appendChild(candidateGrid);
    }

    const backlog = Array.isArray(story.future_platform_backlog) ? story.future_platform_backlog : [];
    if (backlog.length) {
      const backlogCard = element('article', 'card extension-verifier-card');
      backlogCard.appendChild(element('h3', '', '未来办公室必须补的平台证据'));
      const list = element('ul', 'proof-list');
      backlog.forEach(function (item) {
        const li = element('li', '');
        li.appendChild(element('strong', '', item.id || 'backlog'));
        li.appendChild(document.createTextNode('：' + text(item.description || item.evidence_required || '')));
        list.appendChild(li);
      });
      backlogCard.appendChild(list);
      target.appendChild(backlogCard);
    }

    const verifierCard = element('article', 'card extension-verifier-card');
    verifierCard.appendChild(element('h3', '', '发布验证命令'));
    const list = element('ul', 'proof-list');
    (story.required_verifiers || []).forEach(function (command) {
      const li = element('li', '');
      li.appendChild(element('code', '', command));
      list.appendChild(li);
    });
    verifierCard.appendChild(list);
    target.appendChild(verifierCard);
  }

  function renderPortfolioIntegration() {
    const portfolio = showcase.portfolio_embed || {};
    const integration = portfolio.portfolio_integration || {};
    const target = document.getElementById('portfolio-integration');
    const count = document.getElementById('integration-count');
    if (!target || !count || !integration.static_export) return;
    const options = Array.isArray(integration.integration_options) ? integration.integration_options : [];
    count.textContent = options.length + ' 种接法';
    target.appendChild(element('p', 'lead compact', integration.summary || '公开展示只接入静态包，不接入真实生产接口。'));
    const exportCard = element('article', 'card integration-export-card');
    exportCard.appendChild(element('h3', '', integration.title || '个人网站接入方式'));
    addTextRow(exportCard, '生成命令', integration.static_export.command);
    addTextRow(exportCard, '验证命令', integration.static_export.verify_command);
    addTextRow(exportCard, '源目录', integration.static_export.source_dir);
    addTextRow(exportCard, '入口文件', integration.static_export.entrypoint);
    target.appendChild(exportCard);
    const optionGrid = element('div', 'card-grid two integration-options');
    options.forEach(function (item) {
      const card = element('article', 'card');
      card.appendChild(element('h3', '', item.label || item.id));
      addTextRow(card, '目标', item.target);
      addTextRow(card, '复制', text(item.copy_from || '') + ' -> ' + text(item.copy_to || ''));
      addTextRow(card, '入口', item.public_url_example);
      card.appendChild(element('p', '', item.best_for || ''));
      optionGrid.appendChild(card);
    });
    target.appendChild(optionGrid);
    const forbidden = element('article', 'card integration-forbidden');
    forbidden.appendChild(element('h3', '', '禁止复制到公开站点'));
    const list = element('ul', 'proof-list');
    (integration.must_not_include || []).forEach(function (item) {
      list.appendChild(element('li', '', item));
    });
    forbidden.appendChild(list);
    target.appendChild(forbidden);
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
  renderFastReviewRoute();
  renderOffices();
  renderReadingGuide();
  renderDownloadCatalog();
  renderDownstreamQuickStart();
  renderShotContract();
  renderInterviewScript();
  renderFirstRunPaths();
  renderReproducibilityChecklist();
  renderPostRunValidation();
  renderOfficeExtensionStory();
  renderPortfolioIntegration();
  renderSafety();
})();
