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
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import config_utils
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo config_utils [hacienda fex-account_move]")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    config_utils = None
    constants = None

class AccountMove(models.Model):

    _inherit = "account.move"

    tipoItemEmisor = fields.Many2one('account.move.tipo_item.field', string="Tipo de Item Emisor")
    sale_order_id = fields.Many2one('sale.order', string='Orden de Venta', compute='_compute_sale_order', store=False)

    def _compute_sale_order(self):
        for rec in self:
            sale_orders = rec.invoice_line_ids.mapped('sale_line_ids.order_id')
            rec.sale_order_id = sale_orders[:1] if sale_orders else False


    def action_post(self):
        # Si FE está desactivada → comportamiento estándar de Odoo
        if not self.env.company.sit_facturacion:
            return super().action_post()

        # FE activa → aplica tus validaciones extra y luego deja que Odoo postee
        for rec in self:
            tipo_dte = rec.journal_id.sit_tipo_documento
            if tipo_dte and getattr(tipo_dte, 'codigo', tipo_dte) == constants.COD_DTE_FEX:
                if not rec.tipoItemEmisor:
                    raise ValidationError(
                        "El campo 'Tipo de Ítem Emisor' es obligatorio para facturas de exportación (11).")
                if not rec.invoice_incoterm_id:
                    raise ValidationError("Debe seleccionar un INCOTERM para facturas de exportación (11).")
                if not rec.partner_id.country_id:
                    raise ValidationError("El receptor debe tener un país seleccionado.")
                if not rec.sit_regimen:
                    raise ValidationError("Debe seleccionar un régimen de exportación.")
                if not rec.sale_order_id.recintoFiscal:
                    raise ValidationError("Debe seleccionar un recinto fiscal.")

                # OJO: si 'constants' no cargó, evita acceder a atributos
                if (constants and rec.partner_id.l10n_latam_identification_type_id
                        and rec.partner_id.l10n_latam_identification_type_id.codigo == constants.COD_TD_DUI):
                    raise ValidationError("Cliente no aplica.")

                # Cuenta seguro/flete
                company = rec.company_id
                cuenta_exportacion = company.account_exportacion_id
                if not cuenta_exportacion:
                    cuenta = config_utils.get_config_value(self.env, 'cuenta_exportacion',
                                                           self.company_id.id) if config_utils else False
                    if cuenta:
                        cuenta = cuenta.strip()
                        cuenta_exportacion = self.env['account.account'].search([('code', '=', cuenta)], limit=1)
                    if not cuenta_exportacion:
                        raise UserError(
                            "Debe configurar la cuenta contable para seguro y flete. "
                            "Hágalo en Ajustes de la Compañía o asigne una cuenta con código '450000'."
                        )
                    company.write({'account_exportacion_id': cuenta_exportacion.id})

                if not rec.invoice_date:
                    raise ValidationError("Debe seleccionar la fecha de la Factura.")

                if not rec.invoice_incoterm_id:
                    raise ValidationError("Es obligatorio seleccionar un Incoterm.")

                if rec.invoice_incoterm_id and not rec.invoice_incoterm_id.codigo_mh:
                    raise ValidationError("El Incoterm seleccionado no tiene Código de Hacienda. Verifique que los códigos estén actualizados.")

        return super().action_post()

    #---------------------------------------------------------------------------------------------
# Exportacion
#---------------------------------------------------------------------------------------------
    # def _post(self, soft=True):
    #     '''validamos que partner cumple los requisitos basados en el tipo
    # de documento de la sequencia del diario selecionado
    # FACTURA ELECTRONICAMENTE
    # '''
    #     for invoice in self:
    #         if invoice.move_type != 'entry':
    #             type_report = invoice.journal_id.type_report
    #             sit_tipo_documento = invoice.journal_id.sit_tipo_documento.codigo
    #             _logger.info("SIT action_post type_report  = %s", type_report)
    #             _logger.info("SIT action_post sit_tipo_documento  = %s", sit_tipo_documento)
    #             validation_type = self._compute_validation_type_2()
    #             _logger.info("SIT action_post validation_type = %s", validation_type)

    #             # if type_report == 'exp':
    #             #     for l in invoice.invoice_line_ids:
    #             #         if not l.product_id.arancel_id:
    #             #             invoice.msg_error("Posicion Arancelaria del Producto %s" % l.product_id.name)
    #             ambiente = "00"
    #             if validation_type == 'homologacioin':
    #                 ambiente = "00"
    #                 _logger.info("SIT Factura de Prueba")
    #             elif validation_type == 'production':
    #                 _logger.info("SIT Factura de Producción")
    #                 ambiente = "01"
    #             # Firmado de documento
    #             print("FIRMAAAAAAAAAAAAAAAAAAAAA")
    #             print(validation_type)
    #             payload = invoice.obtener_payload_fex(validation_type, sit_tipo_documento)
    #             documento_firmado = ""
    #             payload_original = payload
    #             _logger.info("SIT payload_original = %s ", str((payload_original)) ) 


    #             documento_firmado = invoice.firmar_documento_fex(validation_type, payload)
    #             if documento_firmado:
    #                 _logger.info("SIT Firmado de documento")
    #                 _logger.info("SIT Generando DTE")
    #                 #Obtiene el payload DTE
    #                 payload_dte = invoice.sit_obtener_payload_fex_dte_info(ambiente, documento_firmado)
    #                 self.check_parametros_dte_fex(payload_dte)
    #                 Resultado = invoice.generar_dte_fex(validation_type, payload_dte, payload_original)
    #                 from datetime import datetime, timedelta
    #                 if Resultado:
    #                     dat_time  = Resultado['fhProcesamiento']
    #                     _logger.info("SIT Fecha de procesamiento (%s)%s", type(dat_time), dat_time)
    #                     fhProcesamiento = datetime.strptime(dat_time, '%d/%m/%Y %H:%M:%S')
    #                     _logger.info("SIT Fecha de procesamiento (%s)%s", type(fhProcesamiento), fhProcesamiento)
    #                     MENSAJE="SIT Respuesta = " + str(Resultado)
    #                     invoice.hacienda_estado = Resultado['estado']
    #                     invoice.hacienda_codigoGeneracion_identificacion = Resultado['codigoGeneracion']
    #                     invoice.hacienda_selloRecibido = Resultado['selloRecibido']
    #                     invoice.fecha_facturacion_hacienda = fhProcesamiento + timedelta(hours=6)       #  Resultado['fhProcesamiento']
    #                     invoice.hacienda_clasificaMsg = Resultado['clasificaMsg']
    #                     invoice.hacienda_codigoMsg = Resultado['codigoMsg']
    #                     invoice.hacienda_descripcionMsg = Resultado['descripcionMsg']
    #                     invoice.hacienda_observaciones = str(Resultado['observaciones'])
    #                     codigo_qr = invoice._generar_qr(ambiente, Resultado['codigoGeneracion'], invoice.fecha_facturacion_hacienda )
    #                     invoice.sit_qr_hacienda = codigo_qr
    #                     _logger.info("SIT Factura creada correctamente =%s", MENSAJE)
    #                     _logger.info("SIT Factura creada correctamente state =%s", invoice.state)
    #                     payload_original['dteJson']['firmaElectronica'] = documento_firmado
    #                     payload_original['dteJson']['selloRecibido'] = Resultado['selloRecibido']
    #                     _logger.info("SIT Factura creada correctamente payload_original =%s",   str(json.dumps(payload_original)))  
    #                     invoice.sit_json_respuesta = str(json.dumps(payload_original['dteJson']))
    #                     json_str = json.dumps(payload_original['dteJson'])
    #                     json_base64 = base64.b64encode(json_str.encode('utf-8'))
    #                     file_name = payload_original["dteJson"]["identificacion"]["numeroControl"] + '.json'
    #                     _logger.info("SIT file_name =%s", file_name)
    #                     _logger.info("SIT self._name =%s", self._name)
    #                     _logger.info("SIT invoice.id =%s", invoice.id)
    #                     invoice.env['ir.attachment'].sudo().create(
    #                         {
    #                             'name': file_name,
    #                             'datas': json_base64,
    #                             'res_model': self._name,
    #                             'res_id': invoice.id,
    #                             'mimetype': 'application/json'
    #                         }) 
    #                     _logger.info("SIT json creado........................")
    #                     invoice.state = "draft"
    #                     _logger.critical("Numero de Control")
    #                     _logger.critical(invoice.name)
    #                     return super(AccountMove, self)._post()
    #             else:
    #                 _logger.info("SIT  Documento no firmado")    
    #                 raise UserError(_('SIT Documento NO Firmado'))

    #     return super(AccountMove, self)._post()

    # # FIMAR FIMAR FIRMAR =====================================================================================================    
    # def firmar_documento_fex(self, enviroment_type, payload):
    #     _logger.info("SIT  Firmando de documento")
    #     _logger.info("SIT Documento a FIRMAR =%s", payload)
    #     if enviroment_type == 'homologation': 
    #         ambiente = "00"
    #     else:
    #         ambiente = "01"
    #     host = 'http://svfe-api-firmador:8113'
    #     url = host + '/firmardocumento/'
    #     headers = {'Content-Type': 'application/json'}
    #     try:
    #         MENSAJE = "SIT POST, " + str(url) + ", headers=" + str(headers) + ", data=" + str(json.dumps(payload))
    #         _logger.info("SIT A FIRMAR = %s", MENSAJE)
    #         response = requests.request("POST", url, headers=headers, data=json.dumps(payload))
    #     except Exception as e:
    #         error = str(e)
    #         _logger.info('SIT error= %s, ', error)       
    #         if "error" in error or "" in error:
    #             MENSAJE_ERROR = str(error['status']) + ", " + str(error['error']) +", " +  str(error['message'])  
    #             raise UserError(_(MENSAJE_ERROR))
    #         else:
    #             raise UserError(_(error))
    #     resultado = []    
    #     json_response = response.json()
    #     if json_response['status'] in [  400, 401, 402 ] :
    #         _logger.info("SIT Error 40X  =%s", json_response['status'])
    #         status=json_response['status']
    #         error=json_response['error']
    #         message=json_response['message']
    #         MENSAJE_ERROR = "Código de Error:" + str(status) + ", Error:" + str(error) +", Detalle:" +  str(message)  
    #         raise UserError(_(MENSAJE_ERROR))
    #     if json_response['status'] in [ 'ERROR', 401, 402 ] :
    #         _logger.info("SIT Error 40X  =%s", json_response['status'])
    #         status=json_response['status']
    #         body=json_response['body']
    #         codigo=body['codigo']
    #         message=body['mensaje']
    #         resultado.append(status)
    #         resultado.append(codigo)
    #         resultado.append(message)
    #         MENSAJE_ERROR = "Código de Error:" + str(status) + ", Codigo:" + str(codigo) +", Detalle:" +  str(message)  
    #         raise UserError(_(MENSAJE_ERROR))        
    #     elif json_response['status'] == 'OK':
    #         status=json_response['status']
    #         body=json_response['body']
    #         resultado.append(status)
    #         resultado.append(body)
    #         return body

    def obtener_payload_fex(self, enviroment_type, sit_tipo_documento):
        """Construye el payload FEX solo si la FE está activa; de lo contrario, no hace nada."""
        if not self.env.company.sit_facturacion:
            _logger.info("FE OFF: omitiendo obtener_payload_fex en %s", self._name)
            return None

        self.ensure_one()
        _logger.info("SIT  Obteniendo payload")
        ambiente = "00" if enviroment_type == 'homologation' else "01"
        invoice_info = self.sit_fex_base_map_invoice_info()
        _logger.info("SIT invoice_info FExportacion= %s", invoice_info)
        self.check_parametros_firmado_fex()
        _logger.info("SIT payload_data =%s", invoice_info)
        return invoice_info

    def generar_dte_fex(self, enviroment_type, payload, payload_original):
        """Genera el DTE FEX solo si la FE está activa; si está apagada, no hace nada."""
        if not self.env.company.sit_facturacion:
            _logger.info("FE OFF: omitiendo generar_dte_fex en %s", self._name)
            return None

        self.ensure_one()
        _logger.info("SIT  Generando DTE")
        #host = 'https://apitest.dtes.mh.gob.sv' if enviroment_type == 'homologation' else 'https://api.dtes.mh.gob.sv'
        #url = host + '/fesv/recepciondte'
        url = None
        if enviroment_type == 'homologation':
            host = 'https://apitest.dtes.mh.gob.sv'
            url = host + '/fesv/recepciondte'
        else:
            url = config_utils.get_config_value(self.env, 'url_prod_hacienda', self.company_id.id)

        if not self.company_id.sit_token_fecha:
            self.company_id.get_generar_token()
        elif self.company_id.sit_token_fecha.date() and self.company_id.sit_token_fecha.date() < self.date:
            self.company_id.get_generar_token()

        headers = {
            'Content-Type': 'application/json',
            'User-Agent': self.company_id.sit_token_user,
            'Authorization': self.company_id.sit_token,
        }

        if 'version' not in payload:
            payload['version'] = 3

        _logger.info("SIT = requests.request(POST, %s, headers=%s, data=%s)", url, headers, payload)
        try:
            _logger.info("________________________________________________ =%s", payload)
            response = requests.request("POST", url, headers=headers, data=json.dumps(payload))
            _logger.info("SIT DTE response =%s", response)
            _logger.info("SIT DTE response =%s", response.status_code)
            _logger.info("SIT DTE response.text =%s", response.text)
        except Exception as e:
            error = str(e)
            _logger.info('SIT error= %s, ', error)
            if "error" in error or "" in error:
                MENSAJE_ERROR = str(error['status']) + ", " + str(error['error']) + ", " + str(error['message'])
                raise UserError(_(MENSAJE_ERROR))
            else:
                raise UserError(_(error))

        if response.status_code in [401]:
            MENSAJE_ERROR = "ERROR de conexión : " + str(response)
            raise UserError(_(MENSAJE_ERROR))

        json_response = response.json()
        _logger.info("SIT json_responset =%s", json_response)

        if json_response.get('estado') in ["RECHAZADO", 402]:
            estado = json_response.get('estado')
            amb = 'TEST' if json_response.get('ambiente') == '00' else 'PROD'
            clasificaMsg = json_response.get('clasificaMsg')
            message = json_response.get('descripcionMsg')
            observaciones = json_response.get('observaciones')
            MENSAJE_ERROR = (
                f"Código de Error..:{estado}, Ambiente:{amb}, "
                f"ClasificaciónMsje:{clasificaMsg}, Descripcion:{message}, "
                f"Detalle:{observaciones}, DATA: {json.dumps(payload_original)}"
            )
            self.hacienda_estado = estado
            raise UserError(_(MENSAJE_ERROR))

        status = json_response.get('status')
        if status in [400, 401, 402]:
            error = json_response.get('error', 'Error desconocido')
            message = json_response.get('message', 'Mensaje no proporcionado')
            MENSAJE_ERROR = f"Código de Error:{status}, Error:{error}, Detalle:{message}"
            raise UserError(_(MENSAJE_ERROR))

        if json_response.get('estado') == "PROCESADO":
            return json_response

        return None

    def check_parametros_fex(self):
        """Valida solo si la FE está activa; si está apagada, no bloquea."""
        if not self.env.company.sit_facturacion:
            _logger.info("FE OFF: omitiendo check_parametros_fex en %s", self._name)
            return None

        if not self.name:
            raise UserError(_('El Número de control no definido'))
        if not self.company_id.tipoEstablecimiento.codigo:
            raise UserError(_('El tipoEstablecimiento no definido'))
        if not self.sit_tipoAnulacion:
            raise UserError(_('El tipoAnulacion no definido'))
        return None

    def check_parametros_firmado_fex(self):
        """Valida solo si la FE está activa; si está apagada, no bloquea."""
        if not self.env.company.sit_facturacion:
            _logger.info("FE OFF: omitiendo check_parametros_firmado_fex en %s", self._name)
            return None

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

        tipo_dte = self.journal_id.sit_tipo_documento.codigo
        if tipo_dte == constants.COD_DTE_FEX:
            if not self.partner_id.name:
                raise UserError(_('El receptor no tiene NOMBRE configurado para facturas tipo 01.'))
            if self.partner_id.is_company and not self.partner_id.vat:
                _logger.info("SIT, es compañia se requiere NIT")
                raise UserError(_('El receptor no tiene NIT configurado.'))
            if self.partner_id.is_company and not self.partner_id.nrc:
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
        return None

    def check_parametros_linea_firmado_fex(self, line_temp):
        """Valida líneas solo si la FE está activa; si está apagada, no bloquea."""
        if not self.env.company.sit_facturacion:
            _logger.info("FE OFF: omitiendo check_parametros_linea_firmado_fex en %s", self._name)
            return None

        if not line_temp.get("codigo"):
            raise UserError(_('El CODIGO del producto  %s no está definido.') % line_temp.get("descripcion"))
        if not line_temp.get("cantidad"):
            raise UserError(_('La CANTIDAD del producto  %s no está definida.') % line_temp.get("descripcion"))
        if not line_temp.get("precioUni"):
            raise UserError(_('El PRECIO UNITARIO del producto  %s no está definido.') % line_temp.get("descripcion"))
        if not line_temp.get("uniMedida"):
            raise UserError(_('La UNIDAD DE MEDIDA del producto  %s no está definida.') % line_temp.get("descripcion"))
        return None

    def check_parametros_dte_fex(self, generacion_dte):
        """Valida el blob DTE solo si la FE está activa; si está apagada, no bloquea."""
        if not self.env.company.sit_facturacion:
            _logger.info("FE OFF: omitiendo check_parametros_dte_fex en %s", self._name)
            return None

        if not generacion_dte.get("ambiente"):
            raise UserError(_('El ambiente no está definido.'))
        if not generacion_dte.get("idEnvio"):
            raise UserError(_('El IDENVIO no está definido.'))
        if not generacion_dte.get("documento"):
            raise UserError(_('El DOCUMENTO no está presente.'))
        if not generacion_dte.get("version"):
            raise UserError(_('La versión DTE no está definida.'))
        return None
