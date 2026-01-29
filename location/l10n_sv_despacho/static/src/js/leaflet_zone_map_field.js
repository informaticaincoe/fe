/** @odoo-module **/

import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, onMounted, onWillUnmount, onWillUpdateProps, useRef, xml } from "@odoo/owl";
import { loadJS, loadCSS } from "@web/core/assets";

let GEOJSON_CACHE = null;

async function getGeoJson() {
  if (GEOJSON_CACHE) return GEOJSON_CACHE;

  const url = "/l10n_sv_despacho/static/data/slv_admin2.geojson";
  const res = await fetch(url, {
    cache: "no-store",
    credentials: "same-origin",
  });

  const ct = (res.headers.get("content-type") || "").toLowerCase();
  if (!res.ok || ct.includes("text/html")) {
    const text = await res.text();
    throw new Error(
      `GeoJSON devolvió HTML o error. status=${res.status} url_final=${res.url} head=${text.slice(0, 80)}`
    );
  }

  GEOJSON_CACHE = await res.json();
  return GEOJSON_CACHE;
}


export class LeafletZoneMapField extends Component {
  static props = { ...standardFieldProps };
  static template = xml`
    <div class="o_leaflet_zone_map" style="width:100%; height:520px; border:1px solid #ddd; border-radius:8px; overflow:hidden;">
      <div t-ref="map" style="width:100%; height:100%;"></div>
    </div>
  `;

  setup() {
    this.mapRef = useRef("map");
    this.map = null;
    this.layer = null;

    onMounted(async () => {
      // Carga Leaflet (CDN). Si prefieres local, te digo cómo abajo.
      await loadCSS("https://unpkg.com/leaflet@1.9.4/dist/leaflet.css");
      await loadJS("https://unpkg.com/leaflet@1.9.4/dist/leaflet.js");

      // base path para soportar /web o /odoo/web (reverse proxy)
      const base = window.location.pathname.split("/web")[0] || "";

      // eslint-disable-next-line no-undef
      this.map = L.map(this.mapRef.el, { zoomControl: true }).setView([13.7, -88.9], 8);

      // eslint-disable-next-line no-undef
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: "&copy; OpenStreetMap contributors",
      }).addTo(this.map);

      // Si está dentro de notebook/tab, ayuda a que Leaflet calcule tamaño
      setTimeout(() => this.map.invalidateSize(true), 250);

      // Render inicial
      await this._renderGeofence(base);

      // Re-invalidate al cambiar de pestaña (bootstrap tabs)
      const notebook = this.mapRef.el.closest(".o_notebook");
      if (notebook) {
        notebook.addEventListener("shown.bs.tab", () => {
          setTimeout(() => this.map && this.map.invalidateSize(true), 50);
        });
      }
    });

    onWillUpdateProps(async () => {
      if (!this.map) return;
      const base = window.location.pathname.split("/web")[0] || "";
      await this._renderGeofence(base);
    });

    onWillUnmount(() => {
      if (this.map) this.map.remove();
      this.map = null;
      this.layer = null;
    });
  }

  _getSelectedList() {
    const data = this.props.record?.data || {};
    const raw = data.selected_munic_pcdes_json || "[]";
    try {
      const arr = JSON.parse(raw);
      return Array.isArray(arr) ? arr : [];
    } catch {
      return [];
    }
  }

  async _renderGeofence(base) {
  // 1) lee lo que viene desde Odoo
  const selectedList = this._getSelectedList();
  console.log("selected raw json:", this.props.record?.data?.selected_munic_pcdes_json);
  console.log("selected parsed:", selectedList);

  // 2) normaliza a string para evitar problemas de tipos
  const selected = new Set((selectedList || []).map(String));

  // 3) carga el GeoJSON
  const geo = await getGeoJson();
  console.log("geo features total:", geo.features?.length || 0);

  // 4) mira propiedades reales del GeoJSON (solo para confirmar llaves)
  const sampleProps = geo.features?.[0]?.properties || {};
  console.log("GeoJSON keys:", Object.keys(sampleProps));
  console.log("Sample adm2_pcode:", sampleProps.adm2_pcode, "Sample adm2_name:", sampleProps.adm2_name);

  // Limpia capa anterior
  if (this.layer) {
    this.layer.remove();
    this.layer = null;
  }

  // 5) filtra features
  const features = (geo.features || []).filter((f) => {
    const p = f.properties || {};
    const pcode = p.adm2_pcode != null ? String(p.adm2_pcode) : "";
    const name  = p.adm2_name  != null ? String(p.adm2_name)  : "";
    return selected.has(pcode) || selected.has(name);
  });

  console.log("matched features:", features.length);

  // Si no hay match, salimos
  if (!features.length) return;

  const fc = { type: "FeatureCollection", features };

  // 6) estilo visible (para debug)
  // eslint-disable-next-line no-undef
  this.layer = L.geoJSON(fc, {
    style: () => ({
      color: "#714B67",
      weight: 3,
      opacity: 1,
      fillColor: "#714B67",
      fillOpacity: 0.35,
    }),
  }).addTo(this.map);

  const bounds = this.layer.getBounds();
  if (bounds && bounds.isValid()) {
    this.map.fitBounds(bounds, { padding: [12, 12] });
  }
}

}

console.log("✅ Leaflet widget JS cargado");


registry.category("fields").add("leaflet_zone_map", {
  component: LeafletZoneMapField,
  supportedTypes: ["char"],
});

