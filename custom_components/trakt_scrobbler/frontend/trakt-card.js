/* Trakt card for Home Assistant.
 * A single configurable card served and auto-registered by the
 * trakt_scrobbler integration. No manual resource install needed.
 *
 * config:
 *   type: custom:trakt-card
 *   view: upcoming | next_to_watch | watchlist | recommendations | stats
 *   entity: sensor.xxx        (optional, sensible default per view)
 *   title: "..."              (optional)
 *   max: 20                   (optional item cap for list views)
 */

// The entity id ends with these suffixes; the integration prefixes them with
// its device name (e.g. sensor.trakt_scrobbler_upcoming_shows), so we match by
// suffix instead of hardcoding the full id.
const VIEW_SUFFIX = {
  upcoming: "upcoming_shows",
  next_to_watch: "next_to_watch",
  watchlist: "watchlist",
  recommendations: "recommended_shows",
  stats: "stats",
};

// Find the real sensor entity for a view by matching its suffix in hass.states.
// Falls back to the plain sensor.<suffix> if nothing is found (or no hass).
function entityForView(view, hass) {
  const suffix = VIEW_SUFFIX[view] || VIEW_SUFFIX.upcoming;
  if (hass && hass.states) {
    const match = Object.keys(hass.states).find(
      (id) => id.startsWith("sensor.") && id.endsWith(suffix)
    );
    if (match) return match;
  }
  return `sensor.${suffix}`;
}

const STRINGS = {
  en: {
    upcoming: "Upcoming",
    next_to_watch: "Next to watch",
    watchlist: "Watchlist",
    recommendations: "Recommendations",
    stats: "Stats",
    empty: "Nothing here.",
    not_found: (e) => `Entity ${e} not found.`,
    days_watched: "days watched",
    movies: "Movies",
    episodes: "Episodes",
    shows: "Shows",
    movie_plays: "Movie plays",
    mark_watched: "Mark watched",
    add_watchlist: "Add to watchlist",
    label_view: "View",
    label_entity: "Entity",
    label_title: "Title (optional)",
  },
  fr: {
    upcoming: "À venir",
    next_to_watch: "À regarder ensuite",
    watchlist: "Liste de suivi",
    recommendations: "Recommandations",
    stats: "Statistiques",
    empty: "Rien ici.",
    not_found: (e) => `Entité ${e} introuvable.`,
    days_watched: "jours de visionnage",
    movies: "Films",
    episodes: "Épisodes",
    shows: "Séries",
    movie_plays: "Lectures films",
    mark_watched: "Marquer comme vu",
    add_watchlist: "Ajouter à la liste",
    label_view: "Vue",
    label_entity: "Entité",
    label_title: "Titre (optionnel)",
  },
  de: {
    upcoming: "Demnächst",
    next_to_watch: "Als Nächstes",
    watchlist: "Merkliste",
    recommendations: "Empfehlungen",
    stats: "Statistiken",
    empty: "Nichts hier.",
    not_found: (e) => `Entität ${e} nicht gefunden.`,
    days_watched: "Tage angesehen",
    movies: "Filme",
    episodes: "Folgen",
    shows: "Serien",
    movie_plays: "Film-Wiedergaben",
    mark_watched: "Als gesehen markieren",
    add_watchlist: "Zur Merkliste",
    label_view: "Ansicht",
    label_entity: "Entität",
    label_title: "Titel (optional)",
  },
  es: {
    upcoming: "Próximamente",
    next_to_watch: "Ver a continuación",
    watchlist: "Lista de seguimiento",
    recommendations: "Recomendaciones",
    stats: "Estadísticas",
    empty: "Nada aquí.",
    not_found: (e) => `Entidad ${e} no encontrada.`,
    days_watched: "días vistos",
    movies: "Películas",
    episodes: "Episodios",
    shows: "Series",
    movie_plays: "Reproducciones",
    mark_watched: "Marcar como visto",
    add_watchlist: "Añadir a la lista",
    label_view: "Vista",
    label_entity: "Entidad",
    label_title: "Título (opcional)",
  },
};

class TraktCard extends HTMLElement {
  _t(key, ...args) {
    const lang = (this._hass && this._hass.language) || "en";
    const table = STRINGS[lang] || STRINGS.en;
    const val = table[key] != null ? table[key] : STRINGS.en[key];
    return typeof val === "function" ? val(...args) : val;
  }

  setConfig(config) {
    if (!config) throw new Error("Invalid configuration");
    this._config = config;
    this._view = config.view || "upcoming";
    // Keep an explicit entity if the user set one; otherwise resolve it lazily
    // once hass is available (entity ids carry the integration prefix).
    this._explicitEntity = config.entity || null;
    this._entity = this._explicitEntity;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._explicitEntity) {
      this._entity = entityForView(this._view, hass);
    }
    this._render();
  }

  getCardSize() {
    return this._view === "stats" ? 3 : 6;
  }

  static getConfigElement() {
    return document.createElement("trakt-card-editor");
  }

  static getStubConfig(hass) {
    return { view: "upcoming", entity: entityForView("upcoming", hass) };
  }

  _stateObj() {
    return this._hass && this._entity
      ? this._hass.states[this._entity]
      : undefined;
  }

  _title() {
    return this._config.title || this._t(this._view) || "Trakt";
  }

  _render() {
    if (!this._config || !this._hass) return;
    const st = this._stateObj();
    if (!st) {
      this._card(
        `<div class="tk-empty">${this._esc(this._t("not_found", this._entity))}</div>`
      );
      return;
    }
    if (this._view === "stats") {
      this._renderStats(st);
    } else {
      this._renderList(st);
    }
  }

  _renderList(st) {
    const attrs = st.attributes || {};
    // Prefer the enriched `items` (poster/rating/link); fall back to `data`.
    // If the sensor's data has a flagged empty placeholder, show a localized
    // empty message with no items or action buttons.
    const data = Array.isArray(attrs.data) ? attrs.data.slice(1) : [];
    if (data.length === 1 && data[0] && data[0].empty) {
      this._card(`<div class="tk-empty">${this._esc(this._t("empty"))}</div>`);
      return;
    }

    let items = attrs.items;
    if (!Array.isArray(items) || !items.length) {
      items = data
        .filter((d) => d && !d.empty)
        .map((d) => ({
          title: d.title,
          subtitle: d.episode,
          release: d.release,
          poster: d.poster,
          rating: d.rating,
          genres: d.genres,
          number: d.number,
          link: d.deep_link,
          ids: d.ids,
          season: d.season,
          number_int: d.number_int,
          media_type: d.media_type,
        }));
    }
    const max = this._config.max || 20;
    items = (items || []).filter((it) => it && it.title).slice(0, max);

    if (!items.length) {
      this._card(`<div class="tk-empty">${this._esc(this._t("empty"))}</div>`);
      return;
    }

    const rows = items.map((it, i) => this._row(it, i)).join("");
    this._items = items;
    this._card(`<div class="tk-list">${rows}</div>`);
    this._bindActions();
  }

  _row(it, index) {
    const poster = it.poster
      ? `<img class="tk-poster" src="${it.poster}" loading="lazy" />`
      : `<div class="tk-poster tk-noposter"></div>`;
    const lines = [];
    if (it.subtitle) lines.push(this._esc(it.subtitle));
    const meta = [];
    if (it.number) meta.push(this._esc(it.number));
    if (it.release) meta.push(this._esc(it.release));
    if (it.rating) meta.push("★ " + this._esc(String(it.rating)));
    if (meta.length) lines.push(meta.join(" · "));
    if (it.genres) lines.push(`<span class="tk-genres">${this._esc(it.genres)}</span>`);

    const link = it.link
      ? `<a class="tk-title tk-link" href="${it.link}" target="_blank" rel="noopener">${this._esc(it.title)}</a>`
      : `<div class="tk-title">${this._esc(it.title)}</div>`;

    // Quick actions depend on the view:
    // - recommendations: "add to watchlist" (content not yet followed)
    // - upcoming / next_to_watch: "mark watched"
    // - watchlist: no quick action (already there)
    const buttons = [];
    if (this._view === "recommendations") {
      buttons.push(
        `<ha-icon-button class="tk-act" data-act="watchlist" data-idx="${index}"
           title="${this._esc(this._t("add_watchlist"))}">
           <ha-icon icon="mdi:bookmark-plus-outline"></ha-icon>
         </ha-icon-button>`
      );
    } else if (
      this._view === "upcoming" ||
      this._view === "next_to_watch"
    ) {
      buttons.push(
        `<ha-icon-button class="tk-act" data-act="watched" data-idx="${index}"
           title="${this._esc(this._t("mark_watched"))}">
           <ha-icon icon="mdi:check"></ha-icon>
         </ha-icon-button>`
      );
    }
    const actions = buttons.length
      ? `<div class="tk-actions">${buttons.join("")}</div>`
      : "";

    return `
      <div class="tk-item">
        ${poster}
        <div class="tk-info">
          ${link}
          ${lines.map((l) => `<div class="tk-line">${l}</div>`).join("")}
        </div>
        ${actions}
      </div>`;
  }

  _bindActions() {
    this.querySelectorAll(".tk-act").forEach((btn) => {
      btn.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        const idx = parseInt(btn.getAttribute("data-idx"), 10);
        const act = btn.getAttribute("data-act");
        const item = (this._items || [])[idx];
        if (item) this._doAction(act, item, btn);
      });
    });
  }

  async _doAction(act, item, btn) {
    const ids = item.ids || {};
    const idFields = {};
    for (const k of ["trakt", "imdb", "tmdb", "tvdb"]) {
      if (ids[k]) idFields[k] = String(ids[k]);
    }
    // The item's own media_type is authoritative (show or movie). Never guess
    // from the presence of an episode number, which mismatched shows to movies.
    const mediaType =
      item.media_type ||
      (item.number || this._view === "next_to_watch" ? "show" : "movie");
    const isShow = mediaType === "show";

    // Immediate visual feedback: remove the row right away so it feels instant.
    const row = btn ? btn.closest(".tk-item") : null;
    if (row) {
      row.style.transition = "opacity .2s, height .2s";
      row.style.opacity = "0";
      setTimeout(() => row.remove(), 200);
    }

    try {
      if (act === "watchlist") {
        await this._hass.callService("trakt_scrobbler", "add_to_watchlist", {
          media_type: isShow ? "show" : "movie",
          title: item.title,
          ...idFields,
        });
      } else if (act === "watched") {
        // Mark the specific episode when we have season/number (shows in the
        // upcoming/next lists), else mark the movie.
        const asEpisode = isShow && item.number_int != null;
        const data = {
          media_type: asEpisode ? "episode" : isShow ? "episode" : "movie",
          ...idFields,
        };
        if (asEpisode && item.season != null) {
          data.season = item.season;
          data.episode = item.number_int;
        }
        if (item.title) data.title = item.title;
        await this._hass.callService("trakt_scrobbler", "mark_watched", data);
      }
      this._toast(act);
      // Refresh the sensor so the data catches up (next episode appears).
      setTimeout(() => {
        this._hass.callService("homeassistant", "update_entity", {
          entity_id: this._entity,
        });
      }, 1500);
    } catch (err) {
      if (row) row.style.opacity = "1";
    }
  }

  _toast(act) {
    const msg =
      act === "watchlist" ? this._t("add_watchlist") : this._t("mark_watched");
    const ev = new Event("hass-notification", { bubbles: true, composed: true });
    ev.detail = { message: msg + " ✓" };
    this.dispatchEvent(ev);
  }

  _renderStats(st) {
    const a = st.attributes || {};
    const days = a.total_days;
    const hero =
      days != null
        ? `<div class="tk-hero">
             <ha-icon icon="mdi:filmstrip"></ha-icon>
             <span><b>${this._esc(String(days))}</b> ${this._esc(this._t("days_watched"))}</span>
           </div>`
        : "";
    const tiles = [
      ["mdi:movie", a.movies_watched, this._t("movies")],
      ["mdi:television-classic", a.episodes_watched, this._t("episodes")],
      ["mdi:playlist-play", a.shows_watched, this._t("shows")],
      ["mdi:play-circle-outline", a.movies_plays, this._t("movie_plays")],
    ];
    const body = tiles
      .map(
        ([icon, value, label]) => `
        <div class="tk-stat">
          <ha-icon icon="${icon}"></ha-icon>
          <div class="tk-stat-value">${value ?? "-"}</div>
          <div class="tk-stat-label">${label}</div>
        </div>`
      )
      .join("");
    this._card(`${hero}<div class="tk-stats">${body}</div>`);
  }

  _card(inner) {
    this.innerHTML = `
      <ha-card header="${this._esc(this._title())}">
        <div class="tk-body">${inner}</div>
      </ha-card>
      <style>
        .tk-body { padding: 0 12px 12px; }
        .tk-list { display: flex; flex-direction: column; gap: 12px; }
        .tk-item {
          display: grid;
          grid-template-columns: 62px 1fr auto;
          gap: 12px;
          align-items: start;
          color: var(--primary-text-color);
        }
        .tk-link { text-decoration: none; color: var(--primary-text-color); }
        .tk-link:hover { color: var(--primary-color); }
        .tk-actions {
          display: flex; flex-direction: column; gap: 2px;
          opacity: 0.75;
        }
        .tk-act { --mdc-icon-button-size: 34px; --mdc-icon-size: 20px; }
        .tk-poster {
          width: 62px; height: 92px; object-fit: cover;
          border-radius: 6px; background: var(--secondary-background-color);
        }
        .tk-noposter {
          display: flex; align-items: center; justify-content: center;
        }
        .tk-info {
          display: flex; flex-direction: column; gap: 2px;
          min-width: 0; padding-top: 2px;
        }
        .tk-title {
          font-weight: 600; line-height: 1.2;
          overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
        }
        .tk-line {
          font-size: 0.85em; color: var(--secondary-text-color);
          line-height: 1.35;
          overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
        }
        .tk-genres { font-style: italic; }
        .tk-empty { padding: 16px 0; color: var(--secondary-text-color); }
        .tk-hero {
          display: flex; align-items: center; gap: 10px;
          padding: 12px 0 4px; font-size: 1.1em;
        }
        .tk-hero ha-icon { color: var(--state-icon-color); }
        .tk-hero b { font-size: 1.3em; }
        .tk-stats {
          display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px;
          padding-top: 8px; text-align: center;
        }
        .tk-stat {
          display: flex; flex-direction: column; align-items: center; gap: 4px;
          padding: 12px 4px; border-radius: 10px;
          background: var(--secondary-background-color);
        }
        .tk-stat ha-icon { color: var(--state-icon-color); --mdc-icon-size: 28px; }
        .tk-stat-value { font-size: 1.5em; font-weight: 700; }
        .tk-stat-label { font-size: 0.8em; color: var(--secondary-text-color); }
      </style>`;
  }

  _esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
}

customElements.define("trakt-card", TraktCard);

const VIEWS = [
  "upcoming",
  "next_to_watch",
  "watchlist",
  "recommendations",
  "stats",
];

class TraktCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _t(key) {
    const lang = (this._hass && this._hass.language) || "en";
    const table = STRINGS[lang] || STRINGS.en;
    return table[key] != null ? table[key] : STRINGS.en[key];
  }

  _emit() {
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config: this._config },
        bubbles: true,
        composed: true,
      })
    );
  }

  _render() {
    if (!this._config || !this._hass) return;
    const view = this._config.view || "upcoming";
    const entity = this._config.entity || entityForView(view, this._hass);
    const title = this._config.title || "";

    if (!this._built) {
      this.innerHTML = `
        <div style="display:flex;flex-direction:column;gap:12px;padding:8px 0;">
          <label style="display:flex;flex-direction:column;gap:4px;">
            <span>${this._t("label_view")}</span>
            <select id="tk-view" style="padding:8px;border-radius:6px;
              background:var(--secondary-background-color);
              color:var(--primary-text-color);
              border:1px solid var(--divider-color);"></select>
          </label>
          <ha-entity-picker id="tk-entity"
            .includeDomains='${JSON.stringify(["sensor"])}'
            allow-custom-entity></ha-entity-picker>
          <ha-textfield id="tk-title"></ha-textfield>
        </div>`;
      this._built = true;

      const sel = this.querySelector("#tk-view");
      VIEWS.forEach((v) => {
        const opt = document.createElement("option");
        opt.value = v;
        // Flag views whose sensor is not enabled so the user knows why they are
        // empty (those groups are off in the integration options by default).
        const hasEntity =
          this._hass &&
          this._hass.states &&
          Object.keys(this._hass.states).some(
            (id) => id.startsWith("sensor.") && id.endsWith(VIEW_SUFFIX[v])
          );
        opt.textContent = hasEntity ? this._t(v) : `${this._t(v)} (?)`;
        sel.appendChild(opt);
      });
      sel.addEventListener("change", (e) => {
        const v = e.target.value;
        // Point at the real sensor for the new view. Drop any previous explicit
        // entity so the card resolves the right one for this view.
        this._config = { ...this._config, view: v };
        this._config.entity = entityForView(v, this._hass);
        this._built = false;
        this._render();
        this._emit();
      });

      const ep = this.querySelector("#tk-entity");
      ep.addEventListener("value-changed", (e) => {
        this._config = { ...this._config, entity: e.detail.value };
        this._emit();
      });

      const tf = this.querySelector("#tk-title");
      tf.addEventListener("input", (e) => {
        const val = e.target.value;
        this._config = { ...this._config };
        if (val) this._config.title = val;
        else delete this._config.title;
        this._emit();
      });
    }

    const sel = this.querySelector("#tk-view");
    if (sel) sel.value = view;
    const ep = this.querySelector("#tk-entity");
    if (ep) {
      ep.hass = this._hass;
      ep.value = entity;
    }
    const tf = this.querySelector("#tk-title");
    if (tf) {
      tf.label = this._t("label_title");
      tf.value = title;
    }
  }
}

customElements.define("trakt-card-editor", TraktCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "trakt-card",
  name: "Trakt Card",
  description:
    "Upcoming, next-to-watch, watchlist, stats and recommendations from Trakt.",
  preview: true,
  documentationURL:
    "https://github.com/valentin-gosselin/trakt-scrobbler-ha-integration#trakt-card",
});
