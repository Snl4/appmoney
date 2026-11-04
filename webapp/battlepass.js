const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

const state = {
  player: localStorage.getItem("bp_player") || "Steve",
  view: null,
  questTab: "daily",
  fxBusy: false,
};

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const KNOWN_ICONS = new Set([
  "fa-coins", "fa-key", "fa-helmet-safety", "fa-bolt", "fa-face-smile", "fa-shirt",
  "fa-flag", "fa-sack-dollar", "fa-fire", "fa-certificate", "fa-toolbox", "fa-horse",
  "fa-box-open", "fa-sun", "fa-crown", "fa-person-walking", "fa-hammer", "fa-comments",
  "fa-skull", "fa-cube", "fa-handshake", "fa-compass", "fa-gift", "fa-trophy",
  "fa-scroll", "fa-star", "fa-users", "fa-calendar-days", "fa-fire-flame-curved",
]);

function safeIcon(icon, fallback = "fa-gift") {
  const name = String(icon || "").replace(/^fa-solid\s+/, "").trim();
  if (KNOWN_ICONS.has(name)) return name;
  if (name.startsWith("fa-") && KNOWN_ICONS.has(name)) return name;
  return fallback;
}

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
    $("#fxIcon").className = `fa-solid ${safeIcon(icon, mode === "quest" ? "fa-scroll" : "fa-gift")}`;
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
    icon: safeIcon(quest.icon, "fa-scroll"),
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
    icon: safeIcon(reward.icon, "fa-gift"),
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

function allQuests() {
  const q = state.view?.quests || {};
  return [...(q.daily || []), ...(q.weekly || []), ...(q.season || [])];
}

function rewardStatus(reward, player) {
  if (reward.claimed) return { key: "done", label: "Отримано" };
  if (reward.claimable) return { key: "ready", label: "Забрати" };
  if (reward.premium && !player.premium) return { key: "premium", label: "Premium" };
  if (reward.level > player.level) return { key: "locked", label: `З Lv ${reward.level}` };
  return { key: "locked", label: "Закрито" };
}

function renderGoal() {
  const card = $("#goalCard");
  if (!card || !state.view?.player) return;
  const player = state.view.player;
  const claimableQuests = allQuests().filter((q) => q.claimable);
  const claimableRewards = (state.view.rewards || []).filter((r) => r.claimable);
  const inProgress = allQuests().filter((q) => !q.claimed && !q.claimable);
  const nextReward = (state.view.rewards || []).find((r) => !r.claimed && !r.premium) 
    || (state.view.rewards || []).find((r) => !r.claimed);

  let step = 1;
  let title = "Виконай квест у Minecraft";
  let detail = inProgress.length
    ? `Найближче: «${inProgress[0].title}» — ${inProgress[0].current}/${inProgress[0].target}`
    : "Усі квести виконані або вже забрані.";
  let cta = { href: "#quests", text: "До квестів" };

  if (claimableQuests.length) {
    step = 2;
    title = `Забери XP з ${claimableQuests.length} квест${claimableQuests.length === 1 ? "у" : "ів"}`;
    detail = `«${claimableQuests[0].title}» готовий — +${claimableQuests[0].xp} XP чекають на сторінці.`;
    cta = { href: "#quests", text: "Забрати XP" };
  } else if (claimableRewards.length) {
    step = 3;
    title = `Відкрий ${claimableRewards.length} доступн${claimableRewards.length === 1 ? "у нагороду" : "і нагороди"}`;
    detail = `«${claimableRewards[0].name}» (рівень ${claimableRewards[0].level}) уже можна забрати.`;
    cta = { href: "#progress", text: "До нагород" };
  } else if (nextReward && nextReward.level > player.level) {
    const need = player.xp_to_next - player.xp;
    step = 2;
    title = `Ще ${need.toLocaleString("uk-UA")} XP до рівня ${player.level + 1}`;
    detail = nextReward
      ? `Після цього відкриється «${nextReward.name}».`
      : "Продовжуй виконувати квести.";
    cta = { href: "#quests", text: "Фармити XP" };
  }

  card.innerHTML = `
    <div class="goal-card__step">Крок ${step} з 3</div>
    <div class="goal-card__body">
      <h3>${title}</h3>
      <p>${detail}</p>
    </div>
    <a class="btn-secondary goal-card__cta" href="${cta.href}">${cta.text}</a>
  `;
}

function renderProgress() {
  const { season, player } = state.view;
  if (!season || !player) return;
  $("#seasonChip").innerHTML = `<i class="fa-solid fa-leaf"></i> Сезон ${season.number}`;
  $("#levelVal").textContent = String(player.level);
  const xpLeft = Math.max(0, player.xp_to_next - player.xp);
  const pct = Math.min(100, Math.round((player.xp / player.xp_to_next) * 100));
  $("#xpLabel").textContent = `${player.xp.toLocaleString("uk-UA")} / ${player.xp_to_next.toLocaleString("uk-UA")} XP цього рівня`;
  $("#xpPct").textContent = `${pct}%`;
  $("#xpNeed").textContent = xpLeft === 0
    ? "Рівень заповнено — бери нагороду"
    : `Ще ${xpLeft.toLocaleString("uk-UA")} XP до рівня ${player.level + 1}`;

  const nextFree = (state.view.rewards || []).find((r) => !r.claimed && !r.premium && r.level >= player.level);
  const nextAny = (state.view.rewards || []).find((r) => r.claimable)
    || (state.view.rewards || []).find((r) => !r.claimed && r.level > player.level);
  const nextBox = $("#xpNextReward");
  if (nextBox) {
    if (nextAny?.claimable) {
      nextBox.innerHTML = `<i class="fa-solid fa-gift"></i> Доступно зараз: <strong>${nextAny.name}</strong> — натисни на треку`;
      nextBox.className = "xp-panel__next is-ready";
    } else if (nextFree || nextAny) {
      const target = nextFree || nextAny;
      nextBox.innerHTML = `<i class="fa-solid fa-route"></i> Далі на треку: <strong>${target.name}</strong> · рівень ${target.level}`;
      nextBox.className = "xp-panel__next";
    } else {
      nextBox.innerHTML = `<i class="fa-solid fa-check"></i> Усі доступні нагороди цього шляху отримані`;
      nextBox.className = "xp-panel__next is-done";
    }
  }

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
  const player = state.view.player;
  const level = player?.level || 1;
  track.innerHTML = "";

  rewards.forEach((reward, index) => {
    const status = rewardStatus(reward, player);
    const el = document.createElement("article");
    el.className = [
      "reward",
      reward.premium ? "is-premium" : "is-free",
      reward.claimed ? "is-claimed" : "",
      reward.locked ? "is-locked" : "",
      reward.level === level ? "is-current" : "",
      reward.claimable ? "is-claimable" : "",
      `status-${status.key}`,
    ].filter(Boolean).join(" ");
    el.style.animationDelay = `${index * 40}ms`;
    el.setAttribute("aria-label", `${reward.name}, рівень ${reward.level}, ${status.label}`);
    el.innerHTML = `
      <div class="reward__level">Рівень ${reward.level}</div>
      <div class="reward__slot" title="${reward.name}">
        <span class="reward__badge" aria-hidden="true">
          <i class="fa-solid ${reward.premium ? "fa-crown" : "fa-gift"}"></i>
        </span>
        <i class="fa-solid ${safeIcon(reward.icon)}" aria-hidden="true"></i>
        ${reward.locked && !reward.claimed ? '<span class="reward__lock"><i class="fa-solid fa-lock"></i></span>' : ""}
      </div>
      <div class="reward__name">${reward.name}</div>
      <div class="reward__status status-${status.key}">${status.label}</div>
    `;
    el.addEventListener("click", async () => {
      if (state.fxBusy) return;
      if (reward.claimed) return toast(`Уже отримано: ${reward.name}`);
      if (reward.locked) {
        return toast(reward.premium && !state.view.player.premium
          ? "Ця нагорода з Premium Pass"
          : `Щоб відкрити «${reward.name}», потрібен рівень ${reward.level}. Зараз у тебе ${level}.`);
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

  const focus = track.querySelector(".is-claimable") || track.querySelector(".is-current");
  if (focus) focus.scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" });
}

function renderQuestSummary() {
  const box = $("#questSummary");
  if (!box) return;
  const list = state.view.quests?.[state.questTab] || [];
  const ready = list.filter((q) => q.claimable).length;
  const done = list.filter((q) => q.claimed).length;
  const active = list.filter((q) => !q.claimed && !q.claimable).length;
  const xpReady = list.filter((q) => q.claimable).reduce((s, q) => s + q.xp, 0);
  box.innerHTML = `
    <div class="quest-summary__item"><strong>${active}</strong><span>в процесі</span></div>
    <div class="quest-summary__item is-ready"><strong>${ready}</strong><span>готові забрати${xpReady ? ` · +${xpReady} XP` : ""}</span></div>
    <div class="quest-summary__item is-done"><strong>${done}</strong><span>вже отримано</span></div>
  `;
}

function renderQuests() {
  const list = $("#questList");
  const quests = state.view.quests?.[state.questTab] || [];
  renderQuestSummary();
  list.innerHTML = "";
  if (!quests.length) {
    list.innerHTML = `<div class="empty-quests">Немає квестів у цій вкладці</div>`;
    return;
  }

  quests.forEach((quest, index) => {
    const left = Math.max(0, quest.target - quest.current);
    const pct = Math.min(100, Math.round((quest.current / quest.target) * 100));
    const el = document.createElement("article");
    el.className = `quest${quest.claimable ? " is-claimable" : ""}${quest.claimed ? " is-claimed" : ""}`;
    el.style.animationDelay = `${index * 50}ms`;
    el.setAttribute("role", "listitem");

    let statusText = `Залишилось ${left.toLocaleString("uk-UA")} · зроби в Minecraft`;
    let label = "Ще не готово";
    if (quest.claimed) {
      statusText = "XP уже зараховано до Battle Pass";
      label = "XP отримано";
    } else if (quest.claimable) {
      statusText = "Готово! Натисни, щоб отримати XP";
      label = "Забрати XP";
    }

    el.innerHTML = `
      <div class="quest__icon"><i class="fa-solid ${safeIcon(quest.icon, "fa-scroll")}"></i></div>
      <div class="quest__body">
        <div class="quest__top">
          <h3>${quest.title}</h3>
          <span class="quest__state ${quest.claimable ? "is-ready" : quest.claimed ? "is-done" : ""}">${quest.claimable ? "Готово" : quest.claimed ? "Забрано" : `${pct}%`}</span>
        </div>
        <p>${quest.desc}</p>
        <div class="quest__progress">
          <div class="quest__bar" aria-hidden="true"><span style="width:${pct}%"></span></div>
          <small>${quest.current.toLocaleString("uk-UA")} / ${quest.target.toLocaleString("uk-UA")}</small>
        </div>
        <p class="quest__hint">${statusText}</p>
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
    `Сезон «${season.name}» — квест у грі → XP на сайті → нагорода на треку.`;
  renderGoal();
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
