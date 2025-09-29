6##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from datetime import datetime
import base64
import pyqrcode

import pytz

from ..models.utils.decorators import only_fe

# Definir la zona horaria de El Salvador
tz_el_salvador = pytz.timezone('America/El_Salvador')


import logging
import json

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"



######################################### FCE-SUJETO EXCLUIDO
    @only_fe
    def sit_base_map_invoice_info_fse(self):
        _logger.info("SIT sit_base_map_invoice_info self FSE= %s", self)

        invoice_info = {}
        nit=self.company_id.vat
        nit = nit.replace("-", "")
        invoice_info["nit"] = nit
        invoice_info["activo"] = True
        invoice_info["passwordPri"] = self.company_id.sit_passwordPri
        _logger.info("SIT sit_base_map_invoice_info = %s", invoice_info)

        invoice_info["dteJson"] = self.sit__fse_base_map_invoice_info_dtejson()
        # if self.sit_json_respuesta and not self.hacienda_selloRecibido:
        #     try:
        #         # Intentamos convertir el sit_json_respuesta a un diccionario Python
        #         json_data = json.loads(self.sit_json_respuesta)
        #
        #         # Verificamos si el campo ambiente existe y es igual a "00"
        #         ambiente = json_data.get("identificacion", {}).get("ambiente", None)
        #
        #         if ambiente == "00":
        #             _logger.info("SIT Ambiente 00 detectado. Sobreescribiendo JSON.")
        #             invoice_info["dteJson"] = self.sit__fse_base_map_invoice_info_dtejson()
        #     except json.JSONDecodeError as e:
        #         _logger.error(f"SIT Error al procesar el JSON: {e}")
        #         invoice_info["dteJson"] = self.sit_json_respuesta  # En caso de error en la conversión, mantenemos el JSON original
        # if not self.hacienda_selloRecibido and self.sit_factura_de_contingencia and self.sit_json_respuesta:
        #     _logger.info("SIT sit_base_map_invoice_info contingencia")
        #     invoice_info["dteJson"] = self.sit_json_respuesta
        # else:
        #     _logger.info("SIT sit_base_map_invoice_info dte")
        #     invoice_info["dteJson"] = self.sit__fse_base_map_invoice_info_dtejson()
        return invoice_info

    @only_fe
    def sit__fse_base_map_invoice_info_dtejson(self):
        _logger.info("SIT sit_base_map_invoice_info_dtejson self FSE= %s", self)
        invoice_info = {}
        invoice_info["identificacion"] = self.sit__fse_base_map_invoice_info_identificacion()
        _logger.info("SIT sit_base_map_invoice_info_dtejson = %s", invoice_info)
        invoice_info["emisor"] = self.sit__fse_base_map_invoice_info_emisor()
        invoice_info["sujetoExcluido"] = self.sit__fse_base_map_invoice_info_sujeto_excluido()
        cuerpoDocumento = self.sit_fse_base_map_invoice_info_cuerpo_documento()
        _logger.info("SIT Cuerpo documento =%s", cuerpoDocumento)
        invoice_info["cuerpoDocumento"] = cuerpoDocumento[0]
        _logger.info("SIT CUERTO_DOCUMENTO = %s",   invoice_info["cuerpoDocumento"] )
        if str(invoice_info["cuerpoDocumento"]) == 'None':
            raise UserError(_('La Factura no tiene linea de Productos Valida.'))
        invoice_info["resumen"] = self.sit_fse_base_map_invoice_info_resumen()
        invoice_info["apendice"] = None
        _logger.info("RESUMEEEEEEEEn %s", self.sit_fse_base_map_invoice_info_resumen())

        return invoice_info

    @only_fe
    def sit__fse_base_map_invoice_info_identificacion(self):
        _logger.info("SIT sit_base_map_invoice_info_identificacion self FSE= %s", self)
        invoice_info = {}
        invoice_info["version"] = int(self.journal_id.sit_tipo_documento.version) #1
        validation_type = self._compute_validation_type_2()
        param_type = self.env["ir.config_parameter"].sudo().get_param("afip.ws.env.type")
        if param_type:
            validation_type = param_type
        if validation_type == 'homologation':
            ambiente = "00"
        else:
            ambiente = "01"
        invoice_info["ambiente"] = ambiente
        invoice_info["tipoDte"] = self.journal_id.sit_tipo_documento.codigo
        invoice_info["numeroControl"] = self.name
        _logger.info("SIT Número de control = %s", invoice_info["numeroControl"])
        _logger.info("SIT sit_base_map_invoice_info_identificacion0 = %s", invoice_info)
        invoice_info["codigoGeneracion"] = self.hacienda_codigoGeneracion_identificacion# self.sit_generar_uuid()          #  company_id.sit_uuid.upper()
        invoice_info["tipoModelo"] = int(self.journal_id.sit_modelo_facturacion)
        invoice_info["tipoOperacion"] = int(self.journal_id.sit_tipo_transmision)
        tipoContingencia = int(self.sit_tipo_contingencia)
        invoice_info["tipoContingencia"] = tipoContingencia
        _logger.info("SIT tipo de modelo= %s, tipo de operacion= %s", invoice_info["tipoModelo"], invoice_info["tipoOperacion"])

        motivoContin = str(self.sit_tipo_contingencia_otro)
        invoice_info["motivoContin"] = motivoContin
        import datetime
        import pytz
        import os
        os.environ['TZ'] = 'America/El_Salvador'  # Establecer la zona horaria
        datetime.datetime.now()
        salvador_timezone = pytz.timezone('America/El_Salvador')
        # FechaEmi = datetime.datetime.now(salvador_timezone)

        FechaEmi = None
        if self.invoice_date:
            FechaEmi = self.invoice_date
        else:
            FechaEmi = config_utils.get_fecha_emi()
        _logger.info("SIT FechaEmi = %s (%s)", FechaEmi, type(FechaEmi))

        invoice_info["fecEmi"] = FechaEmi # FechaEmi.strftime('%Y-%m-%d')
        invoice_info["horEmi"] = self.invoice_time # FechaEmi.strftime('%H:%M:%S')

        invoice_info["tipoMoneda"] =  self.currency_id.name
        if invoice_info["tipoOperacion"] == 1:
            invoice_info["tipoModelo"] = 1
            invoice_info["tipoContingencia"] = None
            invoice_info["motivoContin"] = None
        else:
            invoice_info["tipoModelo"] = 2
        if invoice_info["tipoOperacion"] == 2:
            invoice_info["tipoContingencia"] = tipoContingencia
        if invoice_info["tipoContingencia"] == 5:
            invoice_info["motivoContin"] = motivoContin
        _logger.info("SIT sit_fse_ base_map_invoice_info_identificacion1 = %s", invoice_info)
        return invoice_info

    @only_fe
    def sit__fse_base_map_invoice_info_emisor(self):
        _logger.info("SIT sit__fse_base_map_invoice_info_emisor self FSE= %s", self)
        invoice_info = {}
        direccion = {}
        nit=self.company_id.vat
        nit = nit.replace("-", "")
        invoice_info["nit"] = nit
        nrc= self.company_id.company_registry
        if nrc:
            nrc = nrc.replace("-", "")
        invoice_info["nrc"] = nrc
        invoice_info["nombre"] = self.company_id.name
        invoice_info["codActividad"] = self.company_id.codActividad.codigo
        invoice_info["descActividad"] = self.company_id.codActividad.valores
        direccion["departamento"] =  self.company_id.state_id.code
        direccion["municipio"] =  self.company_id.munic_id.code
        direccion["complemento"] =  self.company_id.street
        _logger.info("SIT direccion self = %s", direccion)
        invoice_info["direccion"] = direccion
        if  self.company_id.phone:
            invoice_info["telefono"] =  self.company_id.phone
        else:
            invoice_info["telefono"] =  None
        invoice_info["correo"] =  self.company_id.email
        invoice_info["codEstableMH"] =  self.journal_id.sit_codestable
        invoice_info["codEstable"] =  self.journal_id.sit_codestable
        invoice_info["codPuntoVentaMH"] =  self.journal_id.sit_codpuntoventa
        invoice_info["codPuntoVenta"] =  self.journal_id.sit_codpuntoventa
        return invoice_info

    @only_fe
    def sit__fse_base_map_invoice_info_sujeto_excluido(self):
        _logger.info("SIT sit_base_map_invoice_info_receptor self FSE= %s", self)
        direccion_rec = {}
        invoice_info = {}
       # Número de Documento (Nit)
        if self.partner_id and self.partner_id.dui:
            nit = self.partner_id.dui.replace("-", "") if self.partner_id.dui and isinstance(self.partner_id.dui, str) else None
        else:
            nit = self.partner_id.vat.replace("-", "") if self.partner_id.vat and isinstance(self.partner_id.vat, str) else None
        invoice_info["numDocumento"] = nit

        # Establece 'tipoDocumento' como None si 'nit' es None
        tipoDocumento = self.partner_id.l10n_latam_identification_type_id.codigo
        invoice_info["tipoDocumento"] = tipoDocumento
        nrc= self.partner_id.nrc
        if nrc:
            nrc = nrc.replace("-", "")
        invoice_info["nombre"] = self.partner_id.name
        codActividad = self.partner_id.codActividad.codigo if self.partner_id.codActividad and hasattr(self.partner_id.codActividad, 'codigo') else None
        invoice_info["codActividad"] = codActividad
        descActividad = self.partner_id.codActividad.valores if self.partner_id.codActividad and hasattr(self.partner_id.codActividad, 'valores') else None
        invoice_info["descActividad"] = descActividad
        direccion_rec["departamento"] = self.partner_id.state_id.code
        direccion_rec["municipio"] =   self.partner_id.munic_id.code
        direccion_rec["complemento"] =  self.partner_id.street
        _logger.info("SIT direccion self = %s", direccion_rec)
        invoice_info["direccion"] = direccion_rec
        if self.partner_id.phone:
            invoice_info["telefono"] =  self.partner_id.phone
        else:
            invoice_info["telefono"] = None
        if self.partner_id.email:
            invoice_info["correo"] =  self.partner_id.email
        else:
            invoice_info["correo"] = None
        return invoice_info

    @only_fe
    def sit_fse_base_map_invoice_info_cuerpo_documento(self):
            _logger.info("SIT sit_base_map_invoice_info_cuerpo_documento self FSE= %s", self)

            lines = []
            _logger.info("SIT sit_fse_base_map_invoice_info_cuerpo_documento self FSE= %s", self.invoice_line_ids)

            # for line in self.invoice_line_ids.filtered(lambda x: not x.display_type):
            item_numItem = 0
            total_Gravada = 0.0
            totalIva = 0.0
            uniMedida = None
            codigo_tributo_codigo = None
            codigo_tributo = None
            for line in self.invoice_line_ids:
                if not line.custom_discount_line:
                    item_numItem += 1
                    line_temp = {}
                    lines_tributes = []
                    line_temp["numItem"] = item_numItem
                    tipoItem = int(line.product_id.tipoItem.codigo or line.product_id.product_tmpl_id.tipoItem.codigo)
                    #Validación: tipoItem debe ser código 1, 2 o 3
                    # if tipoItem not in [1, 2, 3]:
                    #     raise UserError(
                    #         _("El producto '%s' tiene un tipo de ítem inválido: %s. Solo se permiten los valores 1, 2 o 3.") %
                    #         (line.product_id.name, tipoItem)
                    #     )
                    line_temp["tipoItem"] = tipoItem
                    line_temp["cantidad"] = line.quantity
                    line_temp["codigo"] = line.product_id.default_code
                    if not line.product_id:
                        _logger.error("Producto no configurado en la línea de factura.")
                        continue  # O puedes decidir manejar de otra manera
                    # unidad de referencia del producto si se comercializa
                    # en una unidad distinta a la de consumo
                    # uom is not mandatory, if no UOM we use "unit"
                    codTributo = line.product_id.tributos_hacienda_cuerpo.codigo
                    # if codTributo == False:
                    #     line_temp["codTributo"] = None
                    # else:
                    #     line_temp["codTributo"] = line.product_id.tributos_hacienda_cuerpo.codigo
                    _logger.info("SIT UOM =%s",  line.product_id)
                    if not line.product_id.uom_hacienda:
                        uniMedida = 7
                        raise UserError(
                            _("UOM de producto no configurado para:  %s" % (line.product_id.name))
                        )
                    else:
                        _logger.info("SIT uniMedida self = %s",  line.product_id)
                        _logger.info("SIT uniMedida self = %s",  line.product_id.uom_hacienda)

                        uniMedida = int(line.product_id.uom_hacienda.codigo)
                    if tipoItem == 2:
                        line_temp["uniMedida"] = 99
                    else:
                        line_temp["uniMedida"] = int(uniMedida)

                    line_temp["descripcion"] = line.name
                    line_temp["precioUni"] = round(line.price_unit,2)
                    # line_temp["importe"] = line.price_subtotal
                    # calculamos bonificacion haciendo teorico menos importe

                    line_temp["montoDescu"] = (
                        line_temp["cantidad"]  * (line.price_unit * (line.discount / 100))

                        or 0.0
                    )
                    for line_tributo in line.tax_ids:
                        codigo_tributo_codigo = line_tributo.tributos_hacienda.codigo
                        codigo_tributo = line_tributo.tributos_hacienda
                    lines_tributes.append(codigo_tributo_codigo)
                    # line_temp["tributos"] = lines_tributes
                    vat_taxes_amounts = line.tax_ids.compute_all(
                        line.price_unit,
                        self.currency_id,
                        line.quantity,
                        product=line.product_id,
                        partner=self.partner_id,
                    )
                    if vat_taxes_amounts['taxes']:
                        _logger.info("SIT vat_taxes_amounts 0=%s", vat_taxes_amounts['taxes'][0])
                        vat_taxes_amount = vat_taxes_amounts['taxes'][0]['amount']
                        sit_amount_base = round(vat_taxes_amounts['taxes'][0]['base'], 2)
                    else:
                        # Manejar el caso donde no hay impuestos
                        vat_taxes_amount = 0
                        sit_amount_base = round(line.quantity * line.price_unit, 2)
                    compraS = line_temp["cantidad"] * (line.price_unit - (line.price_unit * (line.discount / 100)))
                    line_temp["compra"] = round(compraS,2)
                    _logger.info("line_temp['compra']=%s", line_temp["compra"])

                    totalIva += 0

                    lines.append(line_temp)
                    self.check_parametros_linea_firmado(line_temp)
            return lines, codigo_tributo, total_Gravada, float(totalIva)

    @only_fe
    def sit_fse_base_map_invoice_info_resumen(self):
        _logger.info("SIT sit_base_map_invoice_info_resumen self FSE= %s", self)
        invoice_info = {}

        subtotal = sum(line.price_subtotal for line in self.invoice_line_ids)
        total = self.amount_total

        rete_iva = round(self.retencion_iva_amount or 0.0, 2)
        rete_renta = round(self.retencion_renta_amount or 0.0, 2)
        _logger.warning("SIT  RENTA RENTA= %s", rete_renta)
        _logger.warning("SIT  rete iva = %s", rete_iva)
        _logger.warning("SIT  total pagar resta = %s", self.total_operacion - (rete_renta + rete_iva))
        _logger.warning("SIT  total pagar = %s", self.total_operacion)

        monto_descu = 0.0

        for line in self.invoice_line_ids:
            taxes = line.tax_ids.compute_all(
                line.price_unit,
                self.currency_id,
                line.quantity,
                product=line.product_id,
                partner=self.partner_id,
            )

            monto_descu += round(line.quantity * (line.price_unit * (line.discount / 100)), 2)

        invoice_info["totalCompra"] = round(self.total_gravado , 2)
        invoice_info["descu"] = self.descuento_gravado # suma de descuento por item
        invoice_info["totalDescu"] = round(self.total_descuento,2) # suma de descuento por item (descu) + descuentos globales y por operacion

        invoice_info["subTotal"] = round(self.sub_total, 2)
        invoice_info["ivaRete1"] = round(rete_iva, 2)
        invoice_info["reteRenta"] = round(rete_renta, 2)
        invoice_info["totalPagar"] = round(self.total_pagar, 2)
        invoice_info["totalLetras"] = self.amount_text
        invoice_info["condicionOperacion"] = int(self.condiciones_pago)
        invoice_info["observaciones"] = None
        pagos = {}  # Inicializa el diccionario pagos
        pagos["codigo"] = self.forma_pago.codigo  # '01'   # CAT-017 Forma de Pago    01 = bienes
        pagos["montoPago"] = round(self.total_pagar, 2)
        pagos["referencia"] = None  # Un campo de texto llamado Referencia de pago
        if int(self.condiciones_pago) in [2]:
            pagos["plazo"] = self.sit_plazo.codigo
            pagos["periodo"] = self.sit_periodo   #30      #  Es un nuevo campo entero
            invoice_info["pagos"] = [pagos]  # Asigna pagos como un elemento de una lista
            pagos["montoPago"] = 0.00
        else:
            # pagos["plazo"] = self.sit_plazo.codigo 
            pagos["plazo"] = None    # Temporal
            pagos["periodo"] = None   #30      #  Es un nuevo campo entero
        invoice_info["pagos"] = [pagos]  # por ahora queda en null.

        # Validar forma de pago cuando condiciones_pago es 1 o 3
        if int(self.condiciones_pago) in [1, 3] and not self.forma_pago:
            raise UserError(
                _("Debe seleccionar una forma de pago para condiciones de operación Contado (1) u Otros (3)."))

        return invoice_info

    @only_fe
    def sit_obtener_payload_fse_dte_info(self,  ambiente, doc_firmado):
        _logger.info("SIT sit_obtener_payload_exp_dte_info self = %s", self)
        invoice_info = {}
        nit = self.company_id.vat
        nit = nit.replace("-", "")
        invoice_info["ambiente"] = ambiente
        invoice_info["idEnvio"] = 1
        invoice_info["version"] = 1
        if doc_firmado:
            invoice_info["documento"] = doc_firmado
        else:
            invoice_info["documento"] = None
        invoice_info["codigoGeneracion"] = self.sit_generar_uuid()
        return invoice_info

    @only_fe
    def sit_generar_uuid(self):
        import uuid
        # Genera un UUID versión 4 (basado en números aleatorios)
        uuid_aleatorio = uuid.uuid4()
        uuid_cadena = str(uuid_aleatorio)
        return uuid_cadena.upper()

    @only_fe
    def sit_debug_mostrar_json_fse(self):
        """Solo muestra el JSON generado de la factura FSE sin enviarlo."""
        if len(self) != 1:
            raise UserError("Selecciona una sola factura para depurar el JSON.")

        invoice_json = self.sit__fse_base_map_invoice_info_dtejson()

        import json
        pretty_json = json.dumps(invoice_json, indent=4, ensure_ascii=False)
        _logger.info("📄 JSON DTE FSE generado:\n%s", pretty_json)
        print("📄 JSON DTE FSE generado:\n", pretty_json)

        return True
