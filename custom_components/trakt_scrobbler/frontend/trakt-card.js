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

const DEFAULT_ENTITY = {
  upcoming: "sensor.upcoming_shows",
  next_to_watch: "sensor.next_to_watch",
  watchlist: "sensor.watchlist",
  recommendations: "sensor.recommended_shows",
  stats: "sensor.stats",
};

const VIEW_TITLE = {
  upcoming: "Upcoming",
  next_to_watch: "Next to watch",
  watchlist: "Watchlist",
  recommendations: "Recommendations",
  stats: "Stats",
};

class TraktCard extends HTMLElement {
  setConfig(config) {
    if (!config) throw new Error("Invalid configuration");
    this._config = config;
    this._view = config.view || "upcoming";
    this._entity = config.entity || DEFAULT_ENTITY[this._view];
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return this._view === "stats" ? 3 : 6;
  }

  static getStubConfig() {
    return { view: "upcoming", entity: "sensor.upcoming_shows" };
  }

  _stateObj() {
    return this._hass && this._entity
      ? this._hass.states[this._entity]
      : undefined;
  }

  _title() {
    return this._config.title || VIEW_TITLE[this._view] || "Trakt";
  }

  _render() {
    if (!this._config || !this._hass) return;
    const st = this._stateObj();
    if (!st) {
      this._card(`<div class="tk-empty">Entity ${this._entity} not found.</div>`);
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
    let items = attrs.items;
    if (!Array.isArray(items) || !items.length) {
      const data = Array.isArray(attrs.data) ? attrs.data.slice(1) : [];
      items = data.map((d) => ({
        title: d.title,
        subtitle: d.episode,
        release: d.release,
        poster: d.poster,
        rating: d.rating,
        genres: d.genres,
        number: d.number,
        link: d.deep_link,
      }));
    }
    const max = this._config.max || 20;
    items = (items || []).filter((it) => it && it.title).slice(0, max);

    if (!items.length) {
      this._card(`<div class="tk-empty">Nothing here.</div>`);
      return;
    }

    const rows = items.map((it) => this._row(it)).join("");
    this._card(`<div class="tk-list">${rows}</div>`);
  }

  _row(it) {
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

    const body = `
      <div class="tk-info">
        <div class="tk-title">${this._esc(it.title)}</div>
        ${lines.map((l) => `<div class="tk-line">${l}</div>`).join("")}
      </div>`;

    const inner = `${poster}${body}`;
    return it.link
      ? `<a class="tk-item" href="${it.link}" target="_blank" rel="noopener">${inner}</a>`
      : `<div class="tk-item">${inner}</div>`;
  }

  _renderStats(st) {
    const a = st.attributes || {};
    const tiles = [
      ["mdi:movie", a.movies_watched, "Movies"],
      ["mdi:television-classic", a.episodes_watched, "Episodes"],
      ["mdi:playlist-play", a.shows_watched, "Shows"],
      ["mdi:clock-outline", a.total_days, "Days"],
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
    this._card(`<div class="tk-stats">${body}</div>`);
  }

  _card(inner) {
    this.innerHTML = `
      <ha-card header="${this._esc(this._title())}">
        <div class="tk-body">${inner}</div>
      </ha-card>
      <style>
        .tk-body { padding: 0 12px 12px; }
        .tk-list { display: flex; flex-direction: column; gap: 10px; }
        .tk-item {
          display: flex; gap: 12px; align-items: flex-start;
          text-decoration: none; color: var(--primary-text-color);
        }
        .tk-poster {
          width: 62px; min-width: 62px; height: 92px; object-fit: cover;
          border-radius: 6px; background: var(--secondary-background-color);
        }
        .tk-noposter { display: block; }
        .tk-info { display: flex; flex-direction: column; gap: 2px; }
        .tk-title { font-weight: 600; }
        .tk-line { font-size: 0.85em; color: var(--secondary-text-color); }
        .tk-genres { font-style: italic; }
        .tk-empty { padding: 16px 0; color: var(--secondary-text-color); }
        .tk-stats {
          display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px;
          padding-top: 8px; text-align: center;
        }
        .tk-stat ha-icon { color: var(--state-icon-color); }
        .tk-stat-value { font-size: 1.4em; font-weight: 600; }
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

window.customCards = window.customCards || [];
window.customCards.push({
  type: "trakt-card",
  name: "Trakt Card",
  description:
    "Upcoming, next-to-watch, watchlist, stats and recommendations from Trakt.",
  preview: true,
});
