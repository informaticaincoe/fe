from odoo import api, fields, models, _, Command
from odoo.exceptions import ValidationError, UserError

class DispatchRouteInvoiceReturn(models.Model):
    _name = "dispatch.route.invoice.return"
    _description = "Devolución de factura de ruta"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(
        string="Número",
        required=True,
        copy=False,
        readonly=True,
        default="/"
    )
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

    order_id = fields.Many2one("sale.order", string="Orden", required=True)
    move_id = fields.Many2one("account.move", string="Factura")  # ya NO required

    partner_id = fields.Many2one(related="order_id.partner_id", store=True, readonly=True)

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

    def action_load_products(self):
        cmds = [Command.clear()]
        if self.move_id:
            src_lines = self.move_id.invoice_line_ids.filtered(lambda l: l.product_id and not l.display_type)
            for il in src_lines:
                uom = il.product_uom_id or il.product_id.uom_id
                cmds.append(Command.create({
                    "select": True,
                    "product_id": il.product_id.id,
                    "uom_id": uom.id,
                    "qty_invoiced": il.quantity or 0.0,
                    "qty_return": 0.0,
                    "reason": "other",
                    "note": False,
                }))
        else:
            src_lines = self.order_id.order_line.filtered(lambda l: l.product_id and not l.display_type)
            for sl in src_lines:
                uom = sl.product_uom.id if sl.product_uom else sl.product_id.uom_id.id
                cmds.append(Command.create({
                    "select": True,
                    "product_id": sl.product_id.id,
                    "uom_id": uom,
                    "qty_invoiced": sl.product_uom_qty or 0.0,  # “qty ordenada”
                    "qty_return": 0.0,
                    "reason": "other",
                    "note": False,
                }))
        return cmds

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

    @api.onchange("move_id")
    def _onchange_move_id(self):
        if not self.move_id:
            self.line_ids = [Command.clear()]
            return

        cmds = [Command.clear()]

        # ESTE es el punto clave
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
            if rec.name == "/":
                rec.name = self.env["ir.sequence"].next_by_code(
                    "dispatch.route.invoice.return"
                ) or "/"

            rec.state = "confirmed"

    def action_liberate_invoice(self):
        for rec in self:
            if rec.state != "confirmed":
                raise ValidationError(_("Debe confirmar la devolución antes de liberar la factura."))

            move = rec.move_id
            if not move:
                raise ValidationError(_("No hay factura asociada."))

            move.write({
                "dispatch_state": "free",
                "dispatch_route_id": False,
                "dispatch_reception_line_id": False,
            })

            rec.write({
                "state": "draft"
            })

    #AQUÍ ESTÁ LA CLAVE
    @api.model
    def create(self, vals):
        record = super().create(vals)

        if not record.move_id:
            return record

        if vals.get("name", "/") == "/":
            vals["name"] = self.env["ir.sequence"].next_by_code(
                "dispatch.route.invoice.return"
            ) or "/"

        lines = []
        for il in record.move_id.invoice_line_ids.filtered(
                lambda l: l.product_id and not l.display_type
        ):
            lines.append((0, 0, {
                "product_id": il.product_id.id,
                "uom_id": il.product_uom_id.id,
                "qty_invoiced": il.quantity,
                "qty_return": 0.0,
            }))

        record.write({"line_ids": lines})

        # marcar que la factura ya tiene devolución
        record.reception_line_id.write({"has_return": True})

        return record

    def _load_invoice_products(self):
        """Carga los productos de la factura"""
        self.ensure_one()

        if not self.move_id:
            return

        lines = []
        invoice_lines = self.move_id.invoice_line_ids.filtered(
            lambda l: l.product_id and not l.display_type
        )

        for il in invoice_lines:
            lines.append((0, 0, {
                "product_id": il.product_id.id,
                "uom_id": il.product_uom_id.id,
                "qty_invoiced": il.quantity,
                "qty_return": 0.0,
                "reason": "other",
            }))

        self.line_ids = lines

    def action_delete_return(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError("Solo se pueden eliminar devoluciones en estado Borrador.")

            # 🔹 Liberar la línea de recepción
            if rec.reception_line_id:
                rec.reception_line_id.has_return = False

            # 🔹 Eliminar líneas hijas
            rec.line_ids.unlink()

            # 🔹 Eliminar cabecera
            rec.unlink()

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
        for l in move.invoice_line_ids.filtered(lambda x: x.product_id):
            lines.append((0, 0, {
                "product_id": l.product_id.id,
                "uom_id": l.product_uom_id.id,
                "qty_invoiced": l.quantity,
                "qty_return": 0.0,
                "reason": "other",
            }))

        res["line_ids"] = lines
        return res

    def action_load_invoice_lines(self):
        for ret in self:
            if not ret.move_id:
                continue

            ret.line_ids.unlink()  # volver a cargar limpio

            for line in ret.move_id.invoice_line_ids:
                if not line.product_id:
                    continue

                self.env["dispatch.route.invoice.return.line"].create({
                    "return_id": ret.id,
                    "product_id": line.product_id.id,
                    "uom_id": line.product_uom_id.id,
                    "qty_invoiced": line.quantity,
                    "qty_return": 0.0,
                })

