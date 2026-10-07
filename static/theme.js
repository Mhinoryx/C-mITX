"use strict";
(() => {
  const storageKey = "cem-itx-theme";
  const root = document.documentElement;
  function applyTheme(theme) {
    root.dataset.theme = theme === "dark" ? "dark" : "classic";
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", theme === "dark" ? "#141916" : "#faf8f4");
    for (const button of document.querySelectorAll("[data-theme-choice]")) {
      button.setAttribute("aria-pressed", String(button.dataset.themeChoice === root.dataset.theme));
    }
  }
  let savedTheme = "classic";
  try { savedTheme = localStorage.getItem(storageKey) || "classic"; } catch {}
  applyTheme(savedTheme);
  document.addEventListener("DOMContentLoaded", () => {
    applyTheme(root.dataset.theme);
    for (const button of document.querySelectorAll("[data-theme-choice]")) {
      button.addEventListener("click", () => {
        applyTheme(button.dataset.themeChoice);
        try { localStorage.setItem(storageKey, root.dataset.theme); } catch {}
      });
    }
  });
})();
