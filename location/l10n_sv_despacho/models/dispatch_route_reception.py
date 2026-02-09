from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)

class DispatchRouteReception(models.Model):
    _name = "dispatch.route.reception"
    _description = "Recepción de Ruta (CxC)"
    _order = "create_date desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        string="Número",
        required=True,
        copy=False,
        readonly=True,
        default="/"
    )

    route_id = fields.Many2one("dispatch.route", string="Ruta", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="route_id.company_id", store=True, readonly=True)
    currency_id = fields.Many2one(related="route_id.currency_id", store=True, readonly=True)

    state = fields.Selection([
        ("draft", "Borrador"),
        ("confirmed", "Confirmada"),
        ("done", "Finalizada"),
        ("cancel", "Cancelada"),
    ], default="draft", tracking=True)

    received_by_id = fields.Many2one("res.users", string="Recibido por", default=lambda self: self.env.user, required=True)
    received_date = fields.Datetime(string="Fecha recepción", default=fields.Datetime.now, required=True)

    cash_received = fields.Monetary(string="Efectivo recibido", currency_field="currency_id", required=True, default=0.0)
    expected_cash_total = fields.Monetary(
        compute="_compute_expected_cash_total",
        store=True,
    )
    cash_difference = fields.Monetary(string="Diferencia", currency_field="currency_id", compute="_compute_difference", store=True)

    notes = fields.Text(string="Observaciones")

    line_ids = fields.One2many("dispatch.route.reception.line", "reception_id", string="Facturas")

    @api.model_create_multi
    def create(self, vals_list):
        receptions = super().create(vals_list)

        for reception, vals in zip(receptions, vals_list):
          
          if vals.get("name", "/") == "/":
                reception.name = self.env["ir.sequence"].next_by_code(
                    "dispatch.route.reception"
                ) or "/"

           if reception.route_id:
              lines = []
              for so in reception.route_id.sale_order_ids:
                  is_credit = bool(so.payment_term_id)  # o tu regla real
                  lines.append((0, 0, {
                      "order_id": so.id,
                      "is_credit": is_credit,
                      "status": "delivered",
                  }))

              reception.write({"line_ids": lines})

              if reception.route_id:
                  lines = []
                  for move in reception.route_id.account_move_ids.filtered(
                          lambda m: m.move_type in ("out_invoice", "out_refund")
                  ):
                      is_credit = bool(
                          move.invoice_payment_term_id
                          and any(
                              line.nb_days > 0
                              for line in move.invoice_payment_term_id.line_ids)
                      )
                      _logger.info(
                          "[Reception] create() Factura %s → is_credit=%s",
                          move.name,
                          is_credit,
                      )
                      lines.append((0, 0, {
                          "move_id": move.id,
                          "partner_id": move.partner_id.id,
                          "move_total": move.amount_total,
                          "is_credit": is_credit,
                          "status": "delivered",
                      }))

                  reception.line_ids = lines

        return receptions

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        route_id = res.get("route_id") or self.env.context.get("default_route_id")
        _logger.debug("default_get route_id=%s", route_id)
        if route_id:
            route = self.env["dispatch.route"].browse(route_id)
            lines = []
            for mv in route.invoice_ids:
                # Heurística simple: si tiene término de pago => crédito
                # is_credit = bool(mv.invoice_payment_term_id and mv.invoice_payment_term_id.line_ids)
                is_credit = bool(
                    mv.invoice_payment_term_id
                    and any(
                        line.nb_days > 0
                        for line in mv.invoice_payment_term_id.line_ids)
                )
                _logger.info(
                    "[ROUTE %s] default_get() Factura %s → is_credit=%s",
                    route.id,
                    mv.name,
                    is_credit,
                )
                lines.append((0, 0, {
                    "move_id": mv.id,
                    "status": "delivered",
                    "is_credit": is_credit,
                }))
            res["line_ids"] = lines
            res["line_ids"] = self._prepare_lines_from_route(route)
        return res

    @api.depends("line_ids.status", "line_ids.is_credit", "line_ids.order_total")
    def _compute_expected_cash_total(self):
        for rec in self:
            total = 0.0
            for line in rec.line_ids:
                # Solo efectivo (no crédito) y solo lo entregado/parcial si es tu regla
                if not line.is_credit and line.status in ("delivered", "partial"):
                    total += (line.order_total or 0.0)
            rec.expected_cash_total = total

    @api.depends("cash_received", "expected_cash_total")
    def _compute_difference(self):
        for rec in self:
            rec.cash_difference = rec.cash_received - rec.expected_cash_total

    def action_confirm(self):
        for rec in self:

            if rec.state != "draft":
                continue

            if not rec.route_id:
                raise UserError(_("Debe seleccionar una ruta."))

            if rec.route_id.state != "in_transit":
                raise UserError(_("La ruta debe estar 'En tránsito' para poder recibirla."))

            # Validaciones
            for ln in rec.line_ids:
                if ln.status == "not_delivered" and not (ln.not_delivered_reason or "").strip():
                    raise ValidationError(_("Debe ingresar el motivo cuando una factura es 'No entregada'."))
                if ln.status == "partial" and not (ln.partial_note or "").strip():
                    raise ValidationError(_("Agregue un detalle para 'Parcial / Avería'."))

            # Actualiza ruta a recibido + resumen
            rec.route_id.write({
                "state": "received",
                "received_by_id": rec.received_by_id.id,
                "received_date": rec.received_date,
                "cash_received": rec.cash_received,
                "expected_cash_total": rec.expected_cash_total,
                "cash_difference": rec.cash_difference,
                "last_reception_id": rec.id,
            })

            # Secuencia
            if rec.name == "/":
                rec.name = self.env["ir.sequence"].next_by_code(
                    "dispatch.route.reception"
                ) or "/"

            rec.state = "confirmed"

    def action_cancel(self):
        self.write({"state": "cancel"})

    ### CARGAR TODOS LOS DUCMENTOS RELACIONADOS A LA RUTA
    def _prepare_lines_from_route(self, route):
        """ construye comando O2M para line_ids desde las facturas de la ruta """
        _logger.info(
            "[ROUTE %s] Iniciando preparación de líneas desde facturas (%s documentos)",
            route.id,
            len(route.sale_order_ids),
        )

        lines_cmds = [(5, 0, 0)] # limpia lineas actuales
        for mv in route.sale_order_ids:
            _logger.debug(
                "[ROUTE %s] Procesando factura %s (id=%s, payment_term=%s)",
                route.id,
                mv.name,
                mv.id,
                mv.invoice_payment_term_id.display_name if mv.invoice_payment_term_id else None,
            )
            is_credit = bool(
                mv.invoice_payment_term_id
                and any(
                    line.nb_days > 0
                    for line in mv.invoice_payment_term_id.line_ids)
            )
            _logger.info(
                "[ROUTE %s] Factura %s → is_credit=%s",
                route.id,
                mv.name,
                is_credit,
            )
            lines_cmds.append((0, 0, {
                "order_id": so.id,
                "status": "delivered",
                "is_credit": is_credit,
            }))
        return lines_cmds

    @api.onchange("route_id")
    def _onchange_route_id_load_invoices(self):
        for rec in self:
            if not rec.route_id:
                rec.line_ids = [(5, 0, 0)]
                return

            # solo auto-carga cuando esta en borrador (para no pisar recepcion confirmada)
            if rec.state != "draft":
                return

            # evitar cargar lineas cuando ya hay carga
            if rec.line_ids:
                return

            rec.line_ids = rec._prepare_lines_from_route(rec.route_id)

            # resetear fectivo si se cambia la ruta
            rec.cash_received = 0.0

    def action_set_draft(self):
        for rec in self:
            if rec.state != "cancel":
                raise UserError(_("Solo se puede restablecer a borrador una recepcion cancelada."))
            rec.route_id.write({"state": "in_transit"})
            rec.state = "draft"

    def write(self, vals):
        for rec in self:
            if rec.state == "confirmed":
                # permitir solo cambiar state para restablecer/cancelar si lo deseas
                allowed = {"state"}
                if set(vals.keys()) - allowed:
                    raise UserError(_("No puedes modificar una recepción confirmada."))
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.state == "confirmed":
                raise UserError(_("No puedes eliminar una recepción confirmada."))
        return super().unlink()

    def action_download_reporte_reception(self):
        self.ensure_one()

        return self.env.ref("l10n_sv_despacho.action_report_recepcion_ruta").report_action(self)


class DispatchRouteInvoiceReturnLine(models.Model):
    _name = "dispatch.route.invoice.return.line"
    _description = "Línea devolución factura ruta"

    return_id = fields.Many2one("dispatch.route.invoice.return", required=True, ondelete="cascade")
    select = fields.Boolean(default=True, string="Devolver")

    product_id = fields.Many2one("product.product", required=True)
    uom_id = fields.Many2one("uom.uom", required=True)

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

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for ln in self:
            if ln.product_id and not ln.uom_id:
                ln.uom_id = ln.product_id.uom_id.id











































