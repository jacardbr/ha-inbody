/*
 * HA InBody card
 *
 * Tabs for the body composition sensors:
 *   - Weight / mass (kg): weight, skeletal muscle, body fat, body water
 *   - Percentage (%):     body fat, skeletal muscle, body water
 *   - Body composition:   body map (male or female figure) with water,
 *                         skeletal muscle and body fat bands
 * The first two show the current values and a statistics graph (so the
 * imported history is visible). Plain JavaScript, no dependencies.
 *
 * Usage:
 *   type: custom:ha-inbody-card
 *
 * Options: see README.md.
 */

const DOMAIN = "ha_inbody";
const TAG = "ha-inbody-card";
const EDITOR_TAG = "ha-inbody-card-editor";

// translation_key of the sensors, in display order
const MASS_KEYS = [
  "weight",
  "skeletal_muscle_mass",
  "body_fat_mass",
  "body_water_mass",
];
const PERCENTAGE_KEYS = [
  "body_fat_percentage",
  "skeletal_muscle_percentage",
  "body_water_percentage",
];
const TABS = ["mass", "percentage", "composition", "quadrant"];
// tabs that list sensors (the checklists in the editor); the others are fixed charts
const SENSOR_TABS = ["mass", "percentage"];
const COMPOSITION_KEYS = [
  "body_fat_percentage",
  "skeletal_muscle_percentage",
  "body_water_percentage",
  "body_fat_mass",
  "skeletal_muscle_mass",
  "body_water_mass",
  "weight",
];
// Entity name without the "InBody" device prefix ("InBody Weight" -> "Weight").
function shortName(hass, entityId) {
  const st = hass && hass.states && hass.states[entityId];
  const name = (st && st.attributes && st.attributes.friendly_name) || "";
  const short = name.replace(/^\s*InBody\s+/i, "").trim();
  return short || undefined;
}

// Graph line colours, the same palette as the composition map; weight is red.
const SERIES_COLORS = {
  weight: "#e53935",
  body_water_mass: "#1e88e5",
  body_water_percentage: "#1e88e5",
  skeletal_muscle_mass: "#43a047",
  skeletal_muscle_percentage: "#43a047",
  body_fat_mass: "#fb8c00",
  body_fat_percentage: "#fb8c00",
};
const BODY_TYPES = ["male", "female"];
// Original, simple silhouettes (union of rounded shapes used as a clip path).
const SILHOUETTES = {
  male: {
    parts: '<path d="M208.0 42.4L207.6 46.8L206.6 51.0L204.9 55.1L202.6 58.8L199.8 62.2L196.4 65.0L192.7 67.3L188.6 69.0L184.4 70.0L180.0 70.4L175.6 70.0L171.4 69.0L167.3 67.3L163.6 65.0L160.2 62.2L157.4 58.8L155.1 55.1L153.4 51.0L152.4 46.8L152.0 42.4L152.4 38.0L153.4 33.8L155.1 29.7L157.4 26.0L160.2 22.6L163.6 19.8L167.3 17.5L171.4 15.8L175.6 14.8L180.0 14.4L184.4 14.8L188.6 15.8L192.7 17.5L196.4 19.8L199.8 22.6L202.6 26.0L204.9 29.7L206.6 33.8L207.6 38.0Z"/><path d="M108.4 113.0L108.8 107.4L110.1 102.0L112.2 96.9L115.2 92.1L118.8 87.9L123.0 84.3L127.8 81.3L132.9 79.2L138.3 77.9L143.9 77.5L216.1 77.5L221.7 77.9L227.1 79.2L232.2 81.3L237.0 84.3L241.2 87.9L244.8 92.1L247.8 96.9L249.9 102.0L251.2 107.4L251.6 113.0L251.6 132.2L108.4 132.2Z"/><path d="M108.4 115.5L136.4 115.5L136.4 205.1L136.2 207.3L135.7 209.4L134.8 211.4L133.7 213.3L132.3 215.0L130.6 216.4L128.7 217.5L126.7 218.4L124.6 218.9L122.4 219.1L122.4 219.1L120.2 218.9L118.0 218.4L116.0 217.5L114.1 216.4L112.5 215.0L111.0 213.3L109.9 211.4L109.1 209.4L108.5 207.3L108.4 205.1Z"/><path d="M223.6 115.5L251.6 115.5L251.6 205.1L251.5 207.3L250.9 209.4L250.1 211.4L249.0 213.3L247.5 215.0L245.9 216.4L244.0 217.5L242.0 218.4L239.8 218.9L237.6 219.1L237.6 219.1L235.4 218.9L233.3 218.4L231.3 217.5L229.4 216.4L227.7 215.0L226.3 213.3L225.2 211.4L224.3 209.4L223.8 207.3L223.6 205.1Z"/><path d="M144.3 77.5L215.3 77.5L215.3 224.1L144.3 224.1Z"/><path d="M144.3 219.1L176.0 219.1L176.0 331.8L175.9 333.2L175.6 334.7L175.0 336.0L174.3 337.2L173.3 338.3L172.2 339.2L171.0 340.0L169.7 340.6L168.3 340.9L166.8 341.0L160.2 341.0L157.7 340.8L155.3 340.2L153.0 339.3L150.8 338.0L148.9 336.4L147.3 334.5L146.0 332.3L145.1 330.0L144.5 327.6L144.3 325.1Z"/><path d="M183.5 219.1L215.3 219.1L215.3 325.1L215.1 327.6L214.5 330.0L213.6 332.3L212.3 334.5L210.6 336.4L208.7 338.0L206.6 339.3L204.3 340.2L201.9 340.8L199.4 341.0L192.7 341.0L191.3 340.9L189.9 340.6L188.6 340.0L187.3 339.2L186.2 338.3L185.3 337.2L184.6 336.0L184.0 334.7L183.7 333.2L183.5 331.8Z"/>',
    edge: [null,163.2,157.0,154.0,152.2,152.0,153.0,155.5,160.0,169.0,null,130.5,121.0,115.0,111.5,109.5,108.5,108.2,108.2,108.2,108.2,108.2,108.2,108.2,108.2,108.2,108.2,108.2,108.2,108.2,108.2,108.2,108.2,110.2,117.2,144.2,144.2,144.2,144.2,144.2,144.2,144.2,144.2,144.2,144.2,144.2,144.2,144.2,144.2,144.2,144.2,144.2,144.2,146.0,151.0],
  },
  female: {
    parts: '<path d="M208.0 42.4L207.6 46.8L206.6 51.0L204.9 55.1L202.6 58.8L199.8 62.2L196.4 65.0L192.7 67.3L188.6 69.0L184.4 70.0L180.0 70.4L175.6 70.0L171.4 69.0L167.3 67.3L163.6 65.0L160.2 62.2L157.4 58.8L155.1 55.1L153.4 51.0L152.4 46.8L152.0 42.4L152.4 38.0L153.4 33.8L155.1 29.7L157.4 26.0L160.2 22.6L163.6 19.8L167.3 17.5L171.4 15.8L175.6 14.8L180.0 14.4L184.4 14.8L188.6 15.8L192.7 17.5L196.4 19.8L199.8 22.6L202.6 26.0L204.9 29.7L206.6 33.8L207.6 38.0Z"/><path d="M119.7 113.0L120.1 107.4L121.4 102.0L123.5 96.9L126.4 92.1L130.1 87.9L134.3 84.3L139.0 81.3L144.2 79.2L149.6 77.9L155.2 77.5L205.3 77.5L210.8 77.9L216.2 79.2L221.4 81.3L226.1 84.3L230.4 87.9L234.0 92.1L236.9 96.9L239.0 102.0L240.3 107.4L240.8 113.0L240.8 130.1L119.7 130.1Z"/><path d="M151.0 123.8L209.0 123.8L242.0 248.3L118.0 248.3Z"/><path d="M121.7 98.8L144.7 128.0L122.2 205.7L94.2 200.3Z"/><path d="M122.4 203.0L122.2 205.2L121.7 207.4L120.8 209.4L119.7 211.3L118.2 213.0L116.5 214.5L114.6 215.6L112.6 216.5L110.4 217.0L108.2 217.2L105.9 217.0L103.8 216.5L101.7 215.6L99.8 214.5L98.1 213.0L96.7 211.3L95.5 209.4L94.7 207.4L94.1 205.2L94.0 203.0L94.1 200.8L94.7 198.6L95.5 196.5L96.7 194.6L98.1 192.9L99.8 191.5L101.7 190.3L103.8 189.5L105.9 189.0L108.2 188.8L110.4 189.0L112.6 189.5L114.6 190.3L116.5 191.5L118.2 192.9L119.7 194.6L120.8 196.5L121.7 198.6L122.2 200.8Z"/><path d="M265.8 200.3L237.8 205.7L215.3 128.0L238.3 98.8Z"/><path d="M237.8 200.8L238.3 198.6L239.2 196.5L240.3 194.6L241.8 192.9L243.5 191.5L245.4 190.3L247.4 189.5L249.6 189.0L251.8 188.8L254.1 189.0L256.2 189.5L258.3 190.3L260.2 191.5L261.9 192.9L263.3 194.6L264.5 196.5L265.3 198.6L265.9 200.8L266.0 203.0L265.9 205.2L265.3 207.4L264.5 209.4L263.3 211.3L261.9 213.0L260.2 214.5L258.3 215.6L256.2 216.5L254.1 217.0L251.8 217.2L249.6 217.0L247.4 216.5L245.4 215.6L243.5 214.5L241.8 213.0L240.3 211.3L239.2 209.4L238.3 207.4L237.8 205.2L237.6 203.0Z"/><path d="M144.7 247.0L176.0 247.0L176.0 331.8L175.9 333.2L175.6 334.7L175.0 336.0L174.3 337.2L173.3 338.3L172.2 339.2L171.0 340.0L169.7 340.6L168.3 340.9L166.8 341.0L160.6 341.0L158.1 340.8L155.7 340.2L153.4 339.3L151.3 338.0L149.4 336.4L147.7 334.5L146.4 332.3L145.5 330.0L144.9 327.6L144.7 325.1Z"/><path d="M183.5 247.0L215.7 247.0L215.7 325.1L215.5 327.6L214.9 330.0L214.0 332.3L212.7 334.5L211.1 336.4L209.2 338.0L207.0 339.3L204.7 340.2L202.3 340.8L199.8 341.0L192.7 341.0L191.3 340.9L189.9 340.6L188.6 340.0L187.3 339.2L186.2 338.3L185.3 337.2L184.6 336.0L184.0 334.7L183.7 333.2L183.5 331.8Z"/>',
    edge: [null,163.2,157.0,154.0,152.2,152.0,153.0,155.5,160.0,169.0,null,141.8,132.2,126.2,123.0,120.0,118.5,116.8,115.2,113.5,112.0,110.2,108.8,107.0,105.5,103.8,102.2,100.5,99.0,97.2,95.8,94.0,94.2,97.2,125.8,124.2,122.5,121.0,119.5,117.8,144.5,144.5,144.5,144.5,144.5,144.5,144.5,144.5,144.5,144.5,144.5,144.5,144.5,146.2,151.5],
  },
};
const EDGE_STEP = 6; // `edge[i]` = leftmost x of the figure at y = FIGURE_TOP + EDGE_STEP * i
const FIGURE_TOP = 14;
const FIGURE_BOTTOM = 341;
// Pictogram-style figures: round head, block shoulders, arms separated from the
// body by a narrow gap. The head is part of the clip, so the bands run from
// the top of the head. The right edge is the mirror image of the left one.
const silhouetteParts = (fig) => fig.parts;
const silhouetteEdge = (fig, cy) => {
  const i = Math.max(0, Math.min(fig.edge.length - 1, Math.round((cy - FIGURE_TOP) / EDGE_STEP)));
  return fig.edge[i] === null ? 150 : fig.edge[i];
};
const DEFAULT_PERIOD = "month";
const DEFAULT_DAYS = 365;

const STRINGS = {
  mass: "Weight",
  percentage: "Percentage",
  composition: "Composition",
  quadrant: "Quadrant",
  last_scan: "Last weigh-in",
  nav_first: "First weigh-in",
  nav_prev: "Previous weigh-in",
  nav_next: "Next weigh-in",
  nav_last: "Latest weigh-in",
  quad_empty: "The quadrant needs the BMI and body fat percentage sensors.",
  quad_label: "Body type quadrant: BMI against percent body fat",
  quad_bmi: "BMI",
  quad_pbf: "Percent Body Fat",
  quad_body_fat: "Body fat",
  muscle: "Skeletal muscle",
  fat: "Body fat",
  map_note: "Band heights are proportional to the three values; body water overlaps muscle and fat.",
  body_type: "Body type",
  male: "Male",
  female: "Female",
  water: "Body water",
  weight: "Weight",
  map_label: "Body composition map",
  map_empty: "The body composition map needs the body water, skeletal muscle and body fat percentage sensors.",
  empty:
    "No sensors found. Check that the integration is set up, or list the entities in the card options (mass_entities / percentage_entities).",
};

// ---- quadrant ("body type"): BMI against percent body fat ---------------------
// A 4x4 grid of equal cells. Columns: body fat < 10, 10-15, 15-20, >= 20 %.
// Rows (top to bottom): BMI >= 25, 21.75-25, 18.5-21.75, < 18.5.
const Q_PBF_MIN = 5;
const Q_PBF_MAX = 25;
const Q_BMI_MIN = 15.25;
const Q_BMI_MAX = 28.25;
const Q_PBF_CUTS = [10, 15, 20];
const Q_BMI_CUTS = [25, 21.75, 18.5];
// [name, first column, first row, columns, rows]
const Q_REGIONS = [
  ["Athletic", 0, 0, 2, 1],
  ["Overweight", 2, 0, 1, 1],
  ["Obesity", 3, 0, 1, 1],
  ["Muscular", 0, 1, 2, 1],
  ["Average", 2, 1, 1, 2],
  ["Mild Obesity", 3, 1, 1, 1],
  ["Slim Muscular", 0, 2, 1, 1],
  ["Slim", 1, 2, 1, 1],
  ["Sarcopenic Obesity", 3, 2, 1, 2],
  ["Thin", 0, 3, 1, 1],
  ["Slightly Thin", 1, 3, 2, 1],
];

// Region of the quadrant for a body fat percentage and a BMI.
function classifyQuadrant(pbf, bmi) {
  const col = Q_PBF_CUTS.filter((c) => pbf >= c).length;
  const row = Q_BMI_CUTS.filter((c) => bmi < c).length;
  const hit = Q_REGIONS.find(([, c, r, w, h]) => col >= c && col < c + w && row >= r && row < r + h);
  return hit ? hit[0] : null;
}

const CSS = `
  :host { display: block; }
  ha-card { display: block; overflow: hidden; }
  .title {
    padding: 16px 16px 0;
    font-size: var(--ha-card-header-font-size, 24px);
    line-height: 32px;
    color: var(--ha-card-header-color, var(--primary-text-color));
  }
  .lastscan { padding: 12px 16px 0; font-size: 13px; color: var(--secondary-text-color); }
  .lastscan b { font-weight: 600; color: var(--primary-text-color); }
  .lastscan.warn, .lastscan.warn b { color: #fb8c00; }
  .lastscan.alert, .lastscan.alert b { color: #e53935; }
  .nav { display: flex; align-items: center; justify-content: center; gap: 4px; padding: 0 12px 12px; }
  .nav[hidden] { display: none; }
  .nav button {
    border: none; background: none; cursor: pointer; font: inherit; font-size: 20px; line-height: 1;
    width: 36px; height: 36px; border-radius: 50%; color: var(--primary-text-color);
  }
  .nav button:hover:not([disabled]) { background: var(--secondary-background-color, rgba(127,127,127,.15)); }
  .nav button:focus-visible { outline: 2px solid var(--primary-color); }
  .nav button[disabled] { opacity: .3; cursor: default; }
  .nav .navlabel { min-width: 170px; text-align: center; font-size: 13px; color: var(--secondary-text-color); }
  .nav .navlabel b { color: var(--primary-text-color); font-weight: 600; }
  .nav.past .navlabel, .nav.past .navlabel b { color: var(--primary-color); }
  .tabs { display: flex; border-bottom: 1px solid var(--divider-color); }
  .tab {
    flex: 1;
    padding: 12px 8px;
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    color: var(--secondary-text-color);
    font: inherit;
    font-weight: 500;
    cursor: pointer;
  }
  .tab[aria-selected="true"] {
    color: var(--primary-color);
    border-bottom-color: var(--primary-color);
  }
  .tab:focus-visible { outline: 2px solid var(--primary-color); outline-offset: -2px; }
  .panel {
    --ha-card-box-shadow: none;
    --ha-card-border-width: 0;
    --ha-card-background: transparent;
    --ha-card-border-radius: 0;
  }
  .panel[hidden] { display: none; }
  .empty { padding: 16px; color: var(--secondary-text-color); }
  .comp {
    --ib-water: #1e88e5;
    --ib-muscle: #43a047;
    --ib-fat: #fb8c00;
    padding: 8px 16px 16px;
  }
  .comp svg { display: block; width: 100%; max-width: 420px; margin: 0 auto; height: auto; }
  .comp .name { font-size: 11px; fill: var(--secondary-text-color); }
  .comp .value { font-size: 13px; font-weight: 600; fill: var(--primary-text-color); }
  .comp .extra {
    display: flex; justify-content: center; gap: 24px; flex-wrap: wrap;
    margin-top: 8px; color: var(--secondary-text-color); font-size: 13px;
  }
  .quad { --ib-fat: #fb8c00; padding: 8px 16px 16px; text-align: center; }
  .quad svg { display: block; width: 100%; max-width: 420px; margin: 0 auto; height: auto; }
  .quad .cell { fill: var(--secondary-background-color, #f0f1f5); stroke: var(--card-background-color, #fff); stroke-width: 2; }
  .quad .cell.on { fill: var(--ib-fat); fill-opacity: 0.28; }
  .quad .rname { font-size: 10.5px; font-weight: 600; fill: var(--secondary-text-color); }
  .quad .rname.on { fill: var(--primary-text-color); }
  .quad .tick { font-size: 11px; fill: var(--secondary-text-color); }
  .quad .axis { font-size: 11px; font-weight: 600; fill: var(--secondary-text-color); }
  .quad .dot { fill: var(--ib-fat); stroke: var(--card-background-color, #fff); stroke-width: 3; }
  .quad .summary { margin-top: 8px; color: var(--secondary-text-color); font-size: 13px; }
  .quad .summary b { color: var(--primary-text-color); font-weight: 600; }
  .comp .extra b { color: var(--primary-text-color); font-weight: 600; }
  .comp .note { margin: 8px 0 0; text-align: center; font-size: 11px; color: var(--secondary-text-color); }
`;

// InBody sensors in the entity registry, grouped by translation_key.
function scanSensors(hass, deviceId) {
  const entities = (hass && hass.entities) || {};
  const byKey = {};
  for (const [entityId, ent] of Object.entries(entities)) {
    if (ent.platform !== DOMAIN || ent.hidden) continue;
    if (deviceId && ent.device_id !== deviceId) continue;
    if (!ent.translation_key) continue;
    (byKey[ent.translation_key] ||= []).push(entityId);
  }
  for (const ids of Object.values(byKey)) ids.sort();
  return byKey;
}

// InBody sensors found in the entity registry, per tab, in display order.
function discoverSensors(hass, deviceId) {
  const byKey = scanSensors(hass, deviceId);
  const pick = (keys) => keys.flatMap((k) => byKey[k] || []);
  return {
    mass: pick(MASS_KEYS),
    percentage: pick(PERCENTAGE_KEYS),
    composition: COMPOSITION_KEYS.flatMap((k) => (byKey[k] || []).slice(0, 1)),
    quadrant: ["bmi", "body_fat_percentage"].flatMap((k) => (byKey[k] || []).slice(0, 1)),
  };
}

function el(tag, props = {}, text) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") node.className = v;
    else node.setAttribute(k, v);
  }
  if (text !== undefined) node.textContent = text;
  return node;
}

// Date in the user's language, e.g. "Oct 15, 2026".
function fmtDate(hass, when) {
  const lang = (hass && ((hass.locale && hass.locale.language) || hass.language)) || "en";
  try {
    return when.toLocaleDateString(lang, { year: "numeric", month: "short", day: "numeric" });
  } catch (e) {
    return when.toLocaleDateString();
  }
}

// How long ago a date was, in words ("today", "3 days ago", "2 weeks ago").
function ago(days) {
  const n = Math.floor(days);
  const plural = (v, unit) => `${v} ${unit}${v === 1 ? "" : "s"} ago`;
  if (n < 1) return "today";
  if (n === 1) return "yesterday";
  if (n < 14) return plural(n, "day");
  if (n < 60) return plural(Math.floor(n / 7), "week");
  if (n < 730) return plural(Math.floor(n / 30.44), "month");
  return plural(Math.floor(n / 365.25), "year");
}

class HaInbodyCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = null;
    this._hass = null;
    this._sig = null;
    this._lists = { mass: [], percentage: [], composition: [], quadrant: [] };
    this._active = "mass";
    this._visible = TABS;
    this._inner = {};
    this._panels = {};
    this._buttons = {};
    this._gen = 0;
    this._lastEl = null;
    this._bodies = {};
    this._navs = {};
    this._scans = null; // every weigh-in, oldest first: [{ t: Date, values }]
    this._pos = null; // null = the latest one (live sensors), else an index in _scans
    this._scansFor = null;
    this._scansBusy = false;
    this._scansWanted = false;
  }

  // ---- Lovelace card API -------------------------------------------------

  static getStubConfig() {
    return {};
  }

  static getConfigElement() {
    return document.createElement(EDITOR_TAG);
  }

  setConfig(config) {
    if (!config || typeof config !== "object") {
      throw new Error("Invalid configuration");
    }
    for (const key of ["mass_entities", "percentage_entities"]) {
      if (config[key] !== undefined && !Array.isArray(config[key])) {
        throw new Error(`${key} must be a list of entity ids`);
      }
    }
    if (config.tabs !== undefined) {
      if (!Array.isArray(config.tabs) || config.tabs.some((t) => !TABS.includes(t))) {
        throw new Error("tabs must be a list with mass, percentage and/or composition");
      }
    }
    if (config.body_type !== undefined && !BODY_TYPES.includes(config.body_type)) {
      throw new Error("body_type must be male or female");
    }
    this._config = { period: DEFAULT_PERIOD, days_to_show: DEFAULT_DAYS, show_graph: true, ...config };
    // an empty list is treated as "show both"
    const wanted = Array.isArray(config.tabs) && config.tabs.length ? config.tabs : TABS;
    this._visible = TABS.filter((t) => wanted.includes(t));
    this._active = this._visible.includes(config.default_tab) ? config.default_tab : this._visible[0];
    this._sig = null; // force a rebuild
    this._sync();
  }

  set hass(hass) {
    this._hass = hass;
    this._sync();
  }

  getCardSize() {
    return 6;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: 6 };
  }

  // ---- internals ---------------------------------------------------------

  _t(key) {
    return STRINGS[key];
  }

  _discover() {
    return discoverSensors(this._hass, this._config.device_id);
  }

  _computeLists() {
    const found = this._discover();
    return {
      mass: this._config.mass_entities || found.mass,
      percentage: this._config.percentage_entities || found.percentage,
      composition: found.composition,
      quadrant: found.quadrant,
    };
  }

  // Rebuild only when something that affects the layout changed.
  _sync() {
    if (!this._config || !this._hass) return;
    const lists = this._computeLists();
    const sig = JSON.stringify([lists, this._visible]);
    if (sig !== this._sig) {
      this._sig = sig;
      this._lists = lists;
      this._build();
    }
    for (const card of Object.values(this._inner)) card.hass = this._hass;
    this._renderLastScan();
    if (this._scansWanted) this._loadScans();
    if (this._panels.composition) this._renderComposition();
    if (this._panels.quadrant) this._renderQuadrant();
    this._renderNav();
  }

  // First line under the tabs, shown on every tab: date of the last weigh-in, orange
  // after more than a week and red after more than a month.
  _renderLastScan() {
    const line = this._lastEl;
    if (!line) return;
    const id = (scanSensors(this._hass, this._config.device_id).last_scan || [])[0];
    const st = id && this._hass.states && this._hass.states[id];
    const when = st ? new Date(st.state) : null;
    if (!when || Number.isNaN(when.getTime())) {
      line.hidden = true;
      return;
    }
    const days = (Date.now() - when.getTime()) / 86400000;
    const date = fmtDate(this._hass, when);
    line.hidden = false;
    line.className = `lastscan${days > 30 ? " alert" : days > 7 ? " warn" : ""}`;
    line.textContent = "";
    line.append(`${this._t("last_scan")}: `, el("b", {}, date), ` · ${ago(days)}`);
  }

  _build() {
    this._gen += 1;
    this._inner = {};
    this._panels = {};
    this._buttons = {};
    this._bodies = {};
    this._navs = {};
    this._compSig = null;
    this._quadSig = null;

    const root = this.shadowRoot;
    root.textContent = "";
    root.appendChild(el("style", {}, CSS));

    const card = el("ha-card");
    if (this._config.title) card.appendChild(el("div", { class: "title" }, this._config.title));

    const tablist = el("div", { class: "tabs", role: "tablist" });
    for (const name of this._visible) {
      const btn = el("button", { class: "tab", role: "tab", type: "button", "data-tab": name }, this._t(name));
      btn.addEventListener("click", () => this._select(name));
      btn.addEventListener("keydown", (ev) => this._onKey(ev, name));
      this._buttons[name] = btn;
      tablist.appendChild(btn);
    }
    // with a single tab there is nothing to switch between
    if (this._visible.length > 1) card.appendChild(tablist);

    // first line under the tabs
    this._lastEl = el("div", { class: "lastscan" });
    this._lastEl.hidden = true;
    card.appendChild(this._lastEl);

    for (const name of this._visible) {
      const panel = el("div", { class: "panel", role: "tabpanel", "data-tab": name });
      if (!this._lists[name].length && name !== "composition" && name !== "quadrant") panel.appendChild(el("div", { class: "empty" }, this._t("empty")));
      if (name === "composition" || name === "quadrant") {
        // content on top, the weigh-in navigation as the last line
        const body = el("div", { class: "body" });
        const nav = this._makeNav();
        panel.append(body, nav);
        this._bodies[name] = body;
        this._navs[name] = nav;
      }
      this._panels[name] = panel;
      card.appendChild(panel);
    }
    root.appendChild(card);
    this._select(this._active);
    this._renderLastScan();
    this._renderNav();
  }

  // ---- weigh-in history (Composition and Quadrant tabs) ------------------

  _makeNav() {
    const nav = el("div", { class: "nav", role: "group" });
    nav.hidden = true;
    const btn = (cls, label, glyph, action) => {
      const b = el("button", { class: cls, type: "button", "aria-label": this._t(label), title: this._t(label) }, glyph);
      b.addEventListener("click", action);
      return b;
    };
    nav.append(
      btn("first", "nav_first", "«", () => this._go("first")),
      btn("prev", "nav_prev", "‹", () => this._go("prev")),
      el("span", { class: "navlabel", "aria-live": "polite" }),
      btn("next", "nav_next", "›", () => this._go("next")),
      btn("last", "nav_last", "»", () => this._go("last"))
    );
    return nav;
  }

  _go(where) {
    const n = this._scans ? this._scans.length : 0;
    if (n < 2) return;
    const cur = this._pos === null ? n - 1 : this._pos;
    let next = cur;
    if (where === "first") next = 0;
    else if (where === "prev") next = Math.max(0, cur - 1);
    else if (where === "next") next = Math.min(n - 1, cur + 1);
    else if (where === "last") next = n - 1;
    this._pos = next >= n - 1 ? null : next;
    this._compSig = null;
    this._quadSig = null;
    if (this._panels.composition) this._renderComposition();
    if (this._panels.quadrant) this._renderQuadrant();
    this._renderNav();
  }

  _renderNav() {
    const n = this._scans ? this._scans.length : 0;
    const cur = this._pos === null ? n - 1 : this._pos;
    for (const nav of Object.values(this._navs)) {
      nav.hidden = n < 2;
      if (n < 2) continue;
      const when = this._scans[cur].t;
      const label = nav.querySelector(".navlabel");
      label.textContent = "";
      label.append(el("b", {}, fmtDate(this._hass, when)), ` · ${cur + 1} / ${n}`);
      nav.classList.toggle("past", this._pos !== null);
      nav.querySelector(".first").disabled = cur === 0;
      nav.querySelector(".prev").disabled = cur === 0;
      nav.querySelector(".next").disabled = cur === n - 1;
      nav.querySelector(".last").disabled = cur === n - 1;
    }
  }

  // Loads every weigh-in from the integration (once per new scan).
  async _loadScans() {
    const hass = this._hass;
    if (!hass || this._scansBusy || typeof hass.callWS !== "function") return;
    const sig = this._lastScanState();
    if (this._scansFor === sig) return;
    this._scansFor = sig;
    this._scansBusy = true;
    try {
      const msg = { type: `${DOMAIN}/scans` };
      if (this._config.device_id) msg.device_id = this._config.device_id;
      const res = await hass.callWS(msg);
      const scans = ((res && res.scans) || [])
        .map((s) => ({ t: new Date(s.taken_at), values: s.values || {} }))
        .filter((s) => !Number.isNaN(s.t.getTime()))
        .sort((a, b) => a.t - b.t);
      this._scans = scans.length ? scans : null;
    } catch (e) {
      this._scans = null;
    } finally {
      this._scansBusy = false;
    }
    this._pos = null;
    this._compSig = null;
    this._quadSig = null;
    if (this._panels.composition) this._renderComposition();
    if (this._panels.quadrant) this._renderQuadrant();
    this._renderNav();
  }

  _lastScanState() {
    const id = (scanSensors(this._hass, this._config.device_id).last_scan || [])[0];
    const st = id && this._hass.states && this._hass.states[id];
    return st ? String(st.state) : "";
  }

  // Values of the sensors, or of the weigh-in being browsed.
  _numbers(keys) {
    if (this._pos !== null && this._scans && this._scans[this._pos]) {
      const vals = this._scans[this._pos].values;
      return Object.fromEntries(keys.map((k) => [k, Number.isFinite(vals[k]) ? vals[k] : null]));
    }
    const by = scanSensors(this._hass, this._config.device_id);
    const states = this._hass.states || {};
    return Object.fromEntries(
      keys.map((k) => {
        const id = (by[k] || [])[0];
        const n = id && states[id] ? parseFloat(states[id].state) : NaN;
        return [k, Number.isFinite(n) ? n : null];
      })
    );
  }

  _onKey(ev, name) {
    if (ev.key !== "ArrowRight" && ev.key !== "ArrowLeft") return;
    ev.preventDefault();
    const tabs = this._visible;
    const idx = tabs.indexOf(name);
    const next = tabs[(idx + (ev.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length];
    this._select(next);
    this._buttons[next].focus();
  }

  _select(name) {
    this._active = name;
    for (const tab of this._visible) {
      const on = tab === name;
      this._buttons[tab].setAttribute("aria-selected", String(on));
      this._buttons[tab].tabIndex = on ? 0 : -1;
      this._panels[tab].hidden = !on;
    }
    this._ensure(name);
  }

  // Body map: the silhouette is cut into three bands (body water, skeletal
  // muscle, body fat) whose heights follow their relative values.
  _renderComposition() {
    const panel = this._bodies.composition;
    if (!panel || !this._hass) return;
    const v = this._numbers(COMPOSITION_KEYS);
    const type = this._config.body_type === "female" ? "female" : "male";
    const sig = JSON.stringify([v, type]);
    if (sig === this._compSig) return;
    this._compSig = sig;

    panel.textContent = "";
    if (
      v.body_water_percentage === null ||
      v.skeletal_muscle_percentage === null ||
      v.body_fat_percentage === null
    ) {
      panel.appendChild(el("div", { class: "empty" }, this._t("map_empty")));
      return;
    }
    const f1 = (n, unit) => (n === null ? "–" : `${n.toFixed(1)} ${unit}`);

    const shape = SILHOUETTES[type];
    const TOP = FIGURE_TOP;
    const BOTTOM = FIGURE_BOTTOM;
    const edgeLeft = (cy) => silhouetteEdge(shape, cy);
    const edgeRight = (cy) => 360 - silhouetteEdge(shape, cy);

    const bands = [
      { cls: "water", name: this._t("water"), pct: v.body_water_percentage, kg: v.body_water_mass, side: "L" },
      { cls: "muscle", name: this._t("muscle"), pct: v.skeletal_muscle_percentage, kg: v.skeletal_muscle_mass, side: "R" },
      { cls: "fat", name: this._t("fat"), pct: v.body_fat_percentage, kg: v.body_fat_mass, side: "L" },
    ];
    const total = bands.reduce((a, b) => a + Math.max(0, b.pct), 0) || 1;
    let y = TOP;
    for (const b of bands) {
      b.h = ((BOTTOM - TOP) * Math.max(0, b.pct)) / total;
      b.y = y;
      b.cy = y + b.h / 2;
      y += b.h;
    }
    // keep the two labels on the same side from overlapping
    bands[2].cy = Math.max(bands[2].cy, bands[0].cy + 34);

    const color = (cls) => `var(--ib-${cls})`;
    const rects = bands
      .map((b) => `<rect x="-24" y="${b.y.toFixed(1)}" width="408" height="${(b.h + 0.5).toFixed(1)}" fill="${color(b.cls)}"/>`)
      .join("");
    const labels = bands
      .map((b) => {
        const left = b.side === "L";
        const outer = left ? -20 : 380;
        const x1 = left ? edgeLeft(b.cy) - 5 : edgeRight(b.cy) + 5;
        const anchor = left ? "start" : "end";
        const text = `${b.pct.toFixed(1)} % · ${f1(b.kg, "kg")}`;
        return (
          `<line x1="${outer}" y1="${b.cy.toFixed(1)}" x2="${x1.toFixed(1)}" y2="${b.cy.toFixed(1)}" stroke="${color(b.cls)}" stroke-width="2"/>` +
          `<circle cx="${x1.toFixed(1)}" cy="${b.cy.toFixed(1)}" r="3" fill="${color(b.cls)}"/>` +
          `<text class="name" x="${outer}" y="${(b.cy - 19).toFixed(1)}" text-anchor="${anchor}">${b.name}</text>` +
          `<text class="value" x="${outer}" y="${(b.cy - 5).toFixed(1)}" text-anchor="${anchor}">${text}</text>`
        );
      })
      .join("");
    const svg =
      `<svg viewBox="-24 0 408 350" role="img" aria-label="${this._t("map_label")}" data-body="${type}">` +
      `<defs><clipPath id="body">${silhouetteParts(shape)}</clipPath></defs>` +
      `<g clip-path="url(#body)">${rects}</g>${labels}</svg>`;

    const wrap = el("div", { class: "comp" });
    wrap.innerHTML = svg;
    const extra = el("div", { class: "extra" });
    const weight = el("span");
    weight.append(`${this._t("weight")}: `, el("b", {}, f1(v.weight, "kg")));
    extra.appendChild(weight);
    wrap.appendChild(extra);
    wrap.appendChild(el("p", { class: "note" }, this._t("map_note")));
    panel.appendChild(wrap);
  }

  // Quadrant: where the latest BMI and body fat percentage fall in the grid.
  _renderQuadrant() {
    const panel = this._bodies.quadrant;
    if (!panel || !this._hass) return;
    const { bmi, body_fat_percentage: pbf } = this._numbers(["bmi", "body_fat_percentage"]);
    const sig = JSON.stringify([bmi, pbf]);
    if (sig === this._quadSig) return;
    this._quadSig = sig;

    panel.textContent = "";
    if (bmi === null || pbf === null) {
      panel.appendChild(el("div", { class: "empty" }, this._t("quad_empty")));
      return;
    }
    const X0 = 46;
    const Y0 = 6;
    const CELL = 75;
    const SIZE = CELL * 4;
    const current = classifyQuadrant(pbf, bmi);
    const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
    const px = (p) => X0 + ((clamp(p, Q_PBF_MIN, Q_PBF_MAX) - Q_PBF_MIN) / (Q_PBF_MAX - Q_PBF_MIN)) * SIZE;
    const py = (b) => Y0 + ((Q_BMI_MAX - clamp(b, Q_BMI_MIN, Q_BMI_MAX)) / (Q_BMI_MAX - Q_BMI_MIN)) * SIZE;

    const cells = Q_REGIONS.map(([name, c, r, w, h]) => {
      const x = X0 + c * CELL;
      const y = Y0 + r * CELL;
      const on = name === current;
      // wrap long names on word boundaries to fit the cell
      const maxChars = Math.max(6, Math.floor((w * CELL - 12) / 6.2));
      const lines = [];
      for (const word of name.split(" ")) {
        const last = lines[lines.length - 1];
        if (last !== undefined && `${last} ${word}`.length <= maxChars) lines[lines.length - 1] = `${last} ${word}`;
        else lines.push(word);
      }
      const text = lines
        .map((ln, i) => `<tspan x="${x + 7}" dy="${i ? 13 : 0}">${ln}</tspan>`)
        .join("");
      return (
        `<rect class="cell${on ? " on" : ""}" x="${x}" y="${y}" width="${w * CELL}" height="${h * CELL}"/>` +
        `<text class="rname${on ? " on" : ""}" x="${x + 7}" y="${y + 19}">${text}</text>`
      );
    }).join("");

    const xTicks = [10, 20]
      .map((p) => `<text class="tick" x="${px(p)}" y="${Y0 + SIZE + 17}" text-anchor="middle">${p.toFixed(1)}</text>`)
      .join("");
    const yTicks = [25, 18.5]
      .map((b) => `<text class="tick" transform="translate(${X0 - 8} ${py(b)}) rotate(-90)" text-anchor="middle">${b.toFixed(1)}</text>`)
      .join("");
    const svg =
      `<svg viewBox="0 0 360 352" role="img" aria-label="${this._t("quad_label")}" data-region="${current || ""}">` +
      `<defs><clipPath id="qclip"><rect x="${X0}" y="${Y0}" width="${SIZE}" height="${SIZE}" rx="16"/></clipPath></defs>` +
      `<g clip-path="url(#qclip)">${cells}</g>` +
      xTicks +
      yTicks +
      `<text class="axis" transform="translate(12 ${Y0 + 22}) rotate(-90)" text-anchor="end">${this._t("quad_bmi")}</text>` +
      `<text class="axis" x="${X0 + SIZE}" y="${Y0 + SIZE + 38}" text-anchor="end">${this._t("quad_pbf")}</text>` +
      `<circle class="dot" cx="${px(pbf).toFixed(1)}" cy="${py(bmi).toFixed(1)}" r="7"/>` +
      `</svg>`;

    const wrap = el("div", { class: "quad" });
    wrap.innerHTML = svg;
    const summary = el("div", { class: "summary" });
    summary.append(
      el("b", {}, current || "–"),
      ` · ${this._t("quad_bmi")} `,
      el("b", {}, bmi.toFixed(1)),
      ` · ${this._t("quad_body_fat")} `,
      el("b", {}, `${pbf.toFixed(1)} %`)
    );
    wrap.appendChild(summary);
    panel.appendChild(wrap);
  }

  // Inner cards are created lazily, when their tab is first shown, so charts
  // are never measured while hidden.
  async _ensure(name) {
    if (name === "composition" || name === "quadrant") {
      this._scansWanted = true;
      this._loadScans();
      if (name === "composition") this._renderComposition();
      else this._renderQuadrant();
      return;
    }
    if (this._inner[name] || !this._lists[name].length) return;
    const gen = this._gen;
    const entities = this._lists[name];
    const cards = [
      {
        type: "entities",
        entities: entities.map((entity) => {
          const name = shortName(this._hass, entity);
          return name ? { entity, name } : entity;
        }),
      },
    ];
    // Entities of this integration get the colour of their measurement.
    const registry = (this._hass && this._hass.entities) || {};
    const coloured = entities.map((entity) => {
      const reg = registry[entity] || {};
      const color = reg.platform === DOMAIN ? SERIES_COLORS[reg.translation_key] : undefined;
      const name = shortName(this._hass, entity);
      return color || name ? { entity, ...(color ? { color } : {}), ...(name ? { name } : {}) } : entity;
    });
    if (this._config.show_graph !== false) {
      cards.push({
        type: "statistics-graph",
        entities: coloured,
        stat_types: ["mean"],
        chart_type: "line",
        period: this._config.period,
        days_to_show: this._config.days_to_show,
      });
    }
    const helpers = await window.loadCardHelpers();
    if (gen !== this._gen || this._inner[name]) return; // rebuilt meanwhile
    const stack = helpers.createCardElement({ type: "vertical-stack", cards });
    stack.hass = this._hass;
    this._inner[name] = stack;
    this._panels[name].appendChild(stack);
  }
}

if (!customElements.get(TAG)) customElements.define(TAG, HaInbodyCard);

// ---- visual editor ----------------------------------------------------------

const PERIODS = ["5minute", "hour", "day", "week", "month"];

const EDITOR_STRINGS = {
  title: "Title",
  tabs: "Tabs to show",
  body_type: "Composition map figure",
  default_tab: "Starting tab",
  mass_entities: "Sensors in the Weight tab",
  percentage_entities: "Sensors in the Percentage tab",
  sensors_hint: "All sensors are checked by default. Uncheck the ones you do not want in each tab.",
  show_graph: "Show the graph",
  period: "Graph period",
  days_to_show: "Days shown in the graph",
  "period.5minute": "5 minutes",
  "period.hour": "Hour",
  "period.day": "Day",
  "period.week": "Week",
  "period.month": "Month",
};

class HaInbodyCardEditor extends HTMLElement {
  constructor() {
    super();
    this._config = {};
    this._hass = null;
    this._form = null;
  }

  setConfig(config) {
    this._config = { ...config };
    this._update();
  }

  set hass(hass) {
    this._hass = hass;
    this._update();
  }

  _t(key) {
    return EDITOR_STRINGS[key] || key;
  }

  _schema() {
    const tabLabel = (k) => STRINGS[k];
    // A checklist with every sensor the tab can show.
    const sensors = (name, tab) => ({
      name,
      selector: {
        select: {
          multiple: true,
          mode: "list",
          options: this._options(tab).map((value) => ({ value, label: this._name(value) })),
        },
      },
    });
    return [
      { name: "title", selector: { text: {} } },
      {
        name: "tabs",
        selector: {
          select: {
            multiple: true,
            mode: "list",
            options: TABS.map((value) => ({ value, label: tabLabel(value) })),
          },
        },
      },
      {
        name: "default_tab",
        selector: {
          select: {
            mode: "dropdown",
            options: TABS.map((value) => ({ value, label: tabLabel(value) })),
          },
        },
      },
      {
        name: "body_type",
        selector: {
          select: {
            mode: "dropdown",
            options: BODY_TYPES.map((value) => ({ value, label: STRINGS[value] })),
          },
        },
      },
      sensors("mass_entities", "mass"),
      sensors("percentage_entities", "percentage"),
      { name: "show_graph", selector: { boolean: {} } },
      {
        name: "period",
        selector: {
          select: {
            mode: "dropdown",
            options: PERIODS.map((value) => ({ value, label: this._t(`period.${value}`) })),
          },
        },
      },
      {
        name: "days_to_show",
        selector: { number: { min: 1, max: 3650, mode: "box", unit_of_measurement: "days" } },
      },
    ];
  }

  _name(entityId) {
    const st = this._hass && this._hass.states && this._hass.states[entityId];
    return shortName(this._hass, entityId) || (st && st.attributes && st.attributes.friendly_name) || entityId;
  }

  // Every candidate sensor of a tab: the detected ones, plus any sensor the
  // YAML already lists that was not detected (so it is never silently dropped).
  _options(tab) {
    const found = discoverSensors(this._hass, this._config.device_id)[tab];
    const listed = this._config[`${tab}_entities`] || [];
    return [...found, ...listed.filter((id) => !found.includes(id))];
  }

  // Values shown in the form: the card's effective defaults.
  _data() {
    const c = this._config;
    return {
      title: c.title || "",
      tabs: Array.isArray(c.tabs) && c.tabs.length ? c.tabs : [...TABS],
      default_tab: c.default_tab || "mass",
      body_type: c.body_type || "male",
      // everything is checked unless the config narrows it down
      mass_entities: c.mass_entities || this._options("mass"),
      percentage_entities: c.percentage_entities || this._options("percentage"),
      show_graph: c.show_graph !== false,
      period: c.period || DEFAULT_PERIOD,
      days_to_show: c.days_to_show || DEFAULT_DAYS,
    };
  }

  _update() {
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.addEventListener("value-changed", (ev) => this._changed(ev));
      const hint = document.createElement("p");
      hint.className = "hint";
      hint.style.cssText = "margin:8px 0 0;color:var(--secondary-text-color);font-size:12px";
      this._hint = hint;
      this.append(this._form, hint);
    }
    this._form.hass = this._hass;
    this._form.data = this._data();
    this._form.schema = this._schema();
    this._form.computeLabel = (item) => this._t(item.name);
    this._hint.textContent = this._t("sensors_hint");
  }

  _changed(ev) {
    ev.stopPropagation();
    const v = ev.detail.value || {};
    const config = { ...this._config, type: this._config.type || `custom:${TAG}` };
    // store only what differs from the defaults, so the YAML stays short
    const set = (key, value, isDefault) => {
      if (isDefault) delete config[key];
      else config[key] = value;
    };
    set("title", v.title, !v.title);
    const tabs = TABS.filter((t) => (v.tabs || []).includes(t));
    // at least one tab must stay on
    set("tabs", tabs, tabs.length === 0 || tabs.length === TABS.length);
    const visible = tabs.length ? tabs : TABS;
    set("default_tab", v.default_tab, !v.default_tab || v.default_tab === "mass" || !visible.includes(v.default_tab));
    set("body_type", v.body_type, !v.body_type || v.body_type === "male");
    // Checked sensors are stored only when they are a subset of the candidates;
    // all checked (or none) means "everything", the default.
    for (const tab of SENSOR_TABS) {
      const key = `${tab}_entities`;
      const options = this._options(tab);
      const chosen = options.filter((id) => (v[key] || []).includes(id));
      set(key, chosen, chosen.length === 0 || chosen.length === options.length);
    }
    set("show_graph", v.show_graph, v.show_graph !== false);
    set("period", v.period, !v.period || v.period === DEFAULT_PERIOD);
    const days = Number(v.days_to_show);
    set("days_to_show", days, !(days >= 1) || days === DEFAULT_DAYS);
    this._emit(config);
  }

  _emit(config) {
    this._config = config;
    this.dispatchEvent(
      new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true })
    );
  }
}

if (!customElements.get(EDITOR_TAG)) customElements.define(EDITOR_TAG, HaInbodyCardEditor);

window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === TAG)) {
  window.customCards.push({
    type: TAG,
    name: "HA InBody",
    description: "Body composition with tabs for weight (kg), percentage (%), a body composition map and a BMI / body fat quadrant.",
    documentationURL: "https://github.com/jacardbr/ha-inbody",
  });
}
