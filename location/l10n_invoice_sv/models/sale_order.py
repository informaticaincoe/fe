from odoo import api, fields, models, _

class SaleOrder(models.Model):
    _inherit = "sale.order"

    recintoFiscal = fields.Many2one('account.move.recinto_fiscal.field', string="Recinto Fiscal")