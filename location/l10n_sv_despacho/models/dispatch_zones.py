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

    # 1. Agregamos store=True para que se guarde en la BD
    # 2. Agregamos sanitize=False para que Odoo no borre la imagen
    map_url = fields.Html(
        string="Mapa de Cobertura",
        compute="_compute_map_url",
        store=True,
        sanitize=False,
        strip_style=False
    )

    @api.depends('zone_line_ids', 'zone_line_ids.dpto_id', 'zone_line_ids.munic_ids')
    def _compute_map_url(self):
        # Es mejor usar la key de los parámetros, pero para probar dejamos la tuya fija
        api_key = "AIzaSyCrGkTd0pXFZ1lZbj4DJrmsnmmXvT_DKjg"

        for zone in self:
            if not api_key or not zone.zone_line_ids:
                zone.map_url = False
                continue

            markers = ""
            for line in zone.zone_line_ids:
                if line.munic_ids:
                    for munic in line.munic_ids:
                        # Limpieza de nombres para evitar caracteres extraños en la URL
                        addr = f"{munic.name},{line.dpto_id.name},El Salvador".replace(' ', '+')
                        markers += f"&markers=color:blue|label:M|{addr}"
                elif line.dpto_id:
                    addr = f"{line.dpto_id.name},El Salvador".replace(' ', '+')
                    markers += f"&markers=color:red|label:D|{addr}"

            url = f"https://maps.googleapis.com/maps/api/staticmap?size=600x400&maptype=roadmap{markers}&key={api_key.strip()}"

            # Usamos un div contenedor para asegurar el renderizado
            zone.map_url = f'<div class="o_google_map"><img src="{url}" style="max-width:100%; height:auto; border: 1px solid #ccc;"/></div>'


    # -------------------- CODIGO LEAFLET -------------------------
    # Lista de códigos (adm2_pcode) de municipios seleccionados
    # selected_munic_pcdes_json = fields.Char(compute="_compute_selected_munic_pcdes_json")
    #
    # @api.depends("zone_line_ids.munic_ids")
    # def _compute_selected_munic_pcdes_json(self):
    #     for zone in self:
    #         codes = zone.zone_line_ids.mapped("munic_ids.geo_pcode")
    #         if not any(codes):
    #             codes = zone.zone_line_ids.mapped("munic_ids.code")
    #         print(">>>>>>>ZONE ", zone)
    #         zone.selected_munic_pcdes_json = json.dumps([c for c in codes if c])
    #         print(">>>>>>>zone.selected_munic_pcdes_json ", zone.selected_munic_pcdes_json)
    #
    # map_dummy = fields.Char(string="Mapa", compute="_compute_map_dummy")
    #
    # def _compute_map_dummy(self):
    #     for r in self:
    #         r.map_dummy = "ok"
