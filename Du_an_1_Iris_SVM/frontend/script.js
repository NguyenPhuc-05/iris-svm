/* ================================================================
   Iris AI Explorer — Main Script
   Multi-Kernel SVM + Support Vectors + Live Playground + Kernel Arena + XAI + Batch
   ================================================================ */

// ─── API Configuration ───
const isLocal = ['localhost', '127.0.0.1'].includes(location.hostname) || location.protocol === 'file:';

const API_BASE = isLocal
    ? 'http://127.0.0.1:8000'
    : 'https://iris-svm-api-yfd4.onrender.com';

const IDP_API_URL = isLocal
    ? 'http://127.0.0.1:8001'
    : 'https://identity-service-0lph.onrender.com'; // URL trên render

const CLIENT_ID = 'iris-svm-api';

// ─── Identity Service Auth Fetcher ───
async function fetchAuth(endpoint, options = {}) {
    const authErr = document.getElementById('auth-error');
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 60000);
        const res = await fetch(`${IDP_API_URL}${endpoint}`, {
            ...options,
            signal: controller.signal
        });
        clearTimeout(timeoutId);
        return res;
    } catch (e) {
        if (authErr) {
            authErr.textContent = 'Identity service unavailable, try again';
            authErr.hidden = false;
            authErr.style.background = 'rgba(239, 68, 68, 0.15)';
            authErr.style.color = '#ef4444';
        }
        throw e;
    }
}

// Kiểm tra token tại IdP trước khi kết luận phiên đăng nhập đã hết hạn.
// Nếu IdP vẫn chấp nhận token nhưng Iris API trả 401 thì cần kiểm tra cấu hình JWT giữa hai dịch vụ.
async function isIdentityTokenValid() {
    if (!authToken) return false;
    try {
        const res = await fetchAuth('/me', {
            headers: { 'Authorization': 'Bearer ' + authToken }
        });
        return res.ok;
    } catch (error) {
        console.warn('Không thể xác minh phiên với Identity Service:', error);
        return null;
    }
}

function showApiAuthConfigurationError() {
    const message = 'Iris API từ chối token nhưng Identity Service vẫn xác nhận phiên hợp lệ. Hãy kiểm tra JWT_SECRET phải giống hệt nhau ở Render của identity-service và iris-svm-api; CLIENT_ID của API phải là iris-svm-api.';
    const errorEl = document.getElementById('error-msg');
    if (errorEl) {
        errorEl.textContent = message;
        errorEl.hidden = false;
    }
    console.error(message);
}


// ─── Feature Config ───
const FEATURES = [
    { key: 'sepal-length', api: 'sepal_length', label: 'Sepal Length', min: 4.0, max: 8.0 },
    { key: 'sepal-width', api: 'sepal_width', label: 'Sepal Width', min: 2.0, max: 5.0 },
    { key: 'petal-length', api: 'petal_length', label: 'Petal Length', min: 1.0, max: 7.0 },
    { key: 'petal-width', api: 'petal_width', label: 'Petal Width', min: 0.1, max: 3.0 }
];

const PRESETS = {
    setosa: { 'sepal-length': 5.0, 'sepal-width': 3.4, 'petal-length': 1.5, 'petal-width': 0.2 },
    versicolor: { 'sepal-length': 5.9, 'sepal-width': 2.8, 'petal-length': 4.3, 'petal-width': 1.3 },
    virginica: { 'sepal-length': 6.7, 'sepal-width': 3.1, 'petal-length': 5.6, 'petal-width': 2.4 }
};

const BOTANICAL = {
    setosa: {
        name: 'Iris setosa', badge: 'Setosa',
        image: 'images/setosa.jpg',
        fallback: 'https://upload.wikimedia.org/wikipedia/commons/5/56/Kosaciec_szczecinkowaty_Iris_setosa.jpg',
        kingdom: 'Plantae', phylum: 'Magnoliophyta', class_: 'Liliopsida',
        order: 'Asparagales', family: 'Iridaceae', genus: 'Iris', species: 'I. setosa',
        description: 'Đặc trưng bởi cánh hoa rất ngắn, màu xanh tím rực rỡ.',
        habitat: '🌍 Phân bố: Vùng lạnh như Alaska, Canada, Siberia. Thích đất ẩm.'
    },
    versicolor: {
        name: 'Iris versicolor', badge: 'Versicolor',
        image: 'images/versicolor.jpg',
        fallback: 'https://upload.wikimedia.org/wikipedia/commons/4/41/Iris_versicolor_3.jpg',
        kingdom: 'Plantae', phylum: 'Magnoliophyta', class_: 'Liliopsida',
        order: 'Asparagales', family: 'Iridaceae', genus: 'Iris', species: 'I. versicolor',
        description: 'Tên gọi có nghĩa là "nhiều màu". Kích thước trung bình, hoa đổi sắc theo ánh sáng.',
        habitat: '🌍 Phân bố: Bắc Mỹ. Thường mọc ven đầm lầy, bờ ao.'
    },
    virginica: {
        name: 'Iris virginica', badge: 'Virginica',
        image: 'images/virginica.jpg',
        fallback: 'https://upload.wikimedia.org/wikipedia/commons/9/9f/Iris_virginica.jpg',
        kingdom: 'Plantae', phylum: 'Magnoliophyta', class_: 'Liliopsida',
        order: 'Asparagales', family: 'Iridaceae', genus: 'Iris', species: 'I. virginica',
        description: 'Loài lớn nhất trong ba loài, màu tím đậm. Rất dễ nhầm với Versicolor nếu không đo đạc.',
        habitat: '🌍 Phân bố: Miền đông nam nước Mỹ. Ưa môi trường ngập nước.'
    }
};

const IRIS_DATA = [
    [1.4, 0.2, 0], [1.4, 0.2, 0], [1.3, 0.2, 0], [1.5, 0.2, 0], [1.4, 0.2, 0], [1.7, 0.4, 0], [1.4, 0.3, 0], [1.5, 0.2, 0], [1.4, 0.2, 0], [1.5, 0.1, 0],
    [1.5, 0.2, 0], [1.6, 0.2, 0], [1.4, 0.1, 0], [1.1, 0.1, 0], [1.2, 0.2, 0], [1.5, 0.4, 0], [1.3, 0.4, 0], [1.4, 0.3, 0], [1.7, 0.3, 0], [1.5, 0.3, 0],
    [1.7, 0.2, 0], [1.5, 0.4, 0], [1.0, 0.2, 0], [1.7, 0.5, 0], [1.9, 0.2, 0], [1.6, 0.2, 0], [1.6, 0.4, 0], [1.5, 0.2, 0], [1.4, 0.2, 0], [1.6, 0.2, 0],
    [1.6, 0.2, 0], [1.5, 0.4, 0], [1.5, 0.1, 0], [1.4, 0.2, 0], [1.5, 0.2, 0], [1.2, 0.2, 0], [1.3, 0.2, 0], [1.4, 0.1, 0], [1.3, 0.2, 0], [1.5, 0.2, 0],
    [1.3, 0.3, 0], [1.3, 0.3, 0], [1.3, 0.2, 0], [1.6, 0.6, 0], [1.9, 0.4, 0], [1.4, 0.3, 0], [1.6, 0.2, 0], [1.4, 0.2, 0], [1.5, 0.2, 0], [1.4, 0.2, 0],
    [4.7, 1.4, 1], [4.5, 1.5, 1], [4.9, 1.5, 1], [4.0, 1.3, 1], [4.6, 1.5, 1], [4.5, 1.3, 1], [4.7, 1.6, 1], [3.3, 1.0, 1], [4.6, 1.3, 1], [3.9, 1.4, 1],
    [3.5, 1.0, 1], [4.2, 1.5, 1], [4.0, 1.0, 1], [4.7, 1.4, 1], [3.6, 1.3, 1], [4.4, 1.4, 1], [4.5, 1.5, 1], [4.1, 1.0, 1], [4.5, 1.5, 1], [3.9, 1.1, 1],
    [4.8, 1.8, 1], [4.0, 1.3, 1], [4.9, 1.5, 1], [4.7, 1.2, 1], [4.3, 1.3, 1], [4.4, 1.4, 1], [4.8, 1.4, 1], [5.0, 1.7, 1], [4.5, 1.5, 1], [3.5, 1.0, 1],
    [3.8, 1.1, 1], [3.7, 1.0, 1], [3.9, 1.2, 1], [5.1, 1.6, 1], [4.5, 1.5, 1], [4.5, 1.6, 1], [4.7, 1.5, 1], [4.4, 1.3, 1], [4.1, 1.3, 1], [4.0, 1.3, 1],
    [4.4, 1.2, 1], [4.6, 1.4, 1], [4.0, 1.2, 1], [3.3, 1.0, 1], [4.2, 1.3, 1], [4.2, 1.2, 1], [4.2, 1.3, 1], [4.3, 1.3, 1], [3.0, 1.1, 1], [4.1, 1.3, 1],
    [6.0, 2.5, 2], [5.1, 1.9, 2], [5.9, 2.1, 2], [5.6, 1.8, 2], [5.8, 2.2, 2], [6.6, 2.1, 2], [4.5, 1.7, 2], [6.3, 1.8, 2], [5.8, 1.8, 2], [6.1, 2.5, 2],
    [5.1, 2.0, 2], [5.3, 1.9, 2], [5.5, 2.1, 2], [5.0, 2.0, 2], [5.1, 2.4, 2], [5.3, 2.3, 2], [5.5, 1.8, 2], [6.7, 2.2, 2], [6.9, 2.3, 2], [5.0, 1.5, 2],
    [5.7, 2.3, 2], [4.9, 2.0, 2], [6.7, 2.0, 2], [4.9, 1.8, 2], [5.7, 2.1, 2], [6.0, 1.8, 2], [4.8, 1.8, 2], [4.9, 1.8, 2], [5.6, 2.1, 2], [5.8, 1.6, 2],
    [6.1, 1.9, 2], [6.4, 2.0, 2], [5.6, 2.2, 2], [5.1, 1.5, 2], [5.6, 1.4, 2], [6.1, 2.3, 2], [5.6, 2.4, 2], [5.5, 1.8, 2], [4.8, 1.8, 2], [5.4, 2.1, 2],
    [5.6, 2.4, 2], [5.1, 2.3, 2], [5.1, 1.9, 2], [5.9, 2.3, 2], [5.7, 2.5, 2], [5.2, 2.3, 2], [5.0, 1.9, 2], [5.2, 2.0, 2], [5.4, 2.3, 2], [5.1, 1.8, 2]
];

// ─── Constants & State ───

// ===== AUTHENTICATION LOGIC =====
let authToken = localStorage.getItem('iris_auth_token');
let currentUsername = localStorage.getItem('iris_username');
let isOwner = localStorage.getItem('iris_is_owner') === '1';

function parseJwtPayload(token) {
    try {
        const base64Url = token.split('.')[1];
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        const jsonPayload = decodeURIComponent(atob(base64).split('').map(function (c) {
            return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
        }).join(''));
        return JSON.parse(jsonPayload);
    } catch (e) {
        return null;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const authOverlay = document.getElementById('auth-overlay');
    const authForm = document.getElementById('auth-form');
    const userBadge = document.getElementById('user-badge');
    const navUsername = document.getElementById('nav-username');
    const logoutBtn = document.getElementById('logout-btn');
    const authSwitchBtn = document.getElementById('auth-switch-btn');
    const authSwitchText = document.getElementById('auth-switch-text');
    const authTitle = document.getElementById('auth-title');
    const authSubmitBtn = document.getElementById('auth-submit-btn');
    const authError = document.getElementById('auth-error');

    let isLoginMode = true;

    function checkAuth() {
        const appContainer = document.getElementById('app-container');
        if (!authToken) {
            authOverlay.classList.remove('hidden');
            if (appContainer) appContainer.style.display = 'none';
        } else {
            authOverlay.classList.add('hidden');
            if (appContainer) appContainer.style.display = 'block';
            if (userBadge) userBadge.hidden = false;
            if (navUsername) {
                navUsername.innerHTML = currentUsername + (isOwner ? ' <span style="background:rgba(245,158,11,0.2);color:#f59e0b;padding:2px 8px;border-radius:12px;font-size:0.75rem;font-weight:600;margin-left:4px;">👑 Chủ sở hữu</span>' : '');
            }
            const adminTabBtn = document.getElementById('tab-btn-admin');
            if (adminTabBtn) {
                adminTabBtn.style.display = isOwner ? 'inline-block' : 'none';
            }
            loadHistoryFromDB();
            if (isOwner) {
                loadAdminData();
            }
            updateProfileView();
        }
    }

    // Nút hiện/ẩn mật khẩu (dùng chung cho đăng nhập và đăng ký)
    const authPassInput = document.getElementById('auth-pass');
    const authPassToggle = document.getElementById('auth-pass-toggle');

    function setPasswordVisible(visible) {
        if (!authPassInput || !authPassToggle) return;
        authPassInput.type = visible ? 'text' : 'password';
        authPassToggle.setAttribute('aria-pressed', visible ? 'true' : 'false');
        const label = visible ? 'Ẩn mật khẩu' : 'Hiện mật khẩu';
        authPassToggle.setAttribute('aria-label', label);
        authPassToggle.title = label;
    }

    if (authPassToggle && authPassInput) {
        authPassToggle.addEventListener('click', () => {
            const start = authPassInput.selectionStart;
            const end = authPassInput.selectionEnd;
            setPasswordVisible(authPassInput.type === 'password');
            authPassInput.focus();
            try { authPassInput.setSelectionRange(start, end); } catch (e) { /* bỏ qua */ }
        });
    }

    if (authSwitchBtn) {
        authSwitchBtn.addEventListener('click', () => {
            isLoginMode = !isLoginMode;
            authError.hidden = true;
            setPasswordVisible(false);
            if (authPassInput) {
                authPassInput.autocomplete = isLoginMode ? 'current-password' : 'new-password';
            }
            if (isLoginMode) {
                authTitle.textContent = '👋 Chào mừng đến với Iris AI';
                authSubmitBtn.textContent = 'Đăng nhập';
                authSwitchText.textContent = 'Chưa có tài khoản?';
                authSwitchBtn.textContent = 'Đăng ký ngay';
            } else {
                authTitle.textContent = '🚀 Tạo tài khoản mới';
                authSubmitBtn.textContent = 'Đăng ký';
                authSwitchText.textContent = 'Đã có tài khoản?';
                authSwitchBtn.textContent = 'Đăng nhập ngay';
            }
        });
    }

    if (authForm) {
        authForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const email = document.getElementById('auth-user').value.trim();
            const password = document.getElementById('auth-pass').value;
            setPasswordVisible(false);
            authError.hidden = true;
            authSubmitBtn.disabled = true;
            authSubmitBtn.textContent = 'Đang xử lý...';

            try {
                if (isLoginMode) {
                    const res = await fetchAuth('/login', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ email, password, client_id: CLIENT_ID })
                    });
                    const data = await res.json();

                    if (!res.ok) {
                        authError.textContent = data.detail || 'Sai thông tin đăng nhập hoặc client_id không hợp lệ';
                        authError.hidden = false;
                        authError.style.background = 'rgba(239, 68, 68, 0.15)';
                        authError.style.color = '#ef4444';
                    } else {
                        authToken = data.access_token;
                        currentUsername = data.user.email;
                        const payload = parseJwtPayload(authToken);
                        isOwner = !!(data.user && data.user.is_owner) || !!(payload && payload.is_owner);
                        localStorage.setItem('iris_auth_token', authToken);
                        localStorage.setItem('iris_username', currentUsername);
                        localStorage.setItem('iris_is_owner', isOwner ? '1' : '0');
                        checkAuth();
                    }
                } else {
                    const res = await fetchAuth('/register', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ email, password })
                    });
                    const data = await res.json();

                    if (!res.ok) {
                        authError.textContent = data.detail || 'Đã có lỗi khi đăng ký';
                        authError.hidden = false;
                        authError.style.background = 'rgba(239, 68, 68, 0.15)';
                        authError.style.color = '#ef4444';
                    } else {
                        authSwitchBtn.click();
                        authError.textContent = 'Đăng ký thành công! Vui lòng đăng nhập với tài khoản vừa tạo.';
                        authError.hidden = false;
                        authError.style.background = 'rgba(76, 175, 80, 0.1)';
                        authError.style.color = '#4caf50';
                    }
                }
            } catch (err) {
                authError.textContent = 'Identity service unavailable, try again';
                authError.hidden = false;
                authError.style.background = 'rgba(239, 68, 68, 0.15)';
                authError.style.color = '#ef4444';
            } finally {
                authSubmitBtn.disabled = false;
                authSubmitBtn.textContent = isLoginMode ? 'Đăng nhập' : 'Đăng ký';
            }
        });
    }

    function triggerLogout() {
        localStorage.removeItem('iris_auth_token');
        localStorage.removeItem('iris_username');
        localStorage.removeItem('iris_is_owner');
        authToken = null;
        currentUsername = null;
        isOwner = false;
        const adminTabBtn = document.getElementById('tab-btn-admin');
        if (adminTabBtn) adminTabBtn.style.display = 'none';

        // Đưa tab về lại tab Phân tích mặc định
        document.querySelectorAll('.tab-btn').forEach(b => {
            const isPredict = b.dataset.tab === 'predict';
            b.classList.toggle('active', isPredict);
            b.setAttribute('aria-selected', isPredict ? 'true' : 'false');
        });
        document.querySelectorAll('.tab-panel').forEach(p => {
            const isPredict = p.id === 'panel-predict';
            p.classList.toggle('active', isPredict);
            p.hidden = !isPredict;
        });

        // Reset form đăng nhập / đăng ký về trạng thái ban đầu
        const authUser = document.getElementById('auth-user');
        const authPass = document.getElementById('auth-pass');
        const authError = document.getElementById('auth-error');
        if (authUser) authUser.value = '';
        if (authPass) {
            authPass.value = '';
            authPass.autocomplete = 'current-password';
        }
        setPasswordVisible(false);
        if (authError) authError.hidden = true;

        isLoginMode = true;
        if (authTitle) authTitle.textContent = '👋 Chào mừng đến với Iris AI';
        if (authSubmitBtn) authSubmitBtn.textContent = 'Đăng nhập';
        if (authSwitchText) authSwitchText.textContent = 'Chưa có tài khoản?';
        if (authSwitchBtn) authSwitchBtn.textContent = 'Đăng ký ngay';

        checkAuth();
    }
    window.triggerLogout = triggerLogout;

    if (logoutBtn) {
        logoutBtn.addEventListener('click', triggerLogout);
    }
    const profileSignoutBtn = document.getElementById('profile-signout-btn');
    if (profileSignoutBtn) {
        profileSignoutBtn.addEventListener('click', triggerLogout);
    }

    checkAuth();
});
// ================================

const SPECIES_NAMES = ['setosa', 'versicolor', 'virginica'];
const CLASS_COLORS = ['#fb7185', '#a78bfa', '#38bdf8'];

function setFeatureValue(key, val) {
    const inp = document.getElementById(`inp-${key}`);
    const rng = document.getElementById(`rng-${key}`);
    if (inp) inp.value = val;
    if (rng) { rng.value = val; updateSliderFill(rng); }
}

let currentPrediction = null;
let isRequesting = false;
let modelsInfo = null;
let boundaryCache = {};
let currentBoundaryData = null;
let supportVectorsData = null;
let showSupportVectors = true;
let pgDebounceTimer = null;
let batchPredictionsData = [];
let historyData = [];

// ================================================================
// 1. INITIALIZATION
// ================================================================
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initTabs();
    initSliders();
    initPresets();
    initPredictBtn();
    initCursorGlow();
    initMagneticCards();
    initRippleButtons();
    initPetals();
    initKernelSelector();
    initBoundarySelector();
    initSupportVectors();
    initClickToPredict();
    initSvmPlayground();
    initKernelArena();
    initBatchPrediction();
    initExportExcel();
    initExportImage();
    initClearHistory();
    initBotanicalAnatomy();
    initPca3D();
    initStressTest();
    initKktInspector();
    initCertificateModal();
    initGuidedTour();
    drawRadar();
    drawScatter();
    checkApiHealth();
    loadModelsInfo();
    animateNumbers();
});

// ================================================================
// 2. TABS & THEME
// ================================================================
function initTabs() {
    const btns = document.querySelectorAll('.tab-btn');
    const panels = document.querySelectorAll('.tab-panel');

    btns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = `panel-${btn.dataset.tab}`;
            btns.forEach(b => { b.classList.remove('active'); b.setAttribute('aria-selected', 'false'); });
            btn.classList.add('active');
            btn.setAttribute('aria-selected', 'true');
            panels.forEach(p => { p.classList.remove('active'); p.hidden = true; });
            const targetPanel = document.getElementById(targetId);
            if (targetPanel) {
                targetPanel.classList.add('active');
                targetPanel.hidden = false;
            }

            if (btn.dataset.tab === 'data') {
                requestAnimationFrame(() => drawScatter());
            } else if (btn.dataset.tab === 'predict') {
                requestAnimationFrame(() => drawRadar());
            } else if (btn.dataset.tab === 'pca3d') {
                loadPca3D();
            } else if (btn.dataset.tab === 'svm') {
                loadKernelArena();
                loadKktSupportVectors();
            } else if (btn.dataset.tab === 'history') {
                loadHistoryFromDB();
            } else if (btn.dataset.tab === 'admin') {
                loadAdminData();
            } else if (btn.dataset.tab === 'profile') {
                updateProfileView();
            }
        });
    });
}

function initTheme() {
    const saved = localStorage.getItem('iris-theme') || 'light';
    applyTheme(saved);
    const toggle = document.getElementById('theme-toggle');
    if (toggle) {
        toggle.addEventListener('click', () => {
            const current = document.documentElement.getAttribute('data-theme') || 'light';
            const next = current === 'dark' ? 'light' : 'dark';
            applyTheme(next);
            localStorage.setItem('iris-theme', next);
        });
    }
}

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    const icon = document.getElementById('theme-icon');
    if (icon) icon.textContent = theme === 'dark' ? '☀️' : '🌙';
    drawRadar();
    drawScatter();
}

// ================================================================
// 3. KERNEL SELECTOR & MODELS INFO
// ================================================================
function initKernelSelector() {
    const select = document.getElementById('kernel-select');
    if (select) {
        select.addEventListener('change', () => {
            updateKernelInfo();
            // Sync with boundary kernel in Tab 2
            const bKernel = document.getElementById('boundary-kernel');
            if (bKernel && bKernel.value) {
                bKernel.value = select.value;
                loadBoundary(select.value);
                loadSupportVectors(select.value);
            }
        });
    }
}

async function loadModelsInfo() {
    try {
        const res = await fetch(`${API_BASE}/models`);
        if (res.ok) {
            modelsInfo = await res.json();
            updateKernelInfo();
            // Pre-load default kernel boundary and support vectors
            loadBoundary('rbf');
            loadSupportVectors('rbf');
        }
    } catch (e) { /* silent */ }
}

function updateKernelInfo() {
    const select = document.getElementById('kernel-select');
    const accEl = document.getElementById('kernel-acc');
    if (!select || !accEl) return;
    const kernel = select.value;
    if (modelsInfo && modelsInfo.models) {
        const m = modelsInfo.models.find(x => x.kernel === kernel);
        if (m) {
            accEl.textContent = `🎯 Accuracy: ${(m.cv_accuracy_mean * 100).toFixed(1)}% (±${(m.cv_accuracy_std * 100).toFixed(1)}%)`;
            return;
        }
    }
    const fallback = { linear: '96.7%', rbf: '96.0%', poly: '90.7%', sigmoid: '91.3%' };
    accEl.textContent = `🎯 Accuracy: ${fallback[kernel] || '—'}`;
}

// ================================================================
// 4. SLIDERS & PRESETS
// ================================================================
function initSliders() {
    FEATURES.forEach(f => {
        const rng = document.getElementById(`rng-${f.key}`);
        const inp = document.getElementById(`inp-${f.key}`);
        if (!rng || !inp) return;

        const updateVal = (val) => {
            val = Math.max(f.min, Math.min(f.max, parseFloat(val) || f.min));
            val = Math.round(val * 10) / 10;
            rng.value = val;
            inp.value = val;
            updateSliderFill(rng);
            drawRadar();
            drawScatter();
            if (typeof updateBotanicalAnatomyValues === 'function') updateBotanicalAnatomyValues();
        };

        rng.addEventListener('input', () => updateVal(rng.value));
        inp.addEventListener('change', () => updateVal(inp.value));
        updateSliderFill(rng);
    });
}

function updateSliderFill(slider) {
    const min = parseFloat(slider.min), max = parseFloat(slider.max), val = parseFloat(slider.value);
    const pct = ((val - min) / (max - min)) * 100;
    slider.style.background = `linear-gradient(to right, var(--c4) 0%, var(--c4) ${pct}%, rgba(89,62,103,.12) ${pct}%, rgba(89,62,103,.12) 100%)`;
}

function initPresets() {
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const p = PRESETS[btn.dataset.preset];
            if (!p) return;
            FEATURES.forEach(f => setFeatureValue(f.key, p[f.key]));
            drawRadar();
            drawScatter();
            document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        });
    });
}

function getValues() {
    const v = {};
    FEATURES.forEach(f => {
        const inp = document.getElementById(`inp-${f.key}`);
        v[f.api] = parseFloat(inp ? inp.value : f.min);
    });
    return v;
}

// ================================================================
// 5. PREDICTION & EXPLAINABLE AI (XAI)
// ================================================================
function initPredictBtn() {
    const btn = document.getElementById('predict-btn');
    if (btn) btn.addEventListener('click', doPredict);
}

async function doPredict() {
    if (isRequesting) return;
    const vals = getValues();
    const kernelSelect = document.getElementById('kernel-select');
    const kernel = kernelSelect ? kernelSelect.value : 'rbf';
    const body = { ...vals, kernel };

    const errEl = document.getElementById('error-msg');
    const loader = document.getElementById('loader');
    const btnText = document.getElementById('btn-text');
    if (errEl) errEl.hidden = true;
    if (loader) loader.classList.add('active');
    if (btnText) btnText.textContent = 'Đang phân tích...';
    isRequesting = true;

    try {
        const res = await fetch(`${API_BASE}/predict`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + authToken },
            body: JSON.stringify(body)
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            if (res.status === 401) {
                const identityValid = await isIdentityTokenValid();
                if (identityValid === true) {
                    showApiAuthConfigurationError();
                } else if (identityValid === false) {
                    if (window.triggerLogout) window.triggerLogout();
                } else {
                    throw new Error('Chưa xác minh được phiên đăng nhập do Identity Service tạm thời không phản hồi. Vui lòng thử lại.');
                }
                return;
            }
            throw new Error(err.detail || `Lỗi ${res.status}`);
        }

        const data = await res.json();
        const species = data.prediction.toLowerCase();
        currentPrediction = { species, probability: data.probability, id: data.id, kernel: data.kernel };

        highlightCard(species, data.probability);
        showBotanical(species, data.probability, data.kernel);
        triggerConfetti(species);

        // Fetch Explainable AI (XAI)
        fetchXaiExplanation(body);

        // Refresh history
        loadHistoryFromDB();

    } catch (err) {
        if (errEl) {
            errEl.textContent = `❌ ${err.message}`;
            errEl.hidden = false;
        }
    } finally {
        if (loader) loader.classList.remove('active');
        if (btnText) btnText.textContent = '🔬 Phân tích & Dự đoán';
        isRequesting = false;
    }
}

// ─── Explainable AI Feature Attribution ───
async function fetchXaiExplanation(body) {
    const xaiPanel = document.getElementById('xai-panel');
    const xaiBars = document.getElementById('xai-bars');
    const xaiText = document.getElementById('xai-summary-text');
    if (!xaiPanel) return;

    try {
        const res = await fetch(`${API_BASE}/explain`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + authToken },
            body: JSON.stringify(body)
        });
        if (!res.ok) return;

        const data = await res.json();
        xaiPanel.hidden = false;

        if (xaiBars) {
            xaiBars.innerHTML = data.attributions.map(attr => `
                <div class="xai-bar-row">
                    <div class="xai-bar-top">
                        <span>${attr.display_name}: <strong>${attr.value} cm</strong></span>
                        <span style="color:var(--c4);">${attr.importance_pct}% mức độ ảnh hưởng</span>
                    </div>
                    <div class="xai-bar-track">
                        <div class="xai-bar-fill" style="width: ${Math.max(5, attr.importance_pct)}%;"></div>
                    </div>
                    <div class="xai-bar-sub">
                        <span>Khoảng sinh học của ${data.prediction}: ${attr.typical_range}</span>
                    </div>
                </div>
            `).join('');
        }

        if (xaiText) {
            xaiText.innerHTML = data.explanation.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        }
    } catch (e) { /* silent */ }
}

function highlightCard(species, prob) {
    SPECIES_NAMES.forEach(s => {
        const card = document.getElementById(`card-${s}`);
        const probEl = document.getElementById(`prob-${s}`);
        if (!card) return;
        const isMatch = (s === species);
        card.classList.toggle('highlighted', isMatch);
        card.classList.toggle('dimmed', !isMatch);
        if (probEl) {
            probEl.textContent = isMatch ? `${Math.round(prob * 100)}%` : '';
            probEl.classList.toggle('show', isMatch);
        }
    });
}

function showBotanical(species, prob, kernel) {
    const b = BOTANICAL[species];
    const panel = document.getElementById('botanical-panel');
    if (!b || !panel) return;
    panel.hidden = false;

    const imgEl = document.getElementById('bot-img');
    if (imgEl && b.image) {
        imgEl.onerror = function () {
            if (b.fallback && this.src !== b.fallback) {
                this.src = b.fallback;
            }
        };
        imgEl.src = b.image;
        imgEl.alt = b.name;
    }

    panel.style.display = 'block';

    const setText = (id, txt) => {
        const el = document.getElementById(id);
        if (el) el.textContent = txt || '';
    };

    setText('bot-name', b.name);
    setText('bot-badge', b.badge);
    setText('bot-desc', b.description);
    setText('bot-habitat', b.habitat);

    const probEl = document.getElementById('bot-prob') || document.getElementById('bot-conf');
    if (probEl) {
        probEl.textContent = `${Math.round(prob * 100)}% tin cậy`;
        probEl.style.display = 'inline-block';
    }

    ['kingdom', 'phylum', 'class_', 'order', 'family', 'genus', 'species'].forEach(k => {
        setText(`bot-${k === 'class_' ? 'class' : k}`, b[k]);
    });

    const kernelBadge = document.getElementById('bot-kernel-badge');
    if (kernelBadge && kernel) {
        const kernelNames = { linear: 'Linear', rbf: 'RBF', poly: 'Poly', sigmoid: 'Sigmoid' };
        kernelBadge.textContent = `🔧 Kernel: ${kernelNames[kernel] || kernel}`;
        kernelBadge.style.display = 'inline-block';
    }
}

// ================================================================
// 6. RADAR CHART (Canvas)
// ================================================================
function drawRadar() {
    const canvas = document.getElementById('radar-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    const cx = W / 2, cy = H / 2;
    // Generous radial margin
    const R = Math.min((W - 280) / 2, (H - 120) / 2);
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';

    ctx.clearRect(0, 0, W, H);
    const n = FEATURES.length;
    const angleStep = (Math.PI * 2) / n;
    const startAngle = -Math.PI / 2;

    const gridColor = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(89,62,103,0.1)';
    const textColor = isDark ? '#e2d4e0' : '#4a2c4e';
    const valColor = '#fea837';

    // Concentric grid rings (25%, 50%, 75%, 100%)
    for (let ring = 1; ring <= 4; ring++) {
        const r = (R / 4) * ring;
        ctx.beginPath();
        for (let i = 0; i < n; i++) {
            const angle = startAngle + i * angleStep;
            const x = cx + r * Math.cos(angle);
            const y = cy + r * Math.sin(angle);
            i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        }
        ctx.closePath();
        ctx.strokeStyle = gridColor;
        ctx.lineWidth = 1;
        ctx.stroke();
    }

    // Radial Axes
    for (let i = 0; i < n; i++) {
        const angle = startAngle + i * angleStep;
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.lineTo(cx + R * Math.cos(angle), cy + R * Math.sin(angle));
        ctx.strokeStyle = gridColor;
        ctx.stroke();
    }

    // Normalized polygon
    const vals = getValues();
    const pts = FEATURES.map((f, i) => {
        const norm = (vals[f.api] - f.min) / (f.max - f.min);
        const r = R * Math.max(0.05, Math.min(1.0, norm));
        const angle = startAngle + i * angleStep;
        return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
    });

    // Fill & stroke polygon
    ctx.beginPath();
    pts.forEach((p, i) => i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y));
    ctx.closePath();
    ctx.fillStyle = isDark ? 'rgba(186,134,166,0.32)' : 'rgba(89,62,103,0.2)';
    ctx.fill();
    ctx.strokeStyle = isDark ? '#fea837' : '#593e67';
    ctx.lineWidth = 2.5;
    ctx.stroke();

    // Data points on vertices
    pts.forEach(p => {
        ctx.beginPath();
        ctx.arc(p.x, p.y, 4.5, 0, Math.PI * 2);
        ctx.fillStyle = '#fea837';
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 1.5;
        ctx.stroke();
    });

    // Informative labels & live values with smart alignment
    const meta = [
        { label: 'Sepal Length (Dài đài)', align: 'center', dx: 0, dy: -24, valDy: -10 },
        { label: 'Sepal Width (Rộng đài)', align: 'left', dx: 14, dy: -6, valDy: 9 },
        { label: 'Petal Length (Dài cánh)', align: 'center', dx: 0, dy: 16, valDy: 30 },
        { label: 'Petal Width (Rộng cánh)', align: 'right', dx: -14, dy: -6, valDy: 9 }
    ];

    for (let i = 0; i < n; i++) {
        const angle = startAngle + i * angleStep;
        const vx = cx + R * Math.cos(angle);
        const vy = cy + R * Math.sin(angle);
        const m = meta[i];
        const f = FEATURES[i];
        const curVal = (vals[f.api] !== undefined ? vals[f.api] : f.min).toFixed(1);

        ctx.textAlign = m.align;

        // Label name
        ctx.font = '600 11px Inter, sans-serif';
        ctx.fillStyle = textColor;
        ctx.fillText(m.label, vx + m.dx, vy + m.dy);

        // Value text
        ctx.font = '700 11.5px Inter, sans-serif';
        ctx.fillStyle = valColor;
        ctx.fillText(`${curVal} cm`, vx + m.dx, vy + m.valDy);
    }
}

// ================================================================
// 7. SCATTER PLOT & DECISION BOUNDARY & SUPPORT VECTORS
// ================================================================
function initBoundarySelector() {
    const sel = document.getElementById('boundary-kernel');
    if (!sel) return;
    sel.addEventListener('change', (e) => {
        const kernel = e.target.value;
        if (!kernel) {
            currentBoundaryData = null;
            drawScatter();
            return;
        }
        loadBoundary(kernel);
        loadSupportVectors(kernel);
    });
}

function initSupportVectors() {
    const toggle = document.getElementById('toggle-support-vectors');
    if (toggle) {
        toggle.addEventListener('change', (e) => {
            showSupportVectors = e.target.checked;
            drawScatter();
        });
    }
}

async function loadSupportVectors(kernel) {
    if (!kernel) return;
    try {
        const res = await fetch(`${API_BASE}/support-vectors?kernel=${kernel}`);
        if (res.ok) {
            supportVectorsData = await res.json();
            const bar = document.getElementById('sv-stats-bar');
            if (bar && supportVectorsData) {
                const c = supportVectorsData.n_support_per_class;
                bar.innerHTML = `⚡ <strong>${supportVectorsData.total_support_vectors} Support Vectors</strong>: Setosa (${c.setosa}) | Versicolor (${c.versicolor}) | Virginica (${c.virginica})`;
            }
            drawScatter();
        }
    } catch (e) { /* silent */ }
}

async function loadBoundary(kernel) {
    if (boundaryCache[kernel]) {
        currentBoundaryData = boundaryCache[kernel];
        drawScatter();
        return;
    }
    try {
        const res = await fetch(`${API_BASE}/decision-boundary?kernel=${kernel}&feature_x=petal_length&feature_y=petal_width&resolution=60`);
        if (res.ok) {
            const data = await res.json();
            boundaryCache[kernel] = data;
            currentBoundaryData = data;
            drawScatter();
        }
    } catch (e) { /* silent */ }
}

function drawScatter() {
    const canvas = document.getElementById('scatter-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    const pad = { top: 20, right: 20, bottom: 45, left: 55 };
    const pW = W - pad.left - pad.right;
    const pH = H - pad.top - pad.bottom;
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';

    ctx.clearRect(0, 0, W, H);

    const xRange = currentBoundaryData?.x_range || [0.5, 7.5];
    const yRange = currentBoundaryData?.y_range || [0.0, 3.5];

    // 1. Draw Decision Boundary background grid if available
    if (currentBoundaryData && currentBoundaryData.grid) {
        const grid = currentBoundaryData.grid;
        const res = currentBoundaryData.resolution;
        const cellW = pW / res;
        const cellH = pH / res;

        const colors = isDark ? [
            'rgba(251, 113, 133, 0.16)', // setosa
            'rgba(167, 139, 250, 0.16)', // versicolor
            'rgba(56, 189, 248, 0.16)'   // virginica
        ] : [
            'rgba(251, 113, 133, 0.14)',
            'rgba(167, 139, 250, 0.14)',
            'rgba(56, 189, 248, 0.14)'
        ];

        for (let row = 0; row < res; row++) {
            for (let col = 0; col < res; col++) {
                const cls = grid[row][col];
                ctx.fillStyle = colors[cls] || 'transparent';
                const x = pad.left + col * cellW;
                const y = pad.top + (res - 1 - row) * cellH;
                ctx.fillRect(x, y, cellW + 0.5, cellH + 0.5);
            }
        }
    }

    // 2. Axes & Grid Lines
    const gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)';
    const textColor = isDark ? '#a08aaa' : '#6e5570';

    ctx.strokeStyle = gridColor;
    ctx.lineWidth = 1;

    // X-axis ticks (Petal Length: 1 to 7)
    for (let val = 1; val <= 7; val++) {
        const x = pad.left + ((val - xRange[0]) / (xRange[1] - xRange[0])) * pW;
        ctx.beginPath(); ctx.moveTo(x, pad.top); ctx.lineTo(x, H - pad.bottom); ctx.stroke();
        ctx.font = '10px Inter, sans-serif'; ctx.fillStyle = textColor; ctx.textAlign = 'center';
        ctx.fillText(val.toFixed(0), x, H - pad.bottom + 16);
    }

    // Y-axis ticks (Petal Width: 0.5 to 3.0)
    for (let val = 0.5; val <= 3.0; val += 0.5) {
        const y = pad.top + pH - ((val - yRange[0]) / (yRange[1] - yRange[0])) * pH;
        ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(W - pad.right, y); ctx.stroke();
        ctx.font = '10px Inter, sans-serif'; ctx.fillStyle = textColor; ctx.textAlign = 'right';
        ctx.fillText(val.toFixed(1), pad.left - 8, y + 3);
    }

    // Axis Labels
    ctx.font = 'bold 11px Inter, sans-serif';
    ctx.fillStyle = textColor;
    ctx.textAlign = 'center';
    ctx.fillText('Chiều dài cánh hoa — Petal Length (cm)', pad.left + pW / 2, H - 10);

    ctx.save();
    ctx.translate(14, pad.top + pH / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('Chiều rộng cánh hoa — Petal Width (cm)', 0, 0);
    ctx.restore();

    // 3. Plot 150 Iris Points
    const svSet = (showSupportVectors && supportVectorsData?.support_vector_indices)
        ? new Set(supportVectorsData.support_vector_indices)
        : null;

    IRIS_DATA.forEach((pt, idx) => {
        const [pl, pw, cls] = pt;
        const x = pad.left + ((pl - xRange[0]) / (xRange[1] - xRange[0])) * pW;
        const y = pad.top + pH - ((pw - yRange[0]) / (yRange[1] - yRange[0])) * pH;

        // Glowing Support Vector Ring
        if (svSet && svSet.has(idx)) {
            ctx.beginPath();
            ctx.arc(x, y, 7.5, 0, Math.PI * 2);
            ctx.strokeStyle = '#e11d48';
            ctx.lineWidth = 2;
            ctx.stroke();
        }

        ctx.beginPath();
        ctx.arc(x, y, 4, 0, Math.PI * 2);
        ctx.fillStyle = CLASS_COLORS[cls];
        ctx.fill();
        ctx.strokeStyle = isDark ? 'rgba(0,0,0,0.5)' : '#fff';
        ctx.lineWidth = 1;
        ctx.stroke();
    });

    // 4. Current User Selected Point (Star ⭐)
    const vals = getValues();
    const curPL = vals.petal_length, curPW = vals.petal_width;
    const userX = pad.left + ((curPL - xRange[0]) / (xRange[1] - xRange[0])) * pW;
    const userY = pad.top + pH - ((curPW - yRange[0]) / (yRange[1] - yRange[0])) * pH;

    ctx.save();
    ctx.shadowColor = '#eab308';
    ctx.shadowBlur = 12;
    drawStar(ctx, userX, userY, 5, 11, 5.5);
    ctx.fillStyle = '#eab308';
    ctx.fill();
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 1.8;
    ctx.stroke();
    ctx.restore();
}

function drawStar(ctx, cx, cy, spikes, outerR, innerR) {
    let rot = Math.PI / 2 * 3; const step = Math.PI / spikes;
    ctx.beginPath(); ctx.moveTo(cx, cy - outerR);
    for (let i = 0; i < spikes; i++) {
        ctx.lineTo(cx + Math.cos(rot) * outerR, cy + Math.sin(rot) * outerR); rot += step;
        ctx.lineTo(cx + Math.cos(rot) * innerR, cy + Math.sin(rot) * innerR); rot += step;
    }
    ctx.lineTo(cx, cy - outerR); ctx.closePath();
}

// ─── Click-to-Predict on Canvas ───
function initClickToPredict() {
    const canvas = document.getElementById('scatter-canvas');
    const tooltip = document.getElementById('canvas-tooltip');
    if (!canvas) return;

    canvas.addEventListener('click', async (e) => {
        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        const px = (e.clientX - rect.left) * scaleX;
        const py = (e.clientY - rect.top) * scaleY;

        const pad = { top: 20, right: 20, bottom: 45, left: 55 };
        const pW = canvas.width - pad.left - pad.right;
        const pH = canvas.height - pad.top - pad.bottom;

        if (px < pad.left || px > canvas.width - pad.right || py < pad.top || py > canvas.height - pad.bottom) return;

        const xRange = currentBoundaryData?.x_range || [0.5, 7.5];
        const yRange = currentBoundaryData?.y_range || [0.0, 3.5];

        const pl = xRange[0] + ((px - pad.left) / pW) * (xRange[1] - xRange[0]);
        const pw = yRange[1] - ((py - pad.top) / pH) * (yRange[1] - yRange[0]);

        const clampedPL = Math.max(1.0, Math.min(7.0, parseFloat(pl.toFixed(1))));
        const clampedPW = Math.max(0.1, Math.min(3.0, parseFloat(pw.toFixed(1))));

        setFeatureValue('petal-length', clampedPL);
        setFeatureValue('petal-width', clampedPW);

        drawRadar();
        drawScatter();

        // Run quick prediction
        const bSel = document.getElementById('boundary-kernel');
        const kSel = document.getElementById('kernel-select');
        const kernel = (bSel && bSel.value) ? bSel.value : (kSel ? kSel.value : 'rbf');
        const vals = getValues();
        const body = { ...vals, petal_length: clampedPL, petal_width: clampedPW, kernel };

        try {
            const res = await fetch(`${API_BASE}/predict`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + authToken },
                body: JSON.stringify(body)
            });
            if (res.ok) {
                const data = await res.json();
                if (tooltip) {
                    tooltip.innerHTML = `🌸 <strong>${data.prediction.toUpperCase()}</strong> (${(data.probability * 100).toFixed(1)}%)<br><span style="font-size:.7rem;color:var(--text-sec);">PL: ${clampedPL}cm, PW: ${clampedPW}cm</span>`;
                    tooltip.style.left = `${(e.clientX - rect.left)}px`;
                    tooltip.style.top = `${(e.clientY - rect.top)}px`;
                    tooltip.hidden = false;
                    setTimeout(() => { if (tooltip) tooltip.hidden = true; }, 3500);
                }
                fetchXaiExplanation(body);
            }
        } catch (err) { /* silent */ }
    });
}

// ================================================================
// 8. SVM LIVE PLAYGROUND
// ================================================================
function initSvmPlayground() {
    const cSlider = document.getElementById('pg-param-c');
    const gammaSlider = document.getElementById('pg-param-gamma');
    const degreeSlider = document.getElementById('pg-param-degree');
    const cVal = document.getElementById('pg-c-val');
    const gammaVal = document.getElementById('pg-gamma-val');
    const degreeVal = document.getElementById('pg-degree-val');

    if (!cSlider) return;

    const updatePG = () => {
        // C: 10^slider (-2 -> 0.01, 0 -> 1.0, 2 -> 100)
        const cNum = Math.pow(10, parseFloat(cSlider.value));
        const cFormatted = cNum < 0.1 ? cNum.toFixed(2) : (cNum < 10 ? cNum.toFixed(1) : cNum.toFixed(0));
        if (cVal) cVal.textContent = cFormatted;

        // Gamma: 10^slider (-2 -> 0.01, 0 -> 1.0, 1.3 -> ~20)
        const gNum = Math.pow(10, parseFloat(gammaSlider.value));
        const gFormatted = gNum < 0.1 ? gNum.toFixed(2) : (gNum < 10 ? gNum.toFixed(1) : gNum.toFixed(0));
        if (gammaVal) gammaVal.textContent = gFormatted;

        if (degreeVal && degreeSlider) degreeVal.textContent = degreeSlider.value;

        clearTimeout(pgDebounceTimer);
        pgDebounceTimer = setTimeout(() => runSvmPlayground(cNum, gNum, parseInt(degreeSlider?.value || 3)), 250);
    };

    cSlider.addEventListener('input', updatePG);
    if (gammaSlider) gammaSlider.addEventListener('input', updatePG);
    if (degreeSlider) degreeSlider.addEventListener('input', updatePG);

    // Initial run
    updatePG();
}

async function runSvmPlayground(C, gamma, degree) {
    const bSel = document.getElementById('boundary-kernel');
    const kSel = document.getElementById('kernel-select');
    const kernel = (bSel && bSel.value) ? bSel.value : (kSel ? kSel.value : 'rbf');

    // Show/hide degree or gamma based on kernel
    const gammaWrap = document.getElementById('pg-gamma-wrap');
    const degreeWrap = document.getElementById('pg-degree-wrap');
    if (gammaWrap) gammaWrap.style.display = (kernel === 'linear') ? 'none' : 'block';
    if (degreeWrap) degreeWrap.style.display = (kernel === 'poly') ? 'block' : 'none';

    try {
        const t0 = performance.now();
        const res = await fetch(`${API_BASE}/svm-playground?kernel=${kernel}&C=${C}&gamma=${gamma}&degree=${degree}&resolution=55`);
        if (!res.ok) return;
        const data = await res.json();
        const elapsed = (performance.now() - t0).toFixed(0);

        // Update active boundary & support vectors
        currentBoundaryData = data;
        supportVectorsData = {
            total_support_vectors: data.total_support_vectors,
            n_support_per_class: {
                setosa: data.n_support_per_class[0],
                versicolor: data.n_support_per_class[1],
                virginica: data.n_support_per_class[2]
            },
            support_vector_indices: data.support_vector_indices
        };

        const bar = document.getElementById('sv-stats-bar');
        if (bar) {
            const c = supportVectorsData.n_support_per_class;
            bar.innerHTML = `⚡ <strong>${data.total_support_vectors} Support Vectors</strong>: Setosa (${c.setosa}) | Versicolor (${c.versicolor}) | Virginica (${c.virginica})`;
        }

        drawScatter();

        // Update diagnosis box
        const accEl = document.getElementById('pg-diag-acc');
        const svEl = document.getElementById('pg-diag-sv');
        const speedEl = document.getElementById('pg-diag-speed');
        const textEl = document.getElementById('pg-diag-text');
        if (accEl) accEl.textContent = `🎯 Train Accuracy: ${data.train_accuracy}%`;
        if (svEl) svEl.textContent = `⚡ Support Vectors: ${data.total_support_vectors}`;
        if (speedEl) speedEl.textContent = `⚡ Huấn luyện lại trong ${elapsed}ms`;
        if (textEl) textEl.innerHTML = data.diagnosis;
    } catch (e) { /* silent */ }
}

// ================================================================
// 9. KERNEL ARENA (4-WAY BATTLE BENCHMARK)
// ================================================================
function initKernelArena() {
    const btn = document.getElementById('arena-refresh-btn');
    if (btn) btn.addEventListener('click', loadKernelArena);
}

async function loadKernelArena() {
    const grid = document.getElementById('arena-grid');
    if (!grid) return;

    grid.innerHTML = '<div class="arena-loading" style="grid-column:1/-1;text-align:center;padding:2rem;color:var(--text-sec);">⚡ Đang đo lường và dựng 4 bề mặt quyết định...</div>';

    try {
        const res = await fetch(`${API_BASE}/kernel-arena`);
        if (!res.ok) return;
        const data = await res.json();
        const arena = data.arena;

        grid.innerHTML = '';
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';

        arena.forEach(item => {
            const card = document.createElement('div');
            card.className = 'arena-card';
            card.innerHTML = `
                <div class="arena-card-top">
                    <span class="arena-title">${item.display_name}</span>
                    <span class="arena-badge">${item.cv_accuracy}%</span>
                </div>
                <div class="arena-canvas-wrap">
                    <canvas class="arena-canvas" width="240" height="140" id="arena-cvs-${item.kernel}"></canvas>
                </div>
                <div class="arena-stats">
                    <div class="arena-stat-box">
                        <div class="arena-stat-lbl">Độ trễ suy luận</div>
                        <div class="arena-stat-val">${item.latency_ms} ms</div>
                    </div>
                    <div class="arena-stat-box">
                        <div class="arena-stat-lbl">Support Vectors</div>
                        <div class="arena-stat-val">${item.total_support_vectors} SVs</div>
                    </div>
                </div>
                <div class="arena-math">${item.details.math_form || ''}</div>
                <div class="arena-desc"><strong>Ưu thế:</strong> ${item.details.pros || ''}</div>
            `;
            grid.appendChild(card);

            // Draw mini decision boundary
            const cvs = card.querySelector(`#arena-cvs-${item.kernel}`);
            if (cvs) renderMiniBoundary(cvs, item, isDark);
        });
    } catch (e) {
        if (grid) grid.innerHTML = '<p style="color:var(--text-sec);text-align:center;">Không thể tải dữ liệu so sánh mô hình.</p>';
    }
}

function renderMiniBoundary(canvas, item, isDark) {
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    const res = item.resolution;
    const cellW = W / res, cellH = H / res;

    const colors = isDark ? [
        'rgba(251, 113, 133, 0.22)',
        'rgba(167, 139, 250, 0.22)',
        'rgba(56, 189, 248, 0.22)'
    ] : [
        'rgba(251, 113, 133, 0.18)',
        'rgba(167, 139, 250, 0.18)',
        'rgba(56, 189, 248, 0.18)'
    ];

    // Grid cells
    for (let row = 0; row < res; row++) {
        for (let col = 0; col < res; col++) {
            const cls = item.mini_grid[row][col];
            ctx.fillStyle = colors[cls];
            ctx.fillRect(col * cellW, (res - 1 - row) * cellH, cellW + 0.5, cellH + 0.5);
        }
    }

    // Mini points
    const xRange = item.x_range, yRange = item.y_range;
    IRIS_DATA.forEach(pt => {
        const [pl, pw, cls] = pt;
        const x = ((pl - xRange[0]) / (xRange[1] - xRange[0])) * W;
        const y = H - ((pw - yRange[0]) / (yRange[1] - yRange[0])) * H;
        ctx.beginPath();
        ctx.arc(x, y, 1.8, 0, Math.PI * 2);
        ctx.fillStyle = CLASS_COLORS[cls];
        ctx.fill();
    });
}

// ================================================================
// 10. BATCH CSV PREDICTION
// ================================================================
function initBatchPrediction() {
    const dropzone = document.getElementById('csv-dropzone');
    const fileInput = document.getElementById('csv-file-input');
    const sampleLink = document.getElementById('download-sample-csv');
    const exportBtn = document.getElementById('batch-export-btn');

    if (sampleLink) sampleLink.href = `${API_BASE}/sample-csv`;

    if (dropzone && fileInput) {
        dropzone.addEventListener('click', () => fileInput.click());
        dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('dragover'); });
        dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
            if (e.dataTransfer.files.length) handleCsvFile(e.dataTransfer.files[0]);
        });
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length) handleCsvFile(e.target.files[0]);
        });
    }

    if (exportBtn) {
        exportBtn.addEventListener('click', () => {
            if (!batchPredictionsData.length) return;
            let csv = 'id,sepal_length,sepal_width,petal_length,petal_width,kernel,prediction,probability,status\n';
            batchPredictionsData.forEach(r => {
                csv += `${r.id},${r.sepal_length},${r.sepal_width},${r.petal_length},${r.petal_width},${r.kernel},${r.prediction},${r.probability},${r.status}\n`;
            });
            const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = `iris_batch_results_${Date.now()}.csv`;
            link.click();
        });
    }
}

function handleCsvFile(file) {
    const reader = new FileReader();
    reader.onload = async (e) => {
        const text = e.target.result;
        const lines = text.trim().split('\n');
        if (lines.length < 2) {
            alert('File CSV rỗng hoặc không đúng định dạng!');
            return;
        }

        const samples = [];
        for (let i = 1; i < lines.length; i++) {
            const line = lines[i].trim();
            if (!line) continue;
            const parts = line.split(',');
            if (parts.length >= 4) {
                samples.push({
                    sepal_length: parseFloat(parts[0]) || 5.0,
                    sepal_width: parseFloat(parts[1]) || 3.0,
                    petal_length: parseFloat(parts[2]) || 1.5,
                    petal_width: parseFloat(parts[3]) || 0.2,
                    kernel: (parts[4] ? parts[4].trim() : 'rbf') || 'rbf'
                });
            }
        }

        if (!samples.length) {
            alert('Không tìm thấy dòng dữ liệu hợp lệ trong file CSV!');
            return;
        }

        try {
            const res = await fetch(`${API_BASE}/predict-batch`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + authToken },
                body: JSON.stringify({ samples })
            });

            if (!res.ok) throw new Error();
            const data = await res.json();
            batchPredictionsData = data.predictions;
            renderBatchTable(data.predictions);
        } catch (err) {
            alert('Đã xảy ra lỗi khi gửi dữ liệu hàng loạt lên máy chủ.');
        }
    };
    reader.readAsText(file);
}

function renderBatchTable(rows) {
    const wrap = document.getElementById('batch-results-wrap');
    const tbody = document.getElementById('batch-body');
    const badge = document.getElementById('batch-count-badge');
    if (!wrap || !tbody) return;

    wrap.style.display = 'block';
    if (badge) badge.textContent = `Đã phân loại ${rows.length} mẫu`;

    const statusPills = {
        'Tin cậy cao': 'status-pill high',
        'Tin cậy khá': 'status-pill mid',
        'Vùng bất định': 'status-pill low'
    };

    tbody.innerHTML = rows.map(r => `
        <tr>
            <td><strong>#${r.id}</strong></td>
            <td>${r.sepal_length}</td>
            <td>${r.sepal_width}</td>
            <td>${r.petal_length}</td>
            <td>${r.petal_width}</td>
            <td><span style="font-size:.72rem;font-weight:700;text-transform:uppercase;">${r.kernel}</span></td>
            <td><span class="sp-badge ${r.prediction}">${r.prediction}</span></td>
            <td><strong>${r.probability}%</strong></td>
            <td><span class="${statusPills[r.status] || 'status-pill'}">${r.status}</span></td>
        </tr>
    `).join('');
}

// ================================================================
// 11. DATASET INFO ANIMATION
// ================================================================
function animateNumbers() {
    document.querySelectorAll('.info-num').forEach(num => {
        const target = parseInt(num.dataset.count);
        let start = 0;
        const step = Math.max(1, target / 60);
        num.textContent = '0';
        const update = () => {
            start += step;
            if (start < target) { num.textContent = Math.floor(start); requestAnimationFrame(update); }
            else num.textContent = target;
        };
        requestAnimationFrame(update);
    });
}

// ================================================================
// 12. PREDICTION HISTORY (from Database API)
// ================================================================
async function loadHistoryFromDB() {
    try {
        const res = await fetch(`${API_BASE}/predictions?limit=50`, { headers: { 'Authorization': 'Bearer ' + authToken } });
        if (res.status === 401) {
            const identityValid = await isIdentityTokenValid();
            if (identityValid === false) {
                if (window.triggerLogout) window.triggerLogout();
            } else if (identityValid === true) {
                renderHistoryTable([]);
                const empty = document.getElementById('hist-empty');
                if (empty) {
                    empty.textContent = 'Không tải được lịch sử: Iris API từ chối JWT. Kiểm tra JWT_SECRET và CLIENT_ID trên Render.';
                    empty.style.display = 'block';
                }
                showApiAuthConfigurationError();
            }
            // Nếu IdP tạm thời không phản hồi, giữ nguyên phiên và cho phép thử lại.
            return;
        }
        if (!res.ok) throw new Error();
        const history = await res.json();
        renderHistoryTable(history);
    } catch {
        renderHistoryTable([]);
    }
}

function renderHistoryTable(history) {
    historyData = Array.isArray(history) ? history : [];
    const tbody = document.getElementById('hist-body');
    const empty = document.getElementById('hist-empty');
    if (!tbody || !empty) return;

    if (history.length === 0) {
        tbody.innerHTML = '';
        empty.style.display = 'block';
        return;
    }

    empty.style.display = 'none';
    tbody.innerHTML = history.map((h, i) => {
        const dt = new Date(h.created_at);
        const timeStr = isNaN(dt.getTime())
            ? (h.created_at || '—')
            : dt.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });

        return `
            <tr data-id="${h.id}">
                <td>${i + 1}</td>
                <td><span style="font-size:0.8rem;color:var(--primary);font-weight:600">@${h.username || 'unknown'}</span></td>
                <td>${h.sepal_length.toFixed(1)}</td>
                <td>${h.sepal_width.toFixed(1)}</td>
                <td>${h.petal_length.toFixed(1)}</td>
                <td>${h.petal_width.toFixed(1)}</td>
                <td><span style="font-size:.75rem;font-weight:600;color:var(--text-sec);text-transform:uppercase">${h.kernel || 'rbf'}</span></td>
                <td><span class="sp-badge ${h.prediction}">${h.prediction}</span></td>
                <td><strong>${(h.probability * 100).toFixed(1)}%</strong></td>
                <td style="font-size:.74rem;color:var(--text-sec)">${timeStr}</td>
            </tr>
        `;
    }).join('');

    tbody.querySelectorAll('tr').forEach(row => {
        row.addEventListener('click', () => {
            const id = parseInt(row.dataset.id);
            const h = history.find(x => x.id === id);
            if (!h) return;
            FEATURES.forEach(f => setFeatureValue(f.key, h[f.api]));

            const kSel = document.getElementById('kernel-select');
            if (kSel) { kSel.value = h.kernel || 'rbf'; updateKernelInfo(); }

            highlightCard(h.prediction, h.probability);
            showBotanical(h.prediction, h.probability, h.kernel);
            drawRadar();
            drawScatter();

            document.querySelector('.tab-btn[data-tab="predict"]')?.click();
        });
    });
}

function initClearHistory() {
    const btn = document.getElementById('clear-history-btn');
    if (!btn) return;
    btn.addEventListener('click', async () => {
        if (!confirm('Xóa toàn bộ lịch sử dự đoán trong database?')) return;
        try { await fetch(`${API_BASE}/predictions`, { method: 'DELETE', headers: { 'Authorization': 'Bearer ' + authToken } }); } catch { }
        currentPrediction = null;
        SPECIES_NAMES.forEach(s => {
            document.getElementById(`card-${s}`)?.classList.remove('highlighted', 'dimmed');
        });
        const bot = document.getElementById('botanical-panel');
        if (bot) bot.hidden = true;
        const xai = document.getElementById('xai-panel');
        if (xai) xai.hidden = true;
    });
}

// ================================================================
// 13. EXPORTS & EFFECTS
// ================================================================
function initExportExcel() {
    const btn = document.getElementById('export-excel-btn');
    if (btn) {
        btn.addEventListener('click', async () => {
            try {
                const res = await fetch(`${API_BASE}/predictions/export`, { headers: { 'Authorization': 'Bearer ' + authToken } });
                if (!res.ok) throw new Error('Failed to export');
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'iris_predictions.xlsx';
                a.click();
                URL.revokeObjectURL(url);
            } catch (e) {
                console.error(e);
            }
        });
    }
}

function initExportImage() {
    const btn = document.getElementById('export-btn');
    if (!btn) return;
    btn.addEventListener('click', () => {
        const canvas = document.createElement('canvas');
        canvas.width = 600; canvas.height = 400;
        const ctx = canvas.getContext('2d');
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        const styles = getComputedStyle(document.body);

        ctx.fillStyle = isDark ? '#12091a' : '#fdf6f0';
        ctx.fillRect(0, 0, 600, 400);

        ctx.fillStyle = isDark ? styles.getPropertyValue('--c5').trim() : styles.getPropertyValue('--c1').trim();
        ctx.font = 'bold 20px Inter, sans-serif'; ctx.textAlign = 'center';
        ctx.fillText('🌸 Iris AI Explorer — Lịch sử Dự đoán', 300, 35);

        ctx.fillStyle = isDark ? '#a08aaa' : '#6e5570';
        ctx.font = '11px Inter, sans-serif'; ctx.textAlign = 'center';
        ctx.fillText('Đồ án Học máy Nâng cao • 2026 • Nguyễn Xuân Phúc', 300, 380);

        const link = document.createElement('a');
        link.download = `iris-history-${Date.now()}.png`;
        link.href = canvas.toDataURL('image/png');
        link.click();
    });
}

function initCursorGlow() {
    const glow = document.getElementById('cursor-glow');
    if (!glow) return;
    document.addEventListener('mousemove', (e) => {
        glow.style.left = e.clientX + 'px'; glow.style.top = e.clientY + 'px';
        if (!glow.classList.contains('active')) glow.classList.add('active');
    });
    document.addEventListener('mouseleave', () => glow.classList.remove('active'));
}

function initMagneticCards() {
    document.querySelectorAll('.magnetic-card').forEach(card => {
        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const rotY = ((e.clientX - rect.left - rect.width / 2) / (rect.width / 2)) * 8;
            const rotX = ((rect.height / 2 - (e.clientY - rect.top)) / (rect.height / 2)) * 8;
            card.style.transform = `perspective(600px) rotateX(${rotX}deg) rotateY(${rotY}deg) scale(1.02)`;
        });
        card.addEventListener('mouseleave', () => {
            if (card.classList.contains('highlighted')) card.style.transform = 'scale(1.04)';
            else if (card.classList.contains('dimmed')) card.style.transform = 'scale(0.98)';
            else card.style.transform = 'perspective(600px) rotateX(0) rotateY(0) scale(1)';
        });
    });
}

function initRippleButtons() {
    document.querySelectorAll('.ripple-btn').forEach(btn => {
        btn.addEventListener('click', function (e) {
            const rect = this.getBoundingClientRect();
            const ripple = document.createElement('span');
            ripple.classList.add('ripple');
            const size = Math.max(rect.width, rect.height);
            ripple.style.width = ripple.style.height = size + 'px';
            ripple.style.left = (e.clientX - rect.left - size / 2) + 'px';
            ripple.style.top = (e.clientY - rect.top - size / 2) + 'px';
            this.appendChild(ripple);
            ripple.addEventListener('animationend', () => ripple.remove());
        });
    });
}

function initPetals() {
    const container = document.getElementById('petals-container');
    if (!container) return;
    for (let i = 0; i < 12; i++) {
        const petal = document.createElement('div');
        petal.classList.add('petal');
        petal.style.left = `${Math.random() * 100}%`;
        petal.style.animationDuration = `${8 + Math.random() * 8}s`;
        petal.style.animationDelay = `${Math.random() * 5}s`;
        container.appendChild(petal);
    }
}

function triggerConfetti(species) {
    const colors = { setosa: ['#fb7185', '#fda4af'], versicolor: ['#a78bfa', '#c4b5fd'], virginica: ['#38bdf8', '#7dd3fc'] };
    const palette = colors[species] || ['#ba86a6', '#593e67'];
    for (let i = 0; i < 24; i++) {
        const dot = document.createElement('div');
        dot.style.position = 'fixed';
        dot.style.width = '7px'; dot.style.height = '7px';
        dot.style.borderRadius = '50%';
        dot.style.background = palette[i % palette.length];
        dot.style.left = `${40 + Math.random() * 20}%`;
        dot.style.top = '40%';
        dot.style.pointerEvents = 'none';
        dot.style.zIndex = '999';
        dot.style.transition = 'all 1s cubic-bezier(0.2, 0.8, 0.2, 1)';
        document.body.appendChild(dot);

        requestAnimationFrame(() => {
            const angle = Math.random() * Math.PI * 2;
            const dist = 70 + Math.random() * 120;
            dot.style.transform = `translate(${Math.cos(angle) * dist}px, ${Math.sin(angle) * dist}px) scale(0)`;
            dot.style.opacity = '0';
        });
        setTimeout(() => dot.remove(), 1050);
    }
}

// ================================================================
// 14. API HEALTH CHECK
// ================================================================
function setApiStatus(status, label) {
    const el = document.getElementById('api-status');
    const labelEl = document.getElementById('status-label');
    if (!el || !labelEl) return;
    el.classList.remove('online', 'offline', 'warming');
    el.classList.add(status);
    labelEl.textContent = label;
}

async function checkApiHealth() {
    setApiStatus('warming', 'Đang kết nối...');
    for (let i = 1; i <= 4; i++) {
        try {
            const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(15000) });
            if (res.ok) { setApiStatus('online', 'API sẵn sàng'); return; }
        } catch { }
        if (i < 4) await new Promise(r => setTimeout(r, 3000 * i));
    }
    setApiStatus('offline', 'API đang bảo trì');
}


// ================================================================
// QUẢN TRỊ HỆ THỐNG (CHỦ SỞ HỮU)
// ================================================================
function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function formatDateTime(isoStr) {
    if (!isoStr) return '<span style="color:var(--text-sec);font-style:italic;">Chưa đăng nhập</span>';
    try {
        const d = new Date(isoStr);
        if (isNaN(d.getTime())) return isoStr;
        return d.toLocaleString('vi-VN', {
            hour: '2-digit', minute: '2-digit', second: '2-digit',
            day: '2-digit', month: '2-digit', year: 'numeric'
        });
    } catch (e) {
        return isoStr;
    }
}

async function loadAdminData() {
    if (!authToken || !isOwner) return;

    const usersTbody = document.getElementById('admin-users-tbody');
    const predsTbody = document.getElementById('admin-preds-tbody');
    const userCountEl = document.getElementById('admin-user-count');
    const predCountEl = document.getElementById('admin-pred-count');

    // 1. Tải danh sách người dùng (qua fetchAuth với fallback)
    try {
        const resUsers = await fetchAuth('/admin/users', {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        if (resUsers.ok) {
            const users = await resUsers.json();
            if (userCountEl) userCountEl.textContent = `${users.length} tài khoản`;
            if (usersTbody) {
                if (users.length === 0) {
                    usersTbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-sec);padding:16px;">Chưa có tài khoản nào.</td></tr>';
                } else {
                    usersTbody.innerHTML = users.map(u => `
                        <tr style="${u.is_owner ? 'background: rgba(245, 158, 11, 0.08);' : ''}">
                            <td style="font-family: monospace; font-weight: 600;">#${u.id}</td>
                            <td style="font-weight: 500;">
                                ${escapeHtml(u.email)}
                                ${u.is_owner ? ' <span style="background:#f59e0b;color:#000;padding:2px 6px;border-radius:4px;font-size:0.7rem;font-weight:bold;margin-left:4px;">Chủ sở hữu</span>' : ''}
                            </td>
                            <td>
                                ${u.is_owner
                            ? '<span style="color:#f59e0b;font-weight:600;">👑 Chủ sở hữu (Cố định)</span>'
                            : '<span style="color:var(--text-sec);">Người dùng</span>'}
                            </td>
                            <td>${formatDateTime(u.created_at)}</td>
                            <td>${formatDateTime(u.last_login_at)}</td>
                        </tr>
                    `).join('');
                }
            }
        } else if (resUsers.status === 401 || resUsers.status === 403) {
            if (usersTbody) usersTbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#ef4444;padding:16px;">Không có quyền truy cập dữ liệu quản trị.</td></tr>';
        }
    } catch (err) {
        console.error('Error loading admin users:', err);
        if (usersTbody) usersTbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#ef4444;padding:16px;">Lỗi kết nối tới Identity Service.</td></tr>';
    }

    // 2. Tải lịch sử dự đoán toàn hệ thống (BẢO MẬT: KHÔNG HIỆN USERNAME)
    try {
        const resPreds = await fetch(`${API_BASE}/admin/predictions?limit=100`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        if (resPreds.ok) {
            const preds = await resPreds.json();
            if (predCountEl) predCountEl.textContent = `${preds.length} lượt dự đoán`;
            if (predsTbody) {
                if (preds.length === 0) {
                    predsTbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text-sec);padding:16px;">Chưa có lượt dự đoán nào trên hệ thống.</td></tr>';
                } else {
                    predsTbody.innerHTML = preds.map(p => {
                        const badgeColor = p.prediction === 'Iris setosa' ? '#fb7185' : (p.prediction === 'Iris versicolor' ? '#a78bfa' : '#38bdf8');
                        return `
                            <tr>
                                <td style="font-family: monospace; font-weight: 600;">#${p.id}</td>
                                <td style="color: var(--text-primary); font-weight: 500;">${formatDateTime(p.created_at)}</td>
                                <td><span style="font-family: monospace; background: var(--bg-card); padding: 2px 6px; border-radius: 4px; border: 1px solid var(--border-color);">${escapeHtml(p.kernel)}</span></td>
                                <td>
                                    <span style="display:inline-flex; align-items:center; gap:6px;">
                                        <span style="width:8px; height:8px; border-radius:50%; background:${badgeColor}; display:inline-block;"></span>
                                        <strong style="color:${badgeColor};">${escapeHtml(p.prediction)}</strong>
                                    </span>
                                </td>
                                <td><strong>${p.probability}%</strong></td>
                                <td style="color:var(--text-sec); font-size:0.85rem;">${escapeHtml(p.model_version || 'v1.0')}</td>
                            </tr>
                        `;
                    }).join('');
                }
            }
        } else if (resPreds.status === 401 || resPreds.status === 403) {
            if (predsTbody) predsTbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#ef4444;padding:16px;">Không có quyền truy cập nhật ký dự đoán.</td></tr>';
        }
    } catch (err) {
        console.error('Error loading admin predictions:', err);
        if (predsTbody) predsTbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#ef4444;padding:16px;">Lỗi kết nối tới Iris Backend API.</td></tr>';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const refreshBtn = document.getElementById('admin-refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            refreshBtn.disabled = true;
            refreshBtn.textContent = '⏳ Đang tải...';
            loadAdminData().finally(() => {
                refreshBtn.disabled = false;
                refreshBtn.textContent = '🔄 Làm mới dữ liệu';
            });
        });
    }
});

// ─── Profile Tab View Updater ───
function updateProfileView() {
    if (!authToken) return;
    const email = currentUsername || 'user@example.com';
    const emailDisplay = document.getElementById('profile-email-display');
    const infoEmail = document.getElementById('profile-info-email');
    const avatarChar = document.getElementById('profile-avatar-char');
    const roleBadge = document.getElementById('profile-role-badge');
    const infoRole = document.getElementById('profile-info-role');
    const infoId = document.getElementById('profile-info-id');
    const infoPreds = document.getElementById('profile-info-preds');

    if (emailDisplay) emailDisplay.textContent = email;
    if (infoEmail) infoEmail.textContent = email;

    if (avatarChar) {
        const firstChar = email.trim().charAt(0).toUpperCase();
        avatarChar.textContent = firstChar || '👤';
    }

    const payload = parseJwtPayload(authToken);
    const userId = payload?.sub || '1';
    if (infoId) infoId.textContent = `#${userId}`;

    if (isOwner) {
        if (roleBadge) {
            roleBadge.textContent = '👑 Chủ sở hữu';
            roleBadge.classList.add('owner');
        }
        if (infoRole) infoRole.textContent = 'Chủ sở hữu hệ thống (Toàn quyền)';
    } else {
        if (roleBadge) {
            roleBadge.textContent = '👤 Người dùng';
            roleBadge.classList.remove('owner');
        }
        if (infoRole) infoRole.textContent = 'Người dùng tiêu chuẩn';
    }

    if (infoPreds) {
        const count = Array.isArray(historyData) ? historyData.length : 0;
        infoPreds.textContent = `${count} lượt`;
    }
}

// ================================================================
// 10. TÍNH NĂNG ĐỘT PHÁ 1: BOTANICAL ANATOMY SVG INTERACTION
// ================================================================
function initBotanicalAnatomy() {
    updateBotanicalAnatomyValues();

    const sepalGroup = document.getElementById('anat-sepal-group');
    const petalGroup = document.getElementById('anat-petal-group');
    const sepalPill = document.querySelector('.sepal-pill');
    const petalPill = document.querySelector('.petal-pill');

    const sepalInputs = ['inp-sepal-length', 'rng-sepal-length', 'inp-sepal-width', 'rng-sepal-width'];
    const petalInputs = ['inp-petal-length', 'rng-petal-length', 'inp-petal-width', 'rng-petal-width'];

    const setSepalActive = (active) => {
        if (sepalGroup) sepalGroup.classList.toggle('anat-active', active);
        if (sepalPill) sepalPill.classList.toggle('active', active);
    };

    const setPetalActive = (active) => {
        if (petalGroup) petalGroup.classList.toggle('anat-active', active);
        if (petalPill) petalPill.classList.toggle('active', active);
    };

    sepalInputs.forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        el.addEventListener('mouseenter', () => setSepalActive(true));
        el.addEventListener('mouseleave', () => setSepalActive(false));
        el.addEventListener('focus', () => setSepalActive(true));
        el.addEventListener('blur', () => setSepalActive(false));
    });

    petalInputs.forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        el.addEventListener('mouseenter', () => setPetalActive(true));
        el.addEventListener('mouseleave', () => setPetalActive(false));
        el.addEventListener('focus', () => setPetalActive(true));
        el.addEventListener('blur', () => setPetalActive(false));
    });

    // Clicking parts in SVG focuses corresponding sliders
    if (sepalGroup) {
        sepalGroup.addEventListener('click', () => {
            const rng = document.getElementById('rng-sepal-length');
            if (rng) { rng.focus(); rng.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
        });
    }
    if (petalGroup) {
        petalGroup.addEventListener('click', () => {
            const rng = document.getElementById('rng-petal-length');
            if (rng) { rng.focus(); rng.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
        });
    }
}

function updateBotanicalAnatomyValues() {
    const sl = document.getElementById('inp-sepal-length')?.value || '5.1';
    const sw = document.getElementById('inp-sepal-width')?.value || '3.5';
    const pl = document.getElementById('inp-petal-length')?.value || '1.4';
    const pw = document.getElementById('inp-petal-width')?.value || '0.2';

    const slEl = document.getElementById('anat-sl-val');
    const swEl = document.getElementById('anat-sw-val');
    const plEl = document.getElementById('anat-pl-val');
    const pwEl = document.getElementById('anat-pw-val');

    if (slEl) slEl.textContent = sl;
    if (swEl) swEl.textContent = sw;
    if (plEl) plEl.textContent = pl;
    if (pwEl) pwEl.textContent = pw;
}

// ================================================================
// 11. TÍNH NĂNG ĐỘT PHÁ 2: 3D PCA SPACE (XOAY 360 ĐỘ)
// ================================================================
let currentPcaData = null;

function initPca3D() {
    const select = document.getElementById('pca-kernel-select');
    if (select) {
        select.addEventListener('change', () => loadPca3D(select.value));
    }
    const resetBtn = document.getElementById('pca-reset-view-btn');
    if (resetBtn) {
        resetBtn.addEventListener('click', () => {
            if (window.Plotly && document.getElementById('pca-3d-plot')) {
                Plotly.relayout('pca-3d-plot', {
                    'scene.camera': {
                        eye: { x: 1.6, y: 1.6, z: 1.2 }
                    }
                });
            }
        });
    }
}

async function loadPca3D(kernel = 'rbf') {
    const container = document.getElementById('pca-3d-plot');
    if (!container) return;

    const sl = parseFloat(document.getElementById('inp-sepal-length')?.value || '5.1');
    const sw = parseFloat(document.getElementById('inp-sepal-width')?.value || '3.5');
    const pl = parseFloat(document.getElementById('inp-petal-length')?.value || '1.4');
    const pw = parseFloat(document.getElementById('inp-petal-width')?.value || '0.2');

    try {
        const res = await fetch(`${API_BASE}/pca-3d?kernel=${kernel}&user_sl=${sl}&user_sw=${sw}&user_pl=${pl}&user_pw=${pw}`);
        if (!res.ok) throw new Error('Không thể tải dữ liệu PCA 3D');
        const data = await res.json();
        currentPcaData = data;

        // Update variance badges
        const v = data.explained_variance_ratio || [92.46, 5.31, 1.71];
        const pc1 = document.getElementById('pca-var-pc1');
        const pc2 = document.getElementById('pca-var-pc2');
        const pc3 = document.getElementById('pca-var-pc3');
        const total = document.getElementById('pca-var-total');
        if (pc1) pc1.textContent = `PC1: ${v[0]}% (Cánh hoa)`;
        if (pc2) pc2.textContent = `PC2: ${v[1]}% (Đài hoa)`;
        if (pc3) pc3.textContent = `PC3: ${v[2]}% (Vi sai)`;
        if (total) total.textContent = `⭐ Tổng bảo toàn: ${data.total_explained_variance || 99.48}%`;

        renderPlotly3D(data);
    } catch (err) {
        console.warn('Lỗi tải PCA 3D:', err);
    }
}

function renderPlotly3D(data) {
    const container = document.getElementById('pca-3d-plot');
    if (!container) return;

    if (!window.Plotly) {
        // Fallback: load Plotly script dynamically if not yet ready
        const script = document.createElement('script');
        script.src = 'https://cdn.plot.ly/plotly-2.27.0.min.js';
        script.onload = () => renderPlotly3D(data);
        document.head.appendChild(script);
        return;
    }

    const speciesNames = ['setosa', 'versicolor', 'virginica'];
    const speciesDisplay = ['Iris setosa', 'Iris versicolor', 'Iris virginica'];
    const speciesColors = ['#fb7185', '#a78bfa', '#38bdf8'];

    const traces = speciesNames.map((sp, idx) => {
        const pts = data.points.filter(p => p.class_id === idx);
        return {
            name: speciesDisplay[idx],
            x: pts.map(p => p.x),
            y: pts.map(p => p.y),
            z: pts.map(p => p.z),
            mode: 'markers',
            type: 'scatter3d',
            text: pts.map(p => `${speciesDisplay[idx]}<br>SL: ${p.features[0]} cm | SW: ${p.features[1]} cm<br>PL: ${p.features[2]} cm | PW: ${p.features[3]} cm${p.is_support_vector ? '<br>⚡ Support Vector' : ''}`),
            hoverinfo: 'text',
            marker: {
                size: pts.map(p => p.is_support_vector ? 7 : 4.5),
                color: speciesColors[idx],
                opacity: 0.88,
                line: {
                    color: pts.map(p => p.is_support_vector ? '#fbbf24' : 'rgba(255,255,255,0.4)'),
                    width: pts.map(p => p.is_support_vector ? 2.5 : 0.8)
                }
            }
        };
    });

    // User projected point trace
    if (data.user_projection) {
        const u = data.user_projection;
        traces.push({
            name: '⭐ Điểm bạn chọn',
            x: [u.x],
            y: [u.y],
            z: [u.z],
            mode: 'markers+text',
            type: 'scatter3d',
            text: ['⭐ MẪU HIỆN TẠI'],
            textposition: 'top center',
            hoverinfo: 'text',
            hovertext: [`Mẫu bạn chọn<br>SL: ${u.features[0]} cm | SW: ${u.features[1]} cm<br>PL: ${u.features[2]} cm | PW: ${u.features[3]} cm`],
            marker: {
                size: 13,
                color: '#f59e0b',
                symbol: 'diamond',
                line: { color: '#ffffff', width: 2.5 }
            }
        });
    }

    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const textColor = isDark ? '#f1f5f9' : '#1e293b';
    const gridColor = isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.08)';

    const layout = {
        margin: { l: 0, r: 0, b: 0, t: 0 },
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        showlegend: true,
        legend: {
            x: 0,
            y: 1,
            font: { family: 'Inter', color: textColor, size: 11 },
            bgcolor: 'rgba(0,0,0,0)'
        },
        scene: {
            xaxis: { title: 'PC1 (92.5%)', color: textColor, gridcolor: gridColor, zerolinecolor: gridColor },
            yaxis: { title: 'PC2 (5.3%)', color: textColor, gridcolor: gridColor, zerolinecolor: gridColor },
            zaxis: { title: 'PC3 (1.7%)', color: textColor, gridcolor: gridColor, zerolinecolor: gridColor },
            camera: { eye: { x: 1.6, y: 1.6, z: 1.2 } },
            aspectmode: 'cube'
        }
    };

    Plotly.newPlot(container, traces, layout, { responsive: true, displayModeBar: false });
}

// ================================================================
// 12. TÍNH NĂNG ĐỘT PHÁ 3: STRESS-TEST & OUTLIER SIMULATOR
// ================================================================
function initStressTest() {
    const noiseRng = document.getElementById('stress-noise-rng');
    const noiseVal = document.getElementById('stress-noise-val');
    if (noiseRng && noiseVal) {
        noiseRng.addEventListener('input', () => {
            noiseVal.textContent = `${Math.round(parseFloat(noiseRng.value) * 100)}%`;
        });
    }

    const outRng = document.getElementById('stress-outliers-rng');
    const outVal = document.getElementById('stress-outliers-val');
    if (outRng && outVal) {
        outRng.addEventListener('input', () => {
            outVal.textContent = `${outRng.value} mẫu`;
        });
    }

    const runBtn = document.getElementById('run-stress-test-btn');
    if (runBtn) {
        runBtn.addEventListener('click', runStressTest);
    }
}

async function runStressTest() {
    const runBtn = document.getElementById('run-stress-test-btn');
    const grid = document.getElementById('stress-results-grid');
    if (!grid) return;

    const noise = parseFloat(document.getElementById('stress-noise-rng')?.value || '0.15');
    const outliers = parseInt(document.getElementById('stress-outliers-rng')?.value || '2', 10);

    if (runBtn) {
        runBtn.disabled = true;
        runBtn.textContent = '⏳ Đang phân tích...';
    }
    grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:2rem;color:var(--text-sec);">Đang mô phỏng nhiễu Gauss và đánh giá 4 mô hình SVM...</div>';

    try {
        const res = await fetch(`${API_BASE}/stress-test?noise_level=${noise}&outliers=${outliers}&seed=42`);
        if (!res.ok) throw new Error('Không thể chạy thử nghiệm');
        const data = await res.json();

        const kernelColors = {
            linear: '#3b82f6',
            rbf: '#10b981',
            poly: '#a855f7',
            sigmoid: '#f59e0b'
        };

        grid.innerHTML = data.results.map(r => {
            const color = kernelColors[r.kernel] || '#6366f1';
            const scoreColor = r.robustness_score >= 80 ? '#10b981' : (r.robustness_score >= 60 ? '#f59e0b' : '#ef4444');
            return `
                <div class="stress-card">
                    <div class="stress-card-header">
                        <strong style="text-transform:uppercase; font-size:1rem; color:${color};">${r.kernel}</strong>
                        <span class="xai-badge" style="background:${scoreColor}22; color:${scoreColor}; font-weight:700;">
                            Kháng nhiễu: ${r.robustness_score}/100
                        </span>
                    </div>
                    <div class="robustness-meter">
                        <div class="robustness-fill" style="width:${r.robustness_score}%; background:${scoreColor};"></div>
                    </div>
                    <div style="font-size:0.8rem; line-height:1.6; margin:0.6rem 0;">
                        <div>Độ chính xác gốc: <strong>${r.accuracy_on_clean}%</strong></div>
                        <div>Độ chính xác sau nhiễu: <strong style="color:${scoreColor};">${r.accuracy_on_noisy}%</strong></div>
                        <div>Số Support Vectors: <strong>${r.support_vectors}</strong> điểm</div>
                    </div>
                    <p style="font-size:0.75rem; color:var(--text-sec); margin:0.4rem 0 0 0; line-height:1.4; border-top:1px dashed var(--glass-border); padding-top:0.4rem;">
                        💡 ${r.diagnosis}
                    </p>
                </div>
            `;
        }).join('');
    } catch (err) {
        grid.innerHTML = `<div style="grid-column:1/-1;text-align:center;padding:1.5rem;color:#ef4444;">Lỗi khi chạy thử nghiệm: ${err.message}</div>`;
    } finally {
        if (runBtn) {
            runBtn.disabled = false;
            runBtn.textContent = '📊 Chạy Thử Nghiệm Kháng Nhiễu';
        }
    }
}

// ================================================================
// 13. TÍNH NĂNG ĐỘT PHÁ 4: KKT & LAGRANGE MULTIPLIERS INSPECTOR
// ================================================================
function initKktInspector() {
    const select = document.getElementById('kkt-kernel-select');
    if (select) {
        select.addEventListener('change', () => loadKktSupportVectors(select.value));
    }
}

async function loadKktSupportVectors(kernel = 'rbf') {
    const tbody = document.getElementById('kkt-sv-tbody');
    if (!tbody) return;

    try {
        const res = await fetch(`${API_BASE}/support-vectors?kernel=${kernel}`);
        if (!res.ok) throw new Error('Không thể tải dữ liệu KKT');
        const data = await res.json();

        const kkt = data.kkt_analysis || {};
        const cVal = document.getElementById('kkt-c-val');
        const freeCount = document.getElementById('kkt-free-count');
        const freePct = document.getElementById('kkt-free-pct');
        const boundedCount = document.getElementById('kkt-bounded-count');
        const boundedPct = document.getElementById('kkt-bounded-pct');

        if (cVal) cVal.textContent = kkt.C || '1.0';
        if (freeCount) freeCount.textContent = `${kkt.free_sv_count || 0} SVs`;
        if (freePct) freePct.textContent = `${kkt.free_sv_pct || 0}% (Chuẩn trên Margin)`;
        if (boundedCount) boundedCount.textContent = `${kkt.bounded_sv_count || 0} SVs`;
        if (boundedPct) boundedPct.textContent = `${kkt.bounded_sv_pct || 0}% (Lọt vào Margin/Vi phạm)`;

        const speciesColors = { setosa: '#fb7185', versicolor: '#a78bfa', virginica: '#38bdf8' };

        tbody.innerHTML = (data.support_vectors || []).map(sv => {
            const color = speciesColors[sv.species] || '#a78bfa';
            const badgeClass = sv.is_bounded ? 'kkt-badge-bounded' : 'kkt-badge-free';
            const badgeLabel = sv.is_bounded ? 'Bounded (α = C)' : 'Free (0 < α < C)';
            return `
                <tr>
                    <td>#${sv.index}</td>
                    <td><span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:${color}; margin-right:4px;"></span>${sv.species}</td>
                    <td>${sv.sepal_length}</td>
                    <td>${sv.sepal_width}</td>
                    <td>${sv.petal_length}</td>
                    <td>${sv.petal_width}</td>
                    <td><strong style="color:var(--text);">${sv.alpha || '--'}</strong></td>
                    <td><span class="kkt-badge ${badgeClass}">${badgeLabel}</span></td>
                </tr>
            `;
        }).join('');
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:1.5rem; color:#ef4444;">Lỗi tải dữ liệu: ${err.message}</td></tr>`;
    }
}

// ================================================================
// 14. TÍNH NĂNG ĐỘT PHÁ 5: PHIẾU THẨM ĐỊNH MẪU (AUDIT CERTIFICATE)
// ================================================================
function initCertificateModal() {
    const openBtn = document.getElementById('open-certificate-btn');
    const modal = document.getElementById('certificate-modal');
    const closeBtn = document.getElementById('close-certificate-btn');
    const backdrop = document.getElementById('certificate-backdrop');
    const printBtn = document.getElementById('print-certificate-btn');

    const closeModal = () => {
        if (modal) {
            modal.hidden = true;
            modal.style.display = 'none';
            modal.classList.remove('show');
        }
    };

    if (openBtn) {
        openBtn.addEventListener('click', openInspectionCertificate);
    }
    if (closeBtn) {
        closeBtn.addEventListener('click', closeModal);
    }
    if (backdrop) {
        backdrop.addEventListener('click', closeModal);
    }
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && modal && modal.style.display !== 'none') {
            closeModal();
        }
    });
    if (printBtn) {
        printBtn.addEventListener('click', () => window.print());
    }
}

async function openInspectionCertificate() {
    const modal = document.getElementById('certificate-modal');
    if (!modal) return;

    const sl = document.getElementById('inp-sepal-length')?.value || '5.1';
    const sw = document.getElementById('inp-sepal-width')?.value || '3.5';
    const pl = document.getElementById('inp-petal-length')?.value || '1.4';
    const pw = document.getElementById('inp-petal-width')?.value || '0.2';
    const kernel = document.getElementById('kernel-select')?.value || 'rbf';

    const predName = document.getElementById('bot-name')?.textContent || 'Iris setosa';
    const probText = document.getElementById('bot-prob')?.textContent || '99.4%';
    const descText = document.getElementById('bot-desc')?.textContent || 'Đặc trưng bởi cánh hoa ngắn, màu sắc rực rỡ.';

    // Fill table
    const cfSl = document.getElementById('cf-sl');
    const cfSw = document.getElementById('cf-sw');
    const cfPl = document.getElementById('cf-pl');
    const cfPw = document.getElementById('cf-pw');
    if (cfSl) cfSl.textContent = sl;
    if (cfSw) cfSw.textContent = sw;
    if (cfPl) cfPl.textContent = pl;
    if (cfPw) cfPw.textContent = pw;

    // References
    const cfrSl = document.getElementById('cfr-sl');
    const cfrSw = document.getElementById('cfr-sw');
    const cfrPl = document.getElementById('cfr-pl');
    const cfrPw = document.getElementById('cfr-pw');
    if (cfrSl) cfrSl.textContent = '4.3 – 5.8 cm';
    if (cfrSw) cfrSw.textContent = '2.3 – 4.4 cm';
    if (cfrPl) cfrPl.textContent = '1.0 – 1.9 cm';
    if (cfrPw) cfrPw.textContent = '0.1 – 0.6 cm';

    // Summary metadata
    const certCode = document.getElementById('cert-code');
    const certDate = document.getElementById('cert-date');
    const certSpecies = document.getElementById('cert-species-name');
    const certDesc = document.getElementById('cert-species-desc');
    const certProb = document.getElementById('cert-prob-val');
    const certKernel = document.getElementById('cert-kernel-val');
    const certModelVer = document.getElementById('cert-model-ver');
    const certHash = document.getElementById('cert-hash-val');

    const now = new Date();
    const formattedDate = now.toLocaleDateString('vi-VN') + ' ' + now.toLocaleTimeString('vi-VN');
    const randHex = Math.floor(Math.random() * 0xffffff).toString(16).toUpperCase().padStart(6, '0');

    if (certCode) certCode.textContent = `IRIS-SVM-2026-${randHex}`;
    if (certDate) certDate.textContent = formattedDate;
    if (certSpecies) certSpecies.textContent = predName.toUpperCase();
    if (certDesc) certDesc.textContent = descText;
    if (certProb) certProb.textContent = probText;
    if (certKernel) certKernel.textContent = `${kernel.toUpperCase()} Kernel`;
    if (certModelVer) certModelVer.textContent = 'v2.1.0 (Production)';

    // Generate SHA-256 integrity hash
    const rawString = `${sl}|${sw}|${pl}|${pw}|${kernel}|${formattedDate}|Nguyễn Xuân Phúc`;
    try {
        const msgBuffer = new TextEncoder().encode(rawString);
        const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer);
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
        if (certHash) certHash.textContent = hashHex;
    } catch (e) {
        if (certHash) certHash.textContent = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855';
    }

    modal.hidden = false;
    modal.style.display = 'flex';
    modal.classList.add('show');
}

// ================================================================
// 15. TÍNH NĂNG ĐỘT PHÁ 6: GUIDED TOUR (THAM QUAN ĐỒ ÁN CÓ THUYẾT MINH)
// ================================================================
const TOUR_STEPS = [
    {
        targetId: 'top-header',
        title: '👋 Chào mừng đến với Iris AI Explorer!',
        content: 'Đồ án môn học <strong>Học máy Nâng cao</strong> của sinh viên <strong>Nguyễn Xuân Phúc (MSSV 3110524025 — Lớp 24CKDL)</strong>, GVHD <strong>TS. Phan Trần Đức Minh</strong>, Khoa Toán - Tin, ĐH Sư phạm — ĐHĐN.'
    },
    {
        targetId: 'anatomy-wrap',
        title: '🌸 Sơ đồ Cấu tạo hoa',
        content: 'Sơ đồ SVG minh họa trực quan 4 thông số hình thái: Đài hoa (Sepal) và Cánh hoa (Petal). Khi điều chỉnh hoặc rê chuột vào thanh trượt, thành phần tương ứng sẽ sáng lên.'
    },
    {
        targetId: 'radar-canvas',
        title: '📊 Biểu đồ Radar & XAI',
        content: 'Mô hình phân tích độ nhạy của từng đặc trưng (Feature Sensitivity Attribution), giải thích lý do đằng sau kết quả phân loại.'
    },
    {
        targetId: 'tab-data',
        title: '📈 Bản đồ 2D & Siêu tham số',
        content: 'Khảo sát đường biên phân tách của 150 mẫu hoa và điều chỉnh siêu tham số C, γ để quan sát hiện tượng Overfitting/Underfitting.'
    },
    {
        targetId: 'tab-pca3d',
        title: '🧊 Không gian 3D PCA (Xoay 360°)',
        content: 'Chiếu giảm chiều từ 4D xuống 3D bảo toàn <strong>99.48% phương sai</strong>. Bạn có thể kéo chuột xoay 360° và quan sát vị trí của các Support Vectors.'
    },
    {
        targetId: 'tab-svm',
        title: '📐 Điều kiện KKT & Báo cáo kết quả',
        content: 'Phân tích hệ số nhân Lagrange α_i theo định lý Karush-Kuhn-Tucker để phân loại Free SV vs Bounded SV, cùng chức năng xuất <strong>Báo Cáo Phân Loại (PDF)</strong>.'
    }
];

let currentTourIndex = 0;

function initGuidedTour() {
    const tourBtn = document.getElementById('tour-btn');
    const closeBtn = document.getElementById('tour-close-btn');
    const skipBtn = document.getElementById('tour-skip-btn');
    const prevBtn = document.getElementById('tour-prev-btn');
    const nextBtn = document.getElementById('tour-next-btn');

    if (tourBtn) tourBtn.addEventListener('click', startGuidedTour);
    if (closeBtn) closeBtn.addEventListener('click', closeGuidedTour);
    if (skipBtn) skipBtn.addEventListener('click', closeGuidedTour);

    if (prevBtn) {
        prevBtn.addEventListener('click', () => {
            if (currentTourIndex > 0) {
                currentTourIndex--;
                renderTourStep();
            }
        });
    }

    if (nextBtn) {
        nextBtn.addEventListener('click', () => {
            if (currentTourIndex < TOUR_STEPS.length - 1) {
                currentTourIndex++;
                renderTourStep();
            } else {
                closeGuidedTour();
            }
        });
    }
}

function startGuidedTour() {
    currentTourIndex = 0;
    const overlay = document.getElementById('tour-overlay');
    if (overlay) {
        overlay.hidden = false;
        overlay.style.display = 'block';
        overlay.classList.add('show');
    }
    renderTourStep();
}

function closeGuidedTour() {
    const overlay = document.getElementById('tour-overlay');
    if (overlay) {
        overlay.hidden = true;
        overlay.style.display = 'none';
        overlay.classList.remove('show');
    }
    document.querySelectorAll('.tour-highlight-target').forEach(el => el.classList.remove('tour-highlight-target'));
}

function renderTourStep() {
    const step = TOUR_STEPS[currentTourIndex];
    if (!step) return;

    // Remove old highlights
    document.querySelectorAll('.tour-highlight-target').forEach(el => el.classList.remove('tour-highlight-target'));

    const badge = document.getElementById('tour-step-badge');
    const title = document.getElementById('tour-title');
    const content = document.getElementById('tour-content');
    const prevBtn = document.getElementById('tour-prev-btn');
    const nextBtn = document.getElementById('tour-next-btn');
    const card = document.getElementById('tour-card');

    if (badge) badge.textContent = `Bước ${currentTourIndex + 1} / ${TOUR_STEPS.length}`;
    if (title) title.innerHTML = step.title;
    if (content) content.innerHTML = step.content;

    if (prevBtn) prevBtn.style.display = currentTourIndex === 0 ? 'none' : 'inline-block';
    if (nextBtn) nextBtn.textContent = currentTourIndex === TOUR_STEPS.length - 1 ? 'Hoàn tất ✓' : 'Tiếp theo →';

    // Switch tab if step targets a tab
    if (step.targetId === 'tab-data') {
        document.getElementById('tab-data')?.click();
    } else if (step.targetId === 'tab-pca3d') {
        document.getElementById('tab-pca3d')?.click();
    } else if (step.targetId === 'tab-svm') {
        document.getElementById('tab-svm')?.click();
    } else if (currentTourIndex === 0 || currentTourIndex === 1 || currentTourIndex === 2) {
        document.getElementById('tab-predict')?.click();
    }

    // Position tour card near target
    const targetEl = document.getElementById(step.targetId) || document.querySelector('.top-header');
    if (targetEl && card) {
        targetEl.classList.add('tour-highlight-target');
        const rect = targetEl.getBoundingClientRect();
        const top = Math.min(window.innerHeight - 300, Math.max(20, rect.bottom + 15));
        const left = Math.min(window.innerWidth - 400, Math.max(20, rect.left));
        card.style.top = `${top}px`;
        card.style.left = `${left}px`;
    }
}
