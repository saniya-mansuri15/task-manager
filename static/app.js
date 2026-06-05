const API = "/api";

const els = {
  taskList: document.getElementById("task-list"),
  emptyState: document.getElementById("empty-state"),
  stats: document.getElementById("stats"),
  search: document.getElementById("search"),
  filterStatus: document.getElementById("filter-status"),
  filterPriority: document.getElementById("filter-priority"),
  dialog: document.getElementById("task-dialog"),
  form: document.getElementById("task-form"),
  dialogTitle: document.getElementById("dialog-title"),
  taskId: document.getElementById("task-id"),
  title: document.getElementById("title"),
  description: document.getElementById("description"),
  priority: document.getElementById("priority"),
  status: document.getElementById("status"),
  dueDate: document.getElementById("due_date"),
  newTaskBtn: document.getElementById("new-task-btn"),
  cancelBtn: document.getElementById("cancel-btn"),
};

const STATUS_LABELS = {
  pending: "Pending",
  in_progress: "In Progress",
  completed: "Completed",
};

let debounceTimer;

async function api(path, options = {}) {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (res.status === 204) return null;
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || data.errors?.join(" ") || "Request failed");
  return data;
}

function formatDate(dateStr) {
  if (!dateStr) return null;
  const date = new Date(dateStr + "T00:00:00");
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function isOverdue(dateStr, status) {
  if (!dateStr || status === "completed") return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const due = new Date(dateStr + "T00:00:00");
  return due < today;
}

function renderStats(stats) {
  els.stats.innerHTML = Object.entries(STATUS_LABELS)
    .map(([key, label]) => `
      <div class="stat-card">
        <div class="label">${label}</div>
        <div class="value">${stats[key] ?? 0}</div>
      </div>
    `)
    .join("");
}

function renderTask(task) {
  const due = formatDate(task.due_date);
  const overdue = isOverdue(task.due_date, task.status);

  return `
    <li class="task-card ${task.status === "completed" ? "completed" : ""}" data-id="${task.id}">
      <div class="task-main">
        <div class="task-title">${escapeHtml(task.title)}</div>
        ${task.description ? `<div class="task-description">${escapeHtml(task.description)}</div>` : ""}
        <p>Due: ${task.due_date ? escapeHtml(task.due_date) : ""}</p>
        <div class="task-meta">
          <span class="badge priority-${task.priority}">${task.priority}</span>
          <span class="badge status-${task.status}">${STATUS_LABELS[task.status]}</span>
          ${due ? `<span class="due-date ${overdue ? "overdue" : ""}">Due ${due}</span>` : ""}
        </div>
      </div>
      <div class="task-actions">
        ${task.status !== "completed" ? `<button class="btn btn-ghost complete-btn" data-id="${task.id}">Done</button>` : ""}
        <button class="btn btn-ghost edit-btn" data-id="${task.id}">Edit</button>
        <button class="btn btn-danger delete-btn" data-id="${task.id}">Delete</button>
      </div>
    </li>
  `;
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

async function loadTasks() {
  const params = new URLSearchParams();
  const search = els.search.value.trim();
  const status = els.filterStatus.value;
  const priority = els.filterPriority.value;

  if (search) params.set("search", search);
  if (status) params.set("status", status);
  if (priority) params.set("priority", priority);

  const query = params.toString() ? `?${params}` : "";
  const [tasks, stats] = await Promise.all([
    api(`/tasks${query}`),
    api("/stats"),
  ]);

  renderStats(stats);
  els.taskList.innerHTML = tasks.map(renderTask).join("");
  els.emptyState.hidden = tasks.length > 0;
}

function openDialog(task = null) {
  els.dialogTitle.textContent = task ? "Edit Task" : "New Task";
  els.taskId.value = task?.id ?? "";
  els.title.value = task?.title ?? "";
  els.description.value = task?.description ?? "";
  els.priority.value = task?.priority ?? "medium";
  els.status.value = task?.status ?? "pending";
  els.dueDate.value = task?.due_date ?? "";
  els.dialog.showModal();
  els.title.focus();
}

function closeDialog() {
  els.dialog.close();
  els.form.reset();
}

els.newTaskBtn.addEventListener("click", () => openDialog());
els.cancelBtn.addEventListener("click", closeDialog);

els.form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const id = els.taskId.value;
  const payload = {
    title: els.title.value,
    description: els.description.value,
    priority: els.priority.value,
    status: els.status.value,
    due_date: els.dueDate.value || null,
  };

  try {
    if (id) {
      await api(`/tasks/${id}`, { method: "PUT", body: JSON.stringify(payload) });
    } else {
      await api("/tasks", { method: "POST", body: JSON.stringify(payload) });
    }
    closeDialog();
    await loadTasks();
  } catch (err) {
    alert(err.message);
  }
});

els.taskList.addEventListener("click", async (e) => {
  const id = e.target.dataset.id;
  if (!id) return;

  if (e.target.classList.contains("edit-btn")) {
    const task = await api(`/tasks/${id}`);
    openDialog(task);
  } else if (e.target.classList.contains("complete-btn")) {
    await api(`/tasks/${id}`, {
      method: "PUT",
      body: JSON.stringify({ status: "completed" }),
    });
    await loadTasks();
  } else if (e.target.classList.contains("delete-btn")) {
    if (!confirm("Delete this task?")) return;
    await api(`/tasks/${id}`, { method: "DELETE" });
    await loadTasks();
  }
});

function debouncedLoad() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(loadTasks, 250);
}

els.search.addEventListener("input", debouncedLoad);
els.filterStatus.addEventListener("change", loadTasks);
els.filterPriority.addEventListener("change", loadTasks);

loadTasks().catch((err) => {
  els.emptyState.hidden = false;
  els.emptyState.textContent = `Failed to load tasks: ${err.message}`;
});
