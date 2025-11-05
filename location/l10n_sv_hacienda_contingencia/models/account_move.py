# -*- coding: utf-8 -*-
import base64

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
    # sit_tipo_contingencia = fields.Many2one('account.move.tipo_contingencia.field', string="Tipo de Contingencia")
    sit_tipo_contingencia = fields.Many2one(related='sit_factura_de_contingencia.sit_tipo_contingencia', string="Tipo de Contingencia")
    sit_tipo_contingencia_otro = fields.Text(related='sit_factura_de_contingencia.sit_tipo_contingencia_otro', string="Especifique el Otro Tipo de Contingencia")
    sit_tipo_contingencia_valores = fields.Char(related="sit_factura_de_contingencia.sit_tipo_contingencia_valores", string="Tipo de contingiancia(nombre)")
    sit_factura_de_contingencia = fields.Many2one('account.contingencia1', string="Referencia de contingencia", ondelete="set null")
    sit_es_configencia = fields.Boolean('Contingencia',  copy=False,)
    sit_factura_por_lote = fields.Boolean('Facturado por lote ?',  copy=False, default=False)
    sit_documento_firmado = fields.Text(string="Documento Firmado", copy=False, readonly=True)
    sit_lote_contingencia = fields.Many2one('account.lote', string="Factura asignada en el lote", ondelete="set null")
    sit_bloque_contingencia = fields.Many2one('account.contingencia.bloque', string='Bloque de Factura')

    # @api.onchange('sit_es_configencia')
    # def check_sit_es_configencia(self):
    #     _logger.info("SIT revisando  si es o no sit_es_configencia  <---------------------------------------------")
    #     if self.sit_es_configencia:
    #         _logger.info("SIT sit_es_configencia")
    #         #self.sit_block_hacienda = True
    #     else:
    #         _logger.info("SIT NO sit_es_configencia")
    #         #self.sit_block_hacienda = False

# ---------------------------------------------------------------------------------------------
# LOTES DE CONTINGENCIA
#---------------------------------------------------------------------------------------------
    def action_post_contingencia_validation(self):
        '''validamos que partner cumple los requisitos basados en el tipo
        de documento de la sequencia del diario selecionado
        FACTURA ELECTRONICAMENTE
        '''
        _logger.info("SIT action_post_contingencia_validation Validacion de contingencia =%s", self.id)
        for invoice in self:

            MENSAJE = "action_post_contingencia -->" + str(self.name)
            # raise UserError(_(MENSAJE))
            if invoice.name == "/" or not invoice.name:
                NUMERO_FACTURA = invoice._set_next_sequence()
            else:
                NUMERO_FACTURA = "/"
            _logger.info("SIT NUMERO FACTURA =%s", NUMERO_FACTURA)
            if invoice.sit_es_configencia and invoice.company_id.sit_facturacion:
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

    def reenviar_dte(self):
        self.ensure_one()
        _logger.info(f"SIT reenviar_dte iniciado para factura ID {self.id}")

        resultado_final = {
            "exito": False,
            "mensaje": "",
            "resultado_mh": None
        }
        actualizar_informacion_dte = False

        ambiente_test = False
        if config_utils:
            ambiente_test = config_utils._compute_validation_type_2(self.env, self.company_id)
            _logger.info("SIT Validaciones[Ambiente]: %s", ambiente_test)

        _logger.info("SIT Partner: %s | Parent: %s", self.invoice_user_id.partner_id.vat, self.invoice_user_id.partner_id.parent_id.vat)
        try:
            if not self.hacienda_codigoGeneracion_identificacion:
                raise Exception("No tiene código de generación.")

            payload = None
            ambiente = config_utils.compute_validation_type_2(self.env) if config_utils else None
            _logger.info(f"SIT Ambiente calculado: {ambiente}")

            # Firmar solo si no está firmado
            if not ambiente_test and not self.sit_documento_firmado:
                _logger.info("Documento no firmado. Se procede a firmar.")
                payload = self.obtener_payload(ambiente, self.journal_id.sit_tipo_documento.codigo)
                _logger.info(f"Payload para firma obtenido: {payload}")
                documento_firmado = self.firmar_documento(ambiente, payload)
                if not documento_firmado:
                    _logger.warning("Error en firma del documento: documento_firmado vacío o nulo")
                    raise Exception("Error en firma del documento")
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
            self.check_parametros_dte(payload_dte, ambiente_test)

            _logger.info("Generando DTE en Hacienda")
            Resultado = self.generar_dte(ambiente, payload_dte, payload, ambiente_test)
            _logger.info(f"Resultado generado: {Resultado}")

            if not Resultado:
                _logger.warning("Resultado de generación DTE vacío o nulo")
                raise Exception("Error al generar DTE: Resultado vacío o nulo.")

            estado = Resultado.get('estado', '').strip().lower()
            _logger.info(f"Estado del DTE: {estado}")

            # Revisa si el rechazo es por número de control duplicado
            descripcion = Resultado.get('descripcionMsg', '').lower()
            if 'identificacion.numerocontrol' in descripcion:
                _logger.warning("SIT DTE rechazado por número de control duplicado. Generando nuevo número.")

                actualizar_informacion_dte = True
                # Generar nuevo número de control
                nuevo_nombre = self._generate_dte_name(actualizar_secuencia=True)
                # Verifica si el nuevo nombre es diferente antes de actualizar
                if nuevo_nombre != self.name:
                    _logger.info("SIT Actualizando nombre DTE: %s a %s", self.name, nuevo_nombre)
                    self.write({'name': nuevo_nombre})  # Actualiza el nombre
                    self.write({'sit_json_respuesta': None})
                    self.sequence_number = int(nuevo_nombre.split("-")[-1])
                    _logger.info("SIT name actualizado: %s | sequence number: %s", self.name, self.sequence_number)

                    # Forzar un commit explícito a la base de datos
                    self._cr.commit()
                else:
                    _logger.info("SIT El nombre ya está actualizado, no se requiere escribir.")

                # Reemplazar numeroControl en el payload original
                payload['dteJson']['identificacion']['numeroControl'] = nuevo_nombre

                # Volver a firmar con el nuevo número
                documento_firmado = self.firmar_documento(ambiente, payload)

                if not documento_firmado:
                    raise UserError(_('SIT Documento NO Firmado después de reintento con nuevo número de control'))

                # Intentar nuevamente generar el DTE
                payload_dte = self.sit_obtener_payload_dte_info(ambiente, documento_firmado)
                self.check_parametros_dte(payload_dte, ambiente_test)
                Resultado = self.generar_dte(ambiente, payload_dte, payload, ambiente_test)
                estado = Resultado.get('estado', '').strip().lower() if Resultado else None
            else:
                actualizar_informacion_dte = False

            # Guardar json generado
            json_dte = payload.get('dteJson') if payload else None
            try:
                if not self.sit_json_respuesta or actualizar_informacion_dte:
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

            _logger.info("Estado: %s", estado)
            if estado and estado.lower() == 'procesado':
                _logger.info("Estado procesado, actualizando secuencia y datos...")
                self.actualizar_secuencia()

                # Fecha procesamiento MH
                fh_procesamiento = None
                if Resultado.get('fhProcesamiento') and not ambiente_test:
                    fh_procesamiento = Resultado.get('fhProcesamiento')
                if not fh_procesamiento:
                    fh_procesamiento = self.invoice_time

                if fh_procesamiento:
                    try:
                        fh_dt = datetime.strptime(fh_procesamiento, '%d/%m/%Y %H:%M:%S') + timedelta(hours=6)
                        if not self.fecha_facturacion_hacienda:
                            self.write({'fecha_facturacion_hacienda': fh_dt})
                            _logger.info(f"Fecha facturacion actualizada: {self.fecha_facturacion_hacienda}")
                    except Exception as e:
                        _logger.warning(f"Error al parsear fhProcesamiento: {e}")

                if ambiente_test:
                    self.write({
                        'hacienda_estado': Resultado['estado'],
                        'hacienda_descripcionMsg': Resultado.get('descripcionMsg'),
                        'hacienda_observaciones': str(Resultado.get('observaciones', '')),
                        'state': 'posted',
                    })
                else:
                    self.write({
                        'hacienda_estado': Resultado['estado'],
                        'hacienda_selloRecibido': Resultado.get('selloRecibido'),
                        'hacienda_clasificaMsg': Resultado.get('clasificaMsg'),
                        'hacienda_codigoMsg': Resultado.get('codigoMsg'),
                        'hacienda_descripcionMsg': Resultado.get('descripcionMsg'),
                        'hacienda_observaciones': str(Resultado.get('observaciones', '')),
                        'state': 'posted',
                        'recibido_mh': True,
                        'sit_json_respuesta': self.sit_json_respuesta,
                    })

                    qr_code = self._generar_qr(ambiente, self.hacienda_codigoGeneracion_identificacion, self.fecha_facturacion_hacienda)
                    self.sit_qr_hacienda = qr_code
                    self.sit_documento_firmado = documento_firmado
                    _logger.info("QR generado y firma guardada")

                    try:
                        json_original = json.loads(self.sit_json_respuesta) if self.sit_json_respuesta else {}
                    except json.JSONDecodeError:
                        json_original = {}
                        _logger.warning("No se pudo cargar sit_json_respuesta para fusionar JSONRespuestaMh")

                    json_original.update({"jsonRespuestaMh": Resultado})
                    self.sit_json_respuesta = json.dumps(json_original)
                    _logger.info("JSON respuesta MH fusionado correctamente")
                _logger.info("Campos MH actualizados correctamente")

                resultado_final["exito"] = True
                resultado_final["mensaje"] = "Procesado correctamente"
                resultado_final["resultado_mh"] = Resultado

                try:
                    json_str = json.dumps(json_dte, ensure_ascii=False, default=str)
                    json_base64 = base64.b64encode(json_str.encode('utf-8'))
                    file_name = json_dte.get("identificacion", {}).get("numeroControl", "dte") + '.json'
                    self.env['ir.attachment'].sudo().create({
                        'name': file_name,
                        'datas': json_base64,
                        'res_model': self._name,
                        'res_id': self.id,
                        'company_id': self.company_id.id,
                        'mimetype': str(config_utils.get_config_value(self.env, 'content_type', self.company_id.id)),
                    })
                    _logger.info("SIT JSON creado y adjuntado como attachment")
                except Exception as e:
                    _logger.warning(f"Error al crear o adjuntar JSON: {e}")

                try:
                    self.with_context(from_button=False, from_invalidacion=False).sit_enviar_correo_dte_automatico()
                    _logger.info("Correo con PDF enviado exitosamente")
                except Exception as e:
                    _logger.warning(f"SIT | Error al enviar DTE por correo o generar PDF: {e}")

            else:
                resultado_final["mensaje"] = Resultado.get('descripcionMsg') or "Error en procesamiento MH"
                resultado_final["resultado_mh"] = Resultado

        except Exception as e:
            resultado_final["mensaje"] = str(e)
        return resultado_final

    def action_reenviar_facturas_lote(self):
        _logger.info("Inicio reenvio del dte a MH, ID lote: %s, ID bloque: %s:", self.mapped('sit_lote_contingencia.id'), self.mapped('sit_bloque_contingencia.id'))

        usa_lote = self.company_id.sit_usar_lotes_contingencia

        active_ids = self.env.context.get('active_ids')
        if not active_ids:
            mensaje = "Debe seleccionar al menos un documento."
            _logger.warning(mensaje)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Validación',
                    'message': mensaje,
                    'type': 'warning',
                    'sticky': False,
                }
            }

        facturas = self.env['account.move'].browse(active_ids)

        # Validar que todas las facturas están en el mismo lote o bloque
        if not facturas or len(facturas) != len(active_ids):
            mensaje = f"Los documentos electrónicos seleccionados no pertenecen al mismo {'lote' if usa_lote else 'bloque'}."
            _logger.warning(mensaje)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Validación',
                    'message': mensaje,
                    'type': 'warning',
                    'sticky': False,
                }
            }

        # Validar por lote o bloque
        if self.company_id.sit_usar_lotes_contingencia:
            # Validación por lote
            lote_ids = facturas.mapped('sit_lote_contingencia.id')
            lotes = self.env['account.lote'].browse(lote_ids)
            if len(set(lote_ids)) != 1:
                mensaje =  "Los documentos electrónicos seleccionados no pertenecen al mismo lote."
                _logger.warning(mensaje)
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Validación lote',
                        'message': mensaje,
                        'type': 'warning',
                        'sticky': False,
                    }
                }

            # Validar que esos lotes tengan el sello y código
            lotes_no_procesados = [
                lote for lote in lotes
                if not (
                        (lote.lote_recibido_mh and lote.hacienda_codigoLote_lote)
                        or (lote.hacienda_estado_lote or '').strip().upper() == "RECIBIDO"
                )
            ]

            if lotes_no_procesados:
                mensaje = "Existen lotes pendientes de envío o no procesados. No se permite reenviar hasta que se procesen."
                _logger.warning(mensaje)
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Lotes Pendientes',
                        'message': mensaje,
                        'type': 'warning',
                        'sticky': False,
                    }
                }
        else:
            # Si no se usan lotes, verificar por bloque
            bloque_ids = facturas.mapped('sit_bloque_contingencia.id')

            if len(set(bloque_ids)) != 1:
                mensaje = "Los documentos seleccionados no pertenecen al mismo bloque."
                _logger.warning(mensaje)
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Validación bloque',
                        'message': mensaje,
                        'type': 'warning',
                        'sticky': False,
                    }
                }

        # Filtrar facturas que pertenecen al lote o bloque
        if self.company_id.sit_usar_lotes_contingencia:
            # Filtrar facturas que pertenezcan al lote
            facturas = facturas.filtered(lambda f: f.sit_lote_contingencia.id == lote_ids[0])
        else:
            # Filtrar facturas que pertenezcan al bloque
            facturas = facturas.filtered(lambda f: f.sit_bloque_contingencia.id == bloque_ids[0])

        # Excluir facturas ya procesadas o con sello de recepción
        facturas = facturas.filtered(
            lambda f: not f.hacienda_selloRecibido)

        if not facturas:
            mensaje = "No hay documentos electrónicos pendientes para reenviar."
            _logger.warning(mensaje)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Validación',
                    'message': mensaje,
                    'type': 'warning',
                    'sticky': False,
                }
            }

        resultados_ok = []
        resultados_error = []

        # Reenvío de las facturas
        for factura in facturas:
            try:
                resultado = factura.reenviar_dte()
                if resultado["exito"]:
                    resultados_ok.append(factura.name)
                else:
                    resultados_error.append(f"Documento electrónico {factura.name}: {resultado['mensaje']}")
            except Exception as e:
                resultados_error.append(f"Documento electrónico {factura.name}: Excepción {str(e)}")

        mensaje = []
        if resultados_ok:
            mensaje.append(f"Documentos electrónicos reenviados correctamente ({len(resultados_ok)}):\n" + "\n".join(resultados_ok))
        if resultados_error:
            mensaje.append(f"Errores en ({len(resultados_error)}):\n" + "\n".join(resultados_error))

        _logger.info("\n".join(mensaje))

        # Notificación de resultado
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Resultado Reenvío',
                'message': "\n".join(mensaje),
                'type': 'info',
                'sticky': False,
            },
        }
