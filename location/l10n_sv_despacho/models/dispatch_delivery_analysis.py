from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class DispatchDeliveryAnalysis(models.TransientModel):
    _name = "dispatch.delivery.analysis"
    _description = "Análisis de Estados de Ruta (ORM)"
    # OJO: TransientModel sí tiene tabla, no necesita SQL view.

    user_id = fields.Many2one("res.users", default=lambda self: self.env.user, index=True, readonly=True)

    route_id = fields.Many2one("dispatch.route", string="Ruta", readonly=True)
    invoice_id = fields.Many2one("account.move", string="Factura", readonly=True)
    partner_id = fields.Many2one("res.partner", string="Cliente", readonly=True)

    route_state = fields.Selection([
        ("confirmed", "Confirmado"),
        ("in_transit", "En tránsito"),
        ("received", "Recibido (CxC)"),
        ("cancel", "Cancelado"),
    ], string="Estado de Ruta", readonly=True)

    delivery_status = fields.Selection([
        ("delivered", "Entregado"),
        ("partial", "Parcial"),
        ("not_delivered", "No Entregado"),
        ("pending", "Pendiente (En Viaje)"),
    ], string="Resultado Entrega", readonly=True)

    currency_id = fields.Many2one("res.currency", string="Moneda", readonly=True)
    order_total = fields.Monetary(string="Monto", currency_field="currency_id", readonly=True)

    date = fields.Date(string="Fecha de Ruta", readonly=True)

    # -----------------------------
    # BUILD REPORT (ORM)
    # -----------------------------
    @api.model
    def _rebuild_report(self):
        """Reconstruye el reporte para el usuario actual (sin SQL)."""
        uid = self.env.user.id

        # 1) limpiar registros previos del usuario (evita mezclas)
        self.search([("user_id", "=", uid)]).unlink()

        Line = self.env["dispatch.route.reception.line"]
        Move = self.env["account.move"]

        # ---------------------------------------------------------
        # A) Facturas que YA tienen recepción (desde reception lines)
        # ---------------------------------------------------------
        # Nota: esto filtra por estado de la RUTA (no por recepción)
        lines = Line.search([
            ("reception_id.route_id", "!=", False),
            ("reception_id.route_id.state", "!=", "draft"),
        ])

        received_invoice_ids = set(lines.mapped("invoice_id").ids)

        vals = []
        for l in lines:
            route = l.reception_id.route_id
            # moneda: la de la recepción/route (ambas relacionadas en tu modelo)
            currency = (
                    l.reception_id.currency_id
                    or route.currency_id
                    or (l.invoice_id.currency_id if l.invoice_id else False)
            )

            vals.append({
                "user_id": uid,
                "route_id": route.id,
                "invoice_id": l.invoice_id.id if l.invoice_id else False,
                "partner_id": l.partner_id.id,
                "route_state": route.state,
                "delivery_status": l.status,
                "order_total": l.order_total,
                "currency_id": currency.id if currency else False,
                "date": route.route_date,
            })

        # ---------------------------------------------------------
        # B) Facturas en rutas confirmadas/en tránsito pero sin recepción
        # ---------------------------------------------------------
        domain_pending = [
            ("dispatch_route_id", "!=", False),
            ("dispatch_route_id.state", "in", ("confirmed", "in_transit")),
        ]
        if received_invoice_ids:
            domain_pending.append(("id", "not in", list(received_invoice_ids)))

        pending_moves = Move.search(domain_pending)

        for m in pending_moves:
            route = m.dispatch_route_id
            vals.append({
                "user_id": uid,
                "route_id": route.id,
                "invoice_id": m.id,
                "partner_id": m.partner_id.id,
                "route_state": route.state,
                "delivery_status": "pending",
                "order_total": m.amount_total,
                "currency_id": m.currency_id.id,
                "date": route.route_date,
            })

        if vals:
            self.create(vals)

        _logger.info("DispatchDeliveryAnalysis | user=%s | lines=%s | pending=%s | total=%s",
                     uid, len(lines), len(pending_moves), len(vals))

        return True

    # -----------------------------
    # ACTION OPEN (para menú)
    # -----------------------------
    @api.model
    def action_open_report(self):
        self._rebuild_report()

        return {
            "type": "ir.actions.act_window",
            "name": _("Estados de Ruta"),
            "res_model": "dispatch.delivery.analysis",
            "view_mode": "list",
            "target": "current",
            "domain": [("user_id", "=", self.env.user.id)],
            "context": dict(self.env.context, search_default_this_month=1),
        }

    def action_refresh_report(self):
        """Botón 'Actualizar' opcional."""
        self._rebuild_report()
        return {"type": "ir.actions.client", "tag": "reload"}

    # -----------------------------
    # PDF
    # -----------------------------
    def action_print_pdf(self):
        """
        - Si hay filas seleccionadas: imprime esas (active_ids)
        - Si NO hay selección: intenta usar active_domain (lo que está en pantalla)
          Si no viene active_domain: fallback por user_id actual.
        """
        ctx = dict(self.env.context or {})
        active_ids = ctx.get("active_ids") or []
        active_domain = ctx.get("active_domain")

        if active_ids:
            recs = self.browse(active_ids)
        elif active_domain:
            # normalmente ya viene el filtro por user_id en el dominio, pero por seguridad:
            dom = list(active_domain)
            if ("user_id", "=", self.env.user.id) not in dom:
                dom.append(("user_id", "=", self.env.user.id))
            recs = self.search(dom)
        else:
            recs = self.search([("user_id", "=", self.env.user.id)])

        return self.env.ref("l10n_sv_despacho.action_report_dispatch_delivery_analysis_pdf").report_action(recs)
