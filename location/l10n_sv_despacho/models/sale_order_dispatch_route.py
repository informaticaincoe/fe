# models/sale_order_dispatch_route.py
from odoo import fields, models

class SaleOrder(models.Model):
    _inherit = "sale.order"

    dispatch_route_id = fields.Many2one(
        "dispatch.route",
        string="Ruta de despacho",
        copy=False,
        index=True,
        ondelete="set null",
    )

    partner_phone = fields.Char(
        related='partner_id.phone',
        string='Teléfono',
        store=False
    )

    partner_address = fields.Char(
        string='Dirección',
        compute='_compute_partner_address',
        store=False
    )

    dispatch_state = fields.Selection([
        ("free", "Libre"),
        ("assigned", "Asignada a ruta"),
        ("delivered", "Entregada"),
        ("returned", "Devuelta"),
    ], default="free", copy=False)

    dispatch_reception_line_id = fields.Many2one("dispatch.route.reception.line", copy=False)
