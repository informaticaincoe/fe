import json
from odoo import models, fields, api

class DispatchZones(models.Model):
    _name = "dispatch.zones"
    name = fields.Char(string="Name", required=True, help="Nombre de la zona", )

    zone_line_ids = fields.One2many(
        'dispatch.zone.line',
        'zone_id',
        string="Distribución Geográfica"
    )

    # Este es el campo que el Widget de JS leerá.
    # store=True es vital para que OWL detecte el cambio tras el save/onchange.
    selected_districts_json = fields.Char(
        compute="_compute_selected_districts_json",
        store=True,
        help="JSON con los PCODEs de los municipios seleccionados"
    )

    # Campo técnico para disparar el Widget en la vista
    map_view = fields.Char(string="Mapa", default="map")

    @api.depends("zone_line_ids", "zone_line_ids.munic_ids", "zone_line_ids.munic_ids.geo_pcode")
    def _compute_selected_districts_json(self):
        for zone in self:
            # Extraemos los códigos de los municipios seleccionados
            # Asegúrate de que tus registros en res.municipality tengan el geo_pcode lleno
            codes = zone.zone_line_ids.mapped("munic_ids.geo_pcode")

            # Limpiamos nulos y duplicados
            valid_codes = list(set([c for c in codes if c]))

            # Debug en consola de Odoo
            print(">>>>>>> ACTUALIZANDO ZONA:", zone.name)
            print(">>>>>>> CODES ENCONTRADOS:", valid_codes)

            zone.selected_districts_json = json.dumps(valid_codes)

            print("zone.selected_districts_json :", zone.selected_districts_json)
