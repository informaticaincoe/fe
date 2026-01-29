/** @odoo-module **/
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, onMounted, useRef } from "@odoo/owl";

export class MapDistrictsComponent extends Component {
  static template = "l10n_sv_despacho.MapContainer";
  static props = { ...standardFieldProps };

  setup() {
    this.mapRef = useRef("map");

    onMounted(async () => {
        // Intentar esperar un poco si google no está listo inmediatamente
        let attempts = 0;
        const checkGoogle = setInterval(async () => {
            attempts++;
            if (typeof google !== "undefined") {
                clearInterval(checkGoogle);
                await this.initMap();
            } else if (attempts > 50) { // Si después de 5 seg no carga, dar error
                clearInterval(checkGoogle);
                console.error("Google Maps API no cargó después de varios intentos.");
            }
        }, 100);
    });
  }

  async initMap() {

    let districts = [];
    try {
      districts = JSON.parse(this.props.record.data.selected_districts_json || "[]");
    } catch (e) {}

    const mapOptions = { center: { lat: 13.794, lng: -88.896 }, zoom: 8 };
    const map = new google.maps.Map(this.mapRef.el, mapOptions);

    map.data.loadGeoJson(
      "/l10n_sv_despacho/static/data/slv_admin2.geojson",
      null,
      (features) => {

        // Opcional: hacer fit bounds
        const bounds = new google.maps.LatLngBounds();
        features.forEach(f => {
          f.getGeometry().forEachLatLng((latlng) => bounds.extend(latlng));
        });
        if (!bounds.isEmpty()) map.fitBounds(bounds);
      }
    );

    map.data.setStyle((feature) => {
      const name = feature.getProperty("adm3_name");
      const isSelected = districts.includes(name);
      return {
        fillColor: isSelected ? "#714B67" : "transparent",
        strokeColor: isSelected ? "#714B67" : "#9E9E9E",
        strokeWeight: isSelected ? 2 : 0.5,
        fillOpacity: isSelected ? 0.5 : 0,
        visible: true,
      };
    });
  }
}

registry.category("fields").add("map_districts_widget", { component: MapDistrictsComponent });
