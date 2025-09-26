from odoo import fields, models, api, _

class ResCompany(models.Model):
    _inherit = "res.company"

    sit_usar_lotes_contingencia = fields.Boolean(
        string="Usar lotes en contingencia",
        default=False,
        help="Si está desmarcado, al crear contingencia no se asignarán ni crearán lotes."
    )
