/**
 * Offline LaTeX Generator — Vanilla JS Single Page Application (Phase 19.3)
 */

(function () {
  "use strict";

  // Application State
  const state = {
    jobId: null,
    selectedFile: null,
    pdfBlobUrl: null,
    latexSource: null,
  };

  // DOM Element References
  const elements = {
    // Views & Banners
    uploadView: document.getElementById("upload-view"),
    processingView: document.getElementById("processing-view"),
    workspaceView: document.getElementById("workspace-view"),
    errorBanner: document.getElementById("error-banner"),
    errorMessage: document.getElementById("error-message"),
    btnCloseError: document.getElementById("btn-close-error"),

    // Upload Elements
    dropZone: document.getElementById("drop-zone"),
    fileInput: document.getElementById("file-input"),
    btnBrowse: document.getElementById("btn-browse"),
    fileCard: document.getElementById("file-card"),
    fileName: document.getElementById("file-name"),
    fileSize: document.getElementById("file-size"),
    btnRemoveFile: document.getElementById("btn-remove-file"),
    btnProcess: document.getElementById("btn-process"),

    // Processing Stepper
    processingStatusText: document.getElementById("processing-status-text"),
    stepUpload: document.getElementById("step-upload"),
    stepOcr: document.getElementById("step-ocr"),
    stepStruct: document.getElementById("step-struct"),
    stepPreview: document.getElementById("step-preview"),

    // Workspace & Tabs
    tabBtnHtml: document.getElementById("tab-btn-html"),
    tabBtnPdf: document.getElementById("tab-btn-pdf"),
    tabBtnLatex: document.getElementById("tab-btn-latex"),
    panelHtml: document.getElementById("panel-html"),
    panelPdf: document.getElementById("panel-pdf"),
    panelLatex: document.getElementById("panel-latex"),
    iframeHtml: document.getElementById("iframe-html"),
    iframePdf: document.getElementById("iframe-pdf"),
    codeLatex: document.getElementById("code-latex"),

    // Action Buttons
    btnCopyLatex: document.getElementById("btn-copy-latex"),
    btnDownloadTex: document.getElementById("btn-download-tex"),
    btnResetWorkspace: document.getElementById("btn-reset-workspace"),
    btnResetHeader: document.getElementById("btn-reset-header"),
  };

  // Allowed extensions
  const ALLOWED_EXTENSIONS = ["pdf", "png", "jpg", "jpeg", "bmp", "tiff", "tif"];
  const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB

  // Initialize Event Listeners
  function init() {
    setupUploadEvents();
    setupTabEvents();
    setupActionEvents();
  }

  // Helper: Format Bytes to human readable
  function formatBytes(bytes) {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  }

  // Helper: Show Error Banner
  function showError(msg) {
    elements.errorMessage.textContent = msg || "An unknown error occurred.";
    elements.errorBanner.classList.remove("hidden");
  }

  // Helper: Hide Error Banner
  function hideError() {
    elements.errorBanner.classList.add("hidden");
    elements.errorMessage.textContent = "";
  }

  // ---------------------------------------------------------------------------
  // Upload Workflow & File Selection
  // ---------------------------------------------------------------------------

  function setupUploadEvents() {
    // Browse File Button
    elements.btnBrowse.addEventListener("click", (e) => {
      e.stopPropagation();
      elements.fileInput.click();
    });

    elements.dropZone.addEventListener("click", () => {
      elements.fileInput.click();
    });

    elements.fileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files[0]) {
        validateAndSelectFile(e.target.files[0]);
      }
    });

    // Drag & Drop
    ["dragenter", "dragover"].forEach((eventName) => {
      elements.dropZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        elements.dropZone.classList.add("drag-over");
      });
    });

    ["dragleave", "drop"].forEach((eventName) => {
      elements.dropZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        elements.dropZone.classList.remove("drag-over");
      });
    });

    elements.dropZone.addEventListener("drop", (e) => {
      const files = e.dataTransfer.files;
      if (files && files.length > 0) {
        validateAndSelectFile(files[0]);
      }
    });

    // Remove selected file
    elements.btnRemoveFile.addEventListener("click", (e) => {
      e.stopPropagation();
      clearSelectedFile();
    });

    // Process File Button
    elements.btnProcess.addEventListener("click", (e) => {
      e.stopPropagation();
      if (state.selectedFile) {
        startProcessing();
      }
    });

    // Close error banner
    elements.btnCloseError.addEventListener("click", hideError);
  }

  function validateAndSelectFile(file) {
    hideError();
    const ext = file.name.split(".").pop().toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      showError(`Unsupported file format '.${ext}'. Please upload a PDF or supported image.`);
      return;
    }

    if (file.size > MAX_FILE_SIZE) {
      showError(`File exceeds maximum allowed size of 50MB.`);
      return;
    }

    state.selectedFile = file;
    elements.fileName.textContent = file.name;
    elements.fileSize.textContent = formatBytes(file.size);

    elements.dropZone.classList.add("hidden");
    elements.fileCard.classList.remove("hidden");
  }

  function clearSelectedFile() {
    state.selectedFile = null;
    elements.fileInput.value = "";
    elements.fileCard.classList.add("hidden");
    elements.dropZone.classList.remove("hidden");
    hideError();
  }

  // ---------------------------------------------------------------------------
  // Processing Pipeline Execution
  // ---------------------------------------------------------------------------

  async function startProcessing() {
    if (!state.selectedFile) return;
    hideError();

    // Show processing view
    elements.uploadView.classList.add("hidden");
    elements.processingView.classList.remove("hidden");
    updateStepper(1, "Initializing workspace & uploading...");

    try {
      // 1. Create Job
      const createRes = await fetch("/api/jobs", { method: "POST" });
      if (!createRes.ok) throw new Error("Failed to create job workspace");
      const createData = await createRes.json();
      state.jobId = createData.job_id;

      // 2. Upload File
      updateStepper(1, `Uploading ${state.selectedFile.name}...`);
      const formData = new FormData();
      formData.append("file", state.selectedFile);

      const uploadRes = await fetch(`/api/jobs/${state.jobId}/upload`, {
        method: "POST",
        body: formData,
      });

      if (!uploadRes.ok) {
        const errJson = await uploadRes.json().catch(() => ({}));
        throw new Error(errJson.error || "File upload failed");
      }

      // 3. Process Document Pipeline
      updateStepper(2, "Running OCR layout analysis & formula reconstruction...");
      const processRes = await fetch(`/api/jobs/${state.jobId}/process`, {
        method: "POST",
      });

      if (!processRes.ok) {
        const errJson = await processRes.json().catch(() => ({}));
        throw new Error(errJson.error || "Document processing failed");
      }

      updateStepper(3, "Structuring document & generating LaTeX...");

      // Short pause for UX stepper
      await new Promise((r) => setTimeout(r, 400));

      updateStepper(4, "Rendering HTML and PDF previews...");

      // 4. Load Results
      await loadWorkspaceResults();
    } catch (err) {
      console.error(err);
      showError(err.message);
      // Fallback back to upload view
      elements.processingView.classList.add("hidden");
      elements.uploadView.classList.remove("hidden");
    }
  }

  function updateStepper(activeStepNum, statusMsg) {
    elements.processingStatusText.textContent = statusMsg;

    const steps = [
      elements.stepUpload,
      elements.stepOcr,
      elements.stepStruct,
      elements.stepPreview,
    ];

    steps.forEach((step, idx) => {
      const stepNum = idx + 1;
      step.classList.remove("step-active", "step-completed");
      if (stepNum < activeStepNum) {
        step.classList.add("step-completed");
      } else if (stepNum === activeStepNum) {
        step.classList.add("step-active");
      }
    });
  }

  // ---------------------------------------------------------------------------
  // Load Workspace Previews & Results
  // ---------------------------------------------------------------------------

  async function loadWorkspaceResults() {
    if (!state.jobId) return;

    try {
      // 1. Fetch HTML Preview
      const htmlRes = await fetch(`/api/jobs/${state.jobId}/preview/html`);
      if (htmlRes.ok) {
        const htmlStr = await htmlRes.text();
        elements.iframeHtml.srcdoc = htmlStr;
      }

      // 2. Fetch PDF Preview
      const pdfRes = await fetch(`/api/jobs/${state.jobId}/preview/pdf`);
      if (pdfRes.ok) {
        const pdfBlob = await pdfRes.blob();
        if (state.pdfBlobUrl) {
          URL.revokeObjectURL(state.pdfBlobUrl);
        }
        state.pdfBlobUrl = URL.createObjectURL(pdfBlob);
        elements.iframePdf.src = state.pdfBlobUrl;
      }

      // 3. Fetch LaTeX Source
      const latexRes = await fetch(`/api/jobs/${state.jobId}/latex`);
      if (latexRes.ok) {
        state.latexSource = await latexRes.text();
        elements.codeLatex.textContent = state.latexSource;
      }

      // Show Workspace View
      elements.processingView.classList.add("hidden");
      elements.workspaceView.classList.remove("hidden");
      elements.btnResetHeader.classList.remove("hidden");

      // Default to HTML Preview tab
      switchTab("html");
    } catch (err) {
      console.error("Error loading workspace results:", err);
      showError("Failed to load previews: " + err.message);
      elements.processingView.classList.add("hidden");
      elements.uploadView.classList.remove("hidden");
    }
  }

  // ---------------------------------------------------------------------------
  // Tabs & Action Event Handlers
  // ---------------------------------------------------------------------------

  function setupTabEvents() {
    elements.tabBtnHtml.addEventListener("click", () => switchTab("html"));
    elements.tabBtnPdf.addEventListener("click", () => switchTab("pdf"));
    elements.tabBtnLatex.addEventListener("click", () => switchTab("latex"));
  }

  function switchTab(tabName) {
    const tabs = [
      { btn: elements.tabBtnHtml, panel: elements.panelHtml, name: "html" },
      { btn: elements.tabBtnPdf, panel: elements.panelPdf, name: "pdf" },
      { btn: elements.tabBtnLatex, panel: elements.panelLatex, name: "latex" },
    ];

    tabs.forEach((tab) => {
      if (tab.name === tabName) {
        tab.btn.classList.add("active");
        tab.btn.setAttribute("aria-selected", "true");
        tab.panel.classList.remove("hidden");
        tab.panel.classList.add("active");
      } else {
        tab.btn.classList.remove("active");
        tab.btn.setAttribute("aria-selected", "false");
        tab.panel.classList.add("hidden");
        tab.panel.classList.remove("active");
      }
    });
  }

  function setupActionEvents() {
    // Copy LaTeX to Clipboard
    elements.btnCopyLatex.addEventListener("click", async () => {
      if (!state.latexSource) return;
      try {
        await navigator.clipboard.writeText(state.latexSource);
        const originalText = elements.btnCopyLatex.textContent;
        elements.btnCopyLatex.textContent = "✅ Copied!";
        setTimeout(() => {
          elements.btnCopyLatex.textContent = originalText;
        }, 2000);
      } catch (err) {
        showError("Failed to copy LaTeX code to clipboard.");
      }
    });

    // Download .tex file
    elements.btnDownloadTex.addEventListener("click", () => {
      if (!state.jobId) return;
      window.location.href = `/api/jobs/${state.jobId}/latex?download=true`;
    });

    // Reset / New Document
    elements.btnResetWorkspace.addEventListener("click", resetWorkspace);
    elements.btnResetHeader.addEventListener("click", resetWorkspace);
  }

  async function resetWorkspace() {
    if (state.jobId) {
      try {
        await fetch(`/api/jobs/${state.jobId}`, { method: "DELETE" });
      } catch (e) {
        console.warn("Failed to delete workspace:", e);
      }
    }

    if (state.pdfBlobUrl) {
      URL.revokeObjectURL(state.pdfBlobUrl);
      state.pdfBlobUrl = null;
    }

    state.jobId = null;
    state.selectedFile = null;
    state.latexSource = null;

    elements.iframeHtml.srcdoc = "";
    elements.iframePdf.src = "";
    elements.codeLatex.textContent = "";

    clearSelectedFile();

    elements.workspaceView.classList.add("hidden");
    elements.processingView.classList.add("hidden");
    elements.btnResetHeader.classList.add("hidden");
    elements.uploadView.classList.remove("hidden");

    hideError();
  }

  // Initialize Application on DOM Ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
