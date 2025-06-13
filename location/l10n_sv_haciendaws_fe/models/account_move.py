##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from odoo.tools import float_repr
#from odoo.addons.l10n_sv_haciendaws_fe.afip_utils import get_invoice_number_from_response
import base64
import pyqrcode
import qrcode
import os
from PIL import Image
import io


base64.encodestring = base64.encodebytes
import json
import requests

import logging
import sys
import traceback
from datetime import datetime, timedelta
import pytz

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    hacienda_estado = fields.Char(
        copy=False,
        string="Estado DTE",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    hacienda_codigoGeneracion = fields.Char(
        copy=False,
        string="Codigo de Generación",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    hacienda_codigoGeneracion_identificacion = fields.Char(
        copy=False,
        string="Codigo de Generación de Identificación",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    hacienda_selloRecibido = fields.Char(
        copy=False,
        string="Sello Recibido",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    hacienda_clasificaMsg = fields.Char(
        copy=False,
        string="Cladificación",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    hacienda_codigoMsg = fields.Char(
        copy=False,
        string="Codigo de Mensaje",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    hacienda_descripcionMsg = fields.Char(
        copy=False,
        string="Descripción",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    hacienda_observaciones = fields.Char(
        copy=False,
        string="Observaciones",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )

    afip_auth_mode = fields.Selection(
        [("CAE", "CAE"), ("CAI", "CAI"), ("CAEA", "CAEA")],
        string="AFIP authorization mode",
        copy=False,
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    afip_auth_code = fields.Char(
        copy=False,
        string="CAE/CAI/CAEA Code",
        readonly=True,
        size=24,
        states={"draft": [("readonly", False)]},
    )
    afip_auth_code_due = fields.Date(
        copy=False,
        readonly=True,
        string="CAE/CAI/CAEA due Date",
        states={"draft": [("readonly", False)]},
    )
    afip_associated_period_from = fields.Date(
        'AFIP Period from'
    )
    afip_associated_period_to = fields.Date(
        'AFIP Period to'
    )
    afip_qr_code = fields.Char(compute="_compute_qr_code", string="AFIP QR code")
    afip_message = fields.Text(
        string="AFIP Message",
        copy=False,
    )
    afip_xml_request = fields.Text(
        string="AFIP XML Request",
        copy=False,
    )
    afip_xml_response = fields.Text(
        string="AFIP XML Response",
        copy=False,
    )
    afip_result = fields.Selection(
        [("", "n/a"), ("A", "Aceptado"), ("R", "Rechazado"), ("O", "Observado")],
        "Resultado",
        readonly=True,
        states={"draft": [("readonly", False)]},
        copy=False,
        help="AFIP request result",
    )
    validation_type = fields.Char(
        "Validation Type",
        compute="_compute_validation_type",
    )
    afip_fce_es_anulacion = fields.Boolean(
        string="FCE: Es anulacion?",
        help="Solo utilizado en comprobantes MiPyMEs (FCE) del tipo débito o crédito. Debe informar:\n"
        "- SI: sí el comprobante asociado (original) se encuentra rechazado por el comprador\n"
        "- NO: sí el comprobante asociado (original) NO se encuentra rechazado por el comprador",
    )
    asynchronous_post = fields.Boolean()
    fecha_facturacion_hacienda = fields.Datetime("Fecha de Facturación - Hacienda",  help="Asignación de Fecha manual para registrarse en Hacienda", )

    name = fields.Char(
        readonly=True,  # Lo dejamos como solo lectura después de ser asignado
        copy=False,
        string="Número de Control",
    )

    error_log = fields.Text(string="Error técnico DTE", readonly=True)

    recibido_mh = fields.Boolean(string="Dte recibido por MH", copy=False)
    correo_enviado = fields.Boolean(string="Correo enviado en la creacion del dte", copy=False)
    invoice_time = fields.Char(string="Hora de Facturación", compute='_compute_invoice_time', store=True, readonly=True)

    @api.depends('invoice_date')
    def _compute_invoice_time(self):
        _logger.info("---> _compute_invoice_time iniciado con %d registros", len(self))
        salvador_tz = pytz.timezone('America/El_Salvador')
        for move in self:
            _logger.info("---> Procesando factura ID: %s", move.id)
            if move.invoice_date:
                now_salvador = datetime.now(salvador_tz)
                hora_formateada = now_salvador.strftime('%H:%M:%S')
                move.invoice_time = hora_formateada
                _logger.info("---> Hora asignada: %s", hora_formateada)
            else:
                _logger.info("---> Sin invoice_date asignada")

    @api.onchange('move_type')
    def _onchange_move_type(self):
        # Si el tipo de movimiento es una reversión (out_refund), no se debe permitir modificar el nombre (número de control)
        if self.move_type == 'out_refund' and self.name:
            self._fields['name'].readonly = True
        else:
            self._fields['name'].readonly = False

    @api.onchange('journal_id', 'l10n_latam_document_type_id')
    def _onchange_journal_id(self):
        _logger.info("Cambiando el tipo de documento o el diario")
        # Verifica que el campo 'name' (número de control) no se modifique después de haber sido asignado
        if self.name and self.name.startswith("DTE-"):
            _logger.info("El número de control ya ha sido asignado y no debe modificarse.")
            return  # No permite la modificación si ya tiene un número de control asignado

        #if self.journal_id and self.journal_id.type_report == 'ndc':  # Ajusta según tu configuración de tipo de diario
            #self.l10n_latam_document_type_id = self.journal_id.sit_tipo_documento

    @api.model_create_multi
    def create(self, vals_list):
        _logger.info("SIT vals list: %s", vals_list)

        for vals in vals_list:
            move_type = vals.get('move_type')
            _logger.info("SIT modulo detectado: %s", move_type)

            # --- extraer partner_id como antes ---
            partner_id = vals.get('partner_id')
            if not partner_id:
                for cmd in vals.get('line_ids', []):
                    if isinstance(cmd, tuple) and len(cmd) == 3:
                        lvals = cmd[2]
                        partner_id = lvals.get('partner_id') or partner_id
                        if partner_id:
                            break
            if partner_id:
                vals['partner_id'] = partner_id
            _logger.info("SIT Partner detectado: %s", partner_id)

            # --- Solo para diarios de venta (y compras): generar DTE/número de control ---
            journal_id = vals.get('journal_id')
            if not journal_id:
                journal_id= self.journal_id

            journal = self.env['account.journal'].browse(journal_id) if journal_id else None
            if (journal and journal.type == 'sale') or move_type == 'in_invoice':
                name = vals.get('name')
                # respetar si ya viene un DTE válido
                if not (name and name != '/' and name.startswith('DTE-')):
                    # usar un record virtual para llamar a métodos que requieren self.ensure_one()
                    virtual_move = self.env['account.move'].new(vals)
                    #virtual_move._onchange_journal()  # por si depende del diario
                    vals['name'] = virtual_move._generate_dte_name()
                    _logger.info("SIT DTE generado: %s", vals['name'])
                _logger.info("SIT DTE generado: %s", vals['name'])

                # partner obligatorio para DTE
                if not vals.get('partner_id'):
                    raise UserError(_("No se pudo obtener el partner para el crédito fiscal."))

                # códigoGeneracion_identificación
                if not vals.get('hacienda_codigoGeneracion_identificacion'):
                    vals['hacienda_codigoGeneracion_identificacion'] = self.sit_generar_uuid()
                    _logger.info("Codigo de generacion asignado: %s", vals['hacienda_codigoGeneracion_identificacion'])
            else:
                _logger.info("Diario '%s' no es venta, omito DTE", journal and journal.name)

            # ——— NUEVA SECCIÓN: para asientos contables (entry) ———
            if move_type == 'entry':
                # Si no viene nombre o viene como '/', se lo asignamos desde la secuencia
                if not vals.get('name') or vals['name'] == '/':
                    journal = self.env['account.journal'].browse(vals.get('journal_id'))
                    if journal and journal.sequence_id:
                        # Reservar siguiente número de la secuencia del diario
                        # nuevo:
                        if journal.sequence_id:
                            # next_by_id() sabe gestionar date_ranges internamente
                            vals['name'] = journal.sequence_id.next_by_id()
                        else:
                            # fallback genérico
                            vals['name'] = self.env['ir.sequence'].next_by_code('account.move') or '/'

                        _logger.info("SIT Asignado nombre de entry desde secuencia: %s", vals['name'])
                    else:
                        # Fallback genérico por si no hay sequence_id
                        vals['name'] = self.env['ir.sequence'].next_by_code('account.move') or '/'
                        _logger.info("SIT Asignado nombre genérico: %s", vals['name'])

        # no forzar name
        self._fields['name'].required = False
        records = super().create(vals_list)

        # refuerzo para name si quedó en '/'
        for vals, rec in zip(vals_list, records):
            if vals.get('name') and vals['name'] != '/' and rec.name == '/':
                rec.name = vals['name']
                _logger.info("SIT Refuerzo name=%s", rec.name)

            rec._copiar_retenciones_desde_documento_relacionado()
        return records

    @api.depends("move_type")
    def _compute_name(self):
        for rec in self:
            # Si es una reversión (out_refund) y ya tiene un número de control, no permitas que sea modificado.
            if rec.move_type == 'out_refund' and rec.name:
                rec._fields['name'].readonly = True

    def cron_asynchronous_post(self):
        queue_limit = self.env['ir.config_parameter'].sudo().get_param('l10n_sv_haciendaws_fe.queue_limit', 20)
        queue = self.search([
            ('asynchronous_post', '=', True),'|',
            ('afip_result', '=', False),
            ('afip_result', '=', ''),
        ], limit=queue_limit)
        if queue:
            queue._post()

    @api.depends("journal_id", "afip_auth_code")
    def _compute_validation_type(self):
        for rec in self:
            if  not rec.afip_auth_code:
                validation_type = self.env["res.company"]._get_environment_type()
                # if we are on homologation env and we dont have certificates
                # we validate only locally
                _logger.info("SIT validation_type =%s", validation_type)
                if validation_type == "homologation":
                    try:
                        rec.company_id.get_key_and_certificate(validation_type)
                    except Exception:
                        validation_type = False
                rec.validation_type = validation_type
            else:
                rec.validation_type = False
            _logger.info("SIT validtion_type =%s", rec.validation_type)

    @api.depends("afip_auth_code")
    def _compute_qr_code(self):
        for rec in self:
            if rec.afip_auth_mode in ["CAE", "CAEA"] and rec.afip_auth_code:
                number_parts = self._l10n_ar_get_document_number_parts(
                    rec.l10n_latam_document_number, rec.l10n_latam_document_type_id.code
                )

                qr_dict = {
                    "ver": 1,
                    "fecha": str(rec.invoice_date),
                    "cuit": int(rec.company_id.partner_id.l10n_ar_vat),
                    "ptoVta": number_parts["point_of_sale"],
                    "tipoCmp": int(rec.l10n_latam_document_type_id.code),
                    "nroCmp": number_parts["invoice_number"],
                    "importe": float(float_repr(rec.amount_total, 2)),
                    "moneda": rec.currency_id.l10n_ar_afip_code,
                    "ctz": float(float_repr(rec.l10n_ar_currency_rate, 2)),
                    "tipoCodAut": "E" if rec.afip_auth_mode == "CAE" else "A",
                    "codAut": int(rec.afip_auth_code),
                }
                if (
                    len(rec.commercial_partner_id.l10n_latam_identification_type_id)
                    and rec.commercial_partner_id.fax
                ):
                    qr_dict["tipoDocRec"] = int(
                        rec.commercial_partner_id.l10n_latam_identification_type_id.l10n_ar_afip_code
                    )
                    qr_dict["nroDocRec"] = int(
                        rec.commercial_partner_id.fax.replace("-", "").replace(".", "")
                    )
                qr_data = base64.encodestring(
                    json.dumps(qr_dict, indent=None).encode("ascii")
                ).decode("ascii")
                qr_data = str(qr_data).replace("\n", "")
                rec.afip_qr_code = "https://www.afip.gob.ar/fe/qr/?p=%s" % qr_data
            else:
                rec.afip_qr_code = False

    def get_related_invoices_data(self):
        """
        List related invoice information to fill CbtesAsoc.
        """
        self.ensure_one()
        if self.l10n_latam_document_type_id.internal_type == "credit_note":
            return self.reversed_entry_id
        elif self.l10n_latam_document_type_id.internal_type == "debit_note":
            return self.debit_origin_id
        else:
            return self.browse()

    def _get_sequence(self):
        # Regresa una secuencia por cada factura sin usar move.id como clave
        today = fields.Date.context_today(self)
        result = []

        for move in self:
            journal = move.journal_id
            if not journal:
                raise UserError(_("Debe definir un diario."))

            if not journal.sit_tipo_documento or not journal.sit_tipo_documento.codigo:
                raise UserError(_("Debe configurar el Tipo de DTE en el diario '%s'.") % journal.name)
            if not journal.sit_codestable:
                raise UserError(_("Debe configurar el Código de Establecimiento en el diario '%s'.") % journal.name)

            tipo_dte = journal.sit_tipo_documento.codigo
            cod_estable = journal.sit_codestable
            sequence_code = f'dte.{tipo_dte}'

            sequence = self.env['ir.sequence'].with_context({
                'dte': tipo_dte,
                'estable': cod_estable,
                'ir_sequence_date': today,
            }).search([('code', '=', sequence_code)], limit=1)

            if not sequence:
                raise UserError(_("No se encontró la secuencia con código '%s'.") % sequence_code)

            result.append((move, sequence))

        return result

    def _generate_dte_name(self, journal=None, actualizar_secuencia=False):
        self.ensure_one()
        journal = journal or self.journal_id
        _logger.info("SIT diario: %s, tipo. %s", journal, journal.type)

        if journal.type != 'sale' and journal.type != 'purchase':
            return False
        if not journal.sit_tipo_documento or not journal.sit_tipo_documento.codigo:
            raise UserError(_("Configure Tipo de DTE en diario '%s'.") % journal.name)
        if not journal.sit_codestable:
            raise UserError(_("Configure Código de Establecimiento en diario '%s'.") % journal.name)

        tipo = journal.sit_tipo_documento.codigo
        estable = journal.sit_codestable
        seq_code = f'dte.{tipo}'
        date_range = None

        # Buscar el último DTE emitido con este tipo y establecimiento
        domain = [
            ('journal_id', '=', journal.id),
            ('name', 'like', f'DTE-{tipo}-0000{estable}-%')
        ]
        ultimo = self.search(domain, order='name desc', limit=1)

        if ultimo:
            try:
                ultima_parte = int(ultimo.name.split('-')[-1])
            except ValueError:
                raise UserError(_("No se pudo interpretar el número del último DTE: %s") % ultimo.name)
            nuevo_numero = ultima_parte + 1
        else:
            ultima_parte = 0
            nuevo_numero = 1

        # Obtener secuencia configurada
        sequence = self.env['ir.sequence'].search([('code', '=', seq_code)], limit=1)
        if sequence:
            _logger.info("SIT | Sequence: %s", sequence)
            if sequence.use_date_range:
                today = fields.Date.context_today(self)
                date_range = self.env['ir.sequence.date_range'].search([
                    ('sequence_id', '=', sequence.id),
                    ('date_from', '<=', today),
                    ('date_to', '>=', today)
                ], limit=1)
                if date_range and date_range.number_next_actual > nuevo_numero:
                    _logger.info("SIT | Ajustando número desde secuencia con rango: %s > %s",
                                 date_range.number_next_actual, nuevo_numero)
                    nuevo_numero = date_range.number_next_actual
            else:
                if sequence.number_next_actual > nuevo_numero:
                    _logger.info("SIT | Ajustando número desde secuencia directa: %s > %s", sequence.number_next_actual,
                                 nuevo_numero)
                    nuevo_numero = sequence.number_next_actual

        nuevo_name = f"DTE-{tipo}-0000{estable}-{str(nuevo_numero).zfill(15)}"

        # Verificar duplicado antes de retornar
        if self.search_count([('name', '=', nuevo_name), ('journal_id', '=', journal.id)]):
            raise UserError(_("El número DTE generado ya existe: %s") % nuevo_name)

        _logger.info("SIT Nombre DTE generado manualmente: %s", nuevo_name)

        # Actualizar secuencia (ir.sequence o ir.sequence.date_range)
        if actualizar_secuencia and sequence:
            next_num = nuevo_numero + 1
            if sequence.use_date_range:
                if date_range and date_range.number_next_actual < next_num:
                    date_range.number_next_actual = next_num
                    _logger.info("SIT Secuencia con date_range '%s' actualizada a %s", seq_code, next_num)
            else:
                if sequence.number_next_actual < next_num:
                    sequence.number_next_actual = next_num
                    _logger.info("SIT Secuencia '%s' actualizada a %s", seq_code, next_num)
            _logger.info("SIT Actualizar secuencia _generar_dte_name(): %s", actualizar_secuencia)
        return nuevo_name

    # ---------------------------------------------------------------------------------------------
#     def _post(self, soft=True):
#         '''validamos que partner cumple los requisitos basados en el tipo
#         de documento de la secuencia del diario seleccionado
#         FACTURA ELECTRONICAMENTE
#         '''
#         invoices_to_post = self
#         _logger.info("SIT _post override for invoices: %s", self.ids)
#         _logger.info("Iniciando _post para account.move")
#         _logger.info("SIT _post llamado con self=%s", self)
#         _logger.info("SIT _post llamado con len(self)=%s", len(self))
#
#         if not self:
#
#             if self.move_type == 'out_refund' and self.name:
#                 _logger.debug("SIT No se puede modificar el número de control después de la reversión.")
#                 self._fields['name'].readonly = True
#                 _logger.info(f"El número de control {self.name} no puede ser modificado.")
#
#             _logger.warning("SIT _post llamado sin registros. Posiblemente acción revertir sin contexto válido.")
#             move_type = self.env.context.get('default_move_type', 'entry')
#             journal_id = self.env.context.get('default_journal_id')
#
#             if not journal_id:
#                 raise UserError(_("No se puede generar número de control porque no hay contexto de diario definido."))
#
#             if move_type == 'out_refund':
#                 # ⚠️ Solo crear movimiento temporal si es una nota de crédito
#                 default_vals = {
#                     'journal_id': journal_id,
#                     'move_type': move_type,
#                 }
#                 temp_move = self.with_context(default_journal_id=journal_id).create([default_vals])
#                 invoices_to_post = temp_move
#                 _logger.info("SIT se creó temp_move para out_refund con id=%s y diario=%s", temp_move.id, journal_id)
#             else:
#                 raise UserError(_("No se puede continuar: _post() llamado sin registros y no es out_refund."))
#         else:
#             invoices_to_post = self
#
#         _logger.debug("SIT Invoice: %s", invoices_to_post)
#
# ############################
#         for inv in invoices_to_post:
#             journal = inv.journal_id
#             _logger.info("SIT Procesando invoice %s (journal=%s)", inv.id, journal.name)
#
#             # --- solo Venta: DTE name / validaciones ---
#             if journal.type == 'sale' and inv.move_type in ('out_invoice', 'out_refund'):
#                 # generación / validación de DTE
#                 if not (inv.name and inv.name.startswith("DTE-")):
#                     nr = inv._generate_dte_name()
#                     if not nr:
#                         raise UserError(_("No se pudo generar número de control DTE para %s.") % inv.id)
#                     inv.write({'name': nr})
#                     _logger.info("SIT DTE generado en _post: %s", nr)
#                 if not inv.name.startswith("DTE-"):
#                     raise UserError(_("Número de control DTE inválido para %s.") % inv.id)
#             else:
#                 _logger.info("Diario '%s' no es venta, omito DTE en _post", journal.name)
#                 # dejo que Odoo asigne su name normal y salto todas las validaciones DTE
#                 continue
#
# #################################
#             # Si el tipo de documento requiere validación adicional, hacerlo aquí
#             if invoice.journal_id.sit_tipo_documento:
#                 type_report = invoice.journal_id.type_report
#                 sit_tipo_documento = invoice.journal_id.sit_tipo_documento.codigo
#
#                 _logger.info("SIT action_post type_report = %s", type_report)
#                 _logger.info("SIT action_post sit_tipo_documento = %s", sit_tipo_documento)
#                 _logger.info("SIT Receptor = %s, info=%s", invoice.partner_id, invoice.partner_id.parent_id)
#                 # Validación del partner y otros parámetros según el tipo de DTE
#                 if type_report == 'ccf':
#                     # Validaciones específicas para CCF
#                     if not invoice.partner_id.parent_id:
#                         if not invoice.partner_id.nrc:
#                             invoice.msg_error("N.R.C.")
#                         if not invoice.partner_id.vat and not invoice.partner_id.dui:
#                             invoice.msg_error("N.I.T O D.U.I.")
#                         if not invoice.partner_id.codActividad:
#                             invoice.msg_error("Giro o Actividad Económica")
#                     else:
#                         if not invoice.partner_id.parent_id.nrc:
#                             invoice.msg_error("N.R.C.")
#                         if not invoice.partner_id.parent_id.vat and not invoice.partner_id.parent_id.dui:
#                             invoice.msg_error("N.I.T O D.U.I.")
#                         if not invoice.partner_id.parent_id.codActividad:
#                             invoice.msg_error("Giro o Actividad Económica")
#
#                 elif type_report == 'ndc':
#                     # Asignar el partner_id relacionado con el crédito fiscal si no existe parent_id
#                     if not invoice.partner_id.parent_id:
#                         if not invoice.partner_id.nrc:
#                             _logger.info("SIT nrc partner = %s", invoice.partner_id.parent_id)
#                             invoice.msg_error("N.R.C.")
#                         if not invoice.partner_id.fax:
#                             invoice.msg_error("N.I.T.")
#                         if not invoice.partner_id.codActividad:
#                             invoice.msg_error("Giro o Actividad Económica")
#                     else:
#                         if not invoice.partner_id.parent_id.nrc:
#                             invoice.msg_error("N.R.C.")
#                         if not invoice.partner_id.parent_id.fax:
#                             invoice.msg_error("N.I.T.")
#                         if not invoice.partner_id.parent_id.codActividad:
#                             invoice.msg_error("Giro o Actividad Económica")
#
#                 ambiente = "00"
#                 if self._compute_validation_type_2() == 'production':
#                     ambiente = "01"
#                     _logger.info("SIT Factura de Producción")
#
#                 # Firmar el documento y generar el DTE
#                 payload = invoice.obtener_payload('production', sit_tipo_documento)
#                 documento_firmado = invoice.firmar_documento('production', payload)
#
#                 if documento_firmado:
#                     _logger.info("SIT Firmado de documento")
#                     payload_dte = invoice.sit_obtener_payload_dte_info(ambiente, documento_firmado)
#                     self.check_parametros_dte(payload_dte)
#                     Resultado = invoice.generar_dte('production', payload_dte, payload)
#                     if Resultado:
#                         # Procesar la respuesta de Hacienda
#                         dat_time = Resultado['fhProcesamiento']
#                         fhProcesamiento = datetime.strptime(dat_time, '%d/%m/%Y %H:%M:%S')
#                         invoice.hacienda_estado = Resultado['estado']
#                         invoice.hacienda_codigoGeneracion_identificacion = Resultado['codigoGeneracion']
#                         invoice.hacienda_selloRecibido = Resultado['selloRecibido']
#                         invoice.fecha_facturacion_hacienda = fhProcesamiento + timedelta(hours=6)
#                         invoice.hacienda_clasificaMsg = Resultado['clasificaMsg']
#                         invoice.hacienda_codigoMsg = Resultado['codigoMsg']
#                         invoice.hacienda_descripcionMsg = Resultado['descripcionMsg']
#                         invoice.hacienda_observaciones = str(Resultado['observaciones'])
#                         codigo_qr = invoice._generar_qr(ambiente, Resultado['codigoGeneracion'],
#                                                         invoice.fecha_facturacion_hacienda)
#                         invoice.sit_qr_hacienda = codigo_qr
#                         invoice.state = "draft"
#
#                         dte = payload['dteJson']
#                         invoice.sit_json_respuesta = json.dumps(dte, ensure_ascii=False, default=str)
#                         json_str = json.dumps(dte, ensure_ascii=False, default=str)
#                         json_base64 = base64.b64encode(json_str.encode('utf-8'))
#                         file_name = dte["identificacion"]["numeroControl"] + '.json'
#                         invoice.env['ir.attachment'].sudo().create({
#                             'name': file_name,
#                             'datas': json_base64,
#                             'res_model': self._name,
#                             'res_id': invoice.id,
#                             'mimetype': 'application/json'
#                         })
#                         _logger.info("SIT JSON creado y adjuntado.")
#
#                 else:
#                     _logger.info("SIT Documento no firmado")
#                     raise UserError(_('SIT Documento NO Firmado'))
#
#         _logger.info("SIT Terminando _post sin procesar ningún DTE (self=%s)", self)
#         return super(AccountMove, self)._post(soft=soft)

    def actualizar_secuencia(self):
        _logger.info("SIT Actualizar secuencia: %s")
        tipo = self.journal_id.sit_tipo_documento.codigo
        estable = self.journal_id.sit_codestable
        seq_code = f'dte.{tipo}'
        numero_control = self.name
        try:
            secuencia_actual = int(numero_control.split("-")[-1])
        except Exception:
            secuencia_actual = 0
        sequence = self.env['ir.sequence'].search([('code', '=', seq_code)], limit=1)
        if sequence:
            next_num = secuencia_actual + 1
            if sequence.use_date_range:
                today = fields.Date.context_today(self)
                date_range = self.env['ir.sequence.date_range'].search([
                    ('sequence_id', '=', sequence.id),
                    ('date_from', '<=', today),
                    ('date_to', '>=', today)
                ], limit=1)
                if date_range and date_range.number_next_actual < next_num:
                    date_range.number_next_actual = next_num
                    _logger.info("SIT Secuencia con date_range '%s' actualizada a %s", seq_code, next_num)
            else:
                if sequence.number_next_actual < next_num:
                    sequence.number_next_actual = next_num
                    _logger.info("SIT Secuencia '%s' actualizada a %s", seq_code, next_num)

    def _post(self, soft=True):
        """Override para:
        - Diarios sale: generar/validar DTE y enviar a Hacienda.
        - Resto: usar secuencia estándar y omitir DTE.
        """
        Resultado = None
        payload = None
        invoices_to_post = self
        respuesta_mh = False
        errores_dte = []
        estado = None
        json_dte = None
        _logger.info("SIT _post override for invoices: %s", self.ids)

        # 1) Cuando no hay registros (p.ej. reversión), delegar al super
        if not invoices_to_post:
            return super(AccountMove, self)._post(soft=soft)

        # 2) Procesar cada factura
        for invoice in invoices_to_post:
            try:

                if invoice.hacienda_selloRecibido and invoice.recibido_mh:
                    raise UserError("Documento ya se encuentra procesado")

                journal = invoice.journal_id
                _logger.info("SIT Procesando invoice %s (journal=%s)", invoice.id, journal.name)

                if not self.invoice_time:
                    self._compute_invoice_time()

                # —————————————————————————————————————————————
                # A) DIARIOS NO-VENTA/COMPRA: saltar lógica DTE
                # —————————————————————————————————————————————
                if journal.type not in ('sale','purchase'):  # or invoice.move_type not in ('out_invoice', 'out_refund'):
                    _logger.info("Diario '%s' no aplica, omito DTE en _post", journal.name)
                    # Dejar que Odoo asigne su name normal en el super al final
                    continue

                # —————————————————————————————————————————————
                # B) DIARIOS VENTA: generación/validación de DTE
                # —————————————————————————————————————————————
                # 1) Número de control DTE
                if not (invoice.name and invoice.name.startswith("DTE-")):
                    numero_control = invoice._generate_dte_name()
                    if not numero_control:
                        raise UserError(_("No se pudo generar número de control DTE para la factura %s.") % invoice.id)
                    invoice.name = numero_control
                    _logger.info("SIT DTE generado en _post: %s", numero_control)

                if not invoice.hacienda_codigoGeneracion_identificacion:
                    invoice.hacienda_codigoGeneracion_identificacion = self.sit_generar_uuid()
                    _logger.info("Codigo de generacion asignado en el post: %s", invoice.hacienda_codigoGeneracion_identificacion)

                # Si el tipo de documento requiere validación adicional, hacerlo aquí
                if invoice.journal_id.sit_tipo_documento:
                    type_report = invoice.journal_id.type_report
                    sit_tipo_documento = invoice.journal_id.sit_tipo_documento.codigo

                    _logger.info("SIT action_post type_report = %s", type_report)
                    _logger.info("SIT action_post sit_tipo_documento = %s", sit_tipo_documento)
                    _logger.info("SIT Receptor = %s, info=%s", invoice.partner_id, invoice.partner_id.parent_id)
                    # Validación del partner y otros parámetros según el tipo de DTE
                    if type_report == 'ccf':
                        # Validaciones específicas para CCF
                        if not invoice.partner_id.parent_id:
                            if not invoice.partner_id.nrc:
                                invoice.msg_error("N.R.C.")
                            if not invoice.partner_id.fax and not invoice.partner_id.dui:
                                invoice.msg_error("N.I.T O D.U.I.")
                            if not invoice.partner_id.codActividad:
                                invoice.msg_error("Giro o Actividad Económica")
                        else:
                            if not invoice.partner_id.parent_id.nrc:
                                invoice.msg_error("N.R.C.")
                            if not invoice.partner_id.parent_id.fax and not invoice.partner_id.parent_id.dui:
                                invoice.msg_error("N.I.T O D.U.I.")
                            if not invoice.partner_id.parent_id.codActividad:
                                invoice.msg_error("Giro o Actividad Económica")

                    elif type_report == 'ndc':
                        # Asignar el partner_id relacionado con el crédito fiscal si no existe parent_id
                        if not invoice.partner_id.parent_id:
                            if not invoice.partner_id.nrc:
                                invoice.msg_error("N.R.C.")
                            if not invoice.partner_id.fax:
                                invoice.msg_error("N.I.T.")
                            if not invoice.partner_id.codActividad:
                                invoice.msg_error("Giro o Actividad Económica")
                        else:
                            parent = invoice.partner_id.parent_id
                            if not invoice.partner_id.parent_id.nrc:
                                invoice.msg_error("N.R.C.")
                            if not invoice.partner_id.parent_id.fax:
                                invoice.msg_error("N.I.T.")
                            if not invoice.partner_id.parent_id.codActividad:
                                invoice.msg_error("Giro o Actividad Económica")

                    ambiente = "00"
                    if self._compute_validation_type_2() == 'production':
                        ambiente = "01"
                        _logger.info("SIT Factura de Producción")

                    # Generar json del DTE
                    payload = invoice.obtener_payload('production', sit_tipo_documento)

                    # Firmar el documento y generar el DTE
                    documento_firmado = invoice.firmar_documento('production', payload)

                    if not documento_firmado:
                        raise UserError("Error en firma del documento")

                    if documento_firmado:
                        _logger.info("SIT Firmado de documento")
                        payload_dte = invoice.sit_obtener_payload_dte_info(ambiente, documento_firmado)
                        self.check_parametros_dte(payload_dte)

                        # Intentar generar el DTE
                        Resultado = invoice.generar_dte('production', payload_dte, payload)
                        _logger.warning("SIT Resultado. =%s, estado=%s", Resultado, Resultado.get('estado', ''))

                        # Si el resp es un rechazo por número de control
                        if isinstance(Resultado, dict) and Resultado.get('estado', '').strip().lower() == 'rechazado':
                            error_text = json.dumps(Resultado).lower()
                            if 'numero de control' in error_text or 'ya existe un registro con ese valor' in error_text:
                                _logger.warning(
                                    "SIT DTE rechazado por número de control duplicado. Generando nuevo número.")

                                # Generar nuevo número de control
                                nuevo_nombre = invoice._generate_dte_name()
                                invoice.write({'name': nuevo_nombre})
                                invoice.sequence_number = int(nuevo_nombre.split("-")[-1])

                                # Reemplazar numeroControl en el payload original
                                payload['dteJson']['identificacion']['numeroControl'] = nuevo_nombre

                                # Volver a firmar con el nuevo número
                                documento_firmado = invoice.firmar_documento('production', payload)

                                if not documento_firmado:
                                    raise UserError(
                                        _('SIT Documento NO Firmado después de reintento con nuevo número de control'))

                                # Intentar nuevamente generar el DTE
                                payload_dte = invoice.sit_obtener_payload_dte_info(ambiente, documento_firmado)
                                self.check_parametros_dte(payload_dte)
                                Resultado = invoice.generar_dte('production', payload_dte, payload)

                        # Guardar json generado
                        json_dte = payload['dteJson']
                        _logger.info("Tipo de dteJson: %s", type(json_dte))
                        _logger.info("SIT JSON=%s", json_dte)

                        # Solo serializar si no es string
                        try:
                            if isinstance(json_dte, str):
                                try:
                                    # Verifica si es un JSON string válido, y lo convierte a dict
                                    json_dte = json.loads(json_dte)
                                except json.JSONDecodeError:
                                    # Ya era string, pero no era JSON válido -> guardar tal cual
                                    invoice.sit_json_respuesta = json_dte
                                else:
                                    # Era un JSON string válido → ahora es dict
                                    invoice.sit_json_respuesta = json.dumps(json_dte, ensure_ascii=False)
                            elif isinstance(json_dte, dict):
                                invoice.sit_json_respuesta = json.dumps(json_dte, ensure_ascii=False)
                            else:
                                # Otro tipo de dato no esperado
                                invoice.sit_json_respuesta = str(json_dte)
                        except Exception as e:
                            _logger.warning("No se pudo guardar el JSON del DTE: %s", e)

                        estado = None
                        if Resultado and Resultado.get('estado'):
                            estado = Resultado['estado'].strip().lower()

                        if Resultado and Resultado.get('estado', '').lower() == 'procesado': #if Resultado:
                            if estado == 'procesado':
                                invoice.actualizar_secuencia()

                            _logger.info("SIT Estado DTE: %s", Resultado['estado'])
                            _logger.info("SIT Resultado DTE")

                            # Fecha de procesamiento
                            fh_procesamiento = Resultado['fhProcesamiento']
                            if fh_procesamiento:
                                try:
                                    fh_dt = datetime.strptime(fh_procesamiento, '%d/%m/%Y %H:%M:%S') + timedelta(
                                        hours=6)
                                    if not invoice.fecha_facturacion_hacienda:
                                        invoice.fecha_facturacion_hacienda = fh_dt
                                except Exception as e:
                                    _logger.warning("Error al parsear fhProcesamiento: %s", e)
                            _logger.info("SIT Fecha facturacion=%s", invoice.fecha_facturacion_hacienda)

                            # Procesar la respuesta de Hacienda
                            invoice.hacienda_estado = Resultado['estado']
                            invoice.hacienda_codigoGeneracion_identificacion = self.hacienda_codigoGeneracion_identificacion
                            _logger.info("Codigo de generacion session: %s, codigo generacion bd: %s", self.hacienda_codigoGeneracion_identificacion, invoice.hacienda_codigoGeneracion_identificacion)
                            invoice.hacienda_selloRecibido = Resultado['selloRecibido']
                            invoice.hacienda_clasificaMsg = Resultado['clasificaMsg']
                            invoice.hacienda_codigoMsg = Resultado['codigoMsg']
                            invoice.hacienda_descripcionMsg = Resultado['descripcionMsg']
                            invoice.hacienda_observaciones = str(Resultado['observaciones'])
                            #invoice.sit_json_respuesta = json_dte

                            codigo_qr = invoice._generar_qr(ambiente,self.hacienda_codigoGeneracion_identificacion,
                                                            invoice.fecha_facturacion_hacienda)
                            invoice.sit_qr_hacienda = codigo_qr
                            invoice.sit_documento_firmado = documento_firmado

                            # —————————————————————————————————————————————
                            # C) Guardar DTE
                            # —————————————————————————————————————————————

                            # Guardar archivo .json
                            json_str = json.dumps(payload['dteJson'], ensure_ascii=False, default=str)
                            json_base64 = base64.b64encode(json_str.encode('utf-8'))
                            file_name = payload['dteJson']["identificacion"]["numeroControl"] + '.json'
                            invoice.env['ir.attachment'].sudo().create({
                                'name': file_name,
                                'datas': json_base64,
                                'res_model': self._name,
                                'res_id': invoice.id,
                                'mimetype': 'application/json'
                            })
                            _logger.info("SIT JSON creado y adjuntado.")

                            # Respuesta json
                            json_response_data = {
                                "jsonRespuestaMh": Resultado
                            }
                            # Convertir el JSON en el campo sit_json_respuesta a un diccionario de Python
                            try:
                                json_original = json.loads(
                                    invoice.sit_json_respuesta) if invoice.sit_json_respuesta else {}
                            except json.JSONDecodeError:
                                json_original = {}

                            # Fusionar JSONs
                            json_original.update(json_response_data)
                            sit_json_respuesta_fusionado = json.dumps(json_original)
                            invoice.sit_json_respuesta = sit_json_respuesta_fusionado

                            _logger.info("Codigo de generacion resultado: %s", Resultado['codigoGeneracion'])
                            invoice.write({
                                'hacienda_estado': Resultado['estado'],
                                'hacienda_codigoGeneracion_identificacion': Resultado['codigoGeneracion'],
                                'hacienda_selloRecibido': Resultado['selloRecibido'],
                                'hacienda_clasificaMsg': Resultado['clasificaMsg'],
                                'hacienda_codigoMsg': Resultado['codigoMsg'],
                                'hacienda_descripcionMsg': Resultado['descripcionMsg'],
                                'hacienda_observaciones': str(Resultado.get('observaciones', '')),
                                'state': 'draft',
                                'recibido_mh': True,
                            })

                            # Guardar archivo .pdf y enviar correo al cliente
                            try:
                                invoice.sudo().sit_enviar_correo_dte_automatico()
                            except Exception as e:
                                _logger.warning("SIT | Error al enviar DTE por correo o generar PDF: %s", str(e))
                        else:
                            # Lanzar error al final si fue rechazado
                            if estado:
                                if estado == 'rechazado':
                                    mensaje = Resultado['descripcionMsg'] or _('Documento rechazado por Hacienda.')
                                    raise UserError(_("DTE rechazado por MH:\n%s") % mensaje)
                                elif estado not in ('procesado', ''):
                                    mensaje = Resultado.get('descripcionMsg') or _('DTE no procesado correctamente')
                                    raise UserError(_("Respuesta inesperada de Hacienda. Estado: %s\nMensaje: %s") % (estado, mensaje))

                        # 2) Validar formato
                        if not invoice.name.startswith("DTE-"):
                            raise UserError(
                                _("Número de control DTE inválido para la factura %s.") % invoice.id)
            except Exception as e:
                error_msg = traceback.format_exc()
                _logger.exception("SIT Error durante el _post para invoice ID %s: %s", invoice.id, str(e))
                invoice.write({
                    'error_log': error_msg,
                    'state': 'draft',
                    'sit_es_configencia': False,
                })
        _logger.info("SIT Fin _post")

        return super(AccountMove, self)._post(soft=soft)

    def _compute_validation_type_2(self):
        for rec in self:
            parameter_env_type = self.env["ir.config_parameter"].sudo().get_param("afip.ws.env.type")
            if parameter_env_type == "production":
                environment_type = "production"
            else:
                environment_type = "production"
            return environment_type

    # FIMAR FIMAR FIRMAR =======
    def firmar_documento(self, enviroment_type, payload):
        _logger.info("SIT  Firmando documento")
        _logger.info("SIT Documento a FIRMAR = %s", payload)

        # 1) inicializar la lista donde acumularás status/cuerpo o errores
        resultado = []

        if enviroment_type == 'homologation':
            ambiente = "01"
        else:
            ambiente = "01"
        max_intentos = 3
        resultado = []
        # host = self.company_id.sit_firmador
        url = "http://192.168.2.25:8113/firmardocumento/"  # host + '/firmardocumento/'
        headers = {
            'Content-Type': 'application/json'
        }

        payload = {
            "nit": payload["nit"],  # <--- aquí estaba el error, decía 'liendre'
            "activo": True,
            "passwordPri": payload["passwordPri"],
            "dteJson": payload["dteJson"],
        }

        for intento in range(1, max_intentos + 1):
            _logger.info("Intento %s de %s para firmar el documento", intento, max_intentos)
            try:
                response = requests.request("POST", url, headers=headers, data=json.dumps(payload, default=str))
                _logger.info("SIT firmar_documento response =%s", response.text)
                _logger.info("SIT dte json =%s",
                             json.dumps(payload.get("dteJson", {}), indent=2, ensure_ascii=False, default=str))

                json_response = response.json()
                # Manejo de errores 400–402
                if json_response.get('status') in [400, 401, 402, 'ERROR']:
                    _logger.info("SIT Error 40X  =%s", json_response['status'])
                    status = json_response['status']
                    error = json_response['error']
                    message = json_response['message']
                    MENSAJE_ERROR = "Código de Error:" + str(status) + ", Error:" + str(error) + ", Detalle:" + str(
                        message)
                    # raise UserError(_(MENSAJE_ERROR))
                    _logger.warning("Error de firma intento %s: %s", intento, MENSAJE_ERROR)

                    if intento == max_intentos:
                        raise UserError(_(MENSAJE_ERROR))
                    continue

                if json_response['status'] in ['ERROR', 401, 402]:
                    _logger.info("SIT Error 40X  =%s", json_response['status'])
                    status = json_response['status']
                    body = json_response['body']
                    codigo = body['codigo']
                    message = body['mensaje']
                    resultado.append(status)
                    resultado.append(codigo)
                    resultado.append(message)
                    MENSAJE_ERROR = "Código de Error:" + str(status) + ", Codigo:" + str(codigo) + ", Detalle:" + str(
                        message)
                    if intento == max_intentos:
                        raise UserError(_(MENSAJE_ERROR))
                    continue
                elif json_response['status'] == 'OK':
                    status = json_response['status']
                    body = json_response['body']
                    resultado.append(status)
                    resultado.append(body)
                    return body
            except Exception as e:
                _logger.warning("Excepción en firma intento %s: %s", intento, str(e))
                if intento == max_intentos:
                    error = str(e)
                    _logger.info('SIT error= %s, ', error)
                    if "error" in error or "" in error:
                        try:
                            error_dict = json.loads(error) if isinstance(error, str) else error
                            MENSAJE_ERROR = str(error_dict.get('status', '')) + ", " + str(
                                error_dict.get('error', '')) + ", " + str(error_dict.get('message', ''))
                        except Exception:
                            MENSAJE_ERROR = error
                        raise UserError(_(MENSAJE_ERROR))
                    else:
                        raise UserError(_(error))
                    continue
        # Si todos los intentos fallan sin lanzar excepciones
        raise UserError(_("No se pudo firmar el documento. Inténtelo nuevamente más tarde."))

    def obtener_payload(self, enviroment_type, sit_tipo_documento):
        _logger.info("SIT  Obteniendo payload")
        _logger.info("SIT  Tipo de documento= %s", sit_tipo_documento)
        invoice_info = None

        if enviroment_type == 'homologation':
            ambiente = "00"
        else:
            ambiente = "01"
        if sit_tipo_documento in ("01", "13"):
            invoice_info = self.sit_base_map_invoice_info()
            _logger.info("SIT invoice_info FE = %s", invoice_info)
            self.check_parametros_firmado()
        elif sit_tipo_documento == "03":
            invoice_info = self.sit__ccf_base_map_invoice_info()
            _logger.info("SIT invoice_info CCF = %s", invoice_info)
            self.check_parametros_firmado()
        elif sit_tipo_documento == "05":
            invoice_info = self.sit_base_map_invoice_info_ndc()
            self.check_parametros_firmado()
        elif sit_tipo_documento == "06":
            invoice_info = self.sit_base_map_invoice_info_ndd()
            self.check_parametros_firmado()
        elif sit_tipo_documento == "11":
            invoice_info = self.sit_base_map_invoice_info_fex()
            _logger.info("SIT invoice_info FEX = %s", invoice_info)
            self.check_parametros_firmado()
        elif sit_tipo_documento == "14":
            invoice_info = self.sit_base_map_invoice_info_fse()
            _logger.info("SIT invoice_info FSE = %s", invoice_info)
            self.check_parametros_firmado()
        _logger.info("SIT payload_data =%s", invoice_info)
        return invoice_info


    # FRANCISCO # SE OBTIENE EL JWT Y SE ENVIA A HACIENDA PARA SU VALIDACION
    def generar_dte(self, environment_type, payload, payload_original):
        """
        1) Refresca el token si caducó.
        2) Si no hay JWT en payload['documento'], llama al firmador.
        3) Envía el JWT firmado a Hacienda.
        4) Gestiona el caso 004 (YA EXISTE) para no dejar en borrador.
        """
        data = None
        max_intentos = 3
        # ——— 1) Selección de URL de Hacienda ———
        host = (
            "https://apitest.dtes.mh.gob.sv"
            if environment_type == "homologation"
            else "https://api.dtes.mh.gob.sv"
        )
        url_receive = f"{host}/fesv/recepciondte"

        # ——— 2) Refrescar token si hace falta ———
        today = fields.Date.context_today(self)
        if not self.company_id.sit_token_fecha or self.company_id.sit_token_fecha.date() < today:
            self.company_id.get_generar_token()

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Odoo",
            "Authorization": f"Bearer {self.company_id.sit_token}",
        }

        # ——— 3) Obtener o firmar el JWT ———
        jwt_token = payload.get("documento")
        if not (isinstance(jwt_token, str) and jwt_token.strip()):
            firmador_url = (
                    getattr(self.company_id, "sit_firmador", None)
                    or "http://192.168.2.25:8113/firmardocumento"
            )
            sign_payload = {
                "nit": payload_original["dteJson"]["emisor"]["nit"],
                "activo": True,
                "passwordPri": payload_original.get("passwordPri")
                               or self.company_id.sit_password
                               or payload_original["dteJson"].get("passwordPri"),
                "dteJson": payload_original["dteJson"],
            }
            try:
                resp_sign = requests.post(
                    firmador_url, headers={"Content-Type": "application/json"}, json=sign_payload, timeout=30
                )
                resp_sign.raise_for_status()
                data_sign = resp_sign.json()
                if data_sign.get("status") != "OK":
                    # raise UserError(_("Firma rechazada: %s – %s") % (data_sign.get("status"), data_sign.get("message", "")))
                    return data_sign
                jwt_token = data_sign["body"]
            except Exception as e:
                _logger.warning("Error al firmar el documento: %s", e)
                return {
                    "estado": "ERROR_FIRMA",
                    "mensaje": str(e),
                }

        # ——— 4) Construir el payload para Hacienda ———
        ident = payload_original["dteJson"]["identificacion"]
        send_payload = {
            "ambiente": ident["ambiente"],
            "idEnvio": int(self.id),
            "tipoDte": ident["tipoDte"],
            "version": int(ident.get("version", 3)),
            "documento": jwt_token,
            "codigoGeneracion": ident["codigoGeneracion"],
        }

        # ——— 5) Envío a Hacienda ———
        # ——— Intentos para enviar a Hacienda ———
        for intento in range(1, max_intentos + 1):
            _logger.info("Intento %s de %s para enviar DTE a Hacienda", intento, max_intentos)
            try:
                resp = requests.post(url_receive, headers=headers, json=send_payload, timeout=30)
            except Exception as e:
                # raise UserError(_("Error de conexión con Hacienda: %s") % e)
                if intento == max_intentos:
                    raise UserError(_("Error de conexión con Hacienda tras %s intentos: %s") % (max_intentos, e))
                _logger.warning("Error de conexión con Hacienda: %s", e)
                continue  # intenta de nuevo

            # Intentamos parsear JSON incluso si es 400
            try:
                data = resp.json()
            except ValueError:
                data = {}

            _logger.info("SIT MH status=%s text=%s", resp.status_code, resp.text)
            _logger.info("SIT MH fecha procesamiento text=%s", resp.text)
            _logger.info("SIT MH DATA=%s", data)

            # ——— 6) Manejo especial de códigoMsg '004' ———
            if resp.status_code == 400 and data.get("clasificaMsg") == "11" and data.get("codigoMsg") == "004":
                # Ya existe un registro con ese codigoGeneracion
                _logger.warning("MH 004 → YA EXISTE, marcando como registrado en Odoo")
                self.write({
                    "hacienda_estado": "PROCESADO",
                    "hacienda_codigoGeneracion_identificacion": data.get("codigoGeneracion"),
                    "hacienda_selloRecibido": data.get("selloRecibido"),
                    "hacienda_clasificaMsg": data.get("clasificaMsg"),
                    "hacienda_codigoMsg": data.get("codigoMsg"),
                    "hacienda_descripcionMsg": data.get("descripcionMsg"),
                    "hacienda_observaciones": ", ".join(data.get("observaciones") or []),
                    "state": "posted",
                })
                self.message_post(
                    body=_("Documento ya existente en Hacienda: %s") % data.get("descripcionMsg")
                )
                return data

            # ——— 7) Errores HTTP distintos de 200 ———
            if resp.status_code != 200:
                mensaje = f"Error MH (HTTP {resp.status_code}): {data or resp.text}"
                _logger.warning(mensaje)
                if intento == max_intentos:
                    self._crear_contingencia(resp, data, mensaje)
                    raise UserError(_("Error MH (HTTP %s): %s") % (resp.status_code, data or resp.text))
                continue  # intenta de nuevo
            # data = resp.json()

            estado = data.get('estado')
            if estado == 'RECHAZADO':
                mensaje = f"Rechazado por MH: {data.get('clasificaMsg')} - {data.get('descripcionMsg')}"
                _logger.warning(mensaje)
                if intento == max_intentos:
                    self._crear_contingencia(resp, data, mensaje)
                    raise UserError(_("Rechazado por MH: %s – %s") % (data.get('clasificaMsg'), data.get('descripcionMsg')))
                continue

            if estado == 'PROCESADO':
                return data

            # ——— 9) Caso realmente inesperado ———
            _logger.warning("Respuesta inesperada de MH: %s", data)
            _logger.warning("Finalizó sin respuesta exitosa ni contingencia: %s", data)
        return data

    def _autenticar(self,user,pwd):
        _logger.info("SIT self = %s", self)
        _logger.info("SIT self = %s, %s", user, pwd)
        enviroment_type = self._get_environment_type()
        _logger.info("SIT Modo = %s", enviroment_type)
        if enviroment_type == 'homologation':
            host = 'https://apitest.dtes.mh.gob.sv'
        else:
            host = 'https://api.dtes.mh.gob.sv'
        url = host + '/seguridad/auth'
        self.check_hacienda_values()
        try:
            payload = "user=" + user + "&pwd=" + pwd
            #'user=06140902221032&pwd=D%237k9r%402mP1!b'
            headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
            }
            response = requests.request("POST", url, headers=headers, data=payload)
            _logger.info("SIT response =%s", response.text)
        except Exception as e:
            error = str(e)
            _logger.info('SIT error= %s, ', error)
            if "error" in error or "" in error:
                MENSAJE_ERROR = str(error['status']) + ", " + str(error['error']) +", " +  str(error['message'])
                raise UserError(_(MENSAJE_ERROR))
            else:
                raise UserError(_(error))
        resultado = []
        json_response = response.json()

    def _generar_qr(self, ambiente, codGen, fechaEmi):
        _logger.info("SIT generando qr = %s", self)
        # enviroment_type = self._get_environment_type()
        # enviroment_type = self.env["res.company"]._get_environment_type()
        enviroment_type =  'homologation'
        if enviroment_type == 'homologation':
            host = 'https://admin.factura.gob.sv'
        else:
            host = 'https://admin.factura.gob.sv'
        fechaEmision =  str(fechaEmi.year) + "-" + str(fechaEmi.month).zfill(2) + "-" + str(fechaEmi.day).zfill(2)
        texto_codigo_qr = host + "/consultaPublica?ambiente=" + str(ambiente) + "&codGen=" + str(codGen) + "&fechaEmi=" + str(fechaEmision)
        _logger.info("SIT generando qr texto_codigo_qr = %s", texto_codigo_qr)
        codigo_qr = qrcode.QRCode(
            version=1,  # Versión del código QR (ajústala según tus necesidades)
            error_correction=qrcode.constants.ERROR_CORRECT_L,  # Nivel de corrección de errores
            box_size=10,  # Tamaño de los cuadros del código QR
            border=4,  # Ancho del borde del código QR
        )
        codigo_qr.add_data(texto_codigo_qr)
        #os.chdir('C:/Users/INCOE/PycharmProjects/fe/location/mnt/src')
        os.chdir('C:/Users/admin/Documents/GitHub/fe/location/mnt/certificado')
        directory = os.getcwd()
        _logger.info("SIT directory =%s", directory)
        basewidth = 100
        buffer = io.BytesIO()
        codigo_qr.make(fit=True)
        img = codigo_qr.make_image(fill_color="black", back_color="white")
        wpercent = (basewidth/float(img.size[0]))
        hsize = int((float(img.size[1])*float(wpercent)))
        new_img = img.resize((basewidth,hsize), Image.BICUBIC)
        new_img.save(buffer, format="PNG")
        qrCode = base64.b64encode(buffer.getvalue())
        # self.sit_qr_hacienda = qrCode
        return qrCode

    def generar_qr(self):
        _logger.info("SIT generando qr = %s", self)
        enviroment_type =  'homologation'
        if enviroment_type == 'homologation':
            host = 'https://admin.factura.gob.sv'
            ambiente = "00"
        else:
            host = 'https://admin.factura.gob.sv'
            ambiente = "01"
        texto_codigo_qr = host + "/consultaPublica?ambiente=" + str(ambiente) + "&codGen=" + str(self.hacienda_codigoGeneracion_identificacion) + "&fechaEmi=" + str(self.fecha_facturacion_hacienda)
        codigo_qr = qrcode.QRCode(
            version=1,  # Versión del código QR (ajústala según tus necesidades)
            error_correction=qrcode.constants.ERROR_CORRECT_L,  # Nivel de corrección de errores
            box_size=10,  # Tamaño de los cuadros del código QR
            border=1,  # Ancho del borde del código QR
        )
        codigo_qr.add_data(texto_codigo_qr)
        os.chdir('C:/Users/INCOE/Documents/GitHub/fe/location/mnt')
        directory = os.getcwd()

        _logger.info("SIT directory =%s", directory)
        basewidth = 100
        buffer = io.BytesIO()

        codigo_qr.make(fit=True)
        img = codigo_qr.make_image(fill_color="black", back_color="white")

        wpercent = (basewidth/float(img.size[0]))
        hsize = int((float(img.size[1])*float(wpercent)))
        new_img = img.resize((basewidth,hsize), Image.BICUBIC)
        new_img.save(buffer, format="PNG")
        qrCode = base64.b64encode(buffer.getvalue())
        self.sit_qr_hacienda = qrCode
        return

    def check_parametros_firmado(self):
        if not self.journal_id.sit_tipo_documento.codigo:
            raise UserError(_('El Tipo de DTE no definido.'))
        if not self.name:
            raise UserError(_('El Número de control no definido'))
        tipo_dte = self.journal_id.sit_tipo_documento.codigo

        if tipo_dte == '01':
            # Solo validar el nombre para DTE tipo 01
            if not self.partner_id.name:
                raise UserError(_('El receptor no tiene NOMBRE configurado para facturas tipo 01.'))
        elif tipo_dte == '03':
            # Validaciones completas para DTE tipo 03
            if not self.partner_id.fax and self.partner_id.is_company:
                _logger.info("SIT, es compañia se requiere NIT")
                raise UserError(_('El receptor no tiene NIT configurado.'))
            if not self.partner_id.nrc and self.partner_id.is_company:
                _logger.info("SIT, es compañia se requiere NRC")
                raise UserError(_('El receptor no tiene NRC configurado.'))
            if not self.partner_id.name:
                raise UserError(_('El receptor no tiene NOMBRE configurado.'))
            if not self.partner_id.codActividad:
                raise UserError(_('El receptor no tiene CODIGO DE ACTIVIDAD configurado.'))
            # if not self.partner_id.state_id:
            #     raise UserError(_('El receptor no tiene DEPARTAMENTO configurado.'))
            # if not self.partner_id.munic_id:
            #     raise UserError(_('El receptor no tiene MUNICIPIO configurado.'))
            # if not self.partner_id.email:
            #     raise UserError(_('El receptor no tiene CORREO configurado.'))
        elif tipo_dte == '14':
            # Validaciones completas para DTE tipo 03
            if not self.invoice_date:
                raise UserError(_('Se necesita establecer la fecha de factura.'))

        # Validaciones comunes para cualquier tipo de DTE
        if not self.invoice_line_ids:
            raise UserError(_('La factura no tiene LINEAS DE PRODUCTOS asociada.'))

    def check_parametros_linea_firmado(self, line_temp):
        if not line_temp["codigo"]:
            ERROR = 'El CODIGO del producto  ' + line_temp["descripcion"] + ' no está definido.'
            raise UserError(_(ERROR))
        if not line_temp["cantidad"]:
            ERROR = 'La CANTIDAD del producto  ' + line_temp["descripcion"] + ' no está definida.'
            raise UserError(_(ERROR))
        if not  line_temp["precioUni"]:
            ERROR = 'El PRECIO UNITARIO del producto  ' + line_temp["descripcion"] + ' no está definido.'
            raise UserError(_(ERROR))
        if not line_temp["uniMedida"]:
            ERROR = 'La UNIVAD DE MEDIDA del producto  ' + line_temp["descripcion"] + ' no está definido.'
            raise UserError(_(ERROR))

    def check_parametros_dte(self, generacion_dte):
        if not generacion_dte["idEnvio"]:
            ERROR = 'El IDENVIO  no está definido.'
            raise UserError(_(ERROR))
        if not generacion_dte["tipoDte"]:
            ERROR = 'El tipoDte  no está definido.'
            raise UserError(_(ERROR))
        if not generacion_dte["documento"]:
            ERROR = 'El DOCUMENTO  no está presente.'
            raise UserError(_(ERROR))
        if not generacion_dte["codigoGeneracion"]:
            ERROR = 'El codigoGeneracion  no está definido.'
            raise UserError(_(ERROR))

    def _evaluar_error_contingencia(self, status_code, origen="desconocido"):
        motivo_otro = False
        mensaje = ""
        contingencia_model = self.env['account.move.tipo_contingencia.field']

        if status_code in [500, 502, 503, 504, 408]:
            contingencia = contingencia_model.search([('codigo', '=', '01')], limit=1)
        elif status_code in [408, 499]:
            contingencia = contingencia_model.search([('codigo', '=', '02')], limit=1)
        elif status_code in [503, 504]:
            contingencia = contingencia_model.search([('codigo', '=', '04')], limit=1)
        else:
            contingencia = contingencia_model.search([('codigo', '=', '05')], limit=1)
            motivo_otro = True
            mensaje = f"Error grave en el envío ({origen}) - Código HTTP: {status_code}"

        return contingencia, motivo_otro, mensaje

    def _crear_contingencia(self, resp, data, mensaje):
        # ___Actualizar dte en contingencia
        max_intentos = 3
        if not data:
            data = {}

        codigo = data.get("codigoMsg") or "SIN_CODIGO"
        descripcion = data.get("descripcionMsg") or resp.text or "Error desconocido"
        _logger.warning("Creando contingencia por error MH: [%s] %s", codigo, descripcion)

        error_msg = _(mensaje)  # mensaje debe ser clave de traducción
        # error_msg = tmpl.format(
        #     max_intentos=max_intentos,
        #     **data,  # extiende data={'timestamp':…, 'status':…} a timestamp=…, status=…
        # )

        tipo_contingencia, motivo_otro, mensaje_motivo = self._evaluar_error_contingencia(
            status_code=resp.status_code,
            origen="envío DTE"
        )

        self.write({
            'error_log': error_msg,
            'sit_es_configencia': False,
            'sit_tipo_contingencia': tipo_contingencia.id if tipo_contingencia else False,
            # 'sit_tipo_contingencia_otro': mensaje_motivo,
        })
        _logger.warning("Guardando DTE en contingencia (%s): %s", tipo_contingencia.codigo if tipo_contingencia else "", self.name)

        _logger.warning("Buscando contingencia activa para empresa: %s", self.company_id.name)

        Contingencia = self.env['account.contingencia1']
        Lote = self.env['account.lote']

        # Buscar contingencia activa
        contingencia_activa = Contingencia.search([
            ('company_id', '=', self.company_id.id),
            ('sit_selloRecibido', '=', False),
            ('contingencia_activa', '=', True),
        ], limit=1)

        lote_asignado = None

        if contingencia_activa:
            _logger.info("Contingencia activa encontrada: %s", contingencia_activa.name)

            # Asociar esta factura a la contingencia
            self.write({'sit_factura_de_contingencia': contingencia_activa.id})

            # Buscar lote incompleto
            lotes_validos = Lote.search([
                ('sit_contingencia', '=', contingencia_activa.id),
                ('hacienda_codigoLote_lote', '=', False),
                ('lote_activo', '=', True),
            ])

            for lote in lotes_validos:
                if len(lote.move_ids) < 2:#100
                    if not self.sit_lote_contingencia:
                        self.write({'sit_lote_contingencia': lote.id})
                    else:
                        self.write({'sit_lote_contingencia': lote.id})
                    lote_asignado = lote
                    _logger.info("Factura asignada a lote existente: %s", lote.id)
                    break

            if not lote_asignado:
                num_lotes = Lote.search_count([('sit_contingencia', '=', contingencia_activa.id)])
                if num_lotes < 2:#400
                    lote_asignado = Lote.create({
                        'name': f"Lote de contingencia {contingencia_activa.name}-{num_lotes + 1}",
                        'sit_contingencia': contingencia_activa.id,
                        'lote_activo': True,
                    })
                    if not self.sit_lote_contingencia:
                        self.write({'sit_lote_contingencia': lote_asignado.id})
                        _logger.info("Factura asignada a nuevo lote: %s", lote_asignado.name)
                    else:
                        _logger.warning("Factura ya tenía un lote asignado al crear nuevo: %s", self.sit_lote_contingencia.name)
                else:
                    _logger.warning("Contingencia ya tiene 400 lotes. Creando nueva contingencia.")
                    contingencia_activa = None  # Forzar nueva contingencia
        else:
            _logger.info("No se encontró contingencia activa. Creando nueva.")

        # Si no hay contingencia activa o válida, crear una nueva
        if not contingencia_activa:
            # contingencia_activa = Contingencia.create({
            #     'company_id': self.company_id.id,
            #     'journal_id': self.journal_id.id,
            #     'sit_tipo_contingencia': tipo_contingencia.id if tipo_contingencia else False,
            #     'contingencia_activa': True,
            #     # 'move_ids': [(6, 0, [self.id])],
            #     # 'estado': 'pendiente',
            #     # 'motivo': f"Error {codigo}: {descripcion}",
            #     # 'respuesta_mh': resp.text,
            #     # 'codigo_generacion': self.codigoGeneracion,
            # })

            lote_asignado = Lote.create({
                'name': f"Lote de contingencia {contingencia_activa.name}-1",
                'sit_contingencia': contingencia_activa.id,
                'lote_activo': True,
            })
            self.write({'sit_lote_contingencia': lote_asignado.id})
            _logger.info("Creada nueva contingencia y lote: %s, %s", contingencia_activa.name, lote_asignado.name)

        _logger.info("Factura %s asignada a contingencia %s y lote %s", self.name, contingencia_activa.name,
                     lote_asignado.name if lote_asignado else "N/A")

    def sit_enviar_correo_dte_automatico(self):
        for invoice in self:
            # Validar que el DTE exista en hacienda
            if not invoice.recibido_mh:
                _logger.warning("SIT | La factura %s no tiene un DTE procesado, no se enviará correo.", invoice.name)
                continue

            _logger.info("SIT | DTE procesado correctamente para la factura %s. Procediendo con envío de correo.", invoice.name)

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
            if invoice.recibido_mh and not invoice.correo_enviado:
                try:
                    _logger.info("SIT | Enviando correo automático para la factura %s", invoice.name)
                    invoice.with_context(from_automatic=True).sudo().sit_action_send_mail()
                except Exception as e:
                    _logger.error("SIT | Error al intentar enviar el correo para la factura %s: %s", invoice.name, str(e))
            else:
                _logger.info("SIT | La correspondencia ya había sido transmitida. %s", invoice.name)

    # @api.model
    # def create(self, vals):
    #     move = super().create(vals)
    #     move._copiar_retenciones_desde_documento_relacionado()
    #     return move

    def write(self, vals):
        res = super().write(vals)
        if any(k in vals for k in ['codigo_tipo_documento', 'reversed_entry_id', 'debit_origin_id']):
            self._copiar_retenciones_desde_documento_relacionado()
        return res

    def _copiar_retenciones_desde_documento_relacionado(self):
        for move in self:
            origen = None
            if move.codigo_tipo_documento == '05' and move.reversed_entry_id:
                origen = move.reversed_entry_id
            elif move.codigo_tipo_documento == '06' and move.debit_origin_id:
                origen = move.debit_origin_id

            if not origen:
                continue

            move.apply_retencion_renta = origen.apply_retencion_renta
            move.retencion_renta_amount = origen.retencion_renta_amount

            move.apply_retencion_iva = origen.apply_retencion_iva
            move.retencion_iva_amount = origen.retencion_iva_amount

            move.apply_iva_percibido = origen.apply_iva_percibido
            move.iva_percibido_amount = origen.iva_percibido_amount
