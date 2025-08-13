##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from odoo.tools import float_repr
from odoo.addons.l10n_sv_haciendaws_fe.afip_utils import get_invoice_number_from_response
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
from datetime import datetime
import pytz

_logger = logging.getLogger(__name__)
try:
    from odoo.addons.common_utils.utils import config_utils
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo config_utils [hacienda ws-account_contingencia_lote]")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    config_utils = None
    constants = None

class sit_AccountContingencia(models.Model):
    _inherit = "account.contingencia1"


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
        string="Fecga de Procesamiento de Lote",
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

    def action_lote_generate(self):
        # after validate, send invoice data to external system via http post
        facturas_firmadas = []
        nro_factura = 0
        payload = None
        facturas_no_asignadas = []
        version = None

        for lote in self.lote_ids:
            # Validar que la contingencia relacionada esté recibida
            contingencia = lote.sit_contingencia  # asumo que lote tiene campo Many2one a contingencia
            if not contingencia or contingencia.sit_selloRecibido in (False, None, '', 'False', '0'):
                raise UserError(f"La contingencia relacionada al lote {lote.id} no ha sido recibida por MH.")

                nro_factura += 1
                _logger.info('SIT action_lote_generate lote a firmar = %s', lote.id)

                if lote.hacienda_codigoLote_lote:
                    _logger.info("SIT Lote ya procesado, se omite: %s", lote.id)
                    continue

                facturas = self.env['account.move'].search([
                    ('sit_lote_contingencia', '=', lote.id)
                ])

                for invoice in facturas:
                    validation_type = self._compute_validation_type_2()
                    ambiente = "00"
                    if validation_type == 'homologacioin':
                        ambiente = "00"
                        _logger.info("SIT Factura de Prueba")
                    elif validation_type == 'production':
                        _logger.info("SIT Factura de Producción")
                        ambiente = "01"
                    emisor = self.company_id.vat
                    emisor = emisor.replace("-", "").replace(".", "")

                    if not emisor:
                        raise UserError("SIT Se requiere definir compañia")

                    if not invoice.sit_json_respuesta or invoice.sit_json_respuesta.strip() in ['', '{}', '[]']:
                        _logger.info("SIT Creando json factura relacionada(contingencia)")
                        sit_tipo_documento = invoice.journal_id.sit_tipo_documento.codigo
                        payload = invoice.obtener_payload('production', sit_tipo_documento)
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

                    firmando = self.firmar_documento('production', payload_dte_firma)
                    if firmando:
                        facturas_firmadas.append(firmando)
                    else:
                        raise UserError(f"Factura no firmada = {invoice.name}")

                    # version = payload["dteJson"]["identificacion"]["ambiente"]
                    payload_dte_envio_mh = self.sit_obtener_payload_lote_dte_info(ambiente, facturas_firmadas, emisor, version)

                    if nro_factura > 20:
                        raise UserError(f"Factura firmada = {firmado}")

                    # Generando el DTE
                    dte_lote = self.generar_dte_lote(validation_type, payload_dte_envio_mh, len(facturas_firmadas))
                    _logger.info("SIT Respuesta MH=%s", dte_lote)

                    # Guardar json respuesta SOLO si la factura no lo tenía
                    if not invoice.sit_json_respuesta or invoice.sit_json_respuesta.strip() in ['', '{}', '[]']:
                        invoice.write({
                            'sit_json_respuesta': payload["dteJson"] if payload["dteJson"] else None
                        })

                    hacienda_fhProcesamiento_lote = None
                    try:
                        fh = dte_lote.get('fhProcesamiento')
                        _logger.info("SIT Fecha de procesamiento (%s)%s", type(fh), fh)
                        if fh:
                            hacienda_fhProcesamiento_lote = datetime.strptime(fh, '%d/%m/%Y %H:%M:%S')
                            _logger.info("hacienda_fhProcesamiento_lote = %s", hacienda_fhProcesamiento_lote)
                    except Exception as e:
                        _logger.warning("No se pudo parsear fecha de procesamiento lote: %s", e)

                    # Guardar datos de account.lote
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

                    if lote.exists():
                        lote.write(lote_vals)
                        lote_record = lote
                    # else:
                    #     lote_record = self.env['account.lote'].create(lote_vals)

                    # Asignar lote a todas las facturas del lote procesado
                    # facturas.write({'sit_lote_contingencia': lote_record.id})
                    _logger.info("Registro de lote creado con ID %s y asignado a facturas %s", lote_record.id,
                                 facturas.ids)

                    # Verificar cuántas facturas se han asignado a este lote y si se excede el límite de lotes
                    if len(facturas_firmadas) >= 400 * 100:
                        _logger.info(
                            "Se ha alcanzado el límite de 400 lotes. Facturas restantes para próxima contingencia.")
                        break  # Salir del ciclo, ya no se añaden más facturas a la contingencia actual

                # Verificar que se hayan creado los lotes y no se hayan excedido
                if len(facturas_firmadas) > 400 * 100:
                    raise UserError("La cantidad de facturas excede el límite de lotes permitido (400 lotes).")

            _logger.info("SIT Fin generar lote")

    def generar_dte_lote(self, enviroment_type, payload_envio_mh, lotes_firmados):
        _logger.info("SIT  Generando DTE")
        if enviroment_type == 'homologation':
            host = 'https://apitest.dtes.mh.gob.sv'
        else:
            host = 'https://api.dtes.mh.gob.sv'
        url = host + '/fesv/recepcionlote/'
        _logger.info("SIT Url: %s", url)

        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Odoo',
            'Authorization': f"Bearer {self.company_id.sit_token}"
        }

        _logger.info("SIT = requests.request(POST, %s, headers=%s, data=%s)", url, headers,
                     json.dumps(payload_envio_mh))
        # response = requests.request("POST", url, headers=headers, data=payload)
        # _logger.info("SIT response generacion DTE = %s", response)
        # _logger.info("SIT response.text generacion DTE = %s", response.text)

        # MENSAJE = "SIT response = requests.request( POST , " + str(url) + ", headers=" + str(headers) + ", data= " + str(json.dumps(payload))
        # raise UserError(_(MENSAJE))

        try:
            response = requests.post(url, headers=headers, json=payload_envio_mh)
            _logger.info("SIT DTE response =%s", response)
            _logger.info("SIT DTE response =%s", response.status_code)
            _logger.info("SIT DTE response.text =%s", response.text)
        except Exception as error:
            try:
                _logger.info('SIT error= %s, ', error)
                status = error.response.status_code if hasattr(error, 'response') and error.response else 'N/A'
                mensaje = str(error)
                MENSAJE_ERROR = str(status) + ", " + mensaje
            except Exception as e:
                MENSAJE_ERROR = "Error desconocido: " + str(error)
                    # raise UserError(_(error))
                raise UserError("Error al generar DTE lote:\n" + MENSAJE_ERROR)
        try:
            json_response = response.json()
            _logger.info("SIT json_responset =%s", json_response)
            self.write({'sit_json_respuesta': json_response})
        except Exception as e:
            _logger.error('SIT error parseando JSON: %s', e)
            return {
                'estado': 'ERROR',
                'descripcionMsg': 'Respuesta inválida JSON',
                'lotes_firmados': lotes_firmados
            }

        resultado = []
        _logger.info("SIT DTE decodificando respuestas")

        if response.status_code in [400, 401]:
            MENSAJE_ERROR = "ERROR de conexión : " + str(response.text) + ", FACTURAS=" + str(
                lotes_firmados) + ",  PAYLOAD = " + str(json.dumps(payload_envio_mh))
            # raise UserError(_(MENSAJE_ERROR))
            return {
                'estado': response.status.code,
                'descripcionMsg': response.text,
                'lotes_firmados': lotes_firmados
            }

        if json_response['estado'] in ["RECHAZADO", 402]:
            status = json_response['estado']
            ambiente = json_response['ambiente']
            if json_response['ambiente'] == '00':
                ambiente = 'TEST'
            else:
                ambiente = 'PROD'
            clasificaMsg = json_response['clasificaMsg']
            message = json_response['descripcionMsg']
            observaciones = json_response['observaciones']
            MENSAJE_ERROR = "Código de Error..:" + str(
                status) + ", Ambiente:" + ambiente + ", ClasificaciónMsje:" + str(
                clasificaMsg) + ", Descripcion:" + str(message) + ", Detalle:" + str(observaciones) + ", DATA:  " + str(
                json.dumps(payload_envio_mh))
            self.hacienda_estado = status

            # MENSAJE_ERROR = "Código de Error:" + str(status) + ", Ambiente:" + ambiente + ", ClasificaciónMsje:" + str(clasificaMsg) +", Descripcion:" + str(message) +", Detalle:" +  str(observaciones)
            # raise UserError(_(MENSAJE_ERROR))
            return MENSAJE_ERROR

        # if json_response['status'] in [  400, 401, 402 ] :
        #     _logger.info("SIT Error 40X  =%s", json_response['status'])
        #     status=json_response['status']
        #     error=json_response['error']
        #     message=json_response['message']
        #     MENSAJE_ERROR = "Código de Error:" + str(status) + ", Error:" + str(error) +", Detalle:" +  str(message)
        #     raise UserError(_(MENSAJE_ERROR))
        # return json_response
        status = json_response.get('status')
        if status and status in [400, 401, 402]:
            _logger.info("SIT Error 40X  =%s", status)
            error = json_response.get('error', 'Error desconocido')  # Si 'error' no existe, devuelve 'Error desconocido'
            message = json_response.get('message', 'Mensaje no proporcionado')  # Si 'message' no existe, devuelve 'Mensaje no proporcionado'
            MENSAJE_ERROR = "Código de Error:" + str(status) + ", Error:" + str(error) + ", Detalle:" + str(message)
            # raise UserError(_(MENSAJE_ERROR))
            return MENSAJE_ERROR

        if json_response['estado'] in ["RECIBIDO"]: #if json_response['estado'] in ["PROCESADO"]:
            _logger.info("SIT Estado RECIBIDO=%s", json_response)
            return json_response

    def sit_obtener_payload_lote_dte_info(self, ambiente, doc_firmado, nitEmisor, version):
        invoice_info = {}
        invoice_info["ambiente"] = ambiente
        invoice_info["idEnvio"] = self.sit_generar_uuid()
        invoice_info["version"] = 3
        invoice_info["nitEmisor"] = nitEmisor
        invoice_info["documentos"] = doc_firmado

        return invoice_info

    def sit_obtener_payload_lote_dte_firma(self, nitEmisor, llavePrivada, doc_firmado):
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
    def action_post_contingencia(self):
        '''validamos que partner cumple los requisitos basados en el tipo
    de documento de la sequencia del diario selecionado
    FACTURA ELECTRONICAMENTE
    '''
        # NUMERO_FACTURA= super(AccountMove, self).action_post()
        # _logger.info("SIT NUMERO FACTURA =%s", NUMERO_FACTURA)
        _logger.info("SIT Iniciando Validación de Contingencia (account_contingencia_lote)")
        for invoice in self:
            try:
                validation_type = self._compute_validation_type_2()
                _logger.info("SIT action_post validation_type = %s", validation_type)

                ambiente = "00"
                if validation_type == 'homologacioin':
                    ambiente = "00"
                    _logger.info("SIT Factura de Prueba")
                elif validation_type == 'production':
                    _logger.info("SIT Factura de Producción")
                    ambiente = "01"
                # Firmado de documento
                documento_firmado = ""
                
                payload_contingencia = invoice.obtener_payload_contingencia(validation_type)

                _logger.info("SIT Generando DTE conteingencia")
                documento_firmado_contingencia = invoice.firmar_documento(validation_type, payload_contingencia)
                payload_dte_contingencia = invoice.sit_obtener_payload_contingencia_dte_info(documento_firmado_contingencia)

                # self.check_parametros_dte(payload_dte)
                Resultado = invoice.generar_dte_contingencia(validation_type, payload_dte_contingencia, payload_contingencia)
                if Resultado:
                    dat_time  = Resultado['fechaHora']
                    _logger.info("SIT Fecha de procesamiento (%s)%s", type(dat_time), dat_time)
                    fechaHora = datetime.strptime(dat_time, '%d/%m/%Y %H:%M:%S')
                    _logger.info("SIT Fecha de procesamiento (%s)%s", type(fechaHora), fechaHora)
                    _logger.info("SIT Fecha de sit_fechaHora (%s)%s", type(invoice.sit_fechaHora), invoice.sit_fechaHora)
                    MENSAJE = "Resultado = " + str(Resultado)
                    invoice.sit_estado = Resultado['estado']
                    invoice.hacienda_estado = Resultado['estado']
                    invoice.sit_fechaHora = fechaHora
                    invoice.sit_mensaje = Resultado['mensaje']
                    invoice.sit_selloRecibido = Resultado['selloRecibido']
                    invoice.sit_observaciones = Resultado['observaciones']
                    invoice.state = "posted" if Resultado['estado'] == 'RECIBIDO' else 'draft',



                    try:
                        tz = pytz.timezone('America/El_Salvador') #Obtener zona horaria de El Salvador
                        now_sv = datetime.now(tz).replace(tzinfo=None)  # Convertir a naive
                        invoice.fechaHoraTransmision = now_sv
                    except pytz.UnknownTimeZoneError:
                        raise UserError("No se pudo determinar la zona horaria 'America/El_Salvador'. Verifique su configuración.")
                    except Exception as e:
                        raise UserError(f"Ocurrió un error al asignar la fecha y hora actual: {str(e)}")

                    #JSON
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

                    #Respuesta json
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
            except Exception as e:
                error_msg = traceback.format_exc()
                _logger.exception("SIT Error durante el _post para invoice ID %s: %s", invoice.id, str(e))
                invoice.write({
                    'error_log': error_msg,
                    'state': 'draft',
                })
                raise e
                    # raise UserError(_(MENSAJE))

    def _compute_validation_type_2(self):
        for rec in self:
                validation_type = self.env["res.company"]._get_environment_type()
                if validation_type == "homologation":
                    try:
                        rec.company_id.get_key_and_certificate(validation_type)
                    except Exception:
                        validation_type = False
                return validation_type

# FIMAR FIMAR FIRMAR =====================================================================================================    
    def firmar_documento(self, enviroment_type, payload):
        _logger.info("SIT  Firmando de documento")
        _logger.info("SIT Documento a FIRMAR =%s", payload)
        if enviroment_type == 'homologation':
            ambiente = "00"
        else:
            ambiente = "01"
        # host = 'http://service-it.com.ar:8113'
        # host = 'http://svfe-api-firmador:8113'
        #host = 'http://192.168.2.25:8113'
        #url = host + '/firmardocumento/'
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
            # raise UserError(_(MENSAJE_ERROR))
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
            # raise UserError(_(MENSAJE_ERROR))
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

    def obtener_payload_contingencia(self, enviroment_type):
        _logger.info("SIT  Obteniendo payload")
        if enviroment_type == 'homologation': 
            ambiente = "00"
        else:
            ambiente = "01"
        
        self.check_parametros_contingencia()
        invoice_info = self.sit__contingencia_base_map_invoice_info()
        _logger.info("SIT invoice_info CONTINGENCIA = %s", invoice_info)
        



        _logger.info("SIT payload_data =%s", invoice_info)
        return invoice_info

    def generar_dte_contingencia(self, enviroment_type, payload, payload_original):
        _logger.info("SIT  Generando DTE___contingencia")
        if enviroment_type == 'homologation': 
            host = 'https://apitest.dtes.mh.gob.sv' 
        else:
            host = 'https://api.dtes.mh.gob.sv'
        url = host + '/fesv/contingencia'

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

        _logger.info("SIT json =%s", payload)
        _logger.info("SIT contingencia  = requests.request(POST, %s, headers=%s, data=%s)", url, headers, payload)

        try:
            #response = requests.request("POST", url, headers=headers, data=json.dumps(payload))
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            _logger.info("SIT DTE contingencia response =%s", response)
            _logger.info("SIT DTE contingencia response status=%s", response.status_code)
            _logger.info("SIT DTE contingencia response.text =%s", response.text)
        except Exception as e:
            error = str(e)
            _logger.info('SIT error= %s, ', error)       
            if "error" in error or "" in error:
                MENSAJE_ERROR = str(error['status']) + ", " + str(error['error']) +", " +  str(error['message'])  
                raise UserError(_(MENSAJE_ERROR))
            else:
                raise UserError(_(error))
        resultado = []    
        _logger.info("SIT DTE decodificando respuestas")
        if response.status_code in [  401 ] :
            MENSAJE_ERROR = "ERROR de conexión : " + str(response )   
            raise UserError(_(MENSAJE_ERROR))


        json_response = response.json()
        _logger.info("SIT json_responset =%s", json_response)
        if json_response['estado'] in [  "RECHAZADO", 402 ] :
            status=json_response['estado']
            fechaHora=json_response['fechaHora']
            mensaje=json_response['mensaje']
            selloRecibido=json_response['selloRecibido']
            observaciones=json_response['observaciones']


            MENSAJE_ERROR = "Código de Error..:" + str(status) + ", fechaHora:" + fechaHora + ", mensaje:" + str(mensaje) +", selloRecibido:" + str(selloRecibido) +", observaciones:" +  str(observaciones) +", DATA:  " +  str(json.dumps(payload_original))  
            self.hacienda_estado= status

            # MENSAJE_ERROR = "Código de Error:" + str(status) + ", Ambiente:" + ambiente + ", ClasificaciónMsje:" + str(clasificaMsg) +", Descripcion:" + str(message) +", Detalle:" +  str(observaciones)  
            raise UserError(_(MENSAJE_ERROR))

            
        # if json_response['status'] in [  400, 401, 402 ] :
        #     _logger.info("SIT Error 40X  =%s", json_response['status'])
        #     status=json_response['status']
        #     error=json_response['error']
        #     message=json_response['message']
        #     MENSAJE_ERROR = "Código de Error:" + str(status) + ", Error:" + str(error) +", Detalle:" +  str(message)  
        #     raise UserError(_(MENSAJE_ERROR))
        # return json_response
        if response.status_code in [ 400 ]:
            _logger.info("SIT Contingencia Error 40X  =%s", response.status_code)
            message = json_response.get('mensaje', 'Mensaje no proporcionado')  # Si 'message' no existe, devuelve 'Mensaje no proporcionado'
            estado =  json_response.get('estado', 'Estado no proporcionado')
            MENSAJE_ERROR = "Código de Error:" + str(response.status_code)  + ", Detalle:" + str(message) + ", DATA REQUEST = " + str(json.dumps(payload))
            raise UserError(_(MENSAJE_ERROR))

        status = json_response.get('status')
        if status and status in [400, 401, 402]:
            _logger.info("SIT Error 40X  =%s", status)
            error = json_response.get('error', 'Error desconocido')  # Si 'error' no existe, devuelve 'Error desconocido'
            message = json_response.get('message', 'Mensaje no proporcionado')  # Si 'message' no existe, devuelve 'Mensaje no proporcionado'
            MENSAJE_ERROR = "Código de Error:" + str(status) + ", Error:" + str(error) + ", Detalle:" + str(message)
            raise UserError(_(MENSAJE_ERROR))
        _logger.info("SIT  json_response('estado) =%s", json_response['estado'])
        if json_response['estado'] in [  "RECIBIDO" ] :
            self.write({'contingencia_recibida_mh': True})
            return json_response

    def _autenticar(self,user,pwd,):
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


    



    def check_parametros_contingencia(self):
        # Tipo de documento: iva/nit(campo fax) = 1, dui(campo dui) = 4, otro = 5, pasaporte = 2, extranjero = 3
        if not self.company_id:
            raise UserError(_('El Nombre de la compañía no definido'))        
        if not self.invoice_user_id.partner_id.name: #if not self.company_id.partner_id.user_id.partner_id.name:
            raise UserError(_('El Nombre de Responsable no definido'))        
        if not self.invoice_user_id.partner_id.vat and not self.invoice_user_id.partner_id.dui:
            raise UserError(_('El Número de Documento no definido')) # raise UserError(_('El Número de RFC no definido'))
        if not self.company_id.tipoEstablecimiento.codigo:
            raise UserError(_('El tipoEstablecimiento no definido'))        
        if not self.sit_tipo_contingencia:
            raise UserError(_('El tipoContingencia no definido'))

        _logger.info("Tipo contingencia: %s | Constante motivo: %s | Motivo contingencia: %s", self.sit_tipo_contingencia.codigo, constants.MOT_CONTIN_OTRO, self.sit_tipo_contingencia_otro)
        if self.sit_tipo_contingencia and self.sit_tipo_contingencia.codigo == constants.MOT_CONTIN_OTRO:
            if not self.sit_tipo_contingencia_otro or not self.sit_tipo_contingencia_otro.strip():
                raise UserError(_('El motivoContingencia no definido'))
        if not self.sit_fFin_hFin:
            raise UserError(_('El campo Fecha de Fin de Contingencia - Hacienda (sit_fFin_hFin) no definido'))        






    def check_parametros_firmado(self):

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
        # if not self.partner_id.tipoEstablecimiento:
            # raise UserError(_('El receptor no tiene TIPO DE ESTABLECIMIENTO configurado.'))
        if not self.partner_id.state_id:
            raise UserError(_('El receptor no tiene DEPARTAMENTO configurado.'))
        if not self.partner_id.munic_id:
            raise UserError(_('El receptor no tiene MUNICIPIO configurado.'))
        if not self.partner_id.email:
            raise UserError(_('El receptor no tiene CORREO configurado.'))
        if not self.invoice_line_ids:
            raise UserError(_('La factura no tiene LINEAS DE PRODUCTOS asociada.'))

                


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

    # Generar secuencia para contingencia
    @api.model
    def _generate_contingencia_name(self, journal=None, actualizar_secuencia=False):
        journal = journal or self.journal_id

        version_contingencia = config_utils.get_config_value(
            self.env, 'version_contingencia', journal.company_id.id
        )
        _logger.info("Version contingencia: %s | Compañia: %s", version_contingencia, journal.company_id)

        if version_contingencia is None:
            raise UserError(_("Debe definir la versión de la contingencia."))

        if not journal.sit_codestable:
            raise UserError(_("Configure Código de Establecimiento en diario '%s'.") % journal.name)

        version_str = str(version_contingencia).zfill(2)
        if not version_str.strip():
            raise UserError("La versión de contingencia no puede estar vacía.")
        estable = journal.sit_codestable
        seq_code = 'CONT'

        # Buscar el último nombre generado que coincida con el patrón
        domain = [
            ('journal_id', '=', journal.id),
            ('name', 'like', f'CON-{version_str}-%{estable}-%')  # patrón que usas
        ]
        ultimo = self.search(domain, order='name desc', limit=1)

        if ultimo:
            try:
                ultima_parte = int(ultimo.name.split('-')[-1])
            except ValueError:
                raise UserError(
                    _("No se pudo interpretar el número del último nombre de contingencia: %s") % ultimo.name)
            nuevo_numero = ultima_parte + 1
        else:
            nuevo_numero = 1

        # Obtener secuencia configurada para actualizar el número, no para generar el nombre
        sequence = self.env['ir.sequence'].search([('code', '=', seq_code)], limit=1)
        if not sequence:
            raise UserError(_("No se encontró la secuencia con código '%s'.") % seq_code)

        nuevo_name = f"CON-{version_str}-0000{estable}-{str(nuevo_numero).zfill(15)}"

        # Verificar duplicado
        if self.search_count([('name', '=', nuevo_name), ('journal_id', '=', journal.id)]):
            raise UserError(_("El número de contingencia generado ya existe: %s") % nuevo_name)

        _logger.info("Nombre de contingencia generado manualmente: %s", nuevo_name)

        # Actualizar secuencia (ir.sequence o ir.sequence.date_range)
        if actualizar_secuencia and sequence:
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
                    _logger.info("Secuencia con date_range '%s' actualizada a %s", seq_code, next_num)
            else:
                if sequence.number_next_actual < next_num:
                    sequence.number_next_actual = next_num
                    _logger.info("Secuencia '%s' actualizada a %s", seq_code, next_num)

        return nuevo_name
