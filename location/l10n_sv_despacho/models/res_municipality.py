from odoo import models, fields


class ResMunicipality(models.Model):
    _inherit = "res.municipality"

    name = fields.Char(string="Name", required=True, help="Name of municipality", translate=True)
    code = fields.Char(string="Code", required=True, help='Code of municipality')
    dpto_id = fields.Many2one('res.country.state', string="State", required=True, help="State")
    geo_pcode = fields.Char(
        string="GeoJSON PCODE",
        index=True,
        help="Código del municipio en el GeoJSON (ej. adm2_pcode)."
    )