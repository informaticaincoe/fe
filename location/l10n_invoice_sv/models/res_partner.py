from odoo import fields, models, api, _

class ResPartner(models.Model):
    _inherit = "res.partner"

    COND_PAGO = [
        ('1', '1-Contado'),
        ('2', '2-A Crédito'),
        ('3', '3-Otro'),
    ]

    gran_contribuyente = fields.Boolean(string="Gran Contribuyente", help="Marque esta opción si el cliente es un gran contribuyente.", default=False)

    condicion_pago_compras_id = fields.Selection(
        COND_PAGO,
        string="Condición de pago"
    )

    terminos_pago_compras_id = fields.Many2one(
        related='property_supplier_payment_term_id',
        string="Terminos de pago"
    )

    formas_pago_compras_id = fields.Many2one(
        'account.move.forma_pago.field',
        string="Formas de pago"
    )

    condicion_pago_venta_id = fields.Selection(
        COND_PAGO,
        string="Condición de pago"
    )

    terminos_pago_venta_id = fields.Many2one(
        related='property_payment_term_id',
        string="Terminos de pago"
    )

    formas_pago_venta_id = fields.Many2one(
        'account.move.forma_pago.field',
        string="Formas de pago"
    )

    enforce_dte_pending_limit = fields.Boolean(
        string='Factura por Factura',
        help='Si está activo, el cliente no puede tener más de una factura pendiente.',
        default=True)

    max_pending_dte_count = fields.Integer(
        string='Limite de facturas pendientes de pago',
        help="Limite de facturas pendientes de pago antes de realizarle una nueva venta al cliente",
        default=1)