// static/index.js (Variant C)
document.addEventListener("DOMContentLoaded", function () {
  const fileInput = document.getElementById("fileInput");
  const fileInfo = document.getElementById("fileInfo");
  const clearBtn = document.getElementById("clearBtn");
  fileInfo.textContent = "";
  fileInput.addEventListener("change", () => {
    const f = fileInput.files;
    if (!f || f.length === 0) fileInfo.textContent = "";
    else if (f.length === 1) fileInfo.textContent = f[0].name;
    else fileInfo.textContent = `${f.length} files selected`;
  });
  clearBtn.addEventListener("click", () => { if (fileInput) fileInput.value = ""; fileInfo.textContent = ""; });
});
