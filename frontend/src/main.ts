import "./style.css";
import * as api from "./api";
import type { ChatEntry, FileInfo } from "./types";
import { renderReply } from "./markdown";

const TEMPLATE_KEYS: { key: string; label: string }[] = [
  { key: "overview", label: "Обзор продаж" },
  { key: "top_products", label: "Топ товаров" },
  { key: "comparison", label: "Сравнение периодов" },
  { key: "anomalies", label: "Аномалии" },
];

const $ = <T extends Element>(sel: string) => document.querySelector(sel) as T;

const el = {
  statusDot: $<HTMLSpanElement>("#statusDot"),
  statusText: $<HTMLSpanElement>("#statusText"),
  modelSelect: $<HTMLSelectElement>("#modelSelect"),
  settingsBtn: $<HTMLButtonElement>("#settingsBtn"),
  settingsPanel: $<HTMLDivElement>("#settingsPanel"),
  apiBaseInput: $<HTMLInputElement>("#apiBaseInput"),
  apiBaseSave: $<HTMLButtonElement>("#apiBaseSave"),
  dropzone: $<HTMLDivElement>("#dropzone"),
  fileInput: $<HTMLInputElement>("#fileInput"),
  fileSummary: $<HTMLDivElement>("#fileSummary"),
  templateChips: $<HTMLDivElement>("#templateChips"),
  systemPromptBox: $<HTMLTextAreaElement>("#systemPromptBox"),
  savePromptBtn: $<HTMLButtonElement>("#savePromptBtn"),
  customPrompts: $<HTMLUListElement>("#customPrompts"),
  newPromptName: $<HTMLInputElement>("#newPromptName"),
  newPromptSave: $<HTMLButtonElement>("#newPromptSave"),
  chatLog: $<HTMLDivElement>("#chatLog"),
  chatForm: $<HTMLFormElement>("#chatForm"),
  chatInput: $<HTMLTextAreaElement>("#chatInput"),
  chatSend: $<HTMLButtonElement>("#chatSend"),
  streamToggle: $<HTMLInputElement>("#streamToggle"),
  refreshCharts: $<HTMLButtonElement>("#refreshCharts"),
  chartGrid: $<HTMLDivElement>("#chartGrid"),
  chartModal: $<HTMLDivElement>("#chartModal"),
  chartModalBackdrop: $<HTMLDivElement>("#chartModalBackdrop"),
  chartModalClose: $<HTMLButtonElement>("#chartModalClose"),
  chartModalTitle: $<HTMLSpanElement>("#chartModalTitle"),
  chartFrame: $<HTMLIFrameElement>("#chartFrame"),
};

interface State {
  sessionId: string | null;
  model: string;
  systemPrompt: string;
  chartIds: Set<string>;
  busy: boolean;
}

const state: State = {
  sessionId: null,
  model: "",
  systemPrompt: "",
  chartIds: new Set(),
  busy: false,
};

function fmtBytes(n: number): string {
  if (n >= 1e9) return (n / 1e9).toFixed(1) + " ГБ";
  if (n >= 1e6) return (n / 1e6).toFixed(1) + " МБ";
  if (n >= 1e3) return (n / 1e3).toFixed(0) + " КБ";
  return n + " Б";
}

function fmtTime(ts: number): string {
  return new Date(ts).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
}

// ---------- health ----------
async function refreshHealth() {
  el.statusDot.className = "dot checking";
  el.statusText.textContent = "проверка соединения…";
  try {
    const h = await api.getHealth();
    if (h.ollama_connected) {
      el.statusDot.className = "dot ok";
      el.statusText.textContent = `бэкенд онлайн · ollama подключена`;
    } else {
      el.statusDot.className = "dot bad";
      el.statusText.textContent = "бэкенд онлайн · ollama недоступна";
    }
  } catch {
    el.statusDot.className = "dot bad";
    el.statusText.textContent = "нет связи с бэкендом";
  }
}

// ---------- models ----------
async function refreshModels() {
  try {
    const res = await api.listModels();
    const current = state.model;
    el.modelSelect.innerHTML = "";
    if (res.models.length === 0) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "нет моделей";
      el.modelSelect.appendChild(opt);
      return;
    }
    for (const m of res.models) {
      const opt = document.createElement("option");
      opt.value = m.name;
      opt.textContent = `${m.name} · ${fmtBytes(m.size)}`;
      el.modelSelect.appendChild(opt);
    }
    if (current && res.models.some((m) => m.name === current)) {
      el.modelSelect.value = current;
    } else {
      state.model = res.models[0].name;
      el.modelSelect.value = state.model;
    }
  } catch {
    el.modelSelect.innerHTML = '<option value="">недоступно</option>';
  }
}

el.modelSelect.addEventListener("change", () => {
  state.model = el.modelSelect.value;
  if (state.model) api.selectModel(state.model).catch(() => {});
});

// ---------- settings ----------
el.settingsBtn.addEventListener("click", () => {
  el.settingsPanel.classList.toggle("hidden");
  el.apiBaseInput.value = api.getApiBase();
});
el.apiBaseSave.addEventListener("click", () => {
  const v = el.apiBaseInput.value.trim();
  if (v) api.setApiBase(v);
  el.settingsPanel.classList.add("hidden");
  bootstrapData();
});

// ---------- upload ----------
function renderFileSummary(info: FileInfo) {
  const nullCols = Object.entries(info.nulls);
  el.fileSummary.innerHTML = `
    <div class="fname">${info.filename}</div>
    <div class="stat-row"><span>Строк</span><b>${info.rows.toLocaleString("ru-RU")}</b></div>
    <div class="stat-row"><span>Столбцов</span><b>${info.columns.length}</b></div>
    <div class="stat-row"><span>Пропуски</span><b class="${nullCols.length ? "null-flag" : ""}">${
      nullCols.length ? nullCols.map(([c, n]) => `${c}:${n}`).join(", ") : "нет"
    }</b></div>
    <div class="col-chips">${info.columns.map((c) => `<span class="col-chip">${c}</span>`).join("")}</div>
  `;
  el.fileSummary.classList.remove("hidden");
}

async function handleFile(file: File) {
  state.busy = true;
  el.dropzone.classList.add("drag");
  el.dropzone.querySelector(".dropzone-text")!.innerHTML = "Загрузка…";
  try {
    const res = await api.uploadFile(file);
    state.sessionId = res.session_id;
    renderFileSummary(res.file_info);
    pushMessage({
      role: "assistant",
      content: `Файл **${res.file_info.filename}** загружен: ${res.file_info.rows} строк, ${res.file_info.columns.length} столбцов. Можно задавать вопросы — например, выберите шаблон анализа слева.`,
      ts: Date.now(),
    });
  } catch (e) {
    pushMessage({ role: "error", content: e instanceof Error ? e.message : String(e), ts: Date.now() });
  } finally {
    state.busy = false;
    el.dropzone.classList.remove("drag");
    el.dropzone.querySelector(".dropzone-text")!.innerHTML =
      'Перетащите файл продаж или нажмите<br><span class="dropzone-hint">.xlsx · .xls · .csv · .json</span>';
  }
}

el.dropzone.addEventListener("click", () => el.fileInput.click());
el.dropzone.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") el.fileInput.click();
});
el.fileInput.addEventListener("change", () => {
  const f = el.fileInput.files?.[0];
  if (f) handleFile(f);
});
["dragover", "dragenter"].forEach((evt) =>
  el.dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    el.dropzone.classList.add("drag");
  }),
);
["dragleave", "drop"].forEach((evt) =>
  el.dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    el.dropzone.classList.remove("drag");
  }),
);
el.dropzone.addEventListener("drop", (e) => {
  const f = e.dataTransfer?.files?.[0];
  if (f) handleFile(f);
});

// ---------- system prompt & templates ----------
async function loadSystemPrompt() {
  try {
    const content = await api.getSystemPrompt();
    state.systemPrompt = content;
    el.systemPromptBox.value = content;
  } catch {
    el.systemPromptBox.placeholder = "Не удалось загрузить";
  }
}

el.savePromptBtn.addEventListener("click", async () => {
  try {
    await api.updateSystemPrompt(el.systemPromptBox.value);
    state.systemPrompt = el.systemPromptBox.value;
    el.savePromptBtn.textContent = "Сохранено ✓";
    setTimeout(() => (el.savePromptBtn.textContent = "Сохранить как системный"), 1400);
  } catch (e) {
    alert("Ошибка сохранения: " + (e instanceof Error ? e.message : e));
  }
});

function renderTemplateChips() {
  el.templateChips.innerHTML = TEMPLATE_KEYS.map(
    (t) => `<button type="button" class="template-chip" data-key="${t.key}">${t.label}</button>`,
  ).join("");
  el.templateChips.querySelectorAll<HTMLButtonElement>(".template-chip").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        const content = await api.getTemplate(btn.dataset.key!);
        el.chatInput.value = content;
        autoGrow();
        el.chatInput.focus();
      } catch {
        /* template not created yet on server; ignore */
      }
    });
  });
}

async function refreshCustomPrompts() {
  try {
    const res = await api.listPrompts();
    const custom = res.prompts.filter((p) => !p.id.startsWith("template_"));
    if (custom.length === 0) {
      el.customPrompts.innerHTML = '<li class="prompt-empty">Пока пусто</li>';
      return;
    }
    el.customPrompts.innerHTML = custom
      .map((p) => `<li><span class="prompt-name" data-id="${p.id}">${p.name}</span><button data-del="${p.id}" title="Удалить">×</button></li>`)
      .join("");
    el.customPrompts.querySelectorAll<HTMLSpanElement>(".prompt-name").forEach((span) => {
      span.addEventListener("click", () => {
        const p = custom.find((x) => x.id === span.dataset.id);
        if (p) {
          el.chatInput.value = p.content;
          autoGrow();
          el.chatInput.focus();
        }
      });
    });
    el.customPrompts.querySelectorAll<HTMLButtonElement>("button[data-del]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await api.deletePrompt(btn.dataset.del!).catch(() => {});
        refreshCustomPrompts();
      });
    });
  } catch {
    el.customPrompts.innerHTML = '<li class="prompt-empty">Недоступно</li>';
  }
}

el.newPromptSave.addEventListener("click", async () => {
  const name = el.newPromptName.value.trim();
  const content = el.chatInput.value.trim();
  if (!name || !content) return;
  try {
    await api.createPrompt({ name, content, description: "Пользовательский промпт" });
    el.newPromptName.value = "";
    refreshCustomPrompts();
  } catch (e) {
    alert(e instanceof Error ? e.message : String(e));
  }
});

// ---------- chat ----------
function pushMessage(entry: ChatEntry): HTMLDivElement {
  el.chatLog.querySelector(".chat-empty")?.remove();
  const div = document.createElement("div");
  div.className = `msg msg-${entry.role}`;
  if (entry.role === "assistant") {
    const meta = `${entry.model || "агент"} · ${fmtTime(entry.ts)}`;
    div.innerHTML = `<div class="msg-meta">${meta}</div><div class="msg-body">${renderReply(entry.content)}</div>`;
  } else if (entry.role === "user") {
    div.textContent = entry.content;
  } else {
    div.textContent = "⚠ " + entry.content;
  }
  el.chatLog.appendChild(div);
  el.chatLog.scrollTop = el.chatLog.scrollHeight;
  return div;
}

function pushThinking(): HTMLDivElement {
  const div = document.createElement("div");
  div.className = "thinking";
  div.innerHTML = `<span>агент анализирует</span><span class="dots"><span></span><span></span><span></span></span>`;
  el.chatLog.appendChild(div);
  el.chatLog.scrollTop = el.chatLog.scrollHeight;
  return div;
}

function autoGrow() {
  el.chatInput.style.height = "auto";
  el.chatInput.style.height = Math.min(el.chatInput.scrollHeight, 140) + "px";
}
el.chatInput.addEventListener("input", autoGrow);
el.chatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    el.chatForm.requestSubmit();
  }
});

el.chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (state.busy) return;
  const message = el.chatInput.value.trim();
  if (!message) return;

  pushMessage({ role: "user", content: message, ts: Date.now() });
  el.chatInput.value = "";
  autoGrow();

  state.busy = true;
  el.chatSend.disabled = true;

  const req = {
    message,
    model: state.model || undefined,
    session_id: state.sessionId || undefined,
    system_prompt: el.systemPromptBox.value || undefined,
  };

  const before = new Set(state.chartIds);

  if (el.streamToggle.checked) {
    const bubble = pushMessage({ role: "assistant", content: "", model: state.model, ts: Date.now() });
    const body = bubble.querySelector(".msg-body")!;
    let acc = "";
    try {
      await api.streamChat(req, (chunk) => {
        acc += chunk;
        body.innerHTML = renderReply(acc);
        el.chatLog.scrollTop = el.chatLog.scrollHeight;
      });
      if (!acc) body.innerHTML = "<em>(пустой ответ)</em>";
    } catch (err) {
      bubble.remove();
      pushMessage({ role: "error", content: err instanceof Error ? err.message : String(err), ts: Date.now() });
    }
  } else {
    const thinking = pushThinking();
    try {
      const res = await api.sendChat(req);
      thinking.remove();
      pushMessage({ role: "assistant", content: res.reply, model: res.model_used, ts: Date.now() });
      await refreshCharts(before);
    } catch (err) {
      thinking.remove();
      pushMessage({ role: "error", content: err instanceof Error ? err.message : String(err), ts: Date.now() });
    }
  }

  state.busy = false;
  el.chatSend.disabled = false;
  el.chatInput.focus();
});

// ---------- charts ----------
async function refreshCharts(prev?: Set<string>) {
  try {
    const charts = await api.listCharts();
    state.chartIds = new Set(charts);
    if (charts.length === 0) {
      el.chartGrid.innerHTML = '<div class="chart-empty">Графики появятся здесь после того, как агент их построит.</div>';
      return;
    }
    el.chartGrid.innerHTML = charts
      .map((id) => {
        const isNew = prev && !prev.has(id);
        return `<div class="chart-card" data-id="${id}">
          ${isNew ? '<span class="chart-new-badge">новый</span>' : ""}
          <button class="chart-del" data-del="${id}" title="Удалить">×</button>
          <div class="chart-id">${id}</div>
          <div class="chart-hint">нажмите, чтобы открыть</div>
        </div>`;
      })
      .join("");
    el.chartGrid.querySelectorAll<HTMLDivElement>(".chart-card").forEach((card) => {
      card.addEventListener("click", (e) => {
        if ((e.target as HTMLElement).dataset.del) return;
        openChart(card.dataset.id!);
      });
    });
    el.chartGrid.querySelectorAll<HTMLButtonElement>("button[data-del]").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        await api.deleteChart(btn.dataset.del!).catch(() => {});
        refreshCharts();
      });
    });
  } catch {
    el.chartGrid.innerHTML = '<div class="chart-empty">Не удалось загрузить список графиков.</div>';
  }
}
el.refreshCharts.addEventListener("click", () => refreshCharts());

async function openChart(id: string) {
  el.chartModalTitle.textContent = id;
  el.chartModal.classList.remove("hidden");
  try {
    const html = await api.getChartHtml(id);
    el.chartFrame.srcdoc = html;
  } catch (e) {
    el.chartFrame.srcdoc = `<p style="font-family:sans-serif;padding:20px;">Ошибка загрузки: ${
      e instanceof Error ? e.message : e
    }</p>`;
  }
}
el.chartModalClose.addEventListener("click", () => el.chartModal.classList.add("hidden"));
el.chartModalBackdrop.addEventListener("click", () => el.chartModal.classList.add("hidden"));
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") el.chartModal.classList.add("hidden");
});

// ---------- bootstrap ----------
async function bootstrapData() {
  await Promise.all([refreshHealth(), refreshModels(), loadSystemPrompt(), refreshCustomPrompts(), refreshCharts()]);
}

renderTemplateChips();
bootstrapData();
setInterval(refreshHealth, 20000);
