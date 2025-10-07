from odoo import fields, models, api, _

class ResPartner(models.Model):
    _inherit = "res.partner"

    gran_contribuyente = fields.Boolean(string="Gran Contribuyente", help="Marque esta opción si el cliente es un gran contribuyente.", default=False)