const $ = (s) => document.querySelector(s);

function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.remove("show"), 2200);
}

function adminKey() {
  return $("#adminKey").value.trim();
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": adminKey(),
      ...(opts.headers || {}),
    },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.ok === false) {
    throw new Error(data.error || res.statusText || "request_failed");
  }
  return data;
}

function toLocalInputValue(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fromLocalInputValue(value) {
  const d = new Date(value);
  return d.toISOString();
}

function fillEventTypes(types) {
  for (const sel of ["#eventTypeSelect", "#simEventType"]) {
    const el = $(sel);
    el.innerHTML = types.map((t) => `<option value="${t}">${t}</option>`).join("");
  }
}

function renderSeasons(seasons, activeId) {
  const box = $("#seasonsList");
  box.innerHTML = seasons.map((s) => `
    <div class="mini-item ${s.id === activeId ? "active" : ""}">
      <span>#${s.number} ${s.name}</span>
      <button type="button" class="btn-tiny" data-activate="${s.id}">${s.active ? "Активний" : "Активувати"}</button>
    </div>
  `).join("");
}

function renderQuests(quests) {
  const wrap = $("#questsTable");
  if (!quests.length) {
    wrap.innerHTML = "<p class='hint'>Квестів ще немає</p>";
    return;
  }
  wrap.innerHTML = `
    <table class="data">
      <thead>
        <tr>
          <th>Назва</th><th>Тип</th><th>Подія</th><th>Ціль</th><th>XP</th><th>Reset</th><th></th>
        </tr>
      </thead>
      <tbody>
        ${quests.map((q) => `
          <tr>
            <td><strong>${q.title}</strong><br><span class="hint">${q.description || ""}</span></td>
            <td>${q.kind}</td>
            <td><code>${q.event_type}</code></td>
            <td>${q.target}</td>
            <td>${q.xp_reward}</td>
            <td>${q.resets}</td>
            <td><button type="button" class="btn-tiny danger" data-del-quest="${q.id}">Видалити</button></td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

function renderEvents(events) {
  const wrap = $("#eventsTable");
  if (!events.length) {
    wrap.innerHTML = "<p class='hint'>Подій ще немає — надішли з плагіна або симуляції</p>";
    return;
  }
  wrap.innerHTML = `
    <table class="data">
      <thead>
        <tr><th>Час</th><th>Гравець</th><th>Подія</th><th>Amount</th><th>Source</th><th>Meta</th></tr>
      </thead>
      <tbody>
        ${events.map((e) => `
          <tr>
            <td>${e.created_at}</td>
            <td>${e.minecraft_name}</td>
            <td><code>${e.event_type}</code></td>
            <td>${e.amount}</td>
            <td>${e.source}</td>
            <td><code>${JSON.stringify(e.meta || {})}</code></td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

async function reload() {
  const data = await api("/api/battlepass/admin/overview");
  fillEventTypes(data.event_types || []);
  renderSeasons(data.seasons || [], data.active_season_id);
  renderQuests(data.quests || []);
  renderEvents(data.recent_events || []);
  if (data.active_season_id) {
    $("#questSeasonId").value = data.active_season_id;
    $("#rewardSeasonId").value = data.active_season_id;
  }
  toast("Дані оновлено");
}

function bindForms() {
  const now = new Date();
  const later = new Date(now.getTime() + 30 * 24 * 3600 * 1000);
  $("#seasonForm").starts_at.value = toLocalInputValue(now.toISOString());
  $("#seasonForm").ends_at.value = toLocalInputValue(later.toISOString());

  $("#reloadBtn").addEventListener("click", () => reload().catch((e) => toast(e.message)));

  $("#seasonForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      await api("/api/battlepass/admin/seasons", {
        method: "POST",
        body: JSON.stringify({
          number: Number(fd.get("number")),
          name: fd.get("name"),
          description: fd.get("description"),
          starts_at: fromLocalInputValue(fd.get("starts_at")),
          ends_at: fromLocalInputValue(fd.get("ends_at")),
          active: fd.get("active") === "on",
        }),
      });
      toast("Сезон створено");
      await reload();
    } catch (err) {
      toast(err.message);
    }
  });

  $("#questForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      await api("/api/battlepass/admin/quests", {
        method: "POST",
        body: JSON.stringify({
          season_id: fd.get("season_id"),
          kind: fd.get("kind"),
          title: fd.get("title"),
          description: fd.get("description"),
          icon: fd.get("icon"),
          event_type: fd.get("event_type"),
          target: Number(fd.get("target")),
          xp_reward: Number(fd.get("xp_reward")),
          resets: fd.get("resets"),
          active: true,
        }),
      });
      toast("Квест додано");
      e.target.reset();
      await reload();
    } catch (err) {
      toast(err.message);
    }
  });

  $("#rewardForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      await api("/api/battlepass/admin/rewards", {
        method: "POST",
        body: JSON.stringify({
          season_id: fd.get("season_id"),
          level: Number(fd.get("level")),
          name: fd.get("name"),
          icon: fd.get("icon"),
          grant_command: fd.get("grant_command"),
          premium: fd.get("premium") === "on",
        }),
      });
      toast("Нагороду збережено");
      await reload();
    } catch (err) {
      toast(err.message);
    }
  });

  $("#simForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const biome = String(fd.get("biome") || "").trim();
    const event = {
      player: fd.get("player"),
      type: fd.get("type"),
      amount: Number(fd.get("amount")),
      meta: biome ? { biome } : {},
    };
    try {
      const res = await api("/api/battlepass/admin/simulate", {
        method: "POST",
        body: JSON.stringify({ events: [event] }),
      });
      toast(`Оновлено квестів: ${res.updated?.length || 0}`);
      await reload();
    } catch (err) {
      toast(err.message);
    }
  });

  document.body.addEventListener("click", async (e) => {
    const activate = e.target.closest("[data-activate]");
    if (activate) {
      try {
        await api(`/api/battlepass/admin/seasons/${activate.dataset.activate}`, {
          method: "PUT",
          body: JSON.stringify({ active: true }),
        });
        toast("Сезон активовано");
        await reload();
      } catch (err) {
        toast(err.message);
      }
    }
    const del = e.target.closest("[data-del-quest]");
    if (del) {
      if (!confirm("Видалити квест?")) return;
      try {
        await api(`/api/battlepass/admin/quests/${del.dataset.delQuest}`, { method: "DELETE" });
        toast("Квест видалено");
        await reload();
      } catch (err) {
        toast(err.message);
      }
    }
  });
}

bindForms();
reload().catch((e) => toast(e.message));
