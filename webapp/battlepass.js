const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

const state = {
  player: localStorage.getItem("bp_player") || "Steve",
  view: null,
  questTab: "daily",
  fxBusy: false,
};

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, reduceMotion ? 0 : ms));
}

function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.remove("show"), 2200);
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ...(opts.headers || {}),
    },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.ok === false) {
    throw new Error(data.error || res.statusText || "request_failed");
  }
  return data;
}

function formatTimer(endsAt) {
  const ms = new Date(endsAt).getTime() - Date.now();
  if (Number.isNaN(ms) || ms <= 0) return "Сезон завершено";
  const total = Math.floor(ms / 1000);
  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  const mins = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  const pad = (n) => String(n).padStart(2, "0");
  return `До кінця сезону: ${days}д ${pad(hours)}:${pad(mins)}:${pad(secs)}`;
}

function spawnBurst(kind = "gold") {
  const burst = $("#fxBurst");
  burst.innerHTML = "";
  const count = reduceMotion ? 0 : 28;
  for (let i = 0; i < count; i += 1) {
    const p = document.createElement("span");
    const angle = (Math.PI * 2 * i) / count + Math.random() * 0.2;
    const dist = 90 + Math.random() * 160;
    p.className = `fx-particle ${i % 3 === 0 ? "is-round" : ""} ${i % 4 === 0 ? "is-soft" : ""} ${kind === "quest" && i % 5 === 0 ? "is-emerald" : ""}`;
    p.style.setProperty("--dx", `${Math.cos(angle) * dist}px`);
    p.style.setProperty("--dy", `${Math.sin(angle) * dist}px`);
    p.style.setProperty("--rot", `${Math.random() * 240 - 120}deg`);
    p.style.animationDelay = `${Math.random() * 120}ms`;
    burst.appendChild(p);
  }
}

function showFxOverlay({ mode, title, sub, kicker, icon }) {
  return new Promise((resolve) => {
    const overlay = $("#fxOverlay");
    const closeBtn = $("#fxClose");
    overlay.hidden = false;
    overlay.setAttribute("aria-hidden", "false");
    overlay.classList.toggle("is-quest", mode === "quest");
    overlay.classList.remove("is-open");
    $("#fxKicker").textContent = kicker;
    $("#fxTitle").textContent = title;
    $("#fxSub").textContent = sub || "";
    $("#fxIcon").className = `fa-solid ${icon || "fa-trophy"}`;
    spawnBurst(mode === "quest" ? "quest" : "gold");

    requestAnimationFrame(() => {
      overlay.classList.add("is-open");
    });

    const finish = () => {
      closeBtn.removeEventListener("click", finish);
      overlay.removeEventListener("click", onBackdrop);
      document.removeEventListener("keydown", onKey);
      overlay.classList.remove("is-open", "is-quest");
      overlay.hidden = true;
      overlay.setAttribute("aria-hidden", "true");
      $("#fxBurst").innerHTML = "";
      resolve();
    };

    const onBackdrop = (e) => {
      if (e.target === overlay || e.target.classList.contains("fx-backdrop")) finish();
    };
    const onKey = (e) => {
      if (e.key === "Escape" || e.key === "Enter") finish();
    };

    closeBtn.addEventListener("click", finish);
    overlay.addEventListener("click", onBackdrop);
    document.addEventListener("keydown", onKey);

    if (reduceMotion) {
      // still show modal, user dismisses
    }
  });
}

function flyXpChip(fromEl, amount) {
  if (reduceMotion || !fromEl) return;
  const rect = fromEl.getBoundingClientRect();
  const chip = document.createElement("div");
  chip.className = "fx-xp-chip";
  chip.textContent = `+${amount} XP`;
  chip.style.left = `${rect.left + rect.width / 2}px`;
  chip.style.top = `${rect.top}px`;
  $("#fxFloatLayer").appendChild(chip);
  setTimeout(() => chip.remove(), 1100);
}

async function animateXpBar(prevPlayer, nextPlayer) {
  const fill = $("#xpFill");
  const panel = $(".xp-panel");
  if (!fill || !panel || !nextPlayer) return;

  fill.classList.add("is-surge");
  if (prevPlayer && nextPlayer.level > prevPlayer.level) {
    panel.classList.add("is-levelup");
  }
  await wait(200);
  renderProgress();
  await wait(700);
  fill.classList.remove("is-surge");
  panel.classList.remove("is-levelup");
}

async function playQuestClaimFx(quest, xpGained, prevPlayer) {
  const card = document.querySelector(`.btn-claim[data-id="${quest.id}"]`)?.closest(".quest");
  if (card) {
    card.classList.add("is-completing");
    flyXpChip(card.querySelector(".quest__xp"), xpGained);
  }
  await wait(350);
  await showFxOverlay({
    mode: "quest",
    kicker: "Квест виконано",
    title: quest.title,
    sub: `+${xpGained} XP зараховано до Battle Pass`,
    icon: quest.icon || "fa-scroll",
  });
  await animateXpBar(prevPlayer, state.view.player);
  if (card) card.classList.remove("is-completing");
}

async function playRewardOpenFx(reward) {
  const node = [...document.querySelectorAll(".reward")].find((el) => {
    return el.querySelector(".reward__name")?.textContent === reward.name;
  });
  if (node) {
    node.classList.add("is-opening");
    await wait(520);
    node.classList.remove("is-opening");
  }

  await showFxOverlay({
    mode: "reward",
    kicker: reward.premium ? "Premium нагорода" : "Нагороду відкрито",
    title: reward.name,
    sub: `Рівень ${reward.level} · ${reward.premium ? "Premium трек" : "Безкоштовний трек"}`,
    icon: reward.icon || "fa-gift",
  });

  // Re-find after re-render and pop claimed state.
  requestAnimationFrame(() => {
    const claimed = [...document.querySelectorAll(".reward")].find((el) => {
      return el.querySelector(".reward__name")?.textContent === reward.name;
    });
    if (claimed) {
      claimed.classList.add("is-just-claimed");
      setTimeout(() => claimed.classList.remove("is-just-claimed"), 800);
    }
  });
}

function renderProgress() {
  const { season, player } = state.view;
  if (!season || !player) return;
  $("#seasonChip").innerHTML = `<i class="fa-solid fa-leaf"></i> Сезон ${season.number}`;
  $("#levelVal").textContent = String(player.level);
  $("#xpLabel").textContent = `${player.xp.toLocaleString("uk-UA")} / ${player.xp_to_next.toLocaleString("uk-UA")} XP`;
  const pct = Math.min(100, Math.round((player.xp / player.xp_to_next) * 100));
  const fill = $("#xpFill");
  requestAnimationFrame(() => {
    fill.style.width = `${pct}%`;
  });
  const bar = fill.parentElement;
  bar.setAttribute("aria-valuenow", String(player.xp));
  bar.setAttribute("aria-valuemax", String(player.xp_to_next));
  $("#seasonTimer").textContent = formatTimer(season.ends_at);
  $("#premiumBtn").classList.toggle("is-active", !!player.premium);
  $("#premiumBtn").innerHTML = player.premium
    ? '<i class="fa-solid fa-crown"></i> Premium ON'
    : '<i class="fa-solid fa-crown"></i> Premium';
  const playerInput = $("#playerName");
  if (playerInput && document.activeElement !== playerInput) {
    playerInput.value = state.player;
  }
}

function renderTrack() {
  const track = $("#rewardTrack");
  const rewards = state.view.rewards || [];
  const level = state.view.player?.level || 1;
  track.innerHTML = "";

  rewards.forEach((reward, index) => {
    const el = document.createElement("article");
    el.className = [
      "reward",
      reward.premium ? "is-premium" : "is-free",
      reward.claimed ? "is-claimed" : "",
      reward.locked ? "is-locked" : "",
      reward.level === level ? "is-current" : "",
      reward.claimable ? "is-claimable" : "",
    ].filter(Boolean).join(" ");
    el.style.animationDelay = `${index * 40}ms`;
    el.innerHTML = `
      <div class="reward__level">Рівень ${reward.level}</div>
      <div class="reward__slot" title="${reward.name}">
        <span class="reward__badge" aria-hidden="true">
          <i class="fa-solid ${reward.premium ? "fa-crown" : "fa-gift"}"></i>
        </span>
        <i class="fa-solid ${reward.icon}" aria-hidden="true"></i>
      </div>
      <div class="reward__name">${reward.name}</div>
    `;
    el.addEventListener("click", async () => {
      if (state.fxBusy) return;
      if (reward.claimed) return toast(`Уже отримано: ${reward.name}`);
      if (reward.locked) {
        return toast(reward.premium && !state.view.player.premium
          ? "Потрібен Premium Pass"
          : `Відкриється на рівні ${reward.level}`);
      }
      state.fxBusy = true;
      try {
        const res = await api("/api/battlepass/claim-reward", {
          method: "POST",
          body: JSON.stringify({
            player: state.player,
            level: reward.level,
            premium: reward.premium,
          }),
        });
        await playRewardOpenFx(reward);
        state.view = res.view;
        renderAll();
        toast(`Нагорода: ${reward.name}`);
      } catch (err) {
        toast(err.message);
      } finally {
        state.fxBusy = false;
      }
    });
    track.appendChild(el);
  });

  const current = track.querySelector(".is-current");
  if (current) current.scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" });
}

function renderQuests() {
  const list = $("#questList");
  const quests = state.view.quests?.[state.questTab] || [];
  list.innerHTML = "";
  if (!quests.length) {
    list.innerHTML = `<div class="empty-quests">Немає квестів у цій вкладці</div>`;
    return;
  }

  quests.forEach((quest, index) => {
    const pct = Math.min(100, Math.round((quest.current / quest.target) * 100));
    const el = document.createElement("article");
    el.className = `quest${quest.claimable ? " is-claimable" : ""}`;
    el.style.animationDelay = `${index * 50}ms`;
    el.setAttribute("role", "listitem");
    const label = quest.claimed ? "Отримано" : quest.claimable ? "Забрати" : "В процесі";
    el.innerHTML = `
      <div class="quest__icon"><i class="fa-solid ${quest.icon}"></i></div>
      <div class="quest__body">
        <h3>${quest.title}</h3>
        <p>${quest.desc}</p>
        <div class="quest__progress">
          <div class="quest__bar" aria-hidden="true"><span style="width:${pct}%"></span></div>
          <small>${quest.current}/${quest.target}</small>
        </div>
      </div>
      <div class="quest__reward">
        <div class="quest__xp">+${quest.xp} XP</div>
        <button type="button" class="btn-claim ${quest.claimed ? "is-done" : ""}" data-id="${quest.id}" ${!quest.claimable ? "disabled" : ""}>
          ${label}
        </button>
      </div>
    `;
    list.appendChild(el);
  });
}

function renderBonuses() {
  const bonuses = [
    {
      title: "Стрік активності",
      desc: "Заходь 7 днів поспіль і отримай +15% XP до кінця тижня.",
      icon: "fa-fire-flame-curved",
      tag: "Подія login_day",
    },
    {
      title: "Подвійний вікенд",
      desc: "У суботу та неділю всі щоденні квести дають ×2 XP.",
      icon: "fa-calendar-days",
      tag: "Налаштовується адміном",
    },
    {
      title: "Подарунок громаді",
      desc: "Рекорд онлайну → кейс удачі всім гравцям сезону.",
      icon: "fa-users",
      tag: "Івент сезону",
    },
  ];
  $("#bonusGrid").innerHTML = bonuses.map((bonus, index) => `
    <article class="bonus" style="animation-delay:${index * 70}ms">
      <div class="bonus__icon"><i class="fa-solid ${bonus.icon}"></i></div>
      <h3>${bonus.title}</h3>
      <p>${bonus.desc}</p>
      <div class="bonus__tag"><i class="fa-solid fa-star"></i> ${bonus.tag}</div>
    </article>
  `).join("");
}

function renderAll() {
  if (!state.view?.season) {
    toast("Немає активного сезону — створи в адмінці");
    return;
  }
  const season = state.view.season;
  $(".hero__lead").textContent =
    `Сезон «${season.name}» — виконуй квести в Minecraft, збирай XP і відкривай нагороди.`;
  renderProgress();
  renderTrack();
  renderQuests();
  renderBonuses();
}

async function loadView() {
  const data = await api(`/api/battlepass/view?player=${encodeURIComponent(state.player)}`);
  state.view = data;
  renderAll();
}

function bindEvents() {
  $$("[data-quest-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.questTab = btn.dataset.questTab;
      $$("[data-quest-tab]").forEach((b) => {
        const on = b === btn;
        b.classList.toggle("active", on);
        b.setAttribute("aria-selected", on ? "true" : "false");
      });
      renderQuests();
    });
  });

  $("#questList").addEventListener("click", async (e) => {
    const btn = e.target.closest(".btn-claim");
    if (!btn || btn.disabled || state.fxBusy) return;
    state.fxBusy = true;
    const prevPlayer = { ...state.view.player };
    const quest = (state.view.quests?.[state.questTab] || []).find((q) => q.id === btn.dataset.id);
    try {
      const res = await api("/api/battlepass/claim-quest", {
        method: "POST",
        body: JSON.stringify({ player: state.player, quest_id: btn.dataset.id }),
      });
      state.view = res.view;
      if (quest) {
        await playQuestClaimFx(quest, res.xp_gained, prevPlayer);
      }
      renderAll();
      toast(`+${res.xp_gained} XP · рівень ${state.view.player.level}`);
    } catch (err) {
      toast(err.message);
    } finally {
      state.fxBusy = false;
    }
  });

  $("#trackPrev").addEventListener("click", () => {
    $("#rewardTrack").scrollBy({ left: -280, behavior: "smooth" });
  });
  $("#trackNext").addEventListener("click", () => {
    $("#rewardTrack").scrollBy({ left: 280, behavior: "smooth" });
  });

  async function setPremium(active) {
    try {
      const res = await api("/api/battlepass/premium", {
        method: "POST",
        body: JSON.stringify({ player: state.player, premium: active }),
      });
      state.view = res.view;
      renderAll();
      toast(active ? "Premium Pass активовано" : "Premium Pass вимкнено");
    } catch (err) {
      toast(err.message);
    }
  }

  $("#premiumBtn").addEventListener("click", () => setPremium(!state.view.player.premium));
  $("#unlockPremium").addEventListener("click", () => setPremium(true));

  const playerInput = $("#playerName");
  if (playerInput) {
    playerInput.value = state.player;
    playerInput.addEventListener("change", async () => {
      state.player = playerInput.value.trim() || "Steve";
      localStorage.setItem("bp_player", state.player);
      await loadView();
      toast(`Гравець: ${state.player}`);
    });
  }

  setInterval(() => {
    if (state.view?.season?.ends_at) {
      $("#seasonTimer").textContent = formatTimer(state.view.season.ends_at);
    }
  }, 1000);
}

bindEvents();
loadView().catch((err) => toast(err.message));
