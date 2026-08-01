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
      if (benchmark.status && Array.isArray(promptQuality.checks) && promptQuality.checks.length) {
        const checks = element('div', 'prompt-gate-checks');
        checks.appendChild(element('strong', '', '提示词门禁'));
        promptQuality.checks.slice(0, 5).forEach(function (item) {
          checks.appendChild(element('span', '', text(item)));
        });
        card.appendChild(checks);
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
      if (demo.office_id === 'comic_production') {
        const inventoryImageSummary = {
          total_images: inventory.total_images,
          usable_images: inventory.usable_images,
          waste_or_rework_rate: inventory.waste_or_rework_rate,
        };
        const imageSummary = Number(inventoryImageSummary.total_images || 0) > 0
          ? inventoryImageSummary
          : (benchmark.image_quality_summary || {});
        if (imageSummary.total_images !== undefined) {
          meta.appendChild(element(
            'span',
            'status-pill',
            '图片 ' + text(imageSummary.usable_images || 0) + '/'
              + text(imageSummary.total_images || 0) + ' 可用'
          ));
          meta.appendChild(element(
            'span',
            'status-pill',
            '返工率 '
              + text(Math.round(Number(imageSummary.waste_or_rework_rate || 0) * 100)) + '%'
          ));
        }
      }
      card.appendChild(meta);

      const proof = element('ul', 'proof-list');
      (demo.proof_points || []).slice(0, 4).forEach(function (item) {
        proof.appendChild(element('li', '', item));
      });
      card.appendChild(proof);
      if (demo.office_id === 'comic_production') {
        renderImageReworkSummary(card, benchmark.image_quality_summary || {});
      }

      const downloads = element('div', 'download-row');
      (demo.downloads || []).forEach(function (item) {
        downloads.appendChild(downloadButton(item, item.title));
      });
      card.appendChild(downloads);
      grid.appendChild(card);
    });
  }

  function renderImageReworkSummary(card, imageQuality) {
    if (!card || !imageQuality || !Array.isArray(imageQuality.rework_action_summary)) return;
    const actions = imageQuality.rework_action_summary.filter(function (item) {
      return item && typeof item === 'object' && (item.action || item.label);
    });
    if (!actions.length) return;
    const panel = element('div', 'image-rework-summary');
    panel.appendChild(element('strong', '', '\u56fe\u7247\u8fd4\u5de5\u52a8\u4f5c'));
    actions.slice(0, 3).forEach(function (item) {
      const row = element('div', 'image-rework-row');
      row.appendChild(element(
        'span',
        'status-pill bounded',
        text(item.next_button_label || item.action || item.label)
      ));
      row.appendChild(element(
        'small',
        '',
        text(item.department || '\u5f85\u5206\u914d') + ' · '
          + text(item.count || 0) + ' \u5f20'
      ));
      const ids = Array.isArray(item.image_ids) ? item.image_ids.slice(0, 3) : [];
      if (ids.length) {
        row.appendChild(element('code', 'hash-code', ids.map(text).join(', ')));
      }
      panel.appendChild(row);
    });
    card.appendChild(panel);
  }

  function renderClaimBoundary() {
    const portfolio = showcase.portfolio_embed || {};
    const claim = portfolio.real_production_claim || {};
    const promotionGate = claim.real_quality_promotion_gate || {};
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

      const handoffItems = Array.isArray(researchClaim.evidence_handoff)
        ? researchClaim.evidence_handoff
        : [];
      if (handoffItems.length) {
        const handoffCard = element('article', 'card claim-card research-evidence-handoff-card');
        handoffCard.appendChild(element('h3', '', '\u5f85\u8865\u8bc1\u636e\u4ea4\u63a5\u8868'));
        handoffItems.slice(0, 3).forEach(function (item) {
          const block = element('div', 'research-evidence-handoff-item');
          block.appendChild(element('strong', '', text(item.title || item.id || '\u8865\u8bc1\u9879')));
          block.appendChild(element('small', '', text(item.owner || '\u4eba\u673a\u534f\u4f5c') + ' · ' + text(item.status || '\u5f85\u8865\u9f50')));
          if (item.target_evidence) {
            block.appendChild(element('p', '', text(item.target_evidence)));
          }
          if (item.why_needed) {
            block.appendChild(element('small', '', '\u4e3a\u4ec0\u4e48\u8981\u8865\uff1a' + text(item.why_needed)));
          }
          if (Array.isArray(item.upgrades) && item.upgrades.length) {
            block.appendChild(element('code', 'hash-code', '\u8865\u5b8c\u5f71\u54cd\uff1a' + item.upgrades.map(text).join(' / ')));
          }
          handoffCard.appendChild(block);
        });
        grid.appendChild(handoffCard);
      }

      const playbook = researchClaim.evidence_capture_playbook || {};
      if (playbook.status) {
        const playbookCard = element('article', 'card claim-card research-capture-playbook-card');
        playbookCard.appendChild(element('h3', '', '\u4eba\u5de5\u8865\u8bc1\u6d41\u7a0b'));
        addTextRow(playbookCard, '\u72b6\u6001', playbook.status);
        addTextRow(playbookCard, '\u6b65\u9aa4\u6570', playbook.step_count);
        addTextRow(playbookCard, '\u6587\u4ef6\u547d\u540d', playbook.file_naming_rule);
        const commandList = element('ul', 'proof-list research-capture-commands');
        (playbook.after_capture_commands || []).slice(0, 3).forEach(function (command) {
          commandList.appendChild(element('li', '', command));
        });
        if (commandList.children.length) {
          playbookCard.appendChild(element('p', 'mini-label', '\u8865\u8bc1\u540e\u590d\u6838\u547d\u4ee4'));
          playbookCard.appendChild(commandList);
        }
        const steps = element('ol', 'research-capture-steps');
        [
          '\u4eba\u53ea\u5728\u81ea\u5df1\u7684\u6d4f\u89c8\u5668\u5b8c\u6210\u7b2c\u4e09\u65b9\u5e73\u53f0\u767b\u5f55\u3002',
          '\u6309\u4ea4\u63a5\u9879\u622a\u53d6\u4ef7\u683c\u5e26\u3001\u7ade\u54c1\u6392\u884c\u548c\u8bc4\u8bba\u75db\u70b9\u3002',
          '\u7814\u7a76\u529e\u516c\u5ba4\u628a\u622a\u56fe\u3001\u6765\u6e90\u8bf4\u660e\u548c\u5f85\u6838\u9a8c\u9879\u91cd\u65b0\u7ec4\u88c5\u8fdb\u62a5\u544a\u3002',
        ].forEach(function (step) {
          steps.appendChild(element('li', '', step));
        });
        playbookCard.appendChild(steps);
        grid.appendChild(playbookCard);
      }
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

    if (promotionGate.status || Array.isArray(promotionGate.checks)) {
      const gateCard = element('article', 'card claim-card claim-upgrade-card public-claim-promotion-gate');
      gateCard.appendChild(element('h3', '', '\u771f\u5b9e\u751f\u4ea7\u8d28\u91cf\u95e8\u7981'));
      addTextRow(gateCard, '\u72b6\u6001', promotionGate.status || '\u5f85\u8865\u9f50');
      addTextRow(gateCard, '\u53ef\u5347\u7ea7', promotionGate.ready ? '\u662f' : '\u5426');
      addTextRow(gateCard, '\u963b\u585e\u9879', promotionGate.blocking_count || 0);
      if (promotionGate.next_action) {
        gateCard.appendChild(element('p', '', text(promotionGate.next_action)));
      }
      const checks = element('ul', 'proof-list');
      (promotionGate.checks || []).forEach(function (item) {
        const statusText = item.passed ? '\u5df2\u901a\u8fc7' : '\u5f85\u8865\u9f50';
        checks.appendChild(element('li', '', statusText + '\uff1a' + text(item.label || item.id || 'check')));
      });
      if (checks.children.length) gateCard.appendChild(checks);
      grid.appendChild(gateCard);
    }

    renderClaimUpgradeRecovery(grid, claim.claim_upgrade_recovery || {});
    renderQualityUpgradePath(grid, qualityUpgradePath);
  }

  function renderClaimUpgradeRecovery(grid, recovery) {
    if (!grid || !recovery || !recovery.recovery_action) return;
    const card = element('article', 'card claim-card claim-upgrade-card claim-recovery-card');
    card.appendChild(element('h3', '', '\u5931\u8d25\u540e\u5982\u4f55\u6062\u590d'));
    card.appendChild(element('p', '', text(recovery.reason || '\u5f53\u524d\u6837\u4f8b\u53ea\u80fd\u8bc1\u660e\u7ed3\u6784\uff0c\u771f\u5b9e\u753b\u8d28\u9700\u8981\u91cd\u65b0\u751f\u56fe\u5e76\u8d28\u68c0\u3002')));
    addTextRow(card, '\u6062\u590d\u52a8\u4f5c', recovery.recovery_action);
    addTextRow(card, '\u6062\u590d\u63a5\u53e3', recovery.recovery_endpoint);
    addTextRow(card, '\u4fdd\u7559', Array.isArray(recovery.preserves) ? recovery.preserves.join('\u3001') : '');
    addTextRow(card, '\u91cd\u5efa', Array.isArray(recovery.rebuilds) ? recovery.rebuilds.join('\u3001') : '');
    if (recovery.next_action) {
      card.appendChild(element('p', 'claim-recovery-next', text(recovery.next_action)));
    }
    const steps = element('ol', 'quality-upgrade-steps claim-recovery-steps');
    (Array.isArray(recovery.steps) ? recovery.steps : []).forEach(function (item) {
      const li = element('li', '');
      li.appendChild(element('strong', '', text(item.owner || 'operator')));
      li.appendChild(element('p', '', text(item.action || '')));
      li.appendChild(element('small', '', '\u9a8c\u6536\uff1a' + text(item.evidence || '') + '\uff1b\u7ed3\u679c\uff1a' + text(item.expected || '')));
      steps.appendChild(li);
    });
    card.appendChild(steps);
    grid.appendChild(card);
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

  function renderAssetProductionSpec() {
    const portfolio = showcase.portfolio_embed || {};
    const spec = portfolio.asset_image_production_spec || {};
    const target = document.getElementById('asset-production-spec');
    if (!target || !spec.asset_types) return;

    const intro = element('article', 'card asset-spec-summary');
    intro.appendChild(element('h3', '', spec.title || 'Asset image production spec'));
    intro.appendChild(element('p', '', spec.summary || ''));
    (spec.why_it_matters || []).forEach(function (item) {
      intro.appendChild(element('small', '', item));
    });
    addTextRow(intro, 'Handoff rule', spec.handoff_rule);
    addTextRow(intro, 'Release gate', spec.release_gate);
    target.appendChild(intro);

    (spec.asset_types || []).forEach(function (item) {
      const card = element('article', 'card asset-spec-card');
      const head = element('div', 'asset-matrix-head');
      head.appendChild(element('h3', '', item.label || item.asset_type));
      head.appendChild(element('span', 'status-pill', item.background_policy || 'background_policy'));
      card.appendChild(head);
      addTextRow(card, 'Required images', (item.required_images || []).join(' / '));
      addTextRow(card, 'Should look like', item.should_look_like);
      const forbidden = element('ul', 'asset-ref-list');
      (item.must_not_do || []).forEach(function (rule) {
        forbidden.appendChild(element('li', '', rule));
      });
      card.appendChild(forbidden);
      addTextRow(card, 'Review focus', (item.review_focus || []).join(' / '));
      target.appendChild(card);
    });
  }

  function renderAssetRequirementMatrix() {
    const portfolio = showcase.portfolio_embed || {};
    const matrix = portfolio.asset_requirement_matrix || {};
    const items = Array.isArray(matrix.items) ? matrix.items : [];
    const count = document.getElementById('asset-matrix-count');
    const target = document.getElementById('asset-requirement-matrix');
    if (!count || !target) return;
    count.textContent = text(matrix.ready_assets || 0) + '/' + text(matrix.total_assets || items.length) + ' ready';
    if (!items.length) {
      target.appendChild(element('p', 'lead compact', matrix.summary || 'No asset requirement matrix is available yet.'));
      return;
    }
    const intro = element('article', 'card asset-matrix-summary');
    intro.appendChild(element('h3', '', matrix.title || 'Asset image requirement matrix'));
    intro.appendChild(element('p', '', matrix.summary || ''));
    addTextRow(intro, 'Manifest', matrix.manifest_uri);
    addTextRow(intro, 'Release gate', matrix.release_gate);
    addTextRow(intro, 'Missing', text(matrix.missing_required_images || 0));
    target.appendChild(intro);

    items.forEach(function (item) {
      const card = element('article', 'card asset-matrix-card');
      const head = element('div', 'asset-matrix-head');
      head.appendChild(element('h3', '', item.name || item.asset_id));
      head.appendChild(element('span', 'status-pill', item.asset_type_label || item.asset_type));
      head.appendChild(element('span', 'status-pill', item.handoff_ready ? 'ready' : 'needs review'));
      card.appendChild(head);
      addTextRow(card, 'Required', (item.required_image_kinds || []).join(' / '));
      addTextRow(card, 'Available', (item.available_image_kinds || []).join(' / '));
      if ((item.missing_image_kinds || []).length) {
        addTextRow(card, 'Missing', item.missing_image_kinds.join(' / '));
      }
      card.appendChild(element(
        'p',
        'asset-background-rule',
        item.clean_background_required
          ? '人物/道具基础资产：干净白底，不讲故事。'
          : item.scene_spatial_required
            ? '场景基础资产：空场景广角和俯视空间关系。'
            : ''
      ));
      const refs = element('ul', 'asset-ref-list');
      (item.image_refs || []).forEach(function (ref) {
        const li = element('li', '');
        li.appendChild(element('strong', '', ref.label || ref.image_kind));
        li.appendChild(document.createTextNode(' · ' + text(ref.file || ref.image_id || 'missing')));
        if (ref.purpose) {
          li.appendChild(element('small', '', ref.purpose));
        }
        refs.appendChild(li);
      });
      card.appendChild(refs);
      target.appendChild(card);
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

    const launchMatrix = portfolio.office_launch_matrix || {};
    const launchOffices = Array.isArray(launchMatrix.offices) ? launchMatrix.offices : [];
    if (launchOffices.length) {
      const matrixCard = element('article', 'card extension-verifier-card launch-matrix-card');
      matrixCard.appendChild(element('h3', '', '办公室公开状态'));
      matrixCard.appendChild(element('p', '', launchMatrix.why_it_matters || '外部访客需要知道哪个办公室能展示、哪个能主推、哪个只是兼容入口。'));
      const launchGrid = element('div', 'launch-matrix-grid');
      launchOffices.forEach(function (office) {
        const item = element('div', 'launch-matrix-item');
        item.appendChild(element('span', 'status-pill', office.visitor_label || office.role || 'office'));
        item.appendChild(element('strong', '', office.office_name || office.office_id));
        item.appendChild(element('p', '', office.visitor_meaning || office.recommended_action || ''));
        const blocked = Array.isArray(office.blocked_by) && office.blocked_by.length
          ? office.blocked_by.join(' / ')
          : '无';
        addTextRow(item, '阻塞项', blocked);
        launchGrid.appendChild(item);
      });
      matrixCard.appendChild(launchGrid);
      target.appendChild(matrixCard);
    }

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
  renderAssetProductionSpec();
  renderAssetRequirementMatrix();
  renderShotContract();
  renderInterviewScript();
  renderFirstRunPaths();
  renderReproducibilityChecklist();
  renderPostRunValidation();
  renderOfficeExtensionStory();
  renderPortfolioIntegration();
  renderSafety();
})();
