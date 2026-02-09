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
