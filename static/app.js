/**
 * GestureAI - Application Logic (Phase 3)
 */

class ApiClient {
    constructor() {
        this.baseUrl = '/api';
        this.socket = io({ transports: ['websocket', 'polling'] });
        
        this.socket.on('connect', () => console.log('✅ Connected to WebSocket server'));
        this.socket.on('disconnect', () => console.warn('❌ Disconnected from WebSocket server'));
    }
    
    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const defaultOptions = { headers: { 'Content-Type': 'application/json' } };
        const fetchOptions = { ...defaultOptions, ...options };
        
        try {
            const response = await fetch(url, fetchOptions);
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || `API Error: ${response.status}`);
            return data;
        } catch (error) {
            console.error(`[API] Fetch failed for ${endpoint}:`, error);
            window.ui.showToast(error.message, 'error');
            throw error;
        }
    }

    async getSystemStatus() { return this.request('/system/status'); }
    async getGestures() { return this.request('/gestures'); }
    async addGesture(name, action, display_name) { return this.request('/gestures', { method: 'POST', body: JSON.stringify({name, action, display_name}) }); }
    async updateGesture(name, action, display_name) { return this.request(`/gestures/${name}`, { method: 'PUT', body: JSON.stringify({action, display_name}) }); }
    async deleteGesture(name) { return this.request(`/gestures/${name}`, { method: 'DELETE' }); }
    async getSettings() { return this.request('/settings'); }
    async updateSettings(data) { return this.request('/settings', { method: 'PUT', body: JSON.stringify(data) }); }
    async getActionLog() { return this.request('/action-log'); }
    async startCamera() { return this.request('/camera/start', { method: 'POST' }); }
    async stopCamera() { return this.request('/camera/stop', { method: 'POST' }); }
    async startCollection(gesture_name) { return this.request('/collect/start', { method: 'POST', body: JSON.stringify({gesture_name}) }); }
    async startTraining() { return this.request('/train/start', { method: 'POST' }); }
}

// UI Utilities
const UI = {
    showToast(message, type = 'success') {
        const container = document.getElementById('toast-root');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        const icon = type === 'success' ? 'fa-check-circle' : 'fa-circle-exclamation';
        toast.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${message}</span>`;
        container.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
};
window.ui = UI;

// ──────────────────────────────────────────────────
// ACTION PRESETS — Two-Dropdown Cascading Config
// ──────────────────────────────────────────────────
const ACTION_PRESETS = {
    os_keys: {
        label: '🖥️ Operating System Keys',
        presets: [
            { label: 'Print Screen',             type: 'press',   params: { key: 'printscreen' } },
            { label: 'Task View (Win+Tab)',       type: 'hotkey',  params: { keys: 'win+tab' } },
            { label: 'Lock Screen (Win+L)',       type: 'hotkey',  params: { keys: 'win+l' } },
            { label: 'Show Desktop (Win+D)',      type: 'hotkey',  params: { keys: 'win+d' } },
            { label: 'Copy (Ctrl+C)',             type: 'hotkey',  params: { keys: 'ctrl+c' } },
            { label: 'Paste (Ctrl+V)',            type: 'hotkey',  params: { keys: 'ctrl+v' } },
            { label: 'Cut (Ctrl+X)',              type: 'hotkey',  params: { keys: 'ctrl+x' } },
            { label: 'Undo (Ctrl+Z)',             type: 'hotkey',  params: { keys: 'ctrl+z' } },
            { label: 'Redo (Ctrl+Y)',             type: 'hotkey',  params: { keys: 'ctrl+y' } },
            { label: 'Select All (Ctrl+A)',       type: 'hotkey',  params: { keys: 'ctrl+a' } },
            { label: 'Task Manager (Ctrl+Shift+Esc)', type: 'hotkey', params: { keys: 'ctrl+shift+escape' } },
            { label: 'Switch Window (Alt+Tab)',   type: 'alt_tab', params: { count: 1 } },
            { label: 'Close Window (Alt+F4)',     type: 'hotkey',  params: { keys: 'alt+f4' } },
            { label: 'File Explorer (Win+E)',     type: 'hotkey',  params: { keys: 'win+e' } },
            { label: 'Run Dialog (Win+R)',        type: 'hotkey',  params: { keys: 'win+r' } },
            { label: 'Virtual Desktop Left',      type: 'hotkey',  params: { keys: 'ctrl+win+left' } },
            { label: 'Virtual Desktop Right',     type: 'hotkey',  params: { keys: 'ctrl+win+right' } },
            { label: '✏️ Custom OS Shortcut…',    type: 'hotkey',  params: null, custom: true, customField: 'keys', customLabel: 'Keys (e.g. win+shift+s)', customPlaceholder: 'win+shift+s' },
        ]
    },
    keyboard: {
        label: '⌨️ Keyboard Keys',
        presets: [
            { label: 'Enter',       type: 'press', params: { key: 'enter' } },
            { label: 'Escape',      type: 'press', params: { key: 'escape' } },
            { label: 'Space',       type: 'press', params: { key: 'space' } },
            { label: 'Backspace',   type: 'press', params: { key: 'backspace' } },
            { label: 'Delete',      type: 'press', params: { key: 'delete' } },
            { label: 'Tab',         type: 'press', params: { key: 'tab' } },
            { label: 'Arrow Up',    type: 'press', params: { key: 'up' } },
            { label: 'Arrow Down',  type: 'press', params: { key: 'down' } },
            { label: 'Arrow Left',  type: 'press', params: { key: 'left' } },
            { label: 'Arrow Right', type: 'press', params: { key: 'right' } },
            { label: 'Page Up',     type: 'press', params: { key: 'pageup' } },
            { label: 'Page Down',   type: 'press', params: { key: 'pagedown' } },
            { label: 'Home',        type: 'press', params: { key: 'home' } },
            { label: 'End',         type: 'press', params: { key: 'end' } },
            { label: 'F5 (Refresh)',type: 'press', params: { key: 'f5' } },
            { label: '✏️ Custom Key…', type: 'press', params: null, custom: true, customField: 'key', customLabel: 'Key Name', customPlaceholder: 'f11' },
        ]
    },
    shortcuts: {
        label: '⚡ Keyboard Shortcuts',
        presets: [
            { label: 'New Tab (Ctrl+T)',          type: 'hotkey', params: { keys: 'ctrl+t' } },
            { label: 'Close Tab (Ctrl+W)',        type: 'hotkey', params: { keys: 'ctrl+w' } },
            { label: 'Reopen Tab (Ctrl+Shift+T)', type: 'hotkey', params: { keys: 'ctrl+shift+t' } },
            { label: 'Find (Ctrl+F)',             type: 'hotkey', params: { keys: 'ctrl+f' } },
            { label: 'Save (Ctrl+S)',             type: 'hotkey', params: { keys: 'ctrl+s' } },
            { label: 'Save As (Ctrl+Shift+S)',    type: 'hotkey', params: { keys: 'ctrl+shift+s' } },
            { label: 'Print (Ctrl+P)',            type: 'hotkey', params: { keys: 'ctrl+p' } },
            { label: 'Zoom In (Ctrl++)',          type: 'hotkey', params: { keys: 'ctrl+plus' } },
            { label: 'Zoom Out (Ctrl+-)',         type: 'hotkey', params: { keys: 'ctrl+minus' } },
            { label: 'Bold (Ctrl+B)',             type: 'hotkey', params: { keys: 'ctrl+b' } },
            { label: 'Italics (Ctrl+I)',          type: 'hotkey', params: { keys: 'ctrl+i' } },
            { label: 'Underline (Ctrl+U)',        type: 'hotkey', params: { keys: 'ctrl+u' } },
            { label: 'Next Window (Alt+Tab)',     type: 'alt_tab', params: { count: 1 } },
            { label: '✏️ Custom Shortcut…',       type: 'hotkey', params: null, custom: true, customField: 'keys', customLabel: 'Keys (e.g. ctrl+shift+n)', customPlaceholder: 'ctrl+shift+n' },
        ]
    },
    volume: {
        label: '🔊 Volume',
        presets: [
            { label: 'Volume Up',       type: 'volume', params: { direction: 'up' } },
            { label: 'Volume Down',     type: 'volume', params: { direction: 'down' } },
            { label: 'Mute / Unmute',   type: 'press',  params: { key: 'volumemute' } },
        ]
    },
    playback: {
        label: '🎵 Playback / Media',
        presets: [
            { label: 'Play / Pause',       type: 'press',  params: { key: 'playpause' } },
            { label: 'Next Track',          type: 'press',  params: { key: 'nexttrack' } },
            { label: 'Previous Track',      type: 'press',  params: { key: 'prevtrack' } },
            { label: 'Stop Media',          type: 'press',  params: { key: 'stop' } },
            { label: 'Fast Forward (→ 5s)', type: 'hotkey', params: { keys: 'shift+right' } },
            { label: 'Rewind (← 5s)',       type: 'hotkey', params: { keys: 'shift+left' } },
            { label: 'Toggle Fullscreen',   type: 'press',  params: { key: 'f11' } },
        ]
    },
    type_text: {
        label: '✍️ Type Custom Text',
        presets: [
            { label: '✏️ Enter text to type…', type: 'type_text', params: null, custom: true, customField: 'text', customLabel: 'Text to type when gesture is shown', customPlaceholder: 'Hello World!' },
        ]
    },
    open_app: {
        label: '📂 Open Application',
        presets: [
            { label: 'Notepad',             type: 'open_app', params: { path: 'notepad.exe' } },
            { label: 'Calculator',           type: 'open_app', params: { path: 'calc.exe' } },
            { label: 'File Explorer',        type: 'open_app', params: { path: 'explorer.exe' } },
            { label: 'Chrome',               type: 'open_app', params: { path: 'chrome' } },
            { label: 'VS Code',              type: 'open_app', params: { path: 'code' } },
            { label: 'Command Prompt',       type: 'open_app', params: { path: 'cmd.exe' } },
            { label: 'PowerShell',           type: 'open_app', params: { path: 'powershell.exe' } },
            { label: '✏️ Custom App Path…',  type: 'open_app', params: null, custom: true, customField: 'path', customLabel: 'Application path or command', customPlaceholder: 'C:\\Program Files\\App\\app.exe' },
        ]
    }
};

/**
 * Get a friendly human-readable label for a stored action object.
 * Searches through ACTION_PRESETS to find a matching preset label.
 */
function getActionLabel(actionObj) {
    if (!actionObj) return 'Unmapped';
    
    const type = typeof actionObj === 'string' ? actionObj : actionObj.type;
    if (!type || type === 'none') return 'None';
    if (type === 'tracking') return 'Cursor Tracking';
    if (type === 'left_click') return 'Left Click';
    
    const params = actionObj.params || actionObj;
    
    // Search presets for an exact match
    for (const catKey of Object.keys(ACTION_PRESETS)) {
        for (const preset of ACTION_PRESETS[catKey].presets) {
            if (preset.custom || !preset.params) continue;
            if (preset.type !== type) continue;
            
            // Compare params
            let match = true;
            for (const [k, v] of Object.entries(preset.params)) {
                if (String(params[k]).toLowerCase() !== String(v).toLowerCase()) { match = false; break; }
            }
            if (match) return preset.label;
        }
    }
    
    // Fallback: build a description from raw data
    if (type === 'hotkey') return `Hotkey: ${params.keys || ''}`;
    if (type === 'press') return `Key: ${params.key || ''}`;
    if (type === 'alt_tab') return `Alt+Tab (${params.count || 1}x)`;
    if (type === 'volume') return `Volume ${params.direction || ''}`;
    if (type === 'open_app') return `Open: ${params.path || ''}`;
    if (type === 'type_text') return `Type: "${(params.text || '').substring(0, 20)}…"`;
    if (type === 'system_command') return `Cmd: ${params.command || ''}`;
    
    return type;
}

/**
 * Given an existing action object, find the matching category key and preset index.
 * Returns { categoryKey, presetIndex } or null.
 */
function findPresetForAction(actionObj) {
    if (!actionObj || typeof actionObj === 'string') return null;
    
    const type = actionObj.type;
    const params = actionObj.params || actionObj;
    
    for (const catKey of Object.keys(ACTION_PRESETS)) {
        const category = ACTION_PRESETS[catKey];
        for (let i = 0; i < category.presets.length; i++) {
            const preset = category.presets[i];
            if (preset.custom || !preset.params) continue;
            if (preset.type !== type) continue;
            
            let match = true;
            for (const [k, v] of Object.entries(preset.params)) {
                if (String(params[k]).toLowerCase() !== String(v).toLowerCase()) { match = false; break; }
            }
            if (match) return { categoryKey: catKey, presetIndex: i };
        }
    }
    
    // No exact preset match — find the right category and use its custom entry
    for (const catKey of Object.keys(ACTION_PRESETS)) {
        const category = ACTION_PRESETS[catKey];
        const customIdx = category.presets.findIndex(p => p.custom && p.type === type);
        if (customIdx !== -1) return { categoryKey: catKey, presetIndex: customIdx, isCustom: true };
    }
    
    return null;
}

// Page Controllers
const Controllers = {
    async initDashboard() {
        const badge = document.getElementById('status-badge');
        const feedImg = document.getElementById('camera-feed');
        const overlay = document.getElementById('feed-overlay');
        const btnStart = document.getElementById('btn-start-camera');
        const btnStop = document.getElementById('btn-stop-camera');
        
        const updateStatus = (active) => {
            if (active) {
                badge.className = 'badge badge-active';
                badge.innerHTML = '<i class="fa-solid fa-circle"></i> Active';
                overlay.classList.add('hidden');
                btnStop.classList.remove('hidden');
                feedImg.src = '/api/camera/feed?' + new Date().getTime();
            } else {
                badge.className = 'badge badge-inactive';
                badge.innerHTML = '<i class="fa-solid fa-circle"></i> Inactive';
                overlay.classList.remove('hidden');
                btnStop.classList.add('hidden');
                feedImg.src = '';
            }
        };

        const status = await window.api.getSystemStatus();
        updateStatus(status.camera_running);

        btnStart.onclick = async () => {
            await window.api.startCamera();
            updateStatus(true);
        };

        btnStop.onclick = async () => {
            await window.api.stopCamera();
            updateStatus(false);
        };

        const camSelect = document.getElementById('select-camera-dashboard');
        if (camSelect) {
            const settings = await window.api.getSettings();
            camSelect.value = settings.camera_index;
            camSelect.onchange = async () => {
                const nextIdx = parseInt(camSelect.value);
                await window.api.updateSettings({ camera_index: nextIdx });
                
                const sys = await window.api.getSystemStatus();
                if (sys.camera_running) {
                    await window.api.stopCamera();
                    updateStatus(false);
                    setTimeout(async () => {
                        await window.api.startCamera();
                        updateStatus(true);
                        window.ui.showToast(`Switched to Camera ${nextIdx}`);
                    }, 500);
                } else {
                    window.ui.showToast(`Switched to Camera ${nextIdx}. Start engine to view.`);
                }
            };
        }

        // Socket Listeners (Remove old listeners first to avoid duplicates when routing back)
        window.api.socket.off('fps_update');
        window.api.socket.off('prediction');
        window.api.socket.off('action_triggered');

        window.api.socket.on('fps_update', (d) => {
            const el = document.getElementById('fps-value');
            if (el) el.innerText = d.fps;
        });

        window.api.socket.on('prediction', (d) => {
            const g = document.getElementById('pred-value');
            const c = document.getElementById('pred-conf');
            if (g && c) {
                g.innerText = d.gesture || '-';
                c.innerText = Math.round(d.confidence * 100);
            }
        });

        const logContainer = document.getElementById('action-log-container');
        const addLogEntry = (data) => {
            const empty = logContainer.querySelector('.empty-state');
            if (empty) empty.remove();
            
            const el = document.createElement('div');
            el.className = 'log-entry page-fade-in';
            const time = new Date(data.timestamp * 1000).toLocaleTimeString();
            el.innerHTML = `<div class="log-time">${time}</div><div class="log-content"><strong>${data.gesture}</strong> → ${data.action}</div>`;
            logContainer.prepend(el);
            if (logContainer.children.length > 50) logContainer.lastChild.remove();
        };

        window.api.socket.on('action_triggered', addLogEntry);

        const logs = await window.api.getActionLog();
        if (logs.length > 0) {
            logContainer.innerHTML = '';
            logs.reverse().forEach(addLogEntry); // Reverse to prepend in correct order
        }
    },

    async initGestures() {
        const data = await window.api.getGestures();
        const builtinGrid = document.getElementById('builtin-grid');
        const customGrid = document.getElementById('custom-grid');
        const displayNames = data.display_names || {};
        
        const renderCard = (gesture, isBuiltin) => {
            const actionObj = data.action_map[gesture];
            const actionStr = getActionLabel(actionObj);
            const dName = displayNames[gesture] || gesture;
                
            return `
                <div class="card gesture-card page-fade-in">
                    <div class="gesture-card-header">
                        <img src="/static/images/${gesture}.jpeg" class="gesture-img" onerror="this.src='data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMDAgMTAwIj48cmVjdCB3aWR0aD0iMTAwIiBoZWlnaHQ9IjEwMCIgZmlsbD0iI2U1ZTdlYiIvPjx0ZXh0IHg9IjUwIiB5PSI1NSIgZm9udC1mYW1pbHk9IkFyaWFsIiBmb250LXNpemU9IjI0IiBmaWxsPSIjOWNhM2FmIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIj4/PC90ZXh0Pjwvc3ZnPg=='">
                        <div class="gesture-info">
                            <h4>${dName}</h4>
                            <span class="mapped-action">${actionStr}</span>
                        </div>
                    </div>
                    <div class="gesture-actions">
                        <button class="btn btn-secondary btn-remap" data-gesture="${gesture}"><i class="fa-solid fa-pen"></i> Remap</button>
                        ${!isBuiltin ? `<button class="btn btn-secondary btn-delete" data-gesture="${gesture}"><i class="fa-solid fa-trash text-danger"></i></button>` : ''}
                    </div>
                </div>
            `;
        };

        builtinGrid.innerHTML = data.builtin.map(g => renderCard(g, true)).join('');
        customGrid.innerHTML = data.custom.length ? data.custom.map(g => renderCard(g, false)).join('') : '<p class="text-tertiary">No custom gestures found.</p>';

        // Bind Buttons
        document.querySelectorAll('.btn-remap').forEach(btn => btn.onclick = () => Controllers.openGestureModal(btn.dataset.gesture, data.action_map[btn.dataset.gesture], displayNames[btn.dataset.gesture]));
        document.querySelectorAll('.btn-delete').forEach(btn => btn.onclick = async () => {
            if (confirm(`Delete ${btn.dataset.gesture}?`)) {
                await window.api.deleteGesture(btn.dataset.gesture);
                window.ui.showToast('Gesture deleted');
                Controllers.initGestures(); // refresh
            }
        });
        document.getElementById('btn-add-custom').onclick = () => Controllers.openGestureModal();
    },
    
    openGestureModal(gestureName = '', existingAction = null, existingDisplayName = '', onSaveCallback = null) {
        const root = document.getElementById('modal-root');
        const tpl = document.getElementById('tpl-modal-gesture');
        root.innerHTML = '';
        root.appendChild(tpl.content.cloneNode(true));
        
        // Store callback globally for delegation handler
        window.modalSaveCallback = onSaveCallback || null;
        
        const title = root.querySelector('#modal-title');
        const nameInput = root.querySelector('#modal-gesture-name');
        const dNameInput = root.querySelector('#modal-display-name');
        const categorySelect = root.querySelector('#modal-action-category');
        const presetGroup = root.querySelector('#group-action-preset');
        const presetSelect = root.querySelector('#modal-action-preset');
        const dynamicParams = root.querySelector('#modal-dynamic-params');
        
        if (gestureName) {
            title.innerText = 'Remap Gesture';
            nameInput.value = gestureName;
            nameInput.disabled = true;
            dNameInput.value = existingDisplayName || gestureName;
        } else {
            title.innerText = 'Add Custom Gesture';
            nameInput.disabled = false;
        }

        // Populate Dropdown 2 when Category changes
        const populatePresets = (catKey) => {
            presetSelect.innerHTML = '<option value="">-- Select an Action --</option>';
            dynamicParams.innerHTML = '';
            
            if (!catKey || !ACTION_PRESETS[catKey]) {
                presetGroup.classList.add('hidden');
                return;
            }
            
            const category = ACTION_PRESETS[catKey];
            category.presets.forEach((p, idx) => {
                const opt = document.createElement('option');
                opt.value = idx;
                opt.textContent = p.label;
                presetSelect.appendChild(opt);
            });
            presetGroup.classList.remove('hidden');
            
            // If only 1 preset (e.g. type_text), auto-select it
            if (category.presets.length === 1) {
                presetSelect.value = '0';
                onPresetChange();
            }
        };

        // Show custom param input when a Custom preset is chosen
        const onPresetChange = () => {
            const catKey = categorySelect.value;
            const idx = presetSelect.value;
            dynamicParams.innerHTML = '';
            
            if (idx === '' || !catKey) return;
            
            const preset = ACTION_PRESETS[catKey].presets[parseInt(idx)];
            if (preset.custom) {
                dynamicParams.innerHTML = `
                    <label>${preset.customLabel}</label>
                    <input type="text" id="modal-custom-param" class="form-control" placeholder="${preset.customPlaceholder}">
                `;
            }
        };

        categorySelect.onchange = () => populatePresets(categorySelect.value);
        presetSelect.onchange = onPresetChange;
        
        // Pre-fill if editing an existing action
        if (existingAction && typeof existingAction === 'object' && existingAction.type) {
            const match = findPresetForAction(existingAction);
            if (match) {
                categorySelect.value = match.categoryKey;
                populatePresets(match.categoryKey);
                presetSelect.value = match.presetIndex;
                onPresetChange();
                
                // Fill custom param input if it's a custom match
                if (match.isCustom) {
                    const preset = ACTION_PRESETS[match.categoryKey].presets[match.presetIndex];
                    const customInput = root.querySelector('#modal-custom-param');
                    if (customInput && preset.customField) {
                        const params = existingAction.params || existingAction;
                        customInput.value = params[preset.customField] || '';
                    }
                }
            }
        }
        
        // Note: Modal save and close are handled via global Event Delegation below
    },

    async initTraining() {
        const gestures = await window.api.getGestures();
        const select = document.getElementById('collect-gesture-select');
        const btnCollect = document.getElementById('btn-start-collection');
        const btnCancel = document.getElementById('btn-cancel-collection');
        const btnTrain = document.getElementById('btn-start-training');
        const btnNew = document.getElementById('btn-train-add-custom');
        const feedImg = document.getElementById('training-camera-feed');
        const feedPlaceholder = document.getElementById('training-feed-placeholder');
        
        // Setup New button
        if (btnNew) {
            btnNew.onclick = () => {
                Controllers.openGestureModal('', null, '', () => {
                    Controllers.initTraining(); // Refresh dropdown
                });
            };
        }
        
        // Populate select with custom gestures
        const displayNames = gestures.display_names || {};
        select.innerHTML = '<option value="">-- Select Custom Gesture --</option>' + 
            gestures.custom.map(g => `<option value="${g}">${displayNames[g] || g}</option>`).join('');
            
        select.onchange = () => { btnCollect.disabled = !select.value; };

        // Data Collection Flow
        btnCollect.onclick = async () => {
            const name = select.value;
            if (!name) return;
            
            document.getElementById('collection-progress-container').classList.remove('hidden');
            btnCollect.classList.add('hidden');
            btnCancel.classList.remove('hidden');
            select.disabled = true;
            
            feedPlaceholder.style.display = 'none';
            feedImg.src = '/api/camera/feed?' + new Date().getTime();
            
            await window.api.request('/collect/start', { method: 'POST', body: JSON.stringify({gesture_name: name}) });
        };
        
        btnCancel.onclick = async () => {
            await window.api.request('/collect/cancel', { method: 'POST' });
            window.ui.showToast('Collection canceled.');
            btnCollect.classList.remove('hidden');
            btnCancel.classList.add('hidden');
            select.disabled = false;
            feedImg.src = '';
            feedPlaceholder.style.display = 'block';
            document.getElementById('collection-progress-container').classList.add('hidden');
        };

        // Train Flow
        btnTrain.onclick = async () => {
            document.getElementById('training-progress-container').classList.remove('hidden');
            btnTrain.disabled = true;
            await window.api.startTraining();
        };

        // Socket Listeners
        window.api.socket.off('collection_progress');
        window.api.socket.off('training_progress');

        window.api.socket.on('collection_progress', (data) => {
            const pct = data.progress || 0;
            const bar = document.getElementById('collection-progress-bar');
            const txt = document.getElementById('collection-progress-text');
            const stat = document.getElementById('collection-status-text');
            
            if(bar) bar.style.width = `${pct}%`;
            if(txt) txt.innerText = `${data.samples}/${data.total || 400}`;
            
            if (data.status === 'completed') {
                if(stat) stat.innerText = 'Complete!';
                btnCollect.classList.remove('hidden');
                btnCancel.classList.add('hidden');
                select.disabled = false;
                feedImg.src = '';
                feedPlaceholder.style.display = 'block';
                window.ui.showToast("Data collection complete!");
            } else if (data.status === 'idle') {
                if(stat) stat.innerText = 'Idle';
                if(bar) bar.style.width = `0%`;
                if(txt) txt.innerText = `0/400`;
            } else {
                if(stat) stat.innerText = 'Collecting...';
            }
        });

        window.api.socket.on('training_progress', (data) => {
            const pct = data.progress || 0;
            const bar = document.getElementById('training-progress-bar');
            if(bar) bar.style.width = `${pct}%`;
            
            if (data.epoch) document.getElementById('training-epoch-text').innerText = `Epoch ${data.epoch}/${data.total_epochs}`;
            if (data.loss) document.getElementById('train-loss').innerText = data.loss.toFixed(3);
            if (data.accuracy) document.getElementById('train-acc').innerText = `${Math.round(data.accuracy*100)}%`;
            if (data.val_accuracy) document.getElementById('val-acc').innerText = `${Math.round(data.val_accuracy*100)}%`;
            
            if (data.status === 'completed') {
                document.getElementById('training-status-text').innerText = 'Complete!';
                btnTrain.disabled = false;
                window.ui.showToast(`Training complete! Test Acc: ${data.accuracy}%`);
            } else if (data.status === 'error') {
                document.getElementById('training-status-text').innerText = 'Error!';
                btnTrain.disabled = false;
                window.ui.showToast(data.message || 'Training failed', 'error');
            }
        });
    },

    async initSettings() {
        const settings = await window.api.getSettings();
        
        const iCam = document.getElementById('setting-camera-index');
        const iCool = document.getElementById('setting-cooldown');
        const iThresh = document.getElementById('setting-threshold');
        const iFrames = document.getElementById('setting-frames');
        
        iCam.value = settings.camera_index;
        iCool.value = settings.action_cooldown;
        iThresh.value = settings.confidence_threshold;
        iFrames.value = settings.frame_confirmation;
        
        document.getElementById('btn-save-settings').onclick = async () => {
            await window.api.updateSettings({
                camera_index: parseInt(iCam.value),
                action_cooldown: parseFloat(iCool.value),
                confidence_threshold: parseFloat(iThresh.value),
                frame_confirmation: parseInt(iFrames.value)
            });
            window.ui.showToast('Settings saved successfully!');
        };
    }
};

// Router Update
class HashRouter {
    constructor() {
        this.routes = ['dashboard', 'gestures', 'training', 'tutorial', 'settings'];
        this.defaultRoute = 'dashboard';
        this.container = document.getElementById('page-container');
        window.addEventListener('hashchange', () => this.handleRoute());
    }
    init() {
        if (!window.location.hash || window.location.hash === '#') window.location.hash = `#${this.defaultRoute}`;
        else this.handleRoute();
    }
    handleRoute() {
        let hash = window.location.hash.substring(1);
        if (!this.routes.includes(hash)) {
            window.location.hash = `#${this.defaultRoute}`;
            return;
        }
        this.renderPage(hash);
        this.updateSidebarActiveState(hash);
    }
    renderPage(routeName) {
        const template = document.getElementById(`tpl-${routeName}`);
        if (template) {
            this.container.innerHTML = '';
            this.container.appendChild(template.content.cloneNode(true));
            
            this.container.classList.remove('page-fade-in');
            void this.container.offsetWidth; 
            this.container.classList.add('page-fade-in');
            
            // Call Page Controller
            if (routeName === 'dashboard') Controllers.initDashboard();
            else if (routeName === 'gestures') Controllers.initGestures();
            else if (routeName === 'training') Controllers.initTraining();
            else if (routeName === 'settings') Controllers.initSettings();
            
        }
    }
    updateSidebarActiveState(routeName) {
        document.querySelectorAll('.nav-link').forEach(link => {
            if (link.dataset.route === routeName) link.classList.add('active');
            else link.classList.remove('active');
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.api = new ApiClient();
    
    // Theme Management
    const themeToggleBtn = document.getElementById('theme-toggle');
    const htmlElement = document.documentElement;
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) htmlElement.setAttribute('data-theme', savedTheme);
    else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        htmlElement.setAttribute('data-theme', 'dark');
        localStorage.setItem('theme', 'dark');
    }
    themeToggleBtn.addEventListener('click', () => {
        const newTheme = htmlElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        htmlElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
    });

    // Global Modal Event Delegation
    document.addEventListener('click', async (e) => {
        // Modal Close
        if (e.target.closest('.btn-modal-close') || (e.target.classList.contains('modal-backdrop') && !e.target.closest('.modal-content'))) {
            const root = document.getElementById('modal-root');
            if (root) root.innerHTML = '';
        }

        // Modal Save
        if (e.target.closest('#btn-modal-save')) {
            const root = document.getElementById('modal-root');
            const nameInput = root.querySelector('#modal-gesture-name');
            const dNameInput = root.querySelector('#modal-display-name');
            const categorySelect = root.querySelector('#modal-action-category');
            const presetSelect = root.querySelector('#modal-action-preset');
            
            if (!nameInput) return;

            const dName = dNameInput.value.trim();
            let name = nameInput.value.trim().replace(/\s+/g, '_');
            
            if (!name && !nameInput.disabled) {
                name = dName.toLowerCase().replace(/[^a-z0-9]/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '');
            }
            
            if (!name) return window.ui.showToast('Display Name required', 'error');
            if (!dName) return window.ui.showToast('Display Name required', 'error');
            
            // Build action object from the selected preset
            const catKey = categorySelect.value;
            const presetIdx = presetSelect.value;
            
            if (!catKey || presetIdx === '') {
                return window.ui.showToast('Please select an action category and action', 'error');
            }
            
            const preset = ACTION_PRESETS[catKey].presets[parseInt(presetIdx)];
            let actionObj;
            
            if (preset.custom) {
                // Custom entry — read from text input
                const customInput = root.querySelector('#modal-custom-param');
                const customVal = customInput ? customInput.value.trim() : '';
                if (!customVal) return window.ui.showToast('Please enter a value for the custom action', 'error');
                
                const params = {};
                params[preset.customField] = customVal;
                actionObj = { type: preset.type, params };
            } else {
                // Standard preset — use its pre-defined type + params
                actionObj = { type: preset.type, params: { ...preset.params } };
            }
            
            try {
                if (nameInput.disabled) {
                    await window.api.updateGesture(name, actionObj, dName);
                } else {
                    await window.api.addGesture(name, actionObj, dName);
                }
                window.ui.showToast('Mapping saved successfully!');
                root.innerHTML = '';
                
                if (window.modalSaveCallback) {
                    window.modalSaveCallback();
                    window.modalSaveCallback = null;
                } else {
                    Controllers.initGestures();
                }
            } catch (err) {
                window.ui.showToast('Error saving mapping', 'error');
            }
        }
    });
    
    window.router = new HashRouter();
    window.router.init();
});
