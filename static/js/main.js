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
