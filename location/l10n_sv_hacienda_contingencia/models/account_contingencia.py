# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from odoo.tools import float_repr
from odoo.addons.l10n_sv_haciendaws_fe.afip_utils import get_invoice_number_from_response
import base64
import pytz
import logging
_logger = logging.getLogger(__name__)

from pytz import timezone
from datetime import datetime, timedelta

base64.encodestring = base64.encodebytes
import json
import requests
import traceback

try:
    from odoo.addons.common_utils.utils import config_utils
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo config_utils [contingencia account_contingencia1[contingencia]]")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    config_utils = None
    constants = None

def _default_fecha_hora_sv(self):
    """
    Devuelve la fecha y hora actual convertida a la zona horaria de El Salvador,
    sin información de zona (naive datetime), para usar como valor por defecto en campos datetime.
    """
    tz = pytz.timezone('America/El_Salvador')
    dt_with_tz = pytz.utc.localize(datetime.utcnow()).astimezone(tz)
    return dt_with_tz.replace(tzinfo=None)

class sit_account_contingencia(models.Model):
    
    _name = 'account.contingencia1'
    _description = "Entrada de contingencia"

    name = fields.Char(
        string='Number',
        compute='_compute_name', 
        required=True,
        store=True,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Nuevo'),
            ('posted', 'Validado'),
            ('posted_lote', 'Lote Validado'),
            ('cancel', 'Cancelado'),
        ],
        string='Estado',
        required=True,
        readonly=True,
        tracking=True,
        default='draft',
    )
    date = fields.Datetime(
        string='Date',
        index=True,
        compute='_compute_date', 
        store=True, 
        required=True,
        precompute=True,
    )
    invoice_user_id = fields.Many2one(
        string='Responsable',
        comodel_name='res.users',
        copy=False,
        tracking=True,
        default=lambda self: self.env.user,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        compute='_compute_company_id', store=True, readonly=False, precompute=True,
        index=True,
    )    
    journal_id = fields.Many2one(
        'account.journal',
        string='Diario',
        required=False,
    )
    sit_fInicio_hInicio = fields.Datetime("Fecha de Inicio de Contingencia - Hacienda", required=True, help="Asignación de Fecha manual para registrarse en Hacienda", default=_default_fecha_hora_sv)
    fecha_hora_creacion = fields.Datetime(string="Fecha y hora (El Salvador)", readonly=True)

    sit_fFin_hFin = fields.Datetime("Fecha de Fin de Contingencia - Hacienda",  help="Asignación de Fecha manual para registrarse en Hacienda", )
    sit_tipo_contingencia = fields.Many2one('account.move.tipo_contingencia.field', string="Tipo de Contingencia")
    sit_tipo_contingencia_otro = fields.Text(string="Especifique el Otro Tipo de Contingencia")
    sit_tipo_contingencia_valores = fields.Char(related="sit_tipo_contingencia.valores", string="Tipo de contingiancia(nombre)")
    sit_facturas_relacionadas = fields.One2many(
        'account.move',
        'sit_factura_de_contingencia',
        string='Facturas relacionadas',
    )

    sit_estado = fields.Text(string="Estado - Hacienda", default="")
    sit_fechaHora = fields.Datetime("Fecha de Hacienda",  help="Asignación de Fecha manual para registrarse en Hacienda", )
    sit_mensaje = fields.Text(string="Mensaje - Hacienda", default="")
    sit_selloRecibido = fields.Text(string="sello Recibido - Hacienda", default="")
    sit_observaciones=fields.Text("observaciones - Hacienda", default="") 
    hacienda_estado=fields.Text("hacienda estado", default="") 
    sit_json_respuesta = fields.Text("Json de Respuesta", default="")
    hacienda_codigoGeneracion_identificacion = fields.Char(
        copy=False,
        string="Codigo de Generación de Identificación Contingencia",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    sit_documento_firmado_contingencia = fields.Text(
        string="Documento Firmado Contingencia",
        copy=False,
        readonly=True,
    )

    lote_ids = fields.One2many(
        'account.lote',
        'sit_contingencia',
        string='Lotes asociados'
    )

    contingencia_recibida_mh = fields.Boolean(string="Lote recibido por MH", copy=False)
    contingencia_activa = fields.Boolean(string="Contingencia Activa", copy=False, default=True)

    boton_contingencia = fields.Boolean(
        string="Mostrar botón de lote",
        compute='_compute_mostrar_boton_contingencia',
        store=False
    )

    boton_lote = fields.Boolean(
        string="Mostrar botón de lote",
        compute='_compute_mostrar_boton_lote',
        store=False
    )

    ultima_actualizacion_task = fields.Datetime(string="Última actualización del cron")
    sit_usar_lotes = fields.Boolean(string="Usar Lotes", default=False)
    sit_bloque = fields.Boolean(string="Usar Bloques de contingencia", default=False)
    bloque_ids = fields.One2many("account.contingencia.bloque", "contingencia_id", string="Bloques de Facturas")

    fechaHoraTransmision = fields.Datetime(
        copy=False,
        string="Fecha/Hora de Transmisión",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )

    # --------CAMPOS LOTE --------------------

    hacienda_estado_lote = fields.Char(
        copy=False,
        string="Estado Lote",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    hacienda_idEnvio_lote = fields.Char(
        copy=False,
        string="Id de Envio Lote",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    hacienda_fhProcesamiento_lote = fields.Datetime(
        copy=False,
        string="Fecha de Procesamiento de Lote",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    hacienda_codigoLote_lote = fields.Char(
        copy=False,
        string="Codigo de Lote",
        readonly=True,
    )
    hacienda_codigoMsg_lote = fields.Char(
        copy=False,
        string="Codigo de Mensaje",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    hacienda_descripcionMsg_lote = fields.Char(
        copy=False,
        string="Descripción de Lote",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )

    error_log = fields.Text(string="Error técnico Contingencia", readonly=True)

    # ---------------------------------------------------------------------------------------------    POST LOTE
    @api.depends('lote_ids.lote_recibido_mh')
    def _compute_mostrar_boton_lote(self):
        """Calcula si debe mostrarse el botón de envío de lote. Se muestra solo cuando existen lotes activos que aún no han sido recibidos por Hacienda."""
        for rec in self:
            # Lógica de ejemplo: mostrar solo si está en 'posted' y aún no tiene lote
            rec.boton_lote = any(not lote.lote_recibido_mh and lote.lote_activo for lote in rec.lote_ids)

    def action_lote_generate(self): # Generacion de lotes en contingencia(envio de lotes a MH)
        """
        Genera y envía lotes de facturas electrónicas en contingencia a Hacienda.
        Valida el estado de la contingencia, firma las facturas, genera el payload del lote,
        y registra la respuesta de Hacienda, actualizando los campos del lote correspondiente.
        """
        facturas_firmadas = []
        payload = None
        facturas_no_asignadas = []
        version = None
        mensajes = []
        cant_lotes = int(config_utils.get_config_value(self.env, 'cantidad_lote', self.company_id.id) or 400)
        cant_facturas = int(config_utils.get_config_value(self.env, 'cantidad_factura', self.company_id.id) or 100)

        for lote in self.lote_ids:
            ambiente_test = False

            # Validar que la contingencia relacionada esté recibida
            contingencia = lote.sit_contingencia
            _logger.info('SIT action_lote_generate contingencia = %s', contingencia)

            if config_utils:
                ambiente_test = config_utils._compute_validation_type_2(self.env, self.company_id)
                _logger.info("SIT-Lote Tipo de entorno[Ambiente]: %s", ambiente_test)

            estado = (contingencia.sit_estado or '').strip().lower() if contingencia else ''
            sello = str(contingencia.sit_selloRecibido or '').strip().lower() if contingencia else ''

            # Validar existencia
            if not contingencia:
                raise UserError(f"El lote {lote.id} no tiene una contingencia relacionada.")

            # Validación según ambiente
            if not ambiente_test:
                # En producción se exige sello y estado
                if sello in ('false', '0', '', 'none') or estado != "recibido":
                    raise UserError(f"La contingencia relacionada al lote {lote.id} no ha sido recibida por MH.")
            else:
                if estado != "recibido":
                    raise UserError(f"La contingencia relacionada al lote {lote.id} no ha sido recibida por MH.")

            # nro_factura += 1
            _logger.info('SIT action_lote_generate lote a firmar = %s', lote.id)

            if lote.hacienda_codigoLote_lote:
                _logger.info("SIT Lote ya procesado, se omite: %s", lote.id)
                continue

            facturas = self.env['account.move'].search([
                ('sit_lote_contingencia', '=', lote.id)
            ])

            for invoice in facturas:
                validation_type = self.company_id._get_environment_type()
                ambiente = constants.AMBIENTE_TEST
                if validation_type == constants.HOMOLOGATION:
                    _logger.info("SIT Factura de Prueba")
                elif validation_type == constants.AMBIENTE_PROD:
                    _logger.info("SIT Factura de Producción")
                    ambiente = constants.PROD_AMBIENTE
                emisor = self.company_id.vat
                emisor = emisor.replace("-", "").replace(".", "")

                if not emisor:
                    raise UserError("SIT Se requiere definir compañia")

                if not invoice.sit_json_respuesta or invoice.sit_json_respuesta.strip() in ['', '{}', '[]']:
                    _logger.info("SIT Creando json factura relacionada(contingencia)")
                    sit_tipo_documento = invoice.journal_id.sit_tipo_documento.codigo
                    payload = invoice.obtener_payload(constants.AMBIENTE_PROD, sit_tipo_documento)
                else:
                    payload = invoice.sit_json_respuesta

                # Convertir payload a dict si no lo es
                if not isinstance(payload, dict):
                    try:
                        payload = json.loads(payload)
                    except Exception as e:
                        _logger.error("Error al convertir payload a JSON: %s", e)
                        raise UserError("El payload no es un JSON válido.")

                # Si dteJson existe en payload, convertirlo a dict
                if "dteJson" in payload and not isinstance(payload["dteJson"], dict):
                    try:
                        payload["dteJson"] = json.loads(payload["dteJson"])
                    except Exception as e:
                        _logger.error("Error al convertir dteJson a dict: %s", e)
                        raise UserError("El campo dteJson no es un JSON válido.")
                version = payload.get("dteJson", {}).get("identificacion", {}).get("ambiente") or \
                          payload.get("identificacion", {}).get("ambiente")
                _logger.info("SIT json dte: %s", payload)

                payload_dte_firma = self.sit_obtener_payload_lote_dte_firma(emisor, self.company_id.sit_passwordPri, payload)
                _logger.info("SIT payload: %s", payload_dte_firma)

                if not ambiente_test:
                    firmando = self.firmar_documento(constants.AMBIENTE_PROD, payload_dte_firma)
                    if firmando:
                        facturas_firmadas.append(firmando)
                    else:
                        raise UserError(f"Factura no firmada = {invoice.name}")

                # version = payload["dteJson"]["identificacion"]["ambiente"]
                payload_dte_envio_mh = self.sit_obtener_payload_lote_dte_info(ambiente, facturas_firmadas, emisor, version)

                # if nro_factura > 20:
                #     raise UserError(f"Factura firmada = {firmado}")

                # Generando el DTE
                dte_lote = self.generar_dte_lote(validation_type, payload_dte_envio_mh, len(facturas_firmadas), ambiente_test)
                _logger.info("SIT Respuesta MH=%s", dte_lote)

                # Guardar json respuesta SOLO si la factura no lo tenía
                if not invoice.sit_json_respuesta or invoice.sit_json_respuesta.strip() in ['', '{}', '[]']:
                    invoice.write({
                        'sit_json_respuesta': payload["dteJson"] if payload["dteJson"] else None
                    })

                hacienda_fhProcesamiento_lote = None
                fh = None
                if dte_lote and dte_lote.get('fhProcesamiento') and not ambiente_test:
                    fh = dte_lote.get('fhProcesamiento')

                try:
                    if fh:
                        _logger.info("SIT Fecha de procesamiento (%s)%s", type(fh), fh)
                        hacienda_fhProcesamiento_lote = datetime.strptime(fh, '%d/%m/%Y %H:%M:%S')
                        _logger.info("hacienda_fhProcesamiento_lote = %s", hacienda_fhProcesamiento_lote)
                    else:
                        # si no hay fecha de Hacienda, usamos la hora actual de El Salvador
                        if config_utils:
                            hacienda_fhProcesamiento_lote = config_utils._get_fecha_procesamiento(fh)
                        if not hacienda_fhProcesamiento_lote:
                            # fallback final: usar fecha de creación de Odoo
                            hacienda_fhProcesamiento_lote = self.create_date
                        _logger.info("Asignando fecha de procesamiento: %s", hacienda_fhProcesamiento_lote)
                except Exception as e:
                    _logger.warning("No se pudo parsear fecha de procesamiento lote: %s", e)

                if hacienda_fhProcesamiento_lote and hacienda_fhProcesamiento_lote.tzinfo:
                    hacienda_fhProcesamiento_lote = hacienda_fhProcesamiento_lote.replace(tzinfo=None)

                # Guardar datos de account.lote
                if not ambiente_test:
                    lote_vals = {
                        'hacienda_estado_lote': dte_lote.get('estado', ''),
                        'hacienda_idEnvio_lote': dte_lote.get('idEnvio', ''),
                        'hacienda_fhProcesamiento_lote': hacienda_fhProcesamiento_lote,
                        'hacienda_codigoLote_lote': dte_lote.get('codigoLote', ''),
                        'hacienda_codigoMsg_lote': dte_lote.get('codigoMsg', ''),
                        'hacienda_descripcionMsg_lote': dte_lote.get('descripcionMsg', ''),
                        'state': "posted" if dte_lote.get('estado') == 'RECIBIDO' else 'draft',
                        'lote_recibido_mh': bool(dte_lote.get('codigoLote')),
                        'sit_json_respuesta': json.dumps(dte_lote) if isinstance(dte_lote, dict) else str(dte_lote),
                    }
                else:
                    lote_vals = {
                        'hacienda_estado_lote': dte_lote.get('estado', ''),
                        'hacienda_fhProcesamiento_lote': hacienda_fhProcesamiento_lote,
                        'hacienda_codigoMsg_lote': dte_lote.get('codigoMsg', ''),
                        'hacienda_descripcionMsg_lote': dte_lote.get('descripcionMsg', ''),
                        'state': "posted" if dte_lote.get('estado') == 'RECIBIDO' else 'draft',
                        'sit_json_respuesta': json.dumps(dte_lote) if isinstance(dte_lote, dict) else str(dte_lote),
                    }

                lote_record = None
                if lote.exists():
                    lote.write(lote_vals)
                    lote_record = lote

                # Asignar lote a todas las facturas del lote procesado
                _logger.info("Registro de lote creado con ID %s y asignado a facturas %s", lote_record.id, facturas.ids)

                if lote.hacienda_estado_lote and lote.hacienda_estado_lote.strip().upper() == "RECIBIDO":
                    mensajes.append(f"{lote.name}: {lote.hacienda_estado_lote}")

                # Verificar cuántas facturas se han asignado a este lote y si se excede el límite de lotes
                if len(facturas_firmadas) >= cant_lotes * cant_facturas:
                    _logger.info("Se ha alcanzado el límite de 400 lotes. Facturas restantes para próxima contingencia.")
                    break  # Salir del ciclo, ya no se añaden más facturas a la contingencia actual

            # Verificar que se hayan creado los lotes y no se hayan excedido
            if len(facturas_firmadas) > cant_lotes * cant_facturas:
                raise UserError("La cantidad de facturas excede el límite de lotes permitido (400 lotes).")

            _logger.info("SIT Fin generar lote")

        # Notificar al usuario si hubo alguna factura con sello o estado RECIBIDO
        if mensajes:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Lotes validados',
                    'message': "\n".join(mensajes),
                    'type': 'success',
                    'sticky': False,
                }
            }

        # Caso en que no hubo mensajes → retornar None explícitamente
        return None

    def generar_dte_lote(self, enviroment_type, payload_envio_mh, lotes_firmados, ambiente_test):
        """
        Envía el lote DTE a Hacienda según el entorno configurado (producción o pruebas).
        Retorna la respuesta de Hacienda o una simulación si está en ambiente de prueba.
        """
        _logger.info("SIT Generando DTE (env=%s)", enviroment_type)
        url = response = None

        # Simulación en ambiente de pruebas
        if ambiente_test:
            _logger.info("SIT Ambiente de pruebas, simulando respuesta exitosa.")
            return {
                "codigoMsg": "000",
                "descripcionMsg": "Ambiente de pruebas, no se envió a MH",
                "observaciones": ["Simulación de éxito en pruebas"],
                "es_test": True,
                "estado": "RECIBIDO",
            }

        # Determinar URL según ambiente
        if enviroment_type == constants.HOMOLOGATION:
            url = config_utils.get_config_value(self.env, "url_test_lotes", self.company_id.id) if config_utils else "https://apitest.dtes.mh.gob.sv/fesv/recepcionlote/"
        else:
            url = config_utils.get_config_value(self.env, "url_prod_lotes", self.company_id.id) if config_utils else "https://api.dtes.mh.gob.sv/fesv/recepcionlote/"
        _logger.info("SIT URL envío lote: %s", url)

        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Odoo',
            'Authorization': f"Bearer {self.company_id.sit_token}",
        }

        _logger.info("SIT = requests.request(POST, %s, headers=%s, data=%s)", url, headers, json.dumps(payload_envio_mh))
        # Intentar envío del lote
        try:
            response = requests.post(url, headers=headers, json=payload_envio_mh)
            _logger.info("SIT DTE response =%s", response)
            _logger.info("SIT DTE response =%s", response.status_code)
            _logger.info("SIT DTE response.text =%s", response.text)
        except Exception as error:
            status = getattr(getattr(error, 'response', None), 'status_code', 'N/A')
            mensaje_error = f"{status}, {str(error)}"
            _logger.error("SIT Error al enviar lote: %s", mensaje_error)
            raise UserError(_("Error al generar DTE lote:\n%s") % mensaje_error)

        # Intentar parsear JSON
        try:
            json_response = response.json()
            _logger.info("SIT JSON Response: %s", json_response)
        except Exception as e:
            _logger.error("SIT Error parseando JSON: %s", e)
            return {
                'estado': 'ERROR',
                'descripcionMsg': 'Respuesta inválida JSON',
                'lotes_firmados': lotes_firmados
            }

        # Manejo de errores HTTP
        _logger.info("SIT DTE decodificando respuestas")
        if response.status_code in [400, 401]:
            return {
                'estado': response.status_code,
                'descripcionMsg': response.text,
                'lotes_firmados': lotes_firmados
            }

        # Manejo de respuestas de Hacienda
        estado = json_response.get('estado') or json_response['estado']
        if estado in ["RECHAZADO", 402]:
            ambiente = 'TEST' if json_response.get('ambiente') == constants.AMBIENTE_TEST else 'PROD'
            MENSAJE_ERROR = (
                f"Código de Error: {estado}, Ambiente: {ambiente}, "
                f"Clasificación: {json_response.get('clasificaMsg')}, "
                f"Descripción: {json_response.get('descripcionMsg')}, "
                f"Detalle: {json_response.get('observaciones')},"
                f"DATA: {json.dumps(payload_envio_mh)}"
            )
            self.hacienda_estado = estado
            _logger.warning("SIT Lote rechazado: %s", MENSAJE_ERROR)
            return MENSAJE_ERROR

        # Errores genéricos (400-402 en JSON)
        status = json_response.get('status')
        if status and status in [400, 401, 402]:
            MENSAJE_ERROR = (
                f"Código de Error: {status}, "
                f"Error: {json_response.get('error', 'Desconocido')}, "
                f"Detalle: {json_response.get('message', 'No proporcionado')}"
            )
            _logger.warning("SIT Error 40X: %s", MENSAJE_ERROR)
            return MENSAJE_ERROR

        # Éxito
        if estado == "RECIBIDO":  # if json_response['estado'] in ["PROCESADO"]:
            _logger.info("SIT Estado RECIBIDO: %s", json_response)
            return json_response

        # Caso no esperado
        _logger.warning("SIT Estado desconocido: %s", json_response)
        return {'estado': 'DESCONOCIDO', 'descripcionMsg': 'Respuesta no reconocida', 'json': json_response}

    ##################################### GENERAR JSON LOTE
    def sit_obtener_payload_lote_dte_info(self, ambiente, doc_firmado, nitEmisor, version):
        """
        Construye el payload JSON para el envío de un lote DTE a Hacienda.
        Incluye ambiente, versión, NIT emisor y documentos firmados.
        """
        invoice_info = {}
        invoice_info["ambiente"] = ambiente
        invoice_info["idEnvio"] = self.sit_generar_uuid()
        version = int(config_utils.get_config_value(self.env, 'version_lote', self.company_id.id)) if config_utils else 3
        invoice_info["version"] = version
        invoice_info["nitEmisor"] = nitEmisor
        invoice_info["documentos"] = doc_firmado

        return invoice_info

    def sit_obtener_payload_lote_dte_firma(self, nitEmisor, llavePrivada, doc_firmado):
        """Genera el payload para firmar un DTE en lote, incluyendo NIT, llave privada y JSON del documento."""
        invoice_info = {}
        invoice_info["nit"] = nitEmisor
        invoice_info["activo"] = True
        invoice_info["passwordPri"] = llavePrivada

        # Convertir JSON string a dict
        if isinstance(doc_firmado, dict):
            invoice_info["dteJson"] = doc_firmado
        else:
            invoice_info["dteJson"] = json.loads(doc_firmado)
        return invoice_info

    # ---------------------------------------------------------------------------------------------    POST CONTINGENCIA
    @api.depends('contingencia_recibida_mh')
    def _compute_mostrar_boton_contingencia(self):
        """Controla la visibilidad del botón de contingencia. Se muestra solo si la contingencia está activa y aún no ha sido recibida por MH."""
        for rec in self:
            # Lógica de ejemplo: mostrar solo si está en 'posted' y aún no tiene lote
            rec.boton_contingencia = not rec.contingencia_recibida_mh and rec.contingencia_activa

    def _compute_company_id(self):
        """Asigna la compañía actual al registro si difiere de la existente y garantiza coherencia entre el entorno activo y el registro."""
        _logger.info("SIT calculando company_id")
        for move in self:
            company_id = self.env.company
            if company_id != move.company_id:
                move.company_id = company_id

    def _compute_date(self):
        """
        Asigna la fecha actual al registro si no tiene una definida.
        Asegura que todos los movimientos tengan una fecha válida.
        """
        _logger.info("SIT calculando date")
        for move in self:
            if not move.date:
                move.date = fields.Date.context_today(self)

    def _compute_name(self):
        _logger.info("SIT asignando name")
        for record in self:
            FechaEventoContingencia = datetime.datetime.now()
            _logger.info("SIT FechaEventoContingencia = %s (%s)", FechaEventoContingencia, type(FechaEventoContingencia))
            FECHA_EVENTO_CONTINGENCIA = FechaEventoContingencia.strftime('%Y-%m-%d_%H%M%S')
            _logger.info("SIT sit_ccf_ FECHA_EVENTO_CONTINGENCIA = %s", FECHA_EVENTO_CONTINGENCIA)
            NAME = "EVENTO_CONTINGENCIA_" + str(FECHA_EVENTO_CONTINGENCIA)
            record.name = NAME

    def action_post_contingencia(self):  # Generacion de eventos en contingencia(envio a MH)
        '''validamos que partner cumple los requisitos basados en el tipo
        de documento de la sequencia del diario selecionado
        FACTURA ELECTRONICAMENTE
        '''
        _logger.info("SIT Iniciando Validación de Contingencia (account_contingencia_lote)")
        mensajes = []
        for invoice in self:
            ambiente_test = False
            ambiente = None
            documento_firmado = ""

            try:
                validation_type = self.company_id._get_environment_type()
                _logger.info("SIT action_post validation_type = %s", validation_type)

                if validation_type == constants.HOMOLOGATION:
                    ambiente = constants.AMBIENTE_TEST
                    _logger.info("SIT Factura de Prueba")
                elif validation_type == constants.AMBIENTE_PROD:
                    _logger.info("SIT Factura de Producción")
                    ambiente = constants.PROD_AMBIENTE

                payload_contingencia = invoice.obtener_payload_contingencia(validation_type)

                if config_utils:
                    ambiente_test = config_utils._compute_validation_type_2(self.env, self.company_id)
                    _logger.info("SIT-Contingencia Tipo de entorno[Ambiente]: %s", ambiente_test)

                _logger.info("SIT Generando DTE conteingencia")
                documento_firmado_contingencia = None
                if not ambiente_test:
                    documento_firmado_contingencia = invoice.firmar_documento(validation_type, payload_contingencia)

                    if not documento_firmado_contingencia:
                        raise UserError("Error en firma del documento")

                _logger.info("SIT Documento firmado: %s", documento_firmado_contingencia)
                payload_dte_contingencia = invoice.sit_obtener_payload_contingencia_dte_info(documento_firmado_contingencia)

                # self.check_parametros_dte(payload_dte)
                Resultado = invoice.generar_dte_contingencia(validation_type, payload_dte_contingencia, payload_contingencia, ambiente_test)
                if Resultado:
                    dat_time = None
                    fechaHora = None
                    if not ambiente_test and Resultado['fechaHora']:
                        dat_time = Resultado['fechaHora']

                    try:
                        if config_utils:
                            fechaHora = config_utils._get_fecha_procesamiento(dat_time)
                        if not fechaHora:
                            # fallback final: usar fecha de creación de Odoo
                            fechaHora = self.create_date
                    except Exception as e:
                        _logger.warning("No se pudo obtener fechaHora de Resultado: %s", e)
                        fechaHora = None

                    if fechaHora:
                        # Si tiene tzinfo, lo hacemos naive
                        if fechaHora.tzinfo is not None:
                            fechaHora = fechaHora.replace(tzinfo=None)
                        invoice.sit_fechaHora = fechaHora

                    _logger.info("SIT Fecha de procesamiento (%s)%s", type(dat_time), dat_time)
                    _logger.info("SIT Fecha de sit_fechaHora (%s)%s", type(invoice.sit_fechaHora), invoice.sit_fechaHora)
                    invoice.sit_estado = Resultado['estado']
                    invoice.hacienda_estado = Resultado['estado']
                    invoice.sit_mensaje = Resultado['mensaje']
                    invoice.sit_selloRecibido = Resultado.get('selloRecibido', None)
                    invoice.sit_observaciones = Resultado['observaciones']
                    invoice.state = "posted" if Resultado['estado'] == 'RECIBIDO' else 'draft'

                    try:
                        tz = pytz.timezone('America/El_Salvador')  # Obtener zona horaria de El Salvador
                        now_sv = datetime.now(tz).replace(tzinfo=None)  # Convertir a naive
                        invoice.fechaHoraTransmision = now_sv
                    except pytz.UnknownTimeZoneError:
                        raise UserError("No se pudo determinar la zona horaria 'America/El_Salvador'. Verifique su configuración.")
                    except Exception as e:
                        raise UserError(f"Ocurrió un error al asignar la fecha y hora actual: {str(e)}")

                    # JSON
                    dteJson = payload_contingencia['dteJson']
                    _logger.info("Tipo de dteJson: %s, json: %s", type(dteJson), dteJson)
                    if isinstance(dteJson, str):
                        try:
                            # Verifica si es un JSON string válido, y lo convierte a dict
                            dteJson = json.loads(dteJson)
                        except json.JSONDecodeError:
                            # Ya era string, pero no era JSON válido -> guardar tal cual
                            invoice.sit_json_respuesta = dteJson
                        else:
                            # Era un JSON string válido → ahora es dict
                            invoice.sit_json_respuesta = json.dumps(dteJson, ensure_ascii=False)
                    elif isinstance(dteJson, dict):
                        invoice.sit_json_respuesta = json.dumps(dteJson, ensure_ascii=False)
                    else:
                        # Otro tipo de dato no esperado
                        invoice.sit_json_respuesta = str(dteJson)

                    # Respuesta json
                    if not ambiente_test:
                        json_response_data = {
                            "jsonRespuestaMh": Resultado
                        }

                        # Convertir el JSON en el campo sit_json_respuesta a un diccionario de Python
                        try:
                            json_original = json.loads(invoice.sit_json_respuesta) if invoice.sit_json_respuesta else {}
                        except json.JSONDecodeError:
                            json_original = {}

                        # Fusionar JSONs
                        json_original.update(json_response_data)
                        sit_json_respuesta_fusionado = json.dumps(json_original)
                        invoice.sit_json_respuesta = sit_json_respuesta_fusionado

                if invoice.sit_selloRecibido or invoice.sit_estado == 'RECIBIDO':
                    mensajes.append(f"{invoice.name}: {invoice.sit_estado}")

            except Exception as e:
                error_msg = traceback.format_exc()
                _logger.exception("SIT Error durante el _post para invoice ID %s: %s", invoice.id, str(e))
                invoice.write({
                    'error_log': error_msg,
                    'state': 'draft',
                })
                raise e

        # Notificar al usuario si hubo alguna factura con sello o estado RECIBIDO
        if mensajes:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Contingencia validada',
                    'message': "\n".join(mensajes),
                    'type': 'success',
                    'sticky': False,
                }
            }
        # Caso en que no hubo mensajes → retornar None explícitamente
        return None

    # FIMAR FIMAR FIRMAR =====================================================================================================
    def firmar_documento(self, enviroment_type, payload):
        _logger.info("SIT Documento a FIRMAR =%s", payload)
        url = config_utils.get_config_value(self.env, 'url_firma', self.company_id.id)
        if not url:
            _logger.error("SIT | No se encontró 'url_firma' en la configuración para la compañía ID %s", self.company_id.id)
            raise UserError(_("La URL de firma no está configurada en la empresa."))
        authorization = self.company_id.sit_token

        headers = {
            "Authorization": f"Bearer {authorization}",
            'User-Agent': 'Odoo',  # agente,
            'Content-Type': 'application/json',
        }

        response = None
        MENSAJE_ERROR = None
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            _logger.info("SIT firmar_documento response =%s", response.text)
            self.write({'sit_documento_firmado_contingencia': response.text})
        except Exception as e:
            _logger.info('SIT error= %s, ', e)

            MENSAJE_ERROR = str(e)
            try:
                error_dict = json.loads(str(e))
                if isinstance(error_dict, dict):
                    MENSAJE_ERROR = "{}, {}, {}".format(
                        error_dict.get('status'),
                        error_dict.get('error'),
                        error_dict.get('message')
                    )
            except json.JSONDecodeError:
                pass
            _logger.warning("Error firmando documento: %s", MENSAJE_ERROR)
            return False  # SALIR si no se pudo hacer la petición

        resultado = []
        # Verificar que el contenido sea JSON válido
        try:
            json_response = response.json()
        except Exception:
            _logger.warning("Respuesta no es JSON válido: %s", response.text)
            return False

        _logger.info("SIT json responde=%s", json_response)

        if json_response.get('status') in [400, 401, 402]:
            _logger.info("SIT Error 40X  =%s", json_response['status'])
            status = json_response['status']
            error = json_response['error']
            message = json_response['message']
            MENSAJE_ERROR = "Código de Error:" + str(status) + ", Error:" + str(error) + ", Detalle:" + str(message)
            _logger.warning("Error:%s", MENSAJE_ERROR)
            return False

        if json_response['status'] in ['ERROR', 401, 402]:
            _logger.info("SIT Error 40X  =%s", json_response['status'])
            status = json_response['status']
            body = json_response['body']
            codigo = body['codigo']
            message = body['mensaje']
            resultado.append(status)
            resultado.append(codigo)
            resultado.append(message)
            MENSAJE_ERROR = "Código de Error:" + str(status) + ", Codigo:" + str(codigo) + ", Detalle:" + str(message)
            _logger.warning("Error:%s", MENSAJE_ERROR)
            return False
        elif json_response['status'] == 'OK':
            _logger.info("SIT Estado procesado=%s", json_response['status'])
            status = json_response['status']
            body = json_response['body']
            resultado.append(status)
            resultado.append(body)
            return body
        return False

    ##################################### GENERAR JSON CONTINGENCIA
    def obtener_payload_contingencia(self, enviroment_type):
        _logger.info("SIT  Obteniendo payload")

        self.check_parametros_contingencia()
        invoice_info = self.sit__contingencia_base_map_invoice_info()
        _logger.info("SIT invoice_info CONTINGENCIA = %s", invoice_info)

        _logger.info("SIT payload_data =%s", invoice_info)
        return invoice_info

    def generar_dte_contingencia(self, enviroment_type, payload, payload_original, ambiente_test):
        _logger.info("SIT  Generando DTE___contingencia, ambiente: %s", enviroment_type)
        url = None
        if enviroment_type == constants.HOMOLOGATION:
            url = config_utils.get_config_value(self.env, 'url_test_contingencia', self.company_id.id) if config_utils else "https://apitest.dtes.mh.gob.sv/fesv/contingencia"
        else:
            url = config_utils.get_config_value(self.env, 'url_prod_contingencia', self.company_id.id) if config_utils else "https://api.dtes.mh.gob.sv/fesv/contingencia"

        # Regregsar al post si es test
        if ambiente_test:
            _logger.info("SIT Ambiente de pruebas contingencia, se omite envío a Hacienda y se simula respuesta exitosa.")
            return {
                "codigoMsg": "000",
                "mensaje": "Ambiente de pruebas, no se envió a MH",
                "observaciones": ["Simulación de éxito en pruebas"],
                "es_test": True,  # 👈 indica que fue ambiente de prueba
                "estado": "RECIBIDO",
            }

        # Refrescar token si hace falta ———
        today = fields.Date.context_today(self)
        if not self.company_id.sit_token_fecha or self.company_id.sit_token_fecha.date() < today:
            self.company_id.get_generar_token()

        authorization = self.company_id.sit_token

        headers = {
            "Authorization": f"Bearer {authorization}",
            'User-Agent': 'Odoo',  # agente,
            'Content-Type': 'application/json',
        }

        _logger.info("SIT json =%s", payload_original)
        _logger.info("SIT contingencia  = requests.request(POST, %s, headers=%s, data=%s)", url, headers, payload)

        try:
            # response = requests.request("POST", url, headers=headers, data=json.dumps(payload))
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            _logger.info("SIT DTE contingencia response =%s", response)
            _logger.info("SIT DTE contingencia response status=%s", response.status_code)
            _logger.info("SIT DTE contingencia response.text =%s", response.text)
        except Exception as e:
            error = str(e)
            _logger.info('SIT error= %s, ', error)
            if "error" in error or "" in error:
                MENSAJE_ERROR = str(error['status']) + ", " + str(error['error']) + ", " + str(error['message'])
                raise UserError(_(MENSAJE_ERROR))
            else:
                raise UserError(_(error))
        resultado = []
        _logger.info("SIT DTE decodificando respuestas")
        if response.status_code in [401]:
            MENSAJE_ERROR = "ERROR de conexión : " + str(response)
            raise UserError(_(MENSAJE_ERROR))

        json_response = response.json()
        _logger.info("SIT json_responset =%s", json_response)

        if json_response:
            estado = json_response.get('estado') or json_response.get('status')
            mensaje = json_response.get('mensaje') or json_response.get('message')
            fechaHora_str = json_response.get('fechaHora')
            observaciones = json_response.get('observaciones', '')

            # Convertir fechaHora a datetime si existe
            fechaHora = None
            if fechaHora_str:
                try:
                    fechaHora = datetime.strptime(fechaHora_str, '%d/%m/%Y %H:%M:%S')
                except Exception as e:
                    _logger.warning("No se pudo convertir fechaHora: %s", fechaHora_str)

            # Guardar siempre los datos en la factura/contingencia
            self.write({
                'hacienda_estado': estado,
                'sit_mensaje': mensaje,
                'sit_fechaHora': fechaHora,
                'sit_observaciones': observaciones,
            })
            self.env.cr.commit()

        if json_response['estado'] in ["RECHAZADO", 402]:
            status = json_response['estado']
            fechaHora = json_response['fechaHora']
            mensaje = json_response['mensaje']
            selloRecibido = json_response['selloRecibido']
            observaciones = json_response['observaciones']

            MENSAJE_ERROR = "Código de Error..:" + str(status) + ", fechaHora:" + fechaHora + ", mensaje:" + str(
                mensaje) + ", selloRecibido:" + str(selloRecibido) + ", observaciones:" + str(
                observaciones) + ", DATA:  " + str(json.dumps(payload_original))
            self.hacienda_estado = status
            raise UserError(_(MENSAJE_ERROR))
        if response.status_code in [400]:
            _logger.info("SIT Contingencia Error 40X  =%s", response.status_code)
            message = json_response.get('mensaje', 'Mensaje no proporcionado')  # Si 'message' no existe, devuelve 'Mensaje no proporcionado'
            estado = json_response.get('estado', 'Estado no proporcionado')
            MENSAJE_ERROR = "Código de Error:" + str(response.status_code) + ", Detalle:" + str(
                message) + ", DATA REQUEST = " + str(json.dumps(payload))
            raise UserError(_(MENSAJE_ERROR))

        status = json_response.get('status')
        if status and status in [400, 401, 402]:
            _logger.info("SIT Error 40X  =%s", status)
            error = json_response.get('error', 'Error desconocido')  # Si 'error' no existe, devuelve 'Error desconocido'
            message = json_response.get('message', 'Mensaje no proporcionado')  # Si 'message' no existe, devuelve 'Mensaje no proporcionado'
            MENSAJE_ERROR = "Código de Error:" + str(status) + ", Error:" + str(error) + ", Detalle:" + str(message)
            raise UserError(_(MENSAJE_ERROR))
        _logger.info("SIT  json_response('estado) =%s", json_response['estado'])
        if json_response['estado'] in ["RECIBIDO"]:
            self.write({'contingencia_recibida_mh': True})
            return json_response

    def _autenticar(self, user, pwd, ):
        _logger.info("SIT self = %s", self)
        enviroment_type = self._get_environment_type()
        _logger.info("SIT Modo = %s", enviroment_type)
        url = None
        if enviroment_type == constants.HOMOLOGATION:
            url = config_utils.get_config_value(self.env, 'autenticar_test', self.company_id.id) if config_utils else 'https://apitest.dtes.mh.gob.sv/seguridad/auth'
        else:
            url = config_utils.get_config_value(self.env, 'autenticar_prod', self.company_id.id)  if config_utils else 'https://apitest.dtes.mh.gob.sv/seguridad/auth'

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
        json_response = response.json()

    def check_parametros_contingencia(self):
        # Tipo de documento: iva/nit(campo fax) = 1, dui(campo dui) = 4, otro = 5, pasaporte = 2, extranjero = 3
        if not self.company_id:
            raise UserError(_('El Nombre de la compañía no definido'))

        _logger.info("SIT-Usuario: %s", self.invoice_user_id)
        if not self.invoice_user_id.partner_id.name:
            raise UserError(_('El Nombre de Responsable no definido'))
        if not self.invoice_user_id.partner_id.vat and not self.invoice_user_id.partner_id.dui:
            raise UserError(_('El Número de Documento de Responsable no definido'))  # raise UserError(_('El Número de RFC no definido'))
        if not self.company_id.tipoEstablecimiento.codigo:
            raise UserError(_('El tipoEstablecimiento no definido'))
        if not self.sit_tipo_contingencia:
            raise UserError(_('El tipoContingencia no definido'))

        _logger.info("Tipo contingencia: %s | Constante motivo: %s | Motivo contingencia: %s",
                     self.sit_tipo_contingencia.codigo, constants.MOT_CONTIN_OTRO, self.sit_tipo_contingencia_otro)
        if self.sit_tipo_contingencia and self.sit_tipo_contingencia.codigo == constants.MOT_CONTIN_OTRO:
            if not self.sit_tipo_contingencia_otro or not self.sit_tipo_contingencia_otro.strip():
                raise UserError(_('MotivoContingencia no definido'))
        if not self.sit_fFin_hFin:
            raise UserError(_('El campo Fecha de Fin de Contingencia - Hacienda (sit_fFin_hFin) no definido'))

    def check_parametros_firmado(self):
        _logger.info("SIT-Contingencia Validaciones parametros doc firmado")
        if not self.name:
            raise UserError(_('El Número de control no definido'))
        if not self.company_id.sit_passwordPri:
            raise UserError(_('El valor passwordPri no definido'))
        if not self.company_id.sit_uuid:
            raise UserError(_('El valor uuid no definido'))
        if not self.company_id.vat:
            raise UserError(_('El emisor no tiene NIT configurado.'))
        if not self.company_id.company_registry:
            raise UserError(_('El emisor no tiene NRC configurado.'))
        if not self.company_id.name:
            raise UserError(_('El emisor no tiene NOMBRE configurado.'))
        if not self.company_id.codActividad:
            raise UserError(_('El emisor no tiene CODIGO DE ACTIVIDAD configurado.'))
        if not self.company_id.tipoEstablecimiento:
            raise UserError(_('El emisor no tiene TIPO DE ESTABLECIMIENTO configurado.'))
        if not self.company_id.state_id:
            raise UserError(_('El emisor no tiene DEPARTAMENTO configurado.'))
        if not self.company_id.munic_id:
            raise UserError(_('El emisor no tiene MUNICIPIO configurado.'))
        if not self.company_id.email:
            raise UserError(_('El emisor no tiene CORREO configurado.'))

        if not self.partner_id.vat:
            if self.partner_id.is_company == True:
                _logger.info("SIT, es compañia se requiere NIT")
            raise UserError(_('El receptor no tiene NIT configurado.'))
        if not self.partner_id.nrc:
            if self.partner_id.is_company == True:
                _logger.info("SIT, es compañia se requiere NRC")
                raise UserError(_('El receptor no tiene NRC configurado.'))
        if not self.partner_id.name:
            raise UserError(_('El receptor no tiene NOMBRE configurado.'))
        if not self.partner_id.codActividad:
            raise UserError(_('El receptor no tiene CODIGO DE ACTIVIDAD configurado.'))
        if not self.partner_id.state_id:
            raise UserError(_('El receptor no tiene DEPARTAMENTO configurado.'))
        if not self.partner_id.munic_id:
            raise UserError(_('El receptor no tiene MUNICIPIO configurado.'))
        if not self.partner_id.email:
            raise UserError(_('El receptor no tiene CORREO configurado.'))
        if not self.invoice_line_ids:
            raise UserError(_('La factura no tiene LINEAS DE PRODUCTOS asociada.'))

    def check_parametros_dte(self, generacion_dte, ambiente_test):
        _logger.info("SIT-Contingencia Validaciones check_parametros_dte")
        if not (self.company_id and self.company_id.sit_facturacion):
            _logger.info("SIT No aplica facturación electrónica. Se omite validación de parámetros DTE en modulo de Contingencia.")
            return False

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

    # Generar secuencia para contingencia
    @api.model
    def _generate_contingencia_name(self, journal=None, actualizar_secuencia=False, empresa=False):
        journal = journal

        # Validaciones
        version_contingencia = config_utils.get_config_value(
            self.env, 'version_contingencia', journal.company_id.id
        )
        _logger.info("Versión contingencia: %s | Compañía: %s", version_contingencia, journal.company_id)

        if version_contingencia is None:
            raise UserError(_("Debe definir la versión de la contingencia."))

        if not journal.sit_codestable:
            raise UserError(_("Configure Código de Establecimiento en diario '%s'.") % journal.name)

        if not journal.sit_codpuntoventa:
            raise UserError(_("Configure el Punto de Venta en el diario '%s'.") % journal.name)

        # if not journal.sequence_id:
        #     raise UserError(_("Configure una secuencia de contingencia en el diario '%s'.") % journal.name)

        # Obtener secuencia configurada para actualizar el número, no para generar el nombre
        sequence = self.env['ir.sequence'].search([
            ('code', '=', 'CONT'),
            ('company_id', '=', empresa.id),
        ], limit=1)
        _logger.info("Secuencia contingencia: %s | Empresa: %s", sequence, empresa.id)
        if not sequence or not sequence.exists():
            raise UserError(_("Secuencia no configurada para contingencia."))

        # Tomar el prefix de la secuencia y reemplazar placeholders dinámicamente
        prefix = sequence.prefix or ''  # prefijo dinámico de la secuencia
        _logger.info("Prefix contingencia: %s ", prefix)

        version_str = str(version_contingencia).zfill(2)
        if not version_str.strip():
            raise UserError("La versión de contingencia no puede estar vacía.")
        estable = journal.sit_codestable
        punto_venta = journal.sit_codpuntoventa

        # Diccionario para reemplazar los placeholders dinámicamente
        replacements = {
            'con': version_str,  # Reemplazo para %(con)s
            'estable': estable,  # Reemplazo para %(estable)s
            'punto_venta': punto_venta,  # Reemplazo para %(punto_venta)s
        }

        # Reemplazar los placeholders en el prefix de la secuencia
        pattern_prefix = prefix
        for key, value in replacements.items():
            pattern_prefix = pattern_prefix.replace(f'%({key})s', value)

        _logger.info("Prefijo dinámico final contingencia: %s", pattern_prefix)

        # Buscar el último nombre generado que coincida con el patrón
        ultimo = self.search([('company_id', '=', empresa.id), ('name', 'like', f'{pattern_prefix}%')], order='name desc', limit=1)
        if ultimo:
            try:
                ultima_parte = int(ultimo.name.split('-')[-1])
            except ValueError:
                raise UserError(_("No se pudo interpretar el número del último nombre de contingencia: %s") % ultimo.name)
            nuevo_numero = ultima_parte + 1
        else:
            nuevo_numero = 1

        # Generar el nuevo nombre con el prefix de la secuencia
        nuevo_name = f"{pattern_prefix}{str(nuevo_numero).zfill(15)}"

        # Verificar duplicado
        if self.search_count([('name', '=', nuevo_name), ('company_id', '=', empresa.id)]):
            raise UserError(_("El número de contingencia generado ya existe: %s") % nuevo_name)

        _logger.info("Nombre de contingencia generado dinámicamente con prefix: %s", nuevo_name)

        # Actualizar secuencia (ir.sequence o ir.sequence.date_range)
        if actualizar_secuencia:
            next_num = nuevo_numero + 1
            if sequence.use_date_range:
                today = fields.Date.context_today(self)
                date_range = self.env['ir.sequence.date_range'].search([
                    ('sequence_id', '=', sequence.id),
                    ('date_from', '<=', today),
                    ('date_to', '>=', today)
                ], limit=1)
                if date_range and date_range.number_next_actual < next_num:
                    date_range.number_next_actual = next_num
                    _logger.info("Secuencia con date_range '%s' actualizada a %s", sequence.code, next_num)
            else:
                if sequence.number_next_actual < next_num:
                    sequence.number_next_actual = next_num
                    _logger.info("Secuencia '%s' actualizada a %s", sequence.code, next_num)

        return nuevo_name

    # ---------------------------------------------------------------------------------------------
    def _compute_validation_type_2(self):
        """Determina el tipo de validación (entorno) si no existe código AFIP."""
        for rec in self:
            if not rec.afip_auth_code:
                validation_type = self.env["res.company"]._get_environment_type()
                if validation_type == constants.HOMOLOGATION:
                    try:
                        rec.company_id.get_key_and_certificate(validation_type)
                    except Exception as e:
                        _logger.warning("Error obteniendo certificado: %s", e)
                        validation_type = False

                rec.validation_type = validation_type
            else:
                rec.validation_type = False

    @api.model_create_multi
    def create(self, vals_list):
        _logger.info("SIT | Entrando a create() de contingencia con %s registros a procesar", len(vals_list))

        # Crear el registro de contingencia
        registros_a_procesar = []
        for vals in vals_list:
            _logger.debug("SIT | Procesando vals: %s", vals)
            # Si viene el name o algún indicador de que es del módulo de Hacienda, no hacer lógica de contingencia
            if vals.get('name'):
                _logger.info("SIT | Se detectó 'name' en vals (%s), omitiendo lógica de contingencia.", vals['name'])
                return super().create(vals_list)
            registros_a_procesar.append(vals)

        # Crear los registros base
        _logger.info("SIT | Total de registros a crear en contingencia: %s", len(registros_a_procesar))
        records = super().create(registros_a_procesar)

        for record in records:
            _logger.info("SIT | Procesando contingencia creada con ID=%s", record.id)
            cant_lotes = int(config_utils.get_config_value(self.env, 'cantidad_lote', self.company_id.id) or 400)
            cant_facturas = int(config_utils.get_config_value(self.env, 'cantidad_factura', self.company_id.id) or 1)

            # Buscar todas las facturas que están en contingencia y no están asignadas a ninguna contingencia aún
            facturas_en_contingencia = self.env['account.move'].search([
                ('sit_es_configencia', '=', True),
                ('sit_factura_de_contingencia', '=', False),
                '|', ('hacienda_selloRecibido', '=', None), ('hacienda_selloRecibido', '=', '')
            ])

            # Asignar las facturas al registro actual
            if facturas_en_contingencia:
                facturas_en_contingencia_count = len(facturas_en_contingencia)
                _logger.info("SIT | Facturas encontradas en contingencia: %s", facturas_en_contingencia_count)

                total_lotes = ((facturas_en_contingencia_count // cant_facturas) +
                               (1 if facturas_en_contingencia_count % cant_facturas != 0 else 0))

                if total_lotes > cant_lotes:
                    _logger.info("La cantidad de facturas excede el límite de lotes permitidos. Solo se asignarán los primeros 400 lotes.")
                    facturas_a_incluir = facturas_en_contingencia[:cant_lotes * cant_facturas]
                    facturas_en_contingencia = facturas_a_incluir  # Solo trabajar con las primeras 40,000 facturas

                # Crear los lotes y asignar las facturas a cada lote
                lote_count = 0
                for i in range(0, facturas_en_contingencia_count, cant_facturas):
                    facturas_lote = facturas_en_contingencia[i:i + cant_facturas]

                    # Crear lote
                    lote_vals = {
                        'sit_contingencia': record.id,  # Relaciona el lote con la contingencia
                        'state': 'draft',  # El lote puede empezar en estado borrador
                    }
                    lote_record = super(AccountLote, self.env['account.lote']).create(lote_vals)
                    _logger.info(f"Lote creado con {len(facturas_lote)} facturas en contingencia.")

                    # Asignar cada lote a las facturas correspondientes
                    facturas_lote.write({
                        'sit_lote_contingencia': lote_record.id
                    })
                # Después de asignar todas las facturas a los lotes, las asociamos a la contingencia
                facturas_en_contingencia.write({
                    'sit_factura_de_contingencia': record.id
                })
        return records

    @api.model
    def actualizar_contingencias_expiradas(self):
        """Desactiva contingencias (24h) y sus lotes o bloques (72h) según corresponda."""
        _logger.info("Iniciando actualización de contingencias expiradas")
        tz = pytz.timezone('America/El_Salvador')
        hora_actual = pytz.utc.localize(datetime.utcnow()).astimezone(tz)
        company_id = self.env.company.id

        # --- 1. Desactivar contingencias activas (24h) ---
        contingencias_activas = self.search([
            ('contingencia_activa', '=', True),
            ('sit_fInicio_hInicio', '!=', False),
            ('company_id', '=', company_id),
        ])

        for contingencia in contingencias_activas:
            # Fecha de inicio para validar contingencia activa (24h)
            inicio = contingencia.sit_fechaHora or contingencia.sit_fInicio_hInicio
            if inicio and inicio.tzinfo is None:
                # Convertir a zona horaria de El Salvador si está en UTC
                inicio = pytz.utc.localize(inicio).astimezone(tz)

            # --- Validación de contingencia (24h) ---
            if inicio and hora_actual - inicio >= timedelta(hours=24):  # if hora_actual - inicio >= timedelta(hours=1):
                contingencia.contingencia_activa = False
                _logger.info("Contingencia %s desactivada por vencimiento de 24h desde creación o rechazo", contingencia.id)

        # --- 2. Validar lotes o bloques (72h desde sello MH), aunque la contingencia esté desactivada ---
        contingencias_con_sello = self.search([
            ('sit_fechaHora', '!=', False),
            ('sit_selloRecibido', '!=', False),
            ('company_id', '=', company_id),
        ])

        for contingencia in contingencias_con_sello:
            sello_evento = contingencia.sit_fechaHora
            if sello_evento.tzinfo is None:
                sello_evento = pytz.utc.localize(sello_evento).astimezone(tz)

            if contingencia.sit_usar_lotes:
                # Validar lotes activos aunque la contingencia esté desactivada
                for lote in contingencia.lote_ids.filtered(lambda l: l.lote_activo):
                    if hora_actual - sello_evento >= timedelta(hours=72):
                        lote.lote_activo = False
                        _logger.info("Lote %s de contingencia %s desactivado por vencimiento de 72h desde sello MH", lote.id, contingencia.id)
            else:
                # Validar bloques activos
                for bloque in contingencia.bloque_ids.filtered(lambda b: b.bloque_activo):
                    if hora_actual - sello_evento >= timedelta(hours=72):
                        bloque.bloque_activo = False
                        _logger.info("Bloque %s de contingencia %s desactivado por vencimiento de 72h desde sello MH", bloque.id, contingencia.id)
