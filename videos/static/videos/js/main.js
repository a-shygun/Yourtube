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

async function postForm(form) {
  const response = await fetch(form.action, {
    method: "POST",
    body: new FormData(form),
    headers: { Accept: "application/json" },
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "The request failed.");
  return result;
}

document.querySelectorAll("[data-compact-count]").forEach((element) => {
  element.textContent = compactCount(element.dataset.compactCount);
});

document.querySelectorAll("[data-video-duration]").forEach((element) => {
  element.textContent = formatDuration(element.dataset.videoDuration);
});

document.querySelectorAll("[data-hours]").forEach((element) => {
  const seconds = Number(element.dataset.hours);
  element.textContent = `${(seconds / 3600).toFixed(1)} h`;
});

document.querySelectorAll("[data-favorite-form]").forEach((form) => {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector("button[type='submit']");
    if (!button || button.disabled) return;

    button.disabled = true;
    try {
      const { favorited } = await postForm(form);
      const label = favorited ? "Remove from favorites" : "Add to favorites";
      button.setAttribute("aria-label", label);
      button.title = label;
      button.classList.toggle("text-amber-300", favorited);
      button.querySelector("svg")?.setAttribute("fill", favorited ? "currentColor" : "none");
      const text = button.querySelector("[data-favorite-label]");
      if (text) text.textContent = favorited ? "Favorited" : "Favorite";

      if (!favorited && form.dataset.removeOnUnfavorite) {
        form.closest("[data-favorite-card]")?.remove();
      }
    } catch {
      button.title = "Could not update favorite. Try again.";
    } finally {
      button.disabled = false;
    }
  });
});

document.querySelectorAll("[data-status-form]").forEach((form) => {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const card = form.closest("[data-video-card]");
    const statusForms = card?.querySelectorAll("[data-status-form]");
    const buttons = statusForms?.length
      ? [...statusForms].map((statusForm) => statusForm.querySelector("button[type='submit']"))
      : [form.querySelector("button[type='submit']")];
    if (!buttons[0] || buttons[0].disabled) return;
    buttons.forEach((button) => { if (button) button.disabled = true; });

    try {
      const { status } = await postForm(form);
      if (statusForms?.length) {
        statusForms.forEach((statusForm) => {
          const target = statusForm.dataset.statusTarget;
          const active = status === target;
          let statusInput = statusForm.querySelector("input[name='status']");
          if (!statusInput) {
            statusInput = document.createElement("input");
            statusInput.type = "hidden";
            statusInput.name = "status";
            statusForm.append(statusInput);
          }
          statusInput.value = active ? "" : target;
          statusForm.classList.toggle("opacity-0", !active);

          const button = statusForm.querySelector("button[type='submit']");
          button.textContent = target === "watched" && !active ? "Mark watched" : target === "watched" ? "Watched" : "To watch";
          button.setAttribute("aria-label", active
            ? `Remove ${target === "watched" ? "watched" : "to-watch"} status`
            : target === "watched" ? "Mark watched" : "Mark to watch");
        });
      } else if (form.closest("[data-detail-status-group]")) {
        const group = form.closest("[data-detail-status-group]");
        group.querySelectorAll("[data-status-form]").forEach((statusForm) => {
          const target = statusForm.dataset.statusTarget;
          const active = status === target;
          statusForm.querySelector("input[name='status']").value = active ? "none" : target;
          const button = statusForm.querySelector("button[type='submit']");
          button.setAttribute("aria-pressed", String(active));
          button.classList.toggle("border-accent", active);
          button.classList.toggle("bg-accent", active);
          button.classList.toggle("text-white", active);
          button.classList.toggle("border-input-border", !active);
        });
      } else {
        const select = form.querySelector("select[name='status']");
        if (select) select.value = status;
        const button = buttons[0];
        button.textContent = "Saved";
        setTimeout(() => { button.textContent = "Save"; }, 1500);
      }
    } catch (error) {
      buttons[0].title = error.message;
    } finally {
      buttons.forEach((button) => { if (button) button.disabled = false; });
    }
  });
});

document.querySelectorAll("[data-delete-form]").forEach((form) => {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!window.confirm(form.dataset.confirmDelete)) return;

    const button = form.querySelector("button[type='submit']");
    if (!button || button.disabled) return;
    button.disabled = true;
    try {
      await postForm(form);
      form.closest("[data-video-card]")?.remove();
    } catch (error) {
      button.title = error.message;
      button.disabled = false;
    }
  });
});

const catalogSort = document.querySelector("#sort-catalog");
catalogSort?.addEventListener("change", () => catalogSort.form?.requestSubmit());

document.querySelector("[data-site-search]")?.addEventListener("submit", (event) => {
  const token = event.currentTarget.querySelector("input[name='csrfmiddlewaretoken']");
  if (token) token.disabled = event.submitter?.name !== "index_category";
});

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

const playbackVideo = document.querySelector("video");
if (playbackVideo) {
  document.addEventListener("keydown", (event) => {
    const target = event.target;
    const isTyping = target instanceof HTMLElement && (
      target.isContentEditable ||
      ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)
    );
    if (isTyping || event.altKey || event.ctrlKey || event.metaKey) return;

    const offset = event.key === "ArrowRight" ? 15 : event.key === "ArrowLeft" ? -15 : 0;
    if (!offset) return;

    event.preventDefault();
    event.stopImmediatePropagation();
    const duration = Number.isFinite(playbackVideo.duration) ? playbackVideo.duration : Infinity;
    playbackVideo.currentTime = Math.max(0, Math.min(duration, playbackVideo.currentTime + offset));
  }, { capture: true });
}

