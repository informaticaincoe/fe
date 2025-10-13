from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class AccountQuedan(models.Model):
    _name = "account.quedan"
    _description = "Quedán de Proveedor"
    _order = "id desc"

    name = fields.Char(
        string="Número de Quedán",
        required=True,
        readonly=False,
        copy=False,
        default=lambda self: self.env['ir.sequence'].next_by_code('account.quedan')
    )

    partner_id = fields.Many2one(
        'res.partner',
        string="Proveedor",
        required=True,
        domain=[('supplier_rank', '>', 0)]
    )

    fecha_programada = fields.Date(
        string="Fecha programada de pago",
        required=True
    )

    observaciones = fields.Text(string="Observaciones")

    factura_ids = fields.Many2many(
        'account.move',
        string="Facturas vinculadas",
        domain="[('move_type','=','in_invoice')]",
        help="Facturas de proveedor que serán incluidas en este quedán"
    )

    payment_ids = fields.One2many(
        'account.payment',
        'quedan_id',
        string="Pagos relacionados",
        readonly=True
    )

    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmado'),
        ('paid', 'Pagado'),
    ], string="Estado", default="draft", tracking=True)

    monto_total = fields.Monetary(
        string="Monto total",
        compute="_compute_monto_total",
        store=True
    )

    currency_id = fields.Many2one(
        'res.currency',
        string="Moneda",
        default=lambda self: self.env.company.currency_id
    )

    # === Cálculo del total ===
    @api.depends('factura_ids.amount_total')
    def _compute_monto_total(self):
        for rec in self:
            rec.monto_total = sum(rec.factura_ids.mapped('amount_total'))

    # === Acciones ===
    def action_confirm(self):
        for rec in self:
            facturas_pagadas = rec.factura_ids.filtered(lambda f: f.payment_state == 'paid')
            if facturas_pagadas:
                raise UserError("No puedes confirmar el Quedán con facturas ya pagadas.")
            rec.state = 'confirmed'
            rec._sync_payments()

    def action_reset(self):
        for rec in self:
            rec.state = 'draft'
            rec.payment_ids = [(5, 0, 0)]

    # === Sincronización de pagos ===
    def _sync_payments(self):
        """Actualiza los pagos relacionados y el estado según facturas."""
        for rec in self:
            payments = self.env['account.payment'].search([
                ('reconciled_invoice_ids', 'in', rec.factura_ids.ids)
            ])
            rec.payment_ids = [(6, 0, payments.ids)]
            rec._check_facturas_pagadas()

    # === Verificación en tiempo real ===
    def _check_facturas_pagadas(self):
        """Verifica si todas las facturas están pagadas y actualiza el estado."""
        for rec in self:
            if not rec.factura_ids:
                rec.state = 'draft'
            elif all(f.payment_state == 'paid' for f in rec.factura_ids):
                if rec.state != 'paid':
                    rec.state = 'paid'
                    _logger.info(f"[AUTO] El Quedán {rec.name} pasó a estado PAGADO.")
            else:
                if rec.state == 'paid':
                    rec.state = 'confirmed'

    # === Hook que se ejecuta cada vez que se lee el registro ===
    def read(self, fields=None, load='_classic_read'):
        """Cada vez que se abre un Quedán en vista form, se verifica el estado de sus facturas."""
        records = super().read(fields=fields, load=load)
        # Cargar objetos reales y sincronizar
        for rec in self:
            try:
                rec._check_facturas_pagadas()
            except Exception as e:
                _logger.error(f"Error al sincronizar estado del Quedán {rec.name}: {e}")
        return records

    def action_paid(self):
        """Permite marcar manualmente el Quedán como pagado."""
        for rec in self:
            rec.state = 'paid'

    def download_quedan(self):
        """Genera y devuelve el PDF del Quedán."""
        self.ensure_one()
        _logger.info(f"Generando reporte PDF para el Quedán {self.name}")

        # Ejecutar el reporte definido en XML
        return self.env.ref("l10n_sv_quedan.report_quedan_documento").report_action(self)
