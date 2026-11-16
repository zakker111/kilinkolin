/* Kilinkolin runtime config. */
window.KILINKOLIN = {
  APP_NAME: "Kilinkolin",
  TAGLINE: "Estimated crowd flow for events in Tampere.",
  CITY: "tampere",
  APP_VERSION: "0.16.1",
  MODEL_VERSION: "2026.11.11",
  SCHEMA_VERSION: 3,

  /* Raster basemap. Any XYZ tile template works; no API key needed.
     To switch provider, change these two lines (e.g. a CARTO light basemap). */
  TILE_URL: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
  TILE_ATTRIBUTION: "© OpenStreetMap contributors",
  TILE_MAX_ZOOM: 19,

  REPO: "https://github.com/zakker111/kilinkolin",
  UPSTREAM: "https://github.com/zakker111/tampere-keikat"
};
