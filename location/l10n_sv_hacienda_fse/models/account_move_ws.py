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
import os
from odoo.tools import float_round
from ..models.utils.decorators import only_fe

# Definir la zona horaria de El Salvador
tz_el_salvador = pytz.timezone('America/El_Salvador')

import logging
import json
import uuid

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import config_utils
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo config_utils [hacienda_fse ws-account_move_ws]")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    config_utils = None
    constants = None

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
        if validation_type == constants.HOMOLOGATION:
            ambiente = constants.AMBIENTE_TEST
        else:
            ambiente = constants.PROD_AMBIENTE
        invoice_info["ambiente"] = ambiente
        invoice_info["tipoDte"] = self.journal_id.sit_tipo_documento.codigo
        invoice_info["numeroControl"] = self.name
        _logger.info("SIT Número de control = %s", invoice_info["numeroControl"])
        _logger.info("SIT sit_base_map_invoice_info_identificacion0 = %s", invoice_info)
        invoice_info["codigoGeneracion"] = self.hacienda_codigoGeneracion_identificacion
        invoice_info["tipoModelo"] = int(self.journal_id.sit_modelo_facturacion)
        invoice_info["tipoOperacion"] = int(self.journal_id.sit_tipo_transmision)
        tipoContingencia = int(self.sit_tipo_contingencia)
        invoice_info["tipoContingencia"] = tipoContingencia
        _logger.info("SIT tipo de modelo= %s, tipo de operacion= %s", invoice_info["tipoModelo"], invoice_info["tipoOperacion"])

        motivoContin = str(self.sit_tipo_contingencia_otro)
        invoice_info["motivoContin"] = motivoContin

        FechaEmi = None
        if self.invoice_date:
            FechaEmi = self.invoice_date
        else:
            FechaEmi = config_utils.get_fecha_emi()
        _logger.info("SIT FechaEmi = %s (%s)", FechaEmi, type(FechaEmi))

        invoice_info["fecEmi"] = FechaEmi # FechaEmi.strftime('%Y-%m-%d')
        invoice_info["horEmi"] = self.invoice_time # FechaEmi.strftime('%H:%M:%S')

        invoice_info["tipoMoneda"] =  self.currency_id.name
        if invoice_info["tipoOperacion"] == constants.TRANSMISION_NORMAL:
            invoice_info["tipoModelo"] = constants.MODELO_PREVIO
            invoice_info["tipoContingencia"] = None
            invoice_info["motivoContin"] = None
        else:
            invoice_info["tipoModelo"] = constants.MODELO_DIFERIDO
        if invoice_info["tipoOperacion"] == constants.TRANSMISION_CONTINGENCIA:
            invoice_info["tipoContingencia"] = tipoContingencia
        if invoice_info["tipoContingencia"] == constants.TIPO_CONTIN_OTRO:
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
        nit = None
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
        lines = []
        _logger.info("SIT sit_fse_base_map_invoice_info_cuerpo_documento self FSE= %s", self.invoice_line_ids)

        item_numItem = 0
        total_Gravada = 0.0
        totalIva = 0.0
        uniMedida = None
        codigo_tributo_codigo = None
        codigo_tributo = None

        for line in self.invoice_line_ids.filtered(lambda x: x.price_unit > 0):
            if not line.custom_discount_line:
                item_numItem += 1
                line_temp = {}
                lines_tributes = []
                line_temp["numItem"] = item_numItem
                tipoItem = int(line.product_id.tipoItem.codigo or line.product_id.product_tmpl_id.tipoItem.codigo)
                line_temp["tipoItem"] = tipoItem
                line_temp["cantidad"] = line.quantity
                line_temp["codigo"] = line.product_id.default_code
                if not line.product_id:
                    _logger.error("Producto no configurado en la línea de factura.")
                    continue  # O puedes decidir manejar de otra manera
                # unidad de referencia del producto si se comercializa en una unidad distinta a la de consumo
                codTributo = line.product_id.tributos_hacienda_cuerpo.codigo
                _logger.info("SIT UOM =%s",  line.product_id)
                if not line.product_id.uom_hacienda:
                    uniMedida = 7
                    raise UserError(
                        _("UOM de producto no configurado para:  %s" % (line.product_id.name))
                    )
                else:
                    _logger.info("SIT uniMedida self = %s",  line.product_id.uom_hacienda)

                    uniMedida = int(line.product_id.uom_hacienda.codigo)
                if tipoItem == constants.ITEM_SERVICIO:
                    line_temp["uniMedida"] = constants.UNI_MEDIDA_OTRA
                else:
                    line_temp["uniMedida"] = int(uniMedida)

                line_temp["descripcion"] = line.name
                line_temp["precioUni"] = float_round(line.price_unit, precision_rounding=line.move_id.currency_id.rounding)
                line_temp["montoDescu"] = (
                    line_temp["cantidad"]  * (line.price_unit * (line.discount / 100))
                    or 0.0
                )
                for line_tributo in line.tax_ids:
                    codigo_tributo_codigo = line_tributo.tributos_hacienda.codigo
                    codigo_tributo = line_tributo.tributos_hacienda
                lines_tributes.append(codigo_tributo_codigo)
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
                    sit_amount_base = float_round(vat_taxes_amounts['taxes'][0]['base'], precision_rounding=line.move_id.currency_id.rounding)
                else:
                    # Manejar el caso donde no hay impuestos
                    vat_taxes_amount = 0
                    sit_amount_base = float_round(line.quantity * line.price_unit, precision_rounding=line.move_id.currency_id.rounding)
                compraS = line_temp["cantidad"] * (line.price_unit - (line.price_unit * (line.discount / 100)))
                line_temp["compra"] = float_round(compraS, precision_rounding=line.move_id.currency_id.rounding)
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

        rete_iva = float_round(self.retencion_iva_amount or 0.0, precision_rounding=self.currency_id.rounding)
        rete_renta = float_round(self.retencion_renta_amount or 0.0, precision_rounding=self.currency_id.rounding)
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
            monto_descu += float_round(line.quantity * (line.price_unit * (line.discount / 100)), precision_rounding=self.currency_id.rounding)

        invoice_info["totalCompra"] = float_round(self.total_gravado , precision_rounding=self.currency_id.rounding)
        invoice_info["descu"] = self.descuento_gravado # suma de descuento por item
        invoice_info["totalDescu"] = float_round(self.total_descuento, precision_rounding=self.currency_id.rounding) # suma de descuento por item (descu) + descuentos globales y por operacion

        invoice_info["subTotal"] = float_round(self.sub_total, precision_rounding=self.currency_id.rounding)
        invoice_info["ivaRete1"] = float_round(rete_iva, precision_rounding=self.currency_id.rounding)
        invoice_info["reteRenta"] = float_round(rete_renta, precision_rounding=self.currency_id.rounding)
        invoice_info["totalPagar"] = float_round(self.total_pagar, precision_rounding=self.currency_id.rounding)
        invoice_info["totalLetras"] = self.amount_text
        invoice_info["condicionOperacion"] = int(self.condiciones_pago)
        invoice_info["observaciones"] = None
        pagos = {}  # Inicializa el diccionario pagos
        pagos["codigo"] = self.forma_pago.codigo  # '01'   # CAT-017 Forma de Pago    01 = bienes
        pagos["montoPago"] = float_round(self.total_pagar, precision_rounding=self.currency_id.rounding)
        pagos["referencia"] = None  # Un campo de texto llamado Referencia de pago
        if int(self.condiciones_pago) in [constants.PAGO_CREDITO]:
            pagos["plazo"] = self.sit_plazo.codigo
            pagos["periodo"] = self.sit_periodo   #30      #  Es un nuevo campo entero
            invoice_info["pagos"] = [pagos]  # Asigna pagos como un elemento de una lista
            pagos["montoPago"] = 0.00
        else:
            pagos["plazo"] = None    # Temporal
            pagos["periodo"] = None   #30      #  Es un nuevo campo entero
        invoice_info["pagos"] = [pagos]  # por ahora queda en null.

        # Validar forma de pago cuando condiciones_pago es 1 o 3
        if int(self.condiciones_pago) in [constants.PAGO_CONTADO, constants.PAGO_OTRO] and not self.forma_pago:
            raise UserError(_("Debe seleccionar una forma de pago para condiciones de operación Contado (1) u Otros (3)."))

        return invoice_info

    @only_fe
    def sit_obtener_payload_fse_dte_info(self,  ambiente, doc_firmado):
        _logger.info("SIT sit_obtener_payload_exp_dte_info self = %s", self)
        invoice_info = {}
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
        if not self.env.company.sit_facturacion:
            _logger.info("FE OFF: omitiendo sit_generar_uuid")
            return None
        # Genera un UUID versión 4 (basado en números aleatorios)
        uuid_aleatorio = uuid.uuid4()
        uuid_cadena = str(uuid_aleatorio)
        return uuid_cadena.upper()

    @only_fe
    def sit_debug_mostrar_json_fse(self):
        """Solo muestra el JSON generado de la factura FSE sin enviarlo."""

        # 1 Validar que solo haya una factura seleccionada
        if len(self) != 1:
            raise UserError("Selecciona una sola factura para depurar el JSON.")

        # 2 Validar que aplique solo para compras (in_invoice) con tipo de documento código 14 (FSE)
        tipo_doc = self.journal_id.sit_tipo_documento
        if self.move_type != constants.IN_INVOICE or (tipo_doc and tipo_doc.codigo != constants.COD_DTE_FSE):
            _logger.info(
                "SIT: omitiendo generación de JSON — aplica solo para compras FSE (in_invoice, código 14). "
                "Tipo actual: %s, Código: %s",
                self.move_type, tipo_doc.codigo if tipo_doc else None
            )
            return True

        # 3 Si la facturación electrónica está desactivada, no hacemos nada
        if not self.env.company.sit_facturacion:
            _logger.info("FE OFF: omitiendo sit_debug_mostrar_json_fse")
            return True  # no bloquea la UI

        # 4 Generar y mostrar el JSON FSE
        invoice_json = self.sit__fse_base_map_invoice_info_dtejson()
        pretty_json = json.dumps(invoice_json, indent=4, ensure_ascii=False)
        _logger.info("📄 JSON DTE FSE generado:\n%s", pretty_json)
        print("📄 JSON DTE FSE generado:\n", pretty_json)
        return True
