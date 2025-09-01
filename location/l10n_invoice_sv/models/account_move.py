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

    codigo_tipo_documento = fields.Char(
        related='journal_id.sit_tipo_documento.codigo',
        store=True
    )

    apply_retencion_iva = fields.Boolean(string="Aplicar Retención IVA")
    retencion_iva_amount = fields.Monetary(string="Monto Retención IVA", currency_field='currency_id',
                                           compute='_compute_retencion', readonly=True, store=True)

    apply_retencion_renta = fields.Boolean(string="Aplicar Retención Renta")
    retencion_renta_amount = fields.Monetary(string="Monto Retención Renta", currency_field='currency_id',
                                           compute='_compute_retencion', readonly=True, store=True)

    apply_iva_percibido = fields.Boolean(string="Aplicar IVA percibido")
    iva_percibido_amount = fields.Monetary(string="Monto iva percibido", currency_field='currency_id',
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
    descuento_gravado_pct = fields.Float(string='Descuento Gravado', default=0.0)
    descuento_exento_pct = fields.Float(string='Descuento Exento', default=0.0)
    descuento_no_sujeto_pct = fields.Float(string='Descuento No Sujeto', default=0.0)

    descuento_gravado = fields.Float(string='Monto Desc. Gravado', store=True, compute='_compute_descuentos')
    descuento_exento = fields.Float(string='Monto Desc. Exento', store=True, compute='_compute_descuentos')
    descuento_no_sujeto = fields.Float(string='Monto Desc. No Sujeto', store=True, compute='_compute_descuentos')
    total_descuento = fields.Float(string='Total descuento', default=0.00, store=True,
                                   compute='_compute_total_descuento', )

    descuento_global = fields.Float(string='Monto Desc. Global', default=0.00, store=True,
                                    compute='_compute_descuento_global', inverse='_inverse_descuento_global')

    descuento_global_monto = fields.Float(
        string='Descuento global',
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

    sale_order_id = fields.Many2one('sale.order', string='Orden de Venta', compute='_compute_sale_order_id', store=False)

    seguro = fields.Float(string='Seguro', default=0.0)
    flete = fields.Float(string='Flete', default=0.0)

    def _compute_sale_order_id(self):
        for move in self:
            sale_orders = move.invoice_line_ids.mapped('sale_line_ids.order_id')
            move.sale_order_id = sale_orders[:1] if sale_orders else False
            _logger.info("SIT Cotizacion: %s", move.sale_order_id)

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
            move.iva_percibido_amount = 0.0

            if move.apply_retencion_renta:
                move.retencion_renta_amount = base_total * 0.10

            _logger.info("base total %s", base_total)
            _logger.info(" move.retencion_renta_amount %s",  move.retencion_renta_amount)

            if move.apply_retencion_iva:
                tipo_doc = move.journal_id.sit_tipo_documento.codigo
                # if tipo_doc in ["01", "03"]:  # FCF y CCF
                #     move.retencion_iva_amount = round(((move.sub_total_ventas / 1.13) - move.descuento_global) * 0.01, 2) #En FCF y CCF la retencion es del %
                # else:
                #     move.retencion_iva_amount = round(base_total * 0.13, 2)  # 13% general

                if tipo_doc in ["14"]:  # FCF y CCF
                    move.retencion_iva_amount = round(base_total * 0.13, 2)  # 13% general
                else:
                    move.retencion_iva_amount = round(((move.sub_total_ventas / 1.13) - move.descuento_global) * 0.01,2)  # En FCF y CCF la retencion es del %
            if move.apply_iva_percibido:
                tipo_doc = move.journal_id.sit_tipo_documento.codigo
                move.iva_percibido_amount = ((move.sub_total_ventas / 1.13) - move.descuento_global) * 0.01

    # def _post(self, soft=True):
    #     self._create_retencion_renta_line()
    #     return super()._post(soft=soft)

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

    # def _post(self, soft=True):
    #     '''validamos que partner cumple los requisitos basados en el tipo
    #     de documento de la sequencia del diario selecionado'''
    #     for invoice in self:
    #         _logger.info("PRUEBA EN _POST accounT MOVE -------------- %s", invoice.move_type)
    #         if invoice.move_type != 'entry':
    #
    #             type_report = invoice.journal_id.type_report
    #             _logger.info("Tipo dte=%s", type_report)
    #
    #             _logger.info("invoice.company_id.sit_facturacion:=%s", invoice.company_id.sit_facturacion)
    #             if invoice.company_id.sit_facturacion:
    #                 if type_report == 'fcf':
    #                     if not invoice.partner_id.parent_id:
    #                         if not invoice.partner_id.vat:
    #                             # invoice.msg_error("N.I.T.")
    #                             pass
    #                         if invoice.partner_id.company_type == 'person':
    #                             if not invoice.partner_id.dui:
    #                                 # invoice.msg_error("D.U.I.")
    #                                 pass
    #                     else:
    #                         if not invoice.partner_id.parent_id.vat:
    #                             # invoice.msg_error("N.I.T.")
    #                             pass
    #                         if invoice.partner_id.parent_id.company_type == 'person':
    #                             if not invoice.partner_id.dui:
    #                                 # invoice.msg_error("D.U.I.")
    #                                 pass
    #
    #                 if type_report == 'exp':
    #                     for l in invoice.invoice_line_ids:
    #                         if l and l.product_id and not l.product_id.arancel_id:
    #                             _logger.info("Producto: =%s", l)
    #                             invoice.msg_error("Posicion Arancelaria del Producto %s" % l.product_id.name)
    #
    #                 # si es retificativa
    #                 if type_report == 'ndc':
    #                     if not invoice.partner_id.parent_id:
    #                         if not invoice.partner_id.nrc:
    #                             invoice.msg_error("N.R.C.")
    #                         if not invoice.partner_id.vat:
    #                             invoice.msg_error("N.I.T.")
    #                         if not invoice.partner_id.codActividad:
    #                             invoice.msg_error("Actividad Economica")
    #                     else:
    #                         if not invoice.partner_id.parent_id.nrc:
    #                             invoice.msg_error("N.R.C.")
    #                         if not invoice.partner_id.parent_id.vat:
    #                             invoice.msg_error("N.I.T.")
    #                         if not invoice.partner_id.parent_id.codActividad:
    #                             invoice.msg_error("Actividad Economica")
    #             else:
    #                 #Flujo de facturas preimpresas
    #                 if not invoice.name or invoice.name == '/':
    #                     raise UserError("Debe asignar el número de la factura preimpresa.")
    #
    #
    #     return super(AccountMove, self)._post()

    # ---------------------------------------------------------------------------------------------------------
    #No se esta utilizando
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
        es_invalidacion = self.env.context.get('from_invalidacion', False)
        if es_invalidacion:
            _logger.info("SIT | El correo se enviará como parte de una invalidación.")
        else:
            _logger.info("SIT | El correo se enviará como parte de un DTE procesado normalmente.")

        default_model = None
        try:
            # template = self.env.ref(self._get_mail_template(), raise_if_not_found=False)

            template = self.env.ref(self._get_mail_template_sv(), raise_if_not_found=False)

            _logger.info("SIT | Plantilla de correo obtenida: %s", template and template.name or 'No encontrada')
            print(template)

            _logger.warning("SIT | Email del partner: %s", self.partner_id.email)
            if template and template.email_to:
                email_to = template._render_template(template.email_to, 'account.move', self.ids)

                _logger.info("Email a enviar: %s", email_to)

                # Asegurarse que el correo es válido
                if not email_to:
                    _logger.error("El correo destinatario no es válido: %s", email_to)
                    return False

                template.subject = self._sanitize_string(template.subject, "subject")
                template.body_html = self._sanitize_string(template.body_html, "body_html")
                template.email_from = self._sanitize_string(template.email_from, "email_from")
                _logger.info("SIT | template from: %s", template.email_from)

            # Archivos adjuntos
            attachment_ids = []
            for invoice in self:
                _logger.info("SIT | Procesando factura: %s", invoice.name)
                print(invoice)

                report_xml = invoice.journal_id.report_xml.xml_id if invoice.journal_id.report_xml else False
                _logger.info("SIT | XML ID del reporte: %s", report_xml)

                # Adjuntar archivos de la plantilla, evitando PDFs
                if template:
                    for att in template.attachment_ids:
                        if att.id not in attachment_ids and not att.name.lower().endswith('.pdf'):
                            attachment_ids.append(att.id)

                # Verificar si ya existe un PDF adjunto
                raw_filename = f"{invoice.name or 'invoice'}.pdf"
                pdf_filename = self._sanitize_attachment_name(raw_filename)

                pdf_attachment = self.env['ir.attachment'].search([
                    ('res_id', '=', invoice.id),
                    ('res_model', '=', 'account.move'),
                    ('name', '=', pdf_filename),
                ], limit=1)

                # Generar PDF si no existe
                if not pdf_attachment and report_xml:  # and report_xml
                    try:
                        res = self.env['ir.actions.report'].sudo()._render_qweb_pdf(report_xml, [invoice.id])[0]
                        pdf_base64 = base64.b64encode(res).decode('utf-8')  # codificar a base64 y luego a string
                        pdf_attachment = self.env['ir.attachment'].create({
                            'name': pdf_filename,
                            'type': 'binary',
                            'datas': pdf_base64,
                            'res_model': 'account.move',
                            'res_id': invoice.id,
                            'mimetype': 'application/pdf',
                        })
                        _logger.info("SIT | Nuevo PDF generado y adjuntado: %s", pdf_attachment.name)
                    except Exception as e:
                        _logger.error("SIT | Error generando el PDF: %s", str(e))

                # Adjuntar el PDF si no está duplicado
                if pdf_attachment:
                    if self._has_nul_bytes(pdf_attachment):
                        _logger.warning("SIT | PDF %s contiene byte nulo en contenido", pdf_attachment.name)
                    if pdf_attachment.id not in attachment_ids:
                        attachment_ids.append(pdf_attachment.id)
                        _logger.info("SIT | Adjuntando PDF desde BD: %s", pdf_attachment.name)
                    else:
                        _logger.info("SIT | PDF ya estaba incluido en attachment_ids: %s", pdf_attachment.name)

                _logger.info("SIT | Tipo de movimiento: %s", invoice.move_type)
                _logger.info("SIT | Email destino: %s", invoice.partner_id.email)
                if invoice.company_id.sit_facturacion:
                    if not es_invalidacion and (invoice.hacienda_selloRecibido or invoice.recibido_mh):
                        _logger.info("SIT | Factura %s fue PROCESADA por Hacienda", invoice.name)
                        default_model = "account.move"
                        json_name = self._sanitize_attachment_name(invoice.name.replace('/', '_') + '.json')
                        json_attachment = self.env['ir.attachment'].search([
                            ('res_id', '=', invoice.id),
                            ('res_model', '=', invoice._name),
                            ('name', '=', json_name)
                        ], limit=1)

                        _logger.warning("SIT | JSON: %s", json_attachment)
                        if json_attachment.exists():
                            _logger.warning("SIT | JSON encontrado: %s", json_attachment)
                            if self._has_nul_bytes(json_attachment):
                                _logger.warning("SIT | JSON %s contiene byte nulo en contenido", json_attachment.name)
                            if json_attachment.id not in attachment_ids:
                                _logger.info("SIT | JSON de Hacienda encontrado: %s", json_attachment.name)
                                attachment_ids.append(json_attachment.id)
                                _logger.info("SIT | Archivo JSON de Hacienda encontrado: %s", json_attachment.name)
                        else:
                            _logger.info("SIT | JSON de Hacienda no encontrado, se procederá a generarlo.")

                            if invoice.sit_json_respuesta:
                                try:
                                    # Validar si el contenido es JSON válido
                                    json.loads(invoice.sit_json_respuesta)

                                    # Crear attachment
                                    json_attachment = self.env['ir.attachment'].create({
                                        'name': json_name,
                                        'type': 'binary',
                                        'datas': base64.b64encode(invoice.sit_json_respuesta.encode('utf-8')),
                                        'res_model': invoice._name,
                                        'res_id': invoice.id,
                                        'mimetype': 'application/json',
                                    })
                                    _logger.info("SIT | JSON generado y adjuntado: %s", json_attachment.name)
                                    attachment_ids.append(json_attachment.id)

                                except json.JSONDecodeError:
                                    _logger.error("SIT | El campo 'sit_json_respuesta' no contiene un JSON válido.")
                                except Exception as e:
                                    _logger.error("SIT | Error al generar el archivo JSON: %s", str(e))
                            else:
                                _logger.warning(
                                    "SIT | No se pudo generar el JSON porque el campo 'sit_json_respuesta' está vacío.")

                    # === JSON INVALIDACIÓN ===
                    elif es_invalidacion and (invoice.sit_evento_invalidacion.hacienda_selloRecibido_anulacion or invoice.sit_evento_invalidacion.invalidacion_recibida_mh):
                        default_model = "account.move.invalidation"
                        invalidacion = self.env['account.move.invalidation'].search([
                            ('sit_factura_a_reemplazar', '=', invoice.id)
                        ], limit=1)

                        if not invalidacion:
                            _logger.warning("SIT | No se encontró invalidación para %s", invoice.name)
                        else:
                            json_name = self._sanitize_attachment_name('invalidacion ' + invoice.name.replace('/',
                                                                                                              '_') + '.json')  # ejemplo de json de invalidacion Invalidacion DTE-01-0000M001-000000000000082.json
                            json_attachment = self.env['ir.attachment'].search([
                                ('res_model', '=', 'account.move.invalidation'),
                                ('res_id', '=', invoice.sit_evento_invalidacion.id),
                                ('name', '=', json_name),
                            ], limit=1)

                            if json_attachment.exists():
                                _logger.info("SIT | JSON Invalidación ya existe: %s", json_attachment.name)
                                if self._has_nul_bytes(json_attachment):
                                    _logger.warning("SIT | JSON %s contiene byte nulo", json_attachment.name)
                                attachment_ids.append(json_attachment.id)
                            elif invalidacion.sit_json_respuesta_invalidacion:
                                try:
                                    json.loads(invalidacion.sit_json_respuesta_invalidacion)
                                    json_attachment = self.env['ir.attachment'].create({
                                        'name': json_name,
                                        'type': 'binary',
                                        'datas': base64.b64encode(
                                            invalidacion.sit_json_respuesta_invalidacion.encode('utf-8')),
                                        'res_model': 'account.move.invalidation',
                                        'res_id': invoice.sit_evento_invalidacion.id,
                                        'mimetype': 'application/json',
                                    })
                                    _logger.info("SIT | JSON Invalidación generado: %s", json_attachment.name)
                                    attachment_ids.append(json_attachment.id)
                                except json.JSONDecodeError:
                                    _logger.error("SIT | JSON Invalidación inválido para %s", invoice.name)
                                except Exception as e:
                                    _logger.error("SIT | Error creando JSON Invalidación: %s", str(e))
                            else:
                                _logger.warning("SIT | Campo sit_json_respuesta_invalidacion vacío para %s", invoice.name)

            if any(not x.is_sale_document(include_receipts=True) for x in self):
                _logger.warning("SIT | Documento no permitido para envío por correo.")
            _logger.info("SIT | Attachments antes de enviar: %s", attachment_ids)

            # Validar si viene de un envío automático
            if self.env.context.get('from_automatic'):
                _logger.info("SIT | Envío automático detectado, enviando correo directamente...")
                for invoice in self:
                    if template:
                        if es_invalidacion:
                            if invoice.sit_evento_invalidacion:
                                template.send_mail(invoice.sit_evento_invalidacion.id, force_send=True, email_values={'attachment_ids': [(6, 0, attachment_ids)]})
                                invoice.sit_evento_invalidacion.correo_enviado_invalidacion = True
                                _logger.info("SIT | Correo de invalidación enviado para %s", invoice.name)
                            else:
                                _logger.warning("SIT | No se encontró evento de invalidación para %s", invoice.name)
                        else:
                            template.send_mail(invoice.id, force_send=True, email_values={'attachment_ids': [(6, 0, attachment_ids)]})
                            invoice.correo_enviado = True
                            _logger.info("SIT | Correo normal enviado para %s", invoice.name)
                return True

            # ENVÍO MANUAL: abrir wizard
            compose_form = self.env.ref('mail.email_compose_message_wizard_form', raise_if_not_found=True)
            return {
                'name': _("Send"),
                'type': 'ir.actions.act_window',
                'res_model': 'mail.compose.message',
                'view_mode': 'form',
                'view_id': compose_form.id,
                'target': 'new',
                'context': {
                    'default_model': default_model,
                    'default_res_ids': self.ids,
                    'default_use_template': bool(template),
                    'default_template_id': template.id if template else False,
                    'default_composition_mode': 'comment',
                    'force_email': True,
                    'mark_invoice_as_sent': True,
                    'default_attachment_ids': [(6, 0, list(set(attachment_ids)))],
                },
            }
        except Exception as e:
            _logger.error("SIT | Error en el proceso de envío de correo: %s", str(e))
            import traceback
            _logger.error("SIT | Traceback: %s", traceback.format_exc())
            raise

    @staticmethod
    def _sanitize_string(val, field_name=""):
        if val and '\x00' in val:
            _logger.warning("SIT | Caracter nulo detectado en campo '%s'. Será eliminado.", field_name)
            return val.replace('\x00', '')
        return val

    @staticmethod
    def _sanitize_attachment_name(name):
        if name and '\x00' in name:
            _logger.warning("SIT | Caracter nulo detectado en nombre de adjunto: %s", repr(name))
            return name.replace('\x00', '')
        return name

    @staticmethod
    def _has_nul_bytes(attachment):
        try:
            content = base64.b64decode(attachment.datas)
            return b'\x00' in content
        except Exception as e:
            _logger.error("SIT | Error decodificando contenido de %s: %s", attachment.name, e)
            return False

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
            gravado = exento = no_sujeto = compra = 0.0
            for line in move.invoice_line_ids:
                tipo = line.product_id.tipo_venta
                if tipo == 'gravado':
                    gravado += round(line.precio_gravado, 2)
                elif tipo == 'exento':
                    exento += round(line.precio_exento, 2)
                elif tipo == 'no_sujeto':
                    no_sujeto += round(line.precio_no_sujeto, 2)

                #Total de la compra
                if move.journal_id.sit_tipo_documento.codigo in ["14"]:
                    compra += round(line.quantity * (line.price_unit - (line.price_unit * (line.discount / 100))), 2)

            if move.journal_id.sit_tipo_documento.codigo in ["14"]:
                move.total_gravado = round(compra, 2)
            else:
                move.total_gravado = max(gravado, 0.0)
            move.total_exento = max(exento, 0.0)
            move.total_no_sujeto = max(no_sujeto, 0.0)
            move.sub_total_ventas = round((move.total_gravado + move.total_exento + move.total_no_sujeto), 2)

            _logger.info("SIT Onchange: cambios asignados a los campos en memoria: %s", move.sub_total_ventas)

    @api.depends('descuento_gravado', 'descuento_exento', 'descuento_no_sujeto',
                 'invoice_line_ids.price_unit', 'invoice_line_ids.quantity', 'invoice_line_ids.discount', 'apply_retencion_renta', 'apply_retencion_iva', 'retencion_renta_amount', 'retencion_iva_amount')
    def _compute_total_descuento(self):
        for move in self:
            total_descuentos_globales = round( (
                    move.descuento_gravado +
                    move.descuento_exento +
                    move.descuento_no_sujeto
            ), 2)

            total_descuentos_lineas = 0.0
            for line in move.invoice_line_ids:
                if line.price_unit and line.quantity and line.discount:
                    monto_descuento_linea = round(line.price_unit * line.quantity * (line.discount / 100.0), 2)
                    total_descuentos_lineas += monto_descuento_linea

            move.total_descuento = round(total_descuentos_globales + total_descuentos_lineas, 2)

    @api.depends('descuento_gravado_pct', 'descuento_exento_pct', 'descuento_no_sujeto_pct',
                 'invoice_line_ids.price_unit', 'invoice_line_ids.quantity',
                 'invoice_line_ids.product_id.tipo_venta')
    def _compute_descuentos(self):
        for move in self:
            gravado = exento = no_sujeto = 0.0

            _logger.info(f"Total gravados: {move.total_gravado}, exentos: {move.total_exento}, no sujetos: {move.total_no_sujeto}")
            move.descuento_gravado = round( (move.total_gravado * move.descuento_gravado_pct / 100), 2)
            move.descuento_exento = round( (move.total_exento * move.descuento_exento_pct / 100), 2)
            move.descuento_no_sujeto = round( (move.total_no_sujeto * move.descuento_no_sujeto_pct / 100), 2)
            _logger.info(f"Descuentos gravados: {move.descuento_gravado}, exentos: {move.descuento_exento}, no sujetos: {move.descuento_no_sujeto}")

    @api.depends('amount_total', 'descuento_global', 'sub_total_ventas', 'descuento_no_sujeto', 'descuento_exento',
                 'descuento_gravado', 'amount_tax', 'apply_retencion_renta', 'apply_retencion_iva', 'apply_iva_percibido', 'seguro', 'flete')
    def _compute_total_con_descuento(self):
        for move in self:
            # 1. Obtener montos
            subtotal_base = move.sub_total_ventas
            descuento_global = move.descuento_global

            # 2. Aplicar descuento global solo sobre la sumatoria de ventas
            subtotal_con_descuento_global = round( max(subtotal_base - descuento_global, 0.0), 2)
            move.amount_total_con_descuento = subtotal_con_descuento_global
            _logger.info(f"[{move.name}] sub_total_ventas: {subtotal_base}, descuento_global: {descuento_global}, "
                         f"subtotal_con_descuento_global: {subtotal_con_descuento_global}")

            # 3. Calcular descuentos detalle
            descuentos_detalle = round( (move.descuento_no_sujeto + move.descuento_exento + move.descuento_gravado), 2)

            # 4. Calcular sub_total final restando otros descuentos
            if move.journal_id.sit_tipo_documento.codigo in["14"]:
                move.sub_total = round(max(move.total_gravado - move.descuento_gravado, 0.0), 2)
            else:
                move.sub_total = round(max(subtotal_con_descuento_global - descuentos_detalle, 0.0), 2)

            _logger.info(f"[{move.name}] descuentos no sujeto/exento/gravado: "
                         f"{move.descuento_no_sujeto}/{move.descuento_exento}/{move.descuento_gravado}, "
                         f"sub_total final: {move.sub_total}")

            # 5. Calcular total_operacion y total_pagar
            if move.journal_id.sit_tipo_documento.codigo not in["01", "11"]:
                move.total_operacion = round(move.sub_total + move.amount_tax, 2)
                _logger.info(f"[{move.name}] Documento no es tipo 01, total_operacion: {move.total_operacion}")
            elif move.journal_id.sit_tipo_documento.codigo == "11":
                move.total_operacion = round((move.total_gravado - move.descuento_gravado - descuento_global) + move.amount_tax + move.seguro + move.flete, 2)
            else:
                move.total_operacion = move.sub_total
                _logger.info(f"[{move.name}] Documento tipo 01, total_operacion: {move.total_operacion}")

            if move.journal_id.sit_tipo_documento.codigo == "11":
                move.total_pagar = round( (move.total_operacion - move.retencion_renta_amount), 2)
            elif move.journal_id.sit_tipo_documento.codigo == "14":
                move.total_pagar = round((move.sub_total - move.retencion_iva_amount - move.retencion_renta_amount), 2)
            else:
                move.total_pagar = round((move.total_operacion - (move.retencion_renta_amount + move.retencion_iva_amount + move.iva_percibido_amount)), 2)

            _logger.info(f"{move.journal_id.sit_tipo_documento.codigo}] move.journal_id.sit_tipo_documento.codigo")
            _logger.info(f"Seguro= {move.seguro} | Flete= {move.flete} | Total operacion={move.total_operacion}")
            _logger.info(f"[{move.name}] sub_total: {move.sub_total}")
            _logger.info(f"[{move.name}] total_descuento: {move.total_descuento}")
            _logger.info(f"[{move.name}] move.retencion_renta_amount + move.retencion_iva_amount: {move.retencion_renta_amount + move.retencion_iva_amount}")

            _logger.info(f"[{move.name}] total_pagar: {move.total_pagar}")

    @api.depends('descuento_global_monto', 'sub_total_ventas')
    def _compute_descuento_global(self):
        for move in self:
            if move.journal_id.sit_tipo_documento.codigo in["11"]:
                move.descuento_global = round(((move.total_gravado or 0.0) * (move.descuento_global_monto or 0.0) / 100), 2)
            else:
                move.descuento_global = round( ((move.sub_total_ventas or 0.0) * ( move.descuento_global_monto or 0.0) / 100), 2)
            _logger.info("SIT descuento_global: %.2f aplicado sobre sub_total %.2f (%.2f%%)", move.descuento_global,
                         move.sub_total_ventas, move.descuento_global_monto)

    def _inverse_descuento_global(self):
        for move in self:
            if move.sub_total_ventas:
                move.descuento_global_monto = round( ((move.descuento_global / move.sub_total_ventas) * 100), 2)
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

            # Eliminar líneas de retención anteriores
            cuentas_retencion = [
                move.company_id.retencion_renta_account_id,
                move.company_id.retencion_iva_account_id,
                move.company_id.iva_percibido_account_id,
            ]
            cuentas_retencion = [c for c in cuentas_retencion if c]

            lineas_a_borrar = move.line_ids.filtered(
                lambda l: l.account_id in cuentas_retencion and l.name in (
                    "Retención de Renta", "Retención de IVA", "IVA percibido")
            )
            if lineas_a_borrar:
                _logger.info("SIT | Eliminando líneas antiguas de retención")
                lineas_a_borrar.unlink()

            # Detectar si es nota de crédito
            es_nota_credito_o_sujeto_excluido = move.codigo_tipo_documento in ('05', '14')

            # Retención de Renta
            if move.apply_retencion_renta and move.retencion_renta_amount > 0:
                cuenta_renta = move.company_id.retencion_renta_account_id
                monto = round(move.retencion_renta_amount, 2)
                lineas.append((0, 0, {
                    'account_id': cuenta_renta.id,
                    'name': "Retención de Renta",
                    'credit': monto if es_nota_credito_o_sujeto_excluido else 0.0,
                    'debit': 0.0 if es_nota_credito_o_sujeto_excluido else monto,
                    'partner_id': move.partner_id.id,
                }))
                _logger.info(f"RETENCION RENTA monto={monto}")

            # Retención de IVA
            if move.apply_retencion_iva and move.retencion_iva_amount > 0:
                cuenta_iva = move.company_id.retencion_iva_account_id
                monto = round(move.retencion_iva_amount, 2)
                lineas.append((0, 0, {
                    'account_id': cuenta_iva.id,
                    'name': "Retención de IVA",
                    'credit': monto if es_nota_credito_o_sujeto_excluido else 0.0,
                    'debit': 0.0 if es_nota_credito_o_sujeto_excluido else monto,
                    'partner_id': move.partner_id.id,
                }))
                _logger.info(f"RETENCION IVA monto={monto}")
                _logger.info(f"cuenta_iva retecion={cuenta_iva}")

            # IVA percibido
            # Percepción de IVA
            if move.apply_iva_percibido and move.iva_percibido_amount > 0:
                cuenta_iva = move.company_id.iva_percibido_account_id
                monto = move.iva_percibido_amount  # Usa directamente el valor redondeado previamente

                es_nota_credito = move.move_type == 'out_refund'
                es_factura_venta = move.move_type == 'out_invoice'

                lineas.append((0, 0, {
                    'account_id': cuenta_iva.id,
                    'name': "Percepción de IVA",
                    'credit': monto if es_nota_credito_o_sujeto_excluido else 0.0,
                    'debit': 0.0 if es_nota_credito_o_sujeto_excluido else monto,
                    'partner_id': move.partner_id.id,
                }))
                _logger.info(f"PERCEPCION IVA monto={monto} | "
                             f"{'CRÉDITO' if es_factura_venta else 'DÉBITO'}")

                _logger.info(f"PERCEPCION IVA monto={monto}")
                _logger.info(f"cuenta_iva={cuenta_iva}")

            if lineas:
                move.write({'line_ids': lineas})
                _logger.info(f"SIT | Nuevas líneas de retención escritas: {lineas}")

    # -------Fin retenciones

    # -------Creacion de apunte contable para los descuent|os
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
            move.agregar_lineas_seguro_flete()

        _logger.warning(f"[{self.name}] Total débitos: {sum(l.debit for l in self.line_ids)}, "f"Total créditos: {sum(l.credit for l in self.line_ids)}")

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
                _logger.info("No hay descuentos aplicables, saliendo.")
                continue

            es_nota_credito = move.move_type in ('out_refund', 'in_refund')
            es_factura_o_debito = move.move_type in ('out_invoice', 'in_invoice') and not move.journal_id.type == 'purchase'
            es_factura_compra = move.move_type == 'in_invoice' and move.journal_id.type == 'purchase'
            if es_factura_compra:
                es_nota_credito = True
            #else:
                #es_factura_o_debito = False
            _logger.info(f"Tipo de movimiento: {move.move_type} | Credito: {es_nota_credito} | Débito: {es_factura_o_debito} | FSE: {es_factura_compra}")

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

    def agregar_lineas_seguro_flete(self):
        for move in self:
            # Solo procesar si es factura de exportación
            if move.codigo_tipo_documento != '11':  # Ajusta según tu código real de exportación
                continue

            if move.move_type != 'out_invoice':
                raise UserError("Este método solo soporta facturas de cliente (out_invoice)")

            cuenta_exportacion = move.company_id.account_exportacion_id
            if not cuenta_exportacion:
                _logger.warning(
                    "[agregar_lineas_seguro_flete] No se encontró una cuenta contable configurada para exportación.")
                raise UserError("No se ha configurado una cuenta de exportación en la empresa.")

            _logger.info(
                f"[agregar_lineas_seguro_flete] Cuenta encontrada: {cuenta_exportacion.code} - {cuenta_exportacion.name}")

            cargos = {
                'Seguro': move.seguro or 0.0,
                'Flete': move.flete or 0.0,
            }

            if all(monto <= 0 for monto in cargos.values()):
                _logger.info("[agregar_lineas_seguro_flete] No hay cargos de seguro o flete.")
                continue

            nuevas_lineas = []
            for nombre, monto in cargos.items():
                if monto <= 0:
                    continue

                linea = move.line_ids.filtered(lambda l: l.name == nombre and l.account_id == cuenta_exportacion)

                valores = {'debit': 0.0, 'credit': monto}

                if linea:
                    if linea.debit != valores['debit'] or linea.credit != valores['credit']:
                        _logger.info(f"Actualizando línea existente '{nombre}' con monto {monto}")
                        linea.write(valores)
                else:
                    _logger.info(f"Agregando nueva línea de exportación: '{nombre}' con monto {monto}")
                    nuevas_lineas.append((0, 0, {
                        'account_id': cuenta_exportacion.id,
                        'name': nombre,
                        'custom_discount_line': True,
                        **valores,
                    }))

            if nuevas_lineas:
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
