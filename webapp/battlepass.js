const SEASON = {
  name: "Золота Долина",
  number: 3,
  endsAt: Date.now() + (18 * 24 + 6) * 60 * 60 * 1000 + 42 * 60 * 1000,
  level: 7,
  xp: 1840,
  xpToNext: 2200,
  premium: false,
};

const REWARDS = [
  { level: 1, name: "50 монет", icon: "fa-coins", premium: false, claimed: true },
  { level: 2, name: "Ключ скрині", icon: "fa-key", premium: true, claimed: true },
  { level: 3, name: "Шолом мандрівника", icon: "fa-helmet-safety", premium: false, claimed: true },
  { level: 4, name: "XP буст 1г", icon: "fa-bolt", premium: true, claimed: true },
  { level: 5, name: "Емоут «Чіл»", icon: "fa-face-smile", premium: false, claimed: true },
  { level: 6, name: "Скін плаща", icon: "fa-shirt", premium: true, claimed: true },
  { level: 7, name: "Баннер Долини", icon: "fa-flag", premium: false, claimed: false },
  { level: 8, name: "200 монет", icon: "fa-sack-dollar", premium: true, claimed: false },
  { level: 9, name: "Фейєрверк", icon: "fa-fire", premium: false, claimed: false },
  { level: 10, name: "Титул «Слідопит»", icon: "fa-certificate", premium: true, claimed: false },
  { level: 11, name: "Набір інструментів", icon: "fa-toolbox", premium: false, claimed: false },
  { level: 12, name: "Пегас-маунт скін", icon: "fa-horse", premium: true, claimed: false },
  { level: 13, name: "Рідкісний кейс", icon: "fa-box-open", premium: false, claimed: false },
  { level: 14, name: "Аура золота", icon: "fa-sun", premium: true, claimed: false },
  { level: 15, name: "Корона сезону", icon: "fa-crown", premium: true, claimed: false },
];

const QUESTS = {
  daily: [
    {
      id: "d1",
      title: "Прогулянка долиною",
      desc: "Пройди 2 000 блоків пішки",
      icon: "fa-person-walking",
      current: 1480,
      target: 2000,
      xp: 120,
      claimed: false,
    },
    {
      id: "d2",
      title: "Ремісник дня",
      desc: "Скрафти 16 предметів",
      icon: "fa-hammer",
      current: 16,
      target: 16,
      xp: 150,
      claimed: false,
    },
    {
      id: "d3",
      title: "Голос громади",
      desc: "Напиши 10 повідомлень у чаті",
      icon: "fa-comments",
      current: 4,
      target: 10,
      xp: 80,
      claimed: false,
    },
    {
      id: "d4",
      title: "Полювання на зомбі",
      desc: "Убий 20 ворожих мобів",
      icon: "fa-skull",
      current: 20,
      target: 20,
      xp: 180,
      claimed: true,
    },
  ],
  weekly: [
    {
      id: "w1",
      title: "Будівничий тижня",
      desc: "Постав 500 блоків",
      icon: "fa-cube",
      current: 312,
      target: 500,
      xp: 600,
      claimed: false,
    },
    {
      id: "w2",
      title: "Економіка Долини",
      desc: "Зроби 5 угод на ринку",
      icon: "fa-handshake",
      current: 2,
      target: 5,
      xp: 450,
      claimed: false,
    },
    {
      id: "w3",
      title: "Дослідник країв",
      desc: "Відвідай 3 різні біоми",
      icon: "fa-compass",
      current: 3,
      target: 3,
      xp: 500,
      claimed: false,
    },
  ],
};

const BONUSES = [
  {
    title: "Стрік активності",
    desc: "Заходь 7 днів поспіль і отримай +15% XP до кінця тижня.",
    icon: "fa-fire-flame-curved",
    tag: "Активно · день 4/7",
  },
  {
    title: "Подвійний вікенд",
    desc: "У суботу та неділю всі щоденні квести дають ×2 XP.",
    icon: "fa-calendar-days",
    tag: "Щоп’ятниці 18:00",
  },
  {
    title: "Подарунок громаді",
    desc: "Коли сервер б’є рекорд онлайну — усім гравцям кейс удачі.",
    icon: "fa-users",
    tag: "Івент сезону",
  },
];

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

let activeQuestTab = "daily";

function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.remove("show"), 2200);
}

function formatTimer(ms) {
  if (ms <= 0) return "Сезон завершено";
  const total = Math.floor(ms / 1000);
  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  const mins = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  const pad = (n) => String(n).padStart(2, "0");
  return `До кінця сезону: ${days}д ${pad(hours)}:${pad(mins)}:${pad(secs)}`;
}

function updateTimer() {
  $("#seasonTimer").textContent = formatTimer(SEASON.endsAt - Date.now());
}

function renderProgress() {
  $("#levelVal").textContent = String(SEASON.level);
  $("#xpLabel").textContent = `${SEASON.xp.toLocaleString("uk-UA")} / ${SEASON.xpToNext.toLocaleString("uk-UA")} XP`;
  const fill = $("#xpFill");
  const bar = fill.parentElement;
  const pct = Math.min(100, Math.round((SEASON.xp / SEASON.xpToNext) * 100));
  requestAnimationFrame(() => {
    fill.style.width = `${pct}%`;
  });
  bar.setAttribute("aria-valuenow", String(SEASON.xp));
  bar.setAttribute("aria-valuemax", String(SEASON.xpToNext));
}

function renderTrack() {
  const track = $("#rewardTrack");
  track.innerHTML = "";

  REWARDS.forEach((reward, index) => {
    const locked = reward.level > SEASON.level || (reward.premium && !SEASON.premium);
    const current = reward.level === SEASON.level;
    const el = document.createElement("article");
    el.className = [
      "reward",
      reward.premium ? "is-premium" : "is-free",
      reward.claimed ? "is-claimed" : "",
      locked ? "is-locked" : "",
      current ? "is-current" : "",
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

    el.addEventListener("click", () => {
      if (reward.claimed) {
        toast(`Уже отримано: ${reward.name}`);
        return;
      }
      if (reward.level > SEASON.level) {
        toast(`Відкриється на рівні ${reward.level}`);
        return;
      }
      if (reward.premium && !SEASON.premium) {
        toast("Потрібен Premium Pass");
        return;
      }
      reward.claimed = true;
      toast(`Нагорода отримана: ${reward.name}`);
      renderTrack();
    });

    track.appendChild(el);
  });

  const current = track.querySelector(".is-current");
  if (current) {
    current.scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" });
  }
}

function renderQuests() {
  const list = $("#questList");
  list.innerHTML = "";
  QUESTS[activeQuestTab].forEach((quest, index) => {
    const done = quest.current >= quest.target;
    const pct = Math.min(100, Math.round((quest.current / quest.target) * 100));
    const el = document.createElement("article");
    el.className = "quest";
    el.style.animationDelay = `${index * 50}ms`;
    el.setAttribute("role", "listitem");
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
        <button type="button" class="btn-claim ${quest.claimed ? "is-done" : ""}" data-id="${quest.id}" ${!done || quest.claimed ? "disabled" : ""}>
          ${quest.claimed ? "Отримано" : done ? "Забрати" : "В процесі"}
        </button>
      </div>
    `;
    list.appendChild(el);
  });
}

function renderBonuses() {
  const grid = $("#bonusGrid");
  grid.innerHTML = BONUSES.map((bonus, index) => `
    <article class="bonus" style="animation-delay:${index * 70}ms">
      <div class="bonus__icon"><i class="fa-solid ${bonus.icon}"></i></div>
      <h3>${bonus.title}</h3>
      <p>${bonus.desc}</p>
      <div class="bonus__tag"><i class="fa-solid fa-star"></i> ${bonus.tag}</div>
    </article>
  `).join("");
}

function claimQuest(id) {
  const quest = [...QUESTS.daily, ...QUESTS.weekly].find((q) => q.id === id);
  if (!quest || quest.claimed || quest.current < quest.target) return;

  quest.claimed = true;
  SEASON.xp += quest.xp;
  while (SEASON.xp >= SEASON.xpToNext) {
    SEASON.xp -= SEASON.xpToNext;
    SEASON.level += 1;
    SEASON.xpToNext = Math.round(SEASON.xpToNext * 1.08);
  }
  toast(`+${quest.xp} XP · рівень ${SEASON.level}`);
  renderProgress();
  renderTrack();
  renderQuests();
}

function setPremium(active) {
  SEASON.premium = active;
  $("#premiumBtn").classList.toggle("is-active", active);
  $("#premiumBtn").innerHTML = active
    ? '<i class="fa-solid fa-crown"></i> Premium ON'
    : '<i class="fa-solid fa-crown"></i> Premium';
  toast(active ? "Premium Pass активовано" : "Premium Pass вимкнено");
  renderTrack();
}

function bindEvents() {
  $$("[data-quest-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      activeQuestTab = btn.dataset.questTab;
      $$("[data-quest-tab]").forEach((b) => {
        const on = b === btn;
        b.classList.toggle("active", on);
        b.setAttribute("aria-selected", on ? "true" : "false");
      });
      renderQuests();
    });
  });

  $("#questList").addEventListener("click", (e) => {
    const btn = e.target.closest(".btn-claim");
    if (!btn || btn.disabled) return;
    claimQuest(btn.dataset.id);
  });

  $("#trackPrev").addEventListener("click", () => {
    $("#rewardTrack").scrollBy({ left: -280, behavior: "smooth" });
  });
  $("#trackNext").addEventListener("click", () => {
    $("#rewardTrack").scrollBy({ left: 280, behavior: "smooth" });
  });

  $("#premiumBtn").addEventListener("click", () => setPremium(!SEASON.premium));
  $("#unlockPremium").addEventListener("click", () => setPremium(true));
}

function init() {
  $("#seasonChip").innerHTML = `<i class="fa-solid fa-leaf"></i> Сезон ${SEASON.number}`;
  renderProgress();
  renderTrack();
  renderQuests();
  renderBonuses();
  bindEvents();
  updateTimer();
  setInterval(updateTimer, 1000);
}

init();
