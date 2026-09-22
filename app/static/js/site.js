document.documentElement.classList.add("js-enabled");

document.addEventListener("DOMContentLoaded", () => {
  if (window.lucide) window.lucide.createIcons();

  const panels = [...document.querySelectorAll(".panel")];
  const links = [...document.querySelectorAll("[data-section-link]")];
  const navLinks = [...document.querySelectorAll(".section-nav [data-section-link]")];
  const panelMobileMedia = window.matchMedia("(max-width: 820px), (max-height: 620px) and (max-width: 1100px)");
  const reducedMotionMedia = window.matchMedia("(prefers-reduced-motion: reduce)");

  const updateActiveSection = (id) => {
    links.forEach((link) => link.classList.toggle("is-active", link.dataset.sectionLink === id));
    navLinks.forEach((link) => {
      if (link.dataset.sectionLink === id) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
  };

  const activate = (id, updateHash = true, scrollToPanel = true) => {
    const target = document.getElementById(id);
    if (!target || !target.classList.contains("panel")) return;

    panels.forEach((panel) => {
      const isActive = panel.id === id;
      panel.classList.toggle("is-active", isActive);
      panel.toggleAttribute("hidden", panelMobileMedia.matches && !isActive);
    });
    target.scrollTop = 0;
    if (panelMobileMedia.matches && scrollToPanel) {
      target.scrollIntoView({ behavior: reducedMotionMedia.matches ? "auto" : "smooth", block: "start" });
    }
    updateActiveSection(id);
    document.title = `${target.dataset.title} · Mustafa Yücel`;
    if (updateHash) history.replaceState(null, "", `#${id}`);
  };

  links.forEach((link) => link.addEventListener("click", (event) => {
    const id = link.dataset.sectionLink;
    if (id && document.getElementById(id)) {
      event.preventDefault();
      activate(id);
    }
  }));

  const initial = window.location.hash.slice(1);
  const initialPanel = initial && document.getElementById(initial)?.classList.contains("panel")
    ? initial
    : panels.find((panel) => panel.classList.contains("is-active"))?.id;
  if (initialPanel) activate(initialPanel, false, Boolean(initial));
  window.addEventListener("hashchange", () => activate(window.location.hash.slice(1), false));
  panelMobileMedia.addEventListener("change", () => {
    panels.forEach((panel) => panel.toggleAttribute("hidden", panelMobileMedia.matches && !panel.classList.contains("is-active")));
  });

  const skipLink = document.querySelector(".skip-link");
  const portfolioMenuToggle = document.querySelector(".portfolio-menu-toggle");
  const portfolioMenu = document.querySelector(".portfolio-menu");
  const portfolioMenuBackdrop = document.querySelector(".portfolio-menu-backdrop");
  const pageStage = document.querySelector(".page-stage");
  const mobileSiteHeader = document.querySelector(".mobile-site-header");
  if (portfolioMenuToggle && portfolioMenu && portfolioMenuBackdrop) {
    const setPortfolioMenu = (isOpen) => {
      const isMobile = panelMobileMedia.matches;
      const shouldOpen = isMobile && isOpen;
      const focusWasInMenu = portfolioMenu.contains(document.activeElement);
      document.body.classList.toggle("portfolio-menu-open", shouldOpen);
      portfolioMenu.classList.toggle("is-open", shouldOpen);
      portfolioMenu.toggleAttribute("inert", isMobile && !shouldOpen);
      pageStage?.toggleAttribute("inert", shouldOpen);
      mobileSiteHeader?.toggleAttribute("inert", shouldOpen);
      skipLink?.toggleAttribute("inert", shouldOpen);
      portfolioMenuBackdrop.classList.toggle("is-visible", shouldOpen);
      portfolioMenuBackdrop.setAttribute("aria-hidden", String(!shouldOpen));
      portfolioMenuBackdrop.tabIndex = shouldOpen ? 0 : -1;
      portfolioMenuToggle.setAttribute("aria-expanded", String(shouldOpen));
      portfolioMenuToggle.setAttribute("aria-label", shouldOpen ? "Menüyü kapat" : "Menüyü aç");
      if (shouldOpen) window.requestAnimationFrame(() => {
        (portfolioMenu.querySelector(".section-nav a.is-active") || portfolioMenu.querySelector(".section-nav a"))?.focus({ preventScroll: true });
      });
      else if (isMobile && focusWasInMenu) portfolioMenuToggle.focus();
    };

    portfolioMenuToggle.addEventListener("click", () => {
      setPortfolioMenu(portfolioMenuToggle.getAttribute("aria-expanded") !== "true");
    });
    portfolioMenuBackdrop.addEventListener("click", () => {
      setPortfolioMenu(false);
      portfolioMenuToggle.focus();
    });
    portfolioMenu.addEventListener("click", (event) => {
      if (event.target.closest("[data-section-link]") && panelMobileMedia.matches) setPortfolioMenu(false);
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && portfolioMenuToggle.getAttribute("aria-expanded") === "true") {
        setPortfolioMenu(false);
        portfolioMenuToggle.focus();
      }
    });
    panelMobileMedia.addEventListener("change", () => setPortfolioMenu(false));
    setPortfolioMenu(false);
  }

  const adminMenuToggle = document.querySelector(".admin-menu-toggle");
  const adminMenu = document.querySelector(".admin-sidebar");
  const adminMenuBackdrop = document.querySelector(".admin-menu-backdrop");
  const adminMain = document.querySelector(".admin-main");
  if (adminMenuToggle && adminMenu && adminMenuBackdrop) {
    const adminMenuMedia = window.matchMedia("(max-width: 760px), (max-height: 620px) and (max-width: 1100px)");
    const setAdminMenu = (isOpen) => {
      const isMobile = adminMenuMedia.matches;
      const shouldOpen = isMobile && isOpen;
      const focusWasInMenu = adminMenu.contains(document.activeElement);
      document.body.classList.toggle("admin-menu-open", shouldOpen);
      adminMenu.classList.toggle("is-open", shouldOpen);
      adminMenu.toggleAttribute("inert", isMobile && !shouldOpen);
      adminMain?.toggleAttribute("inert", shouldOpen);
      skipLink?.toggleAttribute("inert", shouldOpen);
      adminMenuBackdrop.classList.toggle("is-visible", shouldOpen);
      adminMenuToggle.setAttribute("aria-expanded", String(shouldOpen));
      adminMenuBackdrop.setAttribute("aria-hidden", String(!shouldOpen));
      adminMenuBackdrop.tabIndex = shouldOpen ? 0 : -1;
      adminMenuToggle.querySelector("span").textContent = shouldOpen ? "Kapat" : "Menü";
      if (shouldOpen) window.requestAnimationFrame(() => {
        (adminMenu.querySelector("a.is-active") || adminMenu.querySelector("a"))?.focus();
      });
      else if (isMobile && focusWasInMenu) adminMenuToggle.focus();
    };

    adminMenuToggle.addEventListener("click", () => {
      setAdminMenu(adminMenuToggle.getAttribute("aria-expanded") !== "true");
    });
    adminMenuBackdrop.addEventListener("click", () => {
      setAdminMenu(false);
      adminMenuToggle.focus();
    });
    adminMenu.addEventListener("click", (event) => {
      if (event.target.closest("a") && adminMenuMedia.matches) setAdminMenu(false);
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && adminMenuToggle.getAttribute("aria-expanded") === "true") {
        setAdminMenu(false);
        adminMenuToggle.focus();
      }
    });
    adminMenuMedia.addEventListener("change", () => setAdminMenu(false));
    setAdminMenu(false);
  }

  document.querySelectorAll("[data-collection-dialog]").forEach((dialog) => {
    const form = dialog.querySelector("form");
    const baseUrl = dialog.dataset.baseUrl;
    const isEditing = dialog.dataset.editing === "true";
    const openOnLoad = dialog.hasAttribute("data-open-on-load");
    let opener;
    let isClosing = false;
    let isDirty = false;

    const openDialog = (trigger) => {
      if (dialog.open) return;
      opener = trigger;
      isClosing = false;
      dialog.classList.remove("is-closing");
      document.body.classList.add("admin-dialog-open");
      dialog.showModal();
      if (window.matchMedia("(hover: hover) and (pointer: fine)").matches) {
        window.requestAnimationFrame(() => {
          const firstField = form.querySelector('input:not([type="hidden"]):not(.image-picker__input), textarea:not([hidden]), select');
          firstField?.focus({ preventScroll: true });
        });
      }
    };

    const finishClose = () => {
      document.body.classList.remove("admin-dialog-open");
      isDirty = false;
      if (isEditing) {
        window.location.replace(baseUrl);
        return;
      }
      isDirty = false;
      form.reset();
      dialog.close();
      if (openOnLoad) history.replaceState(null, "", baseUrl);
      dialog.classList.remove("is-closing");
      isClosing = false;
      opener?.focus({ preventScroll: true });
    };

    const closeDialog = () => {
      if (!dialog.open || isClosing) return;
      if (isDirty && !window.confirm("Kaydedilmemiş değişiklikler silinsin mi?")) return;
      isClosing = true;
      dialog.classList.add("is-closing");
      window.setTimeout(finishClose, reducedMotionMedia.matches ? 0 : 160);
    };

    document.querySelectorAll("[data-collection-open]").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        openDialog(button);
      });
    });
    dialog.querySelectorAll("[data-collection-close]").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        closeDialog();
      });
    });
    dialog.addEventListener("cancel", (event) => {
      event.preventDefault();
      closeDialog();
    });
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) closeDialog();
    });
    form.addEventListener("input", () => { isDirty = true; });
    form.addEventListener("change", () => { isDirty = true; });
    form.addEventListener("click", (event) => {
      if (event.target.closest("[data-remove-image], .tag-chip button")) isDirty = true;
    });
    form.addEventListener("submit", () => { isDirty = false; });
    window.addEventListener("beforeunload", (event) => {
      if (!isDirty) return;
      event.preventDefault();
      event.returnValue = "";
    });
    if (openOnLoad) {
      dialog.removeAttribute("open");
      window.requestAnimationFrame(() => openDialog());
    }
  });

  document.querySelectorAll("form[data-confirm]").forEach((form) => form.addEventListener("submit", (event) => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  }));

  const blogEditorForm = document.querySelector(".blog-editor-form");
  const markdownEditor = document.querySelector("[data-markdown-editor]");
  const editorCount = document.querySelector("[data-editor-count]");
  if (markdownEditor && editorCount) {
    const updateCount = () => {
      const words = markdownEditor.value.trim().match(/\S+/g)?.length || 0;
      editorCount.textContent = `${words} kelime`;
    };
    markdownEditor.addEventListener("input", updateCount);
    updateCount();
  }

  const editorModeButtons = document.querySelectorAll("[data-editor-mode]");
  const editorWritePane = document.querySelector('[data-editor-pane="write"]');
  const editorPreviewPane = document.querySelector('[data-editor-pane="preview"]');
  const markdownPreview = document.querySelector("[data-markdown-preview]");
  if (markdownEditor && editorModeButtons.length && editorWritePane && editorPreviewPane && markdownPreview) {
    let previewRequest;

    const renderPreview = async () => {
      if (!markdownEditor.value.trim()) {
        markdownPreview.innerHTML = '<div class="editor-preview__empty"><i data-lucide="file-search"></i><span>Önizlemek için içerik yazın.</span></div>';
        if (window.lucide) window.lucide.createIcons();
        return;
      }
      previewRequest?.abort();
      previewRequest = new AbortController();
      const formData = new FormData();
      formData.append("body", markdownEditor.value);
      formData.append("csrf_token", document.querySelector('.blog-editor-form [name="csrf_token"]').value);
      editorPreviewPane.classList.add("is-loading");
      try {
        const response = await fetch(editorPreviewPane.dataset.previewUrl, {
          method: "POST",
          body: formData,
          signal: previewRequest.signal,
        });
        if (!response.ok) throw new Error();
        markdownPreview.innerHTML = await response.text();
      } catch (error) {
        if (error.name !== "AbortError") markdownPreview.innerHTML = '<div class="editor-preview__empty"><span>Önizleme yüklenemedi.</span></div>';
      } finally {
        editorPreviewPane.classList.remove("is-loading");
      }
    };

    editorModeButtons.forEach((button) => button.addEventListener("click", () => {
      const showPreview = button.dataset.editorMode === "preview";
      editorModeButtons.forEach((item) => {
        const isActive = item === button;
        item.classList.toggle("is-active", isActive);
        item.setAttribute("aria-pressed", String(isActive));
      });
      editorWritePane.classList.toggle("is-hidden", showPreview);
      editorPreviewPane.classList.toggle("is-hidden", !showPreview);
      if (showPreview) renderPreview();
      else markdownEditor.focus();
    }));
  }

  const editorDropzone = document.querySelector(".editor-dropzone");
  const uploadStatus = document.querySelector("[data-upload-status]");
  if (markdownEditor && editorDropzone && uploadStatus) {
    const editorImageInput = document.querySelector("[data-editor-image-input]");
    const editorSaveButton = blogEditorForm?.querySelector('.editor-save[type="submit"]');
    const mediaLibrary = document.querySelector("[data-media-library]");
    const mediaGrid = document.querySelector("[data-media-grid]");
    const mediaCount = document.querySelector("[data-media-count]");
    const mediaEmpty = document.querySelector("[data-media-empty]");
    const pendingUploads = new Set();
    let editorIsSaving = false;

    const setUploadStatus = (message, state = "") => {
      uploadStatus.textContent = message;
      uploadStatus.className = `editor-upload-status${state ? ` is-${state}` : ""}`;
    };

    const insertImageMarkdown = (file, url) => {
      const start = markdownEditor.selectionStart;
      const end = markdownEditor.selectionEnd;
      const before = markdownEditor.value.slice(0, start);
      const after = markdownEditor.value.slice(end);
      const alt = file.name.replace(/\.[^.]+$/, "").replace(/[\[\]()]/g, " ").trim() || "Görsel";
      const prefix = before && !before.endsWith("\n") ? "\n\n" : "";
      const suffix = after && !after.startsWith("\n") ? "\n\n" : "";
      const markdownImage = `${prefix}![${alt}](${url})${suffix}`;
      markdownEditor.value = `${before}${markdownImage}${after}`;
      const cursor = before.length + markdownImage.length;
      markdownEditor.setSelectionRange(cursor, cursor);
      markdownEditor.focus();
      markdownEditor.dispatchEvent(new Event("input", { bubbles: true }));
    };

    const updateMediaState = () => {
      const count = mediaGrid?.children.length || 0;
      if (mediaCount) mediaCount.textContent = count;
      mediaEmpty?.classList.toggle("is-hidden", count > 0);
    };

    const addMediaItem = (url) => {
      if (!mediaGrid || mediaGrid.querySelector(`[data-image-url="${CSS.escape(url)}"]`)) return;
      const item = document.createElement("article");
      item.className = "editor-media-item";
      item.dataset.imageUrl = url;
      const copyButton = document.createElement("button");
      copyButton.className = "editor-media-copy";
      copyButton.type = "button";
      copyButton.dataset.copyImage = url;
      copyButton.title = "Görsel adresini kopyala";
      const image = document.createElement("img");
      image.src = url;
      image.alt = "Yazı görseli";
      const copyText = document.createElement("span");
      copyText.textContent = "Adresi kopyala";
      copyButton.append(image, copyText);
      const deleteButton = document.createElement("button");
      deleteButton.className = "editor-media-delete";
      deleteButton.type = "button";
      deleteButton.dataset.deleteImage = url;
      deleteButton.setAttribute("aria-label", "Görseli sunucudan sil");
      deleteButton.innerHTML = '<i data-lucide="trash-2"></i>';
      item.append(copyButton, deleteButton);
      mediaGrid.append(item);
      updateMediaState();
      if (window.lucide) window.lucide.createIcons();
    };

    const copyImageUrl = async (url) => {
      try {
        await navigator.clipboard.writeText(url);
      } catch {
        const helper = document.createElement("textarea");
        helper.value = url;
        document.body.append(helper);
        helper.select();
        document.execCommand("copy");
        helper.remove();
      }
      setUploadStatus("Görsel adresi panoya kopyalandı.", "success");
    };

    const removeImageMarkdown = (url) => {
      const escapedUrl = url.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      markdownEditor.value = markdownEditor.value
        .replace(new RegExp(`!\\[[^\\]]*\\]\\(\\s*${escapedUrl}(?:\\s+["'][^"']*["'])?\\s*\\)`, "g"), "")
        .replace(/\n{3,}/g, "\n\n")
        .trim();
      markdownEditor.dispatchEvent(new Event("input", { bubbles: true }));
    };

    const deleteEditorImage = async (url, item) => {
      if (!window.confirm("Bu görsel sunucudan kalıcı olarak silinsin mi?")) return;
      const formData = new FormData();
      formData.append("url", url);
      formData.append("slug", mediaLibrary?.dataset.postSlug || "");
      formData.append("csrf_token", document.querySelector('.blog-editor-form [name="csrf_token"]').value);
      const response = await fetch(mediaLibrary.dataset.deleteUrl, { method: "POST", body: formData });
      const result = await response.json();
      if (!response.ok) {
        setUploadStatus(result.error || "Görsel silinemedi.", "error");
        return;
      }
      pendingUploads.delete(url);
      removeImageMarkdown(url);
      item.remove();
      updateMediaState();
      setUploadStatus("Görsel sunucudan silindi.", "success");
    };

    const uploadDroppedImage = async (file) => {
      if (editorDropzone.classList.contains("is-uploading")) {
        setUploadStatus("Mevcut görselin yüklenmesini bekleyin.", "error");
        return;
      }
      if (!file.type.startsWith("image/")) {
        setUploadStatus("Yalnızca görsel dosyaları eklenebilir.", "error");
        return;
      }
      if (file.size > 5 * 1024 * 1024) {
        setUploadStatus("Görsel 5 MB sınırını aşmamalıdır.", "error");
        return;
      }
      const formData = new FormData();
      formData.append("file", file);
      formData.append("csrf_token", document.querySelector('.blog-editor-form [name="csrf_token"]').value);
      editorDropzone.classList.add("is-uploading");
      editorDropzone.setAttribute("aria-busy", "true");
      if (editorImageInput) editorImageInput.disabled = true;
      if (editorSaveButton) editorSaveButton.disabled = true;
      setUploadStatus("Görsel yükleniyor…");
      try {
        const response = await fetch(editorDropzone.dataset.imageUploadUrl, {
          method: "POST",
          body: formData,
        });
        const isJson = response.headers.get("content-type")?.includes("application/json");
        const result = isJson ? await response.json() : {};
        if (!response.ok) {
          const fallback = response.status === 413 ? "Görsel 5 MB sınırını aşmamalıdır." : "Görsel yüklenemedi.";
          throw new Error(result.error || fallback);
        }
        insertImageMarkdown(file, result.url);
        pendingUploads.add(result.url);
        addMediaItem(result.url);
        setUploadStatus("Görsel yüklendi ve yazıya eklendi.", "success");
      } catch (error) {
        setUploadStatus(error.message || "Görsel yüklenemedi.", "error");
      } finally {
        editorDropzone.classList.remove("is-uploading");
        editorDropzone.removeAttribute("aria-busy");
        if (editorImageInput) editorImageInput.disabled = false;
        if (editorSaveButton) editorSaveButton.disabled = false;
      }
    };

    ["dragenter", "dragover"].forEach((eventName) => editorDropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      if (!editorDropzone.classList.contains("is-uploading")) editorDropzone.classList.add("is-dragging");
    }));
    ["dragleave", "dragend"].forEach((eventName) => editorDropzone.addEventListener(eventName, () => {
      editorDropzone.classList.remove("is-dragging");
    }));
    editorDropzone.addEventListener("drop", (event) => {
      event.preventDefault();
      editorDropzone.classList.remove("is-dragging");
      const file = event.dataTransfer.files[0];
      if (file && !editorDropzone.classList.contains("is-uploading")) uploadDroppedImage(file);
    });
    editorImageInput?.addEventListener("change", () => {
      const file = editorImageInput.files[0];
      if (file && !editorDropzone.classList.contains("is-uploading")) uploadDroppedImage(file);
      editorImageInput.value = "";
    });
    mediaLibrary?.addEventListener("click", (event) => {
      const deleteButton = event.target.closest("[data-delete-image]");
      if (deleteButton) {
        deleteEditorImage(deleteButton.dataset.deleteImage, deleteButton.closest(".editor-media-item"));
        return;
      }
      const copyButton = event.target.closest("[data-copy-image]");
      if (copyButton) copyImageUrl(copyButton.dataset.copyImage);
    });
    blogEditorForm?.addEventListener("submit", (event) => {
      if (editorDropzone.classList.contains("is-uploading")) {
        event.preventDefault();
        setUploadStatus("Yazıyı kaydetmeden önce görsel yüklemesinin tamamlanmasını bekleyin.", "error");
        return;
      }
      editorIsSaving = true;
    });
    window.addEventListener("pagehide", () => {
      if (editorIsSaving || !pendingUploads.size) return;
      pendingUploads.forEach((url) => {
        const formData = new FormData();
        formData.append("url", url);
        formData.append("slug", mediaLibrary?.dataset.postSlug || "");
        formData.append("csrf_token", document.querySelector('.blog-editor-form [name="csrf_token"]').value);
        navigator.sendBeacon(mediaLibrary.dataset.deleteUrl, formData);
      });
    });
    updateMediaState();
  }

  const blogSearch = document.querySelector(".blog-search");
  const blogResults = document.querySelector("[data-blog-results]");
  if (blogSearch && blogResults) {
    let debounceTimer;
    let activeRequest;

    const loadResults = async (url) => {
      activeRequest?.abort();
      const requestController = new AbortController();
      activeRequest = requestController;
      blogSearch.classList.add("is-loading");
      blogResults.setAttribute("aria-busy", "true");
      try {
        const response = await fetch(url, {
          headers: { "X-Requested-With": "XMLHttpRequest" },
          signal: requestController.signal,
        });
        if (!response.ok) throw new Error("Arama sonuçları alınamadı.");
        blogResults.innerHTML = await response.text();
        history.replaceState(null, "", url);
        if (window.lucide) window.lucide.createIcons();
      } catch (error) {
        if (error.name !== "AbortError") blogSearch.submit();
      } finally {
        if (activeRequest === requestController) {
          blogSearch.classList.remove("is-loading");
          blogResults.removeAttribute("aria-busy");
        }
      }
    };

    const searchNow = () => {
      const url = new URL(blogSearch.action, window.location.origin);
      new FormData(blogSearch).forEach((value, key) => {
        if (value) url.searchParams.set(key, value);
      });
      loadResults(url);
    };

    blogSearch.addEventListener("input", () => {
      window.clearTimeout(debounceTimer);
      debounceTimer = window.setTimeout(searchNow, 280);
    });
    blogSearch.addEventListener("submit", (event) => {
      event.preventDefault();
      window.clearTimeout(debounceTimer);
      searchNow();
    });
    blogResults.addEventListener("click", (event) => {
      const pageLink = event.target.closest(".blog-pagination a:not(.is-disabled)");
      if (!pageLink) return;
      event.preventDefault();
      loadResults(new URL(pageLink.href));
    });
  }

  document.querySelectorAll("[data-image-picker]").forEach((picker) => {
    const input = picker.querySelector('input[type="file"]');
    const preview = picker.querySelector("[data-image-preview]");
    const fileName = picker.querySelector("[data-image-name]");
    const imageTitle = picker.querySelector("[data-image-title]");
    const removeInput = picker.querySelector("[data-remove-image-input]");
    const removeButton = picker.querySelector("[data-remove-image]");
    const initialPreview = preview.innerHTML;
    const initialFileName = fileName?.textContent;
    const initialImageTitle = imageTitle?.textContent;
    const initiallyHasImage = picker.classList.contains("has-image");
    const initialRemoveHidden = removeButton?.hidden;
    let previewUrl;

    const showSelectedImage = () => {
      const file = input.files[0];
      if (!file) return;
      if (!file.type.startsWith("image/")) {
        input.value = "";
        return;
      }
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      previewUrl = URL.createObjectURL(file);
      const image = document.createElement("img");
      image.src = previewUrl;
      image.alt = "Seçilen görsel önizlemesi";
      preview.replaceChildren(image);
      fileName.textContent = file.name;
      picker.classList.add("has-image");
      picker.classList.remove("is-marked-remove");
      if (removeInput) removeInput.value = "0";
      if (removeButton) removeButton.hidden = false;
      if (imageTitle) imageTitle.textContent = "Seçilen görsel";
    };

    input.addEventListener("change", showSelectedImage);
    ["dragenter", "dragover"].forEach((eventName) => picker.addEventListener(eventName, (event) => {
      event.preventDefault();
      picker.classList.add("is-dragging");
    }));
    ["dragleave", "dragend"].forEach((eventName) => picker.addEventListener(eventName, () => {
      picker.classList.remove("is-dragging");
    }));
    picker.addEventListener("drop", (event) => {
      event.preventDefault();
      picker.classList.remove("is-dragging");
      const file = event.dataTransfer.files[0];
      if (!file?.type.startsWith("image/")) return;
      const transfer = new DataTransfer();
      transfer.items.add(file);
      input.files = transfer.files;
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });
    removeButton?.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      input.value = "";
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      previewUrl = undefined;
      preview.innerHTML = '<i data-lucide="image-plus"></i>';
      removeInput.value = "1";
      removeInput.dispatchEvent(new Event("input", { bubbles: true }));
      removeButton.hidden = true;
      picker.classList.remove("has-image");
      picker.classList.add("is-marked-remove");
      imageTitle.textContent = "Görsel kaldırılacak";
      fileName.textContent = "Değişikliği uygulamak için formu kaydedin.";
      if (window.lucide) window.lucide.createIcons();
    });
    input.form?.addEventListener("reset", () => window.requestAnimationFrame(() => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      previewUrl = undefined;
      preview.innerHTML = initialPreview;
      if (fileName) fileName.textContent = initialFileName;
      if (imageTitle) imageTitle.textContent = initialImageTitle;
      picker.classList.toggle("has-image", initiallyHasImage);
      picker.classList.remove("is-marked-remove", "is-dragging");
      if (removeButton) removeButton.hidden = initialRemoveHidden;
      if (window.lucide) window.lucide.createIcons();
    }));
  });

  document.querySelectorAll("[data-copy-input]").forEach((input) => {
    const preview = document.querySelector(`[data-copy-preview="${input.dataset.copyInput}"]`);
    if (!preview) return;
    input.addEventListener("input", () => {
      preview.textContent = input.value || "—";
    });
  });

  const themeSelect = document.querySelector("[data-theme-select]");
  if (themeSelect) {
    const swatches = document.querySelectorAll("[data-theme-swatch]");
    const description = document.querySelector("[data-theme-description]");
    const updateTheme = () => {
      const option = themeSelect.selectedOptions[0];
      document.body.dataset.theme = themeSelect.value;
      option.dataset.colors.split(",").forEach((color, index) => {
        if (swatches[index]) swatches[index].style.setProperty("--swatch", color);
      });
      description.textContent = option.dataset.description;
    };
    themeSelect.addEventListener("change", updateTheme);
    updateTheme();
  }

  document.querySelectorAll("[data-tag-editor]").forEach((editor) => {
    const list = editor.querySelector("[data-tag-list]");
    const input = editor.querySelector("[data-tag-input]");
    const valueField = editor.querySelector("[data-tag-value]");
    let tags = valueField.value.split(/\r?\n/).map((tag) => tag.trim()).filter(Boolean);
    const initialTags = [...tags];

    const sync = () => {
      valueField.value = tags.join("\n");
      list.replaceChildren();
      tags.forEach((tag, index) => {
        const chip = document.createElement("span");
        chip.className = "tag-chip";
        const text = document.createElement("span");
        text.textContent = tag;
        const remove = document.createElement("button");
        remove.type = "button";
        remove.setAttribute("aria-label", `${tag} etiketini kaldır`);
        remove.innerHTML = '<i data-lucide="x"></i>';
        remove.addEventListener("click", () => {
          tags.splice(index, 1);
          sync();
          notifyChange();
          input.focus();
        });
        chip.append(text, remove);
        list.append(chip);
      });
      if (window.lucide) window.lucide.createIcons();
    };

    const notifyChange = () => valueField.dispatchEvent(new Event("input", { bubbles: true }));

    const addTag = (rawTag, notify = true) => {
      const tag = rawTag.trim();
      if (!tag || tags.some((item) => item.toLocaleLowerCase("tr-TR") === tag.toLocaleLowerCase("tr-TR"))) return;
      tags.push(tag);
      input.value = "";
      sync();
      if (notify) notifyChange();
    };

    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        addTag(input.value);
      } else if (event.key === "Backspace" && !input.value && tags.length) {
        tags.pop();
        sync();
        notifyChange();
      }
    });
    input.addEventListener("paste", (event) => {
      const pasted = event.clipboardData.getData("text");
      if (!pasted.includes("\n")) return;
      event.preventDefault();
      pasted.split(/\r?\n/).forEach(addTag);
    });
    editor.addEventListener("click", () => input.focus());
    const form = editor.closest("form");
    form?.addEventListener("submit", () => addTag(input.value, false));
    form?.addEventListener("reset", () => window.requestAnimationFrame(() => {
      tags = [...initialTags];
      input.value = "";
      sync();
    }));
    sync();
  });

  if (blogEditorForm) {
    let hasUnsavedChanges = false;
    blogEditorForm.addEventListener("input", () => { hasUnsavedChanges = true; });
    blogEditorForm.addEventListener("change", () => { hasUnsavedChanges = true; });
    blogEditorForm.addEventListener("submit", (event) => {
      if (!event.defaultPrevented) hasUnsavedChanges = false;
    });
    window.addEventListener("beforeunload", (event) => {
      if (!hasUnsavedChanges) return;
      event.preventDefault();
      event.returnValue = "";
    });
  }

  const flashes = document.querySelectorAll(".flash--success");
  if (flashes.length) window.setTimeout(() => flashes.forEach((flash) => flash.remove()), 5000);
});
