from odoo import models, fields


class ResMunicipality(models.Model):
    _inherit = "res.municipality"

    geo_pcode = fields.Char(
        string="GeoJSON PCODE",
        index=True,
        help="Código del municipio en el GeoJSON (ej. adm2_pcode)."
    )