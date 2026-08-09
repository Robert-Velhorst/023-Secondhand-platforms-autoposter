const state = {
  token: localStorage.getItem("autoposterToken"),
  user: null,
  platforms: [],
  listings: [],
  recentListings: [],
  jobs: [],
  latestJobs: [],
  accounts: [],
  templates: [],
  categoryMappings: [],
  auditEvents: [],
  haiTokens: [],
  newHaiToken: null,
  analytics: null,
  actionCenter: null,
  validationResults: {},
  qualityResult: null,
  selectedListingId: null,
  selectedPlatforms: new Set(),
  imageObjectUrls: [],
  imageRenderGeneration: 0,
  listingQuery: {
    search: "",
    status: "",
    sort: "-updated_at",
    limit: 10,
    offset: 0,
    total: 0,
  },
  jobQuery: {
    platform: "",
    status: "",
    sort: "-created_at",
    limit: 10,
    offset: 0,
    total: 0,
  },
  accountQuery: {
    platform: "",
    status: "",
    sort: "-created_at",
    limit: 10,
    offset: 0,
    total: 0,
  },
  templateQuery: {
    platform: "",
    variant: "",
    search: "",
    sort: "name",
    limit: 10,
    offset: 0,
    total: 0,
  },
  mappingQuery: {
    platform: "",
    sourceCategory: "",
    sort: "source_category",
    limit: 10,
    offset: 0,
    total: 0,
  },
  jobPolling: {
    enabled: true,
    intervalMs: 10000,
    timerId: null,
    inFlight: false,
    lastUpdatedAt: null,
  },
  pendingRequests: 0,
  locale: localStorage.getItem("autoposterLocale") || document.documentElement.lang || "en",
  localization: null,
  autosave: {
    timerId: null,
    inFlight: false,
  },
};

const $ = (selector) => document.querySelector(selector);
const COPY_CATALOG = {
  en: {
    "app.name": "Secondhand Autoposter",
    "auth.email": "Email",
    "auth.password": "Password",
    "auth.name": "Name",
    "auth.signIn": "Sign in",
    "auth.createAccount": "Create account",
    "nav.dashboard": "Dashboard",
    "nav.listings": "Listings",
    "nav.queue": "Queue",
    "nav.accounts": "Accounts",
    "nav.settings": "Settings",
    "nav.signOut": "Sign out",
    "nav.language": "Language",
    "status.checking": "Checking",
    "status.offline": "Offline",
    "action.newListing": "New listing",
    "action.refresh": "Refresh",
    "action.previous": "Previous",
    "action.next": "Next",
    "action.save": "Save",
    "action.duplicate": "Duplicate",
    "action.delete": "Delete",
    "action.cancel": "Cancel",
    "action.validate": "Validate",
    "action.check": "Check",
    "action.queuePackage": "Queue assisted package",
    "action.regeneratePackage": "Regenerate package",
    "dashboard.insights": "Insights",
    "dashboard.localOnly": "Local only",
    "dashboard.recentListings": "Recent listings",
    "dashboard.latestJobs": "Latest jobs",
    "dashboard.actionCenter": "Getting started and action center",
    "dashboard.derivedLocal": "Derived locally",
    "metric.listings": "Listings",
    "metric.ready": "Ready",
    "metric.needAction": "Need action",
    "metric.failed": "Failed",
    "listings.search": "Search",
    "listings.searchPlaceholder": "title, category, location",
    "label.status": "Status",
    "label.sort": "Sort",
    "label.platform": "Platform",
    "label.title": "Title",
    "label.price": "Price",
    "label.condition": "Condition",
    "label.category": "Category",
    "label.location": "Location",
    "label.tags": "Tags",
    "label.brand": "Brand",
    "label.model": "Model",
    "label.color": "Color",
    "label.material": "Material",
    "label.categoryAttributes": "Category attributes",
    "label.weightGrams": "Weight grams",
    "label.shippingCost": "Shipping cost",
    "label.pickup": "Pickup",
    "label.shipping": "Shipping",
    "label.template": "Template",
    "label.description": "Description",
    "label.deliveryOptions": "Delivery options",
    "label.dimensions": "Dimensions",
    "label.notes": "Notes",
    "label.internalNotes": "Internal notes",
    "quality.title": "Quality assistant",
    "images.title": "Images",
    "images.upload": "Upload image",
    "platforms.title": "Platforms",
    "queue.title": "Assisted package queue",
    "queue.liveOn": "Live refresh on",
    "queue.pause": "Pause live refresh",
    "queue.manualCompletion": "Confirm manual completion",
    "queue.platformUrl": "Marketplace listing URL",
    "queue.platformListingId": "Marketplace listing ID",
    "queue.complete": "Record completion",
    "accounts.title": "Platform accounts",
    "accounts.displayName": "Display name",
    "accounts.save": "Save account",
    "templates.title": "Description templates",
    "templates.name": "Name",
    "templates.variant": "Variant",
    "templates.body": "Body",
    "templates.save": "Save template",
    "mappings.title": "Category mappings",
    "mappings.source": "Source category",
    "mappings.target": "Platform category",
    "mappings.save": "Save mapping",
    "settings.data": "Data portability",
    "settings.exportJson": "Export JSON",
    "settings.exportCsv": "Export listings CSV",
    "settings.exportImages": "Export images ZIP",
    "settings.importJson": "Import JSON",
    "settings.importCsv": "Import listings CSV",
    "settings.diagnostics": "Diagnostics",
    "settings.hai": "HAI connection",
    "settings.haiHelp": "Create a read-only connector token for HAI. The token can read your listing feed, but cannot post, edit, or export credentials.",
    "settings.haiName": "Connection name",
    "settings.haiExpiry": "Expires after",
    "settings.haiCreate": "Create read-only token",
    "settings.runDiagnostics": "Run diagnostics",
    "settings.notRun": "Not run yet.",
    "settings.privacy": "Privacy",
    "settings.deleteAccount": "Delete my account data",
    "settings.privacyWarning": "This removes your account, sessions, listings, jobs, templates, mappings, accounts, and uploaded images.",
    "settings.privacyActivity": "Privacy activity",
  },
  nl: {
    "app.name": "Tweedehands Autoposter",
    "auth.email": "E-mail",
    "auth.password": "Wachtwoord",
    "auth.name": "Naam",
    "auth.signIn": "Inloggen",
    "auth.createAccount": "Account maken",
    "nav.dashboard": "Dashboard",
    "nav.listings": "Advertenties",
    "nav.queue": "Wachtrij",
    "nav.accounts": "Accounts",
    "nav.settings": "Instellingen",
    "nav.signOut": "Uitloggen",
    "nav.language": "Taal",
    "status.checking": "Controleren",
    "status.offline": "Offline",
    "action.newListing": "Nieuwe advertentie",
    "action.refresh": "Vernieuwen",
    "action.previous": "Vorige",
    "action.next": "Volgende",
    "action.save": "Opslaan",
    "action.duplicate": "Dupliceren",
    "action.delete": "Verwijderen",
    "action.cancel": "Annuleren",
    "action.validate": "Valideren",
    "action.check": "Controleren",
    "action.queuePackage": "Assistentiepakket in wachtrij",
    "action.regeneratePackage": "Pakket opnieuw maken",
    "dashboard.insights": "Inzichten",
    "dashboard.localOnly": "Alleen lokaal",
    "dashboard.recentListings": "Recente advertenties",
    "dashboard.latestJobs": "Laatste taken",
    "dashboard.actionCenter": "Aan de slag en actiecentrum",
    "dashboard.derivedLocal": "Lokaal afgeleid",
    "metric.listings": "Advertenties",
    "metric.ready": "Klaar",
    "metric.needAction": "Actie nodig",
    "metric.failed": "Mislukt",
    "listings.search": "Zoeken",
    "listings.searchPlaceholder": "titel, categorie, locatie",
    "label.status": "Status",
    "label.sort": "Sorteren",
    "label.platform": "Platform",
    "label.title": "Titel",
    "label.price": "Prijs",
    "label.condition": "Staat",
    "label.category": "Categorie",
    "label.location": "Locatie",
    "label.tags": "Tags",
    "label.brand": "Merk",
    "label.model": "Model",
    "label.color": "Kleur",
    "label.material": "Materiaal",
    "label.categoryAttributes": "Categoriekenmerken",
    "label.weightGrams": "Gewicht in gram",
    "label.shippingCost": "Verzendkosten",
    "label.pickup": "Ophalen",
    "label.shipping": "Verzenden",
    "label.template": "Sjabloon",
    "label.description": "Beschrijving",
    "label.deliveryOptions": "Leveringsopties",
    "label.dimensions": "Afmetingen",
    "label.notes": "Notities",
    "label.internalNotes": "Interne notities",
    "quality.title": "Kwaliteitsassistent",
    "images.title": "Afbeeldingen",
    "images.upload": "Afbeelding uploaden",
    "platforms.title": "Platformen",
    "queue.title": "Wachtrij voor assistentiepakketten",
    "queue.liveOn": "Live verversen aan",
    "queue.pause": "Live verversen pauzeren",
    "queue.manualCompletion": "Handmatige voltooiing bevestigen",
    "queue.platformUrl": "Marketplace-advertentie URL",
    "queue.platformListingId": "Marketplace-advertentie ID",
    "queue.complete": "Voltooiing vastleggen",
    "accounts.title": "Platformaccounts",
    "accounts.displayName": "Weergavenaam",
    "accounts.save": "Account opslaan",
    "templates.title": "Beschrijving-sjablonen",
    "templates.name": "Naam",
    "templates.variant": "Variant",
    "templates.body": "Inhoud",
    "templates.save": "Sjabloon opslaan",
    "mappings.title": "Categoriemapping",
    "mappings.source": "Broncategorie",
    "mappings.target": "Platformcategorie",
    "mappings.save": "Mapping opslaan",
    "settings.data": "Data-overdracht",
    "settings.exportJson": "JSON exporteren",
    "settings.exportCsv": "Advertenties CSV exporteren",
    "settings.exportImages": "Afbeeldingen ZIP exporteren",
    "settings.importJson": "JSON importeren",
    "settings.importCsv": "Advertenties CSV importeren",
    "settings.diagnostics": "Diagnostiek",
    "settings.hai": "HAI-koppeling",
    "settings.haiHelp": "Maak een alleen-lezen koppeltoken voor HAI. Het token kan je advertentiefeed lezen, maar niets plaatsen, wijzigen of inloggegevens exporteren.",
    "settings.haiName": "Naam van koppeling",
    "settings.haiExpiry": "Verloopt na",
    "settings.haiCreate": "Alleen-lezen token maken",
    "settings.runDiagnostics": "Diagnostiek uitvoeren",
    "settings.notRun": "Nog niet uitgevoerd.",
    "settings.privacy": "Privacy",
    "settings.deleteAccount": "Mijn accountgegevens verwijderen",
    "settings.privacyWarning": "Dit verwijdert je account, sessies, advertenties, taken, sjablonen, mappings, accounts en geuploade afbeeldingen.",
    "settings.privacyActivity": "Privacyactiviteit",
  },
};

const money = (cents) => (cents / 100).toLocaleString(state.locale, { style: "currency", currency: "EUR" });
let listingSearchTimer = null;
let templateSearchTimer = null;
let mappingSearchTimer = null;

function t(key) {
  return COPY_CATALOG[state.locale]?.[key] || COPY_CATALOG.en[key] || key;
}

function applyTranslations() {
  document.documentElement.lang = state.locale;
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-label]").forEach((node) => {
    const textNode = Array.from(node.childNodes).find((child) => child.nodeType === Node.TEXT_NODE && child.textContent.trim());
    if (textNode) textNode.textContent = t(node.dataset.i18nLabel);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
    node.placeholder = t(node.dataset.i18nPlaceholder);
  });
  document.querySelectorAll("[data-i18n-title]").forEach((node) => {
    node.title = t(node.dataset.i18nTitle);
  });
  const localeSelect = $("#localeSelect");
  if (localeSelect) localeSelect.value = state.locale;
  const activeView = document.querySelector(".nav.active")?.dataset.view || "dashboard";
  const titleKey = `nav.${activeView}`;
  const title = $("#viewTitle");
  if (title) title.textContent = t(titleKey);
}

function setLocale(locale) {
  state.locale = COPY_CATALOG[locale] ? locale : "en";
  localStorage.setItem("autoposterLocale", state.locale);
  applyTranslations();
  render();
}

class ApiError extends Error {
  constructor(message, options = {}) {
    super(message || "Request failed");
    this.name = "ApiError";
    this.code = options.code || "REQUEST_FAILED";
    this.requestId = options.requestId || "";
    this.retryable = Boolean(options.retryable);
    this.fieldErrors = options.fieldErrors || {};
    this.status = options.status || 0;
  }
}

function setBusy(delta) {
  state.pendingRequests = Math.max(0, state.pendingRequests + delta);
  document.body.classList.toggle("busy", state.pendingRequests > 0);
}

function showAppMessage(message, tone = "error") {
  const node = $("#appMessage");
  if (!node) return;
  node.textContent = message || "Something went wrong";
  node.className = `app-message ${tone}`;
}

function showAppError(error, fallback = "Something went wrong") {
  const node = $("#appMessage");
  if (!node) return;
  const message = error?.message || fallback;
  const details = [];
  if (error?.fieldErrors && Object.keys(error.fieldErrors).length) {
    const fieldSummary = Object.entries(error.fieldErrors)
      .slice(0, 3)
      .map(([field, messages]) => `${formatFieldLabel(field)}: ${[].concat(messages).join(", ")}`)
      .join(" ");
    details.push(fieldSummary);
  }
  if (error?.retryable) details.push("You can retry this request.");
  if (error?.requestId) details.push(`Request ID: ${error.requestId}`);
  node.innerHTML = `
    <strong>${escapeHtml(message)}</strong>
    ${details.length ? `<span>${escapeHtml(details.join(" "))}</span>` : ""}
  `;
  node.className = "app-message error";
}

function clearAppMessage() {
  const node = $("#appMessage");
  if (!node) return;
  node.textContent = "";
  node.className = "app-message hidden";
}

async function api(path, options = {}) {
  const { data } = await apiWithMeta(path, options);
  return data;
}

async function apiWithMeta(path, options = {}) {
  const headers = options.headers || {};
  if (!(options.body instanceof FormData)) headers["Content-Type"] = "application/json";
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  setBusy(1);
  try {
    const response = await fetch(`/api${path}`, { ...options, headers });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({ detail: response.statusText }));
      const envelope = payload.error || {};
      throw new ApiError(envelope.message || payload.detail || "Request failed", {
        code: envelope.code,
        requestId: envelope.request_id || response.headers.get("X-Request-ID") || "",
        retryable: envelope.retryable,
        fieldErrors: envelope.field_errors,
        status: response.status,
      });
    }
    const data = response.status === 204 ? null : await response.json();
    return { data, headers: response.headers };
  } catch (error) {
    if (error instanceof Error) throw error;
    throw new ApiError("Network request failed", { retryable: true });
  } finally {
    setBusy(-1);
  }
}

async function downloadApiFile(path, filename) {
  const headers = {};
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  setBusy(1);
  try {
    const response = await fetch(`/api${path}`, { headers });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({ detail: response.statusText }));
      const envelope = payload.error || {};
      throw new ApiError(envelope.message || payload.detail || "Download failed", {
        code: envelope.code,
        requestId: envelope.request_id || response.headers.get("X-Request-ID") || "",
        retryable: envelope.retryable,
        fieldErrors: envelope.field_errors,
        status: response.status,
      });
    }
    const blob = await response.blob();
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
    URL.revokeObjectURL(link.href);
  } finally {
    setBusy(-1);
  }
}

function listingQueryPath() {
  const params = new URLSearchParams({
    limit: String(state.listingQuery.limit),
    offset: String(state.listingQuery.offset),
    sort: state.listingQuery.sort,
  });
  if (state.listingQuery.search.trim()) params.set("search", state.listingQuery.search.trim());
  if (state.listingQuery.status) params.set("status", state.listingQuery.status);
  return `/listings?${params.toString()}`;
}

function jobQueryPath() {
  const params = new URLSearchParams({
    limit: String(state.jobQuery.limit),
    offset: String(state.jobQuery.offset),
    sort: state.jobQuery.sort,
  });
  if (state.jobQuery.platform) params.set("platform", state.jobQuery.platform);
  if (state.jobQuery.status) params.set("status", state.jobQuery.status);
  return `/jobs?${params.toString()}`;
}

function accountQueryPath() {
  const params = new URLSearchParams({
    limit: String(state.accountQuery.limit),
    offset: String(state.accountQuery.offset),
    sort: state.accountQuery.sort,
  });
  if (state.accountQuery.platform) params.set("platform", state.accountQuery.platform);
  if (state.accountQuery.status) params.set("status", state.accountQuery.status);
  return `/accounts?${params.toString()}`;
}

function templateQueryPath() {
  const params = new URLSearchParams({
    limit: String(state.templateQuery.limit),
    offset: String(state.templateQuery.offset),
    sort: state.templateQuery.sort,
  });
  if (state.templateQuery.platform) params.set("platform", state.templateQuery.platform);
  if (state.templateQuery.variant.trim()) params.set("variant", state.templateQuery.variant.trim());
  if (state.templateQuery.search.trim()) params.set("search", state.templateQuery.search.trim());
  return `/templates?${params.toString()}`;
}

function mappingQueryPath() {
  const params = new URLSearchParams({
    limit: String(state.mappingQuery.limit),
    offset: String(state.mappingQuery.offset),
    sort: state.mappingQuery.sort,
  });
  if (state.mappingQuery.platform) params.set("platform", state.mappingQuery.platform);
  if (state.mappingQuery.sourceCategory.trim()) {
    params.set("source_category", state.mappingQuery.sourceCategory.trim());
  }
  return `/category-mappings?${params.toString()}`;
}

function show(view) {
  clearAppMessage();
  document.querySelectorAll(".view").forEach((node) => node.classList.remove("active"));
  document.querySelectorAll(".nav").forEach((node) => node.classList.toggle("active", node.dataset.view === view));
  $(`#${view}View`).classList.add("active");
  $("#viewTitle").textContent = t(`nav.${view}`);
}

function statusClass(status) {
  return `status ${status || ""}`;
}

function selectedListing() {
  return state.listings.find((listing) => listing.id === state.selectedListingId) || null;
}

function platformByKey(key) {
  return state.platforms.find((platform) => platform.key === key) || { key, name: key, compliance_notes: [] };
}

function resetListingReviewState() {
  state.validationResults = {};
  state.qualityResult = null;
}

function selectListing(listingId, { resetReview = true } = {}) {
  state.selectedListingId = listingId ? Number(listingId) : null;
  if (resetReview) resetListingReviewState();
}

function markSelectedListingMutated() {
  resetListingReviewState();
}

async function loadAll() {
  const [
    platforms,
    listingResult,
    jobResult,
    accountResult,
    templateResult,
    categoryMappingResult,
    auditResult,
    haiTokens,
    dashboard,
  ] = await Promise.all([
    api("/platforms"),
    apiWithMeta(listingQueryPath()),
    apiWithMeta(jobQueryPath()),
    apiWithMeta(accountQueryPath()),
    apiWithMeta(templateQueryPath()),
    apiWithMeta(mappingQueryPath()),
    api("/audit-events?limit=8"),
    api("/hai/tokens"),
    api("/dashboard"),
  ]);
  state.platforms = platforms;
  state.listings = listingResult.data;
  state.listingQuery.total = Number(listingResult.headers.get("X-Total-Count") || state.listings.length);
  state.jobs = jobResult.data;
  state.jobQuery.total = Number(jobResult.headers.get("X-Total-Count") || state.jobs.length);
  state.accounts = accountResult.data;
  state.accountQuery.total = Number(accountResult.headers.get("X-Total-Count") || state.accounts.length);
  state.templates = templateResult.data;
  state.templateQuery.total = Number(templateResult.headers.get("X-Total-Count") || state.templates.length);
  state.categoryMappings = categoryMappingResult.data;
  state.auditEvents = auditResult;
  state.haiTokens = haiTokens;
  state.mappingQuery.total = Number(
    categoryMappingResult.headers.get("X-Total-Count") || state.categoryMappings.length
  );
  state.analytics = dashboard.analytics;
  state.actionCenter = dashboard.action_center;
  state.recentListings = dashboard.recent_listings;
  state.latestJobs = dashboard.latest_jobs;
  if (state.selectedListingId && !state.listings.some((listing) => listing.id === state.selectedListingId)) {
    selectListing(null);
  }
  if (!state.selectedListingId && state.listings.length) selectListing(state.listings[0].id, { resetReview: false });
  render();
  scheduleJobPolling();
}

async function loadRequestedListing() {
  const requestedId = Number(new URLSearchParams(window.location.search).get("listing"));
  if (!Number.isInteger(requestedId) || requestedId < 1) return;
  let listing = state.listings.find((item) => item.id === requestedId);
  if (!listing) {
    listing = await api(`/listings/${requestedId}`);
    state.listings = [listing, ...state.listings.filter((item) => item.id !== requestedId)];
  }
  selectListing(requestedId);
  show("listings");
  renderListings();
}

async function loadListingPage() {
  const result = await apiWithMeta(listingQueryPath());
  state.listings = result.data;
  state.listingQuery.total = Number(result.headers.get("X-Total-Count") || state.listings.length);
  if (state.selectedListingId && !state.listings.some((listing) => listing.id === state.selectedListingId)) {
    selectListing(null);
  }
  if (!state.selectedListingId && state.listings.length) selectListing(state.listings[0].id, { resetReview: false });
  renderListings();
}

async function loadJobPage() {
  const result = await apiWithMeta(jobQueryPath());
  state.jobs = result.data;
  state.jobQuery.total = Number(result.headers.get("X-Total-Count") || state.jobs.length);
  renderJobs();
}

async function loadAccountPage() {
  const result = await apiWithMeta(accountQueryPath());
  state.accounts = result.data;
  state.accountQuery.total = Number(result.headers.get("X-Total-Count") || state.accounts.length);
  renderAccounts();
}

async function loadTemplatePage() {
  const result = await apiWithMeta(templateQueryPath());
  state.templates = result.data;
  state.templateQuery.total = Number(result.headers.get("X-Total-Count") || state.templates.length);
  renderSettings();
}

async function loadMappingPage() {
  const result = await apiWithMeta(mappingQueryPath());
  state.categoryMappings = result.data;
  state.mappingQuery.total = Number(result.headers.get("X-Total-Count") || state.categoryMappings.length);
  renderSettings();
}

async function refreshJobsOnly() {
  if (!state.token || state.jobPolling.inFlight) return;
  state.jobPolling.inFlight = true;
  try {
    const [jobResult, dashboard] = await Promise.all([
      apiWithMeta(jobQueryPath()),
      api("/dashboard"),
    ]);
    state.jobs = jobResult.data;
    state.jobQuery.total = Number(jobResult.headers.get("X-Total-Count") || state.jobs.length);
    state.analytics = dashboard.analytics;
    state.actionCenter = dashboard.action_center;
    state.recentListings = dashboard.recent_listings;
    state.latestJobs = dashboard.latest_jobs;
    state.jobPolling.lastUpdatedAt = new Date();
    renderDashboard();
    renderJobs();
  } catch (error) {
    showAppError(error, "Could not refresh jobs");
  } finally {
    state.jobPolling.inFlight = false;
    scheduleJobPolling();
  }
}

function scheduleJobPolling() {
  if (state.jobPolling.timerId) {
    clearTimeout(state.jobPolling.timerId);
    state.jobPolling.timerId = null;
  }
  if (!state.token || !state.jobPolling.enabled) {
    renderJobPollingStatus();
    return;
  }
  state.jobPolling.timerId = setTimeout(refreshJobsOnly, state.jobPolling.intervalMs);
  renderJobPollingStatus();
}

function renderJobPollingStatus() {
  const toggle = $("#jobPollingToggle");
  const status = $("#jobPollingStatus");
  if (!toggle || !status) return;
  toggle.textContent = state.jobPolling.enabled ? "Pause live refresh" : "Resume live refresh";
  const updated = state.jobPolling.lastUpdatedAt
    ? `Updated ${state.jobPolling.lastUpdatedAt.toLocaleTimeString()}`
    : "Waiting for first refresh";
  status.textContent = state.jobPolling.enabled ? `Live refresh on - ${updated}` : "Live refresh paused";
}

function render() {
  renderDashboard();
  renderListings();
  renderJobs();
  renderAccounts();
  renderSettings();
}

function renderDashboard() {
  const summary = state.analytics?.summary || {};
  $("#metricListings").textContent = summary.listings_total || 0;
  $("#metricReady").textContent = summary.ready_listings || 0;
  $("#metricAction").textContent = summary.needs_action_jobs || 0;
  $("#metricFailed").textContent = summary.failed_jobs || 0;
  renderAnalytics();
  renderActionCenter();
  $("#recentListings").innerHTML = state.recentListings.map(listingItemHtml).join("") || `<p class="muted">No listings yet.</p>`;
  $("#latestJobs").innerHTML = state.latestJobs.map(jobItemHtml).join("") || `<p class="muted">No jobs yet.</p>`;
}

function renderActionCenter() {
  const center = state.actionCenter;
  if (!center) {
    $("#onboardingSteps").innerHTML = `<p class="muted">Loading next actions...</p>`;
    $("#actionCenterList").innerHTML = "";
    return;
  }
  $("#onboardingSteps").innerHTML = (center.onboarding_steps || []).map((step) => `
    <button type="button" class="onboarding-step ${step.complete ? "complete" : ""}" data-action-view="${escapeHtml(step.target_view)}">
      <span aria-hidden="true">${step.complete ? "Done" : "Next"}</span>
      <span>${escapeHtml(step.label)}</span>
    </button>
  `).join("");
  $("#actionCenterList").innerHTML = (center.reminders || []).map((item) => `
    <article class="action-item ${escapeHtml(item.severity)}">
      <div class="pane-head">
        <strong>${escapeHtml(item.title)}</strong>
        <span class="${statusClass(item.severity)}">${escapeHtml(item.severity)}</span>
      </div>
      <p>${escapeHtml(item.detail)}</p>
      <div class="recovery-row">
        <span>${escapeHtml(item.next_action)}</span>
        <button type="button" class="ghost" data-action-view="${escapeHtml(item.target_view)}" data-action-resource="${escapeHtml(item.resource_type || "")}" data-action-resource-id="${escapeHtml(item.resource_id || "")}">Open</button>
      </div>
    </article>
  `).join("") || `<p class="muted">No outstanding actions.</p>`;
}

function renderAnalytics() {
  const analytics = state.analytics;
  if (!analytics) {
    $("#analyticsSummary").innerHTML = `<p class="muted">No insights yet.</p>`;
    $("#analyticsDetails").innerHTML = "";
    return;
  }
  const summary = analytics.summary || {};
  const quality = analytics.quality || {};
  $("#analyticsSummary").innerHTML = [
    analyticsMetricHtml("Quality", `${summary.average_quality_score || 0}/100`),
    analyticsMetricHtml("Inventory value", money(summary.inventory_value_cents || 0)),
    analyticsMetricHtml("Avg price", money(summary.average_price_cents || 0)),
    analyticsMetricHtml("Missing images", quality.listings_missing_images || 0),
  ].join("");
  $("#analyticsDetails").innerHTML = `
    <div>
      <strong>Quality grades</strong>
      ${analyticsBarsHtml(quality.grade_counts || {})}
    </div>
    <div>
      <strong>Selected platforms</strong>
      ${analyticsBarsHtml(analytics.selected_platforms || {})}
    </div>
    <div>
      <strong>Job outcomes</strong>
      ${analyticsBarsHtml(analytics.job_statuses || {})}
    </div>
    <div>
      <strong>Common fixes</strong>
      ${analyticsIssueListHtml(quality.top_issue_fields || [])}
    </div>
  `;
}

function analyticsMetricHtml(label, value) {
  return `
    <article>
      <strong>${escapeHtml(value)}</strong>
      <span>${escapeHtml(label)}</span>
    </article>
  `;
}

function analyticsBarsHtml(values) {
  const entries = Object.entries(values);
  if (!entries.length) return `<p class="muted">No data</p>`;
  const max = Math.max(...entries.map(([, count]) => Number(count) || 0), 1);
  return `
    <div class="analytics-bars">
      ${entries.map(([label, count]) => `
        <div class="analytics-bar-row">
          <span>${escapeHtml(formatFieldLabel(label))}</span>
          <div><i style="width: ${Math.max(8, (Number(count) / max) * 100)}%"></i></div>
          <strong>${Number(count)}</strong>
        </div>
      `).join("")}
    </div>
  `;
}

function analyticsIssueListHtml(items) {
  if (!items.length) return `<p class="muted">No recurring fixes</p>`;
  return `
    <div class="analytics-issues">
      ${items.map((item) => `
        <span>${escapeHtml(formatFieldLabel(item.field))}: ${Number(item.count)}</span>
      `).join("")}
    </div>
  `;
}

function listingItemHtml(listing) {
  return `
    <article class="list-item ${listing.id === state.selectedListingId ? "selected" : ""}" data-listing-id="${listing.id}">
      <strong>${escapeHtml(listing.title || "Untitled listing")}</strong>
      <span class="muted">${escapeHtml(listing.category || "No category")} · ${money(listing.price_cents || 0)}</span>
      <span class="${statusClass(listing.status)}">${escapeHtml(listing.status)}</span>
    </article>
  `;
}

function jobItemHtml(job) {
  return `
    <article class="list-item" data-job-id="${job.id}">
      <div class="pane-head">
        <strong>${escapeHtml(job.platform)}</strong>
        <span class="${statusClass(job.status)}">${escapeHtml(job.status)}</span>
      </div>
      <span class="muted">Listing #${job.listing_id} · Attempt ${job.attempts}/${job.max_attempts}</span>
    </article>
  `;
}

function renderListings() {
  $("#listingSearch").value = state.listingQuery.search;
  $("#listingStatusFilter").value = state.listingQuery.status;
  $("#listingSort").value = state.listingQuery.sort;
  const start = state.listingQuery.total ? state.listingQuery.offset + 1 : 0;
  const end = Math.min(state.listingQuery.offset + state.listingQuery.limit, state.listingQuery.total);
  $("#listingPageInfo").textContent = `${start}-${end} of ${state.listingQuery.total}`;
  $("#listingPrevPage").disabled = state.listingQuery.offset === 0;
  $("#listingNextPage").disabled = state.listingQuery.offset + state.listingQuery.limit >= state.listingQuery.total;
  $("#listingList").innerHTML = state.listings.map(listingItemHtml).join("") || `<p class="muted">No listings yet.</p>`;
  const listing = selectedListing();
  $("#listingEditor").classList.toggle("hidden", !listing);
  if (!listing) return;
  const form = $("#listingForm");
  form.title.value = listing.title || "";
  form.price.value = ((listing.price_cents || 0) / 100).toFixed(2);
  form.condition.value = listing.condition || "used";
  form.category.value = listing.category || "";
  form.location.value = listing.location || "";
  form.brand.value = listing.brand || "";
  form.model.value = listing.model || "";
  form.color.value = listing.color || "";
  form.material.value = listing.material || "";
  form.category_attributes.value = JSON.stringify(listing.category_attributes || {}, null, 2);
  form.weight_grams.value = listing.weight_grams || 0;
  form.shipping_cost.value = ((listing.shipping_cost_cents || 0) / 100).toFixed(2);
  form.pickup_allowed.checked = Boolean(listing.pickup_allowed);
  form.shipping_allowed.checked = Boolean(listing.shipping_allowed);
  form.tags.value = (listing.tags || []).join(", ");
  form.description.value = listing.description || "";
  form.delivery_options.value = JSON.stringify(listing.delivery_options || {}, null, 2);
  form.dimensions.value = JSON.stringify(listing.dimensions || {}, null, 2);
  form.notes.value = listing.notes || "";
  form.internal_notes.value = listing.internal_notes || "";
  $("#listingRevision").textContent = `Revision ${listing.revision || 1}`;
  renderListingTemplateOptions();
  renderQualityAssistant();
  renderImages(listing);
  renderPlatforms(listing);
}

function renderQualityAssistant() {
  const result = state.qualityResult;
  const panel = $("#qualityAssistant");
  if (!result) {
    panel.innerHTML = `<p class="muted">Not checked</p>`;
    return;
  }
  const issues = result.issues || [];
  const suggestions = result.suggestions || [];
  panel.innerHTML = `
    <div class="quality-score">
      <strong>${Number(result.score || 0)}</strong>
      <span class="${statusClass(result.grade)}">${escapeHtml(formatFieldLabel(result.grade))}</span>
      <p>${escapeHtml(result.summary)}</p>
      <small class="muted">Provider: ${escapeHtml(result.provider)} · deterministic · no external data sent</small>
    </div>
    <div class="quality-checklist">
      ${Object.entries(result.checklist || {}).map(([field, passed]) => `
        <span class="${passed ? "check-pass" : "check-fail"}">${passed ? "OK" : "Fix"} ${escapeHtml(formatFieldLabel(field))}</span>
      `).join("")}
    </div>
    <div class="quality-grid">
      <section>
        <h4>Fixes</h4>
        ${issues.map(qualityIssueHtml).join("") || `<p class="muted">No required fixes.</p>`}
      </section>
      <section>
        <h4>Suggestions</h4>
        ${suggestions.map(qualitySuggestionHtml).join("") || `<p class="muted">No suggestions.</p>`}
      </section>
    </div>
  `;
}

function listingFormPayload(form) {
  return {
    title: form.title.value,
    price_cents: Math.round(Number(form.price.value || 0) * 100),
    condition: form.condition.value,
    category: form.category.value,
    location: form.location.value,
    brand: form.brand.value,
    model: form.model.value,
    color: form.color.value,
    material: form.material.value,
    category_attributes: parseDeliveryOptions(form.category_attributes.value),
    weight_grams: Math.round(Number(form.weight_grams.value || 0)),
    shipping_cost_cents: Math.round(Number(form.shipping_cost.value || 0) * 100),
    pickup_allowed: form.pickup_allowed.checked,
    shipping_allowed: form.shipping_allowed.checked,
    tags: form.tags.value.split(",").map((tag) => tag.trim()).filter(Boolean),
    description: form.description.value,
    delivery_options: parseDeliveryOptions(form.delivery_options.value),
    dimensions: parseDeliveryOptions(form.dimensions.value),
    notes: form.notes.value,
    internal_notes: form.internal_notes.value,
    status: "draft",
  };
}

function scheduleListingAutosave() {
  const listing = selectedListing();
  if (!listing || state.autosave.inFlight) return;
  if (state.autosave.timerId) clearTimeout(state.autosave.timerId);
  $("#editorMessage").textContent = "Unsaved changes";
  state.autosave.timerId = setTimeout(autosaveSelectedListing, 1200);
}

async function autosaveSelectedListing() {
  const listing = selectedListing();
  if (!listing || state.autosave.inFlight) return;
  state.autosave.timerId = null;
  state.autosave.inFlight = true;
  $("#editorMessage").textContent = "Autosaving...";
  try {
    await api(`/listings/${listing.id}`, {
      method: "PATCH",
      body: JSON.stringify(listingFormPayload($("#listingForm"))),
    });
    markSelectedListingMutated();
    $("#editorMessage").textContent = "Saved automatically";
    await loadAll();
  } catch (error) {
    showAppError(error, "Autosave failed; your fields remain on screen");
    $("#editorMessage").textContent = "Autosave failed - use Save to retry";
  } finally {
    state.autosave.inFlight = false;
  }
}

function qualityIssueHtml(issue) {
  return `
    <article class="quality-item">
      <div class="pane-head">
        <strong>${escapeHtml(formatFieldLabel(issue.field))}</strong>
        <span class="${statusClass(issue.severity)}">${escapeHtml(issue.severity)}</span>
      </div>
      <p>${escapeHtml(issue.message)}</p>
      <div class="recovery-row">
        <span>${escapeHtml(issue.action)}</span>
        <button type="button" class="ghost" data-focus-quality="${escapeHtml(issue.field)}">Fix</button>
      </div>
    </article>
  `;
}

function qualitySuggestionHtml(suggestion) {
  return `
    <article class="quality-item">
      <div class="pane-head">
        <strong>${escapeHtml(formatFieldLabel(suggestion.field))}</strong>
        <button type="button" class="ghost" data-apply-suggestion="${escapeHtml(suggestion.field)}">Apply</button>
      </div>
      <p>${escapeHtml(suggestion.rationale)}</p>
      <pre>${escapeHtml(formatFieldValue(suggestion.value))}</pre>
    </article>
  `;
}

function renderListingTemplateOptions() {
  const options = state.templates.map((template) => {
    const platform = template.platform ? ` (${template.platform})` : "";
    const variant = template.variant && template.variant !== "default" ? ` - ${template.variant}` : "";
    return `<option value="${template.id}">${escapeHtml(template.name)}${escapeHtml(variant)}${escapeHtml(platform)}</option>`;
  }).join("");
  $("#listingTemplateSelect").innerHTML = `<option value="">Choose template</option>${options}`;
}

function renderImages(listing) {
  state.imageRenderGeneration += 1;
  const generation = state.imageRenderGeneration;
  state.imageObjectUrls.forEach((url) => URL.revokeObjectURL(url));
  state.imageObjectUrls = [];
  const images = listing.images || [];
  $("#imageList").innerHTML = images.map((image, index) => `
    <article class="image-tile">
      <img data-image-content="${image.id}" alt="${escapeHtml(image.filename)}" />
      <strong>${escapeHtml(image.filename)}</strong>
      <div class="image-actions">
        <button class="ghost" data-move-image="${image.id}" data-direction="-1" ${index === 0 ? "disabled" : ""}>Up</button>
        <button class="ghost" data-move-image="${image.id}" data-direction="1" ${index === images.length - 1 ? "disabled" : ""}>Down</button>
        <button class="ghost" data-delete-image="${image.id}">Delete</button>
      </div>
    </article>
  `).join("") || `<p class="muted">No images uploaded.</p>`;
  void hydrateListingImages(listing, generation);
}

async function hydrateListingImages(listing, generation) {
  await Promise.all((listing.images || []).map(async (image) => {
    const headers = state.token ? { Authorization: `Bearer ${state.token}` } : {};
    try {
      const response = await fetch(`/api/listings/${listing.id}/images/${image.id}/content`, { headers });
      if (!response.ok) return;
      const blob = await response.blob();
      if (generation !== state.imageRenderGeneration || listing.id !== state.selectedListingId) return;
      const imageUrl = URL.createObjectURL(blob);
      state.imageObjectUrls.push(imageUrl);
      const node = document.querySelector(`[data-image-content="${image.id}"]`);
      if (node) node.src = imageUrl;
    } catch {
      // Metadata remains usable if an image object is temporarily unavailable.
    }
  }));
}

function renderPlatforms(listing) {
  const mappings = new Map((listing.platform_mappings || []).map((mapping) => [mapping.platform, mapping]));
  state.selectedPlatforms = new Set([...mappings.values()].filter((m) => m.status !== "skipped").map((m) => m.platform));
  $("#platformList").innerHTML = state.platforms.map((platform) => {
    const mapping = mappings.get(platform.key);
    const checked = state.selectedPlatforms.has(platform.key) ? "checked" : "";
    const override = mapping?.overrides?.description || "";
    const errors = mapping?.validation_errors?.length ? `Missing: ${mapping.validation_errors.join(", ")}` : "Ready for validation";
    const capabilities = platform.capabilities || {};
    const complianceNotes = platform.compliance_notes || [];
    return `
      <article class="platform-card">
        <label><input type="checkbox" data-platform="${platform.key}" ${checked} /> ${escapeHtml(platform.name)}</label>
        <span class="${statusClass(mapping?.status || "draft")}">${escapeHtml(mapping?.status || platform.automation_mode)}</span>
        <div class="capability-strip">
          ${capabilityChipHtml(`${(capabilities.prepared_fields || []).length} prepared fields`)}
          ${capabilityChipHtml(capabilities.requires_user_final_submission ? "manual submit" : "API submit")}
          ${capabilities.official_api_candidate ? capabilityChipHtml("API candidate") : ""}
        </div>
        ${complianceNotesHtml(complianceNotes)}
        <textarea data-platform-description="${platform.key}" placeholder="Platform description variant">${escapeHtml(override)}</textarea>
        <small class="muted">${escapeHtml(errors)}</small>
      </article>
    `;
  }).join("");
  renderPrepublishReview(listing);
}

function capabilityChipHtml(label) {
  return `<span>${escapeHtml(label)}</span>`;
}

function complianceNotesHtml(notes) {
  if (!notes?.length) return "";
  return `
    <div class="compliance-panel">
      <strong>Compliance</strong>
      <ul>${notes.map((note) => `<li>${escapeHtml(note)}</li>`).join("")}</ul>
    </div>
  `;
}

function renderPrepublishReview(listing) {
  const selectedKeys = state.platforms
    .map((platform) => platform.key)
    .filter((platformKey) => state.selectedPlatforms.has(platformKey));
  const review = $("#prepublishReview");
  if (!selectedKeys.length) {
    review.classList.add("hidden");
    review.innerHTML = "";
    return;
  }

  review.classList.remove("hidden");
  review.innerHTML = `
    <div class="pane-head">
      <h3>Prepublish review</h3>
      <span class="muted">Listing #${listing.id} - revision ${listing.revision || 1}</span>
    </div>
    <div class="review-grid">
      ${selectedKeys.map((platformKey) => reviewCardHtml(platformKey)).join("")}
    </div>
  `;
}

function reviewCardHtml(platformKey) {
  const platform = platformByKey(platformKey);
  const validation = state.validationResults[platformKey];
  const notes = platform.compliance_notes || [];
  if (!validation) {
    return `
      <article class="review-card">
        <div class="pane-head">
          <strong>${escapeHtml(platform.name)}</strong>
          <span class="status">not checked</span>
        </div>
        <p class="muted">Run validation to build the copy-ready posting package.</p>
        ${platform.posting_url ? `<a href="${escapeHtml(platform.posting_url)}" target="_blank" rel="noreferrer">Open platform</a>` : ""}
        ${complianceNotesHtml(notes)}
      </article>
    `;
  }

  const fields = Object.entries(validation.mapped_fields || {});
  const missing = validation.missing_fields || [];
  const warnings = validation.warnings || [];
  return `
    <article class="review-card">
      <div class="pane-head">
        <strong>${escapeHtml(platform.name)}</strong>
        <span class="${statusClass(validation.ready ? "ready" : "needs_user_action")}">${validation.ready ? "ready" : "needs action"}</span>
      </div>
      ${platform.posting_url ? `<a href="${escapeHtml(platform.posting_url)}" target="_blank" rel="noreferrer">Open platform</a>` : ""}
      ${missing.length ? `
        <p class="review-alert">Missing: ${escapeHtml(missing.join(", "))}</p>
        <div class="recovery-list">
          ${missing.map((field) => missingFieldRecoveryHtml(field)).join("")}
        </div>
      ` : `<p class="muted">Required fields are present.</p>`}
      ${warnings.length ? `<ul class="review-notes">${warnings.map((warning) => `<li>${escapeHtml(warning)}</li>`).join("")}</ul>` : ""}
      ${complianceNotesHtml(notes)}
      <div class="review-actions">
        <button type="button" class="ghost" data-copy-package="${platformKey}">Copy package</button>
      </div>
      <div class="field-list">
        ${fields.map(([field, value]) => `
          <div class="field-row">
            <div>
              <strong>${escapeHtml(formatFieldLabel(field))}</strong>
              <span>${escapeHtml(formatFieldValue(value))}</span>
            </div>
            <button type="button" class="ghost" data-copy-field="${platformKey}" data-copy-name="${escapeHtml(field)}">Copy</button>
          </div>
        `).join("") || `<p class="muted">No mapped fields returned.</p>`}
      </div>
    </article>
  `;
}

function formatFieldLabel(value) {
  return String(value).replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatFieldValue(value) {
  if (value === null || value === undefined || value === "") return "";
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}

function formatDateTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString();
}

function missingFieldRecoveryHtml(field) {
  return `
    <div class="recovery-row">
      <span>${escapeHtml(missingFieldHint(field))}</span>
      <button type="button" class="ghost" data-focus-missing="${escapeHtml(field)}">Fix</button>
    </div>
  `;
}

function missingFieldHint(field) {
  const hints = {
    title: "Add a title that identifies the item clearly.",
    description: "Add the buyer-facing description.",
    price_cents: "Set a price above zero.",
    condition: "Choose the item condition.",
    category: "Choose the source category or add a platform mapping.",
    location: "Add the pickup or shipping location.",
    delivery_options: "Fill delivery options or pickup/shipping flags.",
    images: "Upload at least one item image.",
  };
  return hints[field] || `Review ${formatFieldLabel(field)}.`;
}

function focusRecoveryTarget(field) {
  const fieldMap = {
    price_cents: "price",
    shipping_cost_cents: "shipping_cost",
    delivery_options: "delivery_options",
    dimensions: "dimensions",
    images: "imageInput",
  };
  if (field === "images") {
    $("#imageInput")?.focus();
    return;
  }
  const targetName = fieldMap[field] || field;
  const target = document.querySelector(`#listingForm [name="${targetName}"]`);
  if (!target) return;
  target.focus();
  target.scrollIntoView({ block: "center", behavior: "smooth" });
}

function applyQualitySuggestion(suggestion) {
  const form = $("#listingForm");
  if (!form) return;
  if (suggestion.field === "title") {
    form.title.value = String(suggestion.value || "");
  } else if (suggestion.field === "description") {
    form.description.value = String(suggestion.value || "");
  } else if (suggestion.field === "tags" && Array.isArray(suggestion.value)) {
    form.tags.value = suggestion.value.join(", ");
  } else {
    return;
  }
  $("#editorMessage").textContent = `${formatFieldLabel(suggestion.field)} suggestion applied`;
  focusRecoveryTarget(suggestion.field);
}

function packageText(platformKey) {
  const platform = platformByKey(platformKey);
  const validation = state.validationResults[platformKey];
  if (!validation) return "";
  const lines = [
    platform.name,
    platform.posting_url ? `Posting URL: ${platform.posting_url}` : "",
    `Ready: ${validation.ready ? "yes" : "no"}`,
    (validation.missing_fields || []).length ? `Missing: ${validation.missing_fields.join(", ")}` : "",
    "",
    ...Object.entries(validation.mapped_fields || {}).map(
      ([field, value]) => `${formatFieldLabel(field)}: ${formatFieldValue(value)}`
    ),
  ];
  return lines.filter((line, index) => line || index > 3).join("\n").trim();
}

async function copyText(text) {
  if (!text) return;
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  textarea.remove();
}

function renderJobs() {
  const platformOptions = state.platforms.map((platform) => `<option value="${platform.key}">${escapeHtml(platform.name)}</option>`).join("");
  $("#jobPlatformFilter").innerHTML = `<option value="">All platforms</option>${platformOptions}`;
  $("#jobPlatformFilter").value = state.jobQuery.platform;
  $("#jobStatusFilter").value = state.jobQuery.status;
  $("#jobSort").value = state.jobQuery.sort;
  const start = state.jobQuery.total ? state.jobQuery.offset + 1 : 0;
  const end = Math.min(state.jobQuery.offset + state.jobQuery.limit, state.jobQuery.total);
  $("#jobPageInfo").textContent = `${start}-${end} of ${state.jobQuery.total}`;
  $("#jobPrevPage").disabled = state.jobQuery.offset === 0;
  $("#jobNextPage").disabled = state.jobQuery.offset + state.jobQuery.limit >= state.jobQuery.total;
  $("#jobList").innerHTML = state.jobs.map(jobItemHtml).join("") || `<p class="muted">No assisted packages queued.</p>`;
}

function renderAccounts() {
  const platformOptions = state.platforms.map((platform) => `<option value="${platform.key}">${escapeHtml(platform.name)}</option>`).join("");
  $("#accountPlatform").innerHTML = platformOptions;
  $("#templatePlatform").innerHTML = `<option value="">All platforms</option>${platformOptions}`;
  $("#mappingPlatform").innerHTML = platformOptions;
  $("#accountPlatformFilter").innerHTML = `<option value="">All platforms</option>${platformOptions}`;
  $("#accountPlatformFilter").value = state.accountQuery.platform;
  $("#accountStatusFilter").value = state.accountQuery.status;
  $("#accountSort").value = state.accountQuery.sort;
  const start = state.accountQuery.total ? state.accountQuery.offset + 1 : 0;
  const end = Math.min(state.accountQuery.offset + state.accountQuery.limit, state.accountQuery.total);
  $("#accountPageInfo").textContent = `${start}-${end} of ${state.accountQuery.total}`;
  $("#accountPrevPage").disabled = state.accountQuery.offset === 0;
  $("#accountNextPage").disabled = state.accountQuery.offset + state.accountQuery.limit >= state.accountQuery.total;
  $("#accountList").innerHTML = state.accounts.map((account) => `
    <article class="list-item">
      <div class="pane-head">
        <strong>${escapeHtml(account.display_name)}</strong>
        <div class="row compact-actions">
          <button class="ghost" data-edit-account="${account.id}">Edit</button>
          <button class="ghost" data-delete-account="${account.id}">Delete</button>
        </div>
      </div>
      <span class="muted">${escapeHtml(account.platform)} · ${escapeHtml(account.mode)}</span>
      <span class="${statusClass(account.status)}">${escapeHtml(account.status)}</span>
    </article>
  `).join("") || `<p class="muted">No platform accounts.</p>`;
}

function renderSettings() {
  const platformOptions = state.platforms.map((platform) => `<option value="${platform.key}">${escapeHtml(platform.name)}</option>`).join("");
  $("#templatePlatformFilter").innerHTML = `<option value="">All platforms</option>${platformOptions}`;
  $("#templatePlatformFilter").value = state.templateQuery.platform;
  $("#templateVariantFilter").value = state.templateQuery.variant;
  $("#templateSearch").value = state.templateQuery.search;
  $("#templateSort").value = state.templateQuery.sort;
  const templateStart = state.templateQuery.total ? state.templateQuery.offset + 1 : 0;
  const templateEnd = Math.min(state.templateQuery.offset + state.templateQuery.limit, state.templateQuery.total);
  $("#templatePageInfo").textContent = `${templateStart}-${templateEnd} of ${state.templateQuery.total}`;
  $("#templatePrevPage").disabled = state.templateQuery.offset === 0;
  $("#templateNextPage").disabled = state.templateQuery.offset + state.templateQuery.limit >= state.templateQuery.total;

  $("#mappingPlatformFilter").innerHTML = `<option value="">All platforms</option>${platformOptions}`;
  $("#mappingPlatformFilter").value = state.mappingQuery.platform;
  $("#mappingSourceFilter").value = state.mappingQuery.sourceCategory;
  $("#mappingSort").value = state.mappingQuery.sort;
  const mappingStart = state.mappingQuery.total ? state.mappingQuery.offset + 1 : 0;
  const mappingEnd = Math.min(state.mappingQuery.offset + state.mappingQuery.limit, state.mappingQuery.total);
  $("#mappingPageInfo").textContent = `${mappingStart}-${mappingEnd} of ${state.mappingQuery.total}`;
  $("#mappingPrevPage").disabled = state.mappingQuery.offset === 0;
  $("#mappingNextPage").disabled = state.mappingQuery.offset + state.mappingQuery.limit >= state.mappingQuery.total;

  $("#templateList").innerHTML = state.templates.map((template) => `
    <article class="list-item">
      <div class="pane-head">
        <strong>${escapeHtml(template.name)}</strong>
        <div class="row compact-actions">
          <button class="ghost" data-edit-template="${template.id}">Edit</button>
          <button class="ghost" data-delete-template="${template.id}">Delete</button>
        </div>
      </div>
      <span class="muted">${escapeHtml(template.variant || "default")} - ${escapeHtml(template.platform || "All platforms")}</span>
      <p>${escapeHtml(template.body.slice(0, 160))}</p>
    </article>
  `).join("") || `<p class="muted">No templates saved.</p>`;
  $("#categoryMappingList").innerHTML = state.categoryMappings.map((mapping) => `
    <article class="list-item">
      <div class="pane-head">
        <strong>${escapeHtml(mapping.source_category)}</strong>
        <div class="row compact-actions">
          <button class="ghost" data-edit-category-mapping="${mapping.id}">Edit</button>
          <button class="ghost" data-delete-category-mapping="${mapping.id}">Delete</button>
        </div>
      </div>
      <span class="muted">${escapeHtml(mapping.platform)} -> ${escapeHtml(mapping.platform_category)}</span>
    </article>
  `).join("") || `<p class="muted">No category mappings saved.</p>`;

  $("#auditEventList").innerHTML = state.auditEvents.map((event) => `
    <article class="list-item">
      <div class="pane-head">
        <strong>${escapeHtml(formatFieldLabel(event.action))}</strong>
        <span class="muted">${escapeHtml(formatDateTime(event.created_at))}</span>
      </div>
      <pre>${escapeHtml(JSON.stringify(event.event_data || {}, null, 2))}</pre>
    </article>
  `).join("") || `<p class="muted">No privacy activity yet.</p>`;

  $("#haiTokenList").innerHTML = state.haiTokens.map((token) => `
    <article class="list-item">
      <div class="pane-head">
        <div>
          <strong>${escapeHtml(token.name)}</strong>
          <span class="muted">Read only - expires ${escapeHtml(formatDateTime(token.expires_at))}</span>
        </div>
        <button type="button" class="ghost" data-revoke-hai-token="${token.id}">Revoke</button>
      </div>
      <span class="muted">${token.last_used_at ? `Last used ${escapeHtml(formatDateTime(token.last_used_at))}` : "Not used yet"}</span>
    </article>
  `).join("") || `<p class="muted">No active HAI connections.</p>`;

  const tokenOnce = $("#haiTokenOnce");
  if (state.newHaiToken) {
    tokenOnce.classList.remove("hidden");
    tokenOnce.innerHTML = `
      <strong>Copy this token now. It will not be shown again.</strong>
      <code>${escapeHtml(state.newHaiToken)}</code>
      <button type="button" class="ghost" id="copyHaiTokenButton">Copy token</button>
    `;
  } else {
    tokenOnce.textContent = "";
    tokenOnce.classList.add("hidden");
  }
}

function renderDiagnostics(result) {
  const checks = result.doctor?.checks || [];
  $("#diagnosticsOutput").classList.remove("muted");
  $("#diagnosticsOutput").innerHTML = `
    <div class="pane-head">
      <strong>Status: ${escapeHtml(result.status)}</strong>
      <span class="${statusClass(result.status)}">${escapeHtml(result.doctor?.status || result.status)}</span>
    </div>
    <p class="muted">${Number(result.listings || 0)} listings · ${Number(result.jobs || 0)} jobs · ${(result.platforms || []).length} platforms</p>
    <div class="diagnostic-checks">
      ${checks.map((check) => `
        <article class="diagnostic-check">
          <div class="pane-head">
            <strong>${escapeHtml(check.name)}</strong>
            <span class="${statusClass(check.status)}">${escapeHtml(check.status)}</span>
          </div>
          <p>${escapeHtml(check.message)}</p>
        </article>
      `).join("")}
    </div>
  `;
}

function parseDeliveryOptions(value) {
  if (!value.trim()) return {};
  try {
    return JSON.parse(value);
  } catch {
    return { note: value };
  }
}

async function savePlatformOverrides() {
  const listing = selectedListing();
  if (!listing) return;
  const cards = document.querySelectorAll("[data-platform]");
  for (const checkbox of cards) {
    const platform = checkbox.dataset.platform;
    const description = document.querySelector(`[data-platform-description="${platform}"]`)?.value || "";
    await api(`/listings/${listing.id}/platforms`, {
      method: "POST",
      body: JSON.stringify({
        platform,
        selected: checkbox.checked,
        overrides: description ? { description } : {},
      }),
    });
  }
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  })[char]);
}

window.addEventListener("unhandledrejection", (event) => {
  event.preventDefault();
  showAppError(event.reason, "Something went wrong");
});

async function boot() {
  applyTranslations();
  try {
    state.localization = await api("/localization", { headers: {} });
    const supported = new Set((state.localization.supported_locales || []).map((locale) => locale.code));
    if (!supported.has(state.locale)) state.locale = state.localization.default_locale || "en";
    applyTranslations();
  } catch {
    applyTranslations();
  }

  try {
    const health = await api("/health", { headers: {} });
    $("#healthBadge").textContent = health.status;
  } catch {
    $("#healthBadge").textContent = t("status.offline");
  }

  if (!state.token) return;
  try {
    state.user = await api("/auth/me");
    $("#userEmail").textContent = state.user.email;
    $("#authView").classList.add("hidden");
    $("#shell").classList.remove("hidden");
  } catch {
    localStorage.removeItem("autoposterToken");
    state.token = null;
    return;
  }

  try {
    await loadAll();
    await loadRequestedListing();
  } catch (error) {
    showAppError(error);
  }
}

$("#authForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("#authError").textContent = "";
  try {
    const payload = {
      email: $("#authEmail").value,
      password: $("#authPassword").value,
      name: $("#authName").value,
    };
    const data = await api("/auth/login", { method: "POST", body: JSON.stringify(payload) });
    state.token = data.token;
    localStorage.setItem("autoposterToken", data.token);
    await boot();
  } catch (error) {
    $("#authError").textContent = error.message;
  }
});

$("#registerButton").addEventListener("click", async () => {
  $("#authError").textContent = "";
  try {
    const data = await api("/auth/register", {
      method: "POST",
      body: JSON.stringify({
        email: $("#authEmail").value,
        password: $("#authPassword").value,
        name: $("#authName").value,
      }),
    });
    state.token = data.token;
    localStorage.setItem("autoposterToken", data.token);
    await boot();
  } catch (error) {
    $("#authError").textContent = error.message;
  }
});

$("#logoutButton").addEventListener("click", () => {
  api("/auth/logout", { method: "POST" }).finally(() => {
    localStorage.removeItem("autoposterToken");
    window.location.reload();
  });
});

document.querySelectorAll(".nav").forEach((node) => node.addEventListener("click", () => show(node.dataset.view)));

$("#localeSelect")?.addEventListener("change", (event) => setLocale(event.target.value));

$("#newListingButton").addEventListener("click", async () => {
  const listing = await api("/listings", {
    method: "POST",
    body: JSON.stringify({ title: "Untitled listing", status: "draft" }),
  });
  selectListing(listing.id);
  state.listingQuery.search = "";
  state.listingQuery.status = "";
  state.listingQuery.sort = "-updated_at";
  state.listingQuery.offset = 0;
  show("listings");
  await loadAll();
});

$("#refreshButton").addEventListener("click", loadAll);

$("#refreshJobsButton").addEventListener("click", refreshJobsOnly);

$("#jobPollingToggle").addEventListener("click", () => {
  state.jobPolling.enabled = !state.jobPolling.enabled;
  scheduleJobPolling();
});

$("#listingSearch").addEventListener("input", (event) => {
  clearTimeout(listingSearchTimer);
  listingSearchTimer = setTimeout(async () => {
    state.listingQuery.search = event.target.value;
    state.listingQuery.offset = 0;
    await loadListingPage();
  }, 250);
});

$("#listingStatusFilter").addEventListener("change", async (event) => {
  state.listingQuery.status = event.target.value;
  state.listingQuery.offset = 0;
  await loadListingPage();
});

$("#listingSort").addEventListener("change", async (event) => {
  state.listingQuery.sort = event.target.value;
  state.listingQuery.offset = 0;
  await loadListingPage();
});

$("#listingPrevPage").addEventListener("click", async () => {
  state.listingQuery.offset = Math.max(0, state.listingQuery.offset - state.listingQuery.limit);
  await loadListingPage();
});

$("#listingNextPage").addEventListener("click", async () => {
  const nextOffset = state.listingQuery.offset + state.listingQuery.limit;
  if (nextOffset >= state.listingQuery.total) return;
  state.listingQuery.offset = nextOffset;
  await loadListingPage();
});

$("#jobPlatformFilter").addEventListener("change", async (event) => {
  state.jobQuery.platform = event.target.value;
  state.jobQuery.offset = 0;
  await loadJobPage();
});

$("#jobStatusFilter").addEventListener("change", async (event) => {
  state.jobQuery.status = event.target.value;
  state.jobQuery.offset = 0;
  await loadJobPage();
});

$("#jobSort").addEventListener("change", async (event) => {
  state.jobQuery.sort = event.target.value;
  state.jobQuery.offset = 0;
  await loadJobPage();
});

$("#jobPrevPage").addEventListener("click", async () => {
  state.jobQuery.offset = Math.max(0, state.jobQuery.offset - state.jobQuery.limit);
  await loadJobPage();
});

$("#jobNextPage").addEventListener("click", async () => {
  const nextOffset = state.jobQuery.offset + state.jobQuery.limit;
  if (nextOffset >= state.jobQuery.total) return;
  state.jobQuery.offset = nextOffset;
  await loadJobPage();
});

$("#accountPlatformFilter").addEventListener("change", async (event) => {
  state.accountQuery.platform = event.target.value;
  state.accountQuery.offset = 0;
  await loadAccountPage();
});

$("#accountStatusFilter").addEventListener("change", async (event) => {
  state.accountQuery.status = event.target.value;
  state.accountQuery.offset = 0;
  await loadAccountPage();
});

$("#accountSort").addEventListener("change", async (event) => {
  state.accountQuery.sort = event.target.value;
  state.accountQuery.offset = 0;
  await loadAccountPage();
});

$("#accountPrevPage").addEventListener("click", async () => {
  state.accountQuery.offset = Math.max(0, state.accountQuery.offset - state.accountQuery.limit);
  await loadAccountPage();
});

$("#accountNextPage").addEventListener("click", async () => {
  const nextOffset = state.accountQuery.offset + state.accountQuery.limit;
  if (nextOffset >= state.accountQuery.total) return;
  state.accountQuery.offset = nextOffset;
  await loadAccountPage();
});

$("#templateSearch").addEventListener("input", (event) => {
  clearTimeout(templateSearchTimer);
  templateSearchTimer = setTimeout(async () => {
    state.templateQuery.search = event.target.value;
    state.templateQuery.offset = 0;
    await loadTemplatePage();
  }, 250);
});

$("#templatePlatformFilter").addEventListener("change", async (event) => {
  state.templateQuery.platform = event.target.value;
  state.templateQuery.offset = 0;
  await loadTemplatePage();
});

$("#templateVariantFilter").addEventListener("input", (event) => {
  clearTimeout(templateSearchTimer);
  templateSearchTimer = setTimeout(async () => {
    state.templateQuery.variant = event.target.value;
    state.templateQuery.offset = 0;
    await loadTemplatePage();
  }, 250);
});

$("#templateSort").addEventListener("change", async (event) => {
  state.templateQuery.sort = event.target.value;
  state.templateQuery.offset = 0;
  await loadTemplatePage();
});

$("#templatePrevPage").addEventListener("click", async () => {
  state.templateQuery.offset = Math.max(0, state.templateQuery.offset - state.templateQuery.limit);
  await loadTemplatePage();
});

$("#templateNextPage").addEventListener("click", async () => {
  const nextOffset = state.templateQuery.offset + state.templateQuery.limit;
  if (nextOffset >= state.templateQuery.total) return;
  state.templateQuery.offset = nextOffset;
  await loadTemplatePage();
});

$("#mappingSourceFilter").addEventListener("input", (event) => {
  clearTimeout(mappingSearchTimer);
  mappingSearchTimer = setTimeout(async () => {
    state.mappingQuery.sourceCategory = event.target.value;
    state.mappingQuery.offset = 0;
    await loadMappingPage();
  }, 250);
});

$("#mappingPlatformFilter").addEventListener("change", async (event) => {
  state.mappingQuery.platform = event.target.value;
  state.mappingQuery.offset = 0;
  await loadMappingPage();
});

$("#mappingSort").addEventListener("change", async (event) => {
  state.mappingQuery.sort = event.target.value;
  state.mappingQuery.offset = 0;
  await loadMappingPage();
});

$("#mappingPrevPage").addEventListener("click", async () => {
  state.mappingQuery.offset = Math.max(0, state.mappingQuery.offset - state.mappingQuery.limit);
  await loadMappingPage();
});

$("#mappingNextPage").addEventListener("click", async () => {
  const nextOffset = state.mappingQuery.offset + state.mappingQuery.limit;
  if (nextOffset >= state.mappingQuery.total) return;
  state.mappingQuery.offset = nextOffset;
  await loadMappingPage();
});

$("#listingList").addEventListener("click", (event) => {
  const item = event.target.closest("[data-listing-id]");
  if (!item) return;
  selectListing(item.dataset.listingId);
  renderListings();
});

$("#recentListings").addEventListener("click", (event) => {
  const item = event.target.closest("[data-listing-id]");
  if (!item) return;
  selectListing(item.dataset.listingId);
  show("listings");
  renderListings();
});

$("#dashboardView").addEventListener("click", (event) => {
  const target = event.target.closest("[data-action-view]");
  if (!target) return;
  const resourceType = target.dataset.actionResource;
  const resourceId = Number(target.dataset.actionResourceId || 0);
  if (resourceType === "listing" && resourceId) selectListing(resourceId);
  show(target.dataset.actionView);
  render();
});

$("#listingForm").addEventListener("input", scheduleListingAutosave);
$("#listingForm").addEventListener("change", scheduleListingAutosave);

$("#listingForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const listing = selectedListing();
  if (!listing) return;
  const form = event.currentTarget;
  if (state.autosave.timerId) {
    clearTimeout(state.autosave.timerId);
    state.autosave.timerId = null;
  }
  await api(`/listings/${listing.id}`, {
    method: "PATCH",
    body: JSON.stringify(listingFormPayload(form)),
  });
  await savePlatformOverrides();
  markSelectedListingMutated();
  $("#editorMessage").textContent = "Saved";
  await loadAll();
});

$("#applyTemplateButton").addEventListener("click", () => {
  const templateId = Number($("#listingTemplateSelect").value);
  const template = state.templates.find((candidate) => candidate.id === templateId);
  if (!template) return;
  const description = $("#listingForm").description;
  description.value = [description.value.trim(), template.body.trim()].filter(Boolean).join("\n\n");
  $("#editorMessage").textContent = "Template applied";
  scheduleListingAutosave();
});

$("#duplicateButton").addEventListener("click", async () => {
  const listing = selectedListing();
  if (!listing) return;
  const clone = await api(`/listings/${listing.id}/duplicate`, { method: "POST" });
  selectListing(clone.id);
  await loadAll();
});

$("#deleteListingButton").addEventListener("click", async () => {
  const listing = selectedListing();
  if (!listing) return;
  await api(`/listings/${listing.id}`, { method: "DELETE" });
  selectListing(null);
  await loadAll();
});

$("#imageInput").addEventListener("change", async (event) => {
  const listing = selectedListing();
  if (!listing || !event.target.files.length) return;
  for (const file of event.target.files) {
    const data = new FormData();
    data.append("file", file);
    await api(`/listings/${listing.id}/images`, { method: "POST", body: data, headers: {} });
  }
  event.target.value = "";
  markSelectedListingMutated();
  await loadAll();
});

$("#imageList").addEventListener("click", async (event) => {
  const listing = selectedListing();
  if (!listing) return;
  const moveButton = event.target.closest("[data-move-image]");
  if (moveButton) {
    const imageId = Number(moveButton.dataset.moveImage);
    const direction = Number(moveButton.dataset.direction);
    const imageIds = (listing.images || []).map((image) => image.id);
    const index = imageIds.indexOf(imageId);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= imageIds.length) return;
    [imageIds[index], imageIds[target]] = [imageIds[target], imageIds[index]];
    await api(`/listings/${listing.id}/images/order`, {
      method: "PATCH",
      body: JSON.stringify({ image_ids: imageIds }),
    });
    markSelectedListingMutated();
    await loadAll();
    return;
  }
  const deleteButton = event.target.closest("[data-delete-image]");
  if (!deleteButton) return;
  await api(`/listings/${listing.id}/images/${deleteButton.dataset.deleteImage}`, { method: "DELETE" });
  markSelectedListingMutated();
  await loadAll();
});

$("#platformList").addEventListener("change", (event) => {
  const checkbox = event.target.closest("[data-platform]");
  if (!checkbox) return;
  if (checkbox.checked) {
    state.selectedPlatforms.add(checkbox.dataset.platform);
  } else {
    state.selectedPlatforms.delete(checkbox.dataset.platform);
  }
  resetListingReviewState();
  const listing = selectedListing();
  if (listing) renderPrepublishReview(listing);
});

$("#platformList").addEventListener("input", (event) => {
  if (!event.target.closest("[data-platform-description]")) return;
  resetListingReviewState();
  const listing = selectedListing();
  if (listing) renderPrepublishReview(listing);
});

$("#validateButton").addEventListener("click", async () => {
  const listing = selectedListing();
  if (!listing) return;
  await savePlatformOverrides();
  const selectedPlatforms = [...state.selectedPlatforms];
  const validationRequests = selectedPlatforms.length
    ? selectedPlatforms.map((platform) => api(`/listings/${listing.id}/validate?platform=${encodeURIComponent(platform)}`))
    : [api(`/listings/${listing.id}/validate`)];
  const results = (await Promise.all(validationRequests)).flat();
  state.validationResults = Object.fromEntries(results.map((result) => [result.platform, result]));
  $("#editorMessage").textContent = `${results.filter((item) => item.ready).length}/${results.length} ready`;
  await loadAll();
});

$("#qualityButton").addEventListener("click", async () => {
  const listing = selectedListing();
  if (!listing) return;
  state.qualityResult = await api(`/listings/${listing.id}/quality`);
  $("#editorMessage").textContent = `Quality ${state.qualityResult.score}/100`;
  renderQualityAssistant();
});

$("#qualityAssistant").addEventListener("click", (event) => {
  const focusButton = event.target.closest("[data-focus-quality]");
  if (focusButton) {
    focusRecoveryTarget(focusButton.dataset.focusQuality);
    return;
  }
  const applyButton = event.target.closest("[data-apply-suggestion]");
  if (!applyButton || !state.qualityResult) return;
  const suggestion = (state.qualityResult.suggestions || []).find(
    (candidate) => candidate.field === applyButton.dataset.applySuggestion
  );
  if (!suggestion) return;
  applyQualitySuggestion(suggestion);
});

$("#prepublishReview").addEventListener("click", async (event) => {
  const packageButton = event.target.closest("[data-copy-package]");
  if (packageButton) {
    await copyText(packageText(packageButton.dataset.copyPackage));
    $("#editorMessage").textContent = "Package copied";
    return;
  }
  const fieldButton = event.target.closest("[data-copy-field]");
  if (fieldButton) {
    const validation = state.validationResults[fieldButton.dataset.copyField];
    const value = validation?.mapped_fields?.[fieldButton.dataset.copyName];
    await copyText(formatFieldValue(value));
    $("#editorMessage").textContent = "Field copied";
    return;
  }
  const fixButton = event.target.closest("[data-focus-missing]");
  if (!fixButton) return;
  focusRecoveryTarget(fixButton.dataset.focusMissing);
  $("#editorMessage").textContent = `Review ${formatFieldLabel(fixButton.dataset.focusMissing)}`;
});

async function queueAssistedPackage({ forceNewRevision = false } = {}) {
  const listing = selectedListing();
  if (!listing) return;
  await savePlatformOverrides();
  const platforms = [...document.querySelectorAll("[data-platform]")]
    .filter((checkbox) => checkbox.checked)
    .map((checkbox) => checkbox.dataset.platform);
  if (!platforms.length) {
    $("#editorMessage").textContent = "Select at least one platform";
    return;
  }
  await api(`/listings/${listing.id}/publish`, {
    method: "POST",
    body: JSON.stringify({ platforms, process_now: true, force_new_revision: forceNewRevision }),
  });
  resetListingReviewState();
  state.jobQuery.offset = 0;
  $("#editorMessage").textContent = forceNewRevision ? "Fresh assisted package queued" : "Assisted package queued";
  show("queue");
  await loadAll();
}

$("#publishButton").addEventListener("click", () => queueAssistedPackage());

$("#regeneratePackageButton").addEventListener("click", () => queueAssistedPackage({ forceNewRevision: true }));

$("#jobList").addEventListener("click", (event) => {
  const item = event.target.closest("[data-job-id]");
  if (!item) return;
  const job = state.jobs.find((candidate) => candidate.id === Number(item.dataset.jobId));
  if (!job) return;
  $("#jobDetails").classList.remove("hidden");
  $("#jobDetails").innerHTML = `
    <div class="pane-head">
      <h3>${escapeHtml(job.platform)} job #${job.id}</h3>
      <button class="ghost" id="retryJobButton">Retry</button>
    </div>
    <p><span class="${statusClass(job.status)}">${escapeHtml(job.status)}</span></p>
    <p class="muted">${escapeHtml(job.error_message || job.result?.posting_url || "")}</p>
    <p class="retry-guidance">${escapeHtml(jobRetryGuidance(job))}</p>
    ${manualCompletionHtml(job)}
    <h3>Logs</h3>
    ${(job.logs || []).map((log) => `<p class="job-log">${escapeHtml(log.message)}</p>`).join("")}
  `;
  $("#retryJobButton").addEventListener("click", async () => {
    await api(`/jobs/${job.id}/retry`, { method: "POST" });
    await loadAll();
  });
  $("#manualCompletionForm")?.addEventListener("submit", async (submitEvent) => {
    submitEvent.preventDefault();
    await api(`/jobs/${job.id}/manual-completion`, {
      method: "POST",
      body: JSON.stringify({
        platform_url: $("#manualPlatformUrl").value,
        platform_listing_id: $("#manualPlatformListingId").value || null,
      }),
    });
    await loadAll();
  });
});

function manualCompletionHtml(job) {
  if (job.status !== "needs_user_action") return "";
  return `
    <form id="manualCompletionForm" class="manual-completion">
      <h3>${escapeHtml(t("queue.manualCompletion"))}</h3>
      <label>${escapeHtml(t("queue.platformUrl"))}<input id="manualPlatformUrl" type="url" required /></label>
      <label>${escapeHtml(t("queue.platformListingId"))}<input id="manualPlatformListingId" /></label>
      <button type="submit">${escapeHtml(t("queue.complete"))}</button>
    </form>
  `;
}

function jobRetryGuidance(job) {
  if (job.status === "failed") return "Retry after fixing the listing, platform account, or reported validation issue.";
  if (job.status === "needs_user_action") {
    return "Retry only if you want to regenerate the assisted package after changing the listing.";
  }
  if (job.next_retry_at) return `This job is waiting for its cooldown until ${new Date(job.next_retry_at).toLocaleString()}.`;
  return "Retry requeues this job; use it only when the previous attempt is stale or intentionally corrected.";
}

$("#accountForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const accountId = event.currentTarget.dataset.accountId;
  await api(accountId ? `/accounts/${accountId}` : "/accounts", {
    method: accountId ? "PATCH" : "POST",
    body: JSON.stringify({
      platform: $("#accountPlatform").value,
      display_name: $("#accountName").value,
      status: $("#accountStatus").value,
      mode: "assisted",
      connection_data: {},
    }),
  });
  $("#accountName").value = "";
  delete event.currentTarget.dataset.accountId;
  $("#accountForm button[type='submit']").textContent = "Save account";
  $("#cancelAccountEditButton").classList.add("hidden");
  state.accountQuery.offset = 0;
  await loadAll();
});

$("#cancelAccountEditButton").addEventListener("click", () => {
  $("#accountName").value = "";
  delete $("#accountForm").dataset.accountId;
  $("#accountForm button[type='submit']").textContent = "Save account";
  $("#cancelAccountEditButton").classList.add("hidden");
});

$("#accountList").addEventListener("click", async (event) => {
  const editButton = event.target.closest("[data-edit-account]");
  if (editButton) {
    const account = state.accounts.find((candidate) => candidate.id === Number(editButton.dataset.editAccount));
    if (!account) return;
    $("#accountPlatform").value = account.platform;
    $("#accountName").value = account.display_name;
    $("#accountStatus").value = account.status;
    $("#accountForm").dataset.accountId = account.id;
    $("#accountForm button[type='submit']").textContent = "Update account";
    $("#cancelAccountEditButton").classList.remove("hidden");
    return;
  }
  const deleteButton = event.target.closest("[data-delete-account]");
  if (!deleteButton) return;
  await api(`/accounts/${deleteButton.dataset.deleteAccount}`, { method: "DELETE" });
  await loadAll();
});

$("#templateForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const templateId = event.currentTarget.dataset.templateId;
  await api(templateId ? `/templates/${templateId}` : "/templates", {
    method: templateId ? "PATCH" : "POST",
    body: JSON.stringify({
      name: $("#templateName").value,
      variant: $("#templateVariant").value || "default",
      platform: $("#templatePlatform").value || null,
      body: $("#templateBody").value,
    }),
  });
  $("#templateName").value = "";
  $("#templateVariant").value = "default";
  $("#templateBody").value = "";
  $("#templatePlatform").value = "";
  delete event.currentTarget.dataset.templateId;
  $("#templateForm button[type='submit']").textContent = "Save template";
  $("#cancelTemplateEditButton").classList.add("hidden");
  state.templateQuery.offset = 0;
  await loadAll();
});

$("#cancelTemplateEditButton").addEventListener("click", () => {
  $("#templateName").value = "";
  $("#templateVariant").value = "default";
  $("#templateBody").value = "";
  $("#templatePlatform").value = "";
  delete $("#templateForm").dataset.templateId;
  $("#templateForm button[type='submit']").textContent = "Save template";
  $("#cancelTemplateEditButton").classList.add("hidden");
});

$("#templateList").addEventListener("click", async (event) => {
  const editButton = event.target.closest("[data-edit-template]");
  if (editButton) {
    const template = state.templates.find((candidate) => candidate.id === Number(editButton.dataset.editTemplate));
    if (!template) return;
    $("#templateName").value = template.name;
    $("#templateVariant").value = template.variant || "default";
    $("#templatePlatform").value = template.platform || "";
    $("#templateBody").value = template.body;
    $("#templateForm").dataset.templateId = template.id;
    $("#templateForm button[type='submit']").textContent = "Update template";
    $("#cancelTemplateEditButton").classList.remove("hidden");
    return;
  }
  const deleteButton = event.target.closest("[data-delete-template]");
  if (!deleteButton) return;
  await api(`/templates/${deleteButton.dataset.deleteTemplate}`, { method: "DELETE" });
  await loadAll();
});

$("#categoryMappingForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const mappingId = event.currentTarget.dataset.mappingId;
  const payload = {
    source_category: $("#mappingSourceCategory").value,
    platform: $("#mappingPlatform").value,
    platform_category: $("#mappingPlatformCategory").value,
  };
  await api(mappingId ? `/category-mappings/${mappingId}` : "/category-mappings", {
    method: mappingId ? "PATCH" : "POST",
    body: JSON.stringify(payload),
  });
  $("#mappingSourceCategory").value = "";
  $("#mappingPlatformCategory").value = "";
  delete event.currentTarget.dataset.mappingId;
  $("#categoryMappingForm button[type='submit']").textContent = "Save mapping";
  state.mappingQuery.offset = 0;
  await loadAll();
});

$("#categoryMappingList").addEventListener("click", async (event) => {
  const editButton = event.target.closest("[data-edit-category-mapping]");
  if (editButton) {
    const mapping = state.categoryMappings.find((candidate) => candidate.id === Number(editButton.dataset.editCategoryMapping));
    if (!mapping) return;
    $("#mappingSourceCategory").value = mapping.source_category;
    $("#mappingPlatform").value = mapping.platform;
    $("#mappingPlatformCategory").value = mapping.platform_category;
    $("#categoryMappingForm").dataset.mappingId = mapping.id;
    $("#categoryMappingForm button[type='submit']").textContent = "Update mapping";
    return;
  }
  const deleteButton = event.target.closest("[data-delete-category-mapping]");
  if (!deleteButton) return;
  await api(`/category-mappings/${deleteButton.dataset.deleteCategoryMapping}`, { method: "DELETE" });
  await loadAll();
});

$("#haiTokenForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const created = await api("/hai/tokens", {
    method: "POST",
    body: JSON.stringify({
      name: $("#haiTokenName").value,
      expires_days: Number($("#haiTokenExpiry").value),
    }),
  });
  state.newHaiToken = created.token;
  state.haiTokens = [created, ...state.haiTokens];
  renderSettings();
});

$("#haiTokenList").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-revoke-hai-token]");
  if (!button) return;
  await api(`/hai/tokens/${button.dataset.revokeHaiToken}`, { method: "DELETE" });
  state.haiTokens = state.haiTokens.filter((token) => token.id !== Number(button.dataset.revokeHaiToken));
  renderSettings();
});

$("#haiTokenOnce").addEventListener("click", async (event) => {
  if (!event.target.closest("#copyHaiTokenButton") || !state.newHaiToken) return;
  await copyText(state.newHaiToken);
  event.target.textContent = "Copied";
});

$("#exportDataButton").addEventListener("click", async () => {
  const bundle = await api("/export");
  const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `autoposter-export-${new Date().toISOString().slice(0, 10)}.json`;
  link.click();
  URL.revokeObjectURL(link.href);
  $("#dataPortabilityMessage").textContent = "Export ready";
});

$("#exportListingsCsvButton").addEventListener("click", async () => {
  await downloadApiFile("/export/listings.csv", `autoposter-listings-${new Date().toISOString().slice(0, 10)}.csv`);
  $("#dataPortabilityMessage").textContent = "Listings CSV export ready";
});

$("#exportImagesZipButton").addEventListener("click", async () => {
  await downloadApiFile("/export/images.zip", `autoposter-images-${new Date().toISOString().slice(0, 10)}.zip`);
  $("#dataPortabilityMessage").textContent = "Images ZIP export ready";
});

$("#importDataInput").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  try {
    const bundle = JSON.parse(await file.text());
    const result = await api("/import", { method: "POST", body: JSON.stringify(bundle) });
    $("#dataPortabilityMessage").textContent =
      `Imported ${result.listings_created} listings, ${result.templates_created + result.templates_updated} templates, ` +
      `${result.category_mappings_created + result.category_mappings_updated} mappings`;
    await loadAll();
  } catch (error) {
    $("#dataPortabilityMessage").textContent = [
      error.message,
      error.retryable ? "Try the import again after checking the file." : "",
      error.requestId ? `Request ID: ${error.requestId}` : "",
    ].filter(Boolean).join(" ");
  } finally {
    event.target.value = "";
  }
});

$("#importListingsCsvInput").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  try {
    const formData = new FormData();
    formData.append("file", file);
    const result = await api("/import/listings.csv", { method: "POST", body: formData });
    $("#dataPortabilityMessage").textContent = `Imported ${result.listings_created} listings from CSV`;
    await loadAll();
  } catch (error) {
    $("#dataPortabilityMessage").textContent = [
      error.message,
      error.retryable ? "Try the import again after checking the CSV file." : "",
      error.requestId ? `Request ID: ${error.requestId}` : "",
    ].filter(Boolean).join(" ");
  } finally {
    event.target.value = "";
  }
});

$("#runDiagnosticsButton").addEventListener("click", async () => {
  const diagnostics = await api("/diagnostics");
  renderDiagnostics(diagnostics);
});

$("#deleteMyDataButton").addEventListener("click", async () => {
  const confirmation = window.prompt("Type DELETE to permanently remove your account data.");
  if (confirmation !== "DELETE") return;
  await api("/auth/me", { method: "DELETE" });
  localStorage.removeItem("autoposterToken");
  window.location.reload();
});

boot();
