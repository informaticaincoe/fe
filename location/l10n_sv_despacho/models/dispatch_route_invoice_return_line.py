from odoo import fields, models

class DispatchRouteInvoiceReturnLine(models.Model):
    _name = "dispatch.route.invoice.return.line"
    _description = "Línea devolución factura ruta"

    return_id = fields.Many2one(
        "dispatch.route.invoice.return",
        required=True,
        ondelete="cascade"
    )

    order_id = fields.Many2one("sale.order", related="return_id.order_id", store=True, readonly=True)
    move_id = fields.Many2one("account.move", related="return_id.move_id", store=True, readonly=True)

    select = fields.Boolean(default=True, string="Devolver")

    product_id = fields.Many2one(
        "product.product",
        required=True
    )
    uom_id = fields.Many2one(
        "uom.uom",
        required=True
    )

    qty_invoiced = fields.Float(readonly=True)
    qty_return = fields.Float(default=0.0)

    reason = fields.Selection([
        ("damaged", "Avería"),
        ("wrong", "Producto equivocado"),
        ("expired", "Vencido"),
        ("customer_reject", "Rechazado por cliente"),
        ("other", "Otro"),
    ], default="other", required=True)

    note = fields.Char("Detalle")
