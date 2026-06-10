/** 三个臭皮匠 · Web UI */

async function apiJson(url, options = {}) {
    const response = await fetch(url, options);
    let payload = {};
    try {
        payload = await response.json();
    } catch (e) {
        payload = {};
    }
    if (!response.ok || payload.detail) {
        const detail = payload.detail || response.statusText || '请求失败';
        const message = Array.isArray(detail)
            ? detail.join('；')
            : (typeof detail === 'object' ? JSON.stringify(detail) : String(detail));
        throw new Error(message);
    }
    return payload;
}

const API = {
    get: async (url) => apiJson(url),
    post: async (url, data) => apiJson(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }),
    put: async (url, data) => apiJson(url, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }),
    del: async (url) => apiJson(url, { method: 'DELETE' }),
};

// ============================================================
// Navigation
// ============================================================
const OFFICE_LABELS = {
    research: '研究办公室',
    comic: 'AI漫剧办公室',
};

OFFICE_LABELS.comic_production = 'AI漫剧制片办公室';
const WORKBENCH_PAGES = new Set(['research', 'comic', 'comic_production']);

let ACTIVE_OFFICE_ID = readStoredOfficeId();
let MODEL_OFFICE_ID = ACTIVE_OFFICE_ID;

function navigate(page) {
    page = normalizeNavigationTarget(page);
    document.querySelectorAll('.page').forEach(p => p.style.display = 'none');
    const targetPageId = page === 'comic_production' ? 'comic' : page;
    const targetPage = document.getElementById('page-' + targetPageId);
    if (!targetPage) return;
    targetPage.style.display = (page === 'task') ? 'flex' : 'block';
    document.body.classList.toggle('hall-mode', page === 'offices');
    if (page === 'research') setActiveOfficeContext('research', '研究办公室');
    if (page === 'comic') setActiveOfficeContext('comic', 'AI漫剧办公室');
    
    if (page === 'comic_production') setActiveOfficeContext('comic_production', OFFICE_LABELS.comic_production);

    // Fix aside navigation active state
    document.querySelectorAll('.sidebar nav a').forEach(a => a.classList.remove('active'));
    const navPage = WORKBENCH_PAGES.has(page) ? 'workbench' : page;
    const navItem = document.querySelector(`[data-page="${navPage}"]`);
    if (navItem) navItem.classList.add('active');
    
    if (page === 'models') loadModels();
    else if (page === 'tools') loadTools();
    else if (page === 'skills') loadSkills();
    else if (page === 'research') loadResearchOffice();
    else if (page === 'comic' || page === 'comic_production') loadComicOffice();
    else if (page === 'prompts') loadPrompts();
    else if (page === 'history') loadHistory();
}

function navigateActiveWorkbench() {
    navigate(activeWorkbenchPage());
}

function setActiveOfficeContext(officeId, officeName) {
    ACTIVE_OFFICE_ID = officeId;
    MODEL_OFFICE_ID = officeId;
    writeStoredOfficeId(officeId);
    const label = document.getElementById('sidebar-office-name');
    if (label) label.textContent = officeName;
}

function activeWorkbenchPage() {
    return WORKBENCH_PAGES.has(ACTIVE_OFFICE_ID) ? ACTIVE_OFFICE_ID : 'research';
}

function normalizeNavigationTarget(page) {
    if (page === 'comic') return 'comic_production';
    if (page === 'workbench') return activeWorkbenchPage();
    const source = window.event?.target?.closest?.('[data-page]');
    const fromSidebarWorkbench = source?.closest?.('.sidebar') && source.dataset.page === 'research';
    if (page === 'research' && fromSidebarWorkbench && WORKBENCH_PAGES.has(ACTIVE_OFFICE_ID)) {
        return ACTIVE_OFFICE_ID;
    }
    return page;
}

function readStoredOfficeId() {
    try {
        const saved = localStorage.getItem('activeOfficeId');
        if (saved === 'comic') return 'comic_production';
        return WORKBENCH_PAGES.has(saved) ? saved : 'research';
    } catch (e) {
        return 'research';
    }
}

function writeStoredOfficeId(officeId) {
    try {
        localStorage.setItem('activeOfficeId', WORKBENCH_PAGES.has(officeId) ? officeId : 'research');
    } catch (e) {}
}

function refreshOfficeChrome() {
    const label = document.getElementById('sidebar-office-name');
    if (label) label.textContent = OFFICE_LABELS[ACTIVE_OFFICE_ID] || OFFICE_LABELS.research;
}

// ============================================================
// Markdown
// ============================================================
function simpleMarkdown(text) {
    if (!text) return '';
    return text
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/^### (.+)$/gm, '<h4>$1</h4>')
        .replace(/^## (.+)$/gm, '<h3>$1</h3>')
        .replace(/^# (.+)$/gm, '<h2>$1</h2>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/^\- (.+)$/gm, '<li>$1</li>')
        .replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
        .replace(/\|(.+)\|/g, (m) => {
            const cells = m.split('|').filter(c => c.trim());
            if (cells.every(c => /^[\s\-:]+$/.test(c))) return '';
            const isBold = m.includes('**');
            return '<tr>' + cells.map(c => {
                const clean = c.replace(/\*\*/g, '').trim();
                return isBold ? `<th>${clean}</th>` : `<td>${clean}</td>`;
            }).join('') + '</tr>';
        })
        .replace(/\n\n/g, '<br><br>').replace(/\n/g, '<br>');
}

// ============================================================
// Toast
// ============================================================
function toast(msg, type) {
    const t = document.getElementById('toast') || (() => { const e = document.createElement('div'); e.id = 'toast'; e.className = 'toast'; document.body.appendChild(e); return e; })();
    t.textContent = msg; t.className = 'toast ' + type + ' show';
    setTimeout(() => t.classList.remove('show'), 3000);
}

function showOfficeUnavailable(name) {
    toast(`${name} 暂未开放：需要先配置办公室流程、Agent 分工和验收规则。`, 'error');
}

function showSampleUnavailable(name) {
    toast(`${name} 的样品展示暂未开放，后续会放示例项目和交付物。`, 'error');
}

// ============================================================
// Task
// ============================================================
async function submitTask() {
    const input = document.getElementById('task-input');
    const skill = document.getElementById('skill-select');
    const req = input.value.trim();
    if (!req) return;
    const btn = document.getElementById('btn-submit');
    btn.disabled = true; btn.textContent = '执行中...';

    try {
        const r = await API.post('/api/tasks', { user_request: req, template_id: skill.value || null });
        const tid = r.task_id;
        document.getElementById('result-card').style.display = '';
        document.getElementById('result-task-id').textContent = tid;
        document.getElementById('result-status').innerHTML = '<span class="badge badge-info">执行中</span>';
        document.getElementById('result-content').innerHTML = '<p>中书省起草中...</p>';
        document.getElementById('result-files').innerHTML = '';
        
        // Hide welcome screen
        const welcome = document.getElementById('welcome-screen');
        if (welcome) welcome.style.display = 'none';
        
        connectTaskWS(tid);
    } catch (e) { toast('启动失败: ' + e.message, 'error'); }
    btn.disabled = false; btn.textContent = '提交任务';
}

let taskSocket = null;
function connectTaskWS(taskId) {
    if (taskSocket) taskSocket.close();
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    taskSocket = new WebSocket(`${proto}//${location.host}/ws/tasks/${taskId}`);
    taskSocket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        const el = document.getElementById('result-content');
        if (data.type === 'completed') {
            let html = simpleMarkdown(data.result.final_report) || '任务完成';
            el.innerHTML = html;
            document.getElementById('result-status').innerHTML = '<span class="badge badge-ok">完成</span>';
            loadTaskFiles(taskId);
            loadHistory();
            toast('任务完成', 'success');
            scrollToBottom();
        } else if (data.type === 'error') {
            el.innerHTML = '<p style="color:var(--danger)">错误: ' + data.error + '</p>';
            document.getElementById('result-status').innerHTML = '<span class="badge badge-err">失败</span>';
            toast('任务出错', 'error');
            scrollToBottom();
        }
    };
}

function scrollToBottom() {
    const scrollArea = document.querySelector('.chat-scroll-area');
    if (scrollArea) {
        scrollArea.scrollTop = scrollArea.scrollHeight;
    }
}

async function loadTaskFiles(taskId) {
    try {
        const data = await API.get('/api/tasks/' + taskId + '/files');
        const files = data.files || [];
        const el = document.getElementById('result-files');
        if (files.length) {
            el.innerHTML = '<strong>产出文件: </strong>' + files.map(f =>
                `<a href="/api/tasks/${taskId}/download/${encodeURIComponent(f.name)}" download>${f.name}</a> (${f.size > 1024 ? (f.size/1024).toFixed(1)+'KB' : f.size+'B'})`
            ).join(' ');
        }
    } catch (e) {}
}

// ============================================================
// Research Office
// ============================================================
let currentResearchWorkspace = '';
let currentResearchArtifacts = [];
let researchTimelineTimer = null;

const RESEARCH_REQUIRED_ARTIFACTS = [
    ['report', '完整报告'],
    ['briefing', '摘要简报'],
    ['source_list', '来源清单'],
    ['data_table', '数据要点表'],
    ['competitor_table', '竞品分析表'],
    ['review_pain_points', '差评痛点表'],
    ['opportunity_map', '差异化机会表'],
    ['chart_plan', '图表建议'],
    ['screenshot_plan', '截图取证计划'],
    ['quality_report', '验收报告'],
];

function escapeHtml(text) {
    return String(text || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

async function loadResearchOffice() {
    await Promise.all([loadResearchProfile(), loadResearchWorkspaces()]);
}

async function loadResearchProfile() {
    try {
        const office = await API.get('/api/offices/research');
        const duties = office.agent_duties || {};
        const dutyNames = {
            zhongshu: '中书省',
            menxia: '门下省',
            shangshu: '尚书省',
            libu: '吏部',
            hubu: '户部',
            libu_comm: '礼部',
            bingbu: '兵部',
            xingbu: '刑部',
            gongbu: '工部',
        };
        document.getElementById('research-duties').innerHTML = Object.entries(duties).map(([id, text]) => `
            <div class="duty-item">
                <strong>${dutyNames[id] || id}</strong>
                <span>${escapeHtml(text)}</span>
            </div>
        `).join('');
        document.getElementById('research-criteria').innerHTML = (office.acceptance_criteria || []).map(c =>
            `<li>${escapeHtml(c)}</li>`
        ).join('');
    } catch (e) {
        toast('研究办公室配置加载失败', 'error');
    }
}

async function loadResearchWorkspaces() {
    try {
        const data = await API.get('/api/workspaces?office_id=research&limit=50');
        const workspaces = data.workspaces || [];
        document.getElementById('research-workspace-count').textContent = String(workspaces.length);
        const select = document.getElementById('research-workspace-select');
        select.innerHTML = '<option value="">新建工作空间</option>' + workspaces.map(w =>
            `<option value="${w.workspace_id}" ${w.workspace_id === currentResearchWorkspace ? 'selected' : ''}>${escapeHtml(w.title)}</option>`
        ).join('');
        const list = document.getElementById('research-workspaces');
        if (!workspaces.length) {
            list.innerHTML = '<div class="empty-state">还没有研究项目。提交一个调研需求后会自动创建。</div>';
            return;
        }
        list.innerHTML = workspaces.map(w => `
            <button class="workspace-item ${w.workspace_id === currentResearchWorkspace ? 'active' : ''}" onclick="selectResearchWorkspace('${w.workspace_id}')">
                <strong>${escapeHtml(w.title)}</strong>
                <span>${escapeHtml(w.brief || '')}</span>
                <code>${w.workspace_id}</code>
            </button>
        `).join('');
        if (!currentResearchWorkspace && workspaces[0]) {
            selectResearchWorkspace(workspaces[0].workspace_id);
        }
    } catch (e) {
        toast('工作空间加载失败', 'error');
    }
}

async function selectResearchWorkspace(workspaceId) {
    currentResearchWorkspace = workspaceId;
    const select = document.getElementById('research-workspace-select');
    if (select) select.value = workspaceId;
    await Promise.all([loadResearchArtifacts(workspaceId), loadResearchTimeline(workspaceId)]);
    document.querySelectorAll('.workspace-item').forEach(el => {
        el.classList.toggle('active', el.textContent.includes(workspaceId));
    });
}

async function loadResearchTimeline(workspaceId) {
    const count = document.getElementById('research-task-count');
    const list = document.getElementById('research-timeline');
    if (!workspaceId) {
        count.textContent = '0';
        list.innerHTML = '<div class="empty-state">选择一个工作空间后查看任务进度。</div>';
        stopResearchTimelinePolling();
        return;
    }
    try {
        const data = await API.get(`/api/workspaces/${workspaceId}/tasks`);
        const tasks = data.tasks || [];
        count.textContent = String(tasks.length);
        if (!tasks.length) {
            list.innerHTML = '<div class="empty-state">这个工作空间还没有任务记录。</div>';
            stopResearchTimelinePolling();
            return;
        }
        list.innerHTML = tasks.map(renderResearchTaskTimeline).join('');
        const hasRunning = tasks.some(t => ['queued', 'running'].includes(t.status));
        if (hasRunning) startResearchTimelinePolling(workspaceId);
        else stopResearchTimelinePolling();
    } catch (e) {
        list.innerHTML = '<div class="empty-state">任务时间线加载失败。</div>';
    }
}

function renderResearchTaskTimeline(task) {
    const visibleEvents = (task.events || []).slice(-8);
    return `
        <div class="timeline-task">
            <div class="timeline-task-head">
                <div>
                    <strong>${escapeHtml((task.user_request || '').slice(0, 80))}</strong>
                    <code>${escapeHtml(task.task_id)}</code>
                </div>
                <div class="timeline-task-actions">
                    <span class="badge ${task.status === 'completed' ? 'badge-ok' : ['failed', 'interrupted'].includes(task.status) ? 'badge-err' : 'badge-info'}">${escapeHtml(task.status || '')}</span>
                    ${task.status !== 'completed' ? `<button class="ghost btn-sm" onclick="recoverResearchTask('${escapeHtml(task.task_id)}')">整理已有产出</button>` : ''}
                </div>
            </div>
            <div class="timeline-phase">当前阶段：${escapeHtml(phaseLabel(task.current_phase))}</div>
            <div class="timeline-events">
                ${visibleEvents.map(e => `
                    <div class="timeline-event ${e.status === 'failed' ? 'failed' : ''}">
                        <span></span>
                        <div>
                            <strong>${escapeHtml(eventLabel(e.event_type))}</strong>
                            <p>${escapeHtml(e.summary || '')}</p>
                            <time>${escapeHtml((e.created_at || '').replace('T', ' ').slice(0, 19))}</time>
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
}

function phaseLabel(phase) {
    const map = {
        queued: '排队中',
        preparing: '准备中',
        agent_workflow: 'Agent 协作中',
        artifact_packaging: '整理材料包',
        completed: '已完成',
        finished: '已结束',
        interrupted: '后台已中断',
        error: '出错',
    };
    return map[phase] || phase || '未知';
}

function eventLabel(type) {
    const map = {
        task_created: '任务已接收',
        task_started: '开始执行',
        template_applied: '应用模板',
        office_template_applied: '应用办公室流程',
        agent_workflow_started: 'Agent 开始协作',
        agent_workflow_finished: 'Agent 协作结束',
        artifact_packaging_started: '开始整理产物',
        artifacts_created: '产物已生成',
        artifacts_recovered: '产物已恢复',
        task_interrupted_after_restart: '后台已中断',
        task_finished: '任务完成',
        task_failed: '任务失败',
    };
    return map[type] || type || '事件';
}

async function recoverResearchTask(taskId) {
    try {
        const result = await API.post(`/api/tasks/${taskId}/recover-artifacts`, {});
        if (result.detail) throw new Error(result.detail);
        toast(`已整理 ${result.artifact_count || 0} 个产物`, 'success');
        await Promise.all([
            loadResearchTimeline(currentResearchWorkspace),
            loadResearchArtifacts(currentResearchWorkspace),
        ]);
    } catch (e) {
        toast('暂时没有可整理的已有产出', 'error');
    }
}

function startResearchTimelinePolling(workspaceId) {
    if (researchTimelineTimer) return;
    researchTimelineTimer = setInterval(() => {
        if (currentResearchWorkspace === workspaceId) {
            loadResearchTimeline(workspaceId);
            loadResearchArtifacts(workspaceId);
        }
    }, 5000);
}

function stopResearchTimelinePolling() {
    if (researchTimelineTimer) {
        clearInterval(researchTimelineTimer);
        researchTimelineTimer = null;
    }
}

async function loadResearchArtifacts(workspaceId) {
    const label = document.getElementById('research-current-workspace');
    const list = document.getElementById('research-artifacts');
    const detail = document.getElementById('research-artifact-detail');
    label.textContent = workspaceId || '未选择';
    if (!workspaceId) {
        renderResearchPackageBoard([]);
        list.innerHTML = '<div class="empty-state">选择一个工作空间查看产物。</div>';
        detail.innerHTML = '选择一个产物查看完整内容。';
        detail.className = 'artifact-detail empty-state';
        return;
    }
    try {
        const data = await API.get(`/api/workspaces/${workspaceId}/artifacts`);
        const artifacts = data.artifacts || [];
        currentResearchArtifacts = artifacts;
        renderResearchPackageBoard(artifacts);
        if (!artifacts.length) {
            list.innerHTML = '<div class="empty-state">这个项目还没有产物。任务完成后，报告会先进入这里。</div>';
            detail.innerHTML = '选择一个产物查看完整内容。';
            detail.className = 'artifact-detail empty-state';
            return;
        }
        list.innerHTML = artifacts.map((a, index) => `
            <button class="artifact-item" onclick="selectResearchArtifact(${index})">
                <div>
                    <span class="artifact-type">${escapeHtml(a.artifact_type)}</span>
                    <strong>${escapeHtml(a.title)}</strong>
                    <p>${escapeHtml((a.content || '').slice(0, 180))}${(a.content || '').length > 180 ? '...' : ''}</p>
                </div>
            </button>
        `).join('');
        selectResearchArtifact(0);
    } catch (e) {
        toast('产物加载失败', 'error');
    }
}

function renderResearchPackageBoard(artifacts) {
    const board = document.getElementById('research-package-board');
    const scoreEl = document.getElementById('research-package-score');
    if (!board || !scoreEl) return;
    if (!artifacts || !artifacts.length) {
        scoreEl.textContent = '未开始';
        scoreEl.className = 'badge badge-info';
        board.innerHTML = '<div class="empty-state">还没有产物。任务完成后会在这里显示材料包状态。</div>';
        return;
    }

    const byType = new Map();
    artifacts.forEach((artifact, index) => {
        byType.set(artifact.artifact_type, { artifact, index });
    });
    const quality = [...artifacts].reverse().find(a => a.artifact_type === 'quality_report')?.metadata || {};
    const warnings = quality.warnings || [];
    const evidenceCount = artifacts.filter(a => a.artifact_type === 'screenshot_evidence').length;
    const missing = new Set(quality.missing_artifacts || []);
    const readyCount = RESEARCH_REQUIRED_ARTIFACTS.filter(([type]) => byType.has(type) && !missing.has(type)).length;
    const total = RESEARCH_REQUIRED_ARTIFACTS.length;
    const score = Math.round((readyCount / total) * 100);
    const qualityScore = quality.score || score;
    const qualityStatus = quality.status || (score === 100 ? 'ready' : 'incomplete');

    scoreEl.textContent = `${readyCount}/${total} · ${qualityScore}分`;
    scoreEl.className = `badge ${qualityStatus === 'ready' ? 'badge-ok' : qualityStatus === 'incomplete' ? 'badge-err' : 'badge-info'}`;

    board.innerHTML = `
        <div class="package-summary">
            <strong>${packageStatusLabel(qualityStatus)}</strong>
            <span>${evidenceCount ? `已上传 ${evidenceCount} 张截图证据。` : (warnings.length ? escapeHtml(warnings[0]) : '材料包基础产物已形成，可继续核验来源和数据质量。')}</span>
        </div>
        <div class="package-grid">
            ${RESEARCH_REQUIRED_ARTIFACTS.map(([type, label]) => {
                const found = byType.get(type);
                const status = artifactStatus(type, found?.artifact, missing, warnings);
                return `
                    <button class="package-item ${status.kind}" ${found ? `onclick="selectResearchArtifact(${found.index})"` : ''}>
                        <span>${escapeHtml(label)}</span>
                        <strong>${status.text}</strong>
                    </button>
                `;
            }).join('')}
        </div>
    `;
}

function artifactStatus(type, artifact, missing, warnings) {
    if (!artifact || missing.has(type)) return { kind: 'missing', text: '待补' };
    const content = artifact.content || '';
    const isFallback = /暂未|待补充|待核验|无法获取|需要.*补齐/.test(content);
    const sourceWarning = type === 'source_list' && warnings.some(w => String(w).includes('来源清单'));
    if (isFallback || sourceWarning) return { kind: 'review', text: '待核验' };
    return { kind: 'ready', text: '已生成' };
}

function packageStatusLabel(status) {
    const map = {
        ready: '材料包已成型',
        needs_review: '材料包需要复核',
        incomplete: '材料包未完整',
    };
    return map[status] || '材料包状态';
}

function selectResearchArtifact(index) {
    const artifact = currentResearchArtifacts[index];
    const detail = document.getElementById('research-artifact-detail');
    if (!artifact) return;
    document.querySelectorAll('.artifact-item').forEach((el, i) => {
        el.classList.toggle('active', i === index);
    });
    const isMarkdown = artifact.artifact_type === 'report' || artifact.artifact_type === 'briefing';
    const image = artifact.artifact_type === 'screenshot_evidence' && artifact.uri
        ? `<div class="evidence-preview"><img src="${escapeHtml(artifact.uri)}" alt="${escapeHtml(artifact.title)}"></div>`
        : '';
    const body = isMarkdown
        ? simpleMarkdown(artifact.content || '')
        : `${image}<pre>${escapeHtml(artifact.content || '')}</pre>`;
    const evidenceActions = artifact.artifact_type === 'screenshot_evidence'
        ? `<div class="artifact-actions">
                <select id="evidence-extract-agent">
                    <option value="hubu">户部识别</option>
                    <option value="bingbu">兵部识别</option>
                    <option value="xingbu">刑部核验</option>
                    <option value="gongbu">工部整理</option>
                </select>
                <button class="ghost btn-sm" onclick="extractResearchEvidence('${escapeHtml(artifact.artifact_id)}')">识别截图</button>
           </div>`
        : '';
    detail.className = 'artifact-detail';
    detail.innerHTML = `
        <div class="artifact-detail-head">
            <span class="artifact-type">${escapeHtml(artifact.artifact_type)}</span>
            <strong>${escapeHtml(artifact.title)}</strong>
        </div>
        ${evidenceActions}
        <div class="artifact-detail-body">${body || '<em>空内容</em>'}</div>
    `;
}

async function submitResearchTask() {
    const input = document.getElementById('research-input');
    const req = buildResearchRequest();
    if (!req) return;
    try {
        const r = await API.post('/api/tasks', {
            user_request: req,
            office_id: 'research',
            template_id: null,
        });
        currentResearchWorkspace = r.workspace_id;
        input.value = '';
        const subject = document.getElementById('research-subject');
        if (subject) subject.value = '';
        toast('研究任务已提交', 'success');
        await loadResearchWorkspaces();
        await Promise.all([
            loadResearchArtifacts(currentResearchWorkspace),
            loadResearchTimeline(currentResearchWorkspace),
        ]);
    } catch (e) {
        toast('提交失败: ' + e.message, 'error');
    }
}

function buildResearchRequest() {
    const subject = document.getElementById('research-subject')?.value.trim() || '';
    const platform = document.getElementById('research-platform')?.value || '';
    const purpose = document.getElementById('research-purpose')?.value || '';
    const extra = document.getElementById('research-input')?.value.trim() || '';
    const focus = Array.from(document.querySelectorAll('.research-checks input:checked')).map(i => i.value);
    if (!subject && !extra) {
        toast('请先填写研究对象或补充要求', 'error');
        return '';
    }
    return [
        `研究对象：${subject || '见补充要求'}`,
        `主要平台：${platform}`,
        `交付用途：${purpose}`,
        `重点分析维度：${focus.join('、') || '由研究办公室判断'}`,
        '必需产物：完整报告、老板摘要、来源清单、数据要点表、竞品分析表、差评痛点表、差异化机会表、图表建议、截图取证计划、验收报告。',
        '要求：具体数字必须带来源；无法确认的数据标记为待核验；结论需要能支撑开会或立项决策。',
        extra ? `补充要求：${extra}` : '',
    ].filter(Boolean).join('\n');
}

function exportResearchWorkspace() {
    if (!currentResearchWorkspace) {
        toast('请先选择工作空间', 'error');
        return;
    }
    window.location.href = `/api/workspaces/${currentResearchWorkspace}/export`;
}

async function uploadResearchEvidence(event) {
    const file = event.target.files && event.target.files[0];
    event.target.value = '';
    if (!file) return;
    if (!currentResearchWorkspace) {
        toast('请先选择一个研究项目，再上传截图证据', 'error');
        return;
    }
    const formData = new FormData();
    formData.append('file', file);
    formData.append('note', document.getElementById('research-evidence-note')?.value || '');
    try {
        const res = await fetch(`/api/workspaces/${currentResearchWorkspace}/evidence`, {
            method: 'POST',
            body: formData,
        });
        const data = await res.json();
        if (!res.ok || data.detail) throw new Error(data.detail || '上传失败');
        toast('截图证据已入库', 'success');
        const note = document.getElementById('research-evidence-note');
        if (note) note.value = '';
        await loadResearchArtifacts(currentResearchWorkspace);
    } catch (e) {
        toast('截图上传失败: ' + e.message, 'error');
    }
}

async function openResearchLoginBrowser() {
    const url = document.getElementById('research-capture-url')?.value.trim() || 'https://dy3.feigua.cn/';
    try {
        const result = await API.post('/api/browser/start-login', { url });
        if (result.detail) throw new Error(result.detail);
        const hasDialog = result.page && result.page.hasLoginDialog;
        toast(hasDialog ? '飞瓜登录弹窗已打开，请在 Edge 中选择微信或手机登录' : '登录窗口已打开，请在浏览器里登录平台', 'success');
    } catch (e) {
        toast('打开登录窗口失败: ' + e.message, 'error');
    }
}

async function captureResearchUrl() {
    if (!currentResearchWorkspace) {
        toast('请先选择工作空间', 'error');
        return;
    }
    const url = document.getElementById('research-capture-url')?.value.trim() || '';
    if (!url) {
        toast('请先填写要截图的页面 URL', 'error');
        return;
    }
    const title = document.getElementById('research-capture-title')?.value.trim() || '';
    const note = document.getElementById('research-evidence-note')?.value || '';
    try {
        toast('正在打开页面并截图', 'success');
        const result = await API.post(`/api/workspaces/${currentResearchWorkspace}/capture-url`, {
            url,
            title,
            note,
            wait_seconds: 6,
            full_page: true,
        });
        if (result.detail) throw new Error(result.detail);
        toast('页面截图已入库', 'success');
        await loadResearchArtifacts(currentResearchWorkspace);
    } catch (e) {
        toast('自动截图失败: ' + e.message, 'error');
    }
}

function toggleEvidenceAdvanced() {
    const panel = document.getElementById('evidence-advanced');
    if (!panel) return;
    panel.style.display = panel.style.display === 'none' ? '' : 'none';
}

async function captureResearchFeigua() {
    if (!currentResearchWorkspace) {
        toast('请先选择工作空间', 'error');
        return;
    }
    const keyword = document.getElementById('research-subject')?.value.trim()
        || document.getElementById('research-capture-title')?.value.trim()
        || '';
    if (!keyword) {
        toast('请先填写研究对象，例如 民用无人机', 'error');
        return;
    }
    try {
        toast('正在执行飞瓜自动取证', 'success');
        const result = await API.post(`/api/workspaces/${currentResearchWorkspace}/capture-feigua`, {
            keyword,
            wait_seconds: 6,
            limit: 4,
        });
        if (result.detail) throw new Error(result.detail);
        if (!result.created_count) {
            toast(result.note || '飞瓜取证未生成截图，请先登录后重试', 'error');
        } else {
            toast(`已生成 ${result.created_count} 张飞瓜截图证据`, 'success');
        }
        await loadResearchArtifacts(currentResearchWorkspace);
    } catch (e) {
        toast('飞瓜取证失败: ' + e.message, 'error');
    }
}

async function extractResearchEvidence(artifactId) {
    const agent = document.getElementById('evidence-extract-agent')?.value || 'hubu';
    try {
        toast('正在识别截图，稍等一下', 'success');
        const result = await API.post(`/api/artifacts/${artifactId}/extract`, {
            agent_id: agent,
            instruction: '请优先提取榜单、价格、销量、品牌、商品名、评论痛点和可用于图表的数据。',
        });
        if (result.detail) throw new Error(result.detail);
        if (result.status === 'failed') {
            toast('识别未完成：请检查该部门视觉模型配置', 'error');
        } else {
            toast('截图识别结果已生成', 'success');
        }
        await loadResearchArtifacts(currentResearchWorkspace);
        const index = currentResearchArtifacts.findIndex(a => a.artifact_id === result.artifact_id);
        if (index >= 0) selectResearchArtifact(index);
    } catch (e) {
        toast('截图识别失败: ' + e.message, 'error');
    }
}

async function syncResearchEvidence() {
    if (!currentResearchWorkspace) {
        toast('请先选择工作空间', 'error');
        return;
    }
    try {
        const result = await API.post(`/api/workspaces/${currentResearchWorkspace}/evidence/sync`, {});
        if (result.detail) throw new Error(result.detail);
        toast(`已整理 ${result.artifact_count || 0} 个证据产物`, 'success');
        await loadResearchArtifacts(currentResearchWorkspace);
    } catch (e) {
        toast('证据整理失败: ' + e.message, 'error');
    }
}

// ============================================================
// AI Comic Office
// ============================================================
let currentComicWorkspace = '';
let currentComicArtifacts = [];
let currentComicBrief = null;
let currentComicScriptPreview = null;
let currentComicConfirmedScript = null;
let currentComicCabinetSession = null;
let currentComicCabinetReady = false;
let comicTaskPoller = null;

const COMIC_REQUIRED_ARTIFACTS = [
    ['creative_brief', '锁定稿'],
    ['script_preview', '故事预审'],
    ['confirmed_script', '确认稿'],
    ['cabinet_review', '内阁'],
    ['script', '剧本'],
    ['character_sheet', '人物'],
    ['prop_sheet', '道具'],
    ['scene_sheet', '场景'],
    ['style_bible', '风格'],
    ['shot_prompt_table', '镜头提示'],
    ['prompt_package', '提示词'],
    ['production_canvas', '制片画布'],
    ['word_canvas', 'Word'],
    ['generated_image', '预览图'],
    ['image_quality_report', '视觉质检'],
    ['consistency_checklist', '检查'],
];

function activeComicOfficeId() {
    return 'comic_production';
}

function refreshComicOfficeCopy() {
    const isProduction = activeComicOfficeId() === 'comic_production';
    const title = document.querySelector('#page-comic .office-head h2');
    const desc = document.querySelector('#page-comic .office-head .desc');
    if (title) title.textContent = isProduction ? 'AI漫剧制片办公室' : 'AI漫剧创作台';
    if (desc) {
        desc.textContent = isProduction
            ? '隔离版制片链：把确认后的故事拆成任务书、资产表、分镜、运镜、提示词和 Word 画布。'
            : '从一句灵感开始，逐步生成剧本、人物、道具、场景、分镜、运镜和提示词资产。';
    }
}

async function loadComicOffice() {
    refreshComicOfficeCopy();
    toggleComicInputMode();
    await Promise.all([loadComicProfile(), loadComicWorkspaces()]);
}

async function loadComicProfile() {
    try {
        const office = await API.get(`/api/offices/${activeComicOfficeId()}`);
        const duties = office.agent_duties || {};
        document.getElementById('comic-duties').innerHTML = Object.entries(duties).map(([id, text]) => `
            <div class="duty-item">
                <strong>${escapeHtml(agentName(id))}</strong>
                <p>${escapeHtml(text)}</p>
            </div>
        `).join('');
        document.getElementById('comic-criteria').innerHTML = (office.acceptance_criteria || []).map(c =>
            `<li>${escapeHtml(c)}</li>`
        ).join('');
    } catch (e) {
        toast('AI漫剧办公室信息读取失败: ' + e.message, 'error');
    }
}

async function loadComicWorkspaces() {
    const data = await API.get(`/api/workspaces?office_id=${activeComicOfficeId()}&limit=50`);
    const workspaces = data.workspaces || [];
    document.getElementById('comic-workspace-count').textContent = String(workspaces.length);
    const select = document.getElementById('comic-workspace-select');
    select.innerHTML = '<option value="">新建漫剧项目</option>' + workspaces.map(w =>
        `<option value="${w.workspace_id}" ${w.workspace_id === currentComicWorkspace ? 'selected' : ''}>${escapeHtml(w.title || w.workspace_id)}</option>`
    ).join('');
    const list = document.getElementById('comic-workspaces');
    if (!workspaces.length) {
        list.innerHTML = '<div class="empty-state">还没有漫剧项目。输入一个灵感，先生成第一个创作骨架。</div>';
        return;
    }
    const visibleWorkspaces = workspaces.slice(0, 8);
    list.innerHTML = visibleWorkspaces.map(w => `
        <button class="workspace-item ${w.workspace_id === currentComicWorkspace ? 'active' : ''}" onclick="selectComicWorkspace('${w.workspace_id}')">
            <strong>${escapeHtml(w.title || 'AI漫剧项目')}</strong>
            <span>${escapeHtml(w.brief || '')}</span>
            <code>${w.workspace_id}</code>
        </button>
    `).join('') + (workspaces.length > visibleWorkspaces.length
        ? `<div class="empty-state">工作台只显示最近 ${visibleWorkspaces.length} 个项目，完整内容可到历史里查看和下载。</div>`
        : '');
    // 移除自动选中第一个项目的逻辑，确保如果用户选择了新建项目，就不会自动跳回去
    // if (!currentComicWorkspace && workspaces[0]) {
    //     await selectComicWorkspace(workspaces[0].workspace_id);
    // }
}

async function selectComicWorkspace(workspaceId) {
    currentComicWorkspace = workspaceId;
    const select = document.getElementById('comic-workspace-select');
    if (select) select.value = workspaceId;
    
    if (!workspaceId) {
        stopComicTaskPolling();
        // 如果是选择了“新建漫剧项目”，不仅清空变量，还要清空页面上的表单输入
        document.getElementById('comic-idea').value = '';
        const scriptSource = document.getElementById('comic-script-source');
        if (scriptSource) scriptSource.value = '';
        const inputMode = document.getElementById('comic-input-mode');
        if (inputMode) inputMode.value = 'idea';
        toggleComicInputMode();
        document.getElementById('comic-extra').value = '';
        document.getElementById('comic-chat-input').value = '';
        
        // 重新渲染空状态
        await loadComicCabinetSession('');
        await loadComicArtifacts('');
        await loadComicTimeline('');
        
        // 重新渲染左侧列表高亮状态
        const items = document.querySelectorAll('#comic-workspaces .workspace-item');
        items.forEach(item => item.classList.remove('active'));
        
        return;
    }
    
    // 如果不是新建，而是切换到了别的项目，更新左侧列表高亮状态
    const items = document.querySelectorAll('#comic-workspaces .workspace-item');
    items.forEach(item => {
        if (item.getAttribute('onclick').includes(workspaceId)) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });

    await Promise.all([loadComicArtifacts(workspaceId), loadComicTimeline(workspaceId), loadComicCabinetSession(workspaceId)]);
}

async function loadComicCabinetSession(workspaceId) {
    if (!workspaceId) {
        currentComicCabinetSession = null;
        currentComicCabinetReady = false;
        currentComicBrief = null;
        currentComicScriptPreview = null;
        currentComicConfirmedScript = null;
        renderComicCabinet();
        return;
    }
    try {
        const result = await API.get(`/api/comic/cabinet/${workspaceId}`);
        if (result.status !== 'ok') {
            currentComicCabinetSession = null;
            currentComicCabinetReady = false;
            currentComicBrief = null;
            currentComicScriptPreview = null;
            currentComicConfirmedScript = null;
        } else {
            currentComicCabinetSession = result.session || null;
            currentComicCabinetReady = Boolean(result.ready_to_produce);
            currentComicBrief = result.creative_brief || null;
            currentComicScriptPreview = result.script_preview || null;
            currentComicConfirmedScript = result.confirmed_script || null;
        }
        renderComicCabinet();
    } catch (e) {
        currentComicCabinetSession = null;
        currentComicCabinetReady = false;
        currentComicBrief = null;
        currentComicScriptPreview = null;
        currentComicConfirmedScript = null;
        renderComicCabinet();
    }
}

async function loadComicTimeline(workspaceId) {
    const count = document.getElementById('comic-task-count');
    const list = document.getElementById('comic-timeline');
    if (!workspaceId) {
        count.textContent = '0';
        list.innerHTML = '<div class="empty-state">选择一个漫剧项目后查看创作记录。</div>';
        return;
    }
    const data = await API.get(`/api/workspaces/${workspaceId}/tasks`);
    const tasks = data.tasks || [];
    count.textContent = String(tasks.length);
    if (!tasks.length) {
        list.innerHTML = '<div class="empty-state">这个项目还没有任务记录。</div>';
        return;
    }
    list.innerHTML = tasks.map(t => `
        <div class="timeline-item">
            <div class="timeline-dot ${t.status === 'completed' ? 'ok' : ''}"></div>
            <div>
                <strong>${escapeHtml(t.user_request || '')}</strong>
                <span>${escapeHtml(t.status || '')} · ${escapeHtml(t.current_phase || '')}</span>
                <code>${escapeHtml(t.task_id || '')}</code>
            </div>
        </div>
    `).join('');
}

async function loadComicArtifacts(workspaceId) {
    const label = document.getElementById('comic-current-workspace');
    const list = document.getElementById('comic-artifacts');
    const detail = document.getElementById('comic-artifact-detail');
    label.textContent = workspaceId || '未选择';
    if (!workspaceId) {
        currentComicArtifacts = [];
        renderComicPackageBoard([]);
        renderComicAssetReviewPanel([]);
        list.innerHTML = '<div class="empty-state">选择一个漫剧项目查看资产。</div>';
        detail.className = 'artifact-detail empty-state';
        detail.textContent = '选择一个资产查看完整内容。';
        return;
    }
    const data = await API.get(`/api/workspaces/${workspaceId}/artifacts`);
    const artifacts = data.artifacts || [];
    currentComicArtifacts = artifacts;
    renderComicPackageBoard(artifacts);
    renderComicAssetReviewPanel(artifacts);
    if (!artifacts.length) {
        list.innerHTML = '<div class="empty-state">还没有资产。从灵感生成项目后会出现剧本、角色、场景、分镜和提示词。</div>';
        detail.className = 'artifact-detail empty-state';
        detail.textContent = '等待创作资产生成。';
        return;
    }
    list.innerHTML = renderComicArtifactNavigator(artifacts);
    const blockingReviewIndex = latestBlockingComicAssetReviewIndex(artifacts);
    selectComicArtifact(blockingReviewIndex >= 0 ? blockingReviewIndex : 0);
}

function renderComicArtifactNavigator(artifacts) {
    const groups = comicArtifactGroups(artifacts || []);
    const activeKey = groups.find(group => group.items.some(item => item.artifact.artifact_type === 'asset_review_package' && (item.artifact.metadata || {}).review_status !== 'approved'))?.key
        || groups.find(group => group.items.length)?.key
        || '';
    return `
        <div class="asset-filter-tabs">
            ${[
                ['all', '全部'],
                ['review', '待确认'],
                ['images', '图片'],
                ['docs', '文档'],
                ['delivery', '交付'],
                ['issues', '问题'],
            ].map(([key, label]) => `<button class="asset-filter ${key === 'all' ? 'active' : ''}" onclick="filterComicAssets('${key}')">${label}</button>`).join('')}
        </div>
        <div class="asset-group-list">
            ${groups.map(group => renderComicArtifactGroup(group, group.key === activeKey)).join('')}
        </div>
    `;
}

function comicArtifactGroups(artifacts) {
    const defs = [
        { key: 'review', title: '待确认', hint: '需要你做决定的内容', types: ['asset_review_package'], filter: a => a.artifact_type === 'asset_review_package' && (a.metadata || {}).review_status !== 'approved' },
        { key: 'script', title: '剧本与确认', hint: '故事、确认稿、内阁意见', types: ['creative_brief', 'script_preview', 'story_draft', 'confirmed_script', 'cabinet_review', 'script'] },
        { key: 'asset_docs', title: '资产拆解', hint: '人物、道具、场景和审核包', types: ['asset_review_package', 'style_bible', 'character_sheet', 'prop_sheet', 'scene_sheet', 'asset_registry'] },
        { key: 'images', title: '图片资产库', hint: '人物、道具、场景基础资产图', types: ['generated_image'] },
        { key: 'shot_docs', title: '镜头提示词', hint: '镜头画面提示词、视频生成提示词、交接台', types: ['shot_prompt_table', 'shot_prompt_handoff'] },
        { key: 'delivery', title: '交付文件', hint: 'Word 画布、提示词包、执行材料', types: ['word_canvas', 'prompt_package', 'production_canvas', 'production_brief', 'dispatch_plan'] },
        { key: 'quality', title: '质检与问题', hint: '质量报告、错误记录、链路状态', types: ['image_quality_report', 'image_generation_error', 'consistency_checklist', 'production_chain_state'] },
    ];
    const used = new Set();
    const groups = defs.map(def => {
        const items = artifacts
            .map((artifact, index) => ({ artifact, index }))
            .filter(item => {
                if (used.has(item.index)) return false;
                const matched = def.filter ? def.filter(item.artifact) : def.types.includes(item.artifact.artifact_type);
                if (matched) used.add(item.index);
                return matched;
            });
        return { ...def, items };
    });
    const other = artifacts
        .map((artifact, index) => ({ artifact, index }))
        .filter(item => !used.has(item.index));
    if (other.length) groups.push({ key: 'other', title: '其他', hint: '未归类产物', types: [], items: other });
    return groups.filter(group => group.items.length);
}

function renderComicArtifactGroup(group, open = false) {
    const isImageGroup = group.key === 'images';
    return `
        <details class="asset-group" data-group="${escapeHtml(group.key)}" ${open ? 'open' : ''}>
            <summary>
                <span>
                    <strong>${escapeHtml(group.title)}</strong>
                    <small>${escapeHtml(group.hint || '')}</small>
                </span>
                <b>${group.items.length}</b>
            </summary>
            <div class="${isImageGroup ? 'asset-gallery' : 'asset-group-items'}">
                ${group.items.map(({ artifact, index }) => isImageGroup
                    ? renderComicImageAssetCard(artifact, index)
                    : renderComicArtifactNavItem(artifact, index)
                ).join('')}
            </div>
        </details>
    `;
}

function renderComicArtifactNavItem(a, index) {
    return `
        <button class="artifact-item" onclick="selectComicArtifact(${index})">
            <div class="artifact-item-main">
                <span class="artifact-type">${escapeHtml(comicArtifactTypeLabel(a))}</span>
                <strong>${escapeHtml(a.title)}</strong>
                <small>${escapeHtml(a.created_by || '')}</small>
            </div>
            <div class="artifact-item-flags">
                ${renderComicArtifactStatusBadge(a)}
            </div>
        </button>
    `;
}

function renderComicImageAssetCard(a, index) {
    const meta = a.metadata || {};
    return `
        <button class="asset-image-card" onclick="selectComicArtifact(${index})">
            ${a.uri ? `<img src="${escapeHtml(a.uri)}" alt="${escapeHtml(a.title)}">` : '<div class="asset-image-empty">无图</div>'}
            <span>${escapeHtml(comicImageKindLabel(meta.kind || a.artifact_type))}</span>
            <strong>${escapeHtml(meta.source_id || a.title)}</strong>
            ${renderComicArtifactStatusBadge(a)}
        </button>
    `;
}

function filterComicAssets(filterKey) {
    document.querySelectorAll('.asset-filter').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('onclick')?.includes(`'${filterKey}'`));
    });
    document.querySelectorAll('#comic-artifacts .asset-group').forEach(group => {
        const key = group.dataset.group || '';
        const show = filterKey === 'all'
            || (filterKey === 'review' && key === 'review')
            || (filterKey === 'images' && key === 'images')
            || (filterKey === 'docs' && ['script', 'asset_docs', 'shot_docs'].includes(key))
            || (filterKey === 'delivery' && key === 'delivery')
            || (filterKey === 'issues' && key === 'quality');
        group.style.display = show ? '' : 'none';
        if (show && filterKey !== 'all') group.open = true;
    });
}

function comicArtifactTypeLabel(artifact) {
    const labels = {
        asset_review_package: '资产审核',
        generated_image: '图片',
        word_canvas: 'Word',
        prompt_package: '提示词',
        image_quality_report: '质检',
        image_generation_error: '错误',
    };
    return labels[artifact.artifact_type] || artifact.artifact_type;
}

function comicImageKindLabel(kind) {
    const labels = {
        character: '人物设定',
        character_three_view: '人物三视图',
        character_expression_sheet: '表情表',
        prop_turnaround: '道具多角度',
        prop_usage_sheet: '道具使用',
        scene: '场景概念',
        scene_wide_establishing: '场景广角',
        scene_top_down_layout: '场景俯视',
        scene_layout: '场景空间',
        scene_camera_angles: '场景机位',
        storyboard: '镜头参考',
    };
    return labels[kind] || kind || '图片';
}

function latestComicAssetReviewIndex(artifacts, status = '') {
    for (let i = (artifacts || []).length - 1; i >= 0; i -= 1) {
        const artifact = artifacts[i];
        if (artifact.artifact_type !== 'asset_review_package') continue;
        const reviewStatus = (artifact.metadata || {}).review_status || 'pending';
        if (!status || reviewStatus === status) return i;
    }
    return -1;
}

function latestComicAssetReview(artifacts) {
    const index = latestComicAssetReviewIndex(artifacts);
    return index >= 0 ? { artifact: artifacts[index], index } : null;
}

function latestBlockingComicAssetReviewIndex(artifacts) {
    for (let i = (artifacts || []).length - 1; i >= 0; i -= 1) {
        const artifact = artifacts[i];
        if (artifact.artifact_type !== 'asset_review_package') continue;
        const reviewStatus = (artifact.metadata || {}).review_status || 'pending';
        if (reviewStatus !== 'approved') return i;
    }
    return -1;
}

function comicAssetReviewStatusText(status) {
    const labels = {
        pending: '待审核',
        revision_requested: '已退回',
        approved: '已通过',
    };
    return labels[status || 'pending'] || status || '待审核';
}

function renderComicAssetReviewPanel(artifacts) {
    const panel = document.getElementById('comic-asset-review-panel');
    const approveBtn = document.getElementById('comic-approve-assets-btn');
    const startBtn = document.getElementById('comic-start-production-btn');
    const statusBadge = document.getElementById('comic-asset-review-status');
    const copy = document.getElementById('comic-asset-review-copy');
    const review = latestComicAssetReview(artifacts || []);
    const status = review ? ((review.artifact.metadata || {}).review_status || 'pending') : '';
    const pending = Boolean(review && status !== 'approved');
    if (panel) panel.style.display = pending ? '' : 'none';
    if (statusBadge) {
        statusBadge.textContent = comicAssetReviewStatusText(status);
        statusBadge.className = `badge ${status === 'revision_requested' ? 'badge-err' : 'badge-info'}`;
    }
    if (copy) {
        copy.textContent = status === 'revision_requested'
            ? '这份资产拆解已经被退回。请在上方继续补充故事或资产要求，重新生成后再确认。'
            : '中书省和门下省已经把人物、道具、场景和分镜输入拆完。确认它们符合故事后，再继续生成图片和 Word 画布。';
    }
    if (approveBtn) approveBtn.style.display = pending ? '' : 'none';
    if (startBtn) {
        startBtn.textContent = pending ? '等待资产审核通过' : '生成资产拆解审核包';
        startBtn.disabled = pending;
    }
}

function focusComicAssetReview() {
    const index = latestComicAssetReviewIndex(currentComicArtifacts || []);
    if (index >= 0) {
        selectComicArtifact(index);
        document.getElementById('comic-artifact-detail')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else {
        toast('资产拆解审核包还没有生成', 'error');
    }
}

function renderComicPackageBoard(artifacts) {
    const board = document.getElementById('comic-package-board');
    const score = document.getElementById('comic-package-score');
    const items = artifacts || [];
    if (!items.length) {
        score.textContent = '未开始';
        score.className = 'badge badge-info';
        board.className = 'package-board';
        board.innerHTML = '<div class="empty-state">选择一个漫剧项目后查看剧本、资产、分镜和提示词完成度。</div>';
        return;
    }
    const byType = new Map();
    items.forEach((artifact, index) => {
        if (!byType.has(artifact.artifact_type)) byType.set(artifact.artifact_type, { artifact, index });
    });
    const ready = COMIC_REQUIRED_ARTIFACTS.filter(([type]) => byType.has(type)).length;
    const binding = latestComicScriptBinding(items);
    const invalidatedCount = items.filter(a => (a.metadata || {}).invalidated).length;
    score.textContent = `${ready}/${COMIC_REQUIRED_ARTIFACTS.length}`;
    score.className = `badge ${binding.confirmed ? 'badge-ok' : 'badge-info'}`;
    board.className = 'package-board';
    board.innerHTML = `
        <div class="package-summary">
            <strong>${binding.confirmed ? '确认稿已绑定生产链' : '当前仍在预审或局部生产阶段'}</strong>
            <span>${escapeHtml(formatComicBindingHeadline(binding, invalidatedCount))}</span>
        </div>
        <div class="package-grid">
            ${COMIC_REQUIRED_ARTIFACTS.map(([type, label]) => {
                const found = byType.get(type);
                const status = found ? 'ready' : 'missing';
                return `
                    <button class="package-item ${status}" ${found ? `onclick="selectComicArtifact(${found.index})"` : ''}>
                        <span>${escapeHtml(label)}</span>
                        <strong>${found ? '已生成' : '待创作'}</strong>
                    </button>
                `;
            }).join('')}
        </div>
    `;
}

function selectComicArtifact(index) {
    const artifact = currentComicArtifacts[index];
    if (!artifact) return;
    const detail = document.getElementById('comic-artifact-detail');
    document.querySelectorAll('#comic-artifacts .artifact-item').forEach((el, i) => {
        el.classList.toggle('active', i === index);
    });
    document.querySelectorAll('#comic-artifacts .asset-image-card').forEach(el => {
        el.classList.toggle('active', el.getAttribute('onclick')?.includes(`selectComicArtifact(${index})`));
    });
    detail.className = 'artifact-detail';
    const imagePreview = artifact.artifact_type === 'generated_image' && artifact.uri
        ? `<div class="evidence-preview"><img src="${escapeHtml(artifact.uri)}" alt="${escapeHtml(artifact.title)}"></div>`
        : '';
    const downloadAction = artifact.uri
        ? `<a class="ghost btn-sm" href="${escapeHtml(artifact.uri)}" target="_blank">下载/打开文件</a>`
        : '';
    const regenerateAction = artifact.artifact_type === 'generated_image'
        ? `<button class="ghost btn-sm" onclick="regenerateComicImage(${index})">重生成这张图</button>`
        : '';
    const assetReviewAction = artifact.artifact_type === 'asset_review_package' && (artifact.metadata || {}).review_status !== 'approved'
        ? `<button class="ghost btn-sm" onclick="requestComicAssetRevision()">退回补充</button><button class="btn-sm" onclick="approveComicAssetsAndSubmit()">确认拆解无误，继续生成</button>`
        : '';
    const bindingPanel = renderComicArtifactBinding(artifact);
    detail.innerHTML = `
        <div class="artifact-detail-head">
            <span class="artifact-type">${escapeHtml(artifact.artifact_type)}</span>
            <strong>${escapeHtml(artifact.title)}</strong>
            ${downloadAction}
            ${regenerateAction}
            ${assetReviewAction}
        </div>
        ${bindingPanel}
        ${imagePreview}
        <div class="artifact-detail-body">${simpleMarkdown(artifact.content || '') || '<em>空内容</em>'}</div>
    `;
}

async function regenerateComicImage(index) {
    const artifact = currentComicArtifacts[index];
    if (!artifact || artifact.artifact_type !== 'generated_image') return;
    const instruction = window.prompt('这张图想怎么改？例如：短发、表情更冷、服装颜色保持灰黑。', '');
    if (instruction === null) return;
    try {
        toast('正在重生成图片并进行刑部质检...', 'success');
        const result = await API.post(`/api/artifacts/${artifact.artifact_id}/regenerate-comic-image`, { instruction });
        if (result.detail) throw new Error(result.detail);
        if (result.status !== 'completed') throw new Error((result.errors || []).join('；') || '重生成失败');
        await loadComicArtifacts(currentComicWorkspace);
        toast('图片已重生成并完成质检', 'success');
    } catch (e) {
        toast('重生成失败: ' + e.message, 'error');
    }
}

async function startComicCabinet() {
    const payload = readComicFormFields();
    if (!payload.idea && !payload.script_text) {
        toast('请先输入灵感，或粘贴完整剧本', 'error');
        return;
    }
    currentComicCabinetSession = null;
    currentComicCabinetReady = false;
    currentComicScriptPreview = null;
    try {
        const result = await API.post('/api/comic/cabinet/turn', {
            ...comicPayloadForCabinet(payload),
            office_id: activeComicOfficeId(),
            workspace_id: document.getElementById('comic-workspace-select')?.value || currentComicWorkspace || '',
            user_message: '',
            session: {},
        });
        applyComicCabinetResult(result);
        toast('故事稿已生成，你可以先看故事本身', 'success');
    } catch (e) {
        toast('启动内阁讨论失败: ' + e.message, 'error');
    }
}

async function continueComicCabinet() {
    const payload = readComicFormFields();
    if (!payload.idea && !payload.script_text) {
        toast('请先输入灵感，或粘贴完整剧本', 'error');
        return;
    }
    const input = document.getElementById('comic-chat-input');
    const userMessage = input?.value.trim() || '';
    if (!userMessage && currentComicCabinetSession) {
        toast('可以随便补一句你的想法，我会继续帮你收束', 'error');
        return;
    }
    try {
        const result = await API.post('/api/comic/cabinet/turn', {
            ...comicPayloadForCabinet(payload),
            office_id: activeComicOfficeId(),
            workspace_id: currentComicWorkspace || document.getElementById('comic-workspace-select')?.value || '',
            user_message: userMessage,
            session: currentComicCabinetSession || {},
        });
        if (input) input.value = '';
        applyComicCabinetResult(result);
        toast(result.ready_to_produce ? '这版故事已经可以确认，也可以继续修' : '已根据你的补充继续完善故事', 'success');
    } catch (e) {
        toast('继续讨论失败: ' + e.message, 'error');
        // 如果后端报错返回 503 等，不会把用户的输入吃掉，保留输入让用户重试
    }
}

function applyComicCabinetResult(result) {
    currentComicWorkspace = result.workspace_id || currentComicWorkspace;
    currentComicCabinetSession = result.session || null;
    currentComicCabinetReady = Boolean(result.ready_to_produce);
    currentComicBrief = result.creative_brief || null;
    currentComicScriptPreview = result.script_preview || null;
    currentComicConfirmedScript = result.confirmed_script || null;
    renderComicCabinet();
    loadComicWorkspaces();
    if (currentComicWorkspace) {
        loadComicTimeline(currentComicWorkspace);
        loadComicArtifacts(currentComicWorkspace);
    }
}

function renderComicCabinet() {
    const chatContainer = document.getElementById('comic-chat-container');
    const chatHistory = document.getElementById('comic-chat-history');
    const proposalContainer = document.getElementById('comic-proposal-container');
    const confirmedPanel = document.getElementById('comic-confirmed-panel');
    const scriptPreview = document.getElementById('comic-script-preview');
    const confirmedPreview = document.getElementById('comic-confirmed-script');

    const hasStoryDraft = Boolean(currentComicScriptPreview?.story_draft);
    const isConfirmed = Boolean(currentComicConfirmedScript);

    if (chatContainer) {
        chatContainer.style.display = (currentComicCabinetSession && !isConfirmed) ? '' : 'none';
    }
    
    if (chatHistory && currentComicCabinetSession && currentComicCabinetSession.messages) {
        chatHistory.innerHTML = currentComicCabinetSession.messages.map(msg => {
            const roleClass = msg.role === 'user' ? 'chat-user' : 'chat-assistant';
            const roleName = msg.role === 'user' ? '你' : '主创对话官';
            return `<div class="chat-message ${roleClass}">
                <div class="chat-role">${roleName}</div>
                <div class="chat-content">${escapeHtml(msg.content)}</div>
            </div>`;
        }).join('');
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    if (proposalContainer) {
        proposalContainer.style.display = (hasStoryDraft && !isConfirmed) ? '' : 'none';
    }
    
    if (confirmedPanel) {
        confirmedPanel.style.display = isConfirmed ? '' : 'none';
    }

    if (scriptPreview) {
        scriptPreview.innerHTML = currentComicScriptPreview
            ? simpleMarkdown(formatComicStoryForDisplay(currentComicScriptPreview))
            : '';
    }
    if (confirmedPreview) {
        confirmedPreview.innerHTML = currentComicConfirmedScript
            ? simpleMarkdown(formatComicStoryForDisplay(currentComicConfirmedScript, { confirmed: true }))
            : '';
    }
}

async function confirmComicScript() {
    if (!currentComicWorkspace) {
        toast('请先在一个漫剧项目里完成内阁讨论', 'error');
        return;
    }
    if (!currentComicCabinetSession || !currentComicScriptPreview) {
        toast('请先形成当前故事稿，再进行确认', 'error');
        return;
    }
    const confirmationNotes = document.getElementById('comic-chat-input')?.value.trim() || '';
    const productionRequest = buildComicDraftProductionRequest(confirmationNotes);
    const button = document.getElementById('comic-confirm-start-btn');
    const originalText = button?.textContent || '确认故事并开始生成';
    if (button) {
        button.disabled = true;
        button.textContent = '确认中...';
    }
    try {
        toast('正在确认故事，并创建资产拆解任务...', 'success');
        const result = await API.post('/api/comic/confirm-and-start', {
            workspace_id: currentComicWorkspace,
            office_id: activeComicOfficeId(),
            session: currentComicCabinetSession,
            confirmation_notes: confirmationNotes,
            user_request: productionRequest,
        });
        if (!result.task_id) {
            throw new Error('后端没有返回任务编号，请查看日志确认任务是否创建成功。');
        }
        currentComicConfirmedScript = result.confirmed_script || null;
        if (currentComicCabinetSession) {
            currentComicCabinetSession.confirmed_script = result.confirmed_script || null;
            currentComicCabinetSession.confirmed = true;
        }
        renderComicCabinet();
        document.getElementById('comic-confirmed-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        watchComicTask(result.task_id, currentComicWorkspace);
        await loadComicWorkspaces();
        await Promise.all([
            loadComicArtifacts(currentComicWorkspace),
            loadComicTimeline(currentComicWorkspace),
        ]);
        toast(`确认版故事已锁定，资产拆解审核包正在生成：${result.task_id}`, 'success');
    } catch (e) {
        toast('确认并开始生成失败: ' + e.message, 'error');
    } finally {
        if (button) {
            button.disabled = false;
            button.textContent = originalText;
        }
    }
}

function unconfirmComicScript() {
    currentComicConfirmedScript = null;
    if (currentComicCabinetSession) {
        currentComicCabinetSession.confirmed_script = null;
        currentComicCabinetSession.confirmed = false;
    }
    renderComicCabinet();
    toast('已退回修改模式，可继续在聊天框中补充修改意见。', 'success');
}

async function submitComicTask() {
    const blockingReviewIndex = latestBlockingComicAssetReviewIndex(currentComicArtifacts || []);
    if (blockingReviewIndex >= 0) {
        focusComicAssetReview();
        toast('请先确认资产拆解包，再继续生成图片和 Word 画布', 'error');
        return;
    }
    const req = buildComicRequest();
    if (!req) return;
    try {
        const r = await API.post('/api/tasks', {
            user_request: req,
            office_id: activeComicOfficeId(),
            template_id: null,
            workspace_id: currentComicWorkspace,
        });
        currentComicWorkspace = r.workspace_id;
        toast('已开始生成漫剧制片包和 Word 画布', 'success');
        await loadComicWorkspaces();
        await Promise.all([
            loadComicArtifacts(currentComicWorkspace),
            loadComicTimeline(currentComicWorkspace),
        ]);
        watchComicTask(r.task_id, currentComicWorkspace);
    } catch (e) {
        toast('提交失败: ' + e.message, 'error');
    }
}

async function approveComicAssetsAndSubmit() {
    if (!currentComicWorkspace) {
        toast('请先选择一个漫剧项目', 'error');
        return;
    }
    try {
        const reviewerNotes = document.getElementById('comic-asset-review-notes')?.value.trim() || '';
        await API.post(`/api/workspaces/${currentComicWorkspace}/comic/asset-review/decision`, {
            status: 'approved',
            reviewer_notes: reviewerNotes,
        });
        toast('资产拆解已确认，开始继续生成图片和 Word 画布', 'success');
        await loadComicArtifacts(currentComicWorkspace);
        await submitComicTask();
    } catch (e) {
        toast('资产审核确认失败: ' + e.message, 'error');
    }
}

async function requestComicAssetRevision() {
    if (!currentComicWorkspace) {
        toast('请先选择一个漫剧项目', 'error');
        return;
    }
    const reviewerNotes = document.getElementById('comic-asset-review-notes')?.value.trim() || '';
    if (!reviewerNotes) {
        toast('请先写一句要改什么，系统才知道退回补充的方向', 'error');
        return;
    }
    try {
        await API.post(`/api/workspaces/${currentComicWorkspace}/comic/asset-review/decision`, {
            status: 'revision_requested',
            reviewer_notes: reviewerNotes,
        });
        toast('已退回资产拆解。你可以继续补充故事或资产要求后重新生成。', 'success');
        await Promise.all([
            loadComicArtifacts(currentComicWorkspace),
            loadComicTimeline(currentComicWorkspace),
        ]);
    } catch (e) {
        toast('退回资产拆解失败: ' + e.message, 'error');
    }
}

function stopComicTaskPolling() {
    if (comicTaskPoller) {
        clearInterval(comicTaskPoller);
        comicTaskPoller = null;
    }
}

function watchComicTask(taskId, workspaceId) {
    if (!taskId || !workspaceId) return;
    stopComicTaskPolling();
    let quietTicks = 0;
    const tick = async () => {
        try {
            const task = await API.get('/api/tasks/' + taskId);
            if (currentComicWorkspace !== workspaceId) return;
            await loadComicTimeline(workspaceId);
            if (task.status === 'needs_review' || task.current_phase === 'asset_review_pending') {
                stopComicTaskPolling();
                await loadComicArtifacts(workspaceId);
                focusComicAssetReview();
                toast('资产拆解审核包已生成，请先确认人物、道具、场景和分镜输入', 'success');
                return;
            }
            if (task.status === 'completed' || task.status === 'failed' || task.status === 'interrupted' || task.current_phase === 'interrupted') {
                stopComicTaskPolling();
                await loadComicArtifacts(workspaceId);
                const wordIndex = currentComicArtifacts.findIndex(a => a.artifact_type === 'word_canvas');
                if (wordIndex >= 0) selectComicArtifact(wordIndex);
                const isInterrupted = task.status === 'interrupted' || task.current_phase === 'interrupted';
                toast(
                    task.status === 'completed'
                        ? '制片包已完成，Word 画布已准备好'
                        : (isInterrupted ? '后台任务已中断，请重新提交或继续生成' : '制片包生成失败，请查看时间线'),
                    task.status === 'completed' ? 'success' : 'error'
                );
                return;
            }
            quietTicks += 1;
            if (quietTicks % 3 === 0) {
                toast('制片包还在生成中，我会自动刷新产物区', 'success');
            }
        } catch (e) {
            stopComicTaskPolling();
        }
    };
    tick();
    comicTaskPoller = setInterval(tick, 5000);
}

function buildComicRequest() {
    const fields = readComicFormFields();
    if (!fields.idea && !fields.script_text) {
        toast('请先输入灵感，或粘贴完整剧本', 'error');
        return '';
    }
    if (!currentComicCabinetSession || !currentComicBrief) {
        toast('请先和内阁把想法聊出一版方向', 'error');
        return '';
    }
    if (!currentComicScriptPreview) {
        toast('请先让内阁生成当前故事稿', 'error');
        return '';
    }
    if (!currentComicConfirmedScript) {
        toast('请先确认当前故事，再开始生成制片包', 'error');
        return '';
    }
    const answers = (currentComicCabinetSession.user_notes || []).join('\n').trim();
    const scriptNotes = '';
    const scriptSource = comicScriptSourceForRequest(fields);
    return [
        `Idea: ${fields.idea}`,
        `Genre: ${fields.genre}`,
        `Length: ${fields.length}`,
        `Platform: ${fields.platform}`,
        `Visual style: ${fields.visual_style}`,
        fields.extra ? `Extra requirements: ${fields.extra}` : '',
        scriptSource,
        'Creative brief:',
        formatComicBriefForRequest(currentComicBrief),
        answers ? `User answers: ${answers}` : 'User answers: 用户与内阁已完成多轮讨论，暂无额外补充。',
        'Script preview:',
        formatComicScriptPreviewForRequest(currentComicScriptPreview),
        'Confirmed script:',
        formatConfirmedComicScript(currentComicConfirmedScript),
        'Cabinet discussion:',
        formatComicCabinetHistoryForRequest(currentComicCabinetSession),
        scriptNotes ? `Script notes: ${scriptNotes}` : 'Script notes: 用户已确认当前故事，允许进入制片包生产。',
    ].filter(Boolean).join('\n');
}

function buildComicDraftProductionRequest(confirmationNotes = '') {
    const fields = readComicFormFields();
    const answers = (currentComicCabinetSession?.user_notes || []).join('\n').trim();
    const scriptSource = comicScriptSourceForRequest(fields);
    return [
        `Idea: ${fields.idea}`,
        `Genre: ${fields.genre}`,
        `Length: ${fields.length}`,
        `Platform: ${fields.platform}`,
        `Visual style: ${fields.visual_style}`,
        fields.extra ? `Extra requirements: ${fields.extra}` : '',
        scriptSource,
        currentComicBrief ? 'Creative brief:' : '',
        currentComicBrief ? formatComicBriefForRequest(currentComicBrief) : '',
        answers ? `User answers: ${answers}` : '',
        currentComicScriptPreview ? 'Script preview:' : '',
        currentComicScriptPreview ? formatComicScriptPreviewForRequest(currentComicScriptPreview) : '',
        'Confirmed script:',
        currentComicScriptPreview ? formatComicStoryForDisplay(currentComicScriptPreview) : '',
        confirmationNotes ? `Final confirmation notes: ${confirmationNotes}` : 'Final confirmation notes: 用户已确认当前故事，可以进入制片包生产。',
    ].filter(Boolean).join('\n');
}

function readComicFormFields() {
    const idea = document.getElementById('comic-idea')?.value.trim() || '';
    const inputMode = document.getElementById('comic-input-mode')?.value || 'idea';
    const scriptText = document.getElementById('comic-script-source')?.value.trim() || '';
    const genre = document.getElementById('comic-genre-custom')?.value.trim()
        || document.getElementById('comic-genre')?.value
        || '';
    const length = document.getElementById('comic-length-custom')?.value.trim()
        || document.getElementById('comic-length')?.value
        || '';
    const platform = document.getElementById('comic-platform-custom')?.value.trim()
        || document.getElementById('comic-platform')?.value
        || '';
    const style = document.getElementById('comic-style-custom')?.value.trim()
        || document.getElementById('comic-style')?.value
        || '';
    const extra = document.getElementById('comic-extra')?.value.trim() || '';
    const derivedIdea = idea || (inputMode === 'script' ? scriptText.split(/\n+/).find(Boolean)?.slice(0, 40) || '已有完整剧本项目' : '');
    return { idea: derivedIdea, genre, length, platform, visual_style: style, extra, input_mode: inputMode, script_text: scriptText };
}

function toggleComicInputMode() {
    const mode = document.getElementById('comic-input-mode')?.value || 'idea';
    const wrap = document.getElementById('comic-script-source-wrap');
    if (wrap) wrap.style.display = mode === 'script' ? '' : 'none';
}

function comicScriptSourceForRequest(fields) {
    if (!fields || fields.input_mode !== 'script' || !fields.script_text) return '';
    return [
        'Input mode: full_script',
        'Full script:',
        fields.script_text,
    ].join('\n');
}

function comicPayloadForCabinet(fields) {
    const scriptSource = comicScriptSourceForRequest(fields);
    return {
        ...fields,
        extra: [fields.extra || '', scriptSource].filter(Boolean).join('\n\n'),
    };
}

function formatComicBriefForRequest(brief) {
    return [
        `- 核心灵感：${brief.core_idea || ''}`,
        `- 故事承诺：${brief.story_promise || ''}`,
        `- 题材：${brief.genre || ''}`,
        `- 情绪：${brief.tone || ''}`,
        `- 主冲突：${brief.main_conflict || ''}`,
        `- 必须保留：${brief.must_keep || ''}`,
        '',
        '需要你确认的问题：',
        ...(brief.clarifying_questions || []).map((q, i) => `${i + 1}. ${q}`),
    ].filter(Boolean).join('\n');
}

function formatComicScriptPreviewForRequest(script) {
    const episodes = script.episode_outline || [];
    const cabinet = script.cabinet_review || [];
    return [
        `# ${script.title || '未命名漫剧'} 内阁剧本预审`,
        '',
        `- 一句话故事：${script.logline || ''}`,
        `- 为什么发生：${script.why_it_happens || ''}`,
        `- 如何发生：${script.how_it_happens || ''}`,
        `- 主角变化：${script.protagonist_arc || ''}`,
        '',
        '## 每集大纲',
        ...episodes.map(ep =>
            `${ep.episode}. ${ep.title}｜起因：${ep.cause}｜行动：${ep.action}｜转折：${ep.turn}｜钩子：${ep.hook}`
        ),
        '',
        '## 关键转折',
        ...(script.key_turns || []).map(turn => `- ${turn}`),
        '',
        '## 内阁意见',
        ...cabinet.map(item => `- ${item.role}：${item.verdict}（${item.reason}）`),
        '',
        `生产闸门：${script.production_gate || ''}`,
    ].filter(Boolean).join('\n');
}

function deriveComicStoryDraft(script) {
    if (!script) return '';
    if (script.story_draft) return script.story_draft;
    const lines = [];
    if (script.logline) lines.push(script.logline);
    if (script.why_it_happens) lines.push(`起因：${script.why_it_happens}`);
    if (script.how_it_happens) lines.push(`推进：${script.how_it_happens}`);
    if (script.protagonist_arc) lines.push(`人物变化：${script.protagonist_arc}`);
    const episodes = script.episode_outline || [];
    if (episodes.length) {
        lines.push('分集推进：');
        lines.push(...episodes.map(ep => {
            const label = ep.episode ? `第 ${ep.episode} 段` : '剧情段落';
            const title = ep.title ? `《${ep.title}》` : '';
            const action = ep.action || ep.cause || '';
            const hook = ep.hook ? `结尾：${ep.hook}` : '';
            return [label + title, action, hook].filter(Boolean).join('，');
        }));
    }
    return lines.filter(Boolean).join('\n\n');
}

function formatComicStoryForDisplay(script, options = {}) {
    script = script || {};
    const episodes = script.episode_outline || [];
    const story = deriveComicStoryDraft(script);
    if (!story) {
        return [
            `# ${script.title || (options.confirmed ? '已确认故事' : '当前故事稿')}`,
            '',
            options.confirmed
                ? '故事已经确认，但当前确认稿缺少可展示正文。你可以退回修改故事，或继续生成资产拆解审核包。'
                : '故事稿还没有生成完整。你可以补充一句最重要的方向，比如谁是主角、这顿饭为什么重要、结尾想留下什么感觉。',
        ].join('\n');
    }
    const lines = [
        `# ${script.title || '当前故事稿'}`,
        '',
        story,
    ];
    if (episodes.length) {
        lines.push('', '## 每集梗概');
        lines.push(...episodes.map(ep => `${ep.episode}. ${ep.title}：${ep.action || ''}${ep.hook ? `；结尾：${ep.hook}` : ''}`));
    }
    if (options.confirmed) {
        lines.push('', '## 状态');
        lines.push(`- 已确认，后续人物、场景、分镜和提示词都以这版故事为准。`);
    }
    return lines.filter(Boolean).join('\n');
}

function formatConfirmedComicScript(script) {
    script = script || {};
    const episodes = script.episode_outline || [];
    const cabinet = script.cabinet_consensus || [];
    return [
        `# ${script.title || '未命名漫剧'} 确认版剧本`,
        '',
        `- 状态：${script.status || 'confirmed'}`,
        `- 剧本版本：${script.script_version || 1}`,
        `- 剧本哈希：${script.script_hash || '待生成'}`,
        `- 故事承诺：${script.story_promise || ''}`,
        `- 主冲突：${script.main_conflict || ''}`,
        `- 一句话故事：${script.logline || ''}`,
        `- 为什么发生：${script.why_it_happens || ''}`,
        `- 如何发生：${script.how_it_happens || ''}`,
        `- 主角变化：${script.protagonist_arc || ''}`,
        `- 平台：${script.platform || ''}`,
        `- 视觉风格：${script.visual_style || ''}`,
        script.script_hash ? `- 返工提示：若后续确认稿哈希变化，旧资产会自动标记为待返工。` : '',
        '',
        '## 每集确认大纲',
        ...episodes.map(ep =>
            `${ep.episode}. ${ep.title}｜起因：${ep.cause}｜行动：${ep.action}｜转折：${ep.turn}｜钩子：${ep.hook}`
        ),
        '',
        '## 内阁共识',
        ...cabinet.map(item => `- ${item.role}：${item.verdict}｜${item.comment}`),
        '',
        '## 用户最终要求',
        script.confirmation_notes || '用户认可当前剧本方向，未追加新的最终修改说明。',
        '',
        `生产闸门：${script.production_gate || ''}`,
    ].filter(Boolean).join('\n');
}

function latestComicScriptBinding(artifacts) {
    const confirmedArtifact = [...(artifacts || [])].reverse().find(a => a.artifact_type === 'confirmed_script');
    const anyBoundArtifact = [...(artifacts || [])].reverse().find(a => (a.metadata || {}).script_hash);
    const source = confirmedArtifact || anyBoundArtifact || {};
    const metadata = source.metadata || {};
    return {
        script_hash: metadata.script_hash || currentComicConfirmedScript?.script_hash || '',
        script_version: metadata.script_version || currentComicConfirmedScript?.script_version || 0,
        confirmed: Boolean(metadata.script_confirmed ?? metadata.confirmed ?? currentComicConfirmedScript?.status === 'confirmed'),
        source_type: metadata.script_source_type || (currentComicConfirmedScript ? 'confirmed_script' : ''),
        confirmed_script_artifact_id: metadata.confirmed_script_artifact_id || '',
    };
}

function formatComicBindingHeadline(binding, invalidatedCount = 0) {
    if (!binding.script_hash) return '当前还没有绑定到明确的脚本版本。';
    const sourceLabel = binding.source_type === 'confirmed_script' ? '确认故事稿' : (binding.source_type === 'script_preview' ? '故事预审稿' : '当前稿');
    const invalidatedText = invalidatedCount ? ` 当前有 ${invalidatedCount} 个旧资产已标记待返工。` : '';
    return `当前绑定 ${sourceLabel} v${binding.script_version || 0} / ${binding.script_hash}${binding.confirmed ? '，后续资产应保持同一来源。' : '，建议先确认剧本再扩产。'}${invalidatedText}`;
}

function renderComicArtifactBinding(artifact) {
    const metadata = artifact.metadata || {};
    const binding = metadata.binding || {};
    const lines = [];
    if (metadata.script_hash) lines.push(['脚本版本', `v${metadata.script_version || 0} / ${metadata.script_hash}`]);
    if ('script_confirmed' in metadata) lines.push(['脚本状态', metadata.script_confirmed ? '已确认' : '仅预审稿']);
    if (metadata.invalidated) lines.push(['返工状态', '待返工 / 已过期']);
    if (metadata.invalidated_reason) lines.push(['过期原因', metadata.invalidated_reason]);
    if (metadata.current_script_hash) lines.push(['当前有效脚本', `v${metadata.current_script_version || 0} / ${metadata.current_script_hash}`]);
    if (metadata.script_source_type) lines.push(['来源', metadata.script_source_type === 'confirmed_script' ? 'confirmed_script / 确认稿' : metadata.script_source_type]);
    if (metadata.confirmed_script_artifact_id) lines.push(['确认稿产物', metadata.confirmed_script_artifact_id]);
    if (metadata.source_id) lines.push(['源资产 ID', metadata.source_id]);
    if (metadata.replaced_by_artifact_id) lines.push(['替代产物', metadata.replaced_by_artifact_id]);
    if (binding.anchor_id) lines.push(['锚点', binding.anchor_id]);
    if (binding.beat_id) lines.push(['Beat', `${binding.beat_id}${binding.beat_name ? ` / ${binding.beat_name}` : ''}`]);
    if (binding.scene_id) lines.push(['场景锚点', binding.scene_id]);
    if ((binding.character_ids || []).length) lines.push(['人物绑定', binding.character_ids.join('、')]);
    if ((binding.prop_ids || []).length) lines.push(['道具绑定', binding.prop_ids.join('、')]);
    if (!lines.length) return '';
    return `
        <div class="artifact-binding-panel">
            <div class="artifact-binding-head">
                <strong>绑定信息</strong>
                <span>${escapeHtml(comicArtifactReworkHint(metadata, binding))}</span>
            </div>
            <div class="artifact-binding-grid">
                ${lines.map(([label, value]) => `
                    <div class="artifact-binding-item">
                        <span>${escapeHtml(label)}</span>
                        <code>${escapeHtml(value)}</code>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
}

function comicArtifactReworkHint(metadata, binding) {
    if (metadata.replaced_by_artifact_id) return `这个资产已被 ${metadata.replaced_by_artifact_id} 替代。`;
    if (metadata.invalidated) return '当前确认稿已经变化，这个资产需要核对后返工。';
    if (!metadata.script_hash) return '这个资产还没有建立明确脚本绑定。';
    if (!metadata.script_confirmed) return '当前资产仍基于预审稿，建议先确认剧本再继续扩产。';
    if (binding.beat_id || binding.anchor_id) return '若剧本修改，优先按当前锚点做局部返工。';
    return '若确认稿变更，请先核对 script_hash 再决定是否返工。';
}

function renderComicArtifactStatusBadge(artifact) {
    const metadata = artifact.metadata || {};
    if (artifact.artifact_type === 'asset_review_package') {
        return metadata.review_status === 'approved'
            ? '<span class="badge badge-ok">资产已确认</span>'
            : '<span class="badge badge-info">待你确认</span>';
    }
    if (metadata.replaced_by_artifact_id) {
        return '<span class="badge badge-info">已替代</span>';
    }
    if (metadata.invalidated) {
        return '<span class="badge badge-err">待返工</span>';
    }
    if (metadata.script_confirmed) {
        return '<span class="badge badge-ok">已绑定</span>';
    }
    if (metadata.script_hash) {
        return '<span class="badge badge-info">预审绑定</span>';
    }
    return '';
}

function formatComicUserQuestions(session) {
    const questions = session?.story_state?.questions || [];
    if (!questions.length) {
        return [
            '## 还需要一点信息',
            '',
            '请补充你最在意的一点，比如主角是谁、这件事为什么发生、结尾想要什么感受。',
        ].join('\n');
    }
    return [
        '## 还需要一点信息',
        '',
        '你随便补一句就行，不用像填问卷：',
        '',
        ...questions.slice(0, 2).map(question => `- ${escapeMarkdown(question)}`),
    ].join('\n');
}

function formatComicCabinetHistoryForRequest(session) {
    const messages = (session?.messages || []).slice(-10);
    if (!messages.length) return 'Cabinet history: 尚无记录。';
    return messages.map(item => {
        if (item.role !== 'assistant') return `User: ${item.content || ''}`;
        const roleLines = (item.cabinet_roles || []).map(member =>
            `Cabinet-${member.role || '顾问'}: ${member.comment || ''}${member.question ? `｜追问：${member.question}` : ''}`
        );
        return [...roleLines, `Cabinet-summary: ${item.content || ''}`].join('\n');
    }).join('\n');
}

function escapeMarkdown(text) {
    return String(text || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
function exportComicWorkspace() {
    if (!currentComicWorkspace) {
        toast('请先选择漫剧项目', 'error');
        return;
    }
    window.location.href = `/api/workspaces/${currentComicWorkspace}/export`;
}

// ============================================================
// Tools
// ============================================================
async function loadTools() {
    const el = document.getElementById('tools-list');
    el.innerHTML = '<div class="card muted-card">正在读取工具注册表...</div>';
    try {
        const data = await API.get('/api/tools');
        const tools = data.tools || [];
        if (!tools.length) {
            el.innerHTML = '<div class="empty-state">还没有注册可用工具。</div>';
            return;
        }
        el.innerHTML = '<div class="card" style="padding:0">' +
            tools.map(t => {
                const badge = toolBadge(t.name);
                const params = t.parameters || [];
                return `
            <div class="tool-item">
                <div class="tool-icon">${badge.icon}</div>
                <div class="tool-info">
                    <h4>${escapeHtml(t.name)} <span class="agent-tag">${badge.label}</span></h4>
                    <p>${escapeHtml(t.description || '')}</p>
                    <div class="tool-params">
                        ${params.length ? params.map(p => '<code>' + escapeHtml(p) + '</code>').join(' ') : '<code>无参数</code>'}
                    </div>
                </div>
            </div>
                `;
            }).join('') + '</div>';
    } catch (e) {
        el.innerHTML = '<div class="empty-state">工具注册表读取失败。</div>';
        toast('工具读取失败: ' + e.message, 'error');
    }
}

function toolBadge(name) {
    if (name.includes('feigua')) return { icon: '飞', label: '飞瓜取证' };
    if (name.includes('scrapling')) return { icon: '抓', label: '增强抓取' };
    if (name.includes('browser')) return { icon: '窗', label: '浏览器' };
    if (name.includes('web_')) return { icon: '搜', label: '联网' };
    return { icon: '工', label: '工具' };
}

async function uploadTool(event) {
    const file = event.target.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    try {
        const res = await fetch('/api/tools/upload', { method: 'POST', body: formData });
        if (res.ok) {
            toast('工具上传成功', 'success');
            loadTools();
        } else {
            toast('上传失败', 'error');
        }
    } catch (e) {
        toast('上传出错', 'error');
    }
    event.target.value = '';
}

// ============================================================
// Skills (formerly Templates)
// ============================================================
async function loadSkills() {
    const data = await API.get('/api/templates');
    const templates = data.templates || [];
    document.getElementById('skills-list').innerHTML = '<div class="card" style="padding:0">' +
        templates.map(t => `
            <div class="skill-item">
                <div>
                    <h4>${escapeHtml(t.name)} <code style="font-weight:normal">${escapeHtml(t.id)}</code> <span class="agent-tag">${t.source === 'custom' ? '自定义 Skill' : '系统 Skill'}</span></h4>
                    <div class="skill-meta">${escapeHtml(t.description || '')}</div>
                </div>
                <button class="btn-sm btn-ghost" onclick="deleteSkill('${t.id}')">删除</button>
            </div>
        `).join('') + '</div>';
    loadSkillSelect();
}

async function createSkill() {
    const name = document.getElementById('new-skill-name').value.trim();
    const desc = document.getElementById('new-skill-desc').value.trim();
    const prompt = document.getElementById('new-skill-prompt').value.trim();
    if (!name) { toast('请输入名称', 'error'); return; }
    const id = name.replace(/[^a-zA-Z0-9一-鿿]/g, '_').toLowerCase();
    await API.post('/api/templates', { id, name, description: desc, default_prompt: prompt });
    toast('技能已创建', 'success');
    document.getElementById('new-skill-name').value = '';
    document.getElementById('new-skill-desc').value = '';
    document.getElementById('new-skill-prompt').value = '';
    loadSkills();
}

async function deleteSkill(id) {
    // TBD: add delete endpoint
}

async function loadSkillSelect() {
    try {
        const data = await API.get('/api/templates');
        const sel = document.getElementById('skill-select');
        sel.innerHTML = '<option value="">直接输入需求</option>' +
            (data.templates || []).map(t => `<option value="${t.id}">${t.name}</option>`).join('');
    } catch (e) {}
}

async function uploadSkill(event) {
    const file = event.target.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    try {
        const res = await fetch('/api/templates/upload', { method: 'POST', body: formData });
        if (res.ok) {
            toast('技能上传成功', 'success');
            loadSkills();
        } else {
            toast('上传失败', 'error');
        }
    } catch (e) {
        toast('上传出错', 'error');
    }
    event.target.value = '';
}

// ============================================================
// Models
// ============================================================
const PROVIDER_MODELS = {
    deepseek: ['deepseek-chat', 'deepseek-reasoner'],
    openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4.1', 'gpt-4.1-mini', 'gpt-4.1-nano', 'o3', 'o4-mini'],
    anthropic: ['claude-sonnet-4-6', 'claude-sonnet-4-5', 'claude-opus-4-7', 'claude-haiku-4-5'],
    gemini: ['gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-2.5-flash-lite'],
    dashscope: ['qwen-vl-max', 'qwen-vl-plus', 'qwen-max', 'qwen-plus', 'qwen-turbo'],
    doubao: ['doubao-seedream-5', 'doubao-seedream-5-0', 'doubao-seedream-4-5', 'doubao-seedream-4-0'],
    minimax: ['MiniMax-M2.7', 'MiniMax-M2.7-highspeed', 'MiniMax-M2.5', 'MiniMax-M2.5-highspeed', 'MiniMax-M2.1', 'MiniMax-M2.1-highspeed', 'MiniMax-M2'],
    openrouter: ['anthropic/claude-sonnet-4.5', 'openai/gpt-4o', 'google/gemini-2.5-pro', 'qwen/qwen-2.5-vl-72b-instruct'],
    ollama: ['llama3.1', 'llama3.2-vision', 'qwen2.5', 'qwen2.5vl', 'mistral', 'gemma3'],
};

const PROVIDER_BRANDS = {
    deepseek: { label: 'DeepSeek', mark: '深', className: 'deepseek' },
    openai: { label: 'OpenAI', mark: 'AI', className: 'openai' },
    anthropic: { label: 'Anthropic', mark: 'A', className: 'anthropic' },
    gemini: { label: 'Gemini', mark: 'G', className: 'gemini' },
    dashscope: { label: '通义千问', mark: 'Q', className: 'dashscope' },
    doubao: { label: '豆包', mark: '豆', className: 'doubao' },
    minimax: { label: 'MiniMax', mark: 'MM', className: 'minimax' },
    openrouter: { label: 'OpenRouter', mark: 'OR', className: 'openrouter' },
    ollama: { label: 'Ollama', mark: 'O', className: 'ollama' },
};

function providerBrand(provider) {
    return PROVIDER_BRANDS[provider] || { label: provider, mark: provider.slice(0, 2).toUpperCase(), className: 'default' };
}

function providerLogoHtml(provider) {
    const brand = providerBrand(provider);
    return `<span class="provider-logo provider-${brand.className}">${escapeHtml(brand.mark)}</span>`;
}

const AGENT_NAMES = {
    zhongshu: '中书省', menxia: '门下省', shangshu: '尚书省',
    libu: '吏部', hubu: '户部', libu_comm: '礼部',
    bingbu: '兵部', xingbu: '刑部', gongbu: '工部',
};

const AGENT_DESC = {
    zhongshu: '起草方案', menxia: '审议方案', shangshu: '调度执行',
    libu: '记忆检索', hubu: '数据管理', libu_comm: '通信接入',
    bingbu: '执行操作', xingbu: '质量验证', gongbu: '产出报告',
};

const OFFICE_AGENT_DESC = {
    research: {
        zhongshu: '调研方案',
        menxia: '调研审议',
        shangshu: '流程统筹',
        libu: '资料归档',
        hubu: '数据表格',
        libu_comm: '交接说明',
        bingbu: '平台取证',
        xingbu: '证据质检',
        gongbu: '报告产出',
    },
    comic_production: {
        zhongshu: '任务拆解',
        menxia: '资产审议',
        shangshu: '制片调度',
        libu: '连续性',
        hubu: '资产台账',
        libu_comm: '交付说明',
        bingbu: '分镜生图',
        xingbu: '视觉质检',
        gongbu: '资产组装',
    },
};

function agentDesc(id) {
    return ((OFFICE_AGENT_DESC[MODEL_OFFICE_ID] || {})[id]) || AGENT_DESC[id] || '';
}

const MODEL_REQUIREMENTS = {
    default: {
        zhongshu: { type: '文本推理模型', key: 'DeepSeek / 千问 / GPT 等文本 API Key', use: '理解用户任务，起草方案和任务结构。' },
        menxia: { type: '文本推理模型', key: 'DeepSeek / 千问 / GPT 等文本 API Key', use: '审查方案漏洞、遗漏项和风险。' },
        shangshu: { type: '文本推理模型', key: 'DeepSeek / 千问 / GPT 等文本 API Key', use: '统筹多部门执行顺序和交付状态。' },
        libu: { type: '文本推理模型', key: 'DeepSeek / 千问 / GPT 等文本 API Key', use: '整理上下文、历史记忆和规则。' },
        hubu: { type: '文本推理模型', key: 'DeepSeek / 千问 / GPT 等文本 API Key', use: '结构化数据、表格和资产台账。' },
        libu_comm: { type: '文本推理模型', key: 'DeepSeek / 千问 / GPT 等文本 API Key', use: '整理给人的交接说明和状态更新。' },
        bingbu: { type: '文本推理模型', key: 'DeepSeek / 千问 / GPT 等文本 API Key', use: '执行检索、采集、分镜或操作计划。' },
        xingbu: { type: '文本/视觉质检模型', key: '普通任务可用文本 Key；涉及图片时建议千问 VL / GPT 多模态 Key', use: '检查来源、逻辑、图片或交付完整度。' },
        gongbu: { type: '文本生成模型', key: 'DeepSeek / 千问 / GPT 等文本 API Key', use: '撰写报告、提示词和最终材料。' },
    },
    research: {
        hubu: { type: '文本 + 数据整理模型', key: 'DeepSeek / 千问 / GPT 等文本 API Key', use: '整理竞品表、价格带、销量字段和评论痛点。' },
        bingbu: { type: '文本 + 网页取证辅助模型', key: 'DeepSeek / 千问 / GPT 等文本 API Key；截图识别建议千问 VL', use: '规划平台数据采集、截图目标和证据提取。' },
        xingbu: { type: '文本/视觉质检模型', key: '普通质检用文本 Key；截图识别建议千问 VL API Key', use: '核验数据年份、来源质量、截图内容和报告完整度。' },
        gongbu: { type: '文本生成模型', key: 'DeepSeek / 千问 / GPT 等文本 API Key', use: '生成调研报告、老板简报、表格和可导出材料。' },
    },
    comic_production: {
        neige: { type: '文本创作模型', key: 'DeepSeek / 千问 / GPT 等文本 API Key', use: '和人对话，确认故事合约。' },
        zhongshu: { type: '文本编剧/拆解模型', key: 'DeepSeek / 千问 / GPT 等文本 API Key', use: '把确认故事拆成生产任务书。' },
        menxia: { type: '文本审稿模型', key: 'DeepSeek / 千问 / GPT 等文本 API Key', use: '审核故事、人物、道具、场景和分镜是否缺漏。' },
        shangshu: { type: '文本调度模型', key: 'DeepSeek / 千问 / GPT 等文本 API Key', use: '把制片模板分派给各部门并追踪阻塞。' },
        libu: { type: '文本连续性模型', key: 'DeepSeek / 千问 / GPT 等文本 API Key', use: '维护人物、道具、场景和版本连续性。' },
        hubu: { type: '文本/结构化资产模型', key: 'DeepSeek / 千问 / GPT 等文本 API Key', use: '维护资产登记表和资源台账。' },
        libu_comm: { type: '文本交付模型', key: 'DeepSeek / 千问 / GPT 等文本 API Key', use: '整理给下游生图、视频和剪辑平台的交接说明。' },
        bingbu: { type: '文本镜头模型', key: 'DeepSeek / 千问 / GPT 等文本 API Key', use: '生成镜头画面提示词和视频生成提示词，不负责生图。' },
        xingbu: { type: '视觉理解/质检模型', key: '千问 VL / GPT 多模态等图片理解 API Key', use: '检查生成图是否符合人物、道具、场景和画风一致性。' },
        gongbu: { type: '生图模型 + 文本组装', key: '豆包 Seedream / 火山方舟等生图 API Key；文本组装可复用文本模型', use: '生成人物图、道具图、场景图，并组装 Word 制片画布。' },
    },
};

function modelRequirement(agentId) {
    return {
        ...(MODEL_REQUIREMENTS.default[agentId] || {}),
        ...((MODEL_REQUIREMENTS[MODEL_OFFICE_ID] || {})[agentId] || {}),
    };
}

function agentName(id) {
    return AGENT_NAMES[id] || id;
}

async function loadModels() {
    const officeLabel = document.getElementById('model-office-label');
    if (officeLabel) officeLabel.textContent = `当前：${OFFICE_LABELS[MODEL_OFFICE_ID] || OFFICE_LABELS.research}`;
    const data = await API.get('/api/config/models?office_id=' + encodeURIComponent(MODEL_OFFICE_ID));
    const models = data.models || {};
    const el = document.getElementById('model-list');
    el.innerHTML = Object.entries(AGENT_NAMES).map(([id, name]) => {
        const cfg = models[id] || {};
        const prov = cfg.provider || 'deepseek';
        const curModel = cfg.model || 'deepseek-chat';
        const modelsForProvider = PROVIDER_MODELS[prov] || [];
        const requirement = modelRequirement(id);
        const hasAdvanced = cfg.api_base || (cfg.temperature && cfg.temperature !== 0.3) || (cfg.max_tokens && cfg.max_tokens !== 4096);
        return `
        <div class="card model-card">
            <div class="model-card-head">
                <h4>${name} <span class="agent-tag">${escapeHtml(agentDesc(id))}</span></h4>
                <span id="model-test-status-${id}" class="badge badge-info model-test-status">未测试</span>
            </div>
            <div class="model-requirement">
                <strong>需要：${escapeHtml(requirement.type || '文本模型')}</strong>
                <span>${escapeHtml(requirement.key || '填写对应模型供应商的 API Key')}</span>
                <p>${escapeHtml(requirement.use || '')}</p>
            </div>
            <div class="form-row">
                <div>
                    <label>Provider</label>
                    <select onchange="onProviderChange('${id}', this.value)" data-agent="${id}">
                        ${Object.keys(PROVIDER_MODELS).map(p =>
                        `<option value="${p}" ${prov === p ? 'selected' : ''}>${providerBrand(p).label}</option>`
                    ).join('')}
                    </select>
                </div>
                <div>
                    <label>Model</label>
                    <select onchange="updateModel('${id}', 'model', this.value)" data-agent="${id}" data-field="model">
                        ${modelsForProvider.map(m => `<option value="${m}" ${curModel === m ? 'selected' : ''}>${m}</option>`).join('')}
                    </select>
                </div>
                <div>
                    <label>API Key</label>
                    <input type="password" value="${cfg.api_key || ''}" placeholder="sk-..." onchange="updateModel('${id}', 'api_key', this.value)">
                </div>
            </div>
            <div class="model-card-actions">
                <button class="btn-ghost btn-sm" onclick="testModel('${id}', this)">测试此部门</button>
                <span id="model-test-detail-${id}" class="model-test-detail">测试会进行一次最小调用；生图部门会生成一张测试图。</span>
            </div>
            <span class="advanced-toggle" onclick="toggleAdvanced('${id}')">${hasAdvanced ? '▼' : '▶'} 高级选项</span>
            <div class="advanced-row" id="advanced-${id}" style="${hasAdvanced ? '' : 'display:none'}">
                <div class="form-row">
                    <div>
                        <label>Temperature (0-2)</label>
                        <input type="text" value="${cfg.temperature ?? 0.3}" placeholder="0.3" onchange="updateModel('${id}', 'temperature', parseFloat(this.value)||0.3)">
                    </div>
                    <div>
                        <label>Max Tokens</label>
                        <input type="text" value="${cfg.max_tokens ?? 4096}" placeholder="4096" onchange="updateModel('${id}', 'max_tokens', parseInt(this.value)||4096)">
                    </div>
                    <div>
                        <label>API Base (自定义端点)</label>
                        <input type="text" value="${cfg.api_base || ''}" placeholder="仅本地/Ollama 需要" onchange="updateModel('${id}', 'api_base', this.value)">
                    </div>
                </div>
            </div>
        </div>`;
    }).join('');
}

function toggleAdvanced(agentId) {
    const row = document.getElementById('advanced-' + agentId);
    row.style.display = row.style.display === 'none' ? '' : 'none';
    const toggle = row.previousElementSibling;
    toggle.textContent = (row.style.display === 'none' ? '▶' : '▼') + ' 高级选项';
}

async function onProviderChange(agentId, provider) {
    const card = document.querySelector(`[data-agent="${agentId}"]`).closest('.model-card');
    const modelSelect = card.querySelector('[data-field="model"]');
    const keyInput = card.querySelector('input[type="password"]');
    const models = PROVIDER_MODELS[provider] || [];
    modelSelect.innerHTML = models.map(m => `<option value="${m}">${m}</option>`).join('');
    if (keyInput) keyInput.value = '';
    await updateModel(agentId, 'provider', provider);
    await updateModel(agentId, 'model', models[0] || '');
}

async function updateModel(agentId, key, value) {
    const body = {}; body[key] = value;
    const result = await API.put('/api/config/models/' + agentId + '?office_id=' + encodeURIComponent(MODEL_OFFICE_ID), body);
    if (result.warnings && result.warnings.length) {
        toast('已清空旧 API Key，请填写当前供应商的 Key 后测试。', 'error');
    }
    setModelTestState(agentId, { status: 'not_run', detail: '配置已保存，建议重新测试。' });
    return result;
}

async function testModel(agentId, button) {
    const original = button ? button.textContent : '';
    if (button) {
        button.disabled = true;
        button.textContent = '测试中...';
    }
    setModelTestState(agentId, { status: 'running', detail: '正在连接模型服务...' });
    try {
        const result = await API.post('/api/config/models/' + agentId + '/test?office_id=' + encodeURIComponent(MODEL_OFFICE_ID), {});
        setModelTestState(agentId, result);
        toast(`${agentName(agentId)}：${modelStatusText(result)}`, result.status === 'ok' ? 'success' : 'error');
        return result;
    } catch (e) {
        const result = { status: 'error', detail: e.message || String(e) };
        setModelTestState(agentId, result);
        toast(`${agentName(agentId)}：测试失败`, 'error');
        return result;
    } finally {
        if (button) {
            button.disabled = false;
            button.textContent = original || '测试此部门';
        }
    }
}

async function testAllModels() {
    const button = document.getElementById('btn-test-all-models');
    if (button) {
        button.disabled = true;
        button.textContent = '测试中...';
    }
    Object.keys(AGENT_NAMES).forEach(id => setModelTestState(id, { status: 'running', detail: '等待测试结果...' }));
    try {
        const data = await API.post('/api/config/models/test?office_id=' + encodeURIComponent(MODEL_OFFICE_ID), {});
        const results = data.results || [];
        results.forEach(item => setModelTestState(item.agent, item));
        const failed = results.filter(item => item.status !== 'ok');
        toast(failed.length ? `有 ${failed.length} 个部门需要检查` : '当前办公室全部部门测试通过', failed.length ? 'error' : 'success');
    } catch (e) {
        toast('一键测试失败：' + (e.message || e), 'error');
    } finally {
        if (button) {
            button.disabled = false;
            button.textContent = '测试当前办公室全部部门';
        }
    }
}

function setModelTestState(agentId, result) {
    const statusEl = document.getElementById('model-test-status-' + agentId);
    const detailEl = document.getElementById('model-test-detail-' + agentId);
    if (statusEl) {
        statusEl.className = `badge ${modelStatusClass(result.status)} model-test-status`;
        statusEl.textContent = modelStatusText(result);
    }
    if (detailEl) {
        detailEl.textContent = modelStatusDetail(result);
    }
}

function modelStatusClass(status) {
    if (status === 'ok') return 'badge-ok';
    if (['missing_key', 'api_error', 'error', 'timeout'].includes(status)) return 'badge-err';
    return 'badge-info';
}

function modelStatusText(result) {
    const status = result.status || 'not_run';
    const kind = result.kind === 'image' ? '生图' : result.kind === 'vision' ? '视觉' : '文本';
    if (status === 'ok') return `${kind}通过`;
    if (status === 'running') return '测试中';
    if (status === 'missing_key') return '未配置';
    if (status === 'api_error') return '接口失败';
    if (status === 'timeout') return '超时';
    if (status === 'empty_response') return '空响应';
    if (status === 'not_run') return '未测试';
    return '失败';
}

function modelStatusDetail(result) {
    if (result.status === 'ok') return result.detail || '模型已连通。';
    if (result.status === 'missing_key') return 'API Key 为空，请先填写并保存。';
    if (result.status === 'running') return result.detail || '正在测试...';
    if (result.status === 'not_run') return result.detail || '测试会进行一次最小调用；生图部门会生成一张测试图。';
    return result.detail || '请检查供应商、模型名称和 API Key 是否匹配。';
}

// ============================================================
// Prompts
// ============================================================
let currentPromptAgent = 'zhongshu';

async function loadPrompts() {
    const data = await API.get('/api/prompts');
    const agents = data.agents || [];
    const el = document.getElementById('prompt-agent-list');
    el.innerHTML = agents.map(a => `
        <div class="agent-item ${a.id === currentPromptAgent ? 'active' : ''}" onclick="selectPrompt('${a.id}')">
            ${a.name} ${a.is_custom ? '<span class="badge badge-info">已自定义</span>' : ''}
        </div>
    `).join('');
    if (agents.length) selectPrompt(currentPromptAgent);
}

async function selectPrompt(agent) {
    currentPromptAgent = agent;
    document.querySelectorAll('#prompt-agent-list .agent-item').forEach(el => {
        el.classList.toggle('active', el.textContent.includes(AGENT_NAMES[agent] || agent));
    });
    const data = await API.get('/api/prompts/' + agent);
    document.getElementById('prompt-editor-title').textContent = AGENT_NAMES[agent] || agent;
    document.getElementById('prompt-editor-textarea').value = data.text;
}

async function savePrompt() {
    const text = document.getElementById('prompt-editor-textarea').value;
    await API.put('/api/prompts/' + currentPromptAgent, { text });
    toast('提示词已保存', 'success');
    loadPrompts();
}

async function resetPrompt() {
    await API.del('/api/prompts/' + currentPromptAgent);
    toast('已恢复默认', 'success');
    selectPrompt(currentPromptAgent);
}

// ============================================================
// History
// ============================================================
async function loadHistory() {
    const data = await API.get('/api/tasks/history?limit=50');
    const el = document.getElementById('history-list');
    el.innerHTML = (data.history || []).map(h => `
        <tr>
            <td><code>${h.task_id}</code></td>
            <td>
                <strong>${escapeHtml(h.workspace_title || '')}</strong>
                <div>${escapeHtml((h.user_request || '').substring(0, 120))}</div>
                <small>${escapeHtml(historyArtifactSummary(h))}</small>
            </td>
            <td><span class="badge badge-${h.status === 'completed' ? 'ok' : 'err'}">${h.status}</span></td>
            <td>${escapeHtml((h.completed_at || h.updated_at || h.created_at || '').replace('T',' ').substring(0,16))}</td>
            <td>
                <button class="btn-sm" onclick="viewHistoryDetail('${h.task_id}')">查看完整</button>
                ${h.word_canvas_uri ? `<a class="btn-sm ghost" href="${escapeHtml(h.word_canvas_uri)}" target="_blank">下载Word画布</a>` : ''}
                ${h.workspace_export_uri ? `<a class="btn-sm ghost" href="${escapeHtml(h.workspace_export_uri)}" target="_blank">导出全部</a>` : ''}
            </td>
        </tr>
        <tr id="history-detail-${h.task_id}" style="display:none">
            <td colspan="5"><div class="artifact-detail"></div></td>
        </tr>
    `).join('');
}

function historyArtifactSummary(h) {
    const count = h.artifact_count || 0;
    const word = h.word_canvas_uri ? '，含 Word 画布' : '';
    const office = h.office_id ? `${h.office_id}办公室` : '工作区';
    return `${office} · ${count} 个产物${word}`;
}

async function viewHistoryDetail(taskId) {
    const row = document.getElementById('history-detail-' + taskId);
    if (!row) return;
    const box = row.querySelector('.artifact-detail');
    if (row.style.display === '') {
        row.style.display = 'none';
        return;
    }
    row.style.display = '';
    box.innerHTML = '<div class="empty-state">正在读取完整记录...</div>';
    try {
        const history = await API.get('/api/tasks/history?limit=100');
        const item = (history.history || []).find(h => h.task_id === taskId) || {};
        const task = await API.get('/api/tasks/' + taskId);
        const artifacts = item.artifacts || [];
        const report = item.final_report_preview || task.result?.final_report || '';
        box.innerHTML = `
            <div class="artifact-detail-head">
                <span class="artifact-type">${escapeHtml(item.office_id || '')}</span>
                <strong>${escapeHtml(item.workspace_title || item.user_request || taskId)}</strong>
                ${item.word_canvas_uri ? `<a class="ghost btn-sm" href="${escapeHtml(item.word_canvas_uri)}" target="_blank">下载Word画布</a>` : ''}
                ${item.workspace_export_uri ? `<a class="ghost btn-sm" href="${escapeHtml(item.workspace_export_uri)}" target="_blank">导出全部</a>` : ''}
            </div>
            <div class="artifact-detail-body">
                ${report ? simpleMarkdown(report) : '<em>暂无最终报告预览</em>'}
                <h4>产物清单</h4>
                <ul>
                    ${artifacts.map(a => `<li><strong>${escapeHtml(a.artifact_type)}</strong> · ${escapeHtml(a.title || '')} ${a.uri ? `<a href="${escapeHtml(a.uri)}" target="_blank">打开</a>` : ''}</li>`).join('')}
                </ul>
            </div>
        `;
    } catch (e) {
        box.innerHTML = '<div class="empty-state">读取失败：' + escapeHtml(e.message) + '</div>';
    }
}

async function viewReport(taskId) {
    const data = await API.get('/api/tasks/' + taskId + '/report');
    
    // Hide welcome screen
    const welcome = document.getElementById('welcome-screen');
    if (welcome) welcome.style.display = 'none';
    
    document.getElementById('result-card').style.display = '';
    document.getElementById('result-task-id').textContent = taskId;
    document.getElementById('result-status').innerHTML = '<span class="badge badge-ok">' + (data.status || '') + '</span>';
    document.getElementById('result-content').innerHTML = simpleMarkdown(data.report) || '<em>无报告</em>';
    document.getElementById('result-files').innerHTML = '';
    loadTaskFiles(taskId);
    navigate('task');
    const scrollArea = document.querySelector('.chat-scroll-area');
    if (scrollArea) {
        scrollArea.scrollTo({ top: 0, behavior: 'smooth' });
    }
}

// ============================================================
// Init
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
    refreshOfficeChrome();
    loadSkillSelect();
    document.getElementById('task-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            submitTask();
        }
    });
    navigate('offices');
});
