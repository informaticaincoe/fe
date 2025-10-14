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

#EXTRA_ADDONS = r'C:\Users\Administrador\Documents\fe\location\mnt\src'
#EXTRA_ADDONS = r'C:\Users\INCOE\Documents\GitHub\fe\location\mnt\extra-addons\src'

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
EXTRA_ADDONS = os.path.join(PROJECT_ROOT, "mnt", "extra-addons", "src")

try:
    from odoo.addons.common_utils.utils import constants
    from odoo.addons.common_utils.utils import config_utils
    _logger.info("SIT Modulo config_utils [hacienda invalidacion]")
except ImportError as e:
    _logger.error(f"Error al importar 'constants': {e}")
    constants = None
    config_utils = None

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
    temp_fecha_anulacion = fields.Date(string="Fecha de Anulación Temp")
    
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
    def action_button_anulacion(self):
        _logger.info("SIT [INICIO] action_button_anulacion para facturas: %s, clase de documento: %s", self.ids, self.clase_documento_id)

        resultado_final = {
            "exito": False,
            "mensaje": "",
            "resultado_mh": None,
        }

        es_compra = (self.move_type == "in_invoice" and not self.journal_id.sit_tipo_documento)

        if not (es_compra and self.company_id and self.company_id.sit_facturacion):
            raise UserError("Solo se pueden invalidar documentos electrónicos.")

        # Si no se ha guardado el evento de invalidación (o si no se ha asignado en el formulario):
        _logger.info("SIT-Invaldiacion factura a reemplazar: %s", self.sit_factura_a_reemplazar)
        if not self.sit_factura_a_reemplazar:
            raise UserError("Debe seleccionar el documento a invalidar antes de continuar.")

        ambiente_test = False
        if not es_compra:
            if config_utils:
                ambiente_test = config_utils._compute_validation_type_2(self.env, self.company_id)
                _logger.info("SIT Tipo de entorno invalidacion[Ambiente]: %s", ambiente_test)

            # Verificamos si estamos en una factura que puede ser anulada
            if self.state != 'posted' and self.hacienda_estado != 'PROCESADO':
                raise UserError("Solo se pueden invalidar facturas que ya han sido publicadas.")

            _logger.info("SIT Tipo invalidacion: %s, tipo de documento: %s, cod generacion: %s, codGeneracion reemplazo: %s",
                         self.sit_tipoAnulacion, self.journal_id.sit_tipo_documento.codigo, self.hacienda_codigoGeneracion_identificacion, self.sit_factura_a_reemplazar.hacienda_codigoGeneracion_identificacion)
            if (self.journal_id.sit_tipo_documento and self.journal_id.sit_tipo_documento.codigo != constants.COD_DTE_NC
                    and self.sit_tipoAnulacion in ('1', '3') and self.hacienda_codigoGeneracion_identificacion ==  self.sit_factura_a_reemplazar.hacienda_codigoGeneracion_identificacion):
                raise UserError(
                    _("Para invalidar este documento, es necesario generar un documento de reemplazo que cuente con el sello de recepción correspondiente."))

            if self.sit_evento_invalidacion and self.sit_evento_invalidacion.hacienda_selloRecibido_anulacion and self.sit_evento_invalidacion.invalidacion_recibida_mh:
                raise UserError("Este DTE ya ha sido invalidado por Hacienda. No es posible repetir la anulación.")

            if ambiente_test and self.sit_evento_invalidacion and self.sit_evento_invalidacion.state == "annulment" and str(self.sit_evento_invalidacion.hacienda_estado_anulacion).lower() == "procesado":
                raise UserError("Este DTE ya ha sido invalidado. No es posible repetir la anulación.")

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
                    'sit_tipoAnulacion': invoice.sit_tipoAnulacion or '1' if not es_compra else None,  # Tipo de anulación
                    'sit_motivoAnulacion': invoice.sit_motivoAnulacion or 'Error en la información' if not es_compra else 'Se registro la compra como anulada',
                    'company_id': invoice.company_id.id,
                }
                if es_compra:
                    invalidation['state'] = 'annulment'
                    invalidation['sit_nombreSolicita'] = invoice.partner_id.id
                    invalidation['sit_nombreResponsable'] = invoice.partner_id.id
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
                    'sit_evento_invalidacion': invalidation.id
                })
                _logger.info("SIT Estado de factura actualizado a cancelado: %s", invoice.name)

                resultado = None
                if not es_compra:
                    resultado = invalidation.button_anul()
                else:
                    resultado_final["mensaje"] = "Se registro la anulación de la compra."
                    resultado_final["exito"] = True
                    resultado_final["notificar"] = True
                    resultado = resultado_final
                _logger.info("SIT Método button_anul ejecutado correctamente para ID: %s", invalidation.id)

                if resultado.get('exito'):
                    invoice.write({
                        'state': 'cancel',
                    })
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
                            'message': (
                                'Se invalidó el DTE. El sello de Hacienda fue recibido correctamente.'
                                if not ambiente_test else
                                'Se invalidó el DTE correctamente.'
                            ),
                            'type': 'success',
                            'sticky': False,
                        }
                    }
                _logger.info("SIT Método button_anul ejecutado correctamente para ID: %s", invalidation.id)

            except Exception as e:
                _logger.exception("SIT Error posterior al crear la invalidación: %s", e)

        return True

    def _compute_validation_type_2(self):
        validation_type = False
        for rec in self:
            if not (rec.company_id and rec.company_id.sit_facturacion):
                _logger.info("SIT _compute_validation_type_2: empresa %s no tiene facturación electrónica, se asigna False", rec.company_id.id if rec.company_id else None)
                continue

            validation_type = self.env["res.company"]._get_environment_type()
            _logger.info("SIT _compute_validation_type_2 =%s ", validation_type)
                    # if validation_type == "homologation":
                    # try:
                        # rec.company_id.get_key_and_certificate(validation_type)
                    # except Exception:
                        # validation_type = False
        return validation_type

    def _autenticar(self, user, pwd):
        _logger.info("SIT self = %s", self)

        # 1 Validar si la empresa tiene activa la facturación electrónica
        if not (self.company_id and self.company_id.sit_facturacion):
            _logger.info("SIT No aplica facturación electrónica. Se omite autenticación.")
            return False

        # 2 Validar si es una compra normal (sin sujeto excluido)
        if self.move_type in (constants.IN_INVOICE, constants.IN_REFUND):
            tipo_doc = self.journal_id.sit_tipo_documento
            if not tipo_doc or tipo_doc.codigo != constants.COD_DTE_FSE:
                _logger.info("SIT: Documento de compra normal (sin sujeto excluido). Se omite autenticación para DTE.")
                return False

        _logger.info("SIT self = %s, %s", user, pwd)

        # 3 Obtener entorno (homologación o producción)
        enviroment_type = self._get_environment_type()
        _logger.info("SIT Modo = %s", enviroment_type)

        url = None
        # 4 Determinar URL según el entorno
        if enviroment_type == 'homologation':
            url = config_utils.get_config_value(self.env, 'autenticar_test', self.company_id.id) if config_utils else 'https://apitest.dtes.mh.gob.sv/seguridad/auth'
        else:
            url = config_utils.get_config_value(self.env, 'autenticar_prod', self.company_id.id) if config_utils else 'https://api.dtes.mh.gob.sv/seguridad/auth'
        # url = host + '/seguridad/auth'

        # 5 Validar parámetros de Hacienda
        self.check_hacienda_values()

        # 6 Realizar autenticación HTTP
        try:
            payload = "user=" + user + "&pwd=" + pwd
            # 'user=06140902221032&pwd=D%237k9r%402mP1!b'
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            response = requests.request("POST", url, headers=headers, data=payload)
            _logger.info("SIT response = %s", response.text)

        except Exception as e:
            error = str(e)
            _logger.info('SIT error= %s, ', error)
            if "error" in error or "" in error:
                MENSAJE_ERROR = str(error['status']) + ", " + str(error['error']) + ", " + str(error['message'])
                raise UserError(_(MENSAJE_ERROR))
            else:
                raise UserError(_(error))

        # 7 Parsear respuesta JSON
        resultado = []
        json_response = response.json()
        _logger.info("SIT Autenticación exitosa. Respuesta JSON: %s", json_response)
        return json_response

    def _generar_qr(self, ambiente, codGen, fechaEmi):
        _logger.info("SIT generando qr___ = %s", self)

        # 1 Validar si aplica facturación electrónica
        if not (self.company_id and self.company_id.sit_facturacion):
            _logger.info("SIT No aplica facturación electrónica. Se omite generación de QR(_generar_qr) en evento de invalidacion.")
            return False

        # 2 Validar si es una compra normal (sin sujeto excluido)
        if self.move_type in (constants.IN_INVOICE, constants.IN_REFUND):
            tipo_doc = self.journal_id.sit_tipo_documento
            if not tipo_doc or tipo_doc.codigo != constants.COD_DTE_FSE:
                _logger.info("SIT: Documento de compra normal (sin sujeto excluido). Se omite generación de QR.")

        # 3 Obtener URL de consulta según el entorno
        # enviroment_type = self._get_environment_type()
        # enviroment_type = self.env["res.company"]._get_environment_type()
        company = self.company_id
        if not company:
            raise UserError(_("No se encontró la compañía asociada a la factura a reemplazar."))
        enviroment_type = company._get_environment_type()
        # if enviroment_type == 'homologation':
        #     host = 'https://admin.factura.gob.sv'
        # else:
        #     host = 'https://admin.factura.gob.sv'
        host = config_utils.get_config_value(self.env, 'consulta_dte', self.company_id.id) if config_utils else 'https://admin.factura.gob.sv'

        # 4 Construir URL del QR
        # https://admin.factura.gob.sv/consultaPublica?ambiente=00&codGen=00000000-0000-00000000-000000000000&fechaEmi=2022-05-01
        fechaEmision = str(fechaEmi.year) + "-" + str(fechaEmi.month).zfill(2) + "-" + str(fechaEmi.day).zfill(2)
        texto_codigo_qr = host + "/consultaPublica?ambiente=" + str(ambiente) + "&codGen=" + str(codGen) + "&fechaEmi=" + str(fechaEmision)
        _logger.info("SIT generando qr texto_codigo_qr = %s", texto_codigo_qr)

        # 5 Generar QR
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
        wpercent = (basewidth / float(img.size[0]))
        hsize = int((float(img.size[1]) * float(wpercent)))
        new_img = img.resize((basewidth, hsize), Image.BICUBIC)
        new_img.save(buffer, format="PNG")
        qrCode = base64.b64encode(buffer.getvalue())
        # self.sit_qr_hacienda = qrCode
        return qrCode

    def generar_qr(self):
        _logger.info("SIT generando QR para move_id=%s", self.id)

        # 1 Validar si aplica facturación electrónica
        if not (self.company_id and self.company_id.sit_facturacion):
            _logger.info("SIT No aplica facturación electrónica. Se omite generación de QR(generar_qr) en evento de invalidacion.")
            return False

        # 2 Validar si es una compra normal (sin sujeto excluido)
        if self.move_type in (constants.IN_INVOICE, constants.IN_REFUND):
            tipo_doc = self.journal_id.sit_tipo_documento
            if not tipo_doc or tipo_doc.codigo != constants.COD_DTE_FSE:
                _logger.info("SIT: Documento de compra normal (sin sujeto excluido). Se omite generación de QR.")
                return False

        # 3 Obtener entorno y URL
        company = self.company_id
        if not company:
            raise UserError(_("No se encontró la compañía asociada a la factura a reemplazar."))

        enviroment_type = company._get_environment_type()
        if enviroment_type == 'homologation':
            ambiente = "00"
        else:
            ambiente = "01"

        host = config_utils.get_config_value(self.env, 'consulta_dte', self.company_id.id) if config_utils else 'https://admin.factura.gob.sv'
        texto_codigo_qr = host + "/consultaPublica?ambiente=" + str(ambiente) + "&codGen=" + str(self.hacienda_codigoGeneracion_identificacion) + "&fechaEmi=" + str(self.fecha_facturacion_hacienda)
        _logger.info("SIT generando qr xxx texto_codigo_qr= %s", texto_codigo_qr)

        # 4 Generar QR
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

        wpercent = (basewidth / float(img.size[0]))
        hsize = int((float(img.size[1]) * float(wpercent)))
        new_img = img.resize((basewidth, hsize), Image.BICUBIC)
        new_img.save(buffer, format="PNG")
        qrCode = base64.b64encode(buffer.getvalue())
        self.sit_qr_hacienda = qrCode
        return

    # def check_parametros_invalidacion(self):
    #     if not (self.company_id and self.company_id.sit_facturacion):
    #         _logger.info("SIT No aplica facturación electrónica. Se omite generación de check_parametros_invalidacion en evento de invalidacion.")
    #         return False
    #
    #     ambiente_test = False
    #     if config_utils:
    #         ambiente_test = config_utils._compute_validation_type_2(self.env, self.company_id)
    #         _logger.info("SIT Tipo de entorno invalidacion[Ambiente]: %s", ambiente_test)
    #         if ambiente_test:
    #             # Si es ambiente de pruebas, no seguir con el resto del código
    #             _logger.info("SIT Entorno de pruebas detectado, deteniendo generación de payload de anulación.")
    #             return False
    #
    #     if not self.name:
    #          raise UserError(_('El Número de control no definido'))
    #     if not self.company_id.tipoEstablecimiento.codigo:
    #         raise UserError(_('El tipoEstablecimiento no definido'))
    #
    #
    #     if not self.sit_tipoAnulacion or self.sit_tipoAnulacion == False:
    #         raise UserError(_('El tipoAnulacion no definido'))
    #

    # def check_parametros_firmado_anu(self):
    #     if not (self.company_id and self.company_id.sit_facturacion):
    #         _logger.info("SIT No aplica facturación electrónica. Se omite validación de parámetros de firmado en invalidacion.")
    #         return False
    #
    #     if not self.journal_id.sit_tipo_documento.codigo:
    #         raise UserError(_('El Tipo de  DTE no definido.'))
    #     if not self.name:
    #         raise UserError(_('El Número de control no definido'))
    #     if not self.company_id.sit_passwordPri:
    #         raise UserError(_('El valor passwordPri no definido'))
    #     if not self.company_id.sit_uuid:
    #         raise UserError(_('El valor uuid no definido'))
    #     if not self.company_id.vat:
    #         raise UserError(_('El emisor no tiene NIT configurado.'))
    #     if not self.company_id.company_registry:
    #         raise UserError(_('El emisor no tiene NRC configurado.'))
    #     if not self.company_id.name:
    #         raise UserError(_('El emisor no tiene NOMBRE configurado.'))
    #     if not self.company_id.codActividad:
    #         raise UserError(_('El emisor no tiene CODIGO DE ACTIVIDAD configurado.'))
    #     if not self.company_id.tipoEstablecimiento:
    #         raise UserError(_('El emisor no tiene TIPO DE ESTABLECIMIENTO configurado.'))
    #     if not self.company_id.state_id:
    #         raise UserError(_('El emisor no tiene DEPARTAMENTO configurado.'))
    #     if not self.company_id.munic_id:
    #         raise UserError(_('El emisor no tiene MUNICIPIO configurado.'))
    #     if not self.company_id.email:
    #         raise UserError(_('El emisor no tiene CORREO configurado.'))
    #
    #     if not self.journal_id.sit_tipo_documento.codigo:
    #         raise UserError(_('El Tipo de DTE no definido.'))
    #     if not self.name:
    #         raise UserError(_('El Número de control no definido'))
    #     # Validaciones para el emisor (comunes para todos los tipos de DTE)
    #     # ...
    #
    #     # Validaciones específicas según el tipo de DTE
    #     tipo_dte = self.journal_id.sit_tipo_documento.codigo
    #
    #     if tipo_dte == constants.COD_DTE_FE:
    #         # Solo validar el nombre para DTE tipo 01
    #         if not self.partner_id.name:
    #             raise UserError(_('El receptor no tiene NOMBRE configurado para facturas tipo 01.'))
    #     elif tipo_dte == constants.COD_DTE_CCF:
    #         # Validaciones completas para DTE tipo 03
    #         if not self.partner_id.vat and self.partner_id.is_company:
    #             _logger.info("SIT, es compañia se requiere NIT")
    #             _logger.info("SIT, partner campos requeridos account=%s", self.partner_id)
    #             raise UserError(_('El receptor no tiene NIT configurado.'))
    #         if not self.partner_id.nrc and self.partner_id.is_company:
    #             _logger.info("SIT, es compañia se requiere NRC")
    #             raise UserError(_('El receptor no tiene NRC configurado.'))
    #         if not self.partner_id.name:
    #             raise UserError(_('El receptor no tiene NOMBRE configurado.'))
    #         if not self.partner_id.codActividad:
    #             raise UserError(_('El receptor no tiene CODIGO DE ACTIVIDAD configurado.'))
    #         if not self.partner_id.state_id:
    #             raise UserError(_('El receptor no tiene DEPARTAMENTO configurado.'))
    #         if not self.partner_id.munic_id:
    #             raise UserError(_('El receptor no tiene MUNICIPIO configurado.'))
    #         if not self.partner_id.email:
    #             raise UserError(_('El receptor no tiene CORREO configurado.'))
    #
    #     # Validaciones comunes para cualquier tipo de DTE
    #     if not self.invoice_line_ids:
    #         raise UserError(_('La factura no tiene LINEAS DE PRODUCTOS asociada.'))
