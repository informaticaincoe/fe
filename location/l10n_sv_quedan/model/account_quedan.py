# -*- coding: utf-8 -*-
# ------------------------------------------------------------
# Qué es un Quedán:
#   Documento interno de “promesa de pago” a proveedor. Agrupa facturas
#   y fija una fecha objetivo para pagarlas. El estado del Quedán se
#   deriva del estado real de pago de esas facturas.
#
# Principios de diseño:
#   - El estado del Quedán (draft/confirmed/paid) se calcula mirando
#     payment_state de las facturas adjuntas al quedan
#
# Requisitos:
#   - Secuencia 'account.quedan' (ir.sequence).
#   - Reporte QWeb 'l10n_sv_quedan.report_quedan_documento'.
#   - Plantilla email 'l10n_sv_quedan.email_template_quedan'.
# ------------------------------------------------------------

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.exceptions import UserError
import logging
import base64

_logger = logging.getLogger(__name__)


class AccountQuedan(models.Model):
    """Objeto Quedán (promesa de pago a proveedor)."""
    _name = "account.quedan"
    _description = "Quedán de Proveedor"
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']  # chatter + actividades

    # ========= Identificación y metadatos =========
    name = fields.Char(
        string="Número de Quedán",
        required=True,
        copy=False,
        # Se toma de la secuencia técnica 'account.quedan'
        default=lambda self: self.env['ir.sequence'].next_by_code('account.quedan'),
        help="Identificador del Quedán; proviene de la secuencia 'account.quedan'.",
    )
    company_id = fields.Many2one(
        'res.company',
        string="Empresa",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        help="Compañía propietaria del documento.",
    )
    currency_id = fields.Many2one(
        'res.currency',
        string="Moneda",
        required=True,
        default=lambda self: self.env.company.currency_id.id,  # usar .id evita recordsets
        help="Moneda en que se presentan los importes del Quedán.",
    )

    # ========= Datos funcionales del Quedán =========
    partner_id = fields.Many2one(
        'res.partner',
        string="Proveedor",
        required=True,
        domain=[('supplier_rank', '>', 0)],
        help="Proveedor beneficiario del Quedán.",
    )
    fecha_programada = fields.Date(
        string="Fecha programada de pago",
        required=True,
        help="Fecha objetivo para ejecutar el pago (promesa).",
    )
    observaciones = fields.Text(
        string="Observaciones",
        help="Notas internas o condiciones del Quedán.",
    )

    # Facturas a cubrir (solo facturas de proveedor)
    factura_ids = fields.Many2many(
        'account.move',
        string="Facturas vinculadas",
        domain="[('move_type','=','in_invoice')]",
        help="Facturas de proveedor incluidas en este Quedán.",
    )

    # Estado del ciclo de vida (simple)
    state = fields.Selection(
        [
            ('draft', 'Borrador'),  # editable
            ('confirmed', 'Confirmado'),  # listo para pagar
            ('overdue', 'Vencido'),  # no todas pagadas y fecha programada ya pasó
            ('paid', 'Pagado'),  # todas pagadas
        ],
        string="Estado",
        default="draft",
        tracking=True,
        help="Estatus del Quedán según las facturas, fecha programada y pagos.",
    )

    # Total de facturas (monetario con currency_id)
    monto_total = fields.Monetary(
        string="Monto total",
        compute="_compute_monto_total",
        currency_field="currency_id",
        store=True,  # útil para filtrar/ordenar sin recalcular
        help="Suma de los totales de las facturas vinculadas. "
             "Si quieres el saldo comprometido, usa amount_residual en el compute.",
    )

    @api.depends('factura_ids.amount_total')
    def _compute_monto_total(self):
        """Suma amount_total de las facturas.
        - Si mezclas monedas, aquí puedes convertir a company_id.currency_id
          antes de sumar para tener un total homogéneo.
        """
        for rec in self:
            rec.monto_total = sum(rec.factura_ids.mapped('amount_total'))

    # ========= Pagos relacionados (computado, sin acoplar) =========
    payments_ids = fields.Many2many(
        'account.payment',
        string="Pagos relacionados",
        compute="_compute_payments",
        store=False,
        readonly=True,
        help="Pagos detectados por conciliación con las facturas del Quedán.",
    )

    def _compute_payments(self):
        """Deriva pagos por conciliación:
        1) Tomar los apuntes contables de las facturas (line_ids).
        2) Recolectar movimientos contables contrapartida conciliados (matched_*).
        3) Buscar pagos cuyos asientos (move_id) sean esas contrapartidas.
        No guarda relación permanente; se calcula a demanda.
        """
        for rec in self:
            payments = self.env['account.payment']
            if rec.factura_ids:
                amls = rec.factura_ids.mapped('line_ids')
                counterpart_moves = (
                    amls.mapped('matched_debit_ids.debit_move_id.move_id')
                    | amls.mapped('matched_credit_ids.credit_move_id.move_id')
                )
                if counterpart_moves:
                    payments = self.env['account.payment'].search([
                        ('move_id', 'in', counterpart_moves.ids)
                    ])
            rec.payments_ids = payments

    # ========= Acciones de ciclo de vida =========
    def action_confirm(self):
        """Confirma el Quedán.
        Reglas:
          - Debe tener al menos una factura.
          - Rechaza si hay facturas ya pagadas (no tendría sentido prometer pagarlas).
        Después de confirmar, revisa el estado por si ya existen pagos conciliados.
        """
        for rec in self:
            if not rec.factura_ids:
                raise UserError(_("Agrega al menos una factura al Quedán antes de confirmar."))
            if rec.factura_ids.filtered(lambda f: f.payment_state == 'paid'):
                raise UserError(_("No puedes confirmar el Quedán con facturas ya pagadas."))
            rec.state = 'confirmed'
            rec._check_facturas_pagadas()

    def action_reset(self):
        """Vuelve el documento a 'Borrador'. No altera facturas ni pagos."""
        for rec in self:
            rec.state = 'draft'

    def action_paid(self):
        """Marca manualmente el Quedán como 'Pagado'.
        Uso excepcional: normalmente el estado cambia solo cuando
        todas las facturas vinculadas están en 'paid'.
        """
        for rec in self:
            rec.state = 'paid'

    # ========= Sincronización de estado según facturas =========
    def _check_facturas_pagadas(self):
        """Sincroniza el estado del Quedán con facturas y fecha programada:
        - Sin facturas → draft
        - Todas pagadas → paid
        - Si NO todas pagadas:
            * con fecha_programada < hoy → overdue
            * en otro caso → confirmed
        """
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.factura_ids:
                rec.state = 'draft'
                continue

            todas_pagadas = all(f.payment_state == 'paid' for f in rec.factura_ids)

            if todas_pagadas:
                if rec.state != 'paid':
                    rec.state = 'paid'
                    _logger.info("[AUTO] El Quedán %s pasó a estado PAGADO.", rec.name)
                continue

            # No todas pagadas → revisar vencimiento
            if rec.fecha_programada and rec.fecha_programada < today:
                if rec.state != 'overdue':
                    rec.state = 'overdue'
                    _logger.info("[AUTO] El Quedán %s pasó a estado VENCIDO.", rec.name)
            else:
                if rec.state != 'confirmed':
                    rec.state = 'confirmed'

    # Hook de lectura: refresca estado al abrir (mejora UX).
    # Evita abrir cientos a la vez en bases con MUCHAS conciliaciones (costo).
    def read(self, fields=None, load='_classic_read'):
        """Al abrir el Quedán, actualiza su estado para reflejar pagos recientes."""
        records = super().read(fields=fields, load=load)
        for rec in self:
            try:
                rec._check_facturas_pagadas()
            except Exception as e:
                _logger.error("Error al sincronizar estado del Quedán %s: %s", rec.name, e)
        return records

    # ========= Reporte y envío por correo =========
    def download_quedan(self):
        """Devuelve la acción para generar/descargar el PDF del Quedán (QWeb)."""
        self.ensure_one()
        _logger.info("Generando reporte PDF para el Quedán %s", self.name)
        return self.env.ref("l10n_sv_quedan.report_quedan_documento").report_action(self)

    def action_send_email(self):
        """Renderiza el PDF del Quedán y lo envía por correo con la plantilla configurada."""
        self.ensure_one()

        # Idioma preferido: usuario → contexto → es_419 → en_US
        active_langs = set(self.env['res.lang'].search([('active', '=', True)]).mapped('code'))
        candidates = [self.env.user.lang, self.env.context.get('lang'), 'es_419', 'en_US']
        lang_ctx = next((c for c in candidates if c and c in active_langs), 'en_US')

        # Plantilla de correo
        template = self.env.ref('l10n_sv_quedan.email_template_quedan', raise_if_not_found=False)
        if not template:
            raise UserError(_("No se encontró la plantilla de correo 'email_template_quedan'."))
        if not self.partner_id.email:
            raise UserError(_("El proveedor no tiene un correo configurado."))

    # Validacion para agregar maximo 5 facturas
    @api.constrains('factura_ids')
    def _check_max_5_facturas(self):
        for rec in self:
            if len(rec.factura_ids) > 5:
                raise ValidationError(_("Un Quedán no puede tener más de 5 facturas."))

    # Mensaje de error maximo 5 facturas
    @api.onchange('factura_ids')
    def _onchange_factura_ids_limit(self):
        for rec in self:
            if len(rec.factura_ids) > 5:
                # Corta al top-5 (evita guardar el 6º visualmente)
                rec.factura_ids = rec.factura_ids[:5]
                return {
                    'warning': {
                        'title': _("Límite alcanzado"),
                        'message': _("Solo puedes agregar hasta 5 facturas al Quedán."),
                    }
                }
