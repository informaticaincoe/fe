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

    onWillUpdateProps((nextProps) => {
        if (this.map) {
            this._applyStyles(this.map, nextProps);
        }
    });

    onMounted(async () => {
        if (this.el) {
            this.rootRef.el.style.width = "100vw";
            this.rootRef.el.style.display = "block";
        }
        console.log("mapa ", this)

        await this._loadGoogleAPI();
        this._initMap();
    });
  }

  async _loadGoogleAPI() {
    if (window.google) return;
    return new Promise((resolve) => {
        const script = document.createElement("script");
        script.src = `https://maps.googleapis.com/maps/api/js?key=AIzaSyCrGkTd0pXFZ1lZbj4DJrmsnmmXvT_DKjg`;
        script.async = true;
        script.onload = resolve;
        document.head.appendChild(script);
    });
  }

  _initMap() {
    const mapOptions = { center: { lat: 13.794, lng: -88.896 }, zoom: 8 };
    this.map = new google.maps.Map(this.mapRef.el, mapOptions);

    // Cargar del archivo geojson
    this.map.data.loadGeoJson("/l10n_sv_despacho/static/data/slv_admin2_em.geojson");
    this._applyStyles(this.map, this.props);
  }

  _applyStyles(map, props) {
    let districts = [];
    try {
      // leer codigos de los distritos selecionados
      districts = JSON.parse(props.record.data.selected_districts_json || "[]");
    } catch (e) { districts = []; }

    map.data.setStyle((feature) => {
      //obtener codigo de distrito del archivo geojson
      const pcode = feature.getProperty("adm2_pcode");
      //obtener distritos que coincidan su codigo con el codigo del geojson
      const isSelected = districts.includes(pcode);
      return {
        fillColor: isSelected ? "#9741CC" : "transparent",
        strokeColor: isSelected ? "#9741CC" : "#9E9E9E",
        strokeWeight: isSelected ? 2 : 0.5,
        fillOpacity: isSelected ? 0.6 : 0,
        visible: true,
      };
    });
  }
}

registry.category("fields").add("map_districts_widget", { component: MapDistrictsComponent });