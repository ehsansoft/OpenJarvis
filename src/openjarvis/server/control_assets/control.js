const $ = (selector) => document.querySelector(selector);
const state = {
  overview: null,
  capabilities: [],
  history: [],
  research: null,
  projectOffset: 0,
  nextOffset: null,
  busy: false,
  actions: [],
};
let apiKey = sessionStorage.getItem("jarvis-control-key") || "";
const gb = (bytes) => `${(bytes / 1073741824).toFixed(1)} GiB`;
const stamp = (date) => new Date(date).toLocaleString();
function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = String(text);
  if (className) node.className = className;
  return node;
}
function badge(status) {
  return element(
    "span",
    status.replaceAll("_", " ").toLowerCase(),
    `badge ${status.toLowerCase()}`,
  );
}
function empty(target, message) {
  target.replaceChildren(element("p", message, "empty"));
}
function toast(message) {
  $("#toast").textContent = message;
  $("#toast").hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => ($("#toast").hidden = true), 5500);
}
function activity(message) {
  state.actions.unshift({ message, time: new Date().toISOString() });
  const target = $("#activity");
  target.replaceChildren();
  for (const row of state.actions.slice(0, 6)) {
    const item = element("div", row.message);
    item.append(element("time", stamp(row.time)));
    target.append(item);
  }
}
async function api(path, body, timeout = 120000) {
  const headers = { "X-Jarvis-Control": "1" };
  if (apiKey) headers.Authorization = `Bearer ${apiKey}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const response = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(timeout),
    cache: "no-store",
  });
  const data = await response
    .json()
    .catch(() => ({ detail: "The server returned an unreadable response" }));
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : `Request failed (${response.status})`,
    );
  return data;
}
async function guarded(action) {
  try {
    return await action();
  } catch (error) {
    toast(error.message || "Action failed");
    activity(`Action failed: ${error.message}`);
    return null;
  }
}
function button(label, action, className = "secondary") {
  const node = element("button", label, className);
  node.type = "button";
  node.addEventListener("click", () =>
    guarded(async () => {
      node.disabled = true;
      try {
        await action();
      } finally {
        node.disabled = false;
      }
    }),
  );
  return node;
}
async function confirmAction(title, description, scope) {
  const dialog = $("#action-dialog");
  $("#action-title").textContent = title;
  $("#action-description").textContent = description;
  $("#action-scope").textContent = scope;
  dialog.returnValue = "cancel";
  dialog.showModal();
  return new Promise((resolve) =>
    dialog.addEventListener(
      "close",
      () => resolve(dialog.returnValue === "confirm"),
      { once: true },
    ),
  );
}
async function openView(view) {
  document
    .querySelectorAll("[data-panel]")
    .forEach((panel) => (panel.hidden = panel.dataset.panel !== view));
  document
    .querySelectorAll("nav [data-view]")
    .forEach((node) =>
      node.classList.toggle("active", node.dataset.view === view),
    );
  $("#breadcrumb").textContent = view.charAt(0).toUpperCase() + view.slice(1);
  history.replaceState(null, "", `#${view}`);
  if (view === "skills") await guarded(loadSkills);
  if (view === "capabilities") await guarded(loadCapabilities);
  if (view === "tasks") await guarded(loadTasks);
  if (view === "projects") {
    state.projectOffset = 0;
    await guarded(loadProjects);
  }
  if (view === "services") renderServices();
  if (view === "chat") $("#chat-input").focus();
  if (view === "research") renderNotebook();
}
document
  .querySelectorAll("[data-view],[data-open]")
  .forEach((node) =>
    node.addEventListener("click", () =>
      openView(node.dataset.view || node.dataset.open),
    ),
  );
async function refresh() {
  try {
    const data = await api("/v1/control/overview", undefined, 12000);
    state.overview = data;
    $("#connection-alert").hidden = true;
    $("#privacy-status").textContent = data.private_routing
      ? "Private · local only"
      : "Private routing required";
    $("#free-space").textContent = gb(data.disk.free_bytes);
    $("#disk-label").textContent = `${data.disk.path} available space`;
    $("#disk-meter").style.width =
      `${(100 * data.disk.free_bytes) / data.disk.total_bytes}%`;
    $("#service-count").textContent =
      `${data.services.filter((s) => s.status === "RUNNING").length} / ${data.services.length}`;
    $("#active-tasks").textContent = data.active_tasks;
    $("#scheduler-state").textContent = data.scheduler_enabled
      ? "Server-owned scheduler"
      : "Scheduler disabled";
    $("#chat-model").textContent = data.model;
    $("#sidebar-address").textContent = location.origin;
    $("#last-observed").textContent = `Observed ${stamp(data.observed_at)}`;
    if (data.cleanup) {
      $("#cleanup-space").textContent = gb(data.cleanup.recovered_bytes);
      $("#cleanup-state").textContent =
        `Approved batch · ${stamp(data.cleanup.completed_at)}`;
    }
    const pulse = $("#service-pulse");
    pulse.replaceChildren();
    for (const service of data.services) {
      const row = element("div", undefined, "row");
      const info = element("div");
      info.append(
        element("strong", service.name),
        element("small", service.url),
      );
      row.append(info, badge(service.status));
      pulse.append(row);
    }
    renderServices();
  } catch (error) {
    $("#connection-alert").textContent =
      `Jarvis connection unavailable: ${error.message}. Check Servers for the PowerShell startup command.`;
    $("#connection-alert").hidden = false;
    $("#privacy-status").textContent = "Connection unavailable";
  }
}
function renderServices() {
  const target = $("#services-grid");
  if (!state.overview) {
    empty(target, "Waiting for the local server.");
    return;
  }
  target.replaceChildren();
  for (const service of state.overview.services) {
    const card = element("article", undefined, "card");
    card.append(
      badge(service.status),
      element("h2", service.name),
      element("p", service.url, "service-url"),
    );
    const note =
      service.name === "Jarvis"
        ? "Personal API, local chat and the shared task scheduler."
        : service.name === "Ollama"
          ? "Installed local models. Start does not pull or install anything."
          : "Speech is deferred. Restrict Voicebox to loopback before relying on its privacy.";
    card.append(element("p", note, "muted small"));
    const actions = element("div", undefined, "actions");
    if (service.name === "Jarvis")
      actions.append(
        button("Restart Jarvis", async () => {
          if (
            !(await confirmAction(
              "Restart Jarvis?",
              "The owned server drains and restarts at the same loopback address. This dashboard will briefly disconnect.",
              "No model downloads. Task SQLite state is preserved.",
            ))
          )
            return;
          await api("/v1/control/services/jarvis/restart", {
            confirm: "restart-jarvis",
          });
          activity("Requested a local Jarvis restart");
          toast("Restart requested. Reconnecting shortly…");
        }),
      );
    if (service.name === "Ollama")
      actions.append(
        button("Start / check Ollama", async () => {
          if (
            !(await confirmAction(
              "Start the installed Ollama server?",
              "If Ollama is already responding, no second process is started.",
              "Command: installed ollama serve\nBinding: 127.0.0.1 only\nNo model downloads or configuration file changes.",
            ))
          )
            return;
          const result = await api("/v1/control/services/ollama/start", {});
          activity(
            `Ollama: ${result.status.toLowerCase().replaceAll("_", " ")}`,
          );
          toast(result.status.replaceAll("_", " "));
          await refresh();
        }),
      );
    if (service.name === "Voicebox")
      actions.append(
        element("span", "Launch setup requires loopback verification", "tag"),
      );
    card.append(actions);
    target.append(card);
  }
}
async function loadSkills() {
  const data = await api("/v1/control/skills");
  const target = $("#skills-grid");
  target.replaceChildren();
  if (!data.skills.length)
    empty(target, "No installed skills were discovered.");
  for (const skill of data.skills) {
    const card = element("article", undefined, "card");
    card.append(
      element("span", skill.kind.toUpperCase(), "tag"),
      element("h2", skill.name),
      element("p", skill.description, "muted small"),
      element("small", `Version ${skill.version}`),
    );
    if (skill.runnable) card.append(button("Run workstation brief", runBrief));
    else
      card.append(
        element(
          "p",
          "Instruction recipe · no automatic execution",
          "muted small",
        ),
      );
    target.append(card);
  }
}
async function runBrief() {
  const result = await api("/v1/control/skills/workstation-brief/run", {});
  $("#skill-output").hidden = false;
  $("#skill-result").textContent = JSON.stringify(result, null, 2);
  activity(`Workstation brief ${result.success ? "completed" : "failed"}`);
  await openView("skills");
  toast(
    result.success
      ? "Read-only brief completed"
      : "Brief returned a failure; inspect the result",
  );
}
$("#brief").addEventListener("click", () => guarded(runBrief));
$("#research-shortcut").addEventListener("click", () => {
  openView("research");
  $("#research-input").value =
    "Find the completed cleanup in the indexed runbook. Report the recovered space and cite the source path. Keep it under 100 words.";
});
async function loadCapabilities() {
  const data = await api("/v1/control/capabilities", undefined, 30000);
  state.capabilities = data.capabilities;
  renderCapabilities();
}
function renderCapabilities() {
  const query = $("#capability-search").value.toLowerCase();
  const filter = $("#capability-filter").value;
  const target = $("#capability-grid");
  target.replaceChildren();
  const rows = state.capabilities.filter(
    (c) =>
      (!filter || c.status === filter) &&
      `${c.display_name} ${c.reason}`.toLowerCase().includes(query),
  );
  for (const capability of rows) {
    const card = element("article", undefined, "card");
    card.append(
      badge(capability.status),
      element("h2", capability.display_name),
      element("p", capability.reason, "muted small"),
      element("p", `Next: ${capability.next_action}`, "small"),
    );
    if (capability.related_commands?.length)
      card.append(element("pre", capability.related_commands.join("\n")));
    target.append(card);
  }
  if (!rows.length) empty(target, "No matching capabilities.");
}
$("#capability-search").addEventListener("input", renderCapabilities);
$("#capability-filter").addEventListener("change", renderCapabilities);
function addMessage(role, content) {
  const target = $("#chat-messages");
  target.querySelector(".chat-welcome")?.remove();
  const message = element("div", undefined, `message ${role}`);
  message.append(
    element("small", role === "user" ? "YOU" : "JARVIS"),
    document.createTextNode(content),
  );
  target.append(message);
  target.scrollTop = target.scrollHeight;
  return message;
}
$("#chat-form").addEventListener("submit", (event) => {
  event.preventDefault();
  guarded(async () => {
    if (state.busy) return;
    const input = $("#chat-input");
    const prompt = input.value.trim();
    if (!prompt) return;
    state.busy = true;
    const submit = $("#chat-form button[type=submit]");
    submit.disabled = true;
    addMessage("user", prompt);
    input.value = "";
    const pending = addMessage("assistant", "Working locally…");
    try {
      const result = await api("/v1/control/chat", {
        prompt,
        history: state.history.slice(-20),
        mode: "chat",
      });
      pending.replaceChildren(
        element("small", `JARVIS · ${result.model}`),
        document.createTextNode(result.content),
      );
      state.history.push(
        { role: "user", content: prompt },
        { role: "assistant", content: result.content },
      );
      activity("Completed a private chat turn");
    } catch (error) {
      pending.replaceChildren(
        element("small", "REQUEST FAILED"),
        document.createTextNode(error.message),
      );
      throw error;
    } finally {
      state.busy = false;
      submit.disabled = false;
    }
  });
});
$("#chat-input").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey))
    $("#chat-form").requestSubmit();
});
document.querySelectorAll("[data-prompt]").forEach((node) =>
  node.addEventListener("click", () => {
    $("#chat-input").value = node.dataset.prompt;
    $("#chat-input").focus();
  }),
);
$("#clear-chat").addEventListener("click", () => {
  if (state.busy) {
    toast("Wait for the current turn to finish");
    return;
  }
  state.history = [];
  empty($("#chat-messages"), "A new private conversation.");
  activity("Started a new conversation");
});
$("#research-form").addEventListener("submit", (event) => {
  event.preventDefault();
  guarded(async () => {
    const submit = $("#research-form button[type=submit]");
    submit.disabled = true;
    $("#research-result").textContent = "Retrieving and thinking locally…";
    $("#save-research").hidden = true;
    try {
      const prompt = $("#research-input").value;
      const result = await api(
        "/v1/control/chat",
        { prompt, mode: "research", history: [] },
        240000,
      );
      state.research = {
        question: prompt,
        answer: result.content,
        time: new Date().toISOString(),
      };
      $("#research-result").replaceChildren(
        document.createTextNode(result.content),
      );
      if (result.sources) {
        const details = element("details");
        details.append(
          element("summary", "Retrieved sources · review evidence"),
          element("pre", result.sources),
        );
        $("#research-result").append(details);
      }
      $("#save-research").hidden = false;
      activity("Completed local research; citations require review");
    } catch (error) {
      $("#research-result").textContent = `Research failed: ${error.message}`;
      throw error;
    } finally {
      submit.disabled = false;
    }
  });
});
function notebook() {
  try {
    return JSON.parse(
      localStorage.getItem("jarvis-control-notebook") || "[]",
    ).slice(0, 20);
  } catch {
    return [];
  }
}
function renderNotebook() {
  const target = $("#research-notebook");
  target.replaceChildren();
  const notes = notebook();
  if (!notes.length) empty(target, "No saved research yet.");
  for (const note of notes) {
    const item = element("details", undefined, "notebook-entry");
    item.append(
      element("summary", note.question),
      element("small", stamp(note.time)),
      element("p", note.answer),
    );
    target.append(item);
  }
}
$("#save-research").addEventListener("click", () =>
  guarded(async () => {
    if (!state.research) return;
    localStorage.setItem(
      "jarvis-control-notebook",
      JSON.stringify([state.research, ...notebook()].slice(0, 20)),
    );
    $("#save-research").hidden = true;
    renderNotebook();
    toast("Saved in this browser only");
  }),
);
$("#memory-form").addEventListener("submit", (event) => {
  event.preventDefault();
  guarded(async () => {
    const data = await api("/v1/memory/search", {
      query: $("#memory-query").value,
      top_k: 3,
    });
    const target = $("#memory-results");
    target.replaceChildren();
    for (const row of data.results || data.hits || []) {
      const card = element("div", undefined, "notebook-entry");
      card.append(
        element(
          "small",
          row.source || row.metadata?.source || "Indexed source",
        ),
        element("p", row.content || row.text || ""),
      );
      target.append(card);
    }
    if (!target.childElementCount)
      empty(target, "No matching indexed documents.");
  });
});
async function loadTasks() {
  const data = await api("/v1/control/tasks");
  const target = $("#task-list");
  target.replaceChildren();
  if (!data.tasks.length)
    empty(target, "No scheduled tasks. Create a one-shot prompt to begin.");
  for (const task of data.tasks) {
    const row = element("div", undefined, "task");
    row.append(
      badge(task.status.toUpperCase()),
      element("p", task.prompt),
      element(
        "small",
        task.next_run
          ? `Next run: ${stamp(task.next_run)}`
          : `Last run: ${task.last_run ? stamp(task.last_run) : "not run"} · ${task.id}`,
      ),
    );
    const actions = element("div", undefined, "actions");
    actions.append(
      button("History", async () => {
        const result = await api(
          `/v1/control/tasks/${encodeURIComponent(task.id)}/logs`,
        );
        $("#task-log-card").hidden = false;
        $("#task-log").textContent = JSON.stringify(result.logs, null, 2);
      }),
    );
    if (["active", "paused"].includes(task.status)) {
      const action = task.status === "active" ? "pause" : "resume";
      actions.append(
        button(action === "pause" ? "Pause" : "Resume", async () => {
          if (
            !(await confirmAction(
              `${action === "pause" ? "Pause" : "Resume"} task?`,
              task.prompt,
              `Task: ${task.id}\nSchedule: ${task.schedule_value}`,
            ))
          )
            return;
          await api(
            `/v1/control/tasks/${encodeURIComponent(task.id)}/state/${action}`,
            {},
          );
          activity(`Task ${action}d`);
          await loadTasks();
          await refresh();
        }),
      );
      actions.append(
        button("Run now", async () => {
          if (
            !(await confirmAction(
              "Run this task now?",
              task.prompt,
              "Uses the existing server-owned scheduler and read-only tools.\nNo second scheduler or Telegram poller.",
            ))
          )
            return;
          const result = await api(
            `/v1/control/tasks/${encodeURIComponent(task.id)}/execute`,
            {},
          );
          $("#task-log-card").hidden = false;
          $("#task-log").textContent = JSON.stringify(result, null, 2);
          activity(`Task run ${result.success ? "succeeded" : "failed"}`);
          await loadTasks();
          await refresh();
        }),
      );
      actions.append(
        button("Cancel", async () => {
          if (
            !(await confirmAction(
              "Cancel this task?",
              task.prompt,
              "Stops future scheduling. SQLite history is retained.",
            ))
          )
            return;
          await api(
            `/v1/control/tasks/${encodeURIComponent(task.id)}/state/cancel`,
            {},
          );
          activity("Cancelled future task execution");
          await loadTasks();
          await refresh();
        }),
      );
    }
    row.append(actions);
    target.append(row);
  }
}
$("#reload-tasks").addEventListener("click", () => guarded(loadTasks));
$("#task-form").addEventListener("submit", (event) => {
  event.preventDefault();
  guarded(async () => {
    const prompt = $("#task-prompt").value;
    const date = new Date($("#task-time").value);
    if (!Number.isFinite(date.getTime()) || date <= new Date())
      throw new Error("Choose a future run time");
    if (
      !(await confirmAction(
        "Create this one-shot task?",
        prompt,
        `Local: ${date.toLocaleString()}\nStored UTC: ${date.toISOString()}\nRead-only local tools. No recurring job or Telegram notification.`,
      ))
    )
      return;
    const task = await api("/v1/control/tasks", {
      prompt,
      run_at: date.toISOString(),
    });
    activity(`Created one-shot task ${task.id}`);
    toast("Task scheduled");
    await loadTasks();
    await refresh();
  });
});
async function loadProjects() {
  const data = await api(`/v1/control/projects?offset=${state.projectOffset}`);
  state.nextOffset = data.next_offset;
  const target = $("#project-grid");
  target.replaceChildren();
  for (const project of data.reviews) {
    const card = element("article", undefined, "card");
    card.append(
      element("span", "SCANNER PROPOSAL", "tag"),
      element("h2", project.name),
      element("p", project.path, "service-url"),
      element("p", `Proposed role: ${project.proposed_role}`, "muted small"),
      element(
        "p",
        project.identity_conflict
          ? "Identity conflict needs review"
          : "Not adopted into canonical Project Intelligence",
        "muted small",
      ),
    );
    target.append(card);
  }
  if (!data.reviews.length)
    empty(target, data.reason || "No project proposals in this snapshot.");
  $("#more-projects").hidden =
    state.nextOffset === null || state.nextOffset === undefined;
}
$("#more-projects").addEventListener("click", () => {
  state.projectOffset = state.nextOffset;
  guarded(loadProjects);
});
$("#refresh").addEventListener("click", () =>
  guarded(async () => {
    await refresh();
    toast("Local status refreshed");
  }),
);
$("#connection").addEventListener("click", () => {
  const dialog = $("#connection-dialog");
  $("#api-key").value = apiKey;
  dialog.returnValue = "cancel";
  dialog.showModal();
});
$("#connection-dialog").addEventListener("close", () => {
  if ($("#connection-dialog").returnValue === "save") {
    apiKey = $("#api-key").value;
    sessionStorage.setItem("jarvis-control-key", apiKey);
    $("#api-key").value = "";
    refresh();
  }
});
$("#clock").textContent = new Date().toLocaleDateString(undefined, {
  day: "numeric",
  month: "short",
  year: "numeric",
});
const initial = location.hash.slice(1);
openView(
  [
    "chat",
    "research",
    "tasks",
    "projects",
    "services",
    "skills",
    "capabilities",
  ].includes(initial)
    ? initial
    : "overview",
);
refresh();
setInterval(refresh, 15000);
