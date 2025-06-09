# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from .amount_to_text_sv import to_word
import base64

import logging

_logger = logging.getLogger(__name__)
import base64
import json


class AccountMove(models.Model):
    _inherit = 'account.move'

    apply_retencion_iva = fields.Boolean(string="Aplicar Retención IVA")
    retencion_iva_amount = fields.Monetary(string="Monto Retención IVA", currency_field='currency_id',
                                           compute='_compute_retencion', readonly=True, store=True)

    apply_retencion_renta = fields.Boolean(string="Aplicar Retención Renta")
    retencion_renta_amount = fields.Monetary(string="Monto Retención Renta", currency_field='currency_id',
                                           compute='_compute_retencion', readonly=True, store=True)

    inv_refund_id = fields.Many2one('account.move',
                                    'Factura Relacionada',
                                    copy=False,
                                    track_visibility='onchange')

    state_refund = fields.Selection([
        ('refund', 'Retificada'),
        ('no_refund', 'No Retificada'),
    ],
        string="Retificada",
        index=True,
        readonly=True,
        default='no_refund',
        track_visibility='onchange',
        copy=False)

    amount_text = fields.Char(string=_('Amount to text'),
                              store=True,
                              readonly=True,
                              compute='_amount_to_text',
                              track_visibility='onchange')
    descuento_gravado_pct = fields.Float(string='Descuento Gravado (%)', default=0.0)
    descuento_exento_pct = fields.Float(string='Descuento Exento (%)', default=0.0)
    descuento_no_sujeto_pct = fields.Float(string='Descuento No Sujeto (%)', default=0.0)

    descuento_gravado = fields.Float(string='Monto Desc. Gravado', store=True, compute='_compute_descuentos')
    descuento_exento = fields.Float(string='Monto Desc. Exento', store=True, compute='_compute_descuentos')
    descuento_no_sujeto = fields.Float(string='Monto Desc. No Sujeto', store=True, compute='_compute_descuentos')
    total_descuento = fields.Float(string='Total descuento', default=0.00, store=True,
                                   compute='_compute_total_descuento', )

    descuento_global = fields.Float(string='Monto Desc. Global', default=0.00, store=True,
                                    compute='_compute_descuento_global', inverse='_inverse_descuento_global')

    descuento_global_monto = fields.Float(
        string='Descuento global (%)',
        store=True,
        readonly=False,
        default=0.0,
    )

    total_no_sujeto = fields.Float(string='Total operaciones no sujetas', store=True, compute='_compute_totales_sv')
    total_exento = fields.Float(string='Total operaciones exentas', store=True, compute='_compute_totales_sv')
    total_gravado = fields.Float(string='Total operaciones gravadas', store=True, compute='_compute_totales_sv')
    sub_total_ventas = fields.Float(string='Sumatoria de Ventas', store=True, compute='_compute_totales_sv')

    amount_total_con_descuento = fields.Monetary(
        string="Total con descuento global",
        store=True,
        readonly=True,
        compute="_compute_total_con_descuento",
        currency_field='currency_id'
    )

    sub_total = fields.Float(string='Subtotal', default=0.0, compute='_compute_total_con_descuento', store=True)
    total_operacion = fields.Float(string='Total Operacion', default=0.0, compute='_compute_total_con_descuento',
                                   store=True)
    total_pagar = fields.Float(string='Total a Pagar', default=0.0, compute='_compute_total_con_descuento', store=True)
    total_pagar_text = fields.Char(
        string='Total a Pagar en Letras',
        compute='_compute_total_pagar_text',
        store=True
    )

    @api.depends('total_pagar')
    def _compute_total_pagar_text(self):
        for move in self:
            move.total_pagar_text = to_word(move.total_pagar)

    @api.depends('apply_retencion_renta', 'apply_retencion_iva', 'amount_total')
    def _compute_retencion(self):
        for move in self:
            base_total = move.sub_total_ventas - move.descuento_global
            move.retencion_renta_amount = 0.0
            move.retencion_iva_amount = 0.0

            if move.apply_retencion_renta:
                move.retencion_renta_amount = base_total * 0.10
            if move.apply_retencion_iva:
                tipo_doc = move.journal_id.sit_tipo_documento.codigo
                if tipo_doc in ["01", "03"]:  # FCF y CCF
                    move.retencion_iva_amount = base_total * 0.01  # 1% para estos tipos
                else:
                    move.retencion_iva_amount = base_total * 0.13  # 13% general

    def _create_retencion_renta_line(self):
        cuenta_retencion = self.env.ref('mi_modulo.cuenta_retencion_renta')  # Asegúrate de definir esto correctamente
        for move in self:
            if move.state != 'draft':
                continue  # Solo aplicar en borrador

            if not move.apply_retencion_renta or not cuenta_retencion:
                continue

            existe_linea = move.line_ids.filtered(
                lambda l: l.account_id == cuenta_retencion and l.name == "Retención de Renta"
            )
            if not existe_linea:
                move.line_ids += self.env['account.move.line'].new({
                    'name': "Retención de Renta",
                    'account_id': cuenta_retencion.id,
                    'move_id': move.id,
                    'credit': move.retencion_renta_amount,
                    'debit': 0.0,
                    'partner_id': move.partner_id.id,
                })

    def _post(self, soft=True):
        self._create_retencion_renta_line()
        return super()._post(soft=soft)

    @api.depends('amount_total')
    def _amount_to_text(self):
        for l in self:
            l.amount_text = to_word(l.amount_total)

    def print_pos_retry(self):
        return self.action_invoice_print()

    def action_invoice_print(self):
        """ Print the invoice and mark it as sent, so that we can see more
        easily the next step of the workflow
    """
        user_admin = self.env.ref("base.user_admin")
        if any(not move.is_invoice(include_receipts=True) for move in self):
            raise UserError(_("Solo se pueden imprimir facturas."))
        self.filtered(lambda inv: not inv.is_move_sent).write({'is_move_sent': True})

        report = self.journal_id.type_report
        report_xml = self.journal_id.report_xml.xml_id

        if report_xml:
            return self.env.ref(report_xml).with_user(user_admin).report_action(self)

        return self.env.ref('account.account_invoices').with_user(user_admin).report_action(self)

    def msg_error(self, campo):
        raise ValidationError("No puede emitir un documento si falta un campo Legal " \
                              "Verifique %s" % campo)

    def _post(self, soft=True):
        '''validamos que partner cumple los requisitos basados en el tipo
        de documento de la sequencia del diario selecionado'''
        for invoice in self:
            if invoice.move_type != 'entry':
                type_report = invoice.journal_id.type_report

                if type_report == 'fcf':
                    if not invoice.partner_id.parent_id:
                        if not invoice.partner_id.vat:
                            # invoice.msg_error("N.I.T.")
                            pass
                        if invoice.partner_id.company_type == 'person':
                            if not invoice.partner_id.dui:
                                # invoice.msg_error("D.U.I.")
                                pass
                    else:
                        if not invoice.partner_id.parent_id.fax:
                            # invoice.msg_error("N.I.T.")
                            pass
                        if invoice.partner_id.parent_id.company_type == 'person':
                            if not invoice.partner_id.dui:
                                # invoice.msg_error("D.U.I.")
                                pass

                if type_report == 'exp':
                    for l in invoice.invoice_line_ids:
                        if not l.product_id.arancel_id:
                            invoice.msg_error("Posicion Arancelaria del Producto %s" % l.product_id.name)

                # si es retificativa
                if type_report == 'ndc':
                    if not invoice.partner_id.parent_id:
                        if not invoice.partner_id.nrc:
                            invoice.msg_error("N.R.C.")
                        if not invoice.partner_id.fax:
                            invoice.msg_error("N.I.T.")
                        if not invoice.partner_id.codActividad:
                            invoice.msg_error("Actividad Economica")
                    else:
                        if not invoice.partner_id.parent_id.nrc:
                            invoice.msg_error("N.R.C.")
                        if not invoice.partner_id.parent_id.fax:
                            invoice.msg_error("N.I.T.")
                        if not invoice.partner_id.parent_id.codActividad:
                            invoice.msg_error("Actividad Economica")

        return super(AccountMove, self)._post()

    # ---------------------------------------------------------------------------------------------------------

    def sit_action_send_mail(self):
        _logger.info("SIT enviando correo = %s", self)
        """ Open a window to compose an email, with the edi invoice template
            message loaded by default
        """
        # self.ensure_one()
        # template = self.env.ref(self._get_mail_template_sv(), raise_if_not_found=False)
        # lang = False
        # if template:
        #    lang = template._render_lang(self.ids)[self.id]
        # if not lang:
        #    lang = get_lang(self.env).code
        # compose_form = self.env.ref('account.account_invoice_send_wizard_form', raise_if_not_found=False)
        # ctx = dict(
        #    default_model='account.move',
        #    default_res_id=self.id,
        #    default_res_model='account.move',
        #    default_use_template=bool(template),
        #    default_template_id=template and template.id or False,
        #    default_composition_mode='comment',
        #    default_is_print=False,
        #    mark_invoice_as_sent=True,
        #    default_email_layout_xmlid="mail.mail_notification_layout_with_responsible_signature",
        #    model_description=self.with_context(lang=lang).type_name,
        #    force_email=True,
        #    active_ids=self.ids,
        # )
        #
        # report_action = {
        #    'name': _('Enviar Factura_por email'),
        #    'type': 'ir.actions.act_window',
        #    'view_type': 'form',
        #    'view_mode': 'form',
        #    'res_model': 'account.invoice.send',
        #    'views': [(compose_form.id, 'form')],
        #    'view_id': compose_form.id,
        #    'target': 'new',
        #    'context': ctx,
        # }
        #
        # if self.env.is_admin() and not self.env.company.external_report_layout_id and not self.env.context.get('discard_logo_check'):
        #    return self.env['ir.actions.report']._action_configure_external_report_layout(report_action)
        # return report_action

        # template = self.env.ref(self._get_mail_template(), raise_if_not_found=False)
        template = self.env.ref(self._get_mail_template_sv(), raise_if_not_found=False)
        _logger.info("SIT | Plantilla de correo obtenida: %s", template and template.name or 'No encontrada')
        print(template)

        # Archivos adjuntos
        attachment_ids = []
        for invoice in self:
            _logger.info("SIT | Procesando factura: %s", invoice.name)
            print(invoice)

            report_xml = invoice.journal_id.report_xml.xml_id if invoice.journal_id.report_xml else False
            _logger.info("SIT | XML ID del reporte: %s", report_xml)

            # Adjuntos base (los de la plantilla)
            if template:
                for att in template.attachment_ids:
                    if att.id not in attachment_ids:
                        attachment_ids.append(att.id)

            # Verificar si ya existe un PDF adjunto
            pdf_filename = f"{invoice.name or 'invoice'}.pdf"
            pdf_attachment = self.env['ir.attachment'].search([
                ('res_id', '=', invoice.id),
                ('res_model', '=', 'account.move'),
                ('name', '=', pdf_filename),
            ], limit=1)

            # Generar PDF si no existe
            if not pdf_attachment and report_xml:
                try:
                    res = self.env['ir.actions.report'].sudo()._render_qweb_pdf(report_xml, [invoice.id])[0]
                    pdf_binary = base64.encodebytes(res)
                    pdf_attachment = self.env['ir.attachment'].create({
                        'name': pdf_filename,
                        'type': 'binary',
                        'datas': pdf_binary,
                        'res_model': 'account.move',
                        'res_id': invoice.id,
                        'mimetype': 'application/pdf',
                    })
                    _logger.info("SIT | Nuevo PDF generado y adjuntado: %s", pdf_attachment.name)
                except Exception as e:
                    _logger.error("SIT | Error generando el PDF: %s", str(e))
            if pdf_attachment and pdf_attachment.id not in attachment_ids:
                attachment_ids.append(pdf_attachment.id)

            # if report_xml:
            # user_admin = self.env.ref("base.user_admin")
            # _logger.info("SIT | Usuario admin encontrado: %s", user_admin.name)
            # compo = self.env.ref(report_xml).with_user(user_admin).report_action(self)
            # print(report)
            # res = report.with_context().sudo()._render_qweb_pdf(report.id)
            # res = self.env['ir.actions.report'].sudo()._render_qweb_pdf(report_xml, [invoice.id])[0]
            # _logger.info("SIT | PDF generado correctamente para factura: %s", invoice.name)
            # print(compo)
            # print(res)
            # attachment1 = self.env['ir.attachment'].create({
            #    'name': invoice.name + '.pdf',
            #    'type': 'binary',
            #    'datas': base64.encodebytes(res),
            #    'res_model': 'account.move',
            #    'res_id': invoice.id,
            #    })
            # print(attachment1)
            # Verificar si el objeto tiene el atributo 'hacienda_estado'

            # Si fue procesado por Hacienda, añadir JSON
            if invoice.hacienda_estado == 'PROCESADO' or invoice.recibido_mh:
                _logger.info("SIT | Factura %s fue PROCESADA por Hacienda", invoice.name)
                json_attachment = self.env['ir.attachment'].search([
                    ('res_id', '=', invoice.id),
                    ('res_model', '=', invoice._name),
                    ('name', '=', invoice.name.replace('/', '_') + '.json')
                ], limit=1)

                if json_attachment and json_attachment.id not in attachment_ids:
                    _logger.info("SIT | Archivo JSON de Hacienda encontrado: %s", json_attachment.name)
                    attachment_ids.append(json_attachment.id)
                    # attachments.append((invoice.name.replace('/', '_') + '.json', xml_file.datas))
                    # attachments.append((invoice.name + '.pdf',base64.encodebytes(res)))
                    # print(attachments)
                    # results[res_id]['attachments'] = attachments
                    # template.attachment_ids = [attachment1.id,xml_file.id]
                else:
                    _logger.info("SIT | JSON de Hacienda no encontrado.")
            # template.checkbox_download = False

        if any(not x.is_sale_document(include_receipts=True) for x in self):
            _logger.warning("SIT | Documento no permitido para envío por correo.")

        # Validar si viene de un envío automático
        if self.env.context.get('from_automatic'):
            _logger.info("SIT | Envío automático detectado, enviando correo directamente...")
            for invoice in self:
                if template:
                    template.send_mail(invoice.id, force_send=True,
                                       email_values={'attachment_ids': [(6, 0, attachment_ids)]})
                invoice.correo_enviado = True  # si manejas este campo
            return True
        # return {
        #     'name': _("Send"),
        #     'type': 'ir.actions.act_window',
        #     'view_type': 'form',
        #     'view_mode': 'form',
        #     'res_model': 'account.move.send',
        #     'target': 'new',
        #     'context': {
        #         'active_ids': self.ids,
        #         'default_mail_template_id': template and template.id or False,
        #     },
        # }
        # Si no es automático, abrir modal
        compose_form = self.env.ref('mail.email_compose_message_wizard_form', raise_if_not_found=True)
        return {
            'name': _("Send"),
            'type': 'ir.actions.act_window',
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'view_id': compose_form.id,
            'target': 'new',
            'context': {
                'default_model': 'account.move',
                'default_res_ids': self.ids,
                'default_use_template': bool(template),
                'default_template_id': template.id if template else False,
                'default_composition_mode': 'comment',
                'force_email': True,
                'mark_invoice_as_sent': True,
                'default_attachment_ids': [(6, 0, list(set(attachment_ids)))],
            },
        }

    def _get_mail_template_sv(self):
        """
        :return: the correct mail template based on the current move type
        """
        return (
            'account.email_template_edi_credit_note'
            if all(move.move_type == 'out_refund' for move in self)
            else 'l10n_invoice_sv.sit_email_template_edi_invoice'
            # else 'account.sit_email_template_edi_invoice'
        )

    def sit_enviar_correo_dte(self):
        for invoice in self:
            # Validar que el DTE exista en hacienda
            if not invoice.recibido_mh:
                _logger.warning("SIT | La factura %s no tiene un DTE procesado, no se enviará correo.", invoice.name)
                continue

            _logger.info("SIT | DTE procesado correctamente para la factura %s. Procediendo con envío de correo.",
                         invoice.name)

            # Generar PDF como attachment si aún no se ha creado
            try:
                report_xml = invoice.journal_id.report_xml.xml_id
                pdf_content = invoice.env['ir.actions.report'].sudo()._render_qweb_pdf(report_xml, [invoice.id])[0]
                pdf_base64 = base64.b64encode(pdf_content)
                pdf_filename = f"{invoice.name or 'dte'}.pdf"

                # Verifica si ya existe un attachment con ese nombre
                existing_attachment = self.env['ir.attachment'].sudo().search([
                    ('res_model', '=', 'account.move'),
                    ('res_id', '=', invoice.id),
                    ('name', '=', pdf_filename),
                ], limit=1)

                if not existing_attachment:
                    self.env['ir.attachment'].sudo().create({
                        'name': pdf_filename,
                        'datas': pdf_base64,
                        'res_model': 'account.move',
                        'res_id': invoice.id,
                        'mimetype': 'application/pdf',
                        'type': 'binary',
                    })
                    _logger.info("SIT | PDF generado y adjuntado: %s", pdf_filename)
                else:
                    _logger.info("SIT | El attachment PDF ya existe para el dte %s", invoice.name)
            except Exception as e:
                _logger.error("SIT | Error generando PDF para la factura %s: %s", invoice.name, str(e))
                continue

            # Enviar el correo automáticamente solo si el DTE fue aceptado y aún no se ha enviado
            if invoice.recibido_mh:
                try:
                    _logger.info("SIT | Enviando correo automático para la factura %s", invoice.name)
                    invoice.with_context(from_automatic=True).sudo().sit_action_send_mail()
                except Exception as e:
                    _logger.error("SIT | Error al intentar enviar el correo para la factura %s: %s", invoice.name,
                                  str(e))
            else:
                _logger.info("SIT | Ya se envio el correo %s", invoice.name)

    # -------Inicio Descuentos globales
    # @api.depends('invoice_line_ids.precio_gravado', 'invoice_line_ids.precio_exento', 'invoice_line_ids.precio_no_sujeto')
    # def _compute_totales_tipo_venta(self):
    #     for move in self:
    #         total_gravado = total_exento = total_no_sujeto = 0.0
    #         for line in move.invoice_line_ids:
    #             _logger.info("SIT Precio exento: %s, gravado: %s, no sujeto: %s", line.precio_exento, line.precio_gravado, line.precio_no_sujeto)
    #
    #             total_gravado += line.precio_gravado
    #             total_exento += line.precio_exento
    #             total_no_sujeto += line.precio_no_sujeto
    #
    #         move.total_gravado = total_gravado
    #         move.total_exento = total_exento
    #         move.total_no_sujeto = total_no_sujeto

    @api.depends('invoice_line_ids.price_unit', 'invoice_line_ids.quantity', 'invoice_line_ids.discount',
                 'invoice_line_ids.product_id.tipo_venta')
    def _compute_totales_sv(self):
        for move in self:
            move._calcular_totales_sv()

    # @api.onchange('invoice_line_ids')
    # def _onchange_invoice_line_ids(self):
    #     for move in self:
    #         move._calcular_totales_sv()

    def _calcular_totales_sv(self):
        for move in self:
            gravado = exento = no_sujeto = 0.0
            for line in move.invoice_line_ids:
                # if move.journal_id.sit_tipo_documento.codigo != "01":
                #     subtotal = (line.price_unit * line.quantity * (1 - (line.discount or 0.0) / 100.0)) / 1.13
                # else:
                #     subtotal = line.price_unit * line.quantity * (1 - (line.discount or 0.0) / 100.0)

                tipo = line.product_id.tipo_venta
                if tipo == 'gravado':
                    gravado += line.precio_gravado
                elif tipo == 'exento':
                    exento += line.precio_exento
                elif tipo == 'no_sujeto':
                    no_sujeto += line.precio_no_sujeto

            move.total_gravado = max(gravado, 0.0)
            move.total_exento = max(exento, 0.0)
            move.total_no_sujeto = max(no_sujeto, 0.0)
            move.sub_total_ventas = move.total_gravado + move.total_exento + move.total_no_sujeto

            _logger.info("SIT Onchange: cambios asignados a los campos en memoria: %s", move.sub_total_ventas)

    @api.depends('descuento_gravado', 'descuento_exento', 'descuento_no_sujeto',
                 'invoice_line_ids.price_unit', 'invoice_line_ids.quantity', 'invoice_line_ids.discount', 'apply_retencion_renta', 'apply_retencion_iva', 'retencion_renta_amount', 'retencion_iva_amount')
    def _compute_total_descuento(self):
        for move in self:
            total_descuentos_globales = (
                    move.descuento_gravado +
                    move.descuento_exento +
                    move.descuento_no_sujeto
            )

            total_descuentos_lineas = 0.0
            for line in move.invoice_line_ids:
                if line.price_unit and line.quantity and line.discount:
                    monto_descuento_linea = line.price_unit * line.quantity * (line.discount / 100.0)
                    total_descuentos_lineas += monto_descuento_linea

            move.total_descuento = total_descuentos_globales + total_descuentos_lineas

    @api.depends('descuento_gravado_pct', 'descuento_exento_pct', 'descuento_no_sujeto_pct',
                 'invoice_line_ids.price_unit', 'invoice_line_ids.quantity',
                 'invoice_line_ids.product_id.tipo_venta')
    def _compute_descuentos(self):
        for move in self:
            gravado = exento = no_sujeto = 0.0
            for line in move.invoice_line_ids:
                subtotal = line.price_unit * line.quantity
                tipo = line.product_id.tipo_venta
                if tipo == 'gravado':
                    gravado += subtotal
                elif tipo == 'exento':
                    exento += subtotal
                elif tipo == 'no_sujeto':
                    no_sujeto += subtotal

            move.descuento_gravado = gravado * move.descuento_gravado_pct / 100
            move.descuento_exento = exento * move.descuento_exento_pct / 100
            move.descuento_no_sujeto = no_sujeto * move.descuento_no_sujeto_pct / 100

    @api.depends('amount_total', 'descuento_global', 'sub_total_ventas', 'descuento_no_sujeto', 'descuento_exento',
                 'descuento_gravado', 'amount_tax', 'apply_retencion_renta', 'apply_retencion_iva')
    def _compute_total_con_descuento(self):
        for move in self:
            # 1. Obtener montos
            subtotal_base = move.sub_total_ventas
            descuento_global = move.descuento_global

            # 2. Aplicar descuento global solo sobre la sumatoria de ventas
            subtotal_con_descuento_global = max(subtotal_base - descuento_global, 0.0)
            move.amount_total_con_descuento = subtotal_con_descuento_global
            _logger.info(f"[{move.name}] sub_total_ventas: {subtotal_base}, descuento_global: {descuento_global}, "
                         f"subtotal_con_descuento_global: {subtotal_con_descuento_global}")

            # 3. Calcular descuentos detalle
            descuentos_detalle = move.descuento_no_sujeto + move.descuento_exento + move.descuento_gravado

            # 4. Calcular sub_total final restando otros descuentos
            move.sub_total = max(subtotal_con_descuento_global - descuentos_detalle, 0.0)

            _logger.info(f"[{move.name}] descuentos no sujeto/exento/gravado: "
                         f"{move.descuento_no_sujeto}/{move.descuento_exento}/{move.descuento_gravado}, "
                         f"sub_total final: {move.sub_total}")

            # 5. Calcular total_operacion y total_pagar
            if move.journal_id.sit_tipo_documento.codigo != "01":
                move.total_operacion = move.sub_total + move.amount_tax
                _logger.info(f"[{move.name}] Documento no es tipo 01, total_operacion: {move.total_operacion}")
            else:
                move.total_operacion = move.sub_total
                _logger.info(f"[{move.name}] Documento tipo 01, total_operacion: {move.total_operacion}")

            move.total_pagar = move.total_operacion - (move.retencion_renta_amount + move.retencion_iva_amount)

            _logger.info(f"{move.journal_id.sit_tipo_documento.codigo}] move.journal_id.sit_tipo_documento.codigo")

            _logger.info(f"[{move.name}] sub_total: {move.sub_total}")
            _logger.info(f"[{move.name}] total_descuento: {move.total_descuento}")
            _logger.info(f"[{move.name}] move.retencion_renta_amount + move.retencion_iva_amount: {move.retencion_renta_amount + move.retencion_iva_amount}")

            _logger.info(f"[{move.name}] total_pagar: {move.total_pagar}")

    @api.depends('descuento_global_monto', 'sub_total_ventas')
    def _compute_descuento_global(self):
        for move in self:
            move.descuento_global = (move.sub_total_ventas or 0.0) * (move.descuento_global_monto or 0.0) / 100.0
            _logger.info("SIT descuento_global: %.2f aplicado sobre sub_total %.2f (%.2f%%)", move.descuento_global,
                         move.sub_total_ventas, move.descuento_global_monto)

    def _inverse_descuento_global(self):
        for move in self:
            if move.sub_total_ventas:
                move.descuento_global_monto = (move.descuento_global / move.sub_total_ventas) * 100
            else:
                move.descuento_global_monto = 0.0

    @api.depends(
        'invoice_line_ids.precio_gravado', 'invoice_line_ids.precio_exento', 'invoice_line_ids.precio_no_sujeto',
        'invoice_line_ids.price_unit', 'invoice_line_ids.quantity', 'invoice_line_ids.discount',
        'invoice_line_ids.product_id.tipo_venta',
        'descuento_gravado_pct', 'descuento_exento_pct', 'descuento_no_sujeto_pct', 'descuento_global_monto',
        'amount_tax')
    def _recalcular_resumen_documento(self):
        for move in self:
            move._calcular_totales_sv()
            move._compute_descuentos()
            move._compute_total_descuento()
            move._compute_descuento_global()
            move._compute_total_con_descuento()

    # -------Fin descuentos

    # -------Retenciones
    def agregar_lineas_retencion(self):
        for move in self:
            if move.state != 'draft':
                continue

            lineas = []

            # Retención Renta
            if move.apply_retencion_renta and move.retencion_renta_amount > 0:
                cuenta_renta = move.company_id.retencion_renta_account_id
                ya_existe_renta = move.line_ids.filtered(
                    lambda l: l.account_id == cuenta_renta and l.name == "Retención de Renta"
                )
                if cuenta_renta and not ya_existe_renta:
                    lineas.append((0, 0, {
                        'account_id': cuenta_renta.id,
                        'name': "Retención de Renta",
                        'credit': move.retencion_renta_amount,
                        'debit': 0.0,
                        'partner_id': move.partner_id.id,
                    }))

            # Retención IVA
            if move.apply_retencion_iva and move.retencion_iva_amount > 0:
                cuenta_iva = move.company_id.retencion_iva_account_id
                ya_existe_iva = move.line_ids.filtered(
                    lambda l: l.account_id == cuenta_iva and l.name == "Retención de IVA"
                )
                if cuenta_iva and not ya_existe_iva:
                    lineas.append((0, 0, {
                        'account_id': cuenta_iva.id,
                        'name': "Retención de IVA",
                        'credit': move.retencion_iva_amount,
                        'debit': 0.0,
                        'partner_id': move.partner_id.id,
                    }))

            if lineas:
                move.write({'line_ids': lineas})
    # -------Fin retenciones

    # -------Creacion de apunte contable para los descuentos
    # Actualizar apuntes contables
    def action_post(self):
        for move in self:
            _logger.info(f"[action_post] Procesando factura ID {move.id} con número {move.name}")
            if move.state != 'draft':
                continue

            # Solo llamar a agregar_lineas_descuento_a_borrador si hay descuento global
            if (move.descuento_gravado_pct and move.descuento_gravado_pct > 0) \
                    or (move.descuento_exento_pct and move.descuento_exento_pct > 0) \
                    or (move.descuento_no_sujeto_pct and move.descuento_no_sujeto_pct > 0) \
                    or (move.descuento_global_monto and move.descuento_global_monto > 0):
                _logger.info(
                    f"[action_post] La factura tiene descuento global de {move.descuento_global}, agregando línea contable.")
                move.agregar_lineas_descuento()
            else:
                _logger.info("[action_post] No hay descuento global, no se agrega línea contable.")

            # if move.apply_retencion_renta or move.apply_retencion_iva:
            #     move.agregar_lineas_retencion()
            move.agregar_lineas_retencion()
        return super().action_post()

    # Crear o buscar la cuenta contable para descuentos
    def obtener_cuenta_descuento(self):
        self.ensure_one()
        codigo_cuenta = self.company_id.account_discount_id.code  # '5103'

        cuenta = self.env['account.account'].search([
            ('code', '=', codigo_cuenta)
        ], limit=1)

        if cuenta:
            _logger.info(f"[obtener_cuenta_descuento] Cuenta encontrada: {cuenta.code} - {cuenta.name}")
            return cuenta
        else:
            _logger.warning(
                f"[obtener_cuenta_descuento] No se encontró una cuenta contable con código '{codigo_cuenta}'.")
            raise UserError("No se ha configurado una cuenta de descuento global para la empresa.")

    # Agregar las líneas al asiento contable
    def agregar_lineas_descuento(self):
        for move in self:
            _logger.info(f"[agregar_lineas_descuento_a_borrador] Evaluando factura ID {move.id} - Estado: {move.state}")
            cuenta_descuento = move.obtener_cuenta_descuento()

            descuentos = {
                'Descuento sobre ventas gravadas': move.descuento_gravado,
                'Descuento sobre ventas exentas': move.descuento_exento,
                'Descuento sobre ventas no sujetas': move.descuento_no_sujeto,
                'Descuento global': move.descuento_global,
            }

            if all(monto <= 0 for monto in descuentos.values()):
                _logger.info("No hay descuentos aplicables.")
                continue

            es_nota_credito = move.move_type in ('out_refund', 'in_refund')
            es_factura_o_debito = move.move_type in ('out_invoice', 'in_invoice')
            _logger.info(f"Tipo de movimiento: {move.move_type} | Credito: {es_nota_credito} | Débito: {es_factura_o_debito}")

            nuevas_lineas = []
            for nombre, monto in descuentos.items():
                if monto <= 0:
                    continue

                # Buscar línea existente
                linea = move.line_ids.filtered(lambda l: l.name == nombre and l.account_id == cuenta_descuento)
                valores = {
                    'debit': monto if es_factura_o_debito else 0.0,
                    'credit': monto if es_nota_credito else 0.0,
                }

                if linea:
                    if (linea.debit != valores['debit'] or linea.credit != valores['credit']):
                        _logger.info(f"Actualizando línea existente '{nombre}' con monto {monto}")
                        linea.write(valores)
                else:
                    _logger.info(f"Agregando nueva línea de descuento: '{nombre}' con monto {monto}")
                    nuevas_lineas.append((0, 0, {
                        'account_id': cuenta_descuento.id,
                        'name': nombre,
                        'custom_discount_line': True,
                        **valores,
                    }))

            if nuevas_lineas:
                _logger.info("Lineas de factura: %s", nuevas_lineas)
                move.write({'line_ids': nuevas_lineas})

class AccountMoveSend(models.AbstractModel):
    _inherit = 'account.move.send'

    def _get_placeholder_mail_attachments_data(self, move):
        """ Returns all the placeholder data.
        Should be extended to add placeholder based on the checkboxes.
        :param: move:       The current move.
        :returns: A list of dictionary for each placeholder.
        * id:               str: The (fake) id of the attachment, this is needed in rendering in t-key.
        * name:             str: The name of the attachment.
        * mimetype:         str: The mimetype of the attachment.
        * placeholder       bool: Should be true to prevent download / deletion.
        """
        if move.invoice_pdf_report_id:
            return []

        filename = move._get_invoice_report_filename()
        # return [{
        #    'id': f'placeholder_{filename}',
        #    'name': filename,
        #    'mimetype': 'application/pdf',
        #    'placeholder': True,
        # }]

        return []

    @api.model
    def _get_invoice_extra_attachments_data(self, move):
        print(")))))))))))))))))))))))))))qqq")
        print(self.env.context.get('active_ids', []))
        invoice = self.env['account.move'].browse(self.env.context.get('active_ids', []))
        print(invoice)
        report = invoice.journal_id.report_xml
        report_xml = invoice.journal_id.report_xml.xml_id
        if report_xml:
            user_admin = self.env.ref("base.user_admin")
            compo = self.env.ref(report_xml).with_user(user_admin).report_action(self)
            res = self.env['ir.actions.report'].sudo()._render_qweb_pdf(report_xml, [invoice.id])[0]
        # Verificar si el objeto tiene el atributo 'hacienda_estado'
        if invoice.hacienda_estado == 'PROCESADO':
            domain = [
                ('name', '=', invoice.name.replace('/', '_') + '.json')]
            xml_file = self.env['ir.attachment'].search(domain, limit=1)
            domain2 = [('res_id', '=', invoice.id),
                       ('res_model', '=', invoice._name),
                       ('mimetype', '=', 'application/pdf')]
            xml_file2 = self.env['ir.attachment'].search(domain2, limit=1)
            if not xml_file2:
                xml_file2 = self.env['ir.attachment'].create({
                    'name': invoice.name + ' FE' + '.pdf',
                    'type': 'binary',
                    'datas': base64.encodebytes(res),
                    'res_model': 'account.move',
                    'res_id': invoice.id,
                })

            attachments = []
            print(xml_file)
            if xml_file:
                attachments = []
                attachments.append(xml_file)
                attachments.append(xml_file2)

        print(attachments)

        res = [
            {
                'id': attachment.id,
                'name': attachment.name,
                'mimetype': attachment.mimetype,
                'placeholder': False,
                'protect_from_deletion': True,
            }
            for attachment in attachments
        ]

        print(res)
        return res

    @api.depends('enable_download')
    def _compute_checkbox_download(self):
        for wizard in self:
            wizard.checkbox_download = False
