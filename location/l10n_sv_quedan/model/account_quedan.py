from odoo import models, fields, api
from odoo.exceptions import UserError
import logging
import base64

_logger = logging.getLogger(__name__)


class AccountQuedan(models.Model):
    _name = "account.quedan"
    _description = "Quedán de Proveedor"
    _order = "id desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']

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

    company_id = fields.Many2one(
        'res.company',
        string="Empresa",
        required=True,
        default=lambda self: self.env.company,
        index=True
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
        self.ensure_one()
        _logger.info(f"Generando reporte PDF para el Quedán {self.name}")
        return self.env.ref("l10n_sv_quedan.report_quedan_documento").report_action(self)

    def action_send_email(self):
        self.ensure_one()

        # === 1) Seleccionar idioma válido ===
        active_langs = set(self.env['res.lang'].search([('active', '=', True)]).mapped('code'))
        candidates = [
            self.env.user.lang,
            self.env.context.get('lang'),
            'es_419',  # español latino
            'en_US',  # fallback
        ]
        lang_ctx = next((c for c in candidates if c and c in active_langs), 'en_US')

        # === 2) Obtener plantilla de correo ===
        template = self.env.ref('l10n_sv_quedan.email_template_quedan', raise_if_not_found=False)
        if not template:
            raise UserError("No se encontró la plantilla de correo 'email_template_quedan'.")
        if not self.partner_id.email:
            raise UserError("El proveedor no tiene un correo configurado.")

        template_ctx = template.with_context(lang=lang_ctx)

        # === 3) Obtener acción de reporte ===
        report_action = self.env.ref('l10n_sv_quedan.report_quedan_documento', raise_if_not_found=False)
        if not report_action:
            raise UserError("No se encontró el reporte configurado para el Quedán.")
        if report_action.model != 'account.quedan':
            raise UserError("El reporte configurado no corresponde al modelo account.quedan.")

        # === 4) Renderizar el PDF ===
        pdf_content, _ = self.env['ir.actions.report'].with_context(lang=lang_ctx)._render_qweb_pdf(
            report_action.report_name, [self.id]
        )

        # === 5) Crear adjunto ===
        filename = f"Quedan_{self.name.replace('/', '_')}.pdf"
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(pdf_content),
            'res_model': 'account.quedan',
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })

        # === 6) Enviar correo ===
        try:
            template_ctx.send_mail(self.id, force_send=True, email_values={
                'attachment_ids': [(6, 0, [attachment.id])],
            })
            _logger.info("Correo enviado a %s con archivo %s", self.partner_id.email, filename)
            self.message_post(body=f"Correo enviado al proveedor {self.partner_id.name} con el Quedán adjunto.")
        except Exception as e:
            raise UserError(f"Error al enviar el correo: {str(e)}")

        return True
