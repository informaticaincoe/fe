from odoo import models, fields


class ResPreviousMunicipality(models.Model):
    _name = "res.previous.municipality"
    _description = 'Municipios anteriores'

    name = fields.Char(string="Name", required=True, help="Name of municipality", translate=True)
    code = fields.Char(string="Code", required=True, help='Code of municipality')
    dpto_id = fields.Many2one('res.country.state', string="State", required=True, help="State")
    shape_id = fields.Char(
        string="GeoJSON PCODE",
        index=True,
        help="Código del municipio en el GeoJSON."
    )