from odoo import api, fields, models, _, Command
from odoo.exceptions import ValidationError

class DispatchRouteInvoiceReturn(models.Model):
    _name = "dispatch.route.invoice.return"
    _description = "Devolución de factura de ruta"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(default=lambda self: _("Nuevo"), copy=False, readonly=True, tracking=True)
    state = fields.Selection(
        [("draft", "Borrador"), ("confirmed", "Confirmado"), ("cancelled", "Cancelado")],
        default="draft", tracking=True
    )

    company_id = fields.Many2one(
        "res.company",
        related="reception_id.company_id",
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(related="move_id.currency_id", store=True)

    move_id = fields.Many2one("account.move", string="Factura", required=True)
    partner_id = fields.Many2one(related="move_id.partner_id", store=True, readonly=True)

    reception_id = fields.Many2one("dispatch.route.reception", required=True)
    reception_line_id = fields.Many2one("dispatch.route.reception.line", string="Línea de recepción", tracking=True)

    return_type = fields.Selection([
        ("change", "Cambio / Reenvío"),
        ("rejected", "Cliente no quiso"),
        ("not_found", "No encontrado / cerrado"),
        ("damaged", "Avería"),
        ("other", "Otro"),
    ], default="other", required=True, tracking=True)

    notes = fields.Text("Observaciones")
    line_ids = fields.One2many(
        "dispatch.route.invoice.return.line",
        "return_id",
        string="Productos devueltos"
    )

    def _prepare_lines_from_invoice(self, move):
        cmds = [Command.clear()]
        lines = move.invoice_line_ids.filtered(lambda l: l.product_id and not l.display_type)
        for il in lines:
            uom = il.product_uom_id or il.product_id.uom_id
            qty = il.quantity or 0.0
            cmds.append(Command.create({
                "select": True,
                "product_id": il.product_id.id,
                "uom_id": uom.id,
                "qty_invoiced": qty,
                "qty_return": 0.0,
                "reason": "other",
                "note": False,
            }))
        return cmds

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        move_id = self.env.context.get("default_move_id")
        if not move_id:
            return res

        move = self.env["account.move"].browse(move_id)
        if not move.exists():
            return res

        lines = []

        for inv_line in move.invoice_line_ids.filtered(
                lambda l: l.product_id and not l.display_type
        ):
            lines.append((0, 0, {
                "product_id": inv_line.product_id.id,
                "uom_id": inv_line.product_uom_id.id,
                "qty_invoiced": inv_line.quantity,
                "qty_return": 0.0,
                "reason": "other",
            }))

        res["line_ids"] = lines
        return res

    @api.onchange("move_id")
    def _onchange_move_id(self):
        if not self.move_id:
            self.line_ids = [Command.clear()]
            return

        cmds = [Command.clear()]

        # 🔴 ESTE es el punto clave
        lines = self.move_id.invoice_line_ids.filtered(
            lambda l: l.product_id and not l.display_type
        )

        for il in lines:
            cmds.append(Command.create({
                "select": True,
                "product_id": il.product_id.id,
                "uom_id": il.product_uom_id.id or il.product_id.uom_id.id,
                "qty_invoiced": il.quantity,
                "qty_return": 0.0,
                "reason": "other",
            }))

        self.line_ids = cmds

    def action_confirm(self):
        for rec in self:
            if rec.state != "draft":
                continue

            selected = rec.line_ids.filtered(lambda l: l.select and l.qty_return > 0)
            if not selected:
                raise ValidationError(_("Seleccione al menos un producto y coloque cantidad devuelta > 0."))

            for ln in selected:
                if ln.qty_return > ln.qty_invoiced:
                    raise ValidationError(_("La cantidad devuelta no puede exceder la facturada (%s).") % ln.product_id.display_name)

            # Marcar estados / flags en recepción
            if rec.reception_line_id:
                rec.reception_line_id.write({"has_return": True})

            # Marcar la factura como devuelta y bloqueos/estado despacho (campos nuevos)
            rec.move_id.write({
                "dispatch_state": "returned",
                "dispatch_return_id": rec.id,
            })

            # Secuencia
            if rec.name == _("Nuevo"):
                rec.name = self.env["ir.sequence"].next_by_code("dispatch.route.invoice.return") or _("DEV")

            rec.state = "confirmed"

    def action_liberate_invoice(self):
        """Libera la factura para que pueda ir en otra ruta."""
        for rec in self:
            if rec.state != "confirmed":
                raise ValidationError(_("Debe confirmar la devolución antes de liberar la factura."))

            # Limpia la asignación de ruta/recepción en la factura
            rec.move_id.write({
                "dispatch_state": "free",
                "dispatch_reception_line_id": False,  # si creas este campo
                "dispatch_route_id": False,           # si creas este campo
            })

    @api.model
    def create(self, vals):
        record = super().create(vals)

        if record.move_id:
            lines_cmds = []
            for line in record.move_id.invoice_line_ids.filtered(
                    lambda l: l.product_id and not l.display_type
            ):
                lines_cmds.append((0, 0, {
                    "product_id": line.product_id.id,
                    "uom_id": line.product_uom_id.id,
                    "qty_invoiced": line.quantity,
                    "qty_return": 0.0,
                    "reason": "other",
                }))

            record.line_ids = lines_cmds

        return record