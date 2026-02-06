/** @odoo-module **/
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, onMounted, useRef, onWillUpdateProps } from "@odoo/owl";

export class MapDistrictsComponent extends Component {
  static template = "l10n_sv_despacho.MapContainer";
  static props = { ...standardFieldProps };

  setup() {
    this.mapRef = useRef("map");
    this.rootRef = useRef("root");
    this.map = null;

    this.districtsLayer = null; // capa para distritos actuales
    this.previousLayer = null;  // capa para municipios anteriores

    onWillUpdateProps((nextProps) => {
      if (this.districtsLayer && this.previousLayer) {
        this._applyStyles(nextProps);
      }
    });

    onMounted(async () => {
      if (this.el) {
        this.rootRef.el.style.width = "100vw";
        this.rootRef.el.style.display = "block";
      }

      await this._loadGoogleAPI();
      this._initMap();
    });
  }

  async _loadGoogleAPI() {
    if (window.google) return;
    return new Promise((resolve) => {
      const script = document.createElement("script");
      script.src =
        "https://maps.googleapis.com/maps/api/js?key=AIzaSyCrGkTd0pXFZ1lZbj4DJrmsnmmXvT_DKjg";
      script.async = true;
      script.onload = resolve;
      document.head.appendChild(script);
    });
  }

  _initMap() {
    const mapOptions = {
      center: { lat: 13.794, lng: -88.896 },
      zoom: 8,
    };

    this.map = new google.maps.Map(this.mapRef.el, mapOptions);

    // Crear capa de datos para distritos
    this.districtsLayer = new google.maps.Data({ map: this.map });
    this.districtsLayer.loadGeoJson("/l10n_sv_despacho/static/data/slv_admin2_em.geojson", null, () => {
      this._applyStyles(this.props);
    });

    // Crear capa de datos para municipios anteriores
    this.previousLayer = new google.maps.Data({ map: this.map });
    this.previousLayer.loadGeoJson("/l10n_sv_despacho/static/data/geoBoundaries-SLV-ADM2.geojson", null, () => {
      this._applyStyles(this.props);
    });
  }

  _applyStyles(props) {
    let current = [];
    let previous = [];

    try {
      const data = JSON.parse(props.record.data.selected_districts_json || "{}");
      current = data.current || [];
      previous = data.previous || [];
    } catch (e) {
      current = [];
      previous = [];
    }

    // Estilo para distritos (adm2_pcode)
    this.districtsLayer.setStyle((feature) => {
      const adm2Pcode = feature.getProperty("adm2_pcode");
      const isCurrent = adm2Pcode && current.includes(String(adm2Pcode));

      if (isCurrent) {
        return {
          fillColor: "#9741CC",
          strokeColor: "#9741CC",
          strokeWeight: 2,
          fillOpacity: 0.6,
          zIndex: 1,
        };
      }
      return {
        fillColor: "transparent",
        strokeColor: "#9E9E9E",
        strokeWeight: 0.5,
        fillOpacity: 0,
        zIndex: 1,
      };
    });

    // Estilo para municipios anteriores (shapeID)
    this.previousLayer.setStyle((feature) => {
      const shapeID = feature.getProperty("shapeID");
      const isPrevious = shapeID && previous.includes(String(shapeID));

      if (isPrevious) {
        return {
          fillColor: "#FF9800",
          strokeColor: "#FF9800",
          strokeWeight: 2,
          fillOpacity: 0.4,
          zIndex: 2,
        };
      }
      return {
        fillColor: "transparent",
        strokeColor: "#9E9E9E",
        strokeWeight: 0.5,
        fillOpacity: 0,
        zIndex: 2,
      };
    });
  }
}

registry.category("fields").add("map_districts_widget", { component: MapDistrictsComponent });
