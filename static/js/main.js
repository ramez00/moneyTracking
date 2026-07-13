// main.js — students will add JavaScript here as features are built

document.addEventListener("DOMContentLoaded", function () {
  var trigger = document.getElementById("how-it-works-trigger");
  var overlay = document.getElementById("how-it-works-overlay");
  var closeBtn = document.getElementById("how-it-works-close");

  if (!trigger || !overlay || !closeBtn) return;

  function openModal() {
    overlay.hidden = false;
  }

  function closeModal() {
    overlay.hidden = true;
  }

  trigger.addEventListener("click", openModal);
  closeBtn.addEventListener("click", closeModal);

  overlay.addEventListener("click", function (event) {
    if (event.target === overlay) {
      closeModal();
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && !overlay.hidden) {
      closeModal();
    }
  });
});

document.addEventListener("DOMContentLoaded", function () {
  var picker = document.getElementById("theme-picker");
  var colorInput = document.getElementById("theme-base-color");
  var presetsWrap = document.getElementById("theme-presets");
  var swatchesWrap = document.getElementById("theme-swatches");
  var previewBtn = document.getElementById("theme-preview-btn");
  var previewBadge = document.getElementById("theme-preview-badge");
  var previewBar = document.getElementById("theme-preview-bar");
  var applyBtn = document.getElementById("theme-apply-btn");
  var resetBtn = document.getElementById("theme-reset-btn");
  var toast = document.getElementById("theme-toast");

  if (!picker || !colorInput) return;

  var DEFAULT_COLOR = "#1a472a";
  var debounceTimer = null;
  var toastHideTimer = null;

  var i18n = {
    saved: picker.getAttribute("data-i18n-saved"),
    reset: picker.getAttribute("data-i18n-reset"),
    error: picker.getAttribute("data-i18n-error"),
    copied: picker.getAttribute("data-i18n-copied"),
  };

  function showToast(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.hidden = false;
    window.clearTimeout(toastHideTimer);
    toastHideTimer = window.setTimeout(function () {
      toast.hidden = true;
    }, 2000);
  }

  function applyPaletteVars(palette) {
    var root = document.documentElement;
    root.style.setProperty("--accent", palette.primary);
    root.style.setProperty("--accent-light", palette.primary_light);
    root.style.setProperty("--accent-2", palette.accent_2);
    root.style.setProperty("--accent-2-light", palette.accent_2_light);
  }

  function clearPaletteVars() {
    var root = document.documentElement;
    root.style.removeProperty("--accent");
    root.style.removeProperty("--accent-light");
    root.style.removeProperty("--accent-2");
    root.style.removeProperty("--accent-2-light");
  }

  function updatePreview(palette) {
    if (previewBtn) previewBtn.style.background = palette.primary;
    if (previewBadge) {
      previewBadge.style.background = palette.primary_light;
      previewBadge.style.color = palette.primary;
    }
    if (previewBar) previewBar.style.background = palette.primary;
  }

  function renderSwatches(palette) {
    if (!swatchesWrap) return;
    swatchesWrap.innerHTML = "";
    var colors = [
      palette.primary,
      palette.primary_light,
      palette.primary_dark,
      palette.accent_2,
      palette.accent_2_light,
    ];
    colors.forEach(function (hex) {
      var swatch = document.createElement("button");
      swatch.type = "button";
      swatch.className = "theme-swatch";
      swatch.style.background = hex;
      swatch.title = hex;
      swatch.addEventListener("click", function () {
        if (navigator.clipboard) {
          navigator.clipboard.writeText(hex).then(function () {
            showToast(hex + " " + (i18n.copied || "copied"));
          });
        }
      });
      swatchesWrap.appendChild(swatch);
    });
  }

  function generatePalette(color) {
    fetch("/api/generate-palette", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ base_color: color }),
    })
      .then(function (response) {
        if (!response.ok) throw new Error("generate failed");
        return response.json();
      })
      .then(function (palette) {
        applyPaletteVars(palette);
        updatePreview(palette);
        renderSwatches(palette);
      })
      .catch(function () {
        showToast(i18n.error || "Something went wrong");
      });
  }

  function onColorChange(color) {
    colorInput.value = color;
    window.clearTimeout(debounceTimer);
    debounceTimer = window.setTimeout(function () {
      generatePalette(color);
    }, 150);
  }

  colorInput.addEventListener("input", function () {
    onColorChange(colorInput.value);
  });

  if (presetsWrap) {
    presetsWrap.addEventListener("click", function (event) {
      var target = event.target.closest(".theme-preset");
      if (!target) return;
      onColorChange(target.getAttribute("data-color"));
    });
  }

  if (applyBtn) {
    applyBtn.addEventListener("click", function () {
      fetch("/api/save-theme", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ base_color: colorInput.value }),
      })
        .then(function (response) {
          if (!response.ok) throw new Error("save failed");
          return response.json();
        })
        .then(function () {
          showToast(i18n.saved || "Saved");
        })
        .catch(function () {
          showToast(i18n.error || "Something went wrong");
        });
    });
  }

  if (resetBtn) {
    resetBtn.addEventListener("click", function () {
      fetch("/api/reset-theme", { method: "POST" })
        .then(function (response) {
          if (!response.ok) throw new Error("reset failed");
          clearPaletteVars();
          colorInput.value = DEFAULT_COLOR;
          if (swatchesWrap) swatchesWrap.innerHTML = "";
          showToast(i18n.reset || "Reset");
        })
        .catch(function () {
          showToast(i18n.error || "Something went wrong");
        });
    });
  }

  // Restore the saved theme (if any) on page load.
  fetch("/api/theme")
    .then(function (response) {
      if (!response.ok) throw new Error("load failed");
      return response.json();
    })
    .then(function (theme) {
      if (!theme || !theme.base_color || !theme.palette) return;
      colorInput.value = theme.base_color;
      applyPaletteVars(theme.palette);
      updatePreview(theme.palette);
      renderSwatches(theme.palette);
    })
    .catch(function () {});
});
