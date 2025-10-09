from odoo import fields, models, api, _

class ResPartner(models.Model):
    _inherit = "res.partner"

    COND_PAGO = [
        ('1', '1-Contado'),
        ('2', '2-A Crédito'),
        ('3', '3-Otro'),
    ]

    gran_contribuyente = fields.Boolean(string="Gran Contribuyente", help="Marque esta opción si el cliente es un gran contribuyente.", default=False)

    condicion_pago_venta_id = fields.Selection(
        COND_PAGO,
        string="Condición de pago"
    )

    terminos_pago_venta_id = fields.Many2one(
        'account.payment.term',
        string="Terminos de pago"
    )

    formas_pago_venta_id = fields.Many2one(
        'account.move.forma_pago.field',
        string="Formas de pago"
    )