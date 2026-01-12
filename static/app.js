// static/app.js
// UI logic for Upload + Results pages
// Clean, safe, production-ready

(function () {
  "use strict";

  /* =========================
     UTILITIES
  ========================= */
  function el(id) {
    return document.getElementById(id);
  }

  function qselAll(sel, ctx) {
    return Array.from((ctx || document).querySelectorAll(sel));
  }

  function formatBytes(bytes) {
    if (bytes === 0) return "0 B";
    const units = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, i)).toFixed(1) + " " + units[i];
  }

  /* =====================================================
     PAGE 1 — UPLOAD PAGE LOGIC
  ===================================================== */
  function bindUploadPage() {
    const uploadForm = el("uploadForm");
    const fileInput = el("fileInput");
    const uploadBox = el("uploadBox");
    const browseBtn = el("browseBtn");
    const fileInfo = el("fileInfo");
    const clearBtn = el("clearBtn");

    // Not upload page
    if (!uploadForm || !fileInput || !uploadBox) return;

    /* ---------- Helpers ---------- */
    function showFile(files) {
      if (!files || files.length === 0) {
        fileInfo.textContent = "";
        return;
      }
      const f = files[0];
      fileInfo.textContent = `${f.name} (${formatBytes(f.size)})`;
    }

    /* ---------- Click handling ---------- */
    uploadBox.addEventListener("click", () => {
      fileInput.click();
    });

    if (browseBtn) {
      browseBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        fileInput.click();
      });
    }

    /* ---------- File selection ---------- */
    fileInput.addEventListener("change", () => {
      showFile(fileInput.files);
    });

    /* ---------- Drag & Drop ---------- */
    uploadBox.addEventListener("dragover", (e) => {
      e.preventDefault();
      uploadBox.classList.add("dragover");
    });

    uploadBox.addEventListener("dragleave", () => {
      uploadBox.classList.remove("dragover");
    });

    uploadBox.addEventListener("drop", (e) => {
      e.preventDefault();
      uploadBox.classList.remove("dragover");
      fileInput.files = e.dataTransfer.files;
      showFile(e.dataTransfer.files);
    });

    /* ---------- Clear ---------- */
    if (clearBtn) {
      clearBtn.addEventListener("click", () => {
        fileInput.value = "";
        fileInfo.textContent = "";
      });
    }

    /* ---------- Submit protection ---------- */
    uploadForm.addEventListener("submit", () => {
      const submitBtn = uploadForm.querySelector('button[type="submit"]');
      if (submitBtn) submitBtn.disabled = true;

      const overlay = document.createElement("div");
      overlay.id = "upload-overlay";
      Object.assign(overlay.style, {
        position: "fixed",
        inset: "0",
        background: "rgba(255, 255, 255, 0.98)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: "9999",
        fontSize: "18px",
        fontFamily: "Poppins, sans-serif",
      });
      overlay.innerHTML = `
  <div style="display:flex;flex-direction:column;align-items:center;gap:18px;">
    
    <!-- Spinner -->
    <div class="loader-spinner"></div>

    <!-- Text -->
    <div style="
      font-size:16px;
      font-weight:600;
      color:#1e293b;
      letter-spacing:0.3px;">
      Analyzing your resume…
    </div>

    <!-- Sub text -->
    <div style="
      font-size:13px;
      color:#64748b;">
      Parsing • Scoring • ATS Optimization
    </div>
  </div>
`;

      document.body.appendChild(overlay);
    });
  }

  /* =====================================================
     PAGE 2 — RESULTS PAGE HELPERS
  ===================================================== */
  function bindResultsPage() {
    // Toggle preview
    qselAll("[data-toggle-preview]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const target = el(btn.dataset.togglePreview);
        if (!target) return;
        const hidden = target.style.display === "none";
        target.style.display = hidden ? "block" : "none";
        btn.textContent = hidden ? "Hide preview" : "Show preview";
      });
    });

    // Copy preview
    qselAll(".copy-preview").forEach((btn) => {
      btn.addEventListener("click", () => {
        const target = el(btn.dataset.copyTarget);
        if (!target) return;

        navigator.clipboard.writeText(target.innerText || "").then(() => {
          const old = btn.textContent;
          btn.textContent = "Copied!";
          setTimeout(() => (btn.textContent = old), 1200);
        });
      });
    });

    // Download confirm
    qselAll("a.download-file").forEach((a) => {
      a.addEventListener("click", (e) => {
        if (!confirm("Download this file?")) e.preventDefault();
      });
    });
  }

  /* =====================================================
     INIT
  ===================================================== */
  document.addEventListener("DOMContentLoaded", () => {
    bindUploadPage();
    bindResultsPage();
  });
})();
