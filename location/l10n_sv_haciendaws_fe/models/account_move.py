##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from odoo.tools import float_repr
# from odoo.addons.l10n_sv_haciendaws_fe.afip_utils import get_invoice_number_from_response
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
from datetime import datetime, timedelta, time, date
from decimal import Decimal
from copy import deepcopy
import pytz
from functools import cached_property
import ast
import re
import string
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import config_utils
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo config_utils [hacienda ws-account_move]")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    config_utils = None

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
EXTRA_ADDONS = os.path.join(PROJECT_ROOT, "mnt", "extra-addons", "src")

def _json_default(o):
        if isinstance(o, datetime):
            return o.strftime('%Y-%m-%dT%H:%M:%S')
        if isinstance(o, date):
            return o.strftime('%Y-%m-%d')
        if isinstance(o, time):
            return o.strftime('%H:%M:%S')
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, (bytes, bytearray)):
            return base64.b64encode(o).decode('ascii')
        return str(o)

def _sanitize(obj):
    if isinstance(obj, dict):
        return {k: _sanitize(v) if v is not None else None for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(x) for x in obj]
    if isinstance(obj, datetime):
        return obj.strftime('%Y-%m-%dT%H:%M:%S')
    if isinstance(obj, date):
        return obj.strftime('%Y-%m-%d')
    if isinstance(obj, time):
        return obj.strftime('%H:%M:%S')
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (bytes, bytearray)):
        return base64.b64encode(obj).decode('ascii')
    return obj


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
        string="Hacienda Observaciones",
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
    fecha_facturacion_hacienda = fields.Datetime("Fecha de Facturación - Hacienda",
                                                 help="Asignación de Fecha manual para registrarse en Hacienda", )

    name = fields.Char(
        readonly=True,  # Lo dejamos como solo lectura después de ser asignado
        copy=False,
        string="Número de Control",
    )

    error_log = fields.Text(string="Error técnico DTE", readonly=True)

    recibido_mh = fields.Boolean(string="Dte recibido por MH", copy=False)
    correo_enviado = fields.Boolean(string="Correo enviado en la creacion del dte", copy=False)
    invoice_time = fields.Char(string="Hora de Facturación", compute='_compute_invoice_time', store=True, readonly=True)

    # -----Busquedas de configuracion
    @property
    def url_firma(self):
        url = config_utils.get_config_value(self.env, 'url_firma', self.company_id.id)
        if not url:
            _logger.error("SIT | No se encontró 'url_firma' en la configuración para la compañía ID %s", self.company_id.id)
            raise UserError(_("La URL de firma no está configurada en la empresa."))
        return url

    @property
    def content_type(self):
        content = config_utils.get_config_value(self.env, 'content_type', self.company_id.id)
        if not content:
            _logger.error("SIT | No se encontró 'content_type' en la configuración para la compañía ID %s", self.company_id.id)
            raise UserError(_("El tipo de contenido[content_type] no está configurado en la empresa."))
        return content
    # -----FIN

    @api.onchange("partner_id")
    def _onchange_partner_id_set_journal(self):
        """Al seleccionar el cliente, sugerir el diario definido en el cliente."""
        if self.partner_id and self.partner_id.journal_id:
            # Solo asigna si no hay diario aún o si quieres sobreescribir
            if not self.journal_id:
                self.journal_id = self.partner_id.journal_id

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

    @api.model_create_multi
    def create(self, vals_list):
        _logger.info("SIT vals list: %s", vals_list)

        for vals in vals_list:
            company_id = vals.get("company_id") or self.env.company.id
            company = self.env["res.company"].browse(company_id)

            if not (company and company.sit_facturacion):
                _logger.info("Empresa '%s' NO aplica a DTE → se usará flujo estándar.", company.name)
                continue  # no tocamos nada, se creará normal

            move_type = vals.get('move_type')
            _logger.info("SIT modulo detectado: %s", move_type)

            # --- Extraer partner_id ---
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

            # --- Diario ---
            journal_id = vals.get('journal_id') or self._context.get('default_journal_id')
            journal = self.env['account.journal'].browse(journal_id) if journal_id else None

            # --- Solo diarios de venta (y compras): generar nombre desde secuencia (_generate_dte_name) ---
            if (journal and journal.type == 'sale') or move_type == 'in_invoice':
                name = vals.get('name')
                # Respetar si ya viene un nombre válido (cualquiera), solo generarlo si no hay o es '/'
                if not name or name == '/':  # and name.startswith('DTE-')):
                    # usar un record virtual para métodos que requieren ensure_one()
                    virtual_move = self.env['account.move'].new(vals)
                    # virtual_move._onchange_journal()  # por si depende del diario
                    generated_name = virtual_move._generate_dte_name()
                    if generated_name:
                        vals['name'] = generated_name
                        _logger.info("SIT Nombre generado dinámicamente (venta/compra): %s", vals['name'])
                else:
                    _logger.info("SIT Nombre provisto por el usuario/config: %s", name)

                # partner obligatorio para DTE
                if not vals.get('partner_id'):
                    raise UserError(_("No se pudo obtener el partner."))

                # códigoGeneracion_identificación
                if not vals.get('hacienda_codigoGeneracion_identificacion'):
                    vals['hacienda_codigoGeneracion_identificacion'] = self.sit_generar_uuid()
                    _logger.info("Codigo de generacion asignado: %s", vals['hacienda_codigoGeneracion_identificacion'])
            else:
                _logger.info("Diario '%s' no es venta (o move_type no es in_invoice), omito generación DTE", journal and journal.name)

            # ——— Para asientos contables (entry) ———
            if move_type == 'entry':
                # Si no viene nombre o viene como '/', asignarlo desde la secuencia del diario
                if not vals.get('name') or vals['name'] == '/':
                    j = journal or (
                        self.env['account.journal'].browse(vals.get('journal_id')) if vals.get('journal_id') else None)
                    if j and j.sequence_id:
                        # Reservar siguiente número de la secuencia del diario
                        vals['name'] = j.sequence_id.next_by_id()
                    else:
                        # Fallback genérico si el diario no tiene secuencia
                        vals['name'] = self.env['ir.sequence'].next_by_code('account.move') or '/'
                    _logger.info("SIT Asignado nombre de entry desde secuencia: %s", vals['name'])

            # Validación de duplicados antes de la creación
            existing_move = self.env['account.move'].search([('name', '=', vals.get('name'))], limit=1)
            if existing_move:
                _logger.warning("Documento duplicado detectado con el nombre: %s", vals.get('name'))
                continue  # No crear el duplicado, pasa al siguiente

        _logger.info("Valores finales antes de super().create: %s", vals_list)
        # no forzar name
        self._fields['name'].required = False
        records = super().create(vals_list)
        _logger.info("Registros creados: %s", records.ids)

        # Refuerzo para name si quedó en '/'
        for vals, rec in zip(vals_list, records):
            if vals.get('name') and vals['name'] != '/' and rec.name == '/':
                _logger.warning("Refuerzo name para rec ID %s: %s", rec.id, vals["name"])
                rec.name = vals['name']
                _logger.info("SIT Refuerzo name=%s", rec.name)

            rec._copiar_retenciones_desde_documento_relacionado()
        _logger.info("SIT FIN create")

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
            ('asynchronous_post', '=', True), '|',
            ('afip_result', '=', False),
            ('afip_result', '=', ''),
        ], limit=queue_limit)
        if queue:
            queue._post()

    @api.depends("journal_id", "afip_auth_code")
    def _compute_validation_type(self):
        for rec in self:
            rec.validation_type = False

            if rec.company_id and rec.company_id.sit_facturacion:
                if not rec.afip_auth_code:
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
            # Si la empresa no tiene facturación electrónica activa -> no generar QR
            if not (rec.company_id and rec.company_id.sit_facturacion):
                rec.afip_qr_code = False
                continue

            # Solo si tiene modo CAE/CAEA y un código de autorización
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
                        and rec.commercial_partner_id.vat
                ):
                    qr_dict["tipoDocRec"] = int(
                        rec.commercial_partner_id.l10n_latam_identification_type_id.l10n_ar_afip_code
                    )
                    qr_dict["nroDocRec"] = int(
                        rec.commercial_partner_id.vat.replace("-", "").replace(".", "")
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

    def _generate_dte_name(self, journal=None, actualizar_secuencia=False):
        """Genera nombre DTE solo si aplica facturación electrónica.
        Si actualizar_secuencia=True, consume la secuencia con next_by_id y la actualiza en BD.
        Si actualizar_secuencia=False, devuelve una previsualización sin consumir.
        """
        self.ensure_one()
        journal = journal or self.journal_id
        doc_electronico = False

        if journal and journal.sit_tipo_documento and journal.sit_tipo_documento.codigo:
            doc_electronico = True
        _logger.info("SIT diario: %s, tipo. %s, | es dte? %s | Actualizar secuencia? %s", journal, journal.type, doc_electronico, actualizar_secuencia)

        if self.company_id and self.company_id.sit_facturacion and doc_electronico:
            nuevo_numero = 0

            if journal.type not in ('sale', 'purchase'):
                return False

            if doc_electronico and not journal.sit_tipo_documento or not journal.sit_tipo_documento.codigo:
                raise UserError(_("Configure Tipo de DTE en diario '%s'.") % journal.name)
            if doc_electronico and not journal.sit_codestable:
                raise UserError(_("Configure Código de Establecimiento en diario '%s'.") % journal.name)

            tipo = journal.sit_tipo_documento.codigo
            punto_venta = journal.sit_codpuntoventa
            estable = journal.sit_codestable
            _logger.info("SIT tipo documento: %s, cod estable: %s, punto venta. %s", tipo, estable, punto_venta)

            if not journal.sequence_id:
                raise UserError(_("Configure la secuencia en el diario '%s'.") % journal.name)

            sequence = journal.sequence_id
            #seq_code = sequence.code

            # Los placeholders tipo/estable se sustituyen desde el contexto
            dte_param_tipo = config_utils.get_config_value(self.env, 'dte_prefix_tipo', self.company_id.id)  # 'dte'
            dte_param_puntoventa = config_utils.get_config_value(self.env, 'dte_prefix_puntoVenta', self.company_id.id)  # 'puntoVenta'
            dte_param_estable = config_utils.get_config_value(self.env, 'dte_prefix_codEstable', self.company_id.id)  # 'estable'
            _logger.info("SIT Parametros numero de control= tipo dte: %s(%s), cod estable: %s(%s), punto venta: %s(%s)", dte_param_tipo, tipo, dte_param_estable, estable, dte_param_puntoventa, punto_venta)

            if not dte_param_tipo or not dte_param_estable or not dte_param_puntoventa:
                raise UserError(_("Configure los parámetros de la plantilla de prefijo DTE para la empresa '%s'.") % self.company_id.name)

            # Enviar parametros del prefijo de la secuencia
            ctx = {dte_param_tipo: tipo, dte_param_puntoventa:punto_venta, dte_param_estable: estable}
            prefix_rendered = None
            res = sequence.with_context(**ctx)._get_prefix_suffix()
            if isinstance(res, tuple):
                prefix_rendered = res[0] or ''
            elif isinstance(res, dict):
                prefix_rendered = res.get('prefix', '') or ''
            else:
                prefix_rendered = ''
            _logger.info("SIT Prefijo resuelto: %s", prefix_rendered)

            # Si Odoo ya puso un nombre que empieza con este prefijo → lo reusamos
            if not actualizar_secuencia and self.name and self.name.startswith(prefix_rendered):
                _logger.info("SIT Reutilizando número ya asignado por Odoo: %s", self.name)
                return self.name

            # Buscar último documento usando prefijo dinámico
            domain = [
                ('journal_id', '=', journal.id),
                ('name', 'like', prefix_rendered + '%'),
                ('company_id', '=', self.company_id.id)
            ]
            ultimo = self.search(domain, order='name desc', limit=1)

            # Ajuste de secuencia según último DTE emitido
            ultima_parte = 0
            siguiente_dte = 0
            if ultimo:
                try:
                    ultima_parte = int(ultimo.name.split('-')[-1])
                except ValueError:
                    raise UserError(_("No se pudo interpretar el número del último DTE: %s") % ultimo.name)
                siguiente_dte = ultima_parte + 1
            else:
                ultima_parte = 0
                siguiente_dte = 1

            _logger.info("SIT Ultimo num. control: %s(correlativo: %s) ", ultimo.name if ultimo else None, ultima_parte)

            # Obtener secuencia configurada
            date_range = None
            seq_next = sequence.number_next_actual
            _logger.info("SIT Ultimo num. control: %s(correlativo: %s) | Siguiente numero:%s ", ultimo.name, ultima_parte, siguiente_dte)
            if sequence:
                _logger.info("SIT | Sequence: %s", sequence)
                if sequence.use_date_range:
                    today = fields.Date.context_today(self)
                    date_range = self.env['ir.sequence.date_range'].search([
                        ('sequence_id', '=', sequence.id),
                        ('date_from', '<=', today),
                        ('date_to', '>=', today)
                    ], limit=1)
                    if date_range:
                        seq_next = date_range.number_next_actual

                # ------------------------------
                if ultima_parte >= seq_next:
                    siguiente_dte = ultima_parte + 1
                else:
                    siguiente_dte = seq_next
                _logger.info("SIT Control correlativos → Ultimo BD: %s | Seq: %s | Siguiente: %s", ultima_parte, seq_next, siguiente_dte)

                if sequence.use_date_range and date_range:
                    if date_range.number_next_actual < siguiente_dte:
                        _logger.info("SIT | Corrigiendo desfase date_range: estaba %s, ajustando a %s", date_range.number_next_actual, siguiente_dte)
                        date_range.number_next_actual = siguiente_dte
                        #candidate_num = date_range.number_next_actual if date_range else sequence.number_next_actual
                else:
                    # if sequence.number_next_actual < nuevo_numero:
                    if sequence.number_next_actual < siguiente_dte:
                        _logger.info("SIT | Corrigiendo desfase sequence: estaba %s, ajustando a %s", sequence.number_next_actual, siguiente_dte)
                        sequence.number_next_actual = siguiente_dte
                #candidate_num = sequence.number_next_actual

            # 1) obtener prefijo de la secuencia
            prefix_raw = (sequence.prefix or '').strip()
            _logger.info("SIT Prefijo secuencia raw: %s", prefix_raw)

            # 2) extraer placeholders estilo %(... )s
            placeholders_in_prefix = re.findall(r'%\(([^)]+)\)s', prefix_raw)

            # 3) fallback: si no hay, intentar formato con {} (str.format)
            if not placeholders_in_prefix:
                placeholders_in_prefix = [fname for _, fname, _, _ in string.Formatter().parse(prefix_raw) if fname]

            _logger.info("SIT placeholders extraidos de la secuencia: %s", placeholders_in_prefix)

            # 4) validar coincidencia (respetando case; opcional: normalizar .lower())
            missing = [ph for ph in placeholders_in_prefix if ph not in ctx]
            extra = [k for k in ctx.keys() if k not in placeholders_in_prefix]

            if missing or extra:
                msg_parts = []
                if missing:
                    msg_parts.append("Faltan valores para los placeholders en la secuencia: %s" % missing)
                if extra:
                    msg_parts.append(
                        "Hay parámetros configurados que no aparecen en el prefijo de la secuencia: %s" % extra)
                # log informativo y raise para que el usuario corrija configuración/sequence
                _logger.error("SIT Error coincidencia placeholders: %s", "; ".join(msg_parts))
                raise UserError(_("Error en parámetros DTE: %s") % ("; ".join(msg_parts)))

            # nuevo_name = journal.sequence_id.with_context(dte=tipo, estable=estable).next_by_id()
            # Si queremos consumir/actualizar la secuencia -> usar next_by_id (esto YA actualiza ir.sequence)

            # ----------------------------
            # GENERACIÓN FINAL DEL NOMBRE
            # ----------------------------
            nuevo_name = None
            if actualizar_secuencia:
                # Consume la secuencia y actualiza ir.sequence/date_range automáticamente
                nuevo_name = sequence.with_context(**ctx).next_by_id(
                    sequence_date=self.invoice_date)  # **ctx convierte un diccionario en argumentos separados
                # Ahora forzamos el incremento si ya está actualizado
                if int(nuevo_name.split('-')[-1]) < siguiente_dte:
                    #siguiente_dte = int(nuevo_name.split('-')[-1]) + 1
                    nuevo_name = f"{prefix_rendered}{str(siguiente_dte).zfill(15)}"

                # Forzar la actualización del siguiente número en la secuencia
                if sequence.use_date_range and date_range:
                    date_range.number_next_actual = siguiente_dte
                else:
                    sequence.number_next_actual = siguiente_dte
            else:
                # Solo previsualización, construimos nombre sin afectar secuencia
                nuevo_name = f"{prefix_rendered}{str(siguiente_dte).zfill(15)}"

            # Verificar duplicado antes de retornar
            # if self.search_count([('name', '=', nuevo_name), ('journal_id', '=', journal.id)]):
            #     raise UserError(_("El número DTE generado ya existe en la base de datos: %s") % nuevo_name)
            # _logger.info("SIT Nombre DTE generado y secuencia consumida: %s", nuevo_name)

            # Actualizar secuencia (ir.sequence o ir.sequence.date_range)
            # if actualizar_secuencia and sequence:
            #   next_num = nuevo_numero + 1
            #  if sequence.use_date_range:
            #     if date_range and date_range.number_next_actual < next_num:
            #        #date_range.number_next_actual = next_num
            #       nuevo_numero = seq.next_by_id(sequence_date=self.invoice_date, context=ctx)
            #      _logger.info("SIT Secuencia con date_range '%s' actualizada a %s", seq_code, next_num)
            # else:
            #   if sequence.number_next_actual < next_num:
            #      #sequence.number_next_actual = next_num
            #     nuevo_numero = seq._next_do(sequence_date=self.invoice_date, context=ctx)
            #    _logger.info("SIT Secuencia '%s' actualizada a %s", seq_code, next_num)

            # _logger.info("SIT Actualizar secuencia _generar_dte_name(): %s", actualizar_secuencia)

            return nuevo_name
        else:
            return None  # <--- Omitir, que Odoo siga normal

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
        _logger.info("SIT Actualizar secuencia: %s", self.name)

        # Validar empresa
        if not (self.company_id and self.company_id.sit_facturacion):
            _logger.info("SIT No aplica actualización de secuencia (empresa sin facturación electrónica).")
            return

        # Validar diario y configuración
        if not self.journal_id or not self.journal_id.sit_tipo_documento or not self.journal_id.sit_codestable:
            _logger.info("SIT No aplica actualización de secuencia (diario sin configuración).")
            return

        # Usar la secuencia configurada en el diario (no quemar nada)
        sequence = self.journal_id.sequence_id
        if not sequence:
            _logger.warning("SIT El diario '%s' no tiene secuencia configurada", self.journal_id.display_name)
            return

        #tipo = self.journal_id.sit_tipo_documento.codigo
        #estable = self.journal_id.sit_codestable
        #seq_code = f'dte.{tipo}'
        numero_control = self.name
        try:
            secuencia_actual = int(numero_control.split("-")[-1])
        except Exception:
            secuencia_actual = 0
        #sequence = self.env['ir.sequence'].search([('code', '=', seq_code)], limit=1)

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
                _logger.info("SIT Secuencia con date_range '%s' actualizada a %s", sequence.code, next_num)
        else:
            if sequence.number_next_actual < next_num:
                sequence.number_next_actual = next_num
                _logger.info("SIT Secuencia '%s' actualizada a %s", sequence.code, next_num)

    def _post(self, soft=True):
        """Override para:
        - Diarios sale: generar/validar DTE y enviar a Hacienda.
        - Resto: usar secuencia estándar y omitir DTE.
        """
        mensajes_contingencia = []
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

        # 2) Facturas que sí aplican a DTE
        for invoice in invoices_to_post:
            documento_firmado = None
            doc_electronico = False
            # Si el dte ya está posteado, no seguimos
            if invoice.state == "posted":
                _logger.warning("El documento ID %s ya está en estado 'publicado', se omite el reproceso." % invoice.id)
                continue

            # Condicional: Si la empresa no aplica a facturación electrónica, usar el flujo estándar
            if not (invoice.company_id and invoice.company_id.sit_facturacion):
                _logger.info("Empresa aplica a facturacion? %s" % invoice.company_id.sit_facturacion)
                _logger.info("Factura ID %s no aplica a facturación electrónica, usando secuencia estándar." % invoice.id)

                # Verificamos si el diario tiene secuencia y asignamos el nombre automáticamente
                if invoice.journal_id.sequence_id:
                    _logger.info("Aplicando nombre estándar desde secuencia para factura ID %s." % invoice.id)
                    invoice.name = invoice.journal_id.sequence_id.next_by_id()
                    _logger.info("Factura ID %s nombre asignado automáticamente: %s" % (invoice.id, invoice.name))
                else:
                    _logger.warning(
                        "Factura ID %s no tiene secuencia configurada en el diario, asignando nombre por defecto." % invoice.id)
                    invoice.name = "Factura-%s" % invoice.id  # Nombre por defecto si no hay secuencia

                continue # No entra en la lógica de DTE si no aplica a facturación electrónica
            # Si sí aplica a facturación electrónica, no tocamos nada, Odoo maneja el resto
            else:
                _logger.info("Factura ID %s aplica a facturación electrónica, usando flujo personalizado." % invoice.id)

            if invoice.hacienda_selloRecibido and invoice.recibido_mh:
                raise UserError("Documento ya se encuentra procesado")

            try:
                journal = invoice.journal_id
                if journal and journal.sit_tipo_documento and journal.sit_tipo_documento.codigo:
                    doc_electronico = True
                _logger.info("SIT Procesando invoice %s (journal=%s, es documento electronico? %s)", invoice.id, journal.name, doc_electronico)

                if not self.invoice_time:
                    self._compute_invoice_time()

                # —————————————————————————————————————————————
                # A) DIARIOS NO-VENTA/COMPRA: saltar lógica DTE
                # —————————————————————————————————————————————
                if journal.type not in ('sale', 'purchase'):  # or invoice.move_type not in ('out_invoice', 'out_refund'):
                    _logger.info("Diario '%s' no aplica, omito DTE en _post", journal.name)
                    continue # Dejar que Odoo asigne su name normal en el super al final

                # —————————————————————————————————————————————
                # B) DIARIOS VENTA: generación/validación de DTE
                # —————————————————————————————————————————————
                # 1) Número de control DTE
                prefix = (config_utils.get_config_value(self.env, 'dte_prefix', self.company_id.id) or "DTE-").lower()
                if doc_electronico and not (invoice.name and invoice.name.startswith(prefix)):
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
                    if type_report and type_report.lower() == constants.TYPE_REPORT_CCF:
                        # Validaciones específicas para CCF
                        if not invoice.partner_id.parent_id:
                            if not invoice.partner_id.nrc:
                                invoice.msg_error("N.R.C.")
                            if not invoice.partner_id.vat and not invoice.partner_id.dui:
                                invoice.msg_error("N.I.T O D.U.I.")
                            if not invoice.partner_id.codActividad:
                                invoice.msg_error("Giro o Actividad Económica")
                        else:
                            if not invoice.partner_id.parent_id.nrc:
                                invoice.msg_error("N.R.C.")
                            if not invoice.partner_id.parent_id.vat and not invoice.partner_id.parent_id.dui:
                                invoice.msg_error("N.I.T O D.U.I.")
                            if not invoice.partner_id.parent_id.codActividad:
                                invoice.msg_error("Giro o Actividad Económica")
                    elif type_report and type_report.lower() == constants.TYPE_REPORT_NDC:
                        # Asignar el partner_id relacionado con el crédito fiscal si no existe parent_id
                        if not invoice.partner_id.parent_id:
                            if not invoice.partner_id.nrc:
                                invoice.msg_error("N.R.C.")
                            if not invoice.partner_id.vat:
                                invoice.msg_error("N.I.T.")
                            if not invoice.partner_id.codActividad:
                                invoice.msg_error("Giro o Actividad Económica")
                        else:
                            parent = invoice.partner_id.parent_id
                            if not invoice.partner_id.parent_id.nrc:
                                invoice.msg_error("N.R.C.")
                            if not invoice.partner_id.parent_id.vat:
                                invoice.msg_error("N.I.T.")
                            if not invoice.partner_id.parent_id.codActividad:
                                invoice.msg_error("Giro o Actividad Económica")

                    ambiente = None
                    ambiente_test = False
                    if config_utils:
                        ambiente = config_utils.compute_validation_type_2(self.env)
                        ambiente_test = config_utils._compute_validation_type_2(self.env, self.company_id)
                        _logger.info("SIT Tipo de entorno[Ambiente]: %s, tipo entorno contabilidad[Ambiente test]: %s", ambiente, ambiente_test)

                    # Generar json del DTE
                    payload = invoice.obtener_payload(ambiente, sit_tipo_documento)

                    # Firmar el documento y generar el DTE
                    if not ambiente_test:
                        try:
                            documento_firmado = invoice.firmar_documento(ambiente, payload)
                            _logger.info("Documento firmado: %s", documento_firmado)
                        except Exception as e:
                            _logger.error("Error al firmar documento: %s", e)
                            raise

                        if not documento_firmado:
                            raise UserError("Error en firma del documento")

                    # if documento_firmado:
                    _logger.info("SIT Firmado de documento")
                    payload_dte = invoice.sit_obtener_payload_dte_info(ambiente, documento_firmado)
                    self.check_parametros_dte(payload_dte, ambiente_test)

                    # Intentar generar el DTE
                    Resultado = invoice.generar_dte(ambiente, payload_dte, payload, ambiente_test)
                    _logger.warning("SIT Resultado. =%s, estado=%s", Resultado, Resultado.get('estado', ''))

                    # Si el resp es un rechazo por número de control
                    if not ambiente_test and isinstance(Resultado, dict) and Resultado.get('estado', '').strip().lower() == 'rechazado' and Resultado.get('codigoMsg') == '004':
                        descripcion = Resultado.get('descripcionMsg', '')
                        _logger.warning("SIT Descripcion error: %s", descripcion)
                        if 'identificacion.numerocontrol' in descripcion.lower():
                            _logger.warning("SIT DTE rechazado por número de control duplicado. Generando nuevo número.")

                            # Generar nuevo número de control
                            nuevo_nombre = invoice._generate_dte_name(actualizar_secuencia=True)
                            # Verifica si el nuevo nombre es diferente antes de actualizar
                            if nuevo_nombre != invoice.name:
                                _logger.info("SIT Actualizando nombre DTE: %s a %s", invoice.name, nuevo_nombre)
                                invoice.write({'name': nuevo_nombre})  # Actualiza el nombre
                                invoice.sequence_number = int(nuevo_nombre.split("-")[-1])
                                _logger.info("SIT name actualizado: %s | sequence number: %s", invoice.name, invoice.sequence_number)

                                # Forzar un commit explícito a la base de datos
                                invoice._cr.commit()
                            else:
                                _logger.info("SIT El nombre ya está actualizado, no se requiere escribir.")

                            # Reemplazar numeroControl en el payload original
                            payload['dteJson']['identificacion']['numeroControl'] = nuevo_nombre

                            # Volver a firmar con el nuevo número
                            documento_firmado = invoice.firmar_documento(ambiente, payload)
                            if not documento_firmado:
                                raise UserError(
                                    _('SIT Documento NO Firmado después de reintento con nuevo número de control'))

                            # Intentar nuevamente generar el DTE
                            payload_dte = invoice.sit_obtener_payload_dte_info(ambiente, documento_firmado)
                            self.check_parametros_dte(payload_dte, ambiente_test)
                            Resultado = invoice.generar_dte(ambiente, payload_dte, payload, ambiente_test)

                    # Guardar json generado
                    json_dte = payload['dteJson']
                    _logger.info("Tipo de dteJson: %s | SIT JSON=%s", type(json_dte), json_dte)

                    # Solo serializar si no es string
                    try:
                        if isinstance(json_dte, str):
                            try:
                                json_dte = json.loads(json_dte) # Verifica si es un JSON string válido, y lo convierte a dict
                            except json.JSONDecodeError:
                                invoice.sit_json_respuesta = json_dte # Ya era string, pero no era JSON válido -> guardar tal cual
                            else:
                                invoice.sit_json_respuesta = json.dumps(_sanitize(json_dte), ensure_ascii=False) # Era un JSON string válido → ahora es dict
                        elif isinstance(json_dte, dict):
                            invoice.sit_json_respuesta = json.dumps(_sanitize(json_dte), ensure_ascii=False)
                        else:
                            # Otro tipo de dato no esperado
                            invoice.sit_json_respuesta = str(json_dte)
                    except Exception as e:
                        _logger.warning("No se pudo guardar el JSON del DTE: %s", e)

                    estado = None
                    if Resultado and Resultado.get('estado'):
                        estado = Resultado['estado'].strip().lower()

                    if Resultado and Resultado.get('estado', '').lower() == 'procesado':  # if Resultado:
                        invoice.actualizar_secuencia()

                        _logger.info("SIT Resultado DTE | Estado DTE: %s", estado)
                        # Fecha de procesamiento
                        #fh_procesamiento = Resultado['fhProcesamiento'] if Resultado and Resultado['fhProcesamiento'] and not ambiente_test else self.invoice_time
                        fh_procesamiento = None
                        if Resultado and Resultado.get('fhProcesamiento') and not ambiente_test:
                            fh_procesamiento = Resultado.get('fhProcesamiento')
                        if not fh_procesamiento:
                            fh_procesamiento = self.invoice_time

                        _logger.info("SIT Fecha factura=%s", fh_procesamiento)
                        if fh_procesamiento:
                            try:
                                fh_dt = datetime.strptime(fh_procesamiento, '%d/%m/%Y %H:%M:%S') + timedelta(hours=6)
                                if not invoice.fecha_facturacion_hacienda:
                                    invoice.fecha_facturacion_hacienda = fh_dt
                            except Exception as e:
                                _logger.warning("Error al parsear fhProcesamiento: %s", e)
                        _logger.info("SIT Fecha facturacion=%s", invoice.fecha_facturacion_hacienda)

                        if ambiente_test:
                            invoice.write({
                                'hacienda_estado': Resultado.get('estado'),
                                'hacienda_descripcionMsg': Resultado.get('descripcionMsg'),
                                'hacienda_observaciones': str(Resultado.get('observaciones', '')),
                                'state': 'posted',  # <-- ¡Actualizamos el estado!
                            })
                            # Si no manejas el caso de éxito para el entorno de prueba, la ejecución continúa,
                            # pero el estado ya está actualizado. Puedes agregar un `return` para salir aquí si es el final de la ejecución.

                        # Procesar la respuesta de Hacienda
                        if not ambiente_test:
                            invoice.hacienda_estado = Resultado['estado']
                            invoice.hacienda_codigoGeneracion_identificacion = self.hacienda_codigoGeneracion_identificacion
                            _logger.info("Codigo de generacion session: %s, codigo generacion bd: %s", self.hacienda_codigoGeneracion_identificacion, invoice.hacienda_codigoGeneracion_identificacion)
                            invoice.hacienda_selloRecibido = Resultado['selloRecibido']
                            invoice.hacienda_clasificaMsg = Resultado['clasificaMsg']
                            invoice.hacienda_codigoMsg = Resultado['codigoMsg']
                            invoice.hacienda_descripcionMsg = Resultado['descripcionMsg']
                            invoice.hacienda_observaciones = str(Resultado['observaciones'])

                            codigo_qr = invoice._generar_qr(ambiente, self.hacienda_codigoGeneracion_identificacion, invoice.fecha_facturacion_hacienda)
                            invoice.sit_qr_hacienda = codigo_qr

                        if documento_firmado:
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
                            'mimetype': str(config_utils.get_config_value(self.env, 'content_type', self.company_id.id))
                            # 'application/json'
                        })
                        _logger.info("SIT JSON creado y adjuntado.")

                        # Respuesta json
                        if not ambiente_test:
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
                                'state': 'posted',
                                'recibido_mh': True,
                            })
                        else:
                            invoice.write({
                                'state': 'posted',
                            })
                        _logger.info("SIT Estado registro= %s.", invoice.state)

                        self.message_post(
                            body=_("Documento procesado correctamente por Hacienda.")
                        )

                        # Guardar archivo .pdf y enviar correo al cliente
                        try:
                            self.with_context(from_button=False, from_invalidacion=False).sit_enviar_correo_dte_automatico()
                        except Exception as e:
                            _logger.warning("SIT | Error al enviar DTE por correo o generar PDF: %s", str(e))

                        return {
                            'type': 'ir.actions.client',
                            'tag': 'display_notification',
                            'params': {
                                'title': 'DTE procesado correctamente',
                                'message': 'El documento ha sido recibido y sellado por Hacienda.',
                                'type': 'success',
                                'sticky': False,
                            }
                        }

                    if isinstance(Resultado, dict) and Resultado.get('type') == 'ir.actions.client':
                        mensajes_contingencia.append(Resultado)
                    else:
                        _logger.info("=== SIT Error en DTE")
                        # Lanzar error al final si fue rechazado
                        if estado:
                            _logger.info("SIT Estado DTE guardado: %s", estado)
                            if estado == 'rechazado':
                                invoice.hacienda_estado = estado
                                mensaje = Resultado['descripcionMsg'] or _('Documento rechazado por Hacienda.')
                                mensaje_completo = _(
                                    "DTE rechazado por MH:\n"
                                    "Número de control: %s\n"
                                    "%s\n\n"
                                    "Por favor, vuelva a confirmar el documento."
                                ) % (invoice.name, mensaje)
                                invoice.write({'state': 'draft'})
                                self.env.cr.commit()
                                raise UserError(mensaje_completo)
                            elif estado not in ('procesado', ''):
                                invoice.hacienda_estado = estado
                                mensaje = Resultado.get('descripcionMsg') or _('DTE no procesado correctamente')
                                raise UserError(_("Respuesta inesperada de Hacienda. Estado: %s\nMensaje: %s") % (estado, mensaje))

                    # 2) Validar formato
                    if not invoice.name.startswith("DTE-"):
                        raise UserError(_("Número de control DTE inválido para la factura %s.") % invoice.id)
            except UserError:
                # Si el error es un UserError (como el que lanzas en sit_ccf_base_map_invoice_info_resumen),
                # Odoo lo manejará y mostrará el mensaje en una ventana emergente.
                # No necesitas hacer nada aquí, solo relanzar la excepción.
                raise

            except Exception as e:
                error_msg = traceback.format_exc()
                _logger.exception("SIT Error durante el _post para invoice ID %s: %s", invoice.id, str(e))
                invoice.write({
                    'error_log': error_msg,
                    'state': 'draft',
                    'sit_es_configencia': False,
                })
                # errores_dte.append("Factura %s: %s" % (invoice.name or invoice.id, str(e)))
                # UserError(_("Error al procesar la factura %s:\n%s") % (invoice.name or invoice.id, str(e)))
        _logger.info("SIT Fin _post")

        # Solo llamar al super si quedan invoices sin postear
        draft_invoices = invoices_to_post.filtered(lambda m: m.state == 'draft')
        if draft_invoices:
            return super(AccountMove, draft_invoices)._post(soft=soft)
        return True
        # return super(AccountMove, self)._post(soft=soft)

    # def _compute_validation_type_2(self):
    #     environment_type = False
    #     for rec in self:
    #         # Validar si la empresa aplica facturación electrónica
    #         if not (rec.company_id and rec.company_id.sit_facturacion):
    #             _logger.info("SIT No aplica facturación electrónica.")
    #             return False
    #
    #         parameter_env_type = self.env["ir.config_parameter"].sudo().get_param("afip.ws.env.type")
    #         if parameter_env_type == "production":
    #             environment_type = "01"
    #         else:
    #             environment_type = "00"
    #     return environment_type
    # FIMAR FIMAR FIRMAR =======

    # ======================== FIRMA ===========================
    def firmar_documento(self, enviroment_type, payload):
        """
        Envía al firmador un payload con:
        {
            "nit": "...",
            "activo": true,
            "passwordPri": "...",
            "dteJson": { ... }   # SIEMPRE dict (no string)
        }
        Sanitiza fechas/horas/Decimal/bytes antes de serializar.
        Retorna el body parseado (dict) cuando status == 'OK'.
        """

        # ——————————— Validación de facturación electrónica ———————————
        if not (self.company_id and self.company_id.sit_facturacion):
            _logger.info("SIT La empresa no aplica facturación electrónica. Omite firma de documento.")
            return [{"status": "SKIPPED", "mensaje": "Empresa no aplica facturación electrónica"}]

        resultado = []
        dte_json = None  # para logging en except

        try:
            _logger.info("SIT  Firmando documento (raw) = %s", payload)

            url = getattr(self, 'url_firma', None) or "http://192.168.2.49:8113/firmardocumento/"
            _logger.info("SIT Url firma: %s", url)

            headers = {
                'Content-Type': 'application/json'
            }

            nit = payload.get("nit")
            passwordPri = payload.get("passwordPri")
            raw_dte = payload.get("dteJson")
            _logger.info("Json DTE a firmar= %s", raw_dte)

            # Validar que dteJson exista y no esté vacío
            if not raw_dte or (isinstance(raw_dte, str) and not raw_dte.strip()):
                msg = "El JSON del DTE está vacío o inválido"
                _logger.error(msg)
                return [{"status": "ERROR", "mensaje": msg}]

            # Asegurar que dteJson sea dict (no string JSON)
            if isinstance(raw_dte, str):
                try:
                    dte_json = json.loads(raw_dte)
                    _logger.debug("SIT dteJson parseado desde string a dict.")
                except json.JSONDecodeError:
                    msg = "El campo dteJson no contiene JSON válido."
                    _logger.error(msg)
                    return [{"status": "ERROR", "mensaje": msg}]
            elif isinstance(raw_dte, dict):
                dte_json = raw_dte
            else:
                msg = "El campo dteJson debe ser dict o string JSON."
                _logger.error(msg)
                return [{"status": "ERROR", "mensaje": msg}]

            # Sanitizar recursivamente (fechas/horas/decimal/bytes)
            payload_firma = {
                "nit": nit,
                "activo": True,
                "passwordPri": passwordPri,
                "dteJson": _sanitize(deepcopy(dte_json)),
            }
            # Log de lo que realmente se envía (serializado seguro)
            _logger.info("SIT Payload a firmador (sanitizado) = %s", json.dumps(payload_firma, default=_json_default, ensure_ascii=False))

            max_intentos = 3
            for intento in range(1, max_intentos + 1):
                _logger.info("Intento %s de %s para firmar el documento", intento, max_intentos)
                try:
                    # Usa json=... para que requests ponga Content-Type y encodee;
                    # igual ya sanitizamos, así que no habrá problema con fechas/Decimal
                    response = requests.post(url, headers=headers, json=payload_firma, timeout=30)
                    txt = response.text
                    _logger.info("SIT firmar_documento response.status=%s body=%s", response.status_code, txt)

                    # Si no es JSON, error claro
                    try:
                        json_response = response.json()
                    except ValueError:
                        if intento == max_intentos:
                            raise UserError(_("Respuesta no JSON de firmador: %s") % txt)
                        _logger.warning("Respuesta no JSON, reintentando...")
                        continue

                    status = json_response.get('status')

                    # Errores conocidos
                    if status in [400, 401, 402, 'ERROR']:
                        _logger.info("SIT Error 40X  =%s", status)
                        error = json_response.get('error')
                        message = json_response.get('message')
                        MENSAJE_ERROR = f"Código de Error: {status}, Error: {error}, Detalle: {message}"
                        # raise UserError(_(MENSAJE_ERROR))
                        _logger.warning("Error de firma intento %s: %s", intento, MENSAJE_ERROR)
                        resultado.append({"status": status, "mensaje": MENSAJE_ERROR})
                        if intento == max_intentos:
                            return resultado
                        continue

                    if status == 'OK': # OK
                        body = json_response.get('body')
                        # body puede venir ya como dict o como string JSON
                        if isinstance(body, str):
                            try:
                                body = json.loads(body)
                                _logger.info("SIT Body parseado a JSON correctamente")
                            except Exception:
                                _logger.info("SIT Body no era JSON, se retorna tal cual como string")
                        _logger.info("SIT Firma OK, regresando al post")
                        return body

                    # Respuesta inesperada
                    _logger.warning("Respuesta inesperada en firma, intento %s: %s", intento, json_response)
                    if intento == max_intentos:
                        raise UserError(_("No se pudo firmar el documento. Respuesta inesperada."))
                except Exception as e:
                    _logger.warning("Excepción en firma intento %s: %s", intento, str(e))
                    if intento == max_intentos:
                        # Mensaje claro para usuario
                        try:
                            # algunos errores vienen con JSON embebido en el texto
                            ed = json.loads(str(e)) if isinstance(e, str) else {}
                            MENSAJE_ERROR = f"{ed.get('status', '')}, {ed.get('error', '')}, {ed.get('message', '')}"
                        except Exception:
                            MENSAJE_ERROR = str(e)
                        raise UserError(_(MENSAJE_ERROR))
                    continue

            # Fallback si no retornó antes
            raise UserError(_("No se pudo firmar el documento. Inténtelo nuevamente más tarde."))
        except Exception as e_general:
            _logger.info("Error general en firmar_documento: %s", e_general)
            _logger.info("Tipo de dte_json (si existe): %s", type(dte_json) if dte_json is not None else 'No definido')
            _logger.info("Contenido de dte_json (si existe): %s", dte_json if dte_json is not None else 'No definido')
            raise

    def obtener_payload(self, enviroment_type, sit_tipo_documento):
        _logger.info("SIT  Obteniendo payload | Tipo de documento= %s", sit_tipo_documento)

        # Validar si la empresa aplica facturación electrónica
        if not (self.company_id and self.company_id.sit_facturacion):
            _logger.info("SIT No aplica facturación electrónica. Se omite payload.")
            return False

        invoice_info = None

        if sit_tipo_documento in (constants.COD_DTE_FE, "13"):
            invoice_info = self.sit_base_map_invoice_info()
            _logger.info("SIT invoice_info FE = %s", invoice_info)
            self.check_parametros_firmado()
        elif sit_tipo_documento == constants.COD_DTE_CCF:
            invoice_info = self.sit__ccf_base_map_invoice_info()
            _logger.info("SIT invoice_info CCF = %s", invoice_info)
            self.check_parametros_firmado()
        elif sit_tipo_documento == constants.COD_DTE_NC:
            invoice_info = self.sit_base_map_invoice_info_ndc()
            self.check_parametros_firmado()
        elif sit_tipo_documento == constants.COD_DTE_ND:
            invoice_info = self.sit_base_map_invoice_info_ndd()
            self.check_parametros_firmado()
        elif sit_tipo_documento == constants.COD_DTE_FEX:
            invoice_info = self.sit_base_map_invoice_info_fex()
            _logger.info("SIT invoice_info FEX = %s", invoice_info)
            self.check_parametros_firmado()
        elif sit_tipo_documento == constants.COD_DTE_FSE:
            invoice_info = self.sit_base_map_invoice_info_fse()
            _logger.info("SIT invoice_info FSE = %s", invoice_info)
            self.check_parametros_firmado()
        _logger.info("SIT payload_data =%s", invoice_info)
        return invoice_info

    # FRANCISCO # SE OBTIENE EL JWT Y SE ENVIA A HACIENDA PARA SU VALIDACION
    def generar_dte(self, environment_type, payload, payload_original, ambiente_test):
        """
        1) Refresca el token si caducó.
        2) Si no hay JWT en payload['documento'], llama al firmador.
        3) Envía el JWT firmado a Hacienda.
        4) Gestiona el caso 004 (YA EXISTE) para no dejar en borrador.
        """

        # ——— Validar si aplica facturación electrónica ———
        if not (self.company_id and self.company_id.sit_facturacion):
            _logger.info("SIT No aplica facturación electrónica. Se omite generación de DTE.")
            return False

        _logger.info("SIT Generando Dte account_move | payload: %s", payload_original)
        data = None
        max_intentos = 3
        url_receive = None
        dte_json = None
        # ——— 1) Selección de URL de Hacienda ———
        # url rest = "https://apitest.dtes.mh.gob.sv"
        # url prod = "https://api.dtes.mh.gob.sv"
        _logger.info("SIT Tipo de entorno[Ambiente]: %s", ambiente_test)

        # Validar y parsear dteJson si es string
        # dte_json_raw = payload_original.get("dteJson")

        # if not dte_json_raw or not str(dte_json_raw).strip():
        #     _logger.error("El JSON del DTE está vacío o inválido")
        #     raise UserError("El JSON del DTE está vacío o inválido")

        # Obtener el JSON real del DTE
        if "dteJson" in payload_original and payload_original["dteJson"]:
            dte_json_raw = payload_original["dteJson"]
        elif payload_original:
            # Caso cuando el JSON ya viene completo en payload_original
            dte_json_raw = payload_original
        else:
            raise UserError("El JSON del DTE está vacío o inválido")

        if isinstance(dte_json_raw, str):
            try:
                # Intentar parsear como JSON válido
                dte_json = json.loads(dte_json_raw)
                _logger.info("dteJson parseado correctamente en generar_dte")
            except json.JSONDecodeError:
                # Intentar parsear como string de diccionario Python (comillas simples)
                try:
                    # Intentar convertir dict-string Python
                    dte_dict = ast.literal_eval(dte_json_raw)
                    # Convertir a JSON válido
                    dte_json = json.loads(json.dumps(dte_dict))
                    _logger.info("dteJson convertido desde dict-string a dict Python y reconvertido a JSON")
                except Exception as e:
                    _logger.error(f"No se pudo convertir dteJson: {e}")
                    raise UserError("Error interno: dteJson no válido.")
        else:
            dte_json = dte_json_raw

        # Guardar siempre la versión dict en payload_original
        payload_original["dteJson"] = dte_json  # Guardar versión corregida

        if not isinstance(dte_json, dict):
            _logger.warning(f"dteJson no es un diccionario: {dte_json}")
            raise UserError(_("Error interno: dteJson debe ser un diccionario."))

        url_receive = None
        if not ambiente_test:
            url_receive = (
                config_utils.get_config_value(self.env, 'url_test_hacienda', self.company_id.id)
                if environment_type == constants.AMBIENTE_TEST  # Ambiente de prueba
                else config_utils.get_config_value(self.env, 'url_prod_hacienda', self.company_id.id)
            )

        if not ambiente_test and not url_receive:
            _logger.error("SIT: Falta la URL de Hacienda en la configuración de la compañía [ID] %s", self.company_id.id)
            raise UserError(_("La URL de hacienda no está configurada en la empresa."))

        # ——— 2) Refrescar token si hace falta ———
        today = fields.Date.context_today(self)
        if not self.company_id.sit_token_fecha or self.company_id.sit_token_fecha.date() < today:
            self.company_id.get_generar_token()

        user_agent = str(config_utils.get_config_value(self.env, 'user_agent', self.company_id.id))
        if not user_agent:
            user_agent = "Odoo"
            raise UserError(_("No se ha configurado el 'User-Agent' para esta compañía."))

        headers = {
            "Content-Type": str(self.content_type),
            "User-Agent": user_agent,  # "Odoo",
            "Authorization": f"Bearer {self.company_id.sit_token}",
        }

        # ——— 3) Obtener o firmar el JWT ———
        jwt_token = None
        url = None
        if not ambiente_test:
            jwt_token = payload.get("documento")
            url = config_utils.get_config_value(self.env, 'url_firma', self.company_id.id)
            if not url:
                _logger.error("SIT | No se encontró 'url_firma' en la configuración para la compañía ID %s", self.company_id.id)
                raise UserError(_("La URL de firma no está configurada en la empresa."))
            if not (isinstance(jwt_token, str) and jwt_token.strip()):
                firmador_url = (
                        getattr(self.company_id, "sit_firmador", None)
                        or url
                )
                sign_payload = {
                    "nit": dte_json["emisor"]["nit"],
                    "activo": True,
                    "passwordPri": payload_original.get("passwordPri")
                                   or self.company_id.sit_passwordPri
                                   or dte_json.get("passwordPri"),
                    "dteJson": dte_json,
                }
                try:
                    resp_sign = requests.post(firmador_url, headers={"Content-Type": "application/json"}, json=sign_payload, timeout=30)
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
        ident = dte_json["identificacion"] if dte_json["identificacion"] else NotImplemented
        send_payload = {
            "ambiente": ident["ambiente"],
            "idEnvio": int(self.id),
            "tipoDte": ident["tipoDte"],
            "version": int(ident.get("version", 3)),
            "documento": jwt_token,
            "codigoGeneracion": ident["codigoGeneracion"],
        }
        _logger.info(f"send_payload: {send_payload}")

        # ——— 5) Envío a Hacienda ———
        # ——— Intentos para enviar a Hacienda ———
        for intento in range(1, max_intentos + 1):
            _logger.info(f"Intento {intento} de {max_intentos} para enviar DTE a Hacienda")
            if ambiente_test:
                # Simular parámetros para _crear_contingencia
                resp_test = type("RespSimulado", (), {"status_code": 200, "text": "Simulación de prueba"})()
                data_test = {
                    "estado": "PROCESADO",
                    "clasificaMsg": "00",
                    "codigoMsg": "000",
                    "descripcionMsg": "Simulación de contingencia en pruebas",
                    "observaciones": ["Prueba de contingencia"]
                }
                mensaje_test = "Simulación de contingencia en ambiente de prueba"

                resultado_contingencia = {}
                _logger.info(f"Es contingencia?: {self.sit_es_configencia}")
                if self.sit_es_configencia:
                    resultado_contingencia = self._crear_contingencia(resp_test, data_test, mensaje_test) or {}

                # Construir resultado final combinando ambiente_test + contingencia
                resultado_final = {
                    "codigoMsg": "000",
                    "descripcionMsg": "Ambiente de pruebas, no se envió a MH",
                    "observaciones": ["Simulación de éxito en pruebas"],
                    "es_test": True,
                    "estado": "PROCESADO",
                }

                # Unimos la info de contingencia si existe
                if resultado_contingencia:
                    resultado_final.update({
                        "contingencia_title": resultado_contingencia.get('title'),
                        "contingencia_message": resultado_contingencia.get('message'),
                        "contingencia_type": resultado_contingencia.get('type'),
                    })

                    # Si la contingencia requiere notificación, devolvemos acción cliente
                    if resultado_contingencia.get('notificar'):
                        return {
                            'type': 'ir.actions.client',
                            'tag': 'display_notification',
                            'params': {
                                'title': resultado_contingencia.get('title', 'Información'),
                                'message': resultado_contingencia.get('message', ''),
                                'type': resultado_contingencia.get('type', 'info'),
                                'sticky': False,
                            }
                        }

                _logger.info("SIT Ambiente de pruebas, se omite envío a Hacienda y se simula respuesta exitosa.")
                return resultado_final
            resp = None
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
                    "hacienda_clasificaMsg": data.get("clasificaMsg"),
                    "hacienda_codigoMsg": data.get("codigoMsg"),
                    "hacienda_descripcionMsg": data.get("descripcionMsg"),
                    "hacienda_observaciones": ", ".join(data.get("observaciones") or []),
                    "state": "posted",
                })
                if (not self.hacienda_selloRecibido or self.hacienda_selloRecibido.strip()) and data.get("selloRecibido"):
                    self.write({
                        "hacienda_selloRecibido": data.get("selloRecibido")
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
                    observaciones = ""
                    if isinstance(data, dict):
                        obs_list = data.get("observaciones") or []
                        if isinstance(obs_list, list):
                            observaciones = ", ".join(obs_list)
                        else:
                            observaciones = str(obs_list)
                    else:
                        observaciones = str(resp.text)

                    self.write({
                        "hacienda_estado": f"Error HTTP {resp.status_code}",
                        "hacienda_descripcionMsg": str(data or resp.text),
                        "hacienda_observaciones": observaciones,
                        "state": "draft",
                    })
                    resultado = self._crear_contingencia(resp, data, mensaje)
                    if resultado and resultado.get('notificar'):
                        return {
                            'type': 'ir.actions.client',
                            'tag': 'display_notification',
                            'params': {
                                'title': resultado.get('title', 'Información'),
                                'message': resultado.get('message', ''),
                                'type': resultado.get('type', 'info'),
                                'sticky': False,
                            }
                        }
                    raise UserError(_("Error MH estado !=200 (HTTP %s): %s") % (resp.status_code, data or resp.text))
                continue  # intenta de nuevo

            estado = data.get('estado')
            if estado == 'RECHAZADO':
                mensaje = f"Rechazado por MH: {data.get('clasificaMsg')} - {data.get('descripcionMsg')}"
                _logger.warning(mensaje)
                if intento == max_intentos:
                    self.write({
                        "hacienda_estado": data.get("estado", "RECHAZADO"),
                        "hacienda_clasificaMsg": data.get("clasificaMsg"),
                        "hacienda_descripcionMsg": data.get("descripcionMsg"),
                        "hacienda_observaciones": ", ".join(data.get("observaciones") or []),
                    })
                    resultado = self._crear_contingencia(resp, data, mensaje)
                    if resultado and resultado.get('notificar'):
                        return {
                            'type': 'ir.actions.client',
                            'tag': 'display_notification',
                            'params': {
                                'title': resultado.get('title', 'Información'),
                                'message': resultado.get('message', ''),
                                'type': resultado.get('type', 'info'),
                                'sticky': False,
                            }
                        }
                    raise UserError(_("Rechazado por MH: %s – %s") % (data.get('clasificaMsg'), data.get('descripcionMsg')))
                continue

            if estado == 'PROCESADO':
                return data

            # ——— 9) Caso realmente inesperado ———
            _logger.warning("Respuesta inesperada de MH: %s", data)
            _logger.warning("Finalizó sin respuesta exitosa ni contingencia: %s", data)
        return data

    def _autenticar(self, user, pwd):
        _logger.info("SIT self = %s", self)

        if not (self.company_id and self.company_id.sit_facturacion):
            _logger.info("SIT No aplica facturación electrónica. Se omite autenticación.")
            return False

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
            # 'user=06140902221032&pwd=D%237k9r%402mP1!b'
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            response = requests.request("POST", url, headers=headers, data=payload)
            _logger.info("SIT response =%s", response.text)
        except Exception as e:
            error = str(e)
            _logger.info('SIT error= %s, ', error)
            if "error" in error or "" in error:
                MENSAJE_ERROR = str(error['status']) + ", " + str(error['error']) + ", " + str(error['message'])
                raise UserError(_(MENSAJE_ERROR))
            else:
                raise UserError(_(error))
        resultado = []
        json_response = response.json()

    def _generar_qr(self, ambiente, codGen, fechaEmi):
        _logger.info("SIT generando qr = %s", self)

        if not (self.company_id and self.company_id.sit_facturacion):
            _logger.info("SIT No aplica facturación electrónica. Se omite generación de QR(_generar_qr).")
            return False

        #enviroment_type = 'homologation'
        enviroment_type = self._get_environment_type()
        _logger.info("SIT Modo generar_qr= %s", enviroment_type)
        if enviroment_type == 'homologation':
            host = 'https://admin.factura.gob.sv'
        else:
            host = 'https://admin.factura.gob.sv'
        fechaEmision = str(fechaEmi.year) + "-" + str(fechaEmi.month).zfill(2) + "-" + str(fechaEmi.day).zfill(2)
        texto_codigo_qr = host + "/consultaPublica?ambiente=" + str(ambiente) + "&codGen=" + str(
            codGen) + "&fechaEmi=" + str(fechaEmision)
        _logger.info("SIT generando qr texto_codigo_qr = %s", texto_codigo_qr)
        codigo_qr = qrcode.QRCode(
            version=1,  # Versión del código QR (ajústala según tus necesidades)
            error_correction=qrcode.constants.ERROR_CORRECT_L,  # Nivel de corrección de errores
            box_size=10,  # Tamaño de los cuadros del código QR
            border=4,  # Ancho del borde del código QR
        )
        codigo_qr.add_data(texto_codigo_qr)
        # os.chdir('C:/Users/INCOE/PycharmProjects/fe/location/mnt/src')
        # os.chdir('C:/Users/admin/Documents/GitHub/fe/location/mnt/certificado')
        os.chdir(EXTRA_ADDONS)
        directory = os.getcwd()
        _logger.info("SIT directory =%s", directory)
        basewidth = 100
        buffer = io.BytesIO()
        codigo_qr.make(fit=True)
        img = codigo_qr.make_image(fill_color="black", back_color="white")
        wpercent = (basewidth / float(img.size[0]))
        hsize = int((float(img.size[1]) * float(wpercent)))
        new_img = img.resize((basewidth, hsize), Image.BICUBIC)
        new_img.save(buffer, format="PNG")
        qrCode = base64.b64encode(buffer.getvalue())
        # self.sit_qr_hacienda = qrCode
        return qrCode

    def generar_qr(self):
        _logger.info("SIT generando qr = %s", self)

        if not (self.company_id and self.company_id.sit_facturacion):
            _logger.info("SIT No aplica facturación electrónica. Se omite generación de QR(generar_qr).")
            return False

        enviroment_type = 'homologation'
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
        os.chdir(EXTRA_ADDONS)
        directory = os.getcwd()

        _logger.info("SIT directory =%s", directory)
        basewidth = 100
        buffer = io.BytesIO()

        codigo_qr.make(fit=True)
        img = codigo_qr.make_image(fill_color="black", back_color="white")

        wpercent = (basewidth / float(img.size[0]))
        hsize = int((float(img.size[1]) * float(wpercent)))
        new_img = img.resize((basewidth, hsize), Image.BICUBIC)
        new_img.save(buffer, format="PNG")
        qrCode = base64.b64encode(buffer.getvalue())
        self.sit_qr_hacienda = qrCode
        return

    def check_parametros_firmado(self):
        _logger.info("SIT-Hacienda_fe Validaciones parametros doc firmado")
        if not (self.company_id and self.company_id.sit_facturacion):
            _logger.info("SIT No aplica facturación electrónica. Se omite validación de parámetros de firmado.")
            return False

        if not self.journal_id.sit_tipo_documento.codigo:
            raise UserError(_('El Tipo de DTE no definido.'))
        if not self.name:
            raise UserError(_('El Número de control no definido'))
        tipo_dte = self.journal_id.sit_tipo_documento.codigo

        if tipo_dte == constants.COD_DTE_FE:
            # Solo validar el nombre para DTE tipo 01
            if not self.partner_id.name:
                raise UserError(_('El receptor no tiene NOMBRE configurado para facturas tipo 01.'))
        elif tipo_dte == constants.COD_DTE_CCF:
            # Validaciones completas para DTE tipo 03
            if not self.partner_id.vat and self.partner_id.is_company:
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
        elif tipo_dte == constants.COD_DTE_FSE:
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
        if not line_temp["precioUni"]:
            ERROR = 'El PRECIO UNITARIO del producto  ' + line_temp["descripcion"] + ' no está definido.'
            raise UserError(_(ERROR))
        if not line_temp["uniMedida"]:
            ERROR = 'La UNIDAD DE MEDIDA del producto  ' + line_temp["descripcion"] + ' no está definido.'
            raise UserError(_(ERROR))

    def check_parametros_dte(self, generacion_dte, ambiente_test):
        _logger.info("SIT-Hacienda_fe Validaciones check_parametros_dte")
        if not (self.company_id and self.company_id.sit_facturacion):
            _logger.info("SIT No aplica facturación electrónica. Se omite validación de parámetros DTE.")
            return False

        if not generacion_dte["ambiente"]:
            raise UserError(_('El ambiente  no está definido.'))
        if not generacion_dte["idEnvio"]:
            ERROR = 'El IDENVIO  no está definido.'
            raise UserError(_(ERROR))
        if not generacion_dte["tipoDte"]:
            ERROR = 'El tipoDte  no está definido.'
            raise UserError(_(ERROR))
        if not ambiente_test and not generacion_dte["documento"]:
            ERROR = 'El DOCUMENTO  no está presente.'
            raise UserError(_(ERROR))
        if not generacion_dte["codigoGeneracion"]:
            ERROR = 'El codigoGeneracion  no está definido.'
            raise UserError(_(ERROR))
        if not generacion_dte["version"]:
            raise UserError(_('La version dte no está definida.'))
        return True

    def _evaluar_error_contingencia(self, status_code, origen="desconocido"):
        if not (self.company_id and self.company_id.sit_facturacion):
            _logger.info("SIT No aplica facturación electrónica. Se omite evaluación de error de contingencia.")
            return None, False, ""

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
        if not (self.company_id and self.company_id.sit_facturacion):
            _logger.info("SIT No aplica facturación electrónica. Se omite creación de contingencia.")
            return

        # Solo crear si no tiene sello y no está ya en contingencia
        if self.hacienda_selloRecibido or self.sit_factura_de_contingencia:
            _logger.info("Factura %s no entra a contingencia: sello=%s, contingencia=%s", self.name, self.hacienda_selloRecibido, self.sit_factura_de_contingencia)
            return

        journal_contingencia = self.env['account.journal'].search([
            ('code', '=', 'CONT'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        if not journal_contingencia:
            raise UserError(_("No se encontró el diario de contingencia."))

        journal_lote = self.env['account.journal'].search([
            ('code', '=', 'LOTE'),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        if not journal_lote:
            raise UserError(_("No se encontró el diario de lotes."))

        max_intentos = 3
        if not data:
            data = {}

        codigo = data.get("codigoMsg") or "SIN_CODIGO"
        descripcion = data.get("descripcionMsg") or resp.text or "Error desconocido"
        _logger.info("Creando contingencia por error MH: [%s] %s", codigo, descripcion)

        error_msg = _(mensaje)  # mensaje debe ser clave de traducción

        tipo_contingencia, motivo_otro, mensaje_motivo = self._evaluar_error_contingencia(
            status_code=resp.status_code,
            origen="envío DTE"
        )

        self.write({
            'error_log': error_msg,
            'sit_es_configencia': True,
            'sit_tipo_contingencia': tipo_contingencia.id if tipo_contingencia else False,
        })
        _logger.info("Guardando DTE en contingencia (%s): %s", tipo_contingencia.codigo if tipo_contingencia else "", self.name)

        _logger.info("Buscando contingencia activa para empresa: %s", self.company_id.name)
        Contingencia = self.env['account.contingencia1']
        Lote = self.env['account.lote']
        Bloque = self.env['account.contingencia.bloque']  # Modelo de Bloques

        # Buscar contingencia activa
        contingencia_activa = Contingencia.search([
            ('company_id', '=', self.company_id.id),
            ('sit_selloRecibido', '=', False),
            ('contingencia_activa', '=', True),
            ('contingencia_recibida_mh', '=', False),
        ], limit=1)

        lote_asignado = None
        bloque_asignado = None  # Variable para el bloque
        usar_lotes = self.company_id.sit_usar_lotes_contingencia

        if contingencia_activa:
            _logger.info("Contingencia activa encontrada: %s", contingencia_activa.name)

            # Validar solo si NO se usan lotes
            if not usar_lotes:
                # Validación de la cantidad de facturas en la contingencia
                num_facturas_contingencia = self.env['account.move'].search_count([
                    ('sit_factura_de_contingencia', '=', contingencia_activa.id),
                    ('company_id', '=', self.company_id.id),
                ])
                _logger.info("Facturas en contingencia %s: %d", contingencia_activa.name, num_facturas_contingencia)

                if num_facturas_contingencia >= 5000:
                    _logger.warning("Contingencia %s alcanzó el máximo de 5000 facturas. Se creará nueva contingencia.", contingencia_activa.name)
                    contingencia_activa.write({'contingencia_activa': False})
                    contingencia_activa = None

            # Si la contingencia sigue activa, asociamos la factura
            if contingencia_activa:
                # Asociar esta factura a la contingencia
                self.write({'sit_factura_de_contingencia': contingencia_activa.id})

                # Si no se usan lotes, se manejan bloques
                if not usar_lotes:
                    bloque_asignado = self._asignar_a_bloque(contingencia_activa)
                    self.write({'sit_bloque_contingencia': bloque_asignado.id})
                    _logger.info("Factura asignada a bloque: %s", bloque_asignado.name)

                if usar_lotes:
                    # Buscar lote incompleto
                    lotes_validos = Lote.search([
                        ('sit_contingencia', '=', contingencia_activa.id),
                        ('hacienda_codigoLote_lote', 'in', [False, '', None]),
                        ('lote_activo', '=', True),
                        ('company_id', '=', self.company_id.id),
                    ])

                    for lote in lotes_validos:
                        if len(lote.move_ids) < 100:  # 100
                            self.write({'sit_lote_contingencia': lote.id})
                            lote_asignado = lote
                            _logger.info("Factura asignada a lote existente: %s", lote.id)
                            break

                    if not lote_asignado and not self.sit_lote_contingencia:
                        # Eliminar lotes vacíos si los hay (opcional, solo si quieres limpiar)
                        lotes_vacios = Lote.search([
                            ('sit_contingencia', '=', contingencia_activa.id),
                            '|', '|',
                            ('name', '=', False),
                            ('name', '=', ''),
                            ('name', '=ilike', ' '),
                            ('company_id', '=', self.company_id.id),
                        ])
                        if lotes_vacios:
                            _logger.warning("Se eliminarán lotes vacíos sin nombre antes de crear uno nuevo: %s", lotes_vacios.ids)
                            lotes_vacios.unlink()

                        num_lotes = Lote.search_count([('sit_contingencia', '=', contingencia_activa.id)])
                        _logger.info("Cantidad lotes existentes en contingencia %s: %d", contingencia_activa.name, num_lotes)

                        if num_lotes < 400:
                            nuevo_nombre_lote = self.env['account.lote'].generar_nombre_lote(journal=journal_lote, actualizar_secuencia=True)
                            if not nuevo_nombre_lote or not nuevo_nombre_lote.strip():
                                raise UserError(_("El nombre generado para el lote es inválido, no puede ser vacío."))
                            lote_asignado = Lote.create({
                                'name': nuevo_nombre_lote,
                                'sit_contingencia': contingencia_activa.id,
                                'lote_activo': True,
                                'journal_id': journal_lote.id,
                                'company_id': contingencia_activa.company_id.id,
                            })
                            self.write({'sit_lote_contingencia': lote_asignado.id})
                            _logger.info("Factura asignada a nuevo lote: %s", lote_asignado.name)
                        else:
                            _logger.info("Contingencia ya tiene 400 lotes. Creando nueva contingencia.")
                            contingencia_activa = None  # Forzar nueva contingencia

                    elif not lote_asignado and self.sit_lote_contingencia:
                        _logger.info("Factura ya tenía un lote asignado, no se crea nuevo lote: %s", self.sit_lote_contingencia.name)
        else:
            _logger.info("No se encontró contingencia activa. Creando nueva.")

        # Si no hay contingencia activa o válida, crear una nueva
        if not contingencia_activa:
            nuevo_name = Contingencia._generate_contingencia_name(journal=journal_contingencia, actualizar_secuencia=True)
            contingencia_activa = Contingencia.create({
                'name': nuevo_name,
                'company_id': self.company_id.id,
                'journal_id': journal_contingencia.id,
                'sit_tipo_contingencia': tipo_contingencia.id if tipo_contingencia else False,
                'contingencia_activa': True,
                'sit_usar_lotes': usar_lotes,
                'hacienda_codigoGeneracion_identificacion': self.sit_generar_uuid(),
            })

            if usar_lotes:
                nuevo_nombre_lote = Lote.generar_nombre_lote(journal=journal_lote, actualizar_secuencia=True)
                if not nuevo_nombre_lote or not nuevo_nombre_lote.strip():
                    raise UserError(_("El nombre generado para el lote es inválido, no puede ser vacío."))
                lote_asignado = Lote.create({
                    'name': nuevo_nombre_lote,
                    'sit_contingencia': contingencia_activa.id,
                    'lote_activo': True,
                    'journal_id': journal_lote.id,
                    'company_id': contingencia_activa.company_id.id,
                })
                self.write({
                    'sit_lote_contingencia': lote_asignado.id,
                    'sit_factura_de_contingencia': contingencia_activa.id,
                })
                _logger.info("Creada nueva contingencia y lote: %s, %s", contingencia_activa.name, lote_asignado.name)
            else:
                self.write({'sit_factura_de_contingencia': contingencia_activa.id})
                _logger.info("Creada nueva contingencia %s sin lote", contingencia_activa.name)

            # Si no se usan lotes, se crea el bloque directamente
            if not usar_lotes:
                bloque_asignado = self._asignar_a_bloque(contingencia_activa)
                self.write({'sit_bloque_contingencia': bloque_asignado.id})

            _logger.info("Creada nueva contingencia %s", contingencia_activa.name)

        _logger.info("Factura %s asignada a contingencia %s y lote %s", self.name, contingencia_activa.name, lote_asignado.name if lote_asignado else "N/A")
        return {
            'notificar': True,
            'title': 'El DTE se guardó en contingencia',
            'message': f"Dte {self.name} asignado a contingencia {contingencia_activa.name} y lote {lote_asignado.name if lote_asignado else 'N/A'}.",
            'type': 'success',
        }

    def _asignar_a_bloque(self, contingencia_activa):
        # Buscar bloque con menos de 100 facturas
        bloque = self.env['account.contingencia.bloque'].search([
            ('contingencia_id', '=', contingencia_activa.id),
            ('cantidad', '<', 100),
        ], limit=1)

        if not bloque:
            # Crear un nuevo bloque si no se encontró uno con espacio
            nuevo_nombre_bloque = self.env['account.contingencia.bloque'].generar_nombre_bloque()
            bloque = self.env['account.contingencia.bloque'].create({
                'name': nuevo_nombre_bloque,
                'contingencia_id': contingencia_activa.id,
                'factura_ids': [(4, self.id)],
            })
        else:
            # Asignar la factura al bloque existente
            bloque.write({
                'factura_ids': [(4, self.id)],
            })

        return bloque

    def action_post(self):
        if not all(inv.company_id and inv.company_id.sit_facturacion for inv in self):
            _logger.info( "SIT No aplica facturación electrónica para alguna factura. Se omite notificación de contingencia.")
            return super().action_post()

        ambiente_test = False
        if config_utils:
            ambiente_test = config_utils._compute_validation_type_2(self.env, self.company_id)
            _logger.info("SIT Validaciones[Ambiente]: %s", ambiente_test)

        doc_electronico = False
        if self.journal_id and self.journal_id.sit_tipo_documento and self.journal_id.sit_tipo_documento.codigo:
            doc_electronico = True

        if not self.invoice_date:
            raise ValidationError("Debe seleccionar la fecha del documento.")

        if doc_electronico and not self.condiciones_pago:
            raise ValidationError("Debe seleccionar una Condicion de la Operación.")

        if doc_electronico and not self.forma_pago:
            raise ValidationError("Seleccione una Forma de Pago.")

        if self.journal_id and not self.journal_id.report_xml:
            raise ValidationError("El diario debe tener un reporte PDF configurado.")

        if not ambiente_test and self.journal_id.sit_tipo_documento and self.journal_id.sit_tipo_documento.codigo == constants.COD_DTE_NC and self.inv_refund_id and not self.inv_refund_id.hacienda_selloRecibido:
            raise ValidationError("El documento relacionado aún no cuenta con el sello de Hacienda.")

        res = super().action_post()
        facturas_con_contingencia = self.filtered(lambda inv: inv.sit_es_configencia)
        if facturas_con_contingencia:
            mensajes = "\n".join(f"{inv.name} guardado en contingencia." for inv in facturas_con_contingencia)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Contingencias DTE',
                    'message': mensajes,
                    'type': 'warning',
                    'sticky': False,
                }
            }
        return res

    def sit_enviar_correo_dte_automatico(self):
        from_button = self.env.context.get('from_email_button', False)  # Controlar si el envio es desde el post o desde la interfaz(boton)
        es_invalidacion = self.env.context.get('from_invalidacion', False)
        ambiente_test = False

        if from_button:
            _logger.info("SIT | Método invocado desde botón 'Enviar email'")
        else:
            _logger.info("SIT | Método invocado desde _post")

        if config_utils:
            ambiente_test = config_utils._compute_validation_type_2(self.env, self.company_id)
            _logger.info("SIT Enviando correo[Ambiente]: %s", ambiente_test)

        for invoice in self:
            # Validar si la empresa aplica a facturación electrónica
            if invoice.company_id and invoice.company_id.sit_facturacion:

                # Validar que el DTE exista en hacienda
                if not ambiente_test and not invoice.hacienda_selloRecibido and not invoice.recibido_mh:
                    msg = "La factura %s no tiene un DTE procesado, no se enviará correo." % invoice.name
                    _logger.warning("SIT | %s", msg)
                    raise UserError(msg)

                _logger.info("SIT | DTE procesado correctamente para la factura %s. Procediendo con envío de correo.", invoice.name)

                # Enviar el correo automáticamente solo si el DTE fue aceptado y aún no se ha enviado
                _logger.info("SIT | Es evento de invalidacion= %s", es_invalidacion)

                _logger.info(
                    "DEBUG | es_invalidacion=%s recibido_mh=%s correo_enviado=%s inval_recibida=%s inval_correo=%s from_button=%s",
                    es_invalidacion,
                    invoice.recibido_mh,
                    invoice.correo_enviado,
                    getattr(invoice.sit_evento_invalidacion, "invalidacion_recibida_mh", None),
                    getattr(invoice.sit_evento_invalidacion, "correo_enviado_invalidacion", None),
                    from_button,
                    )

                if ((not ambiente_test or from_button)
                        or (not ambiente_test and not es_invalidacion and invoice.recibido_mh and not invoice.correo_enviado)
                        or (not ambiente_test and es_invalidacion and invoice.sit_evento_invalidacion.invalidacion_recibida_mh and not invoice.sit_evento_invalidacion.correo_enviado_invalidacion) ):
                    try:
                        _logger.info("SIT | Enviando correo automático para la factura %s", invoice.name)
                        invoice.with_context(from_automatic=True, from_invalidacion=es_invalidacion).sudo().sit_action_send_mail()
                    except Exception as e:
                        _logger.error("SIT | Error al intentar enviar el correo para la factura %s: %s", invoice.name, str(e))
                if ambiente_test:
                    _logger.info("SIT | La correspondencia no se envia en ambiente de pruebas. %s", invoice.name)
                else:
                    _logger.info("SIT | La correspondencia ya había sido transmitida. %s", invoice.name)
            else:
                _logger.info("SIT | Procediendo con envío de correo para documento. %s", invoice.name)
                invoice.with_context(from_automatic=True, from_invalidacion=es_invalidacion).sudo().sit_action_send_mail()
        # return True

    def write(self, vals):
        # Ejecutar write normal para todas las facturas
        res = super().write(vals)

        # Filtrar solo las facturas que aplican a facturación electrónica
        facturas_aplican = self.filtered(lambda inv: inv.company_id and inv.company_id.sit_facturacion)

        # Si alguna factura aplica y se modifican campos clave, copiar retenciones
        if facturas_aplican and any(k in vals for k in ['codigo_tipo_documento', 'reversed_entry_id', 'debit_origin_id']):
            facturas_aplican._copiar_retenciones_desde_documento_relacionado()
        return res

    def _copiar_retenciones_desde_documento_relacionado(self):
        for move in self:
            # Validar si la empresa aplica a facturación electrónica
            if not (move.company_id and move.company_id.sit_facturacion):
                _logger.info("SIT | La empresa %s no aplica a facturación electrónica. Se omite retenciones para %s", move.company_id.name, move.name)
                continue

            origen = None
            if move.codigo_tipo_documento == constants.COD_DTE_NC and move.reversed_entry_id:
                origen = move.reversed_entry_id
            elif move.codigo_tipo_documento == constants.COD_DTE_ND and move.debit_origin_id:
                origen = move.debit_origin_id

            if not origen:
                continue

            move.apply_retencion_renta = origen.apply_retencion_renta
            move.retencion_renta_amount = origen.retencion_renta_amount

            move.apply_retencion_iva = origen.apply_retencion_iva
            move.retencion_iva_amount = origen.retencion_iva_amount

            move.apply_iva_percibido = origen.apply_iva_percibido
            move.iva_percibido_amount = origen.iva_percibido_amount

    def _products_missing_required_iva(self):
        """Devuelve product.product de líneas que NO tienen aplicado el IVA 13% en tax_ids."""
        self.ensure_one()

        # --- Validación: solo aplicar si la empresa aplica a facturación electrónica ---
        if not (self.company_id and self.company_id.sit_facturacion):
            _logger.info("Empresa %s no aplica a facturación electrónica, se omite validación.", self.company_id.display_name)
            return

        _logger.info("IVA13CHK ▶ start move_id=%s name=%s company=%s", self.id, self.name or '/', self.company_id.display_name)

        # 1) Obtener el impuesto requerido por XMLID; si no existe, buscarlo
        iva_tax = self.env.ref("l10n_sv.tax_sv_iva_13_sale", raise_if_not_found=False)
        if iva_tax:
            _logger.info("IVA13CHK ▶ encontrado por XMLID: id=%s name=%s amount=%s%% company=%s country=%s",
                         iva_tax.id, iva_tax.display_name, iva_tax.amount,
                         iva_tax.company_id and iva_tax.company_id.display_name,
                         iva_tax.country_id and iva_tax.country_id.code)
        else:
            _logger.warning("IVA13CHK ▶ XMLID l10n_sv.tax_sv_iva_13_sale no encontrado; haciendo búsqueda por criterios.")
            iva_tax = self.env["account.tax"].search([
                ("name", "=", "IVA 13% Ventas Bienes"),
                ("amount", "=", 13.0),
                ("type_tax_use", "in", ("sale", "none")),
                ("company_id", "parent_of", self.company_id.id),
                ("country_id", "=", self.company_id.tax_country_id.id or self.company_id.country_id.id),
            ], limit=1)
            _logger.info("IVA13CHK ▶ resultado búsqueda: %s", iva_tax and f"id={iva_tax.id}, name={iva_tax.display_name}" or "SIN RESULTADOS")

        # Si no se encuentra el impuesto, no validar (devolver vacío)
        if not iva_tax:
            _logger.warning("IVA13CHK ▶ No se encontró el impuesto obligatorio IVA 13%% para la compañía %s.", self.company_id.display_name)
            return self.env["product.product"]

        # 2) Revisar SOLO líneas reales con producto y cantidad > 0
        total_lines = len(self.invoice_line_ids)
        lines = self.invoice_line_ids.filtered(lambda l: l.product_id and not l.display_type and l.quantity > 0)
        _logger.info("IVA13CHK ▶ líneas totales=%s | líneas evaluadas=%s | fiscal_position=%s",
                     total_lines, len(lines),
                     self.fiscal_position_id and self.fiscal_position_id.display_name or "None")

        missing_products = self.env["product.product"]

        for idx, line in enumerate(lines, start=1):
            taxes_orig = line.tax_ids
            _logger.info("IVA13CHK ▶ L%s line_id=%s prod=%s qty=%s price=%s taxes(orig)=[%s]",
                         idx, line.id, line.product_id.display_name, line.quantity, line.price_unit,
                         ", ".join(taxes_orig.mapped("display_name")) or "—")

            # mapear por posición fiscal (si aplica)
            taxes_eff = taxes_orig
            if self.fiscal_position_id:
                mapped = self.fiscal_position_id.map_tax(taxes_orig, self.partner_id)
                if mapped:
                    taxes_eff = mapped
                _logger.info("IVA13CHK ▶ L%s taxes(mapped by FP)=[%s]", idx, ", ".join(taxes_eff.mapped("display_name")) or "—")

            # considerar impuestos hijos (por grupos)
            taxes_with_children = taxes_eff | taxes_eff.mapped("children_tax_ids")
            tiene_iva = iva_tax in taxes_with_children
            _logger.info("IVA13CHK ▶ L%s comparación: requerido=%s | en_linea=%s | tiene_IVA13=%s",
                         idx, iva_tax.display_name,
                         ", ".join(taxes_with_children.mapped("display_name")) or "—",
                         tiene_iva)

            if not tiene_iva:
                missing_products |= line.product_id
                _logger.warning("IVA13CHK ▶ L%s SIN IVA13 → producto faltante: %s (line_id=%s)", idx, line.product_id.display_name, line.id)

        _logger.info("IVA13CHK ▶ productos sin IVA13 (conteo=%s): %s", len(missing_products), ", ".join(missing_products.mapped("display_name")) or "NINGUNO")
        return missing_products

    def _products_missing_hacienda_tributo(self):
        """
        Devuelve los productos de las líneas de la factura a los que les falta
        el 'Tributo de Hacienda para el Cuerpo'.
        Si la empresa no aplica a facturación electrónica, no se realiza la validación.
        """
        self.ensure_one()

        # Validar si la empresa aplica a facturación electrónica
        if not (self.company_id and self.company_id.sit_facturacion):
            _logger.info("La empresa %s no aplica a facturación electrónica. Validación omitida.", self.company_id.name)
            return

        missing_products = self.env["product.product"]

        # Filtramos solo las líneas que tienen un producto real y cantidad > 0
        lines_to_check = self.invoice_line_ids.filtered(lambda l: l.product_id and l.quantity > 0)

        for line in lines_to_check:
            if not line.product_id.tributos_hacienda_cuerpo:
                missing_products |= line.product_id

        return missing_products