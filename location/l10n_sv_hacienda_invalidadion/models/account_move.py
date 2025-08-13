##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from ..common_utils.utils import config_utils
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from odoo.tools import float_repr
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
from datetime import datetime, timedelta, time  # Importando directamente las funciones/clases
import pytz
# from datetime import datetime
from pytz import timezone, UTC

_logger = logging.getLogger(__name__)

EXTRA_ADDONS = r'C:\Users\admin\Documents\GitHub\fe\location\mnt\extra-addons\src'
#EXTRA_ADDONS = r'C:\Users\INCOE\Documents\GitHub\fe\location\mnt\extra-addons\src'


class AccountMove(models.Model):
    _inherit = "account.move"


    state = fields.Selection(selection_add=[('annulment', 'Anulado')],ondelete={'annulment': 'cascade'})



    hacienda_estado_anulacion = fields.Char(
        copy=False,
        string="Estado Anulación",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )    
    hacienda_codigoGeneracion_anulacion = fields.Char(
        copy=False,
        string="Codigo de Generación",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )       
    hacienda_selloRecibido_anulacion = fields.Char(
        copy=False,
        string="Sello Recibido",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )       
    hacienda_fhProcesamiento_anulacion = fields.Datetime(
        copy=False,
        string="Fecha de Procesamiento - Hacienda",  
        help="Asignación de Fecha de procesamiento de anulación",
        readonly=True,
          )
    hacienda_codigoMsg_anulacion = fields.Char(
        copy=False,
        string="Codigo de Mensaje",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    hacienda_descripcionMsg_anulacion = fields.Char(
        copy=False,
        string="Descripción",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    hacienda_observaciones_anulacion = fields.Char(
        copy=False,
        string="Observaciones",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    sit_qr_hacienda_anulacion = fields.Binary(
        string="QR Hacienda", 
        copy=False,
        readonly=True,
        )

    sit_documento_firmado_invalidacion=fields.Text(
        string="Documento Firmado",
        copy=False,
        readonly=True,
         )


    # CAMPOS INVALIDACION 
    sit_invalidar = fields.Boolean('Invalidar ?',  copy=False,   default=False)
    sit_codigoGeneracion_invalidacion = fields.Char(string="codigoGeneracion" , copy=False, store=True)
    sit_fec_hor_Anula = fields.Datetime(string="Fecha de Anulación" , copy=False)
    temp_fecha_anulacion = fields.Date(string="Fecha de Anulación")
    
    # sit_codigoGeneracionR = fields.Char(string="codigoGeneracion que Reemplaza" , copy=False, )
    sit_codigoGeneracionR = fields.Char(related="sit_factura_a_reemplazar.hacienda_codigoGeneracion_identificacion", string="codigoGeneracion que Reemplaza" , copy=False, )
    sit_tipoAnulacion = fields.Selection(
        selection='_get_tipo_Anulacion_selection', string="Tipo de invalidacion")
    sit_motivoAnulacion = fields.Char(string="Motivo de invalidacion" , copy=False, )
    sit_nombreResponsable = fields.Many2one('res.partner', string="Nombre de la persona responsable de invalidar el DTE", copy=False)
    
# fields.Char(string="Nombre de la persona responsable de invalidar el DTE" , copy=False, )
    sit_tipDocResponsable = fields.Char(string="Tipo documento de identificación" , copy=False, default="13" )
    # sit_numDocResponsable = fields.Char(related="sit_nombreResponsable.dui", string="Número de documento de identificación" , copy=False, )
    sit_numDocResponsable = fields.Char(related="sit_nombreResponsable.vat", string="Número de documento de identificación" , copy=False, )
    # sit_tipo_contingencia_valores = fields.Char(related="sit_tipo_contingencia.valores", string="Tipo de contingiancia(nombre)")

    
    sit_nombreSolicita = fields.Many2one('res.partner', string="Nombre de la persona que solicita invalidar el DTE", copy=False)
    # sit_nombreSolicita = fields.Char(string="Nombre de la persona que solicita invalidar el DTE" , copy=False, )
    sit_tipDocSolicita = fields.Char(string="Tipo documento de identificación solicitante" , copy=False, default="13")
    # sit_numDocSolicita = fields.Char(string="Número de documento de identificación solicitante." , copy=False, )
    # sit_numDocSolicita = fields.Char(related="sit_nombreSolicita.dui", string="Número de documento de identificación solicitante" , copy=False, )
    sit_numDocSolicita = fields.Char(related="sit_nombreSolicita.vat", string="Número de documento de identificación solicitante" , copy=False, )
    sit_factura_a_reemplazar = fields.Many2one('account.move', string="Documento que reeemplaza", copy=False)
    sit_evento_invalidacion = fields.Many2one('account.move.invalidation', string="Documento que invalida el dte", copy=False)

    @api.model
    def _get_tipo_Anulacion_selection(self):
        return [
            ('1', '1-Error en la Información del Documento Tributario Electrónico a invalidar.'),
            ('2', '2-Rescindir de la operación realizada.'),
            ('3', '3-Otro'),
        ]

#---------------------------------------------------------------------------------------------
# ANULAR FACTURA
#---------------------------------------------------------------------------------------------

    def button_anulacion(self):
        raise UserError("Boton de Prueba")

    def button_anul(self):
        raise UserError("Boton de Prueba")

    def action_button_anulacion(self):
        _logger.info("SIT [INICIO] action_button_anulacion para facturas: %s", self.ids)
        # Verificamos si estamos en una factura que puede ser anulada
        if self.state != 'posted' and self.hacienda_estado != 'PROCESADO':
            raise UserError("Solo se pueden anular facturas que ya han sido publicadas.")

        if self.sit_evento_invalidacion and self.sit_evento_invalidacion.hacienda_selloRecibido_anulacion and self.sit_evento_invalidacion.invalidacion_recibida_mh:
            raise UserError("Este DTE ya ha sido invalidado por Hacienda. No es posible repetir la anulación.")

        EL_SALVADOR_TZ = timezone('America/El_Salvador')

        _logger.info("SIT Fecha invalidacion= %s", self.temp_fecha_anulacion)
        for invoice in self:
            # Primero creamos el registro en account.move.invalidation
            _logger.info("SIT Creando el registro de invalidación para la factura: %s", invoice.name)

            # Si no se seleccionó una fecha, usar la fecha actual
            anulacion_fecha = invoice.temp_fecha_anulacion or datetime.now(EL_SALVADOR_TZ).date()
            _logger.info("SIT Fecha de anulación utilizada: %s", anulacion_fecha)

            # Obtener hora actual en El Salvador
            hora_actual = datetime.now(EL_SALVADOR_TZ).time().replace(microsecond=0)
            fecha_hora_local = datetime.combine(anulacion_fecha, hora_actual)
            fecha_hora_local = EL_SALVADOR_TZ.localize(fecha_hora_local)

            # Convertir a UTC
            utc_dt = fecha_hora_local.astimezone(UTC).replace(tzinfo=None)
            _logger.info("SIT Fecha local + hora actual = UTC: %s", utc_dt)

            try:
                # Buscar si ya existe el registro de invalidación
                existing = self.env['account.move.invalidation'].search([
                    ('sit_factura_a_reemplazar', '=', invoice.id)
                ], limit=1)

                # Crear el registro de invalidación
                invalidation = {
                    'sit_factura_a_reemplazar': invoice.id,  # Factura que estamos anulando
                    'sit_fec_hor_Anula': utc_dt,  # Fecha de anulación
                    'sit_codigoGeneracionR': invoice.sit_codigoGeneracionR,
                    'sit_tipoAnulacion': invoice.sit_tipoAnulacion or '1',  # Tipo de anulación
                    'sit_motivoAnulacion': invoice.sit_motivoAnulacion or 'Error en la información',
                }

                _logger.info("SIT Diccionario para crear invalidación: %s", invalidation)

                if existing:
                    _logger.info("SIT Registro existente encontrado: %s, actualizando", existing.id)
                    existing.write(invalidation)
                    invalidation = existing
                else:
                    # invalidation.update({'sit_factura_a_reemplazar': invoice.id})
                    invalidation = self.env['account.move.invalidation'].create(invalidation)
                    _logger.info("SIT Registro de invalidación creado con ID: %s", invalidation.id)
                    self.env.cr.commit()

                # Continuar con el flujo para ambos casos
                invoice.write({
                    'state': 'cancel',
                    'sit_evento_invalidacion': invalidation.id
                })
                _logger.info("SIT Estado de factura actualizado a cancelado: %s", invoice.name)

                resultado = invalidation.button_anul()
                _logger.info("SIT Método button_anul ejecutado correctamente para ID: %s", invalidation.id)
                if not resultado.get('exito'):
                    # Retornamos la acción para mostrar notificación sin error popup
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': 'Error',
                            'message': resultado.get('mensaje'),
                            'type': 'warning',
                            'sticky': False,
                        }
                    }
                if resultado.get('notificar'):
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': 'Invalidación Exitosa',
                            'message': 'Se invalidó el DTE. El sello de Hacienda fue recibido correctamente.',
                            'type': 'success',
                            'sticky': False,
                        }
                    }
                _logger.info("SIT Método button_anul ejecutado correctamente para ID: %s", invalidation.id)

            except Exception as e:
                _logger.exception("SIT Error posterior al crear la invalidación: %s", e)

        return True

    def _compute_validation_type_2(self):
        for rec in self:
                validation_type = self.env["res.company"]._get_environment_type()
                _logger.info("SIT _compute_validation_type_2 =%s ", validation_type)
                # if validation_type == "homologation":
                    # try:
                        # rec.company_id.get_key_and_certificate(validation_type)
                    # except Exception:
                        # validation_type = False
                return validation_type
                

    # FIMAR FIMAR FIRMAR =====================================================================================================    
    def firmar_documento_anu(self, enviroment_type, payload):
        _logger.info("SIT  Firmando de documento")
        _logger.info("SIT Documento a FIRMAR =%s", payload)
        if enviroment_type == 'homologation': 
            ambiente = "00"
        else:
            ambiente = "01"
        # host = 'http://service-it.com.ar:8113'
        #host = 'http://svfe-api-firmador:8113'
        #host = "http://192.168.2.25:8113"
        #url = host + '/firmardocumento/'
        url = config_utils.get_config_value(self.env, 'url_firma', self.company_id.id)
        if not url:
            _logger.error("SIT | No se encontró 'url_firma' en la configuración para la compañía ID %s", self.company_id.id)
            raise UserError(_("La URL de firma no está configurada en la empresa."))
        headers = {
            'Content-Type': 'application/json'
            }
        try:
            MENSAJE = "SIT POST, " + str(url) + ", headers=" + str(headers) + ", data=" + str(json.dumps(payload))
            _logger.info("SIT A FIRMAR = %s", MENSAJE)
            response = requests.request("POST", url, headers=headers, data=json.dumps(payload))
            # _logger.info("SIT firmar_documento response =%s", response.text)
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
        if json_response['status'] in [  400, 401, 402 ] :
            _logger.info("SIT Error 40X  =%s", json_response['status'])
            status=json_response['status']
            error=json_response['error']
            message=json_response['message']
            MENSAJE_ERROR = "Código de Error:" + str(status) + ", Error:" + str(error) +", Detalle:" +  str(message)  
            raise UserError(_(MENSAJE_ERROR))
        if json_response['status'] in [ 'ERROR', 401, 402 ] :
            _logger.info("SIT Error 40X  =%s", json_response['status'])
            status=json_response['status']
            body=json_response['body']
            codigo=body['codigo']
            message=body['mensaje']
            resultado.append(status)
            resultado.append(codigo)
            resultado.append(message)
            MENSAJE_ERROR = "Código de Error:" + str(status) + ", Codigo:" + str(codigo) +", Detalle:" +  str(message)  
            raise UserError(_(MENSAJE_ERROR))        
        elif json_response['status'] == 'OK':
            status=json_response['status']
            body=json_response['body']
            resultado.append(status)
            resultado.append(body)
            return body


    def obtener_payload_anulacion(self, enviroment_type, sit_tipo_documento):
        _logger.info("SIT  Obteniendo payload")
        if enviroment_type == 'homologation': 
            ambiente = "00"
        else:
            ambiente = "01"
        invoice_info = self.sit_anulacion_base_map_invoice_info()
        _logger.info("SIT invoice_info FINVALIDACION = %s", invoice_info)
        self.check_parametros_firmado_anu()


        _logger.info("SIT payload_data =%s", invoice_info)
        return invoice_info


    def generar_dte_invalidacion(self, enviroment_type, payload, payload_original):
        _logger.info("SIT  Generando DTE Invalidacion =%s", payload)
        if enviroment_type == 'homologation': 
            #host = 'https://apitest.dtes.mh.gob.sv'
            host = "https://api.dtes.mh.gob.sv"
        else:
            host = "https://api.dtes.mh.gob.sv"
        url = host + '/fesv/anulardte'
        agente = self.company_id.sit_token_user
        authorization = self.company_id.sit_token

        headers = {
         'Content-Type': 'application/json', 
         'User-Agent': 'Odoo', #agente,
         'Authorization': f"Bearer {self.company_id.sit_token}" #authorization
        }
        try:
            response = requests.request("POST", url, headers=headers, data=json.dumps(payload))
            _logger.info("SIT generar_dte_invalidacion DTE response =%s", response)
            _logger.info("SIT generar_dte_invalidacion DTE response =%s", response.status_code)
            _logger.info("SIT generar_dte_invalidacion DTE response.text =%s", response.text)
        except Exception as e:
            error = str(e)
            _logger.info('SIT error= %s, ', error)       
            if "error" in error or "" in error:
                MENSAJE_ERROR = str(error['status']) + ", " + str(error['error']) +", " +  str(error['message'])  
                raise UserError(_(MENSAJE_ERROR))
            else:
                raise UserError(_(error))
        resultado = []    
        _logger.info("SIT generar_dte_invalidacion DTE decodificando respuestas invalidacion")
        # status = json_response.get('status')

        if response.status_code in [  400, 401 ] :
            MENSAJE_ERROR = "ERROR de conexión : " + str(response.text )   + " ((( " +str(json.dumps(payload_original))  + " )))"
            raise UserError(_(MENSAJE_ERROR))

        json_response = response.json()
        _logger.info("SIT json_response =%s", json_response)
        if json_response['estado'] in [  "RECHAZADO", 402 ] :
            status=json_response['estado']
            ambiente=json_response['ambiente']
            if json_response['ambiente'] == '00':
                ambiente = 'TEST'
            else:
                ambiente = 'PROD'
            clasificaMsg=json_response['clasificaMsg']
            message=json_response['descripcionMsg']
            observaciones=json_response['observaciones']
            MENSAJE_ERROR = "Código de Error..:" + str(status) + ", Ambiente:" + ambiente + ", ClasificaciónMsje:" + str(clasificaMsg) +", Descripcion:" + str(message) +", Detalle:" +  str(observaciones) +", DATA:  " +  str(json.dumps(payload_original))  
            self.hacienda_estado= status

            # MENSAJE_ERROR = "Código de Error:" + str(status) + ", Ambiente:" + ambiente + ", ClasificaciónMsje:" + str(clasificaMsg) +", Descripcion:" + str(message) +", Detalle:" +  str(observaciones)  
            raise UserError(_(MENSAJE_ERROR))
        status = json_response.get('status')
        if status and status in [400, 401, 402]:
            _logger.info("SIT Error 40X  =%s", status)
            error = json_response.get('error', 'Error desconocido')  # Si 'error' no existe, devuelve 'Error desconocido'
            message = json_response.get('message', 'Mensaje no proporcionado')  # Si 'message' no existe, devuelve 'Mensaje no proporcionado'
            MENSAJE_ERROR = "Código de Error:" + str(status) + ", Error:" + str(error) + ", Detalle:" + str(message)
            raise UserError(_(MENSAJE_ERROR))
        if json_response['estado'] in [  "PROCESADO" ] :

            return json_response
    

    def _autenticar(self,
            user,
            pwd,
            ):
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
        _logger.info("SIT generando qr___ = %s", self)
        # enviroment_type = self._get_environment_type()
        # enviroment_type = self.env["res.company"]._get_environment_type()
        enviroment_type =  'homologation'
        if enviroment_type == 'homologation': 
            host = 'https://admin.factura.gob.sv'

        else:
            host = 'https://admin.factura.gob.sv'

        # https://admin.factura.gob.sv/consultaPublica?ambiente=00&codGen=00000000-0000-00000000-000000000000&fechaEmi=2022-05-01 
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
        import os

        if os.name == 'nt':  # Windows
            os.chdir(EXTRA_ADDONS)
        else:  # Linux/Unix
            os.chdir('/mnt/extra-addons/src')
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
        _logger.info("SIT generando qr xxx= %s", self)
        enviroment_type =  'homologation'        
        if enviroment_type == 'homologation': 
            host = 'https://admin.factura.gob.sv'
            ambiente = "00"
        else:
            host = 'https://admin.factura.gob.sv'
            ambiente = "01"
        texto_codigo_qr = host + "/consultaPublica?ambiente=" + str(ambiente) + "&codGen=" + str(self.hacienda_codigoGeneracion_identificacion) + "&fechaEmi=" + str(self.fecha_facturacion_hacienda)
        _logger.info("SIT generando qr xxx texto_codigo_qr= %s", texto_codigo_qr)

        codigo_qr = qrcode.QRCode(
            version=1,  # Versión del código QR (ajústala según tus necesidades)
            error_correction=qrcode.constants.ERROR_CORRECT_L,  # Nivel de corrección de errores
            box_size=10,  # Tamaño de los cuadros del código QR
            border=1,  # Ancho del borde del código QR
        )
        codigo_qr.add_data(texto_codigo_qr)
        import os

        if os.name == 'nt':  # Windows
            os.chdir(EXTRA_ADDONS)
        else:  # Linux/Unix
            os.chdir('/mnt/extra-addons/src')
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

    def check_parametros_invalidacion(self):
        if not self.name:
             raise UserError(_('El Número de control no definido'))      
        if not self.company_id.tipoEstablecimiento.codigo:
            raise UserError(_('El tipoEstablecimiento no definido'))        
 

        if not self.sit_tipoAnulacion or self.sit_tipoAnulacion == False:
            raise UserError(_('El tipoAnulacion no definido'))        
       

    def check_parametros_firmado_anu(self):
        if not self.journal_id.sit_tipo_documento.codigo:
            raise UserError(_('El Tipo de  DTE no definido.'))
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
        
        if not self.journal_id.sit_tipo_documento.codigo:
            raise UserError(_('El Tipo de DTE no definido.'))
        if not self.name:
            raise UserError(_('El Número de control no definido'))
        # Validaciones para el emisor (comunes para todos los tipos de DTE)
        # ...

        # Validaciones específicas según el tipo de DTE
        tipo_dte = self.journal_id.sit_tipo_documento.codigo

        if tipo_dte == '01':
            # Solo validar el nombre para DTE tipo 01
            if not self.partner_id.name:
                raise UserError(_('El receptor no tiene NOMBRE configurado para facturas tipo 01.'))
        elif tipo_dte == '03':
            # Validaciones completas para DTE tipo 03
            if not self.partner_id.vat and self.partner_id.is_company:
                _logger.info("SIT, es compañia se requiere NIT")
                _logger.info("SIT, partner campos requeridos account=%s", self.partner_id)
                raise UserError(_('El receptor no tiene NIT configurado.'))
            if not self.partner_id.nrc and self.partner_id.is_company:
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

        # Validaciones comunes para cualquier tipo de DTE
        if not self.invoice_line_ids:
            raise UserError(_('La factura no tiene LINEAS DE PRODUCTOS asociada.'))

                

    def check_parametros_dte_invalidacion(self, generacion_dte):
        if not generacion_dte["ambiente"]:
            ERROR = 'El ambiente  no está definido.'
            raise UserError(_(ERROR))
        if not generacion_dte["idEnvio"]:
            ERROR = 'El IDENVIO  no está definido.'
            raise UserError(_(ERROR))        
        if not generacion_dte["documento"]:
            ERROR = 'El DOCUMENTO  no está presente.'
            raise UserError(_(ERROR))
        if not generacion_dte["version"]:
            ERROR = 'La version dte no está definida.'
            raise UserError(_(ERROR))
