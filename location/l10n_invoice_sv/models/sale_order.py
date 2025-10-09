from odoo import api, fields, models, _

class SaleOrder(models.Model):
    _inherit = "sale.order"

    recintoFiscal = fields.Many2one('account.move.recinto_fiscal.field', string="Recinto Fiscal")

    # res.partner
    condiciones_pago_default = fields.Selection(
        [
            ('1', '1-Contado'),
            ('2', '2-A Crédito'),
            ('3', '3-Otro'),
        ],
        string="Condición de pago por defecto (DTE)",
        default='1',
    )
