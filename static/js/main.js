/**
 * Automated Image Preprocessing System Using AWS
 * Module 2: Frontend Validation & Image Upload Controller
 * Module 6: Real-Time SaaS Dashboard & Processing Results Gallery Controller
 */

// Global Dashboard State
let currentView = 'dashboard';
let currentPage = 1;
let currentPerPage = 10;
let totalPages = 1;
let isUploading = false;
let selectedFile = null;

// Allowed Upload Configurations
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB in bytes
const ALLOWED_EXTENSIONS = ['jpg', 'jpeg', 'png'];
const ALLOWED_MIME_TYPES = ['image/jpeg', 'image/png'];

document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize API Health Check
    checkHealthEndpoint();

    // 2. Initialize Image Upload System (Module 2 & 3)
    initImageUpload();

    // 3. Initialize SaaS Dashboard Controller (Module 6)
    initDashboard();
});

/* ==============================================================================
   MODULE 2 & 3: IMAGE UPLOAD AND VALIDATION CONTROLLER
   ============================================================================== */

function initImageUpload() {
    const fileInput = document.getElementById('image-file-input');
    const browseBtn = document.getElementById('browse-btn');
    const dropZone = document.getElementById('drop-zone');
    const removeBtn = document.getElementById('remove-btn');
    const uploadBtn = document.getElementById('upload-btn');

    if (!fileInput || !dropZone || !uploadBtn) {
        return;
    }

    // Browse Button triggers hidden file input
    browseBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        fileInput.click();
    });

    // Clicking dropzone triggers file input
    dropZone.addEventListener('click', () => {
        fileInput.click();
    });

    // File input change event
    fileInput.addEventListener('change', (e) => {
        const file = e.target.files && e.target.files[0];
        handleFileSelection(file);
    });

    // Drag and Drop listeners
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove('dragover');
        });
    });

    dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const file = dt.files && dt.files[0];
        if (file) {
            handleFileSelection(file);
        }
    });

    // Remove Image button listener
    removeBtn.addEventListener('click', () => {
        resetUploadForm();
        showStatusMessage('info', 'Image Removed', 'Selected image was removed. Please choose another file.');
    });

    // Upload button click listener
    uploadBtn.addEventListener('click', () => {
        if (!selectedFile || isUploading) return;
        submitUpload();
    });
}

/**
 * Validates selected file and updates preview.
 */
function handleFileSelection(file) {
    clearStatusMessage();
    hideResultCard();

    if (!file) {
        resetUploadForm();
        return;
    }

    // 1. Check file extension
    const filename = file.name || '';
    const lastDotIndex = filename.lastIndexOf('.');
    if (lastDotIndex === -1) {
        handleValidationError('Unsupported file format. Only JPG, JPEG and PNG images are allowed.');
        return;
    }

    const extension = filename.substring(lastDotIndex + 1).toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(extension)) {
        handleValidationError(`Unsupported extension ".${extension}". Only JPG, JPEG and PNG images are allowed.`);
        return;
    }

    // 2. Check MIME type
    if (file.type && !ALLOWED_MIME_TYPES.includes(file.type.toLowerCase())) {
        handleValidationError(`Invalid file type "${file.type}". Only JPG, JPEG and PNG images are allowed.`);
        return;
    }

    // 3. Check File Size (Max 10 MB)
    if (file.size > MAX_FILE_SIZE) {
        const sizeMb = (file.size / (1024 * 1024)).toFixed(2);
        handleValidationError(`File size (${sizeMb} MB) exceeds maximum allowed limit of 10 MB.`);
        return;
    }

    if (file.size === 0) {
        handleValidationError('Selected file is empty (0 bytes). Please select a valid image.');
        return;
    }

    // Validation Successful!
    selectedFile = file;
    updateStatusSteps('validated');

    // Update Image Preview
    displayImagePreview(file, extension);

    // Enable Upload Button
    const uploadBtn = document.getElementById('upload-btn');
    const actionNote = document.getElementById('action-note');
    uploadBtn.disabled = false;
    actionNote.textContent = 'Image validated and ready for ingestion';
    actionNote.style.color = '#047857';

    showStatusMessage('info', 'Validation Successful', `Image "${file.name}" is valid and ready to upload.`);
}

/**
 * Renders preview image and metadata.
 */
function displayImagePreview(file, extension) {
    const previewCard = document.getElementById('preview-card');
    const previewImg = document.getElementById('preview-image');
    const previewFilename = document.getElementById('preview-filename');
    const previewFormat = document.getElementById('preview-format');
    const previewSize = document.getElementById('preview-size');
    const previewMime = document.getElementById('preview-mimetype');

    previewFilename.textContent = file.name;
    previewFormat.textContent = extension.toUpperCase();
    previewSize.textContent = formatBytes(file.size);
    previewMime.textContent = file.type || 'image/' + extension;

    // Use FileReader for preview
    const reader = new FileReader();
    reader.onload = (e) => {
        previewImg.src = e.target.result;
        previewCard.style.display = 'block';
    };
    reader.readAsDataURL(file);
}

/**
 * Submits the image upload via fetch API to POST /api/upload.
 */
async function submitUpload() {
    if (!selectedFile || isUploading) return;

    isUploading = true;
    const uploadBtn = document.getElementById('upload-btn');
    const uploadSpinner = document.getElementById('upload-spinner');
    const uploadBtnText = document.getElementById('upload-btn-text');
    const actionNote = document.getElementById('action-note');
    const removeBtn = document.getElementById('remove-btn');

    // Prevent duplicate submissions
    uploadBtn.disabled = true;
    removeBtn.disabled = true;
    uploadSpinner.style.display = 'inline-block';
    uploadBtnText.textContent = 'Uploading...';
    actionNote.textContent = 'Transferring file to backend temporary storage...';
    actionNote.style.color = '#0284c7';

    updateStatusSteps('uploading');
    showStatusMessage('info', 'Uploading', 'Sending multipart image data to Flask server...');

    const formData = new FormData();
    formData.append('image', selectedFile);

    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData,
            headers: {
                'Accept': 'application/json'
            }
        });

        const result = await response.json();

        if (response.ok && (result.status === 'success' || result.success === true)) {
            // Upload Completed
            updateStatusSteps('completed');

            const isS3 = (result.storage_backend === 's3' || (result.data && result.data.storage_backend === 's3'));
            if (isS3) {
                showStatusMessage('success', 'Cloud Upload Completed', 'Image uploaded successfully to AWS S3!');
            } else {
                showStatusMessage('success', 'Upload Completed', result.message || 'Image successfully uploaded to local storage.');
            }

            // Consolidate response data
            const displayData = Object.assign({}, result.data || {}, result);
            displayUploadResult(displayData);
            
            // Reset upload form inputs after successful ingestion
            resetUploadFormStateOnly();

            // Auto-refresh Module 6 Dashboard statistics and tables
            loadDashboardStats();
            if (currentView === 'dashboard') {
                loadRecentUploads();
            } else if (currentView === 'images') {
                loadImagesTable(1, currentPerPage);
            } else if (currentView === 'results') {
                loadResultsGallery();
            }
        } else {
            // Server-side validation or error failure
            updateStatusSteps('failed');
            const errorMsg = result.message || 'Server rejected the uploaded file.';
            showStatusMessage('error', 'Upload Failed', errorMsg);
        }
    } catch (err) {
        console.error('Upload request error:', err);
        updateStatusSteps('failed');
        showStatusMessage('error', 'Upload Failed', 'Network or connectivity error while uploading image.');
    } finally {
        isUploading = false;
        uploadSpinner.style.display = 'none';
        uploadBtnText.textContent = 'Upload Image';
        removeBtn.disabled = false;
    }
}

/**
 * Displays upload result card with S3 object key, presigned URL, or local details.
 */
function displayUploadResult(data) {
    const resultCard = document.getElementById('upload-result-card');
    if (!resultCard || !data) return;

    const isS3 = (data.storage_backend === 's3');

    // Headers & Scope
    const badgeHeader = document.getElementById('result-badge-header');
    const scopeLabel = document.getElementById('result-backend-scope');
    if (badgeHeader) {
        badgeHeader.textContent = isS3 ? 'AWS S3 Cloud Upload' : 'Local Upload Completed';
    }
    if (scopeLabel) {
        scopeLabel.textContent = isS3 ? 'Private Bucket Ingestion (ap-south-1)' : 'instance/uploads/ (Local)';
    }

    // Status & Backend
    const statusEl = document.getElementById('res-status');
    if (statusEl) {
        statusEl.textContent = data.upload_status || (isS3 ? 'S3_UPLOAD_COMPLETED' : 'LOCAL_UPLOAD_COMPLETED');
    }
    const backendEl = document.getElementById('res-backend');
    if (backendEl) {
        backendEl.textContent = isS3 ? 'AWS S3 (Mumbai ap-south-1)' : 'Local Storage';
    }

    // Filenames & Metadata
    const filenameEl = document.getElementById('res-filename');
    if (filenameEl) {
        filenameEl.textContent = data.original_filename || data.filename || 'N/A';
    }
    const formatSizeEl = document.getElementById('res-format-size');
    if (formatSizeEl) {
        const dimStr = (data.width && data.height) ? `${data.width} × ${data.height} px • ` : '';
        formatSizeEl.textContent = `${dimStr}${data.format || 'Image'} (${formatBytes(data.size || 0)})`;
    }

    // S3 Object Key
    const s3KeyContainer = document.getElementById('res-s3-key-container');
    const s3KeyEl = document.getElementById('res-s3-key');
    if (s3KeyContainer && s3KeyEl) {
        if (data.s3_key) {
            s3KeyEl.textContent = data.s3_key;
            s3KeyContainer.style.display = 'block';
        } else {
            s3KeyContainer.style.display = 'none';
        }
    }

    // S3 Presigned URL & Cloud Preview
    const presignedContainer = document.getElementById('res-presigned-container');
    const presignedLink = document.getElementById('res-presigned-link');
    const presignedImg = document.getElementById('res-presigned-img');
    if (presignedContainer && presignedLink && presignedImg) {
        if (data.presigned_url) {
            presignedLink.href = data.presigned_url;
            presignedImg.src = data.presigned_url;
            presignedContainer.style.display = 'block';
        } else {
            presignedContainer.style.display = 'none';
        }
    }

    resultCard.style.display = 'block';
}

function hideResultCard() {
    const resultCard = document.getElementById('upload-result-card');
    if (resultCard) {
        resultCard.style.display = 'none';
    }
}

/**
 * Handles client validation error.
 */
function handleValidationError(errorMessage) {
    resetUploadForm();
    updateStatusSteps('failed');
    showStatusMessage('error', 'Validation Failed', errorMessage);
}

/**
 * Resets the file selection and UI state.
 */
function resetUploadForm() {
    selectedFile = null;
    const fileInput = document.getElementById('image-file-input');
    if (fileInput) fileInput.value = '';

    const previewCard = document.getElementById('preview-card');
    const previewImg = document.getElementById('preview-image');
    if (previewCard) previewCard.style.display = 'none';
    if (previewImg) previewImg.src = '';

    const uploadBtn = document.getElementById('upload-btn');
    const actionNote = document.getElementById('action-note');
    if (uploadBtn) uploadBtn.disabled = true;
    if (actionNote) {
        actionNote.textContent = 'Select a valid image file to enable upload';
        actionNote.style.color = '#64748b';
    }

    updateStatusSteps('initial');
}

/**
 * Resets only form state after success (keeping the result visible).
 */
function resetUploadFormStateOnly() {
    selectedFile = null;
    const fileInput = document.getElementById('image-file-input');
    if (fileInput) fileInput.value = '';

    const previewCard = document.getElementById('preview-card');
    const previewImg = document.getElementById('preview-image');
    if (previewCard) previewCard.style.display = 'none';
    if (previewImg) previewImg.src = '';

    const uploadBtn = document.getElementById('upload-btn');
    const actionNote = document.getElementById('action-note');
    if (uploadBtn) uploadBtn.disabled = true;
    if (actionNote) {
        actionNote.textContent = 'Image stored successfully. You may select another image.';
        actionNote.style.color = '#047857';
    }
}

/**
 * Updates visual status stepper.
 * States: initial, selected, validated, uploading, completed, failed
 */
function updateStatusSteps(state) {
    const stepSelect = document.getElementById('step-select');
    const stepValidate = document.getElementById('step-validate');
    const stepUploading = document.getElementById('step-uploading');
    const stepResult = document.getElementById('step-result');
    const stepResultLabel = document.getElementById('step-result-label');

    // Reset all steps
    [stepSelect, stepValidate, stepUploading, stepResult].forEach(s => {
        if (s) {
            s.classList.remove('active', 'completed', 'failed');
        }
    });

    if (state === 'initial') {
        stepResultLabel.textContent = 'Upload status';
    } else if (state === 'selected') {
        stepSelect.classList.add('active');
    } else if (state === 'validated') {
        stepSelect.classList.add('completed');
        stepValidate.classList.add('completed');
        stepResultLabel.textContent = 'Ready for upload';
    } else if (state === 'uploading') {
        stepSelect.classList.add('completed');
        stepValidate.classList.add('completed');
        stepUploading.classList.add('active');
        stepResultLabel.textContent = 'Uploading...';
    } else if (state === 'completed') {
        stepSelect.classList.add('completed');
        stepValidate.classList.add('completed');
        stepUploading.classList.add('completed');
        stepResult.classList.add('completed');
        stepResultLabel.textContent = 'Upload completed';
    } else if (state === 'failed') {
        stepResult.classList.add('failed');
        stepResultLabel.textContent = 'Upload failed';
    }
}

/**
 * Displays status message banner.
 */
function showStatusMessage(type, title, message) {
    const box = document.getElementById('status-message-box');
    const icon = document.getElementById('message-icon');
    const titleEl = document.getElementById('message-title');
    const textEl = document.getElementById('message-text');

    if (!box) return;

    box.className = `status-message-box ${type}`;
    titleEl.textContent = title;
    textEl.textContent = message;

    if (type === 'success') {
        icon.textContent = '✓';
    } else if (type === 'error') {
        icon.textContent = '✕';
    } else {
        icon.textContent = 'ℹ';
    }

    box.style.display = 'flex';
}

function clearStatusMessage() {
    const box = document.getElementById('status-message-box');
    if (box) {
        box.style.display = 'none';
    }
}

function formatBytes(bytes, decimals = 2) {
    const num = Number(bytes);
    if (isNaN(num) || num <= 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(num) / Math.log(k));
    return parseFloat((num / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

/**
 * Health Diagnostics Endpoint Poller (Preserves Module 1 tests and assertions).
 */
async function checkHealthEndpoint() {
    const healthPill = document.getElementById('health-pill');
    const liveStatusText = document.getElementById('live-status-text');
    const backendStatusPill = document.getElementById('backend-status-pill');
    const healthFlaskBadge = document.getElementById('health-flask-badge');
    const healthDbBadge = document.getElementById('health-db-badge');
    const healthS3Badge = document.getElementById('health-s3-badge');
    const rawHealthJson = document.getElementById('raw-health-json');

    try {
        const startTime = performance.now();
        const response = await fetch('/health', {
            method: 'GET',
            headers: { 'Accept': 'application/json' }
        });
        const duration = Math.round(performance.now() - startTime);

        if (response.ok) {
            const data = await response.json();
            if (rawHealthJson) {
                rawHealthJson.textContent = JSON.stringify(data, null, 2);
            }

            if (data.status === 'success') {
                if (healthPill) {
                    healthPill.textContent = `200 OK (${duration}ms)`;
                    healthPill.style.backgroundColor = '#ecfdf5';
                    healthPill.style.color = '#065f46';
                }
                if (liveStatusText) {
                    liveStatusText.textContent = 'Backend Status: Running';
                }
                if (backendStatusPill) {
                    backendStatusPill.textContent = 'Backend Status: Running';
                }
                if (healthFlaskBadge) {
                    healthFlaskBadge.textContent = 'Healthy';
                    healthFlaskBadge.className = 'status-badge status-badge-completed';
                }
                if (healthDbBadge && data.services && data.services.database) {
                    const dbStatus = data.services.database;
                    healthDbBadge.textContent = (dbStatus === 'connected') ? 'Connected' : dbStatus;
                    healthDbBadge.className = (dbStatus === 'connected') 
                        ? 'status-badge status-badge-completed' 
                        : 'status-badge status-badge-pending';
                }
                if (healthS3Badge) {
                    healthS3Badge.textContent = 'Active (ap-south-1)';
                    healthS3Badge.className = 'status-badge status-badge-completed';
                }
            }
        }
    } catch (err) {
        console.warn('Health check request error:', err);
        if (rawHealthJson) {
            rawHealthJson.textContent = JSON.stringify({ error: err.message, status: 'unreachable' }, null, 2);
        }
    }
}

/* ==============================================================================
   MODULE 6: REAL-TIME SAAS DASHBOARD & PROCESSING RESULTS CONTROLLER
   ============================================================================== */

/**
 * Initializes all dashboard interactions, view switching, and data polling.
 */
function initDashboard() {
    // 1. Sidebar View Switching Listeners
    const navLinks = document.querySelectorAll('.sidebar-nav-link');
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const view = link.getAttribute('data-view');
            if (view) {
                window.location.hash = view;
                switchView(view);
            }
        });
    });

    // 2. Mobile Navigation Toggle
    const mobileToggle = document.getElementById('mobile-toggle-btn');
    if (mobileToggle) {
        mobileToggle.addEventListener('click', () => {
            const sidebar = document.getElementById('dashboard-sidebar');
            if (sidebar) {
                sidebar.classList.toggle('open');
            }
        });
    }

    // 3. Quick Navigation Button on Dashboard (View All Images)
    const btnGotoAll = document.getElementById('btn-goto-all-images');
    if (btnGotoAll) {
        btnGotoAll.addEventListener('click', () => {
            window.location.hash = 'images';
            switchView('images');
        });
    }

    // 4. View Refresh Buttons
    const btnRefreshDashboard = document.getElementById('btn-refresh-dashboard');
    if (btnRefreshDashboard) {
        btnRefreshDashboard.addEventListener('click', () => {
            loadDashboardStats();
            loadRecentUploads();
        });
    }

    const btnRefreshImages = document.getElementById('btn-refresh-images');
    if (btnRefreshImages) {
        btnRefreshImages.addEventListener('click', () => {
            loadImagesTable(currentPage, currentPerPage);
        });
    }

    const btnRefreshResults = document.getElementById('btn-refresh-results');
    if (btnRefreshResults) {
        btnRefreshResults.addEventListener('click', () => {
            loadResultsGallery();
        });
    }

    const btnRecheckHealth = document.getElementById('btn-recheck-health');
    if (btnRecheckHealth) {
        btnRecheckHealth.addEventListener('click', () => {
            checkHealthEndpoint();
        });
    }

    // 5. Table Rows-Per-Page Selector
    const perPageSelect = document.getElementById('filter-per-page');
    if (perPageSelect) {
        perPageSelect.addEventListener('change', (e) => {
            currentPerPage = parseInt(e.target.value, 10) || 10;
            currentPage = 1;
            loadImagesTable(currentPage, currentPerPage);
        });
    }

    // 6. Pagination Prev/Next Buttons
    const btnPrev = document.getElementById('btn-page-prev');
    if (btnPrev) {
        btnPrev.addEventListener('click', () => {
            if (currentPage > 1) {
                loadImagesTable(currentPage - 1, currentPerPage);
            }
        });
    }

    const btnNext = document.getElementById('btn-page-next');
    if (btnNext) {
        btnNext.addEventListener('click', () => {
            if (currentPage < totalPages) {
                loadImagesTable(currentPage + 1, currentPerPage);
            }
        });
    }

    // 7. Modal Dismiss Listeners (Close Button, Dismiss Button, Backdrop, and Escape Key)
    const btnModalClose = document.getElementById('btn-modal-close');
    if (btnModalClose) {
        btnModalClose.addEventListener('click', closeImageModal);
    }

    const btnModalDismiss = document.getElementById('btn-modal-dismiss');
    if (btnModalDismiss) {
        btnModalDismiss.addEventListener('click', closeImageModal);
    }

    const modalBackdrop = document.getElementById('image-details-modal');
    if (modalBackdrop) {
        modalBackdrop.addEventListener('click', (e) => {
            if (e.target === modalBackdrop) {
                closeImageModal();
            }
        });
    }

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeImageModal();
        }
    });

    // 8. Hash Change Listener
    window.addEventListener('hashchange', () => {
        const hash = window.location.hash.replace('#', '');
        if (hash) {
            switchView(hash);
        }
    });

    // 9. Initial View Loading from Hash or Default to Dashboard
    const initialView = window.location.hash.replace('#', '') || 'dashboard';
    switchView(initialView);

    // Initial background load of summary statistics
    loadDashboardStats();
}

/**
 * Switches the active dashboard view panel and updates sidebar states.
 */
function switchView(viewName) {
    const validViews = ['dashboard', 'upload', 'images', 'results', 'health'];
    if (!validViews.includes(viewName)) {
        viewName = 'dashboard';
    }
    currentView = viewName;

    // Update Sidebar Navigation Links
    document.querySelectorAll('.sidebar-nav-link').forEach(link => {
        if (link.getAttribute('data-view') === viewName) {
            link.classList.add('active');
        } else {
            link.classList.remove('active');
        }
    });

    // Update View Panels
    document.querySelectorAll('.dashboard-view-panel').forEach(panel => {
        if (panel.id === `view-${viewName}`) {
            panel.classList.add('active');
        } else {
            panel.classList.remove('active');
        }
    });

    // Close Mobile Sidebar
    const sidebar = document.getElementById('dashboard-sidebar');
    if (sidebar) {
        sidebar.classList.remove('open');
    }

    // Trigger View-Specific Data Fetching
    if (viewName === 'dashboard') {
        loadDashboardStats();
        loadRecentUploads();
    } else if (viewName === 'images') {
        loadImagesTable(currentPage, currentPerPage);
    } else if (viewName === 'results') {
        loadResultsGallery();
    } else if (viewName === 'health') {
        checkHealthEndpoint();
    }
}

/**
 * Fetches dashboard statistics from GET /api/dashboard/stats and populates summary cards.
 */
async function loadDashboardStats() {
    try {
        const response = await fetch('/api/dashboard/stats', {
            headers: { 'Accept': 'application/json' }
        });
        if (!response.ok) return;

        const res = await response.json();
        if (res.status === 'success' && res.data) {
            const stats = res.data;

            const totalEl = document.getElementById('stat-total-images');
            const compEl = document.getElementById('stat-completed-images');
            const pendEl = document.getElementById('stat-pending-images');
            const failEl = document.getElementById('stat-failed-images');
            const navBadge = document.getElementById('nav-badge-count');
            const tableTotalBadge = document.getElementById('table-total-count-badge');

            const totalCount = stats.total_images ?? stats.total ?? 0;
            const completedCount = stats.completed_images ?? stats.completed ?? 0;
            const pendingCount = stats.pending_images ?? stats.pending ?? 0;
            const processingCount = stats.processing_images ?? stats.processing ?? 0;
            const inFlightCount = stats.in_flight_images ?? (pendingCount + processingCount);
            const failedCount = stats.failed_images ?? stats.failed ?? 0;

            if (totalEl) totalEl.textContent = totalCount;
            if (compEl) compEl.textContent = completedCount;
            if (pendEl) pendEl.textContent = inFlightCount;
            if (failEl) failEl.textContent = failedCount;
            if (navBadge) navBadge.textContent = totalCount;
            if (tableTotalBadge) tableTotalBadge.textContent = `${totalCount} Image Records`;
        }
    } catch (err) {
        console.warn('Unable to load dashboard statistics:', err);
    }
}

/**
 * Fetches the 5 most recent uploads and populates the dashboard overview table.
 */
async function loadRecentUploads() {
    const tbody = document.getElementById('dashboard-recent-table-body');
    if (!tbody) return;

    try {
        const response = await fetch('/api/images?page=1&per_page=5', {
            headers: { 'Accept': 'application/json' }
        });
        if (!response.ok) throw new Error('API returned ' + response.status);

        const res = await response.json();
        // Support both { data: { images: [...] } } and { data: [...] }
        const records = (res.data && res.data.images) ? res.data.images : (Array.isArray(res.data) ? res.data : []);

        tbody.innerHTML = '';

        if (!records || records.length === 0) {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td colspan="6" class="empty-state">
                    <div class="empty-state-title">No Uploads Ingested Yet</div>
                    <div class="empty-state-desc">Upload your first image to trigger AWS Lambda preprocessing.</div>
                </td>
            `;
            tbody.appendChild(tr);
            return;
        }

        records.forEach(item => {
            const tr = document.createElement('tr');

            // 1. Thumbnail
            const tdThumb = document.createElement('td');
            tdThumb.appendChild(createTableThumbnail(item));
            tr.appendChild(tdThumb);

            // 2. Filename
            const tdFilename = document.createElement('td');
            tdFilename.textContent = item.original_filename || 'Unknown';
            tdFilename.style.fontWeight = '600';
            tdFilename.style.color = 'var(--text-primary)';
            tr.appendChild(tdFilename);

            // 3. Image ID
            const tdId = document.createElement('td');
            const codeId = document.createElement('code');
            codeId.className = 'result-code';
            codeId.textContent = item.image_id ? (item.image_id.substring(0, 8) + '...') : '-';
            codeId.title = item.image_id || '';
            tdId.appendChild(codeId);
            tr.appendChild(tdId);

            // 4. Upload Date
            const tdDate = document.createElement('td');
            tdDate.textContent = formatDateTime(item.created_at);
            tr.appendChild(tdDate);

            // 5. Status Badge
            const tdStatus = document.createElement('td');
            tdStatus.appendChild(createStatusBadge(item.processing_status));
            tr.appendChild(tdStatus);

            // 6. Action Button
            const tdAction = document.createElement('td');
            const btnDetails = document.createElement('button');
            btnDetails.type = 'button';
            btnDetails.className = 'btn-table-action';
            btnDetails.textContent = 'View Details';
            btnDetails.addEventListener('click', () => openImageModal(item.image_id));
            tdAction.appendChild(btnDetails);
            tr.appendChild(tdAction);

            tbody.appendChild(tr);
        });

    } catch (err) {
        console.warn('Unable to load recent uploads:', err);
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="empty-state">
                    <div class="empty-state-title" style="color: var(--error-red);">Failed to Load Recent Images</div>
                    <div class="empty-state-desc">Database or API service is currently unreachable.</div>
                </td>
            </tr>
        `;
    }
}

/**
 * Fetches paginated image records from GET /api/images and populates the All Images table.
 */
async function loadImagesTable(page = 1, perPage = 10) {
    const tbody = document.getElementById('all-images-table-body');
    const paginationInfo = document.getElementById('pagination-info-text');
    if (!tbody) return;

    try {
        const response = await fetch(`/api/images?page=${page}&per_page=${perPage}`, {
            headers: { 'Accept': 'application/json' }
        });
        if (!response.ok) throw new Error('API returned ' + response.status);

        const res = await response.json();
        // Support both { data: { images: [...] } } and { data: [...] }
        const records = (res.data && res.data.images) ? res.data.images : (Array.isArray(res.data) ? res.data : []);
        const pagination = (res.data && res.data.pagination) ? res.data.pagination : (res.pagination || {
            page: page,
            per_page: perPage,
            total_records: records.length,
            total_pages: 1,
            has_prev: false,
            has_next: false
        });

        currentPage = pagination.page || 1;
        totalPages = pagination.total_pages || 1;

        tbody.innerHTML = '';

        if (!records || records.length === 0) {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td colspan="8" class="empty-state">
                    <div class="empty-state-title">No Image Records Stored in RDS MySQL</div>
                    <div class="empty-state-desc">Head to "Upload Image" to ingest and preprocess new media assets.</div>
                </td>
            `;
            tbody.appendChild(tr);
            if (paginationInfo) paginationInfo.textContent = 'Showing 0 of 0 records';
            renderPaginationControls(pagination);
            return;
        }

        records.forEach(item => {
            const tr = document.createElement('tr');

            // 1. Thumbnail
            const tdThumb = document.createElement('td');
            tdThumb.appendChild(createTableThumbnail(item));
            tr.appendChild(tdThumb);

            // 2. Filename
            const tdFilename = document.createElement('td');
            tdFilename.textContent = item.original_filename || 'Unknown';
            tdFilename.style.fontWeight = '600';
            tdFilename.style.color = 'var(--text-primary)';
            tr.appendChild(tdFilename);

            // 3. Image ID
            const tdId = document.createElement('td');
            const codeId = document.createElement('code');
            codeId.className = 'result-code';
            codeId.textContent = item.image_id ? (item.image_id.substring(0, 8) + '...') : '-';
            codeId.title = item.image_id || '';
            tdId.appendChild(codeId);
            tr.appendChild(tdId);

            // 4. Upload Date
            const tdDate = document.createElement('td');
            tdDate.textContent = formatDateTime(item.created_at);
            tr.appendChild(tdDate);

            // 5. Original Size
            const tdOrigSize = document.createElement('td');
            const origBytes = item.original_size_bytes ?? item.original_size ?? 0;
            tdOrigSize.textContent = formatBytes(origBytes);
            tr.appendChild(tdOrigSize);

            // 6. Status Badge
            const tdStatus = document.createElement('td');
            tdStatus.appendChild(createStatusBadge(item.processing_status));
            tr.appendChild(tdStatus);

            // 7. Processed Size
            const tdProcSize = document.createElement('td');
            const statusUpper = (item.processing_status || '').toUpperCase();
            const procBytes = item.processed_size_bytes ?? item.processed_size ?? 0;
            if (statusUpper === 'COMPLETED' && procBytes > 0) {
                tdProcSize.textContent = formatBytes(procBytes);
                tdProcSize.style.fontWeight = '600';
                tdProcSize.style.color = 'var(--primary-blue)';
            } else if (statusUpper === 'FAILED') {
                tdProcSize.textContent = '—';
                tdProcSize.style.color = 'var(--error-red)';
            } else {
                tdProcSize.textContent = 'Pending...';
                tdProcSize.style.color = 'var(--text-muted)';
            }
            tr.appendChild(tdProcSize);

            // 8. Action Button
            const tdAction = document.createElement('td');
            const btnDetails = document.createElement('button');
            btnDetails.type = 'button';
            btnDetails.className = 'btn-table-action';
            btnDetails.textContent = 'View Details';
            btnDetails.addEventListener('click', () => openImageModal(item.image_id));
            tdAction.appendChild(btnDetails);
            tr.appendChild(tdAction);

            tbody.appendChild(tr);
        });

        // Update Pagination Controls
        renderPaginationControls(pagination);

    } catch (err) {
        console.warn('Unable to load images table:', err);
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="empty-state">
                    <div class="empty-state-title" style="color: var(--error-red);">Database Connection Error</div>
                    <div class="empty-state-desc">Unable to retrieve image records. Check Amazon RDS connectivity.</div>
                </td>
            </tr>
        `;
    }
}

/**
 * Updates pagination bar numbers and Prev/Next states.
 */
function renderPaginationControls(pagination) {
    const infoText = document.getElementById('pagination-info-text');
    const btnPrev = document.getElementById('btn-page-prev');
    const btnNext = document.getElementById('btn-page-next');
    const pageContainer = document.getElementById('page-numbers-container');

    const total = pagination.total_records || 0;
    const page = pagination.page || 1;
    const perPage = pagination.per_page || 10;
    const pages = pagination.total_pages || 1;

    if (infoText) {
        if (total === 0) {
            infoText.textContent = 'Showing 0 of 0 records';
        } else {
            const start = (page - 1) * perPage + 1;
            const end = Math.min(page * perPage, total);
            infoText.textContent = `Showing ${start}–${end} of ${total} records`;
        }
    }

    if (btnPrev) {
        btnPrev.disabled = !pagination.has_prev;
    }
    if (btnNext) {
        btnNext.disabled = !pagination.has_next;
    }

    if (pageContainer) {
        pageContainer.innerHTML = '';
        for (let p = 1; p <= pages; p++) {
            const pBtn = document.createElement('button');
            pBtn.type = 'button';
            pBtn.className = `btn-page ${p === page ? 'active' : ''}`;
            pBtn.textContent = p;
            pBtn.addEventListener('click', () => loadImagesTable(p, perPage));
            pageContainer.appendChild(pBtn);
        }
    }
}

/**
 * Fetches images and renders the visual Processing Results Gallery.
 */
async function loadResultsGallery() {
    const galleryContainer = document.getElementById('results-gallery-container');
    if (!galleryContainer) return;

    try {
        const response = await fetch('/api/images?page=1&per_page=24', {
            headers: { 'Accept': 'application/json' }
        });
        if (!response.ok) throw new Error('API returned ' + response.status);

        const res = await response.json();
        // Support both { data: { images: [...] } } and { data: [...] }
        const records = (res.data && res.data.images) ? res.data.images : (Array.isArray(res.data) ? res.data : []);

        galleryContainer.innerHTML = '';

        if (!records || records.length === 0) {
            galleryContainer.innerHTML = `
                <div class="empty-state" style="grid-column: 1 / -1;">
                    <div class="empty-state-title">No Processing Results Available</div>
                    <div class="empty-state-desc">Upload images to trigger the Lambda automated processing workflow and review results here.</div>
                </div>
            `;
            return;
        }

        records.forEach(item => {
            const card = document.createElement('div');
            card.className = 'comp-card';

            const statusUpper = (item.processing_status || '').toUpperCase();
            const isCompleted = (statusUpper === 'COMPLETED');
            const origBytes = item.original_size_bytes ?? item.original_size ?? 0;
            const procBytes = item.processed_size_bytes ?? item.processed_size ?? 0;

            const reduction = (item.reduction && item.reduction.percentage !== undefined)
                ? {
                    percent: item.reduction.percentage,
                    text: item.reduction.is_larger 
                        ? `+${item.reduction.percentage}% (Processed is larger)` 
                        : `${item.reduction.percentage}% Size Reduction`,
                    isLarger: item.reduction.is_larger
                }
                : calculateReductionClient(origBytes, procBytes);

            // 1. Header
            const header = document.createElement('div');
            header.className = 'comp-card-header';
            const title = document.createElement('div');
            title.className = 'comp-card-title';
            title.textContent = item.original_filename || 'Image';
            title.title = item.original_filename || '';
            header.appendChild(title);
            header.appendChild(createStatusBadge(item.processing_status));
            card.appendChild(header);

            // 2. Side-by-side previews row
            const previewsRow = document.createElement('div');
            previewsRow.className = 'comp-previews-row';

            // Original preview
            const origCol = document.createElement('div');
            origCol.className = 'preview-col';
            origCol.innerHTML = `
                <span class="preview-tag">Original</span>
                <div class="comp-img-wrapper">
                    ${item.original_url 
                        ? `<img src="${escapeHtml(item.original_url)}" class="comp-img" alt="Original Preview" loading="lazy">` 
                        : `<div style="color: #94a3b8; font-size: 0.8rem;">No Preview</div>`}
                </div>
            `;
            previewsRow.appendChild(origCol);

            // Processed preview
            const procCol = document.createElement('div');
            procCol.className = 'preview-col';
            let procContent = '';
            if (isCompleted && item.processed_url) {
                procContent = `<img src="${escapeHtml(item.processed_url)}" class="comp-img" alt="Processed Preview" loading="lazy">`;
            } else if (statusUpper === 'FAILED') {
                procContent = `<div style="color: var(--error-red); font-size: 0.8rem; font-weight: 600;">Failed</div>`;
            } else {
                procContent = `<div style="color: #94a3b8; font-size: 0.8rem;">Pending...</div>`;
            }

            procCol.innerHTML = `
                <span class="preview-tag">Processed</span>
                <div class="comp-img-wrapper">${procContent}</div>
            `;
            previewsRow.appendChild(procCol);
            card.appendChild(previewsRow);

            // 3. Card Body: Metrics & Optimization Badge
            const cardBody = document.createElement('div');
            cardBody.className = 'comp-card-body';

            const origDimStr = (item.original_width && item.original_height)
                ? `${item.original_width}×${item.original_height}`
                : (item.original_dimensions || 'N/A');
            const procDimStr = (item.processed_width && item.processed_height)
                ? `${item.processed_width}×${item.processed_height}`
                : (item.processed_dimensions || (isCompleted ? '800×800 (Max)' : 'Pending'));

            cardBody.innerHTML = `
                <table class="comp-metrics-table">
                    <tr>
                        <td>Original:</td>
                        <td class="metric-val">${escapeHtml(origDimStr)} • ${formatBytes(origBytes)}</td>
                    </tr>
                    <tr>
                        <td>Processed:</td>
                        <td class="metric-val">${escapeHtml(procDimStr)} • ${isCompleted ? formatBytes(procBytes) : '—'}</td>
                    </tr>
                </table>
            `;

            if (isCompleted && procBytes > 0) {
                const badgeDiv = document.createElement('div');
                badgeDiv.className = `reduction-badge ${reduction.isLarger ? 'reduction-negative' : 'reduction-positive'}`;
                badgeDiv.textContent = reduction.text;
                cardBody.appendChild(badgeDiv);
            }

            card.appendChild(cardBody);

            // 4. Card Footer: Comparison Action Button
            const cardFooter = document.createElement('div');
            cardFooter.className = 'comp-card-footer';
            const btnCompare = document.createElement('button');
            btnCompare.type = 'button';
            btnCompare.className = 'btn-table-action';
            btnCompare.style.width = '100%';
            btnCompare.style.justifyContent = 'center';
            btnCompare.textContent = 'View Side-by-Side Comparison';
            btnCompare.addEventListener('click', () => openImageModal(item.image_id));
            cardFooter.appendChild(btnCompare);
            card.appendChild(cardFooter);

            galleryContainer.appendChild(card);
        });

    } catch (err) {
        console.warn('Unable to load processing results gallery:', err);
        galleryContainer.innerHTML = `
            <div class="empty-state" style="grid-column: 1 / -1;">
                <div class="empty-state-title" style="color: var(--error-red);">Failed to Load Results Gallery</div>
                <div class="empty-state-desc">Unable to retrieve processed images from database or S3.</div>
            </div>
        `;
    }
}

/**
 * Opens dedicated Image Details & Comparison Modal via GET /api/images/<image_id>.
 */
async function openImageModal(imageId) {
    if (!imageId) return;

    try {
        const response = await fetch(`/api/images/${imageId}`, {
            headers: { 'Accept': 'application/json' }
        });
        if (!response.ok) throw new Error('API returned ' + response.status);

        const res = await response.json();
        const data = res.data;
        if (!data) return;

        const statusUpper = (data.processing_status || '').toUpperCase();
        const isCompleted = (statusUpper === 'COMPLETED');
        const isFailed = (statusUpper === 'FAILED');

        const origBytes = data.original_size_bytes ?? data.original_size ?? 0;
        const procBytes = data.processed_size_bytes ?? data.processed_size ?? 0;

        // Modal Title & Header Badge
        const modalFilename = document.getElementById('modal-filename');
        const modalStatusBadge = document.getElementById('modal-status-badge');
        if (modalFilename) modalFilename.textContent = data.original_filename || 'Image Details';
        if (modalStatusBadge) {
            modalStatusBadge.textContent = statusUpper;
            modalStatusBadge.className = 'status-badge';
            if (isCompleted) modalStatusBadge.classList.add('status-badge-completed');
            else if (statusUpper === 'PROCESSING') modalStatusBadge.classList.add('status-badge-processing');
            else if (statusUpper === 'PENDING') modalStatusBadge.classList.add('status-badge-pending');
            else if (isFailed) modalStatusBadge.classList.add('status-badge-failed');
        }

        // 1. Column: Original Image
        const origFormat = document.getElementById('modal-orig-format');
        const origImg = document.getElementById('modal-orig-img');
        const origDim = document.getElementById('modal-orig-dim');
        const origSize = document.getElementById('modal-orig-size');
        const origKey = document.getElementById('modal-orig-key');

        const origDimStr = (data.original_width && data.original_height)
            ? `${data.original_width}×${data.original_height}`
            : (data.original_dimensions || 'N/A');

        if (origFormat) origFormat.textContent = (data.original_format || 'IMG').toUpperCase();
        if (origImg) origImg.src = data.original_url || '';
        if (origDim) origDim.textContent = origDimStr;
        if (origSize) origSize.textContent = formatBytes(origBytes);
        if (origKey) origKey.textContent = data.original_s3_key || data.s3_original_key || 'uploads/raw-asset';

        // 2. Column: Processed Image
        const procFormat = document.getElementById('modal-proc-format');
        const procImg = document.getElementById('modal-proc-img');
        const procPendingState = document.getElementById('modal-proc-pending-state');
        const procPendingTitle = document.getElementById('modal-proc-pending-title');
        const procPendingText = document.getElementById('modal-proc-pending-text');
        const procDim = document.getElementById('modal-proc-dim');
        const procSize = document.getElementById('modal-proc-size');
        const procKey = document.getElementById('modal-proc-key');

        const procDimStr = (data.processed_width && data.processed_height)
            ? `${data.processed_width}×${data.processed_height}`
            : (data.processed_dimensions || (isCompleted ? '800 × 800 (Max)' : 'Pending...'));

        if (procFormat) procFormat.textContent = (data.processed_format || 'JPEG').toUpperCase();
        if (procDim) procDim.textContent = procDimStr;
        if (procSize) procSize.textContent = procBytes > 0 ? formatBytes(procBytes) : (isCompleted ? 'N/A' : 'Pending...');
        if (procKey) procKey.textContent = data.processed_s3_key || data.s3_processed_key || (isCompleted ? 'processed/...' : 'Pending...');

        // Processed Image View State
        if (isCompleted && data.processed_url) {
            if (procImg) {
                procImg.src = data.processed_url;
                procImg.style.display = 'block';
            }
            if (procPendingState) procPendingState.style.display = 'none';
        } else {
            if (procImg) procImg.style.display = 'none';
            if (procPendingState) {
                procPendingState.style.display = 'block';
                if (isFailed) {
                    if (procPendingTitle) procPendingTitle.textContent = 'Processing Failed';
                    if (procPendingText) procPendingText.textContent = data.error_message || 'Image processing failed during execution.';
                } else {
                    if (procPendingTitle) procPendingTitle.textContent = 'Processing in Progress';
                    if (procPendingText) procPendingText.textContent = 'AWS Lambda is actively transforming this image into an 800×800 JPEG.';
                }
            }
        }

        // 3. Optimization Savings Banner
        const savingsBanner = document.getElementById('modal-savings-banner');
        const savingsVal = document.getElementById('modal-savings-value');
        const savingsDetail = document.getElementById('modal-savings-detail');

        const red = data.reduction || data.size_reduction;
        if (savingsBanner && savingsVal && savingsDetail) {
            if (isCompleted && red) {
                savingsBanner.style.display = 'flex';
                const percent = red.percentage ?? red.savings_percent ?? 0;
                const savedBytes = red.bytes_saved ?? red.saved_bytes ?? 0;
                const isLarger = red.is_larger ?? false;

                if (isLarger) {
                    savingsVal.textContent = `+${percent}%`;
                    savingsVal.style.color = 'var(--warning-yellow)';
                    savingsDetail.textContent = `Original: ${formatBytes(origBytes)} → Processed: ${formatBytes(procBytes)} (Processed is larger)`;
                } else {
                    savingsVal.textContent = `${percent}% Saved`;
                    savingsVal.style.color = 'var(--primary-blue)';
                    savingsDetail.textContent = `Original: ${formatBytes(origBytes)} → Processed: ${formatBytes(procBytes)} (${formatBytes(savedBytes)} savings)`;
                }
            } else {
                savingsBanner.style.display = 'none';
            }
        }

        // 4. Lifecycle Metadata
        const metaId = document.getElementById('modal-meta-id');
        const metaBucket = document.getElementById('modal-meta-bucket');
        const metaCreated = document.getElementById('modal-meta-created');
        const metaCompleted = document.getElementById('modal-meta-completed');
        const errorRow = document.getElementById('modal-error-row');
        const metaError = document.getElementById('modal-meta-error');

        if (metaId) metaId.textContent = data.image_id;
        if (metaBucket) metaBucket.textContent = data.bucket_name || data.s3_bucket || 'aws-project-2515';
        if (metaCreated) metaCreated.textContent = formatDateTime(data.created_at);
        if (metaCompleted) {
            const compTime = data.processed_at || data.completed_at;
            metaCompleted.textContent = compTime ? formatDateTime(compTime) : (isCompleted ? 'Completed' : 'Pending');
        }

        if (errorRow && metaError) {
            if (data.error_message) {
                errorRow.style.display = 'table-row';
                metaError.textContent = data.error_message;
            } else {
                errorRow.style.display = 'none';
            }
        }

        // 5. Direct S3 Cloud Links
        const origLink = document.getElementById('modal-orig-link');
        const procLink = document.getElementById('modal-proc-link');

        if (origLink) {
            if (data.original_url) {
                origLink.href = data.original_url;
                origLink.style.display = 'inline-flex';
            } else {
                origLink.style.display = 'none';
            }
        }

        if (procLink) {
            if (isCompleted && data.processed_url) {
                procLink.href = data.processed_url;
                procLink.style.display = 'inline-flex';
            } else {
                procLink.style.display = 'none';
            }
        }

        // Show Modal
        const modal = document.getElementById('image-details-modal');
        if (modal) {
            modal.classList.add('open');
            modal.classList.add('active');
            document.body.style.overflow = 'hidden';
        }

    } catch (err) {
        console.error('Failed to open image modal details:', err);
    }
}

/**
 * Closes the Image Details Modal.
 */
function closeImageModal() {
    const modal = document.getElementById('image-details-modal');
    if (modal) {
        modal.classList.remove('open');
        modal.classList.remove('active');
        document.body.style.overflow = '';
    }
}

/**
 * Creates an XSS-safe status badge DOM element.
 */
function createStatusBadge(status) {
    const span = document.createElement('span');
    span.className = 'status-badge';

    const dot = document.createElement('span');
    dot.className = 'status-dot-sm';
    span.appendChild(dot);

    const statusText = (status || 'UNKNOWN').toUpperCase();
    const textNode = document.createTextNode(' ' + statusText);
    span.appendChild(textNode);

    if (statusText === 'COMPLETED') {
        span.classList.add('status-badge-completed');
    } else if (statusText === 'PROCESSING') {
        span.classList.add('status-badge-processing');
    } else if (statusText === 'PENDING') {
        span.classList.add('status-badge-pending');
    } else if (statusText === 'FAILED') {
        span.classList.add('status-badge-failed');
    }

    return span;
}

/**
 * Creates a thumbnail DOM wrapper for table rows.
 */
function createTableThumbnail(item) {
    const wrapper = document.createElement('div');
    wrapper.className = 'table-thumb-wrapper';

    const previewUrl = item.processed_url || item.original_url;
    if (previewUrl) {
        const img = document.createElement('img');
        img.className = 'table-thumb-img';
        img.src = previewUrl;
        img.alt = item.original_filename || 'Thumbnail';
        img.loading = 'lazy';
        wrapper.appendChild(img);
    } else {
        const placeholder = document.createElement('div');
        placeholder.className = 'table-thumb-placeholder';
        placeholder.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                <circle cx="8.5" cy="8.5" r="1.5"></circle>
                <polyline points="21 15 16 10 5 21"></polyline>
            </svg>
        `;
        wrapper.appendChild(placeholder);
    }

    return wrapper;
}

/**
 * Calculates file size reduction client-side for card gallery.
 */
function calculateReductionClient(origSize, procSize) {
    const orig = Number(origSize);
    const proc = Number(procSize);
    if (!orig || !proc || orig <= 0 || proc <= 0) {
        return { percent: 0, text: 'N/A', isLarger: false };
    }
    const diff = orig - proc;
    if (diff < 0) {
        const increasePercent = (((proc - orig) / orig) * 100).toFixed(1);
        return {
            percent: parseFloat(increasePercent),
            text: `+${increasePercent}% (Processed is larger)`,
            isLarger: true
        };
    }
    const savingsPercent = ((diff / orig) * 100).toFixed(1);
    return {
        percent: parseFloat(savingsPercent),
        text: `${savingsPercent}% Size Reduction`,
        isLarger: false
    };
}

/**
 * Formats ISO date string to readable YYYY-MM-DD HH:mm:ss.
 */
function formatDateTime(dateStr) {
    if (!dateStr) return '—';
    try {
        const d = new Date(dateStr);
        if (isNaN(d.getTime())) {
            return String(dateStr).replace('T', ' ').substring(0, 19);
        }
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        const hours = String(d.getHours()).padStart(2, '0');
        const minutes = String(d.getMinutes()).padStart(2, '0');
        const seconds = String(d.getSeconds()).padStart(2, '0');
        return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
    } catch (e) {
        return String(dateStr);
    }
}

/**
 * Escapes HTML characters to prevent XSS.
 */
function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
