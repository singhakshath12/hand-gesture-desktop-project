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
            const actionStr = data.action_map[gesture] ? 
                (typeof data.action_map[gesture] === 'string' ? data.action_map[gesture] : data.action_map[gesture].type) 
                : 'Unmapped';
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
        
        const title = root.querySelector('#modal-title');
        const nameInput = root.querySelector('#modal-gesture-name');
        const dNameInput = root.querySelector('#modal-display-name');
        const typeSelect = root.querySelector('#modal-action-type');
        const dynamicParams = root.querySelector('#modal-dynamic-params');
        const btnSave = root.querySelector('#btn-modal-save');
        
        if (gestureName) {
            title.innerText = 'Remap Gesture';
            nameInput.value = gestureName;
            nameInput.disabled = true; // Internal ML ID stays locked
            dNameInput.value = existingDisplayName || gestureName;
        } else {
            title.innerText = 'Add Custom Gesture';
            nameInput.disabled = false;
        }

        const renderParams = () => {
            const type = typeSelect.value;
            let html = '';
            if (type === 'none') html = `<p class="text-tertiary text-sm mt-2">This gesture will only trigger UI visualizations and logging. It will not execute OS actions.</p>`;
            else if (type === 'tracking') html = `<p class="text-tertiary text-sm mt-2">This gesture actively drives the mouse cursor. Action logging is suppressed.</p>`;
            else if (type === 'left_click') html = `<p class="text-tertiary text-sm mt-2">Simulates a native OS left mouse click.</p>`;
            else if (type === 'hotkey') html = `<label>Keys (e.g. ctrl+c)</label><input type="text" id="param-val" class="form-control" placeholder="ctrl+c">`;
            else if (type === 'press') html = `<label>Key</label><input type="text" id="param-val" class="form-control" placeholder="space">`;
            else if (type === 'alt_tab') html = `<label>Tab Count</label><input type="number" id="param-val" class="form-control" value="1">`;
            else if (type === 'open_app') html = `<label>App Path</label><input type="text" id="param-val" class="form-control" placeholder="C:\\Windows\\notepad.exe">`;
            else if (type === 'system_command') html = `<label>Command</label><input type="text" id="param-val" class="form-control" placeholder="shutdown /s">`;
            else if (type === 'volume') html = `<label>Direction</label><select id="param-val" class="form-control"><option value="up">Up</option><option value="down">Down</option></select>`;
            dynamicParams.innerHTML = html;
        };

        typeSelect.onchange = renderParams;
        
        // Pre-fill if editing
        if (existingAction) {
            if (typeof existingAction === 'string') {
                const parts = existingAction.split(':');
                typeSelect.value = parts[0].trim();
                renderParams();
                if(root.querySelector('#param-val') && parts[1]) root.querySelector('#param-val').value = parts[1].trim();
            } else {
                typeSelect.value = existingAction.type;
                renderParams();
                const pVal = root.querySelector('#param-val');
                if (pVal) {
                    if (existingAction.type === 'hotkey') pVal.value = existingAction.params.keys;
                    else if (existingAction.type === 'press') pVal.value = existingAction.params.key;
                    else if (existingAction.type === 'alt_tab') pVal.value = existingAction.params.count;
                    else if (existingAction.type === 'open_app') pVal.value = existingAction.params.path;
                    else if (existingAction.type === 'system_command') pVal.value = existingAction.params.command;
                    else if (existingAction.type === 'volume') pVal.value = existingAction.params.direction;
                }
            }
        } else {
            renderParams();
        };
        
        // Note: Modal save and close are now handled via global Event Delegation
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
            const typeSelect = root.querySelector('#modal-action-type');
            
            if (!nameInput) return;

            const name = nameInput.value.trim().replace(/\s+/g, '_');
            const dName = dNameInput.value.trim();
            if (!name) return window.ui.showToast('Internal Name required', 'error');
            
            const type = typeSelect.value;
            let params = {};
            const pVal = root.querySelector('#param-val');
            if (pVal) {
                if (type === 'hotkey') params.keys = pVal.value;
                else if (type === 'press') params.key = pVal.value;
                else if (type === 'alt_tab') params.count = parseInt(pVal.value) || 1;
                else if (type === 'open_app') params.path = pVal.value;
                else if (type === 'system_command') params.command = pVal.value;
                else if (type === 'volume') params.direction = pVal.value;
            }
            
            const actionObj = { type, params };
            
            try {
                if (nameInput.disabled) {
                    await window.api.updateGesture(name, actionObj, dName);
                } else {
                    await window.api.addGesture(name, actionObj, dName);
                }
                window.ui.showToast('Mapping saved successfully!');
                root.innerHTML = ''; // Close modal
                
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
