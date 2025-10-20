# -*- coding: utf-8 -*-
# ------------------------------------------------------------
# Qué es un Quedán:
#   Documento interno de “promesa de pago” a proveedor. Agrupa facturas
#   y fija una fecha objetivo para pagarlas. El estado del Quedán se
#   deriva del estado real de pago de esas facturas.
#
# Requisitos:
#   - Secuencia 'account.quedan' (ir.sequence).
#   - Reporte QWeb 'l10n_sv_quedan.report_quedan_documento'.
#   - Plantilla email 'l10n_sv_quedan.email_template_quedan'.
# ------------------------------------------------------------

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging
import base64
from email.utils import parseaddr, formataddr
from odoo.tools.misc import ustr
import base64, re
try:
    import unicodedata
except Exception:
    unicodedata = None

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
        default=lambda self: self.env.company.currency_id.id,
        help="Moneda en que se presentan los importes del Quedán.",
    )

    # ========= Datos funcionales =========
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

    # --- Facturas ya tomadas por otros Quedanes (para excluirlas del selector)
    taken_invoice_ids = fields.Many2many(
        'account.move',
        compute='_compute_taken_invoice_ids',
        compute_sudo=True,
        string='Facturas ya usadas',
        help='Facturas que ya pertenecen a otro Quedán.',
    )

    # Facturas a cubrir (solo bills publicadas con saldo y que NO estén en otro quedán)
    factura_ids = fields.Many2many(
        'account.move',
        string="Facturas vinculadas",
        domain="""
            [
                ('move_type', '=', 'in_invoice'),
                ('state', '=', 'posted'),
                ('company_id', '=', company_id),
                ('partner_id', '=', partner_id),
                ('payment_state', 'in', ('not_paid','partial')),
                ('amount_residual', '>', 0),
                ('id', 'not in', taken_invoice_ids)
            ]
        """,
        help="Facturas de proveedor con saldo pendiente para incluir en este Quedán."
    )

    # Estado del ciclo de vida
    state = fields.Selection(
        [
            ('draft', 'Borrador'),  # editable
            ('confirmed', 'Confirmado'),
            ('overdue', 'Vencido'),  # no todas pagadas y fecha programada ya pasó
            ('paid', 'Pagado'),  # todas pagadas
        ],
        string="Estado",
        default="draft",
        tracking=True,
        help="Estado del Quedán según las facturas, fecha programada y pagos.",
    )

    # Total de facturas (monetario con currency_id)
    monto_total = fields.Monetary(
        string="Monto total",
        compute="_compute_monto_total",
        currency_field="currency_id",
        store=True,
        help="Suma de los totales de las facturas vinculadas.",
    )

    @api.depends('factura_ids.amount_total')
    def _compute_monto_total(self):
        for rec in self:
            rec.monto_total = sum(rec.factura_ids.mapped('amount_total'))

    # ========= Pagos relacionados (computado) =========
    payments_ids = fields.Many2many(
        'account.payment',
        string="Pagos relacionados",
        compute="_compute_payments",
        store=False,
        readonly=True,
        help="Pagos detectados por conciliación con las facturas del Quedán.",
    )

    def _compute_payments(self):
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

    # ========= Acciones =========
    def action_confirm(self):
        """Confirma el Quedán (debe tener facturas y ninguna en 'paid')."""
        for rec in self:
            if not rec.factura_ids:
                raise UserError(_("Agrega al menos una factura al Quedán antes de confirmar."))
            if rec.factura_ids.filtered(lambda f: f.payment_state == 'paid'):
                raise UserError(_("No puedes confirmar el Quedán con facturas ya pagadas."))
            rec.state = 'confirmed'
            rec._check_facturas_pagadas()

    def action_reset(self):
        """Vuelve el documento a 'Borrador'."""
        for rec in self:
            rec.state = 'draft'

    def action_paid(self):
        """Marca manualmente el Quedán como 'Pagado'."""
        for rec in self:
            rec.state = 'paid'

    # ========= Sincronización de estado =========
    def _check_facturas_pagadas(self):
        """Sincroniza estado con facturas y fecha programada."""
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
        """Acción para generar/descargar el PDF del Quedán (QWeb)."""
        self.ensure_one()
        _logger.info("Generando reporte PDF para el Quedán %s", self.name)
        return self.env.ref("l10n_sv_quedan.report_quedan_documento").report_action(self)

    def action_send_email(self):
        """Renderiza el PDF del Quedán y lo envía por correo con la plantilla configurada,
           mostrando mensaje de éxito o error."""
        self.ensure_one()
        active_langs = set(self.env['res.lang'].search([('active', '=', True)]).mapped('code'))
        candidates = [self.env.user.lang, self.env.context.get('lang'), 'es_419', 'en_US']
        lang_ctx = next((c for c in candidates if c and c in active_langs), 'en_US')

        template = self.env.ref('l10n_sv_quedan.email_template_quedan', raise_if_not_found=False)
        if not template:
            raise UserError(_("No se encontró la plantilla de correo 'email_template_quedan'."))
        if not self.partner_id.email:
            raise UserError(_("El proveedor no tiene un correo configurado."))

        # ----- Render PDF -----
        report = self.env.ref('l10n_sv_quedan.report_quedan_documento', raise_if_not_found=False)
        pdf_content, out_ext = self.env['ir.actions.report'].with_context(lang=lang_ctx)._render_qweb_pdf(
            report.report_name, [self.id]
        )
        filename = f"Quedan_{self.name.replace('/', '_')}.pdf"
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(pdf_content),
            'res_model': 'account.quedan',
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })

        # ----- Validación y normalización del From -----
        raw_from = (self.company_id.email_from_quedan
                    or self.company_id.email_formatted
                    or self.env.user.email_formatted
                    or '').replace('\r', ' ').replace('\n', ' ').strip()

        name, addr = parseaddr(raw_from)
        if not addr or '@' not in addr:
            raise UserError(_("Remitente Quedán inválido. Configura un correo válido en "
                              "Ajustes → Compañías → Correos de envío."))

        try:
            addr.encode('ascii')
        except UnicodeEncodeError:
            raise UserError(
                _("El correo remitente debe ser ASCII simple (sin tildes ni caracteres especiales): %s") % addr)

        def _sanitize_name(n):
            n = (n or '').replace('\r', ' ').replace('\n', ' ').strip()
            n = re.sub(r'\s+', ' ', n)
            if unicodedata:
                try:
                    n = unicodedata.normalize('NFKD', n).encode('ascii', 'ignore').decode('ascii')
                except Exception:
                    pass
            return n

        name = _sanitize_name(name)
        email_from_norm = formataddr((name, addr)) if name else addr

        # ----- Envío del correo -----
        email_values = {
            'attachment_ids': [(6, 0, [attachment.id])],
            'email_from': email_from_norm,
        }
        if self.company_id.smtp_quedan_id:
            email_values['mail_server_id'] = self.company_id.smtp_quedan_id.id

        try:
            template.with_context(lang=lang_ctx).send_mail(self.id, force_send=True, email_values=email_values)
        except Exception as e:
            # Error → mensaje tipo UserError (modal) y rollback
            raise UserError(_("No se pudo enviar el correo: %s") % ustr(e))

        # Éxito → log al chatter y toast de confirmación (no hace rollback)
        self.message_post(body=_("Correo enviado al proveedor %s con el Quedán adjunto.") % self.partner_id.name)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Quedán"),
                'message': _("Correo enviado con éxito a %s") % (self.partner_id.email or ''),
                'type': 'success',  # success | warning | danger | info
                'sticky': False,
            }
        }

    # ========= Datos derivados para el domain del M2M =========
    @api.depends('company_id', 'partner_id')
    def _compute_taken_invoice_ids(self):
        """Obtiene las facturas que ya están en otros Quedanes para excluirlas del selector."""
        for rec in self:
            if not rec.company_id:
                rec.taken_invoice_ids = self.env['account.move']
                continue
            dom = [('id', '!=', rec.id), ('company_id', '=', rec.company_id.id)]
            if rec.partner_id:
                dom.append(('partner_id', '=', rec.partner_id.id))
            others = self.env['account.quedan'].search(dom)
            rec.taken_invoice_ids = others.mapped('factura_ids')

    # ========= Validaciones =========
    @api.constrains('factura_ids', 'company_id', 'partner_id')
    def _check_invoices_not_in_other_quedan(self):
        """Servidor: evita guardar un quedán con facturas que ya están en otro quedán."""
        for rec in self:
            if not rec.factura_ids:
                continue
            others = self.env['account.quedan'].search([
                ('id', '!=', rec.id),
                ('company_id', '=', rec.company_id.id),
                ('factura_ids', 'in', rec.factura_ids.ids),
            ])
            if others:
                used_ids = set(others.mapped('factura_ids').ids) & set(rec.factura_ids.ids)
                used = self.env['account.move'].browse(list(used_ids))
                raise ValidationError(_(
                    "Las siguientes facturas ya están asociadas a otro Quedán:\n- %s"
                ) % ("\n- ".join(used.mapped('name'))))

    @api.constrains('factura_ids')
    def _check_factura_count(self):
        """Servidor: mínimo 1 factura y máximo 5."""
        for rec in self:
            count = len(rec.factura_ids)
            if count == 0:
                raise ValidationError(_("Un Quedán debe tener al menos 1 factura."))
            if count > 5:
                raise ValidationError(_("Un Quedán no puede tener más de 5 facturas."))

    @api.onchange('factura_ids')
    def _onchange_factura_ids_limit(self):
        """UX: recorta a 5 en la edición y muestra aviso (no molesta al entrar)."""
        for rec in self:
            if len(rec.factura_ids) > 5:
                rec.factura_ids = rec.factura_ids[:5]
                return {
                    'warning': {
                        'title': _("Límite alcanzado"),
                        'message': _("Solo puedes agregar hasta 5 facturas al Quedán."),
                    }
                }
