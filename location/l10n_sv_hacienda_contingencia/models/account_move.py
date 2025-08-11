# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import UserError
import pytz
import logging
import json
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)
tz_el_salvador = pytz.timezone('America/El_Salvador')

try:
    from odoo.addons.common_utils.utils import config_utils
    _logger.info("SIT Modulo config_utils [hacienda ws-account_move[contingencia]]")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    config_utils = None

class sit_account_move(models.Model):
    _inherit = 'account.move'
    sit_tipo_contingencia = fields.Many2one('account.move.tipo_contingencia.field', string="Tipo de Contingencia")
    sit_tipo_contingencia_otro = fields.Text(string="Especifique el Otro Tipo de Contingencia")
    sit_tipo_contingencia_valores = fields.Char(related="sit_tipo_contingencia.valores", string="Tipo de contingiancia(nombre)")
    sit_factura_de_contingencia = fields.Many2one('account.contingencia1', string="Factura de contingencia relacionada", ondelete="set null")
    sit_es_configencia = fields.Boolean('Es contingencia ?',  copy=False,)
    sit_factura_por_lote = fields.Boolean('Facturado por lote ?',  copy=False, default=False)
    sit_documento_firmado = fields.Text(string="Documento Firmado", copy=False, readonly=True)
    sit_lote_contingencia = fields.Many2one('account.lote', string="Factura asignada en el lote", ondelete="set null")

    @api.onchange('sit_es_configencia')
    def check_sit_es_configencia(self):
        _logger.info("SIT revisando  si es o no es sit_es_configencia  <---------------------------------------------")
        if self.sit_es_configencia:
            _logger.info("SIT sit_es_configencia")
            #self.sit_block_hacienda = True
        else:
            _logger.info("SIT NO sit_es_configencia")                
            #self.sit_block_hacienda = False


# ---------------------------------------------------------------------------------------------
# FACTURA CONTINGENCIA
#---------------------------------------------------------------------------------------------
    def action_post_contingencia(self):
        '''validamos que partner cumple los requisitos basados en el tipo
    de documento de la sequencia del diario selecionado
    FACTURA ELECTRONICAMENTE
    '''
        # NUMERO_FACTURA= super(AccountMove, self).action_post()
        # _logger.info("SIT NUMERO FACTURA =%s", NUMERO_FACTURA)
        for invoice in self:
            MENSAJE = "action_post_contingencia -->" + str(self.name)
            # raise UserError(_(MENSAJE))
            if invoice.name == "/" or not invoice.name:
                NUMERO_FACTURA = invoice._set_next_sequence()
            else:
                NUMERO_FACTURA = "/"
            _logger.info("SIT NUMERO FACTURA =%s", NUMERO_FACTURA)
            if invoice.sit_es_configencia:
                sello_contingencia = invoice.sit_factura_de_contingencia.sit_selloRecibido
                if sello_contingencia:
                    #invoice.sit_block_hacienda = False
                    invoice.action_post()        
                else:
                    #invoice.sit_block_hacienda = True
                    MENSAJE = "Se requiere el sello de contingencia para proceder a validar esta factura"
                    raise UserError(_(MENSAJE))

                if not sello_contingencia:
                    MENSAJE = "Se requiere el sello de contingencia para proceder a validar esta factura"
                    raise UserError(_(MENSAJE))
    

        # for invoice in self:
        #     if invoice.move_type != 'entry':
        #         type_report = invoice.journal_id.type_report
        #         sit_tipo_documento = invoice.journal_id.sit_tipo_documento.codigo
                
        #         _logger.info("SIT action_post type_report  = %s", type_report)
        #         _logger.info("SIT action_post sit_tipo_documento  = %s", sit_tipo_documento)
        #         # _logger.info("SIT action_post sit_tipo_documento  = %s", sit_tipo_documento.codigo)
        #         validation_type = self._compute_validation_type_2()
        #         _logger.info("SIT action_post validation_type = %s", validation_type)
               
        #         if type_report == 'ccf':
        #             if not invoice.partner_id.parent_id:
        #                 if not invoice.partner_id.nrc:
        #                     invoice.msg_error("N.R.C.")
        #                 if not invoice.partner_id.vat and not invoice.partner_id.dui:
        #                     invoice.msg_error("N.I.T O D.U.I.")
        #                 # if not invoice.partner_id.giro:
        #                     # invoice.msg_error("Giro")
        #                 if not invoice.partner_id.codActividad:
        #                     invoice.msg_error("Giro o Actividad Económica")
        #             else:
        #                 if not invoice.partner_id.parent_id.nrc:
        #                     invoice.msg_error("N.R.C.")
        #                 if not invoice.partner_id.parent_id.vat and not invoice.partner_id.parent_id.dui:
        #                     invoice.msg_error("N.I.T O D.U.I.")
        #                 if not invoice.partner_id.parent_id.codActividad:
        #                     invoice.msg_error("Giro o Actividad Económica")

        #         elif type_report == 'fcf':
        #             if not invoice.partner_id.parent_id:
        #                 if not invoice.partner_id.vat:
        #                     #invoice.msg_error("N.I.T.")
        #                     pass
        #                 if invoice.partner_id.company_type == 'person':
        #                     if not invoice.partner_id.dui:
        #                         #invoice.msg_error("D.U.I.")
        #                         pass
        #             else:
        #                 if not invoice.partner_id.parent_id.vat:
        #                     #invoice.msg_error("N.I.T.")
        #                     pass
        #                 if invoice.partner_id.parent_id.company_type == 'person':
        #                     if not invoice.partner_id.dui:
        #                         #invoice.msg_error("D.U.I.")
        #                         pass

        #         elif type_report == 'exp':
        #             for l in invoice.invoice_line_ids:
        #                 if not l.product_id.arancel_id:
        #                     invoice.msg_error("Posicion Arancelaria del Producto %s" % l.product_id.name)

        #         # si es retificativa
        #         elif type_report == 'ndc':
        #             if not invoice.partner_id.parent_id:
        #                 if not invoice.partner_id.nrc:
        #                     invoice.msg_error("N.R.C.")
        #                 if not invoice.partner_id.vat:
        #                     invoice.msg_error("N.I.T.")
        #                 # if not invoice.partner_id.giro:
        #                 #     invoice.msg_error("Giro")
        #                 if not invoice.partner_id.codActividad:
        #                     invoice.msg_error("Giro o Actividad Económica")
        #             else:
        #                 if not invoice.partner_id.parent_id.nrc:
        #                     invoice.msg_error("N.R.C.")
        #                 if not invoice.partner_id.parent_id.vat:
        #                     invoice.msg_error("N.I.T.")
        #                 # if not invoice.partner_id.parent_id.giro:
        #                 #     invoice.msg_error("Giro")
        #                 if not invoice.partner_id.parent_id.codActividad:
        #                     invoice.msg_error("Giro o Actividad Económica")
        #         ambiente = "00"
        #         if validation_type == 'homologation':
        #             ambiente = "00"
        #             _logger.info("SIT Factura de Prueba")
        #         elif validation_type == 'production':
        #             _logger.info("SIT Factura de Producción")
        #             ambiente = "01"
        #         # Firmado de documento
        #         payload = invoice.obtener_payload(validation_type, sit_tipo_documento)
        #         documento_firmado = ""
        #         payload_original = payload
        #         _logger.info("SIT payload_original = %s ", str((payload_original)) ) 


        #         documento_firmado = invoice.firmar_documento(validation_type, payload)
        #         # payload_contingencia = invoice.obtener_payload_contingencia(validation_type, sit_tipo_documento)

        #         if documento_firmado:
        #             _logger.info("SIT Firmado de documento contingencia")
        #             _logger.info("SIT Generando DTE contingencia")
        #             #Obtiene el payload DTE
        #             # raise UserError(_('SIT Documento Firmado, Generando DTE'))
        #             # codigo_qr = invoice._generar_qr(ambiente, invoice.hacienda_codigoGeneracion_identificacion, invoice.fecha_facturacion_hacienda )
        #             invoice.sit_documento_firmado = str(documento_firmado)

        #             # raise UserError(_('SIT Documento Firmado, Generando DTE'))

        #         else:
        #             _logger.info("SIT  Documento no firmado contingencia" )    
        #             raise UserError(_('SIT Documento NO Firmado'))

        #         _logger.info("SIT Generando DTE conteingencia")
        #         sello_contingencia = invoice.sit_factura_de_contingencia.sit_selloRecibido
        #         if sello_contingencia:
        #             payload_dte = invoice.sit_obtener_payload_dte_info(ambiente, documento_firmado)
        #             self.check_parametros_dte(payload_dte)
        #             Resultado = invoice.generar_dte(validation_type, payload_dte, payload_original)
        #             if Resultado:

        #                 dat_time  = Resultado['fhProcesamiento']
        #                 _logger.info("SIT Fecha de procesamiento (%s)%s", type(dat_time), dat_time)
        #                 fhProcesamiento = datetime.strptime(dat_time, '%d/%m/%Y %H:%M:%S')
        #                 _logger.info("SIT Fecha de procesamiento (%s)%s", type(fhProcesamiento), fhProcesamiento)

        #                 MENSAJE="SIT Respuesta = " + str(Resultado)
        #                 invoice.hacienda_estado = Resultado['estado']
        #                 invoice.hacienda_codigoGeneracion_identificacion = Resultado['codigoGeneracion']
        #                 invoice.hacienda_selloRecibido = Resultado['selloRecibido']
        #                 invoice.fecha_facturacion_hacienda = fhProcesamiento        #  Resultado['fhProcesamiento']
        #                 invoice.hacienda_clasificaMsg = Resultado['clasificaMsg']
        #                 invoice.hacienda_codigoMsg = Resultado['codigoMsg']
        #                 invoice.hacienda_descripcionMsg = Resultado['descripcionMsg']
        #                 invoice.hacienda_observaciones = str(Resultado['observaciones'])
        #                 codigo_qr = invoice._generar_qr(ambiente, Resultado['codigoGeneracion'], invoice.fecha_facturacion_hacienda )
        #                 invoice.sit_qr_hacienda = codigo_qr
        #                 _logger.info("SIT Factura creada correctamente =%s", MENSAJE)
        #                 _logger.info("SIT Factura creada correctamente state =%s", invoice.state)
        #                 payload_original['dteJson']['firmaElectronica'] = documento_firmado
        #                 payload_original['dteJson']['selloRecibido'] = Resultado['selloRecibido']
        #                 _logger.info("SIT Factura creada correctamente payload_original =%s",   str(json.dumps(payload_original)))  

        #                 invoice.sit_json_respuesta = str(json.dumps(payload_original['dteJson']))
        #                 json_str = json.dumps(payload_original['dteJson'])
        #                 # Codifica la cadena JSON en formato base64
        #                 json_base64 = base64.b64encode(json_str.encode('utf-8'))

        #                 file_name = invoice.name.replace('/', '_') + '.json'
        #                 _logger.info("SIT file_name =%s", file_name)
        #                 _logger.info("SIT self._name =%s", self._name)
        #                 _logger.info("SIT invoice.id =%s", invoice.id)
        #                 invoice.env['ir.attachment'].sudo().create(
        #                     {
        #                         'name': file_name,
        #                         # 'datas': json_response['factura_xml'],
        #                         # 'datas': json.dumps(payload_original),
        #                         'datas': json_base64,
        #                         # 'datas_fname': file_name,
        #                         'res_model': self._name,
        #                         'res_id': invoice.id,
        #                         # 'type': 'binary'
        #                         'mimetype': 'application/json'
        #                     })
                            
        #                 _logger.info("SIT json creado........................")



        #                 invoice.state = "draft"
        #                 return super(AccountMove, self).action_post()
        #                 # raise UserError(_(MENSAJE))

                    

        #         else:
        #             if invoice.hacienda_codigoGeneracion_identificacion:
        #                 MENSAJE = "Se requiere el sello de contingencia para proceder a validar esta factura"
        #                 raise UserError(_(MENSAJE))
        #             else:
        #                 _logger.info("SIT buscando hacienda_codigoGeneracion_identificacion = %s", payload_original['dteJson']['identificacion'])
        #                 invoice.hacienda_codigoGeneracion_identificacion = payload_original['dteJson']['identificacion']['codigoGeneracion']

        # # return super(AccountMove, self).action_post()
        # return 

    def reenviar_dte(self):
        self.ensure_one()
        _logger.info(f"SIT reenviar_dte iniciado para factura ID {self.id}")

        if not self.hacienda_codigoGeneracion_identificacion:
            _logger.warning("No tiene código de generación.")
            raise UserError("No tiene código de generación.")
        payload = None

        ambiente = config_utils.compute_validation_type_2(self.env) if config_utils else None
        _logger.info(f"SIT Ambiente calculado: {ambiente}")

        # Firmar solo si no está firmado
        if not self.sit_documento_firmado:
            _logger.info("Documento no firmado. Se procede a firmar.")
            payload = self.obtener_payload(ambiente, self.journal_id.sit_tipo_documento.codigo)
            _logger.info(f"Payload para firma obtenido: {payload}")
            documento_firmado = self.firmar_documento(ambiente, payload)
            if not documento_firmado:
                _logger.warning("Error en firma del documento: documento_firmado vacío o nulo")
                raise UserError("Error en firma del documento")
        else:
            _logger.info("Documento ya firmado, se reutiliza la firma existente.")
            documento_firmado = self.sit_documento_firmado
            if self.sit_json_respuesta:
                try:
                    payload = json.loads(self.sit_json_respuesta)
                    _logger.info("Payload cargado desde sit_json_respuesta")
                except Exception as e:
                    _logger.warning(f"No se pudo cargar sit_json_respuesta: {e}")

        _logger.info("Obteniendo payload_dte")
        payload_dte = self.sit_obtener_payload_dte_info(ambiente, documento_firmado)
        _logger.info(f"Payload DTE: {payload_dte}")

        _logger.info("Validando parámetros DTE")
        self.check_parametros_dte(payload_dte)

        _logger.info("Generando DTE en Hacienda")
        Resultado = self.generar_dte(ambiente, payload_dte, payload)
        _logger.info(f"Resultado generado: {Resultado}")

        if not Resultado:
            _logger.warning("Resultado de generación DTE vacío o nulo")
            raise UserError("Error al generar DTE: Resultado vacío o nulo.")

        estado = Resultado.get('estado', '').strip().lower()
        _logger.info(f"Estado del DTE: {estado}")

        # Guardar json generado
        json_dte = payload.get('dteJson') if payload else None
        try:
            if not self.sit_json_respuesta:
                if isinstance(json_dte, str):
                    try:
                        json_dte_obj = json.loads(json_dte)
                        self.sit_json_respuesta = json.dumps(json_dte_obj, ensure_ascii=False)
                        json_dte = json_dte_obj
                    except json.JSONDecodeError:
                        self.sit_json_respuesta = json_dte
                elif isinstance(json_dte, dict):
                    self.sit_json_respuesta = json.dumps(json_dte, ensure_ascii=False)
                else:
                    self.sit_json_respuesta = str(json_dte)
                _logger.info("JSON DTE guardado correctamente en sit_json_respuesta")
            else:
                _logger.info("sit_json_respuesta ya contiene datos, no se reemplaza")
        except Exception as e:
            _logger.warning(f"No se pudo guardar el JSON del DTE: {e}")

        if estado == 'procesado':
            _logger.info("Estado procesado, actualizando secuencia y datos...")
            self.actualizar_secuencia()

            # Fecha procesamiento MH
            fh_procesamiento = Resultado.get('fhProcesamiento')
            if fh_procesamiento:
                try:
                    fh_dt = datetime.strptime(fh_procesamiento, '%d/%m/%Y %H:%M:%S') + timedelta(hours=6)
                    if not self.fecha_facturacion_hacienda:
                        self.write({'fecha_facturacion_hacienda': fh_dt})
                        _logger.info(f"Fecha facturacion actualizada: {self.fecha_facturacion_hacienda}")
                except Exception as e:
                    _logger.warning(f"Error al parsear fhProcesamiento: {e}")

            self.write({
                'hacienda_estado': Resultado['estado'],
                'hacienda_selloRecibido': Resultado.get('selloRecibido'),
                'hacienda_clasificaMsg': Resultado.get('clasificaMsg'),
                'hacienda_codigoMsg': Resultado.get('codigoMsg'),
                'hacienda_descripcionMsg': Resultado.get('descripcionMsg'),
                'hacienda_observaciones': str(Resultado.get('observaciones', '')),
                'state': 'draft',
                'recibido_mh': True,
                'sit_json_respuesta': self.sit_json_respuesta,
            })
            _logger.info("Campos MH actualizados correctamente")

            qr_code = self._generar_qr(ambiente, self.hacienda_codigoGeneracion_identificacion,
                                       self.fecha_facturacion_hacienda)
            self.sit_qr_hacienda = qr_code
            self.sit_documento_firmado = documento_firmado
            _logger.info("QR generado y firma guardada")

            try:
                json_str = json.dumps(json_dte, ensure_ascii=False, default=str)
                json_base64 = base64.b64encode(json_str.encode('utf-8'))
                file_name = json_dte.get("identificacion", {}).get("numeroControl", "dte") + '.json'
                self.env['ir.attachment'].sudo().create({
                    'name': file_name,
                    'datas': json_base64,
                    'res_model': self._name,
                    'res_id': self.id,
                    'mimetype': str(config_utils.get_config_value(self.env, 'content_type', self.company_id.id)),
                })
                _logger.info("SIT JSON creado y adjuntado como attachment")
            except Exception as e:
                _logger.warning(f"Error al crear o adjuntar JSON: {e}")

            try:
                json_original = json.loads(self.sit_json_respuesta) if self.sit_json_respuesta else {}
            except json.JSONDecodeError:
                json_original = {}
                _logger.warning("No se pudo cargar sit_json_respuesta para fusionar JSONRespuestaMh")

            json_original.update({"jsonRespuestaMh": Resultado})
            self.sit_json_respuesta = json.dumps(json_original)
            _logger.info("JSON respuesta MH fusionado correctamente")

            try:
                self.with_context(from_button=False, from_invalidacion=False).sit_enviar_correo_dte_automatico()
                _logger.info("Correo con PDF enviado exitosamente")
            except Exception as e:
                _logger.warning(f"SIT | Error al enviar DTE por correo o generar PDF: {e}")

        else:
            _logger.warning(f"Estado no procesado: {estado}")
            if estado == 'rechazado':
                mensaje = Resultado.get('descripcionMsg') or 'Documento rechazado por Hacienda.'
                _logger.warning(f"DTE rechazado por MH: {mensaje}")
                raise UserError(f"DTE rechazado por MH:\n{mensaje}")
            elif estado not in ('procesado', ''):
                mensaje = Resultado.get('descripcionMsg') or 'DTE no procesado correctamente.'
                _logger.warning(f"Respuesta inesperada de Hacienda. Estado: {estado}, Mensaje: {mensaje}")
                raise UserError(f"Respuesta inesperada de Hacienda. Estado: {estado}\nMensaje: {mensaje}")

        if not self.name.startswith("DTE-"):
            _logger.warning(f"Número de control inválido para la factura {self.id}: {self.name}")
            raise UserError(f"Número de control DTE inválido para la factura {self.id}.")

        _logger.info(f"SIT reenviar_dte finalizado exitosamente para factura ID {self.id}")
        return Resultado

    def action_reenviar_facturas_lote(self):
        _logger.info("Inicio reenvio del dte a MH, ID lote: %s", self.mapped('sit_lote_contingencia.id'))

        active_ids = self.env.context.get('active_ids')
        if not active_ids:
            raise UserError("Debe seleccionar al menos una factura del lote.")

        facturas = self.env['account.move'].browse(active_ids)

        # Obtener el lote del primer registro seleccionado
        lote_id = facturas[0].sit_lote_contingencia.id
        if not lote_id:
            raise UserError("Las facturas seleccionadas no tienen lote asignado.")

        # Filtrar facturas que pertenezcan a ese lote
        facturas = facturas.filtered(lambda f: f.sit_lote_contingencia.id == lote_id)
        if not facturas or len(facturas) != len(active_ids):
            raise UserError("Las facturas seleccionadas no pertenecen al mismo lote.")

        # Excluir facturas ya procesadas o con sello de recepción
        facturas = facturas.filtered(
            lambda f: not f.hacienda_selloRecibido and f.hacienda_estado != 'PROCESADO'
        )

        if not facturas:
            raise UserError("No hay facturas pendientes para reenviar en este lote.")

        errores = []
        reenviadas = []

        for factura in facturas:
            try:
                factura.reenviar_dte()
                reenviadas.append(factura.name)
            except Exception as e:
                errores.append(f"Factura {factura.name or factura.id}: {str(e)}")

        mensaje = []
        if reenviadas:
            mensaje.append(f"Facturas reenviadas correctamente ({len(reenviadas)}):\n" + "\n".join(reenviadas))
        if errores:
            mensaje.append(f"Errores en ({len(errores)}):\n" + "\n".join(errores))

        raise UserError("\n\n".join(mensaje))

