function compactCount(value) {
  const count = Number(value);
  if (!Number.isFinite(count)) return value;
  if (count < 1_000) return String(count);

  let divisor;
  let suffix;
  if (count >= 1_000_000_000) {
    divisor = 1_000_000_000;
    suffix = "b";
  } else if (count >= 1_000_000) {
    divisor = 1_000_000;
    suffix = "m";
  } else {
    divisor = 1_000;
    suffix = "k";
  }

  let amount = count / divisor;
  if (amount >= 999.95 && suffix === "k") {
    amount = 1;
    suffix = "m";
  } else if (amount >= 999.95 && suffix === "m") {
    amount = 1;
    suffix = "b";
  }

  return `${parseFloat(amount.toFixed(1))}${suffix}`;
}

function formatDuration(value) {
  const totalSeconds = Number(value);
  if (!Number.isFinite(totalSeconds) || totalSeconds < 0) return value;

  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const paddedSeconds = String(seconds).padStart(2, "0");

  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${paddedSeconds}`;
  }
  return `${minutes}:${paddedSeconds}`;
}

document.querySelectorAll("[data-compact-count]").forEach((element) => {
  element.textContent = compactCount(element.dataset.compactCount);
});

document.querySelectorAll("[data-video-duration]").forEach((element) => {
  element.textContent = formatDuration(element.dataset.videoDuration);
});

const profileImageForm = document.querySelector("#profile-image-form");
const profileImageInput = profileImageForm?.querySelector('input[type="file"]');
profileImageInput?.addEventListener("change", () => {
  if (profileImageInput.files.length) profileImageForm.requestSubmit();
});

const catalogSort = document.querySelector("#sort-catalog");
catalogSort?.addEventListener("change", () => catalogSort.form?.requestSubmit());

const catalogSidebar = document.querySelector("#catalog-sidebar");
const catalogSidebarToggle = catalogSidebar?.querySelector("[data-catalog-sidebar-toggle]");
const catalogSidebarContent = catalogSidebar?.querySelector("[data-catalog-sidebar-content]");
const catalogSidebarLabel = catalogSidebar?.querySelector("[data-catalog-sidebar-label]");
const catalogSidebarIcon = catalogSidebar?.querySelector("[data-catalog-sidebar-icon]");

if (catalogSidebar && catalogSidebarToggle && catalogSidebarContent) {
  const setSidebarCollapsed = (collapsed) => {
    catalogSidebarContent.hidden = collapsed;
    catalogSidebar.classList.toggle("lg:w-64", !collapsed);
    catalogSidebar.classList.toggle("lg:w-16", collapsed);
    catalogSidebarToggle.classList.toggle("justify-between", !collapsed);
    catalogSidebarToggle.classList.toggle("justify-center", collapsed);
    catalogSidebarToggle.setAttribute("aria-expanded", String(!collapsed));
    catalogSidebarToggle.setAttribute("aria-label", collapsed ? "Expand library menu" : "Collapse library menu");
    if (catalogSidebarLabel) catalogSidebarLabel.hidden = collapsed;
    if (catalogSidebarIcon) catalogSidebarIcon.textContent = collapsed ? "›" : "‹";
  };

  try {
    setSidebarCollapsed(localStorage.getItem("yourtube-sidebar-collapsed") === "true");
  } catch {
    setSidebarCollapsed(false);
  }
  catalogSidebarToggle.addEventListener("click", () => {
    const collapsed = catalogSidebarToggle.getAttribute("aria-expanded") === "true";
    setSidebarCollapsed(collapsed);
    try {
      localStorage.setItem("yourtube-sidebar-collapsed", String(collapsed));
    } catch {
      // The sidebar remains usable for this page when browser storage is unavailable.
    }
  });
}

document.querySelectorAll("[data-expandable-text]").forEach((text) => {
  const toggle = text.nextElementSibling;
  if (!toggle || !toggle.matches("[data-expand-toggle]")) return;

  if (text.scrollHeight > text.clientHeight) toggle.hidden = false;
  toggle.addEventListener("click", () => {
    const expanded = toggle.getAttribute("aria-expanded") === "true";
    text.classList.toggle("line-clamp-5", expanded);
    toggle.setAttribute("aria-expanded", String(!expanded));
    toggle.textContent = expanded ? "View more" : "View less";
  });
});

document.querySelectorAll("[data-replies-toggle]").forEach((toggle) => {
  const replies = document.getElementById(toggle.getAttribute("aria-controls"));
  if (!replies) return;

  toggle.addEventListener("click", () => {
    const expanded = toggle.getAttribute("aria-expanded") === "true";
    replies.classList.toggle("hidden", expanded);
    toggle.setAttribute("aria-expanded", String(!expanded));
    toggle.textContent = expanded ? "View replies" : "Hide replies";
  });
});

const themeToggle = document.querySelector("#theme-toggle");

function setTheme(theme) {
  document.documentElement.dataset.theme = theme;
  if (themeToggle) {
    const nextTheme = theme === "dark" ? "light" : "dark";
    const isLight = theme === "light";
    themeToggle.querySelectorAll("[data-theme-icon]").forEach((icon) => {
      icon.style.display = icon.dataset.themeIcon === theme ? "block" : "none";
    });
    themeToggle.setAttribute("aria-checked", String(isLight));
    themeToggle.setAttribute("aria-pressed", String(isLight));
    themeToggle.setAttribute("aria-label", `Switch to ${nextTheme} mode`);
    themeToggle.title = `Switch to ${nextTheme} mode`;
  }
}

if (themeToggle) {
  let savedTheme = "dark";
  try {
    savedTheme = localStorage.getItem("yourtube-theme") || "dark";
  } catch {
    // The toggle still works when browser storage is unavailable.
  }
  setTheme(savedTheme === "light" ? "light" : "dark");
  themeToggle.addEventListener("click", () => {
    const nextTheme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    try {
      localStorage.setItem("yourtube-theme", nextTheme);
    } catch {
      // Keep the selected theme for this page even when it cannot be saved.
    }
    setTheme(nextTheme);
  });
}

const accountMenu = document.querySelector("#account-menu");
const accountMenuToggle = document.querySelector("#account-menu-toggle");
const accountMenuPanel = document.querySelector("#account-menu-panel");

if (accountMenu && accountMenuToggle && accountMenuPanel) {
  const setAccountMenuOpen = (open) => {
    accountMenuPanel.hidden = !open;
    accountMenuToggle.setAttribute("aria-expanded", String(open));
  };

  accountMenuToggle.addEventListener("click", () => {
    setAccountMenuOpen(accountMenuPanel.hidden);
  });
  document.addEventListener("click", (event) => {
    if (!accountMenu.contains(event.target)) setAccountMenuOpen(false);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !accountMenuPanel.hidden) {
      setAccountMenuOpen(false);
      accountMenuToggle.focus();
    }
  });
}

