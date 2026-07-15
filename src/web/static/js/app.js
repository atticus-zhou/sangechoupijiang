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
        const error = new Error(message);
        error.detail = detail;
        error.status = response.status;
        throw error;
    }
    return payload;
}

function formatApiError(error) {
    const detail = error?.detail;
    if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
        const parts = [];
        if (detail.department) parts.push(`${detail.department}`);
        if (detail.reason) parts.push(`原因：${detail.reason}`);
        if (detail.impact) parts.push(`影响：${detail.impact}`);
        if (detail.next_action) parts.push(`下一步：${detail.next_action}`);
        return parts.length ? parts.join('；') : (error.message || '请求失败');
    }
    if (Array.isArray(detail)) return detail.join('；');
    return error?.message || String(error || '请求失败');
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
const OFFICE_HALL_PREFLIGHTS = [
    { officeId: 'research', targetId: 'office-availability-research' },
    { officeId: 'comic_production', targetId: 'office-availability-comic-production' },
];
const OFFICE_HALL_LAUNCH_GATES = ['comic_production', 'research', 'comic'];

let ACTIVE_OFFICE_ID = readStoredOfficeId();
let MODEL_OFFICE_ID = ACTIVE_OFFICE_ID;
let currentOfficePreflight = null;

function navigate(page) {
    page = normalizeNavigationTarget(page);
    document.querySelectorAll('.page').forEach(p => p.style.display = 'none');
    const targetPageId = page === 'comic_production'
        ? 'comic'
        : (page === 'demo_comic' || page === 'demo_research'
            ? 'demo'
            : (page === 'public_showcase' ? 'public-showcase' : page));
    const targetPage = document.getElementById('page-' + targetPageId);
    if (!targetPage) return;
    targetPage.style.display = (page === 'task') ? 'flex' : 'block';
    document.body.classList.toggle('hall-mode', page === 'offices' || page === 'demo_comic' || page === 'demo_research' || page === 'public_showcase');
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
    else if (page === 'demo_comic') loadComicDemo();
    else if (page === 'demo_research') loadResearchDemo();
    else if (page === 'public_showcase') loadPublicShowcase();
    else if (page === 'prompts') loadPrompts();
    else if (page === 'history') loadHistory();
    if (page === 'offices') loadSystemPreflight();
    if (page === 'offices') loadOfficeHallAvailability();
    if (page === 'offices') loadOfficeLaunchGates();
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
    ['standard_report', '标准报告'],
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

function escapeJsAttr(value) {
    return escapeHtml(encodeURIComponent(JSON.stringify(value || {})));
}

function renderArtifactSchemaGatePanel(artifact) {
    const gate = (artifact?.metadata || {}).schema_gate;
    if (!gate) return '';
    const status = gate.status || 'unknown';
    const statusClass = status === 'passed' ? 'schema-gate-passed' : 'schema-gate-failed';
    const statusLabel = status === 'passed' ? '已通过' : '需要复核';
    const rows = [
        ['Schema', gate.schema_id || ''],
        ['状态', statusLabel],
        ['责任办公室', gate.office_id || ''],
        ['行数/段落', gate.row_count || gate.section_count || ''],
        ['原因', gate.reason || '结构校验通过'],
    ].filter(([, value]) => String(value || '').trim());
    return `
        <div class="artifact-schema-gate ${statusClass}">
            <div class="artifact-schema-gate-head">
                <strong>交付结构校验</strong>
                <span>${escapeHtml(statusLabel)}</span>
            </div>
            <div class="artifact-schema-gate-grid">
                ${rows.map(([label, value]) => `
                    <div>
                        <span>${escapeHtml(label)}</span>
                        <p>${escapeHtml(value)}</p>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
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
            ${renderTaskRecoveryPlan(task.recovery_plan)}
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

function renderTaskRecoveryPlan(plan) {
    if (!plan || !plan.recoverable) return '';
    const action = plan.retry_action || {};
    return `
        <div class="task-recovery-plan">
            <div class="task-recovery-plan-head">
                <strong>恢复建议</strong>
                <span>${escapeHtml(plan.department || plan.failed_phase || '任务恢复')}</span>
            </div>
            ${plan.reason ? `<p><b>卡住原因</b>${escapeHtml(plan.reason)}</p>` : ''}
            ${plan.impact ? `<p><b>影响</b>${escapeHtml(plan.impact)}</p>` : ''}
            ${plan.next_action ? `<p><b>下一步</b>${escapeHtml(plan.next_action)}</p>` : ''}
            ${action.path ? `
                <button class="ghost btn-sm" onclick="retryTaskRecoveryAction('${escapeJsAttr(action)}')">
                    ${escapeHtml(action.label || '继续处理')}
                </button>
            ` : ''}
        </div>
    `;
}

async function retryTaskRecoveryAction(encodedAction) {
    let action = {};
    try {
        action = JSON.parse(decodeURIComponent(encodedAction || ''));
    } catch (e) {
        toast('恢复动作解析失败，请刷新后重试', 'error');
        return;
    }
    if (!action.path) {
        toast('这个任务暂时没有可自动执行的恢复动作', 'error');
        return;
    }
    try {
        const method = String(action.method || 'POST').toUpperCase();
        const body = action.body && typeof action.body === 'object' ? action.body : {};
        if (method === 'GET') await API.get(action.path);
        else if (method === 'PUT') await API.put(action.path, body);
        else await API.post(action.path, body);
        toast(action.label ? `${action.label} 已提交` : '恢复动作已提交', 'success');
        if (action.office_id === 'comic_production' && action.workspace_id) {
            await recoverComicWorkspaceFromHistory(action);
            return;
        }
        if (currentResearchWorkspace) await loadResearchTimeline(currentResearchWorkspace);
        if (currentComicWorkspace) {
            await loadComicTimeline(currentComicWorkspace);
            await loadComicArtifacts(currentComicWorkspace);
            await loadComicRuntimeStatus(currentComicWorkspace);
        }
    } catch (e) {
        toast('恢复动作失败：' + formatApiError(e), 'error');
    }
}

async function recoverComicWorkspaceFromHistory(action) {
    navigate('comic_production');
    await loadComicWorkspaces();
    await selectComicWorkspace(action.workspace_id);
    await refreshComicV2Panel(action.label ? `${action.label} 已提交，已回到对应项目。` : '已回到对应项目。');
    focusComicRecoveryTarget(action.focus || 'workspace');
}

function focusComicRecoveryTarget(focus) {
    const targetId = focus === 'prompts'
        ? 'comic-package-board'
        : (focus === 'images'
            ? 'comic-artifacts'
            : (focus === 'delivery' ? 'comic-package-board' : 'comic-workspaces'));
    const target = document.getElementById(targetId) || document.getElementById('comic-package-board');
    if (target?.scrollIntoView) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function phaseLabel(phase) {
    const map = {
        queued: '排队中',
        preparing: '准备中',
        agent_workflow: 'Agent 协作中',
        comic_image_generation: '逐张生成与视觉检查',
        visual_review_pending: '等待图片审核',
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
        comic_image_generation_started: '开始批量生成图片',
        comic_image_item_started: '正在生成图片',
        comic_image_item_completed: '图片生成完成',
        comic_image_item_failed: '图片生成失败',
        comic_artifacts_created: '漫剧制片包已生成',
        comic_v2_quality_recovery_started: '按质量基准退回处理',
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
    if (artifact.artifact_type === 'quality_report') return { kind: 'review', text: '需处理' };
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
    const isMarkdown = ['report', 'standard_report', 'briefing'].includes(artifact.artifact_type);
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
    const schemaGatePanel = renderArtifactSchemaGatePanel(artifact);
    detail.className = 'artifact-detail';
    detail.innerHTML = `
        <div class="artifact-detail-head">
            <span class="artifact-type">${escapeHtml(artifact.artifact_type)}</span>
            <strong>${escapeHtml(artifact.title)}</strong>
        </div>
        ${schemaGatePanel}
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
        toast('截图取证失败: ' + e.message, 'error');
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
        toast('正在辅助飞瓜取证，请留意本地浏览器登录状态和账号权限', 'success');
        const result = await API.post(`/api/workspaces/${currentResearchWorkspace}/capture-feigua`, {
            keyword,
            wait_seconds: 6,
            limit: 4,
        });
        if (result.detail) throw new Error(result.detail);
        if (!result.created_count) {
            toast(result.note || '飞瓜取证未生成截图，请检查登录状态、账号权限或稍后补证', 'error');
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
let currentComicAssistantMessage = '';
let currentComicRuntimeStatus = null;
let currentComicV2Status = null;
let currentComicV2ActionError = null;
let currentComicV2PendingAction = null;
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
    await Promise.all([
        loadComicProfile(),
        loadComicWorkspaces(),
        loadOfficePreflight(activeComicOfficeId(), 'comic-preflight-panel'),
    ]);
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
        resetComicWorkspaceState({ clearInputs: true });
        renderComicPackageBoard();
        currentComicV2Status = null;
        // 如果是选择了“新建漫剧项目”，不仅清空变量，还要清空页面上的表单输入
        document.getElementById('comic-idea').value = '';
        const scriptSource = document.getElementById('comic-script-source');
        if (scriptSource) scriptSource.value = '';
        const characterSource = document.getElementById('comic-character-source');
        if (characterSource) characterSource.value = '';
        const styleReference = document.getElementById('comic-style-reference');
        if (styleReference) styleReference.value = '';
        const inputMode = document.getElementById('comic-input-mode');
        if (inputMode) inputMode.value = 'idea';
        toggleComicInputMode();
        document.getElementById('comic-extra').value = '';
        document.getElementById('comic-chat-input').value = '';
        
        // 重新渲染空状态
        await loadComicCabinetSession('');
        await loadComicArtifacts('');
        await loadComicTimeline('');
        renderOfficeRuntimeStatus(null, '选择一个漫剧项目后查看当前阶段、产物缺口和可恢复动作。');
        
        // 重新渲染左侧列表高亮状态
        const items = document.querySelectorAll('#comic-workspaces .workspace-item');
        items.forEach(item => item.classList.remove('active'));
        
        return;
    }
    
    // 如果不是新建，而是切换到了别的项目，更新左侧列表高亮状态
    resetComicWorkspaceState({ preserveInputs: true });
    renderComicPackageBoard();

    const items = document.querySelectorAll('#comic-workspaces .workspace-item');
    items.forEach(item => {
        if (item.getAttribute('onclick').includes(workspaceId)) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });

    await loadComicRuntimeStatus(workspaceId);
    await loadComicV2Status(workspaceId);
    await Promise.all([loadComicArtifacts(workspaceId), loadComicTimeline(workspaceId), loadComicCabinetSession(workspaceId)]);
}

function resetComicWorkspaceState(options = {}) {
    currentComicArtifacts = [];
    currentComicBrief = null;
    currentComicScriptPreview = null;
    currentComicConfirmedScript = null;
    currentComicCabinetSession = null;
    currentComicCabinetReady = false;
    currentComicAssistantMessage = '';
    currentComicRuntimeStatus = null;
    currentComicV2Status = null;
    currentComicV2ActionError = null;
    currentComicV2PendingAction = null;
    if (options.clearInputs) {
        const idea = document.getElementById('comic-idea');
        if (idea) idea.value = '';
        const scriptSource = document.getElementById('comic-script-source');
        if (scriptSource) scriptSource.value = '';
        const characterSource = document.getElementById('comic-character-source');
        if (characterSource) characterSource.value = '';
        const styleReference = document.getElementById('comic-style-reference');
        if (styleReference) styleReference.value = '';
        const inputMode = document.getElementById('comic-input-mode');
        if (inputMode) inputMode.value = 'idea';
        toggleComicInputMode();
        const extra = document.getElementById('comic-extra');
        if (extra) extra.value = '';
        const chat = document.getElementById('comic-chat-input');
        if (chat) chat.value = '';
    }
    renderComicCabinet();
    renderComicAssetReviewPanel([]);
    const list = document.getElementById('comic-artifacts');
    if (list) list.innerHTML = '<div class="empty-state">选择一个漫剧项目查看资产。</div>';
    const detail = document.getElementById('comic-artifact-detail');
    if (detail) {
        detail.className = 'artifact-detail empty-state';
        detail.textContent = '选择一个资产查看完整内容。';
    }
    const count = document.getElementById('comic-task-count');
    if (count) count.textContent = '0';
    const timeline = document.getElementById('comic-timeline');
    if (timeline) timeline.innerHTML = '<div class="empty-state">选择一个漫剧项目后查看创作记录。</div>';
    renderOfficeRuntimeStatus(null, '选择一个漫剧项目后查看当前阶段、产物缺口和可恢复动作。');
}

async function loadComicRuntimeStatus(workspaceId) {
    if (!workspaceId) {
        currentComicRuntimeStatus = null;
        renderOfficeRuntimeStatus(null, '选择一个漫剧项目后查看当前阶段、产物缺口和可恢复动作。');
        return null;
    }
    try {
        const result = await API.get(`/api/workspaces/${workspaceId}/runtime-status`);
        if (currentComicWorkspace !== workspaceId) return null;
        currentComicRuntimeStatus = result;
        renderOfficeRuntimeStatus(currentComicRuntimeStatus);
    } catch (e) {
        if (currentComicWorkspace !== workspaceId) return null;
        currentComicRuntimeStatus = {
            current_stage: { id: 'runtime_status_error', status: 'failed', summary: e.message || String(e) },
            artifact_progress: { present_count: 0, missing_count: 0, missing: [] },
            next_action: '刷新工作台；如果仍失败，请查看后端日志。',
        };
        renderOfficeRuntimeStatus(currentComicRuntimeStatus);
    }
    return currentComicRuntimeStatus;
}

function renderOfficeRuntimeStatus(status, emptyText = '选择一个工作空间后查看运行状态。') {
    const panel = document.getElementById('comic-runtime-status-panel');
    if (!panel) return;
    if (!status) {
        panel.innerHTML = `<div class="empty-state">${escapeHtml(emptyText)}</div>`;
        return;
    }
    const stage = status.current_stage || {};
    const progress = status.artifact_progress || {};
    const activeTask = status.active_task || {};
    const recovery = activeTask.recovery_plan || {};
    const action = recovery.retry_action || {};
    const missing = Array.isArray(progress.missing) ? progress.missing.slice(0, 6) : [];
    const downloads = Array.isArray(status.downloadable_artifacts) ? status.downloadable_artifacts.slice(0, 5) : [];
    const ratio = Number(progress.completion_ratio || 0);
    const ratioText = `${Math.round(ratio * 100)}%`;
    panel.innerHTML = `
        <div class="runtime-status-head">
            <div>
                <span class="runtime-kicker">当前状态</span>
                <strong>${escapeHtml(stage.id || '未开始')}</strong>
                <small>${escapeHtml(stage.summary || status.next_action || '等待下一步操作。')}</small>
            </div>
            <span class="badge ${stage.status === 'failed' || stage.status === 'interrupted' ? 'badge-err' : 'badge-info'}">${escapeHtml(stage.status || 'waiting')}</span>
        </div>
        <div class="runtime-status-grid">
            <div>
                <b>${escapeHtml(String(progress.present_count ?? 0))}</b>
                <span>已生成产物</span>
            </div>
            <div>
                <b>${escapeHtml(String(progress.missing_count ?? 0))}</b>
                <span>缺失产物</span>
            </div>
            <div>
                <b>${escapeHtml(ratioText)}</b>
                <span>完成度</span>
            </div>
        </div>
        ${missing.length ? `<div class="runtime-missing"><b>优先补齐</b>${missing.map(item => `<code>${escapeHtml(item)}</code>`).join('')}</div>` : ''}
        ${downloads.length ? `
            <div class="runtime-downloads">
                <b>可下载交付物</b>
                <div>
                    ${downloads.map(item => `
                        <a class="runtime-download-link" href="${escapeHtml(item.uri)}" target="_blank" rel="noreferrer">
                            <span>${escapeHtml(item.title || item.artifact_type || '交付物')}</span>
                            <small>${escapeHtml(item.created_by || item.artifact_type || '产物')}</small>
                        </a>
                    `).join('')}
                </div>
            </div>
        ` : ''}
        ${status.next_action ? `<p class="runtime-next">${escapeHtml(status.next_action)}</p>` : ''}
        ${recovery.recoverable ? `
            <div class="runtime-recovery">
                <span>${escapeHtml(recovery.department || recovery.failed_phase || '可恢复阶段')}</span>
                ${action.path ? `<button class="ghost btn-sm" onclick="retryTaskRecoveryAction('${escapeJsAttr(action)}')">${escapeHtml(action.label || '继续处理')}</button>` : ''}
            </div>
        ` : ''}
    `;
}

async function loadComicV2Status(workspaceId) {
    if (!workspaceId || activeComicOfficeId() !== 'comic_production') {
        currentComicV2Status = null;
        return null;
    }
    try {
        const result = await API.get(`/api/workspaces/${workspaceId}/comic/v2/status`);
        if (currentComicWorkspace !== workspaceId) return null;
        currentComicV2Status = result;
    } catch (e) {
        if (currentComicWorkspace !== workspaceId) return null;
        currentComicV2Status = {
            pipeline_version: 2,
            status: 'status_error',
            stage: 'blocked',
            current_agent: '系统',
            current_object: 'V2制片状态',
            blocking_reason: e.message || String(e),
            next_action: '刷新页面；若仍失败，请检查后端日志。',
            completed: 0,
            total: 0,
        };
    }
    return currentComicV2Status;
}

async function refreshComicV2Panel(message = '') {
    if (!currentComicWorkspace) return null;
    const status = await loadComicV2Status(currentComicWorkspace);
    currentComicV2ActionError = null;
    await Promise.all([
        loadComicRuntimeStatus(currentComicWorkspace),
        loadComicArtifacts(currentComicWorkspace),
        loadComicTimeline(currentComicWorkspace),
    ]);
    renderComicPackageBoard(currentComicArtifacts);
    if (message) toast(message, 'success');
    return status;
}

async function loadComicCabinetSession(workspaceId) {
    if (!workspaceId) {
        currentComicCabinetSession = null;
        currentComicCabinetReady = false;
        currentComicBrief = null;
        currentComicScriptPreview = null;
        currentComicConfirmedScript = null;
        currentComicAssistantMessage = '';
        renderComicCabinet();
        return;
    }
    try {
        const result = await API.get(`/api/comic/cabinet/${workspaceId}`);
        if (currentComicWorkspace !== workspaceId) return null;
        if (result.status !== 'ok') {
            currentComicCabinetSession = null;
            currentComicCabinetReady = false;
            currentComicBrief = null;
            currentComicScriptPreview = null;
            currentComicConfirmedScript = null;
            currentComicAssistantMessage = '';
        } else {
            currentComicCabinetSession = result.session || null;
            currentComicCabinetReady = Boolean(result.ready_to_produce);
            currentComicBrief = result.creative_brief || null;
            currentComicScriptPreview = result.script_preview || null;
            currentComicConfirmedScript = result.confirmed_script || null;
            currentComicAssistantMessage = result.assistant_message || '';
        }
        renderComicCabinet();
    } catch (e) {
        if (currentComicWorkspace !== workspaceId) return null;
        currentComicCabinetSession = null;
        currentComicCabinetReady = false;
        currentComicBrief = null;
        currentComicScriptPreview = null;
        currentComicConfirmedScript = null;
        currentComicAssistantMessage = '';
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
    if (currentComicWorkspace !== workspaceId) return null;
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
                ${renderTaskRecoveryPlan(t.recovery_plan)}
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
    if (currentComicWorkspace !== workspaceId) return null;
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
        { key: 'asset_docs', title: '资产拆解', hint: '人物、道具、场景和审核包', types: ['comic_v2_contract', 'asset_review_package', 'style_bible', 'character_sheet', 'prop_sheet', 'scene_sheet', 'asset_registry'] },
        { key: 'images', title: '图片资产库', hint: '人物、道具、场景基础资产图', types: ['generated_image', 'comic_v2_generated_image'] },
        { key: 'shot_docs', title: '镜头提示词', hint: '镜头画面提示词、视频生成提示词、交接台', types: ['shot_prompt_table', 'shot_prompt_handoff'] },
        { key: 'delivery', title: '交付文件', hint: 'Word 画布、引用清单、提示词包、执行材料', types: ['word_canvas', 'comic_v2_word_canvas', 'comic_v2_handoff_manifest', 'prompt_package', 'comic_v2_prompt_package', 'production_canvas', 'production_brief', 'dispatch_plan'] },
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
        if (reviewStatus !== 'approved' && reviewStatus !== 'revision_requested') return i;
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
    const returned = status === 'revision_requested';
    if (panel) panel.style.display = pending ? '' : 'none';
    if (statusBadge) {
        statusBadge.textContent = comicAssetReviewStatusText(status);
        statusBadge.className = `badge ${status === 'revision_requested' ? 'badge-err' : 'badge-info'}`;
    }
    if (copy) {
        copy.textContent = returned
            ? '资产拆解已退回。你可以修改上方要求，然后点击“按退回意见重新拆解”。'
            : '中书省和门下省已经把人物、道具、场景和分镜输入拆完。确认它们符合故事后，再继续生成图片和 Word 画布。';
    }
    if (approveBtn) approveBtn.style.display = pending && !returned ? '' : 'none';
    if (startBtn) {
        startBtn.textContent = returned ? '按退回意见重新拆解' : (pending ? '等待资产审核通过' : '生成资产拆解审核包');
        startBtn.disabled = pending && !returned;
        startBtn.onclick = () => submitComicTask(returned ? { revisionMode: true } : {});
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
    const hasV2Status = Boolean(currentComicV2PendingAction)
        || (currentComicV2Status && currentComicV2Status.pipeline_version === 2 && currentComicV2Status.status !== 'not_started');
    if (hasV2Status) {
        score.textContent = `${Number(currentComicV2Status.completed || 0)}/${Number(currentComicV2Status.total || 0)}`;
        const benchmark = currentComicV2Status.delivery?.quality_benchmark || {};
        const packageReady = currentComicV2Status.stage === 'ready_for_handoff'
            && currentComicV2Status.status === 'completed'
            && (benchmark.package_quality_ready !== false);
        score.className = packageReady ? 'badge badge-ok' : 'badge badge-info';
        board.className = 'package-board';
        board.innerHTML = renderComicV2ProductionFlow();
        return;
    }
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
        ${renderComicProductionFlow(items)}
    `;
}

function latestComicProductionChain(artifacts) {
    const chainItems = (artifacts || [])
        .map((artifact, index) => ({ artifact, index }))
        .filter(item => item.artifact.artifact_type === 'production_chain_state');
    return chainItems.length ? chainItems[chainItems.length - 1] : null;
}

function renderComicProductionFlow(artifacts) {
    if (currentComicV2Status && currentComicV2Status.pipeline_version === 2 && currentComicV2Status.status !== 'not_started') {
        return renderComicV2ProductionFlow();
    }
    const chainItem = latestComicProductionChain(artifacts);
    if (!chainItem) {
        return `
            <div class="production-flow empty">
                <div>
                    <strong>三省六部流程</strong>
                    <span>确认故事并生成资产拆解包后，这里会显示谁在处理、卡在哪里、下一步需要做什么。</span>
                </div>
            </div>
        `;
    }
    const meta = chainItem.artifact.metadata || {};
    const departments = meta.departments || [];
    const nextAction = meta.next_action || '等待下一步生产状态。';
    const currentDepartment = meta.current_department || '尚书省';
    const actionButton = meta.human_action_required
        ? '<button class="ghost btn-sm" onclick="focusComicAssetReview()">查看待审核资产</button>'
        : `<button class="ghost btn-sm" onclick="selectComicArtifact(${chainItem.index})">查看链路详情</button>`;
    return `
        <div class="production-flow">
            <div class="production-flow-head">
                <div>
                    <strong>三省六部流程</strong>
                    <span>当前：${escapeHtml(currentDepartment)} · ${escapeHtml(nextAction)}</span>
                </div>
                ${actionButton}
            </div>
            <div class="department-flow">
                ${departments.map(dept => renderComicDepartmentStep(dept)).join('')}
            </div>
        </div>
    `;
}

function renderComicV2ProductionFlow() {
    const completed = Number(currentComicV2Status.completed || 0);
    const total = Number(currentComicV2Status.total || 0);
    const progress = total > 0 ? `${completed}/${total}` : '等待状态';
    const blocked = currentComicV2Status.blocking_reason || '';
    const actions = renderComicV2StageActions(currentComicV2Status);
    const reviewSummary = renderComicV2ReviewSummary(currentComicV2Status);
    return `
        <div class="production-flow v2-flow">
            <div class="production-flow-head">
                <div>
                    <strong>V2 制片管线 · ${escapeHtml(progress)}</strong>
                    <span>当前 Agent：${escapeHtml(currentComicV2Status.current_agent || '等待分配')}</span>
                </div>
                <span class="badge badge-info">${escapeHtml(currentComicV2Status.stage || '未开始')}</span>
            </div>
            <div class="package-summary">
                <strong>${escapeHtml(currentComicV2Status.current_object || '等待生产对象')}</strong>
                <span>${escapeHtml(blocked || '当前没有阻塞项')}</span>
                <small>下一步：${escapeHtml(currentComicV2Status.next_action || '等待状态更新')}</small>
            </div>
            ${renderComicV2ActionError()}
            ${renderComicV2PendingAction()}
            ${renderComicV2LineageTimeline(currentComicV2Status.production_lineage)}
            ${renderComicV2ReviewGateMap(currentComicV2Status.production_lineage)}
            ${renderComicV2DepartmentFlow(currentComicV2Status.department_flow)}
            ${reviewSummary}
            ${renderComicV2PromptQuality(currentComicV2Status.prompt_quality)}
            ${renderComicV2ShotPromptCards(currentComicV2Status)}
            ${actions ? `<div class="v2-action-row">${actions}</div>` : ''}
        </div>
    `;
}

function renderComicV2PromptQuality(quality) {
    if (!quality || quality.status === 'waiting') return '';
    const statusText = quality.status === 'ready' ? '可交接' : '需复核';
    const issueItems = Array.isArray(quality.issues) ? quality.issues.slice(0, 4) : [];
    const checks = Array.isArray(quality.checks) ? quality.checks : [];
    return `
        <section class="v2-prompt-quality ${escapeHtml(quality.status || 'needs_review')}">
            <div class="v2-prompt-quality-head">
                <div>
                    <strong>提示词质量门禁</strong>
                    <span>${escapeHtml(quality.summary || '等待提示词质量审计')}</span>
                </div>
                <b>${escapeHtml(statusText)}</b>
            </div>
            <div class="v2-prompt-quality-metrics">
                <span>资产提示词：${Number(quality.clean_asset_prompt_count || 0)}/${Number(quality.asset_prompt_count || 0)}</span>
                <span>镜头提示词：${Number(quality.director_prompt_count || 0)}/${Number(quality.shot_prompt_count || 0)}</span>
                <span>问题：${Number(quality.issue_count || 0)}</span>
            </div>
            ${checks.length ? `<div class="v2-prompt-quality-checks">${checks.map(item => `<small>${escapeHtml(item)}</small>`).join('')}</div>` : ''}
            ${renderComicV2PromptQualityRecovery(quality)}
            ${issueItems.length ? `
                <div class="v2-prompt-quality-issues">
                    ${issueItems.map(item => `<small>${escapeHtml(item.id || '')}：${escapeHtml(item.message || '')}</small>`).join('')}
                </div>
            ` : ''}
        </section>
    `;
}

function renderComicV2PromptQualityRecovery(quality) {
    const recovery = quality?.recovery || {};
    if (!recovery.recoverable) return '';
    const canRegenerate = currentComicV2Status?.stage === 'image_generation'
        || currentComicV2Status?.stage === 'prompt_planning'
        || currentComicV2Status?.stage === 'visual_review'
        || currentComicV2Status?.stage === 'document_generation'
        || currentComicV2Status?.stage === 'ready_for_handoff';
    return `
        <div class="v2-prompt-quality-recovery">
            <div>
                <strong>恢复建议：${escapeHtml(recovery.department || '兵部 / 刑部')}</strong>
                <span>${escapeHtml(recovery.impact || '提示词质量需要复核。')}</span>
                <small>下一步：${escapeHtml(recovery.next_action || '重新生成提示词后再继续。')}</small>
            </div>
            <div class="v2-prompt-quality-actions">
                ${canRegenerate ? '<button class="ghost btn-sm" onclick="planComicV2Prompts(this)">重新生成提示词</button>' : ''}
                <button class="ghost btn-sm" onclick="focusComicAssetReview()">回到资产审核</button>
            </div>
        </div>
    `;
}

function buildComicV2PendingAction(label, status) {
    const stage = status?.stage || 'running';
    const map = {
        visual_bible_review: ['中书省 / 门下省', '正在确认视觉母版，完成后进入资产拆解。'],
        asset_planning: ['中书省 / 门下省', '正在生成资产拆解审核包，完成后需要你确认人物、道具和场景。'],
        asset_review: ['门下省 / 尚书省', '正在处理资产审核意见，完成后会进入提示词规划。'],
        prompt_planning: ['工部 / 兵部', '正在生成资产提示词和镜头提示词，完成后进入图片生产。'],
        image_generation: ['工部 / 刑部', '正在生成基础资产图并做视觉质检，完成后进入交付组装。'],
        visual_review: ['刑部 / 工部', '正在处理未通过图片或人工放行，完成后进入文档生成。'],
        document_generation: ['礼部 / 刑部', '正在组装 Word 制片画布并做结构审计。'],
    };
    const [department, next] = map[stage] || [status?.current_agent || '尚书省', status?.next_action || '等待当前动作返回结果。'];
    return {
        label,
        department,
        stage,
        object: status?.current_object || '当前生产对象',
        next_action: next,
    };
}

function renderComicV2PendingAction() {
    if (!currentComicV2PendingAction) return '';
    return `
        <div class="package-summary v2-action-pending">
            <strong>正在处理：${escapeHtml(currentComicV2PendingAction.label || 'V2 操作')}</strong>
            <span>负责部门：${escapeHtml(currentComicV2PendingAction.department || '尚书省')}；对象：${escapeHtml(currentComicV2PendingAction.object || '当前生产对象')}</span>
            <small>下一步：${escapeHtml(currentComicV2PendingAction.next_action || '等待系统返回结果')}</small>
        </div>
    `;
}

function renderComicV2ActionError() {
    if (!currentComicV2ActionError) return '';
    const detail = currentComicV2ActionError.detail && typeof currentComicV2ActionError.detail === 'object'
        ? currentComicV2ActionError.detail
        : {};
    const department = detail.department || '当前生产步骤';
    const impact = detail.impact || currentComicV2ActionError.message || '系统没有返回详细影响';
    const nextAction = detail.next_action || '按当前阶段提示修复后重试。';
    return `
        <div class="package-summary v2-action-error">
            <div class="v2-action-error-body">
                <strong>最近一次操作失败：${escapeHtml(currentComicV2ActionError.label || 'V2 操作')}</strong>
                <span>负责部门：${escapeHtml(department)}</span>
                <span>影响：${escapeHtml(impact)}</span>
                <small>下一步：${escapeHtml(nextAction)}</small>
            </div>
            ${renderComicV2ActionRecovery(currentComicV2ActionError)}
        </div>
    `;
}

function renderComicV2ActionRecovery(error) {
    const detail = error?.detail && typeof error.detail === 'object' ? error.detail : {};
    const actionText = `${detail.reason || ''} ${detail.impact || ''} ${detail.next_action || ''}`;
    const shouldOpenModels = /模型|API Key|Key|配置|额度|生图|视觉/.test(actionText);
    const modelButton = shouldOpenModels
        ? `<button class="ghost btn-sm" onclick="navigate('models')">去模型页检查</button>`
        : '';
    return `
        <div class="v2-action-recovery">
            ${modelButton}
            <button class="ghost btn-sm" onclick="refreshComicV2Panel('已刷新当前阶段状态')">刷新当前阶段</button>
        </div>
    `;
}

function renderComicV2DepartmentFlow(departments) {
    const items = Array.isArray(departments) ? departments : [];
    if (!items.length) return '';
    return `
        <div class="department-flow v2-department-flow">
            ${items.map(dept => `
                <div class="department-step ${escapeHtml(dept.status || 'waiting')}">
                    <div class="department-step-top">
                        <strong>${escapeHtml(dept.name || dept.department_id || '')}</strong>
                        <span>${escapeHtml(comicV2DepartmentStatusText(dept.status))}</span>
                    </div>
                    <p>${escapeHtml(dept.responsibility || '等待分配职责')}</p>
                    ${dept.human_checkpoint ? `<small>${escapeHtml(dept.human_checkpoint)}</small>` : ''}
                </div>
            `).join('')}
        </div>
    `;
}

function comicV2DepartmentStatusText(status) {
    if (status === 'current') return '当前';
    if (status === 'completed') return '已完成';
    return '等待';
}

function renderComicV2ReviewSummary(status) {
    const stage = status?.stage || '';
    if (stage === 'visual_bible_review') {
        const visual = status.contract?.visual || {};
        const palette = Array.isArray(visual.palette) ? visual.palette.join('、') : '';
        const prohibited = Array.isArray(visual.prohibited_elements) ? visual.prohibited_elements.join('、') : '';
        return `
            <div class="package-summary v2-review-summary">
                <strong>待确认：视觉母版</strong>
                <span>风格：${escapeHtml(visual.medium || '未填写')}；时代：${escapeHtml(visual.era || '未填写')}；画幅：${escapeHtml(visual.aspect_ratio || '未填写')}</span>
                <small>色板：${escapeHtml(palette || '未填写')}；禁止元素：${escapeHtml(prohibited || '未填写')}</small>
            </div>
        `;
    }
    if (stage === 'asset_review') {
        const items = status.asset_manifest?.items || [];
        const groups = {
            character: items.filter(item => item.asset_type === 'character'),
            prop: items.filter(item => item.asset_type === 'prop'),
            scene: items.filter(item => item.asset_type === 'scene'),
        };
        const names = items.slice(0, 8).map(item => item.name).filter(Boolean).join('、');
        return `
            <div class="package-summary v2-review-summary">
                <strong>待确认：资产拆解</strong>
                <span>人物 ${groups.character.length} 个，道具 ${groups.prop.length} 个，场景 ${groups.scene.length} 个。</span>
                <small>${escapeHtml(status.asset_review?.human_guidance || names || '只确认人物、道具和场景；提示词会在确认后继续生成。')}</small>
            </div>
            ${renderComicV2AssetRevisionSummary(status.asset_review)}
            ${renderComicV2AssetReviewGroups(status.asset_review?.groups)}
        `;
    }
    if (stage === 'ready_for_handoff' || stage === 'document_generation') {
        const audit = status.delivery?.audit || {};
        const benchmark = status.delivery?.quality_benchmark || {};
        const benchmarkLabel = {
            production_quality_verified: '真实质量已验证',
            demo_structure_verified: '结构演示已验证',
            needs_review: '质量待复核',
        }[benchmark.status] || benchmark.status || '等待质量基准';
        return `
            <div class="package-summary v2-review-summary">
                <strong>交付审计</strong>
                <span>嵌入图片 ${Number(audit.embedded_images || 0)} 张；资产 ${Number(audit.asset_count || 0)} 个；镜头 ${Number(audit.shot_count || 0)} 个。</span>
                <small>${audit.handoff_ready ? '结构审计已通过。' : '等待 Word 结构审计。'}${benchmark.summary ? ` 制片包 ${Number(benchmark.package_quality_score || 0)}/100，${escapeHtml(benchmarkLabel)}。` : ''}</small>
                ${benchmark.summary ? `<small>${escapeHtml(benchmark.summary)}</small>` : ''}
            </div>
        `;
    }
    return '';
}

function renderComicV2ShotPromptCards(status) {
    const shots = currentComicV2Status.prompt_package?.shots || status?.prompt_package?.shots || [];
    if (!Array.isArray(shots) || !shots.length) return '';
    const assetItems = status?.asset_manifest?.items || [];
    const assetNameById = new Map(assetItems.map(item => [item.asset_id, item.name || item.asset_id]));
    const visibleShots = shots.slice(0, 6);
    const hiddenCount = Math.max(0, shots.length - visibleShots.length);
    return `
        <section class="v2-shot-prompt-cards">
            <div class="v2-shot-prompt-head">
                <div>
                    <strong>镜头执行卡</strong>
                    <span>把分镜意图、首帧参考资产、动作链和视频提示词放在一起，方便直接交给视频生成平台。</span>
                </div>
                <span>${shots.length} 个镜头</span>
            </div>
            <div class="v2-shot-card-grid">
                ${visibleShots.map((shot, index) => {
                    const references = Array.isArray(shot.reference_asset_ids) ? shot.reference_asset_ids : [];
                    const referenceLabels = references.map(assetId => assetNameById.get(assetId) || assetId);
                    const criteria = Array.isArray(shot.acceptance_criteria) ? shot.acceptance_criteria.join('；') : '';
                    const actionChain = shot.action_chain || shot.action || '';
                    const camera = shot.camera_movement || shot.camera || '';
                    const dialogue = shot.dialogue || '';
                    const prompt = shot.generator_prompt || shot.prompt || '';
                    const negative = shot.negative_prompt || '';
                    return `
                        <article class="v2-shot-card">
                            <div class="v2-shot-card-top">
                                <strong>${escapeHtml(shot.shot_id || `shot_${index + 1}`)}</strong>
                                <span>${escapeHtml(shot.framing || '镜头景别待确认')}</span>
                            </div>
                            <div class="v2-shot-assets">
                                <small>首帧参考资产</small>
                                ${referenceLabels.length
                                    ? referenceLabels.map(label => `<b>${escapeHtml(label)}</b>`).join('')
                                    : '<em>暂无引用资产</em>'}
                            </div>
                            <p><b>动作链</b>${escapeHtml(actionChain || '待补充角色动作与状态变化')}</p>
                            <p><b>运镜</b>${escapeHtml(camera || '待补充镜头运动')}</p>
                            ${dialogue ? `<p><b>台词</b>${escapeHtml(dialogue)}</p>` : ''}
                            <div class="v2-shot-prompt-block">
                                <small>视频提示词</small>
                                <p>${escapeHtml(prompt || '待生成视频提示词')}</p>
                            </div>
                            <div class="v2-shot-negative">
                                <small>负面提示词</small>
                                <p>${escapeHtml(negative || '禁止脸型变化、服装不一致、画风漂移、不可读文字。')}</p>
                            </div>
                            <div class="v2-shot-acceptance">
                                <small>验收标准</small>
                                <p>${escapeHtml(criteria || '人物、资产、动作、镜头和故事节点必须与资产身份证一致。')}</p>
                            </div>
                        </article>
                    `;
                }).join('')}
            </div>
            ${hiddenCount ? `<small class="v2-shot-hidden-count">还有 ${hiddenCount} 个镜头会写入 Word 画布。</small>` : ''}
        </section>
    `;
}

function renderComicV2AssetRevisionSummary(review) {
    if (!review?.previous_manifest_hash && !review?.revision_note) return '';
    const summary = review.revision_summary || {};
    const sections = [
        ['added', '新增'],
        ['removed', '删除'],
        ['changed', '修改'],
    ];
    return `
        <div class="v2-asset-revision-summary">
            <div>
                <strong>本次退回已生成新版本</strong>
                <span>${escapeHtml(review.revision_note || '未填写退回意见')}</span>
            </div>
            ${review.previous_manifest_hash ? `<small>上一版：${escapeHtml(String(review.previous_manifest_hash).slice(0, 12))}</small>` : ''}
            <div class="v2-asset-revision-diff">
                ${sections.map(([key, label]) => {
                    const items = Array.isArray(summary[key]) ? summary[key] : [];
                    return `<span>${label}：${items.length ? items.map(item => escapeHtml(item.name || item.asset_type || '未命名')).join('、') : '无'}</span>`;
                }).join('')}
            </div>
        </div>
    `;
}

function renderComicV2AssetReviewGroups(groups) {
    if (!groups) return '';
    const sections = [
        ['characters', '人物', '确认是不是故事里真实行动的人。'],
        ['props', '道具', '确认是不是故事里会被使用、发现或影响情节的物件。'],
        ['scenes', '场景', '确认是不是故事明确发生动作的可复用空间。'],
    ];
    return `
        <div class="v2-asset-review-grid">
            ${sections.map(([key, label, hint]) => {
                const items = Array.isArray(groups[key]) ? groups[key] : [];
                return `
                    <section class="v2-asset-review-section">
                        <div class="v2-asset-review-section-head">
                            <strong>${label}</strong>
                            <span>${items.length}</span>
                        </div>
                        <small>${hint}</small>
                        ${items.length ? items.map(renderComicV2AssetReviewItem).join('') : '<p class="muted">这一类暂时没有资产。</p>'}
                    </section>
                `;
            }).join('')}
        </div>
    `;
}

function renderComicV2AssetReviewItem(item) {
    const evidence = item.source_evidence || '';
    const storyUse = item.story_use || '';
    const imageLabels = Array.isArray(item.planned_image_labels) ? item.planned_image_labels.join('、') : '';
    const locks = Array.isArray(item.visual_locks) ? item.visual_locks.join('、') : '';
    const appearances = Array.isArray(item.appearances) ? item.appearances.join('、') : '';
    const nameArg = encodeURIComponent(item.name || '未命名资产');
    const typeArg = encodeURIComponent(item.type_label || item.type || '资产');
    return `
        <article class="v2-asset-review-item">
            <strong>${escapeHtml(item.name || '未命名资产')}</strong>
            <span>原文证据：${escapeHtml(evidence || '缺少证据')}</span>
            <span>故事用途：${escapeHtml(storyUse || '待补充')}</span>
            <span>默认图片：${escapeHtml(imageLabels || '按类型生成')}</span>
            ${locks ? `<span>锁定点：${escapeHtml(locks)}</span>` : ''}
            ${appearances ? `<span>出现位置：${escapeHtml(appearances)}</span>` : ''}
            <div class="v2-asset-review-actions">
                <button class="ghost btn-sm" onclick="appendComicV2AssetReviewNote('modify', '${typeArg}', '${nameArg}')">修改这个资产</button>
                <button class="ghost btn-sm danger" onclick="appendComicV2AssetReviewNote('delete', '${typeArg}', '${nameArg}')">删除这个资产</button>
            </div>
        </article>
    `;
}

function appendComicV2AssetReviewNote(action, encodedTypeLabel, encodedName) {
    const notes = document.getElementById('comic-asset-review-notes');
    if (!notes) {
        toast('没有找到资产退回意见框，请刷新页面后重试。', 'error');
        return;
    }
    const typeLabel = decodeURIComponent(encodedTypeLabel || '资产');
    const name = decodeURIComponent(encodedName || '未命名资产');
    const line = action === 'delete'
        ? `删除【${typeLabel}】资产「${name}」，原因：这个资产不属于当前故事或不应作为独立资产。`
        : `修改【${typeLabel}】资产「${name}」，要求：请按我的补充重新判断名称、证据、用途、视觉锁定和默认图片规格。`;
    const current = notes.value.trim();
    notes.value = current ? `${current}\n${line}` : line;
    notes.focus();
    toast('已写入退回意见。确认无误后点击“按意见重新拆解”。', 'success');
}

function renderComicV2StageActions(status) {
    const stage = status?.stage || '';
    const deliveryUri = status?.delivery?.uri || '';
    const handoffManifestUri = status?.delivery?.handoff_manifest_uri || '';
    if (stage === 'visual_bible_review') {
        return [
            '<button class="btn-sm" onclick="approveComicV2VisualBible(this)">确认视觉母版</button>',
            '<button class="ghost btn-sm" onclick="reviseComicV2VisualBible()">退回视觉母版</button>',
        ].join('');
    }
    if (stage === 'asset_planning') {
        return '<button class="btn-sm" onclick="planComicV2Assets(this)">生成资产拆解审核包</button>';
    }
    if (stage === 'asset_review') {
        return [
            '<button class="btn-sm" onclick="approveComicV2Assets(this)">确认资产拆解</button>',
            '<button class="ghost btn-sm" onclick="reviseComicV2Assets()">按意见重新拆解</button>',
        ].join('');
    }
    if (stage === 'prompt_planning') {
        return '<button class="btn-sm" onclick="planComicV2Prompts(this)">生成专属提示词</button>';
    }
    if (stage === 'image_generation') {
        return '<button class="btn-sm" onclick="generateComicV2Images(this)">生成并质检基础资产图</button>';
    }
    if (stage === 'visual_review') {
        return [
            '<button class="btn-sm" onclick="generateComicV2Images(this)">重新生成未通过图片</button>',
            '<button class="ghost btn-sm" onclick="overrideComicV2VisualReview()">人工放行质检风险</button>',
        ].join('');
    }
    if (stage === 'document_generation') {
        return '<button class="btn-sm" onclick="buildComicV2Delivery(this)">生成 Word 制片画布</button>';
    }
    if (stage === 'ready_for_handoff' && deliveryUri) {
        const recoveryButton = renderComicV2QualityRecoveryButton(status);
        return [
            recoveryButton,
            `<a class="btn-sm" href="${escapeHtml(deliveryUri)}" target="_blank">下载 Word 制片画布</a>`,
            handoffManifestUri ? `<a class="ghost btn-sm" href="${escapeHtml(handoffManifestUri)}" target="_blank">下载引用清单</a>` : '',
        ].join('');
    }
    return '';
}

function renderComicV2QualityRecoveryButton(status) {
    const benchmark = status?.delivery?.quality_benchmark || {};
    const recovery = benchmark.recommended_recovery || {};
    const action = String(recovery.action || '');
    if (benchmark.package_quality_ready !== false || !action) return '';
    const supported = new Set([
        'restart_story_review',
        'revise_assets',
        'regenerate_prompts',
        'regenerate_images',
        'rebuild_delivery',
    ]);
    if (!supported.has(action)) return '';
    const label = recovery.label || '按质量问题退回处理';
    return `
        <div class="v2-quality-recovery-panel">
            ${renderRecoveryPlaybook(recovery)}
            <button class="btn-sm" onclick='recoverComicV2Quality(${JSON.stringify(action)}, this)'>${escapeHtml(label)}</button>
        </div>
    `;
}

function renderRecoveryPlaybook(recovery) {
    if (!recovery || typeof recovery !== 'object') return '';
    const steps = Array.isArray(recovery.operator_steps) ? recovery.operator_steps.filter(Boolean) : [];
    const preserves = Array.isArray(recovery.preserves) ? recovery.preserves.filter(Boolean) : [];
    const clears = Array.isArray(recovery.clears) ? recovery.clears.filter(Boolean) : [];
    const expectedStage = recovery.expected_stage || '';
    const description = recovery.description || '';
    if (!steps.length && !preserves.length && !clears.length && !expectedStage && !description) return '';
    return `
        <div class="recovery-playbook">
            <div class="recovery-playbook-head">
                <strong>恢复说明</strong>
                ${expectedStage ? `<span>预计退回：${escapeHtml(expectedStage)}</span>` : ''}
            </div>
            ${description ? `<p>${escapeHtml(description)}</p>` : ''}
            <div class="recovery-playbook-grid">
                ${preserves.length ? `
                    <div>
                        <b>会保留</b>
                        <small>${escapeHtml(preserves.join('、'))}</small>
                    </div>
                ` : ''}
                ${clears.length ? `
                    <div>
                        <b>会清除</b>
                        <small>${escapeHtml(clears.join('、'))}</small>
                    </div>
                ` : ''}
            </div>
            ${steps.length ? `
                <ol>
                    ${steps.map(step => `<li>${escapeHtml(step)}</li>`).join('')}
                </ol>
            ` : ''}
        </div>
    `;
}

function renderComicDepartmentStep(dept) {
    const uiStatus = dept.ui_status || dept.status || 'waiting';
    const issues = dept.blocking_issues || [];
    const checkpoint = dept.human_checkpoint || '';
    return `
        <div class="department-step ${escapeHtml(uiStatus)}">
            <div class="department-step-top">
                <strong>${escapeHtml(dept.name || dept.department_id || '')}</strong>
                <span>${escapeHtml(dept.status_label || uiStatus)}</span>
            </div>
            <p>${escapeHtml((dept.outputs || []).join('、') || '等待产出')}</p>
            ${checkpoint ? `<small>${escapeHtml(checkpoint)}</small>` : ''}
            ${issues.length ? `<small class="danger">${escapeHtml(issues.join('；'))}</small>` : ''}
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
    const imagePreview = (artifact.artifact_type === 'generated_image' || artifact.artifact_type === 'comic_v2_generated_image') && artifact.uri
        ? `<div class="evidence-preview"><img src="${escapeHtml(artifact.uri)}" alt="${escapeHtml(artifact.title)}"></div>`
        : '';
    const downloadAction = artifact.uri
        ? `<a class="ghost btn-sm" href="${escapeHtml(artifact.uri)}" target="_blank">下载/打开文件</a>`
        : '';
    const regenerateAction = (artifact.artifact_type === 'generated_image' || artifact.artifact_type === 'comic_v2_generated_image')
        ? `<button class="ghost btn-sm" onclick="regenerateComicImage(${index})">重生成这张图</button>`
        : '';
    const reviewStatus = (artifact.metadata || {}).review_status || 'pending';
    const assetReviewAction = artifact.artifact_type === 'asset_review_package' && reviewStatus !== 'approved'
        ? (reviewStatus === 'revision_requested'
            ? `<button class="btn-sm" onclick="submitComicTask({ revisionMode: true })">按退回意见重新拆解</button>`
            : `<button class="ghost btn-sm" onclick="requestComicAssetRevision()">退回补充</button><button class="btn-sm" onclick="approveComicAssetsAndSubmit()">确认拆解无误，继续生成</button>`)
        : '';
    const bindingPanel = renderComicArtifactBinding(artifact);
    const identityPanel = renderComicV2AssetIdentityPanel(artifact);
    const schemaGatePanel = renderArtifactSchemaGatePanel(artifact);
    detail.innerHTML = `
        <div class="artifact-detail-head">
            <span class="artifact-type">${escapeHtml(artifact.artifact_type)}</span>
            <strong>${escapeHtml(artifact.title)}</strong>
            ${downloadAction}
            ${regenerateAction}
            ${assetReviewAction}
        </div>
        ${schemaGatePanel}
        ${bindingPanel}
        ${identityPanel}
        ${imagePreview}
        <div class="artifact-detail-body">${simpleMarkdown(artifact.content || '') || '<em>空内容</em>'}</div>
    `;
}

function renderComicV2AssetIdentityPanel(artifact) {
    const identity = comicV2AssetIdentityForArtifact(artifact);
    if (!identity) return '';
    const asset = identity.asset || {};
    const records = identity.records || [];
    const prompts = identity.prompts || [];
    const shots = identity.shots || [];
    const baseline = records.find(record => record.is_identity_baseline) || records[0] || {};
    return `
        <div class="v2-asset-identity-panel">
            <div class="v2-asset-identity-head">
                <div>
                    <strong>资产身份证</strong>
                    <span>${escapeHtml(asset.asset_id || identity.asset_id || '')} · ${escapeHtml(asset.name || '')}</span>
                </div>
                <b>${escapeHtml(asset.type_label || asset.asset_type || '')}</b>
            </div>
            <div class="v2-asset-identity-grid">
                <div><span>资产ID</span><code>${escapeHtml(asset.asset_id || identity.asset_id || '')}</code></div>
                <div><span>原文证据</span><p>${escapeHtml(asset.evidence_quote || asset.source_evidence || '未记录')}</p></div>
                <div><span>故事用途</span><p>${escapeHtml(asset.story_purpose || asset.story_use || '未记录')}</p></div>
                <div><span>计划图片</span><p>${escapeHtml((asset.planned_images || asset.planned_image_labels || []).join('、') || '未记录')}</p></div>
                <div><span>身份基准图</span><code>${escapeHtml(baseline.image_id || asset.identity_baseline_image_id || '等待生成')}</code></div>
                <div><span>视觉锁定</span><p>${escapeHtml((asset.visual_locks || []).join('、') || '未记录')}</p></div>
            </div>
            <div class="v2-asset-reference-chain">
                <strong>引用链路</strong>
                <span>图片 ${records.length} 张 · 提示词 ${prompts.length} 条 · 引用镜头 ${shots.length} 个</span>
                ${records.length ? `<small>图片：${escapeHtml(records.map(record => `${record.image_kind || ''}/${record.image_id || ''}`).join('、'))}</small>` : ''}
                ${prompts.length ? `<small>提示词：${escapeHtml(prompts.map(prompt => prompt.image_kind || prompt.object_id || '').filter(Boolean).join('、'))}</small>` : ''}
                ${shots.length ? `<small>引用镜头：${escapeHtml(shots.map(shot => shot.shot_id || shot.story_beat || '').filter(Boolean).join('、'))}</small>` : ''}
            </div>
        </div>
    `;
}

function comicV2AssetIdentityForArtifact(artifact) {
    if (!currentComicV2Status) return null;
    const metadata = artifact.metadata || {};
    const titleAssetId = String(artifact.title || '').split('/')[0].trim();
    const assetId = metadata.asset_id || metadata.source_id || metadata.object_id || titleAssetId;
    const items = currentComicV2Status.asset_manifest?.items || [];
    const prompts = currentComicV2Status.prompt_package?.prompts || [];
    const records = currentComicV2Status.image_production?.records || [];
    const shots = currentComicV2Status.prompt_package?.shots || [];
    const asset = items.find(item => item.asset_id === assetId);
    if (!asset) return null;
    return {
        asset_id: assetId,
        asset,
        prompts: prompts.filter(prompt => prompt.object_id === assetId),
        records: records.filter(record => record.asset_id === assetId),
        shots: shots.filter(shot => (shot.reference_asset_ids || []).includes(assetId)),
    };
}

async function regenerateComicImage(index) {
    const artifact = currentComicArtifacts[index];
    if (!artifact || (artifact.artifact_type !== 'generated_image' && artifact.artifact_type !== 'comic_v2_generated_image')) return;
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
    currentComicAssistantMessage = '';
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
    currentComicAssistantMessage = result.assistant_message || '';
    renderComicCabinet();
    if (currentComicCabinetSession?.llm_fallback_error) {
        toast(`主创大模型没有正常返回，当前是规则兜底：${currentComicCabinetSession.llm_fallback_error}`, 'error');
    }
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
        const messages = [...(currentComicCabinetSession.messages || [])];
        const assistantFallback = currentComicAssistantMessage && !messages.some(msg => msg.role === 'assistant')
            ? [{ role: 'assistant', content: currentComicAssistantMessage }]
            : [];
        const modelWarning = renderComicCabinetModelWarning(currentComicCabinetSession);
        chatHistory.innerHTML = modelWarning + [...messages, ...assistantFallback].map(msg => {
            const roleClass = msg.role === 'user' ? 'chat-user' : 'chat-assistant';
            const roleName = msg.role === 'user' ? '你' : '主创对话官';
            return `<div class="chat-message ${roleClass}">
                <div class="chat-role">${roleName}</div>
                <div class="chat-content">${escapeHtml(msg.content)}</div>
            </div>`;
        }).join('') + renderComicSuggestedReplies();
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    if (proposalContainer) {
        proposalContainer.style.display = (hasStoryDraft && !isConfirmed) ? '' : 'none';
    }
    
    if (confirmedPanel) {
        confirmedPanel.style.display = isConfirmed ? '' : 'none';
    }

    if (scriptPreview) {
        const modelWarning = renderComicCabinetModelWarning(currentComicCabinetSession);
        scriptPreview.innerHTML = currentComicScriptPreview
            ? modelWarning + simpleMarkdown(formatComicStoryForDisplay(currentComicScriptPreview))
            : modelWarning;
    }
    if (confirmedPreview) {
        confirmedPreview.innerHTML = currentComicConfirmedScript
            ? simpleMarkdown(formatComicStoryForDisplay(currentComicConfirmedScript, { confirmed: true }))
            : '';
    }
}

function renderComicSuggestedReplies() {
    const replies = currentComicCabinetSession?.story_state?.suggested_replies || [];
    if (!replies.length) return '';
    return `<div class="comic-suggested-replies">
        ${replies.map((reply, index) => `
            <button type="button" class="comic-suggested-reply" onclick="selectComicSuggestedReply(${index})">
                ${escapeHtml(reply)}
            </button>
        `).join('')}
    </div>`;
}

function selectComicSuggestedReply(index) {
    const replies = currentComicCabinetSession?.story_state?.suggested_replies || [];
    const reply = replies[index] || '';
    const input = document.getElementById('comic-chat-input');
    if (!reply || !input) return;
    input.value = reply;
    input.focus();
}

function renderComicCabinetModelWarning(session) {
    const error = session?.llm_fallback_error || '';
    if (!error) return '';
    return `<div class="comic-model-warning">
        <strong>主创模型没有正常返回</strong>
        <span>这不是正式模型输出，当前内容来自规则兜底。请检查内阁或中书省模型配置后重试。</span>
        <small>${escapeHtml(error)}</small>
    </div>`;
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
    if (!(await ensureComicCapabilities(['story_planning']))) return;
    const confirmationNotes = document.getElementById('comic-chat-input')?.value.trim() || '';
    const button = document.getElementById('comic-confirm-start-btn');
    const originalText = button?.textContent || '确认故事并开始生成';
    const actionLabel = '确认故事并创建资产拆解';
    if (button) {
        button.disabled = true;
        button.textContent = '确认中...';
    }
    currentComicV2Status = currentComicV2Status || {
        pipeline_version: 2,
        status: 'running',
        stage: 'asset_planning',
        current_agent: '中书省 / 门下省',
        current_object: '确认故事与资产拆解入口',
        blocking_reason: '',
        next_action: '正在锁定确认故事，随后生成视觉母版和资产拆解入口。',
        completed: 1,
        total: 7,
    };
    if (currentComicV2Status.status === 'not_started') {
        currentComicV2Status = {
            ...currentComicV2Status,
            status: 'running',
            stage: 'asset_planning',
            current_agent: '中书省 / 门下省',
            current_object: '确认故事与资产拆解入口',
            blocking_reason: '',
            next_action: '正在锁定确认故事，随后生成视觉母版和资产拆解入口。',
        };
    }
    currentComicV2ActionError = null;
    currentComicV2PendingAction = buildComicV2PendingAction(actionLabel, currentComicV2Status);
    renderComicPackageBoard(currentComicArtifacts);
    try {
        toast('正在确认故事，并创建资产拆解任务...', 'success');
        const result = await API.post('/api/comic/confirm-script', {
            workspace_id: currentComicWorkspace,
            office_id: activeComicOfficeId(),
            session: currentComicCabinetSession,
            confirmation_notes: confirmationNotes,
        });
        await API.post(`/api/workspaces/${currentComicWorkspace}/comic/v2/plan-confirmed`, {});
        currentComicV2PendingAction = null;
        if (!result.confirmed_script) {
            throw new Error('后端没有返回确认版故事，请查看日志确认故事是否锁定成功。');
        }
        currentComicConfirmedScript = result.confirmed_script || null;
        if (currentComicCabinetSession) {
            currentComicCabinetSession.confirmed_script = result.confirmed_script || null;
            currentComicCabinetSession.confirmed = true;
        }
        renderComicCabinet();
        document.getElementById('comic-confirmed-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        await refreshComicV2Panel('确认版故事已锁定，请先审核视觉母版。');
        await loadComicWorkspaces();
    } catch (e) {
        currentComicV2PendingAction = null;
        const message = formatApiError(e);
        currentComicV2ActionError = {
            label: actionLabel,
            message,
            detail: e?.detail || null,
            status: e?.status || null,
        };
        renderComicPackageBoard(currentComicArtifacts);
        toast('确认并开始生成失败: ' + message, 'error');
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

async function runComicV2Action(button, label, action) {
    if (!currentComicWorkspace) {
        toast('请先选择一个漫剧项目', 'error');
        return null;
    }
    const original = button?.textContent || '';
    if (button) {
        button.disabled = true;
        button.textContent = `${label}...`;
    }
    currentComicV2PendingAction = buildComicV2PendingAction(label, currentComicV2Status);
    renderComicPackageBoard(currentComicArtifacts);
    try {
        const result = await action();
        currentComicV2PendingAction = null;
        await refreshComicV2Panel(`${label}完成`);
        return result;
    } catch (e) {
        currentComicV2PendingAction = null;
        const message = formatApiError(e);
        currentComicV2ActionError = {
            label,
            message,
            detail: e?.detail || null,
            status: e?.status || null,
        };
        renderComicPackageBoard(currentComicArtifacts);
        toast(`${label}失败: ${message}`, 'error');
        return null;
    } finally {
        if (button) {
            button.disabled = false;
            button.textContent = original;
        }
    }
}

function setComicV2BlockingActionError(label, blocked) {
    const detail = blocked && typeof blocked === 'object' ? blocked : {};
    currentComicV2ActionError = {
        label,
        message: detail.next_action || detail.impact || '请先补齐当前能力后重试。',
        detail: {
            department: detail.owner_label || detail.department || detail.title || '当前能力',
            reason: detail.title || detail.reason || detail.id || '能力未就绪',
            impact: detail.impact || '当前步骤继续执行可能无法生成可用结果。',
            next_action: detail.next_action || detail.impact || '请先到模型页或预检面板补齐对应配置。',
        },
        status: detail.status || 'preflight_blocked',
    };
    renderComicPackageBoard(currentComicArtifacts);
}

async function ensureComicCapabilities(capabilityIds, options = {}) {
    const officeId = activeComicOfficeId();
    if (!currentOfficePreflight || currentOfficePreflight.office_id !== officeId) {
        currentOfficePreflight = await loadOfficePreflight(officeId, 'comic-preflight-panel');
    }
    if (!currentOfficePreflight) {
        toast('启动检查暂时不可用，请刷新工作台后重试。', 'error');
        return false;
    }
    const blockedStatuses = options.blockedStatuses || ['blocked', 'missing'];
    const capabilities = currentOfficePreflight.capabilities || [];
    const blocked = capabilities.find(item =>
        capabilityIds.includes(item.id) && blockedStatuses.includes(item.status)
    );
    if (!blocked) return true;

    const action = blocked.next_action || blocked.impact || '请先到模型页补齐对应配置。';
    setComicV2BlockingActionError(blocked.title || '能力预检未通过', blocked);
    toast(`${blocked.title || '当前能力'}暂时不能继续：${action}`, 'error');
    document.getElementById('comic-preflight-panel')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    return false;
}

async function approveComicV2VisualBible(button) {
    return runComicV2Action(button, '确认视觉母版', () =>
        API.post(`/api/workspaces/${currentComicWorkspace}/comic/v2/visual-bible/approve`, {})
    );
}

async function reviseComicV2VisualBible() {
    const revision = window.prompt('你希望视觉母版怎么改？例如：更偏古风水墨，禁止现代材质。', '');
    if (!revision) return;
    await runComicV2Action(null, '重写视觉母版', () =>
        API.post(`/api/workspaces/${currentComicWorkspace}/comic/v2/visual-bible/revise`, { revision_request: revision })
    );
}

async function planComicV2Assets(button) {
    if (!(await ensureComicCapabilities(['story_planning', 'asset_planning']))) return null;
    return runComicV2Action(button, '生成资产拆解审核包', () =>
        API.post(`/api/workspaces/${currentComicWorkspace}/comic/v2/assets/plan`, {})
    );
}

async function approveComicV2Assets(button) {
    return runComicV2Action(button, '确认资产拆解', () =>
        API.post(`/api/workspaces/${currentComicWorkspace}/comic/v2/assets/approve`, {})
    );
}

async function reviseComicV2Assets() {
    if (!(await ensureComicCapabilities(['story_planning', 'asset_planning']))) return;
    const notes = document.getElementById('comic-asset-review-notes')?.value.trim()
        || window.prompt('你希望这次拆解怎么改？例如：缺少玉佩道具；删除故事里没有出现的角色。', '');
    if (!notes) {
        toast('请先写清楚要补充或删除什么资产', 'error');
        return;
    }
    await runComicV2Action(null, '重新拆解资产', () =>
        API.post(`/api/workspaces/${currentComicWorkspace}/comic/v2/assets/revise`, { revision_request: notes })
    );
    toast('资产重拆已提交，请核对新版清单的新增、删除和修改。', 'success');
}

async function planComicV2Prompts(button) {
    if (!(await ensureComicCapabilities(['prompt_planning']))) return null;
    return runComicV2Action(button, '生成专属提示词', () =>
        API.post(`/api/workspaces/${currentComicWorkspace}/comic/v2/prompts/plan`, {})
    );
}

async function generateComicV2Images(button) {
    if (!(await ensureComicCapabilities(['image_generation', 'visual_review']))) return null;
    return runComicV2Action(button, '生成并质检基础资产图', () =>
        API.post(`/api/workspaces/${currentComicWorkspace}/comic/v2/images/generate`, {})
    );
}

async function overrideComicV2VisualReview() {
    const reason = window.prompt('为什么可以人工放行？请写清楚后续修正方式。', '');
    if (!reason) return;
    await runComicV2Action(null, '人工放行质检风险', () =>
        API.post(`/api/workspaces/${currentComicWorkspace}/comic/v2/images/override`, { reason })
    );
}

async function buildComicV2Delivery(button) {
    if (!(await ensureComicCapabilities(['local_output']))) return null;
    return runComicV2Action(button, '生成 Word 制片画布', () =>
        API.post(`/api/workspaces/${currentComicWorkspace}/comic/v2/delivery/build`, {})
    );
}

async function recoverComicV2Quality(action, button) {
    if (action === 'restart_story_review') {
        unconfirmComicScript();
        document.getElementById('comic-idea')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        toast('旧交付已保留。请重新确认故事后创建新生产版本。', 'success');
        return null;
    }
    const recovered = await runComicV2Action(button, '按质量基准退回', () =>
        API.post(`/api/workspaces/${currentComicWorkspace}/comic/v2/quality/recover`, { action })
    );
    if (!recovered) return null;
    if (action === 'regenerate_prompts') return planComicV2Prompts(null);
    if (action === 'regenerate_images') return generateComicV2Images(null);
    if (action === 'rebuild_delivery') return buildComicV2Delivery(null);
    if (action === 'revise_assets') {
        focusComicAssetReview();
        toast('已退回资产审核。写清修改意见后点击“按意见重新拆解”。', 'success');
    }
    return recovered;
}

async function submitComicTask(options = {}) {
    const revisionMode = Boolean(options.revisionMode);
    const blockingReviewIndex = latestBlockingComicAssetReviewIndex(currentComicArtifacts || []);
    if (blockingReviewIndex >= 0 && !revisionMode) {
        focusComicAssetReview();
        toast('请先确认资产拆解包，再继续生成图片和 Word 画布', 'error');
        return;
    }
    const req = buildComicRequest(revisionMode ? {
        revisionNotes: document.getElementById('comic-asset-review-notes')?.value.trim() || latestComicAssetRevisionNotes(),
    } : {});
    if (!req) return;
    try {
        const r = await API.post('/api/tasks', {
            user_request: req,
            office_id: activeComicOfficeId(),
            template_id: null,
            workspace_id: currentComicWorkspace,
        });
        currentComicWorkspace = r.workspace_id;
        toast(revisionMode ? '已按退回意见重新生成资产拆解审核包' : '已开始生成漫剧制片包和 Word 画布', 'success');
        await loadComicWorkspaces();
        await Promise.all([
            loadComicRuntimeStatus(currentComicWorkspace),
            loadComicArtifacts(currentComicWorkspace),
            loadComicTimeline(currentComicWorkspace),
        ]);
        watchComicTask(r.task_id, currentComicWorkspace);
    } catch (e) {
        toast('提交失败: ' + e.message, 'error');
    }
}

function latestComicAssetRevisionNotes() {
    const review = latestComicAssetReview(currentComicArtifacts || []);
    return ((review?.artifact?.metadata || {}).reviewer_notes || '').trim();
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
        toast('已退回资产拆解。请修改要求，然后点击“按退回意见重新拆解”。', 'success');
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
            await loadComicRuntimeStatus(workspaceId);
            if (task.status === 'needs_review' || task.current_phase === 'asset_review_pending') {
                stopComicTaskPolling();
                await Promise.all([loadComicArtifacts(workspaceId), loadComicRuntimeStatus(workspaceId)]);
                focusComicAssetReview();
                toast('资产拆解审核包已生成，请先确认人物、道具、场景和分镜输入', 'success');
                return;
            }
            if (task.status === 'completed' || task.status === 'failed' || task.status === 'interrupted' || task.current_phase === 'interrupted') {
                stopComicTaskPolling();
                await Promise.all([loadComicArtifacts(workspaceId), loadComicRuntimeStatus(workspaceId)]);
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

function buildComicRequest(options = {}) {
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
    const revisionNotes = (options.revisionNotes || '').trim();
    const scriptNotes = revisionNotes
        ? `Asset revision notes: ${revisionNotes}\n本次任务只需要根据退回意见重新生成资产拆解审核包，暂时无需继续生成图片和 Word 画布。`
        : '';
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
    const characterSource = document.getElementById('comic-character-source')?.value.trim() || '';
    const styleReference = document.getElementById('comic-style-reference')?.value.trim() || '';
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
    return {
        idea: derivedIdea,
        genre,
        length,
        platform,
        visual_style: style,
        extra,
        input_mode: inputMode,
        script_text: scriptText,
        character_source: characterSource,
        style_reference: styleReference,
    };
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
    const referenceSource = [
        fields.character_source ? `Character references:\n${fields.character_source}` : '',
        fields.style_reference ? `Style references:\n${fields.style_reference}` : '',
    ].filter(Boolean).join('\n\n');
    return {
        ...fields,
        extra: [fields.extra || '', referenceSource, scriptSource].filter(Boolean).join('\n\n'),
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
        bingbu: '镜头提示词',
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

const MODEL_REQUIREMENT_GROUPS = {
    default: [
        { title: '关键部门先填', agents: ['zhongshu', 'menxia', 'shangshu', 'gongbu'] },
        { title: '数据与取证辅助', agents: ['hubu', 'bingbu', 'xingbu'] },
        { title: '记忆与交付说明', agents: ['libu', 'libu_comm'] },
    ],
    research: [
        { title: '关键部门先填', agents: ['zhongshu', 'menxia', 'hubu', 'gongbu'] },
        { title: '取证与质检', agents: ['bingbu', 'xingbu'] },
        { title: '调度、归档与交付', agents: ['shangshu', 'libu', 'libu_comm'] },
    ],
    comic_production: [
        { title: '关键部门先填', agents: ['zhongshu', 'menxia', 'shangshu'] },
        { title: '资产、提示词与交付', agents: ['hubu', 'libu', 'libu_comm', 'bingbu'] },
        { title: '生图模型与视觉理解', agents: ['gongbu', 'xingbu'] },
    ],
};

function modelRequirement(agentId) {
    const requirement = {
        ...(MODEL_REQUIREMENTS.default[agentId] || {}),
        ...((MODEL_REQUIREMENTS[MODEL_OFFICE_ID] || {})[agentId] || {}),
    };
    return {
        ...requirement,
        test: requirement.test || modelRequirementTest(requirement),
        impact: requirement.impact || modelRequirementImpact(agentId, requirement),
    };
}

function modelRequirementTest(requirement) {
    const type = requirement.type || '';
    if (type.includes('生图')) return '点击测试会调用一次生图接口，确认 API Key、模型名和图片生成能力可用。';
    if (type.includes('视觉') || type.includes('图片理解')) return '点击测试会调用一次视觉理解接口，确认图片识别和质检能力可用。';
    return '点击测试会调用一次文本接口，确认 API Key、模型名和基础对话能力可用。';
}

function modelRequirementImpact(agentId, requirement) {
    if (MODEL_OFFICE_ID === 'comic_production') {
        const impact = {
            neige: '无法自然聊故事和锁定创作方向。',
            zhongshu: '无法生成故事合同、视觉母版和生产任务书。',
            menxia: '无法审查故事、人物、道具、场景是否缺漏。',
            bingbu: '无法生成镜头画面提示词和视频生成提示词。',
            xingbu: '可以继续生图，但无法自动检查图片一致性和画风问题。',
            gongbu: '可以先完成故事和提示词，但无法生成基础资产图片。',
        };
        if (impact[agentId]) return impact[agentId];
    }
    return requirement.use || '该部门会被阻塞，相关步骤需要补齐模型后才能继续。';
}

function agentName(id) {
    return AGENT_NAMES[id] || id;
}

function renderModelRequirementSummary() {
    const target = document.getElementById('model-requirement-summary');
    if (!target) return;
    const groups = MODEL_REQUIREMENT_GROUPS[MODEL_OFFICE_ID] || MODEL_REQUIREMENT_GROUPS.default;
    target.innerHTML = `
        <div class="model-summary-head">
            <div>
                <strong>${escapeHtml(OFFICE_LABELS[MODEL_OFFICE_ID] || OFFICE_LABELS.research)}模型需求</strong>
                <span>先按下面清单补齐关键部门，再逐个测试。每个办公室的 Key 和模型配置互相隔离。</span>
            </div>
        </div>
        <div class="model-summary-grid">
            ${groups.map(group => `
                <div class="model-summary-group">
                    <h4>${escapeHtml(group.title)}</h4>
                    ${group.agents.map(agentId => {
                        const requirement = modelRequirement(agentId);
                        return `
                            <div class="model-summary-item">
                                <b>${escapeHtml(agentName(agentId))}</b>
                                <span>${escapeHtml(requirement.type || '文本模型')}</span>
                                <small>${escapeHtml(requirement.key || '')}</small>
                            </div>
                        `;
                    }).join('')}
                </div>
            `).join('')}
        </div>
    `;
}

function renderModelSetupPath() {
    const target = document.getElementById('model-setup-path');
    if (!target) return;
    const officeName = OFFICE_LABELS[MODEL_OFFICE_ID] || OFFICE_LABELS.research || '当前办公室';
    const isComicProduction = MODEL_OFFICE_ID === 'comic_production';
    const steps = isComicProduction
        ? [
            { title: '先跑无 Key 演示', body: '先看固定样例、Word 制片画布和引用清单，不需要 API Key。' },
            { title: '最小可跑配置', body: '先补文本部门，让故事、资产拆解和提示词规划能跑通。' },
            { title: '完整制片配置', body: '再补刑部视觉理解模型和工部图片生成模型，进入图片质检和完整制片包。' },
            { title: '每个部门先点测试按钮', body: '测试通过后再进工作台，避免长任务中途发现模型不可用。' },
        ]
        : [
            { title: '先跑无 Key 演示', body: '先看固定样例、阶段报告和证据清单，不需要 API Key。' },
            { title: '最小可跑配置', body: '先补文本部门，让计划、报告和证据整理能跑通。' },
            { title: '完整工作配置', body: '再补视觉理解模型，用于截图识别、证据提取和质检。' },
            { title: '每个部门先点测试按钮', body: '测试通过后再提交真实任务，避免等待后才发现配置错误。' },
        ];
    target.innerHTML = `
        <div class="model-setup-head">
            <strong>${escapeHtml(officeName)}第一次配置路线</strong>
            <span>按这个顺序配置，不用一开始填满所有模型。</span>
        </div>
        <div class="model-setup-steps">
            ${steps.map((step, index) => `
                <div class="model-setup-step">
                    <b>${index + 1}</b>
                    <div>
                        <strong>${escapeHtml(step.title)}</strong>
                        <span>${escapeHtml(step.body)}</span>
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}

async function loadModels() {
    const officeLabel = document.getElementById('model-office-label');
    if (officeLabel) officeLabel.textContent = `当前：${OFFICE_LABELS[MODEL_OFFICE_ID] || OFFICE_LABELS.research}`;
    await loadOfficePreflight(MODEL_OFFICE_ID, 'model-preflight-panel');
    renderModelSetupPath();
    renderModelRequirementSummary();
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
                <div class="model-requirement-meta">
                    <span><b>测试方式</b>${escapeHtml(requirement.test || '')}</span>
                    <span><b>缺失影响</b>${escapeHtml(requirement.impact || '')}</span>
                </div>
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
                    <input type="password" value="" placeholder="${cfg.has_api_key ? '已配置，留空保持不变' : '尚未配置，请填写'}" onchange="updateModel('${id}', 'api_key', this.value)">
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

async function loadOfficePreflight(officeId, targetId = '') {
    const target = targetId ? document.getElementById(targetId) : null;
    if (target) {
        target.innerHTML = '<div class="empty-state">正在检查当前办公室能力...</div>';
    }
    try {
        const result = await API.get(`/api/offices/${officeId}/preflight`);
        if (officeId === activeComicOfficeId()) {
            currentOfficePreflight = result;
        }
        renderOfficePreflight(result, targetId);
        if (officeId === 'comic_production' || officeId === 'comic') {
            try {
                const readiness = await API.get(`/api/offices/${officeId}/readiness`);
                renderProductReadiness(readiness, targetId);
            } catch (e) {}
            try {
                const realReadiness = await API.get(`/api/offices/${officeId}/real-production-readiness`);
                renderRealProductionReadiness(realReadiness, targetId);
            } catch (e) {}
        }
        return result;
    } catch (e) {
        if (target) {
            target.innerHTML = `<div class="preflight-card preflight-blocked">
                <strong>启动检查失败</strong>
                <p>${escapeHtml(e.message || String(e))}</p>
            </div>`;
        }
        return null;
    }
}

async function loadSystemPreflight() {
    const target = document.getElementById('system-preflight-panel');
    if (!target) return null;
    target.innerHTML = '<div class="empty-state">正在检查本机运行环境...</div>';
    try {
        const result = await API.get('/api/system/preflight');
        renderSystemPreflight(result);
        return result;
    } catch (e) {
        target.innerHTML = `<div class="preflight-card preflight-blocked">
            <div class="preflight-head">
                <div>
                    <strong>系统启动检查失败</strong>
                    <p>${escapeHtml(e.message || String(e))}</p>
                </div>
                <span class="badge badge-err">需检查</span>
            </div>
        </div>`;
        return null;
    }
}

async function loadOfficeHallAvailability() {
    await Promise.all(OFFICE_HALL_PREFLIGHTS.map(async ({ officeId, targetId }) => {
        const target = document.getElementById(targetId);
        if (!target) return null;
        target.className = 'office-availability checking';
        target.innerHTML = '<b>可用性检查中</b><small>正在确认办公室能力</small>';
        try {
            const result = await API.get(`/api/offices/${officeId}/preflight`);
            renderOfficeHallAvailability(result, targetId);
            return result;
        } catch (e) {
            target.className = 'office-availability blocked';
            target.innerHTML = `<b>检查失败</b><small>${escapeHtml(e.message || String(e))}</small>`;
            return null;
        }
    }));
}

function renderOfficeHallAvailability(result, targetId) {
    const target = document.getElementById(targetId);
    if (!target || !result) return;
    const status = result.status || 'unknown';
    const summary = result.next_action || result.summary || '';
    target.className = `office-availability ${escapeHtml(status)}`;
    target.innerHTML = `
        <b>${escapeHtml(preflightStatusText(status))}</b>
        <small>${escapeHtml(summary)}</small>
    `;
}

async function loadOfficeLaunchGates() {
    const target = document.getElementById('office-launch-gates-panel');
    if (!target) return;
    target.innerHTML = '<div class="launch-gates-loading">正在检查办公室上线门禁...</div>';
    try {
        const audits = await Promise.all(OFFICE_HALL_LAUNCH_GATES.map(officeId =>
            API.get(`/api/offices/${officeId}/launch-gates`)
        ));
        renderOfficeLaunchGates(audits);
    } catch (e) {
        target.innerHTML = `<div class="launch-gates-error">上线门禁检查失败：${escapeHtml(e.message || String(e))}</div>`;
    }
}

function renderOfficeLaunchGates(audits) {
    const target = document.getElementById('office-launch-gates-panel');
    if (!target) return;
    const items = Array.isArray(audits) ? audits : [];
    const readyCount = items.filter(item => item.status === 'ready').length;
    target.innerHTML = `
        <section class="launch-gates-card">
            <div class="launch-gates-head">
                <div>
                    <strong>办公室上线门禁</strong>
                    <p>判断每个办公室能不能公开展示、复现和进入真实使用链路。</p>
                </div>
                <span>${escapeHtml(readyCount)} / ${escapeHtml(items.length)} ready</span>
            </div>
            <div class="launch-gate-grid">
                ${items.map(audit => {
                    const gates = Array.isArray(audit.gates) ? audit.gates : [];
                    const passed = gates.filter(gate => gate.status === 'passed').length;
                    const gate = gates.find(gate => gate.status !== 'passed') || gates[0] || {};
                    const evidenceLinks = gates.flatMap(gate => Array.isArray(gate.evidence_links) ? gate.evidence_links : []);
                    const statusClass = audit.status === 'ready' ? 'ready' : 'needs-work';
                    return `
                        <article class="launch-gate-office ${statusClass}">
                            <div>
                                <strong>${escapeHtml(audit.office_name || OFFICE_LABELS[audit.office_id] || audit.office_id || '')}</strong>
                                <span>${escapeHtml(audit.status === 'ready' ? '可公开展示' : '需要补齐')}</span>
                            </div>
                            <p>${escapeHtml(passed)} / ${escapeHtml(gates.length)} 项门禁通过</p>
                            <small>${escapeHtml(gate.next_action || '保持证据随办公室流程同步更新。')}</small>
                            ${evidenceLinks.length ? `
                                <div class="launch-gate-links">
                                    ${evidenceLinks.slice(0, 3).map(link => `<a href="${escapeHtml(link.uri || '#')}" target="_blank">${escapeHtml(link.label || '查看证据')}</a>`).join('')}
                                </div>
                            ` : ''}
                        </article>
                    `;
                }).join('')}
            </div>
        </section>
    `;
}

function renderSystemPreflight(result) {
    const target = document.getElementById('system-preflight-panel');
    if (!target || !result) return;
    const status = result.status || 'unknown';
    const checks = (result.checks || []).slice(0, 5);
    const availableModes = Array.isArray(result.available_modes) ? result.available_modes : [];
    const limitedFeatures = Array.isArray(result.limited_features) ? result.limited_features : [];
    target.innerHTML = `
        <div class="preflight-card preflight-${escapeHtml(status)}">
            <div class="preflight-head">
                <div>
                    <strong>系统启动检查</strong>
                    <p>${escapeHtml(result.summary || '')}</p>
                </div>
                <span class="badge ${preflightBadgeClass(status)}">${escapeHtml(preflightStatusText(status))}</span>
            </div>
            <div class="preflight-next">下一步：${escapeHtml(result.next_action || '')}</div>
            ${availableModes.length ? `
                <div class="preflight-modes">
                    <b>当前可用模式</b>
                    <div>
                        ${availableModes.map(mode => `
                            <span title="${escapeHtml(mode.description || '')}">${escapeHtml(mode.label || mode.id || '')}</span>
                        `).join('')}
                    </div>
                </div>
            ` : ''}
            ${limitedFeatures.length ? `
                <div class="preflight-limited">
                    <b>暂不可用功能</b>
                    ${limitedFeatures.slice(0, 4).map(feature => `
                        <p><span>${escapeHtml(feature.label || feature.id || '')}</span>${escapeHtml(feature.reason || feature.next_action || '')}</p>
                    `).join('')}
                </div>
            ` : ''}
            <div class="preflight-grid">
                ${checks.map(item => `
                    <div class="preflight-item ${escapeHtml(item.status || '')}">
                        <span>${escapeHtml(item.title || item.id || '')}</span>
                        <small>${escapeHtml(item.status === 'ok' ? '已具备' : item.next_action || item.impact || '')}</small>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
}

function renderOfficePreflight(result, targetId = '') {
    const target = targetId ? document.getElementById(targetId) : null;
    if (!target || !result) return;
    const status = result.status || 'unknown';
    const capabilities = result.capabilities || [];
    const visible = capabilities.slice(0, 6);
    target.innerHTML = `
        <div class="preflight-card preflight-${escapeHtml(status)}">
            <div class="preflight-head">
                <div>
                    <strong>启动检查</strong>
                    <p>${escapeHtml(result.summary || '')}</p>
                </div>
                <span class="badge ${preflightBadgeClass(status)}">${escapeHtml(preflightStatusText(status))}</span>
            </div>
            <div class="preflight-next">下一步：${escapeHtml(result.next_action || '')}</div>
            <div class="preflight-grid">
                ${visible.map(item => {
                    const owner = [
                        item.office_id ? `办公室：${OFFICE_LABELS[item.office_id] || item.office_id}` : '',
                        item.owner_label ? `责任：${item.owner_label}` : '',
                        item.model_kind ? `类型：${item.model_kind}` : '',
                    ].filter(Boolean).join(' / ');
                    return `
                        <div class="preflight-item ${escapeHtml(item.status || '')}">
                            <span>${escapeHtml(item.title || item.id || '')}</span>
                            ${owner ? `<em class="preflight-owner">${escapeHtml(owner)}</em>` : ''}
                            <small>${escapeHtml(item.status === 'ok' ? '已具备' : item.next_action || item.impact || '')}</small>
                        </div>
                    `;
                }).join('')}
            </div>
        </div>
    `;
}

function renderProductReadiness(result, targetId = '') {
    const target = targetId ? document.getElementById(targetId) : null;
    if (!target || !result || result.status === 'not_applicable') return;
    const checks = (result.checks || []).slice(0, 6);
    const readyStatuses = ['ready_without_demo', 'ready_with_demo'];
    const status = readyStatuses.includes(result.status) ? 'ready' : 'partial';
    target.insertAdjacentHTML('beforeend', `
        <div class="preflight-card preflight-${escapeHtml(status)} product-readiness-card">
            <div class="preflight-head">
                <div>
                    <strong>产品 readiness</strong>
                    <p>${escapeHtml(result.summary || '')}</p>
                </div>
                <span class="badge ${preflightBadgeClass(status)}">${escapeHtml(readyStatuses.includes(result.status) ? '真实产品已具备' : '需继续补齐')}</span>
            </div>
            <div class="preflight-grid">
                ${checks.map(item => `
                    <div class="preflight-item ${item.status === 'passed' ? 'ok' : 'missing'}">
                        <span>${escapeHtml(item.title || item.id || '')}</span>
                        <small>${escapeHtml((item.evidence || []).join(' / ') || '缺少证据')}</small>
                    </div>
                `).join('')}
            </div>
        </div>
    `);
}

function renderRealProductionReadiness(result, targetId = '') {
    const target = targetId ? document.getElementById(targetId) : null;
    if (!target || !result || result.status === 'not_applicable') return;
    const status = result.status || 'unknown';
    const uiStatus = status === 'ready_for_real_run' ? 'ready' : (status === 'blocked' ? 'blocked' : 'partial');
    const label = status === 'ready_for_real_run'
        ? '可真实生产'
        : (status === 'limited_planning_only' ? '只能先规划' : '暂不建议开工');
    const capabilities = Array.isArray(result.required_capabilities) ? result.required_capabilities : [];
    const inventory = result.handoff_inventory || {};
    const checklist = Array.isArray(result.operator_checklist) ? result.operator_checklist : [];
    target.insertAdjacentHTML('beforeend', `
        <div class="preflight-card preflight-${escapeHtml(uiStatus)} product-readiness-card real-production-readiness-card">
            <div class="preflight-head">
                <div>
                    <strong>真实生产前检查</strong>
                    <p>${escapeHtml(result.summary || '')}</p>
                </div>
                <span class="badge ${preflightBadgeClass(uiStatus)}">${escapeHtml(label)}</span>
            </div>
            <div class="preflight-next">下一步：${escapeHtml(result.next_action || '')}</div>
            <div class="preflight-modes">
                <b>当前开工判断</b>
                <div>
                    <span>完整制片包：${result.can_start_full_production ? '可以开始' : '暂不可开始'}</span>
                    <span>故事/资产/提示词：${result.can_start_limited_planning ? '可以先做' : '暂不可开始'}</span>
                    <span>真实质量通过：${escapeHtml(inventory.production_verified_count || 0)} 份</span>
                    <span>结构样例：${escapeHtml(inventory.demo_only_count || 0)} 份</span>
                </div>
            </div>
            <div class="preflight-grid">
                ${capabilities.map(item => `
                    <div class="preflight-item ${escapeHtml(item.status || '')}">
                        <span>${escapeHtml(item.title || item.id || '')}</span>
                        <em class="preflight-owner">${escapeHtml([item.owner_label, item.model_kind].filter(Boolean).join(' / '))}</em>
                        <small>${escapeHtml(item.status === 'ok' ? '已具备' : item.next_action || item.impact || '')}</small>
                    </div>
                `).join('')}
            </div>
            ${checklist.length ? `
                <div class="preflight-limited">
                    <b>开工前清单</b>
                    ${checklist.slice(0, 5).map(item => `<p><span>检查</span>${escapeHtml(item)}</p>`).join('')}
                </div>
            ` : ''}
        </div>
    `);
}

function preflightBadgeClass(status) {
    if (status === 'ready') return 'badge-ok';
    if (status === 'blocked') return 'badge-err';
    return 'badge-info';
}

function preflightStatusText(status) {
    if (status === 'ready') return '可开工';
    if (status === 'blocked') return '需先配置';
    if (status === 'partial') return '可分阶段推进';
    return '待检查';
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
                ${renderHistoryDeliverySummary(h.delivery_summary, true)}
            </td>
            <td><span class="badge badge-${h.status === 'completed' ? 'ok' : 'err'}">${h.status}</span></td>
            <td>${escapeHtml((h.completed_at || h.updated_at || h.created_at || '').replace('T',' ').substring(0,16))}</td>
            <td>
                <button class="btn-sm" onclick="viewHistoryDetail('${h.task_id}')">查看完整</button>
                ${h.word_canvas_uri ? `<a class="btn-sm ghost" href="${escapeHtml(h.word_canvas_uri)}" target="_blank">下载Word画布</a>` : ''}
                ${h.handoff_manifest_uri ? `<a class="btn-sm ghost" href="${escapeHtml(h.handoff_manifest_uri)}" target="_blank">下载引用清单</a>` : ''}
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
    const handoff = h.handoff_manifest_uri ? '，含引用清单' : '';
    const office = h.office_id ? `${h.office_id}办公室` : '工作区';
    return `${office} · ${count} 个产物${word}${handoff}`;
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
        const traceDownloadLink = item.comic_v2_trace_uri
            ? `<a class="ghost btn-sm" href="${escapeHtml(item.comic_v2_trace_uri)}" target="_blank">下载追溯记录</a>`
            : '';
        box.innerHTML = `
            <div class="artifact-detail-head">
                <span class="artifact-type">${escapeHtml(item.office_id || '')}</span>
                <strong>${escapeHtml(item.workspace_title || item.user_request || taskId)}</strong>
                ${traceDownloadLink}
                ${item.word_canvas_uri ? `<a class="ghost btn-sm" href="${escapeHtml(item.word_canvas_uri)}" target="_blank">下载Word画布</a>` : ''}
                ${item.handoff_manifest_uri ? `<a class="ghost btn-sm" href="${escapeHtml(item.handoff_manifest_uri)}" target="_blank">下载引用清单</a>` : ''}
                ${item.workspace_export_uri ? `<a class="ghost btn-sm" href="${escapeHtml(item.workspace_export_uri)}" target="_blank">导出全部</a>` : ''}
            </div>
            <div class="artifact-detail-body">
                ${report ? simpleMarkdown(report) : '<em>暂无最终报告预览</em>'}
                ${renderHistoryDeliverySummary(item.delivery_summary)}
                ${renderComicV2HistoryTrace(item.comic_v2_trace)}
                <div class="history-artifact-links">
                    ${artifacts.map(renderHistoryArtifactArchiveLink).join('')}
                </div>
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

function renderHistoryArtifactArchiveLink(artifact) {
    if (!artifact || !artifact.download_uri) return '';
    const label = artifact.title || artifact.artifact_type || artifact.artifact_id || 'artifact';
    return `
        <a class="ghost btn-sm" href="${escapeHtml(artifact.download_uri)}" target="_blank">
            下载归档 · ${escapeHtml(label)}
        </a>
    `;
}

function renderHistoryDeliverySummary(summary, compact = false) {
    if (!summary || !summary.status) return '';
    const statusLabel = {
        ready: '可交付',
        partial: '部分可用',
        needs_review: '需补齐',
        pending: '等待交付',
    }[summary.status] || summary.status;
    const files = Array.isArray(summary.downloadable_files) ? summary.downloadable_files : [];
    const missing = Array.isArray(summary.missing_items) ? summary.missing_items : [];
    const actions = Array.isArray(summary.recovery_actions) ? summary.recovery_actions : [];
    const promptQualityLabel = {
        ready: '通过',
        needs_review: '需复核',
        waiting: '待生成',
    }[summary.prompt_quality_status] || summary.prompt_quality_status || '未知';
    const packageQualityLabel = {
        production_quality_verified: '真实质量已验证',
        demo_structure_verified: '结构演示已验证',
        needs_review: '需复核',
        legacy_unverifiable: '旧版不可审计',
    }[summary.package_quality_claim] || summary.package_quality_claim || '待生成';
    return `
        <div class="history-delivery-summary ${compact ? 'compact' : ''} ${escapeHtml(summary.status)}">
            <div class="history-delivery-head">
                <strong>交付摘要</strong>
                <span>${escapeHtml(statusLabel)}</span>
            </div>
            <div class="history-delivery-grid">
                <span>资产 ${escapeHtml(summary.asset_count || 0)}</span>
                <span>镜头 ${escapeHtml(summary.shot_count || 0)}</span>
                <span>提示词 ${escapeHtml(summary.prompt_count || 0)}</span>
                <span>提示词门禁 ${escapeHtml(promptQualityLabel)}</span>
                <span>质检 ${escapeHtml(summary.visual_review_status || 'unknown')}</span>
                <span>制片包 ${summary.legacy_package ? '旧版不可审计' : `${escapeHtml(summary.package_quality_score || 0)}/100`}</span>
            </div>
            ${compact ? '' : `
                ${actions.length ? `
                    <div class="history-delivery-actions">
                        ${actions.map(action => `
                            <div class="history-delivery-action-card">
                                ${renderRecoveryPlaybook(action)}
                                <button class="ghost btn-sm" onclick="runHistoryRecoveryAction('${escapeJsAttr(action)}')">
                                    ${escapeHtml(action.label || '继续处理')}
                                </button>
                            </div>
                        `).join('')}
                    </div>
                ` : ''}
                <p>${escapeHtml(summary.next_action || '')}</p>
                ${summary.prompt_quality_summary ? `<small>提示词质量：${escapeHtml(summary.prompt_quality_summary)}</small>` : ''}
                ${summary.package_quality_summary ? `<small>制片包基准：${escapeHtml(packageQualityLabel)} · ${escapeHtml(summary.package_quality_summary)}</small>` : ''}
                <small>可下载：${escapeHtml(files.length ? files.join('、') : '暂无')}</small>
                <small>缺失项：${escapeHtml(missing.length ? missing.join('、') : '无')}</small>
            `}
        </div>
    `;
}

async function runHistoryRecoveryAction(encodedAction) {
    await retryTaskRecoveryAction(encodedAction);
    await loadHistory();
}

function renderComicV2HistoryTrace(trace) {
    if (!trace || !trace.story_id) return '';
    const visual = trace.visual_review || {};
    const audit = trace.delivery_audit || {};
    const quality = trace.prompt_quality || {};
    const benchmark = trace.quality_benchmark || {};
    const imageAssets = Array.isArray(trace.image_assets) ? trace.image_assets : [];
    const promptQualityLabel = {
        ready: '通过',
        needs_review: '需复核',
        waiting: '待生成',
    }[quality.status] || quality.status || '未知';
    const promptIssues = Array.isArray(quality.issues) ? quality.issues : [];
    const benchmarkLabel = {
        production_quality_verified: '真实质量已验证',
        demo_structure_verified: '结构演示已验证',
        needs_review: '需复核',
        legacy_unverifiable: '旧版不可审计',
    }[benchmark.status] || benchmark.status || '待生成';
    return `
        <h4>制片追溯</h4>
        <ul>
            <li><strong>故事版本</strong> · ${escapeHtml(trace.story_id)} / v${escapeHtml(trace.story_version || '')}</li>
            <li><strong>风格版本</strong> · ${escapeHtml(trace.style_id || '')} / v${escapeHtml(trace.style_version || '')}</li>
            <li><strong>资产版本</strong> · manifest v${escapeHtml(trace.manifest_version || '')}</li>
            <li><strong>提示词</strong> · 资产 ${escapeHtml(trace.asset_prompt_count || 0)} 条，镜头 ${escapeHtml(trace.shot_prompt_count || 0)} 条</li>
            <li><strong>提示词质量门禁</strong> · ${escapeHtml(promptQualityLabel)}，问题 ${escapeHtml(quality.issue_count || 0)} 项</li>
            <li><strong>视觉质检</strong> · 图片 ${escapeHtml(visual.record_count || 0)} 张，失败 ${escapeHtml(visual.failure_count || 0)} 项</li>
            <li><strong>交付审计</strong> · 资产 ${escapeHtml(audit.asset_count || 0)} 个，镜头 ${escapeHtml(audit.shot_count || 0)} 个，${audit.handoff_ready ? '可交付' : '需复查'}</li>
            <li><strong>制片包质量基准</strong> · ${escapeHtml(benchmarkLabel)}，${escapeHtml(benchmark.package_quality_score || 0)}/100，问题 ${escapeHtml(benchmark.issue_count || 0)} 项</li>
            <li><strong>引用清单</strong> · ${trace.handoff_manifest_uri ? `<a href="${escapeHtml(trace.handoff_manifest_uri)}" target="_blank">打开 JSON</a>` : '未生成'}</li>
        </ul>
        ${quality.summary ? `
            <div class="v2-prompt-quality history-prompt-quality ${escapeHtml(quality.status || '')}">
                <div class="v2-prompt-quality-head">
                    <strong>历史提示词门禁</strong>
                    <span>${escapeHtml(promptQualityLabel)}</span>
                </div>
                <p>${escapeHtml(quality.summary)}</p>
                <div class="v2-prompt-quality-grid">
                    <span>干净资产提示词 ${escapeHtml(quality.clean_asset_prompt_count || 0)} / ${escapeHtml(quality.asset_prompt_count || 0)}</span>
                    <span>导演镜头提示词 ${escapeHtml(quality.director_prompt_count || 0)} / ${escapeHtml(quality.shot_prompt_count || 0)}</span>
                    <span>问题 ${escapeHtml(quality.issue_count || 0)}</span>
                </div>
                ${promptIssues.length ? `
                    <ul class="v2-prompt-quality-issues">
                        ${promptIssues.slice(0, 4).map(issue => `
                            <li>${escapeHtml(issue.id || issue.scope || '提示词')}：${escapeHtml(issue.message || '')}</li>
                        `).join('')}
                    </ul>
                ` : ''}
            </div>
        ` : ''}
        ${benchmark.summary ? `
            <div class="v2-prompt-quality history-prompt-quality ${benchmark.package_quality_ready ? 'ready' : 'needs_review'}">
                <div class="v2-prompt-quality-head">
                    <strong>历史制片包质量基准</strong>
                    <span>${escapeHtml(benchmarkLabel)}</span>
                </div>
                <p>${escapeHtml(benchmark.summary)}</p>
                <div class="v2-prompt-quality-grid">
                    <span>综合分 ${escapeHtml(benchmark.package_quality_score || 0)} / 100</span>
                    <span>真实质量 ${benchmark.production_quality_verified ? '已验证' : '未验证'}</span>
                    <span>视觉证据 ${escapeHtml(benchmark.visual_evidence_level || 'unknown')}</span>
                </div>
                ${renderRecoveryPlaybook(benchmark.recommended_recovery)}
                ${(benchmark.limitations || []).length ? `<small>${escapeHtml(benchmark.limitations[0])}</small>` : ''}
            </div>
        ` : ''}
        ${renderComicV2HistoryImageAssets(imageAssets)}
        ${renderComicV2HistoryShotPackages(trace.shots)}
        ${renderComicV2LineageTimeline(trace.production_lineage)}
    `;
}

function renderComicV2HistoryImageAssets(images) {
    const items = Array.isArray(images) ? images.filter(image => image && image.image_id) : [];
    if (!items.length) return '';
    const visible = items.slice(0, 8);
    const hiddenCount = Math.max(0, items.length - visible.length);
    return `
        <section class="v2-shot-prompt-cards">
            <div class="v2-shot-prompt-head">
                <div>
                    <strong>图片资产追溯</strong>
                    <span>每张基础图保留生产角色、白底要求、质检状态和重试次数。</span>
                </div>
                <span>${items.length} 张图片</span>
            </div>
            <div class="v2-shot-card-grid">
                ${visible.map(image => `
                    <article class="v2-shot-card">
                        <h5>${escapeHtml(image.asset_id || image.image_id)}</h5>
                        <p>${escapeHtml(image.image_kind || '')} · ${escapeHtml(image.production_role || '未标记生产角色')}</p>
                        <p>状态 ${escapeHtml(image.status || 'unknown')} · 重试 ${escapeHtml(image.attempts || 0)} · ${image.clean_background_required ? '要求干净白底' : '不要求白底'}</p>
                        <p>质检 ${escapeHtml(image.review_status || 'unknown')} · 模型 ${escapeHtml(image.model || image.provider || '')}</p>
                        ${image.review_recovery_action ? `<p>建议 ${escapeHtml(image.review_recovery_action)} · ${escapeHtml(image.review_recovery_reason || image.review_recovery_focus || '')}</p>` : ''}
                    </article>
                `).join('')}
            </div>
            ${hiddenCount ? `<small>另有 ${hiddenCount} 张图片在追溯 JSON 中。</small>` : ''}
        </section>
    `;
}

function renderComicV2HistoryShotPackages(shots) {
    const items = Array.isArray(shots) ? shots.filter(shot => shot && shot.shot_id) : [];
    if (!items.length) return '';
    const visibleShots = items.slice(0, 6);
    const hiddenCount = Math.max(0, items.length - visibleShots.length);
    return `
        <section class="v2-shot-prompt-cards">
            <div class="v2-shot-prompt-head">
                <div>
                    <strong>镜头生产包</strong>
                    <span>历史记录保留每个镜头的首帧参考、资产引用链、视频提示词和执行步骤。</span>
                </div>
                <span>${items.length} 个镜头</span>
            </div>
            <div class="v2-shot-card-grid">
                ${visibleShots.map((shot, index) => {
                    const firstFrame = shot.first_frame_reference_image || {};
                    const references = Array.isArray(shot.reference_asset_chain) ? shot.reference_asset_chain : [];
                    const steps = Array.isArray(shot.execution_steps) ? shot.execution_steps : [];
                    return `
                        <article class="v2-shot-card">
                            <div class="v2-shot-card-top">
                                <strong>${escapeHtml(shot.shot_id || `shot_${index + 1}`)}</strong>
                                <span>${escapeHtml(shot.scene_id || '')}</span>
                            </div>
                            <p><b>故事节点</b>${escapeHtml(shot.story_beat || '待补充镜头故事节点')}</p>
                            <div class="v2-shot-assets">
                                <small>首帧参考</small>
                                ${firstFrame.file
                                    ? `<b>${escapeHtml(firstFrame.file)}</b>`
                                    : '<em>暂无首帧参考</em>'}
                            </div>
                            <div class="v2-shot-assets">
                                <small>资产引用链</small>
                                ${references.length
                                    ? references.map(asset => `<b>${escapeHtml(asset.name || asset.asset_id || asset.file || '')}${asset.file ? ` · ${escapeHtml(asset.file)}` : ''}</b>`).join('')
                                    : '<em>暂无资产引用</em>'}
                            </div>
                            <div class="v2-shot-prompt-block">
                                <small>视频提示词</small>
                                <p>${escapeHtml(shot.video_prompt_block || '待生成视频提示词')}</p>
                            </div>
                            <div class="v2-shot-negative">
                                <small>负面提示词</small>
                                <p>${escapeHtml(shot.negative_prompt_block || '禁止脸型变化、服装不一致、画风漂移。')}</p>
                            </div>
                            <div class="v2-shot-acceptance">
                                <small>执行步骤</small>
                                <p>${escapeHtml(steps.length ? steps.join('；') : '按首帧参考、资产引用链和视频提示词执行。')}</p>
                            </div>
                        </article>
                    `;
                }).join('')}
            </div>
            ${hiddenCount ? `<small class="v2-shot-hidden-count">还有 ${hiddenCount} 个镜头保存在 Word 画布和交付 JSON 中。</small>` : ''}
        </section>
    `;
}

function renderComicV2ReviewGateMap(lineage) {
    const items = Array.isArray(lineage)
        ? lineage.filter(item => item && item.stage && (item.human_checkpoint || item.handoff_to || item.acceptance_criteria))
        : [];
    if (!items.length) return '';
    return `
        <div class="v2-review-gate-map">
            <div class="v2-review-gate-head">
                <strong>审核节点</strong>
                <span>每一关都显示谁负责、交给谁、用什么标准验收。</span>
            </div>
            <div class="v2-review-gate-grid">
                ${items.map((item, index) => `
                    <article class="v2-review-gate ${escapeHtml(item.status || 'waiting')}">
                        <div class="v2-review-gate-index">${index + 1}</div>
                        <div class="v2-review-gate-body">
                            <strong>${escapeHtml(item.stage_label || item.stage)}</strong>
                            <span>${escapeHtml(item.department || '')} · ${escapeHtml(item.agent || '')}</span>
                            ${item.human_checkpoint ? `<p>人工确认：${escapeHtml(item.human_checkpoint)}</p>` : ''}
                            ${item.handoff_to ? `<small>交给：${escapeHtml(item.handoff_to)}</small>` : ''}
                            ${item.acceptance_criteria ? `<small>验收：${escapeHtml(item.acceptance_criteria)}</small>` : ''}
                        </div>
                    </article>
                `).join('')}
            </div>
        </div>
    `;
}

function renderComicV2LineageTimeline(lineage) {
    const items = Array.isArray(lineage) ? lineage.filter(item => item && item.stage) : [];
    if (!items.length) return '';
    return `
        <div class="lineage-timeline">
            <h4>多 Agent 生产链路</h4>
            <div class="lineage-stage-grid">
                ${items.map((item, index) => `
                    <div class="lineage-stage-card">
                        <div class="lineage-stage-index">${index + 1}</div>
                        <div class="lineage-stage-body">
                            <strong>${escapeHtml(item.stage_label || item.stage)}</strong>
                            <span>${escapeHtml(item.department || '')} · ${escapeHtml(item.agent || '')}</span>
                            <small>状态：${escapeHtml(item.status || '')}</small>
                            ${item.output ? `<small>产出：${escapeHtml(item.output)}</small>` : ''}
                            ${item.handoff_to ? `<small>交给：${escapeHtml(item.handoff_to)}</small>` : ''}
                            ${item.acceptance_criteria ? `<small>验收：${escapeHtml(item.acceptance_criteria)}</small>` : ''}
                            ${item.human_checkpoint ? `<p>人工确认点：${escapeHtml(item.human_checkpoint)}</p>` : ''}
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
}

async function loadPublicShowcase() {
    const box = document.getElementById('public-showcase-content');
    if (!box) return;
    box.innerHTML = '<div class="empty-state">正在加载公开展示页...</div>';
    try {
        const showcase = await API.get('/api/demo/public-showcase');
        box.innerHTML = renderPublicShowcase(showcase);
    } catch (e) {
        box.innerHTML = `<div class="empty-state">公开展示页加载失败：${escapeHtml(e.message || e)}</div>`;
    }
}

function renderPublicShowcase(showcase) {
    const audiences = Array.isArray(showcase.audience_paths) ? showcase.audience_paths : [];
    const demos = Array.isArray(showcase.featured_demos) ? showcase.featured_demos : [];
    const boundaries = Array.isArray(showcase.safety_boundaries) ? showcase.safety_boundaries : [];
    const portfolio = showcase.portfolio_embed || {};
    const deliverables = Array.isArray(portfolio.sample_deliverables) ? portfolio.sample_deliverables : [];
    const readingGuide = Array.isArray(portfolio.deliverable_reading_guide) ? portfolio.deliverable_reading_guide : [];
    const interviewScript = Array.isArray(portfolio.interview_demo_script) ? portfolio.interview_demo_script : [];
    const reproducibility = Array.isArray(portfolio.reproducibility_checklist) ? portfolio.reproducibility_checklist : [];
    const workflow = Array.isArray(portfolio.workflow_showcase) ? portfolio.workflow_showcase : [];
    const handoffInventory = portfolio.handoff_inventory || {};
    const realProductionClaim = portfolio.real_production_claim || {};
    const releaseBadge = portfolio.release_badge || {};
    const deployment = showcase.public_deployment || {};
    return `
        <section class="demo-hero public-showcase-hero">
            <span class="showcase-kicker">Public portfolio</span>
            <h1>${escapeHtml(showcase.product_name || '三个臭皮匠')}</h1>
            <p>${escapeHtml(showcase.tagline || showcase.positioning || '')}</p>
            <div class="showcase-badges">
                <span>无 Key 演示</span>
                <span>不调用真实模型</span>
                <span>不写入用户工作区</span>
                <span>样例交付物可下载</span>
            </div>
            ${releaseBadge.status ? `
                <div class="public-release-badge">
                    <div>
                        <strong>${escapeHtml(releaseBadge.label || '可公开展示')}</strong>
                        <span>${escapeHtml(releaseBadge.mode || 'demo_only')} · ${escapeHtml(releaseBadge.status || '')}</span>
                    </div>
                    <p>${escapeHtml(releaseBadge.summary || '')}</p>
                    <div class="public-release-signals">
                        ${(releaseBadge.signals || []).map(item => `
                            <span class="${escapeHtml(item.status || 'passed')}">${escapeHtml(item.label || '')}：${escapeHtml(item.value || '')}</span>
                        `).join('')}
                    </div>
                    <small>总门禁：${escapeHtml(releaseBadge.primary_gate || '')}</small>
                </div>
            ` : ''}
            <div class="public-showcase-actions">
                <button onclick="navigate('demo_comic')">看 AI 漫剧样例</button>
                <button class="ghost" onclick="navigate('demo_research')">看研究样例</button>
                ${portfolio.repository_url ? `<a class="ghost btn-sm" href="${escapeHtml(portfolio.repository_url)}" target="_blank">打开 GitHub</a>` : ''}
            </div>
        </section>
        <section class="demo-section public-showcase-positioning">
            <div class="demo-section-head">
                <h2>这个产品要证明什么</h2>
                <span>${escapeHtml(showcase.mode || 'public_no_key_showcase')}</span>
            </div>
            <p>${escapeHtml(showcase.positioning || '')}</p>
        </section>
        ${realProductionClaim.claim_level ? `
            <section class="demo-section public-claim-section">
                <div class="demo-section-head">
                    <h2>真实生产声明边界</h2>
                    <span>${escapeHtml(realProductionClaim.claim_level || '')}</span>
                </div>
                <div class="public-claim-grid">
                    <article>
                        <strong>当前能说</strong>
                        ${(realProductionClaim.allowed_public_claims || []).map(item => `<p>${escapeHtml(item)}</p>`).join('')}
                    </article>
                    <article>
                        <strong>当前不能说</strong>
                        ${(realProductionClaim.forbidden_public_claims || []).map(item => `<p>${escapeHtml(item)}</p>`).join('')}
                    </article>
                    <article>
                        <strong>下一步</strong>
                        <p>${escapeHtml(realProductionClaim.next_action || '')}</p>
                        <small>real_quality=${realProductionClaim.can_claim_real_quality ? 'true' : 'false'} · downstream=${escapeHtml(realProductionClaim.downstream_status || '')}</small>
                        ${realProductionClaim.uri ? `<a class="ghost btn-sm" href="${escapeHtml(realProductionClaim.uri)}" target="_blank">打开 claim report</a>` : ''}
                    </article>
                </div>
            </section>
        ` : ''}
        <section class="demo-section">
            <div class="demo-section-head">
                <h2>建议访客这样看</h2>
                <span>${audiences.length} 类访客</span>
            </div>
            <div class="public-audience-grid">
                ${audiences.map(path => `
                    <article>
                        <strong>${escapeHtml(path.label || path.id || '')}</strong>
                        <p>${escapeHtml(path.takeaway || '')}</p>
                        <ol>
                            ${(path.steps || []).map(step => `<li>${escapeHtml(step)}</li>`).join('')}
                        </ol>
                    </article>
                `).join('')}
            </div>
        </section>
        ${interviewScript.length ? `
            <section class="demo-section">
                <div class="demo-section-head">
                    <h2>3 分钟演示脚本</h2>
                    <span>${interviewScript.length} 步</span>
                </div>
                <div class="public-interview-script">
                    ${interviewScript.map(item => `
                        <article>
                            <b>${escapeHtml(item.order || '')}</b>
                            <div>
                                <strong>${escapeHtml(item.title || '')}</strong>
                                <p><span>访客动作</span>${escapeHtml(item.visitor_action || '')}</p>
                                <p><span>产品反馈</span>${escapeHtml(item.product_response || '')}</p>
                                <p><span>证明什么</span>${escapeHtml(item.proof || '')}</p>
                                <small>${escapeHtml(item.boundary || '')}</small>
                            </div>
                        </article>
                    `).join('')}
                </div>
            </section>
        ` : ''}
        ${reproducibility.length ? `
            <section class="demo-section public-repro-section">
                <div class="demo-section-head">
                    <h2>复现与验收清单</h2>
                    <span>${reproducibility.length} 条命令</span>
                </div>
                <div class="public-repro-list">
                    ${reproducibility.map(item => `
                        <article>
                            <b>${escapeHtml(item.order || '')}</b>
                            <div>
                                <strong>${escapeHtml(item.title || '')}</strong>
                                <code>${escapeHtml(item.command || '')}</code>
                                <p><span>通过时</span>${escapeHtml(item.expected || '')}</p>
                                <small>失败时：${escapeHtml(item.if_fails || '')}</small>
                            </div>
                        </article>
                    `).join('')}
                </div>
            </section>
        ` : ''}
        <section class="demo-section">
            <div class="demo-section-head">
                <h2>可体验的办公室</h2>
                <span>${demos.length} 个 no-key demo</span>
            </div>
            <div class="public-demo-grid">
                ${demos.map(demo => `
                    <article>
                        <strong>${escapeHtml(demo.title || demo.office_name || '')}</strong>
                        <p>${escapeHtml(demo.summary || demo.why_it_matters || '')}</p>
                        ${demo.quality_benchmark?.status ? `
                            <div class="showcase-badges">
                                <span>固定样例质量基准 ${escapeHtml(demo.quality_benchmark.package_quality_score || 0)}/100</span>
                                <span>${demo.quality_benchmark.production_quality_verified ? '真实画质已验证' : '仅结构验证，未验证真实画质'}</span>
                                ${demo.office_id === 'comic_production' && handoffInventory.uri ? `
                                    <span>交付盘点 ${escapeHtml(handoffInventory.manifest_count || 0)} 份</span>
                                    <span>真实通过 ${escapeHtml(handoffInventory.production_verified_count || 0)} 份</span>
                                ` : ''}
                            </div>
                        ` : ''}
                        <div class="demo-proof-points">
                            ${(demo.proof_points || []).slice(0, 4).map(point => `<span>${escapeHtml(point)}</span>`).join('')}
                        </div>
                        <div class="public-showcase-actions">
                            <a class="ghost btn-sm" href="${escapeHtml(demo.demo_uri || '#')}" target="_blank">查看 API</a>
                            <button class="btn-sm" onclick="navigate('${demo.office_id === 'research' ? 'demo_research' : 'demo_comic'}')">打开演示页</button>
                        </div>
                    </article>
                `).join('')}
            </div>
        </section>
        <section class="demo-section">
            <div class="demo-section-head">
                <h2>样例交付物</h2>
                <span>${deliverables.length} 个下载物</span>
            </div>
            <div class="demo-artifact-grid">
                ${deliverables.map(item => `
                    <article>
                        <strong>${escapeHtml(item.title || '')}</strong>
                        <span>${escapeHtml(item.office_name || item.office_id || '')}</span>
                        <small>${escapeHtml(item.type || item.status || '')}</small>
                        ${item.reader_guidance ? `<p>${escapeHtml(item.reader_guidance)}</p>` : ''}
                        ${Array.isArray(item.acceptance_signals) && item.acceptance_signals.length ? `
                            <ul class="public-deliverable-signals">
                                ${item.acceptance_signals.map(signal => `<li>${escapeHtml(signal)}</li>`).join('')}
                            </ul>
                        ` : ''}
                        ${item.uri ? `<a class="ghost btn-sm demo-download-link" href="${escapeHtml(item.uri)}" target="_blank">下载样例</a>` : ''}
                    </article>
                `).join('')}
            </div>
        </section>
        ${readingGuide.length ? `
            <section class="demo-section">
                <div class="demo-section-head">
                    <h2>交付物阅读顺序</h2>
                    <span>${readingGuide.length} 步</span>
                </div>
                <div class="public-reading-guide">
                    ${readingGuide.map(item => `
                        <article>
                            <b>${escapeHtml(item.order || '')}</b>
                            <div>
                                <strong>${escapeHtml(item.title || '')}</strong>
                                <p>${escapeHtml(item.look_for || '')}</p>
                                <small>证明：${escapeHtml(item.proves || '')}</small>
                                ${item.uri ? `<a class="ghost btn-sm" href="${escapeHtml(item.uri)}" target="_blank">打开文件</a>` : ''}
                            </div>
                        </article>
                    `).join('')}
                </div>
            </section>
        ` : ''}
        <section class="demo-section">
            <div class="demo-section-head">
                <h2>作品集截图目标</h2>
                <span>${workflow.length} 个证据点</span>
            </div>
            <div class="public-workflow-grid">
                ${workflow.map(item => `
                    <article>
                        <strong>${escapeHtml(item.title || item.kind || '')}</strong>
                        <span>${escapeHtml(item.kind || '')}</span>
                        <p>${escapeHtml(item.caption || '')}</p>
                        ${item.uri ? `<a href="${escapeHtml(item.uri)}" target="_blank">打开下载物</a>` : ''}
                    </article>
                `).join('')}
            </div>
        </section>
        <section class="demo-section public-safety-section">
            <div class="demo-section-head">
                <h2>公开部署安全边界</h2>
                <span>${escapeHtml(deployment.mode || 'demo_only')}</span>
            </div>
            <div class="public-safety-grid">
                ${boundaries.map(item => `<article><strong>边界</strong><p>${escapeHtml(item)}</p></article>`).join('')}
            </div>
            <div class="public-deployment-summary">
                <span>允许路由：${escapeHtml((deployment.allowed_route_prefixes || []).join(' / ') || '/api/demo')}</span>
                <span>真实模型调用：${deployment.allows_real_model_calls ? '允许' : '禁止'}</span>
                <span>写入用户工作区：${deployment.allows_workspace_writes ? '允许' : '禁止'}</span>
            </div>
        </section>
    `;
}

async function loadComicDemo() {
    const box = document.getElementById('comic-demo-content');
    if (!box) return;
    box.innerHTML = '<div class="empty-state">正在加载 AI 漫剧制片办公室演示...</div>';
    try {
        const demo = await API.get('/api/demo/comic-production');
        box.innerHTML = renderComicDemo(demo);
    } catch (e) {
        box.innerHTML = `<div class="empty-state">演示加载失败：${escapeHtml(e.message || e)}</div>`;
    }
}

function renderComicDemo(demo) {
    const stages = Array.isArray(demo.stages) ? demo.stages : [];
    const assets = Array.isArray(demo.assets) ? demo.assets : [];
    const shots = Array.isArray(demo.shots) ? demo.shots : [];
    const artifacts = Array.isArray(demo.artifacts) ? demo.artifacts : [];
    return `
        <section class="demo-hero">
            <span class="showcase-kicker">No-key demo</span>
            <h1>${escapeHtml(demo.title || 'AI 漫剧制片办公室演示')}</h1>
            <p>${escapeHtml(demo.summary || '')}</p>
            <div class="showcase-badges">
                <span>不消耗 API Key，不调用真实模型</span>
                <span>不写入真实工作区</span>
                <span>固定样例，可安全公开展示</span>
            </div>
        </section>
        ${renderDemoViewerPath(demo.viewer_path, demo.proof_points)}
        <section class="demo-section">
            <h2>样例故事</h2>
            <p>${escapeHtml(demo.source_story_preview || '')}</p>
        </section>
        <section class="demo-section">
            <div class="demo-section-head">
                <h2>生产流程</h2>
                <span>${stages.length} 个阶段</span>
            </div>
            <div class="demo-stage-grid">
                ${stages.map((stage, index) => `
                    <article class="demo-stage-card">
                        <b>${index + 1}</b>
                        <strong>${escapeHtml(stage.title || stage.id || '')}</strong>
                        <span>${escapeHtml(stage.owner || '')}</span>
                        <small>${escapeHtml(stage.status || '')}</small>
                    </article>
                `).join('')}
            </div>
        </section>
        ${renderDemoQualityGates(demo.quality_gates)}
        <section class="demo-two-col">
            <div class="demo-section">
                <div class="demo-section-head">
                    <h2>资产样例</h2>
                    <span>${escapeHtml(demo.asset_count || 0)} 个资产</span>
                </div>
                <div class="demo-list">
                    ${assets.map(asset => `
                        <article>
                            <strong>${escapeHtml(asset.name || asset.asset_id || '')}</strong>
                            <span>${escapeHtml(asset.asset_type || '')}</span>
                            <p>${escapeHtml(asset.purpose || '')}</p>
                        </article>
                    `).join('')}
                </div>
            </div>
            <div class="demo-section">
                <div class="demo-section-head">
                    <h2>镜头样例</h2>
                    <span>${escapeHtml(demo.shot_count || 0)} 个镜头</span>
                </div>
                <div class="demo-list">
                    ${shots.map(shot => `
                        <article>
                            <strong>${escapeHtml(shot.shot_id || '')}</strong>
                            <span>${escapeHtml((shot.reference_asset_ids || []).join(' / '))}</span>
                            <p>${escapeHtml(shot.story_beat || '')}</p>
                        </article>
                    `).join('')}
                </div>
            </div>
        </section>
        <section class="demo-section">
            <div class="demo-section-head">
                <h2>交付物</h2>
                <span>固定样例</span>
            </div>
            <div class="demo-artifact-grid">
                ${artifacts.map(item => `
                    <article>
                        <strong>${escapeHtml(item.title || '')}</strong>
                        <span>${escapeHtml(item.type || '')}</span>
                        <small>${escapeHtml(item.status || '')}</small>
                        ${item.uri ? `<a class="ghost btn-sm demo-download-link" href="${escapeHtml(item.uri)}" target="_blank">下载样例</a>` : ''}
                    </article>
                `).join('')}
            </div>
        </section>
    `;
}

function renderDemoViewerPath(path, proofPoints) {
    const steps = Array.isArray(path) ? path : [];
    const proofs = Array.isArray(proofPoints) ? proofPoints : [];
    if (!steps.length && !proofs.length) return '';
    return `
        <section class="demo-section demo-viewer-path">
            <div class="demo-section-head">
                <h2>建议你这样看</h2>
                <span>${steps.length} 步看懂</span>
            </div>
            <div class="demo-viewer-grid">
                ${steps.map((item, index) => `
                    <article>
                        <b>${index + 1}</b>
                        <strong>${escapeHtml(item.title || '')}</strong>
                        <p>${escapeHtml(item.body || '')}</p>
                        ${item.focus ? `<small>${escapeHtml(item.focus)}</small>` : ''}
                    </article>
                `).join('')}
            </div>
            ${proofs.length ? `
                <div class="demo-proof-points">
                    ${proofs.map(point => `<span>${escapeHtml(point)}</span>`).join('')}
                </div>
            ` : ''}
        </section>
    `;
}

function renderDemoQualityGates(gates) {
    const items = Array.isArray(gates) ? gates : [];
    if (!items.length) return '';
    return `
        <section class="demo-section demo-quality-gates">
            <div class="demo-section-head">
                <h2>交付质量</h2>
                <span>${items.length} 项门禁</span>
            </div>
            <div class="demo-quality-grid">
                ${items.map(item => `
                    <article class="${escapeHtml(item.status || 'unknown')}">
                        <strong>${escapeHtml(item.title || item.id || '')}</strong>
                        <span>${escapeHtml(item.status === 'passed' ? '已通过' : item.status || '')}</span>
                        <p>${escapeHtml(item.evidence || '')}</p>
                    </article>
                `).join('')}
            </div>
        </section>
    `;
}

async function loadResearchDemo() {
    const box = document.getElementById('comic-demo-content');
    if (!box) return;
    box.innerHTML = '<div class="empty-state">正在加载研究办公室演示...</div>';
    try {
        const demo = await API.get('/api/demo/research');
        box.innerHTML = renderResearchDemo(demo);
    } catch (e) {
        box.innerHTML = `<div class="empty-state">演示加载失败：${escapeHtml(e.message || e)}</div>`;
    }
}

function renderResearchDemo(demo) {
    const stages = Array.isArray(demo.stages) ? demo.stages : [];
    const sources = Array.isArray(demo.sources) ? demo.sources : [];
    const dataPoints = Array.isArray(demo.data_points) ? demo.data_points : [];
    const competitors = Array.isArray(demo.competitors) ? demo.competitors : [];
    const artifacts = Array.isArray(demo.artifacts) ? demo.artifacts : [];
    const readingGuide = Array.isArray(demo.deliverable_reading_guide) ? demo.deliverable_reading_guide : [];
    const evidenceHandoff = Array.isArray(demo.evidence_handoff) ? demo.evidence_handoff : [];
    return `
        <section class="demo-hero">
            <span class="showcase-kicker">Research no-key demo</span>
            <h1>${escapeHtml(demo.title || '研究办公室演示')}</h1>
            <p>${escapeHtml(demo.summary || '')}</p>
            <div class="showcase-badges">
                <span>不消耗 API Key，不调用真实模型</span>
                <span>固定样例，可安全公开展示</span>
                <span>展示报告、来源和截图计划</span>
            </div>
        </section>
        ${renderDemoViewerPath(demo.viewer_path, demo.proof_points)}
        <section class="demo-section">
            <div class="demo-section-head">
                <h2>调研目标</h2>
                <span>${escapeHtml(demo.deliverable || '阶段报告')}</span>
            </div>
            <p>${escapeHtml(demo.objective || demo.report_preview || '')}</p>
        </section>
        <section class="demo-section">
            <div class="demo-section-head">
                <h2>研究流程</h2>
                <span>${stages.length} 个阶段</span>
            </div>
            <div class="demo-stage-grid">
                ${stages.map((stage, index) => `
                    <article class="demo-stage-card">
                        <b>${index + 1}</b>
                        <strong>${escapeHtml(stage.title || stage.id || '')}</strong>
                        <span>${escapeHtml(stage.owner || '')}</span>
                        <small>${escapeHtml(stage.status || '')}</small>
                    </article>
                `).join('')}
            </div>
        </section>
        ${renderDemoQualityGates(demo.quality_gates)}
        ${evidenceHandoff.length ? `
            <section class="demo-section">
                <div class="demo-section-head">
                    <h2>待补证据交接表</h2>
                    <span>${evidenceHandoff.length} 个待补项</span>
                </div>
                <div class="research-handoff-grid">
                    ${evidenceHandoff.map(item => `
                        <article>
                            <strong>${escapeHtml(item.title || item.id || '')}</strong>
                            <span>${escapeHtml(item.owner || '')}</span>
                            <p>${escapeHtml(item.target_evidence || '')}</p>
                            <small>补完后升级：${escapeHtml((item.upgrades || []).join('、') || item.why_needed || '')}</small>
                        </article>
                    `).join('')}
                </div>
            </section>
        ` : ''}
        ${readingGuide.length ? `
            <section class="demo-section">
                <div class="demo-section-head">
                    <h2>交付物阅读顺序</h2>
                    <span>${readingGuide.length} 步</span>
                </div>
                <div class="public-reading-guide">
                    ${readingGuide.map(item => `
                        <article>
                            <b>${escapeHtml(item.order || '')}</b>
                            <div>
                                <strong>${escapeHtml(item.title || '')}</strong>
                                <p>${escapeHtml(item.look_for || '')}</p>
                                <small>证明：${escapeHtml(item.proves || '')}</small>
                                ${item.uri ? `<a class="ghost btn-sm" href="${escapeHtml(item.uri)}" target="_blank">打开文件</a>` : ''}
                            </div>
                        </article>
                    `).join('')}
                </div>
            </section>
        ` : ''}
        <section class="demo-two-col">
            <div class="demo-section">
                <div class="demo-section-head">
                    <h2>来源与证据</h2>
                    <span>${escapeHtml(demo.source_count || 0)} 个来源</span>
                </div>
                <div class="demo-list">
                    ${sources.map(source => `
                        <article>
                            <strong>${escapeHtml(source.title || source.url || '')}</strong>
                            <span>${escapeHtml(source.publisher || '')}</span>
                            <p>${escapeHtml(source.note || source.url || '')}</p>
                        </article>
                    `).join('')}
                </div>
            </div>
            <div class="demo-section">
                <div class="demo-section-head">
                    <h2>数据与竞品</h2>
                    <span>${escapeHtml(demo.data_point_count || 0)} 个数据点 · ${escapeHtml(demo.competitor_count || 0)} 个竞品</span>
                </div>
                <div class="demo-list">
                    ${dataPoints.map(point => `
                        <article>
                            <strong>${escapeHtml(point.metric || '')}</strong>
                            <span>${escapeHtml(point.value || '')}</span>
                            <p>${escapeHtml(point.note || point.confidence || '')}</p>
                        </article>
                    `).join('')}
                    ${competitors.map(item => `
                        <article>
                            <strong>${escapeHtml(item.product_name || item.brand || '')}</strong>
                            <span>${escapeHtml(item.brand || '')}</span>
                            <p>${escapeHtml(item.selling_points || item.negative_pain_points || '')}</p>
                        </article>
                    `).join('')}
                </div>
            </div>
        </section>
        <section class="demo-section">
            <div class="demo-section-head">
                <h2>交付物</h2>
                <span>固定样例</span>
            </div>
            <div class="demo-artifact-grid">
                ${artifacts.map(item => `
                    <article>
                        <strong>${escapeHtml(item.title || '')}</strong>
                        <span>${escapeHtml(item.type || '')}</span>
                        <small>${escapeHtml(item.status || '')}</small>
                        ${item.uri ? `<a class="ghost btn-sm demo-download-link" href="${escapeHtml(item.uri)}" target="_blank">下载样例</a>` : ''}
                    </article>
                `).join('')}
            </div>
        </section>
    `;
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

function exposeInlineHandlers() {
    window.navigate = navigate;
    window.navigateActiveWorkbench = navigateActiveWorkbench;
    window.showOfficeUnavailable = showOfficeUnavailable;
    window.showSampleUnavailable = showSampleUnavailable;
    window.selectComicWorkspace = selectComicWorkspace;
    window.startComicCabinet = startComicCabinet;
    window.continueComicCabinet = continueComicCabinet;
    window.selectComicSuggestedReply = selectComicSuggestedReply;
    window.confirmComicScript = confirmComicScript;
    window.unconfirmComicScript = unconfirmComicScript;
    window.submitComicTask = submitComicTask;
    window.approveComicAssetsAndSubmit = approveComicAssetsAndSubmit;
    window.requestComicAssetRevision = requestComicAssetRevision;
    window.approveComicV2VisualBible = approveComicV2VisualBible;
    window.reviseComicV2VisualBible = reviseComicV2VisualBible;
    window.planComicV2Assets = planComicV2Assets;
    window.appendComicV2AssetReviewNote = appendComicV2AssetReviewNote;
    window.approveComicV2Assets = approveComicV2Assets;
    window.reviseComicV2Assets = reviseComicV2Assets;
    window.planComicV2Prompts = planComicV2Prompts;
    window.generateComicV2Images = generateComicV2Images;
    window.overrideComicV2VisualReview = overrideComicV2VisualReview;
    window.buildComicV2Delivery = buildComicV2Delivery;
    window.recoverComicV2Quality = recoverComicV2Quality;
    window.filterComicAssets = filterComicAssets;
    window.selectComicArtifact = selectComicArtifact;
    window.regenerateComicImage = regenerateComicImage;
    window.retryTaskRecoveryAction = retryTaskRecoveryAction;
    window.runHistoryRecoveryAction = runHistoryRecoveryAction;
}
exposeInlineHandlers();

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
