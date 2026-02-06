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
        help="JSON con los PCODEs de municipios actuales y anteriores"
    )

    # Campo técnico para disparar el Widget en la vista
    map_view = fields.Char(string="Mapa", default="map")

    @api.depends(
        "zone_line_ids",
        "zone_line_ids.munic_ids.geo_pcode",
        "zone_line_ids.previous_munic_ids.shape_id",
    )

    def _compute_selected_districts_json(self):
        for zone in self:
            # Municipios actuales
            current_codes = list(set(
                c for c in zone.zone_line_ids.mapped("munic_ids.geo_pcode") if c
            ))

            # Municipios anteriores
            previous_codes = list(set(
                c for c in zone.zone_line_ids.mapped("previous_munic_ids.shape_id") if c
            ))

            payload = {
                "current": current_codes,
                "previous": previous_codes,
            }

            print(">>>>>>> ZONA:", zone.name)
            print(">>>>>>> PAYLOAD MAPA:", payload)

            zone.selected_districts_json = json.dumps(payload)

