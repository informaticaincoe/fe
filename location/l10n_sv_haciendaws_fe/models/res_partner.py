from odoo import fields, models, api, _

class ResPartner(models.Model):
    _inherit = "res.partner"

    journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Diario",
        help="Seleccione el diario por defecto para este cliente"
    )