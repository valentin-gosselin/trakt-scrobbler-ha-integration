/* Trakt card for Home Assistant.
 * A single configurable card served and auto-registered by the
 * trakt_scrobbler integration. No manual resource install needed.
 */

class TraktCard extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 6;
  }

  _render() {
    if (!this._config) return;
    const type = this._config.type_view || this._config.view || "upcoming";
    this.innerHTML = `
      <ha-card header="Trakt (${type})">
        <div style="padding:16px">Trakt card loaded.</div>
      </ha-card>`;
  }
}

customElements.define("trakt-card", TraktCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "trakt-card",
  name: "Trakt Card",
  description: "Upcoming, next-to-watch, watchlist, stats and recommendations from Trakt.",
  preview: true,
});
