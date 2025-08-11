##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from typing import Any

import pytz
import os
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import base64
import pyqrcode
import logging

import re
import json
_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import config_utils
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo config_utils hacienda ws")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    config_utils = None

class AccountMove(models.Model):
    _inherit = "account.move"

    def _get_config_cache(self):
        if not hasattr(self, '_config_cache'):
            self._config_cache = {}
        return self._config_cache

    def valor_iva_config(self):
        if config_utils:
            try:
                valor = config_utils.get_config_value(self.env, 'valor_iva', self.company_id.id)
                return float(valor) if valor else 0.13  # Valor por defecto si no hay valor
            except Exception as e:
                raise UserError(_("Error al obtener configuración 'valor_iva': %s") % str(e))
        return 0.13  # Valor por defecto si falla import

    def get_valor_iva_divisor_config(self):
        self.ensure_one()
        if config_utils:
            try:
                valor = config_utils.get_config_value(self.env, 'iva_divisor', self.company_id.id)
                return float(valor) if valor else 1.13
            except Exception as e:
                raise UserError(_("Error al obtener configuración 'iva_divisor': %s" % str(e)))
        return 1.13  # Valor por defecto

    ##------ FEL-COMPROBANTE CREDITO FISCAL----------##

    def sit_debug_mostrar_json_fe(self):
        """Solo muestra el JSON generado de la factura FSE sin enviarlo."""
        if len(self) != 1:
            raise UserError("Selecciona una sola factura para depurar el JSON.")

        invoice_json = self.sit__ccf_base_map_invoice_info_dtejson()

        import json
        pretty_json = json.dumps(invoice_json, indent=4, ensure_ascii=False)
        _logger.info("📄 JSON DTE FSE generado:\n%s", pretty_json)
        print("📄 JSON DTE FSE generado:\n", pretty_json)

        return True

    def sit__ccf_base_map_invoice_info(self):
        invoice_info = {}
        nit = None
        if self.company_id and self.company_id.vat:
            nit = self.company_id.vat.replace("-", "")

        invoice_info["nit"] = nit
        invoice_info["activo"] = True
        invoice_info["passwordPri"] = self.company_id.sit_passwordPri
        invoice_info["dteJson"] = self.sit__ccf_base_map_invoice_info_dtejson()
        return invoice_info

    def sit__ccf_base_map_invoice_info_dtejson(self):
        invoice_info = {}
        invoice_info["identificacion"] = self.sit__ccf_base_map_invoice_info_identificacion()
        invoice_info["documentoRelacionado"] = None  # self.sit__ccf_base_map_invoice_info_documentoRelacionado()
        invoice_info["emisor"] = self.sit__ccf_base_map_invoice_info_emisor()
        invoice_info["receptor"] = self.sit__ccf_base_map_invoice_info_receptor()
        invoice_info["otrosDocumentos"] = None
        invoice_info["ventaTercero"] = None
        cuerpoDocumento = self.sit_ccf_base_map_invoice_info_cuerpo_documento()
        invoice_info["cuerpoDocumento"] = cuerpoDocumento[0]
        if str(invoice_info["cuerpoDocumento"]) == 'None':
            raise UserError(_('La Factura no tiene linea de Productos Valida.'))
        _logger.info("SIT total_iva = %s", cuerpoDocumento[4])
        invoice_info["resumen"] = self.sit_ccf_base_map_invoice_info_resumen(cuerpoDocumento[2], cuerpoDocumento[3],
                                                                             cuerpoDocumento[4],
                                                                             invoice_info["identificacion"])
        invoice_info["extension"] = self.sit_ccf_base_map_invoice_info_extension()
        invoice_info["apendice"] = None
        return invoice_info

    def sit__ccf_base_map_invoice_info_identificacion(self):
        invoice_info = {}
        invoice_info["version"] = int(self.journal_id.sit_tipo_documento.version)  # 3

        # ——————————————————————
        # Ambiente y validación
        ambiente = None
        if config_utils:
            ambiente = config_utils.compute_validation_type_2(self.env)
        invoice_info["ambiente"] = ambiente
        invoice_info["tipoDte"] = self.journal_id.sit_tipo_documento.codigo
        invoice_info["numeroControl"] = self.name

        # ——————————————————————
        # UUID, modelo, operación
        invoice_info["codigoGeneracion"] = self.hacienda_codigoGeneracion_identificacion  # self.sit_generar_uuid()
        invoice_info["tipoModelo"] = int(self.journal_id.sit_modelo_facturacion)
        invoice_info["tipoOperacion"] = int(self.journal_id.sit_tipo_transmision)

        # ——————————————————————
        # Contingencia
        invoice_info["tipoContingencia"] = int(self.sit_tipo_contingencia or 0)
        invoice_info["motivoContin"] = str(self.sit_tipo_contingencia_otro or "")

        # ——————————————————————
        # Fecha y hora de emisión
        FechaEmi = None
        if self.invoice_date:
            FechaEmi = self.invoice_date
        else:
            FechaEmi = config_utils.get_fecha_emi()
        _logger.info("SIT FechaEmi= %s", FechaEmi)
        invoice_info["fecEmi"] = FechaEmi
        invoice_info["horEmi"] = self.invoice_time

        invoice_info["tipoMoneda"] = self.currency_id.name

        # ——————————————————————
        # Ajustes finales
        if invoice_info["tipoOperacion"] == constants.TRANSMISION_NORMAL:
            invoice_info["tipoModelo"] = 1
            invoice_info["tipoContingencia"] = None
            invoice_info["motivoContin"] = None
        else:
            invoice_info["tipoModelo"] = 2
            if invoice_info["tipoContingencia"] != constants.TIPO_CONTIN_OTRO:
                invoice_info["motivoContin"] = None

        # ——————————————————————
        # Log final
        try:
            _logger.info(
                "SIT CCF Identificación — payload final:\n%s",
                json.dumps(invoice_info, indent=2, ensure_ascii=False),
            )
        except Exception as e:
            _logger.error("SIT Error al serializar payload final: %s", e)

        return invoice_info

    def sit__ccf_base_map_invoice_info_documentoRelacionado(self):
        invoice_info = {}
        return invoice_info

    def sit__ccf_base_map_invoice_info_emisor(self):
        invoice_info = {}
        direccion = {}
        nit = self.company_id.vat.replace("-", "") if self.company_id and self.company_id.vat else None
        invoice_info["nit"] = nit

        nrc = self.company_id.company_registry if self.company_id and self.company_id.company_registry else None
        if nrc:
            nrc = nrc.replace("-", "")
        invoice_info["nrc"] = nrc
        invoice_info["nombre"] = self.company_id.name
        invoice_info["codActividad"] = self.company_id.codActividad.codigo
        invoice_info["descActividad"] = self.company_id.codActividad.valores
        if self.company_id.nombre_comercial:
            invoice_info["nombreComercial"] = self.company_id.nombre_comercial
        else:
            invoice_info["nombreComercial"] = None
        invoice_info["tipoEstablecimiento"] = self.company_id.tipoEstablecimiento.codigo
        direccion["departamento"] = self.company_id.state_id.code
        direccion["municipio"] = self.company_id.munic_id.code
        direccion["complemento"] = self.company_id.street
        invoice_info["direccion"] = direccion
        if self.company_id.phone:
            invoice_info["telefono"] = self.company_id.phone
        else:
            invoice_info["telefono"] = None
        invoice_info["correo"] = self.company_id.email
        invoice_info["codEstableMH"] = self.journal_id.sit_codestable
        invoice_info["codEstable"] = self.journal_id.sit_codestable
        invoice_info["codPuntoVentaMH"] = self.journal_id.sit_codpuntoventa
        invoice_info["codPuntoVenta"] = self.journal_id.sit_codpuntoventa
        return invoice_info

    def sit__ccf_base_map_invoice_info_receptor(self):
        _logger.info("SIT sit_base_map_invoice_info_receptor self = %s", self)
        direccion_rec = {}
        invoice_info = {}
        nit = self.partner_id.vat if self.partner_id and self.partner_id.vat else None
        _logger.info("SIT Documento receptor = %s", self.partner_id.dui)

        if isinstance(nit, str):
            nit = nit.replace("-", "")
            invoice_info["nit"] = nit

        nrc = self.partner_id.nrc if self.partner_id and self.partner_id.nrc else None
        if isinstance(nrc, str):
            nrc = nrc.replace("-", "")
        invoice_info["nrc"] = nrc
        invoice_info["nombre"] = self.partner_id.name
        invoice_info["codActividad"] = self.partner_id.codActividad.codigo
        invoice_info["descActividad"] = self.partner_id.codActividad.valores
        if self.partner_id.nombreComercial:
            invoice_info["nombreComercial"] = self.partner_id.nombreComercial
        else:
            invoice_info["nombreComercial"] = None
        if self.partner_id.state_id.code:
            direccion_rec["departamento"] = self.partner_id.state_id.code
        else:
            direccion_rec["departamento"] = None
        if self.partner_id.munic_id.code:
            direccion_rec["municipio"] = self.partner_id.munic_id.code
        else:
            direccion_rec["municicipio"] = None
        if self.partner_id.street2:
            direccion_rec["complemento"] = self.partner_id.street2
        else:
            direccion_rec["complemento"] = None
        invoice_info["direccion"] = direccion_rec
        if self.partner_id.phone:
            invoice_info["telefono"] = self.partner_id.phone
        else:
            invoice_info["telefono"] = None
        if self.partner_id.email:
            invoice_info["correo"] = self.partner_id.email
        else:
            invoice_info["correo"] = None
        return invoice_info

    def sit_ccf_base_map_invoice_info_cuerpo_documento(self):
        lines = []
        item_numItem = 0
        total_Gravada = 0.0
        totalIva = 0.0
        codigo_tributo = None
        ventaGravada = 0.0
        ventaExenta = 0.0

        for line in self.invoice_line_ids.filtered(lambda x: x.price_unit > 0):
            item_numItem += 1
            line_temp = {}
            lines_tributes = []
            line_temp["numItem"] = item_numItem
            tipoItem = int(line.product_id.tipoItem.codigo or line.product_id.product_tmpl_id.tipoItem.codigo)
            line_temp["tipoItem"] = tipoItem
            line_temp["numeroDocumento"] = None
            line_temp["codigo"] = line.product_id.default_code
            codTributo = line.product_id.tributos_hacienda_cuerpo.codigo
            line_temp["codTributo"] = codTributo if codTributo else None
            line_temp["descripcion"] = line.name
            line_temp["cantidad"] = line.quantity

            # Validación UOM
            if not line.product_id.uom_hacienda:
                raise UserError(_("UOM de producto no configurado para:  %s" % (line.product_id.name)))
            uniMedida = int(line.product_id.uom_hacienda.codigo)
            line_temp["uniMedida"] = uniMedida

            # line_temp["precioUni"] = round(line.price_unit, 4)
            line_temp["montoDescu"] = round(line_temp["cantidad"] * (line.price_unit * (line.discount / 100)),
                                            2) or 0.0  # round(line_temp["cantidad"] * (line.price_unit * (line.discount / 100)) / 1.13 ,2) or 0.0
            line_temp["ventaNoSuj"] = round(line.precio_no_sujeto, 2)  # 0.0
            line_temp["ventaExenta"] = round(line.precio_exento, 2)  # 0.0

            # ventaGravada = round(line_temp["cantidad"] * (line.price_unit - (line.price_unit * (line.discount / 100))),2)
            # line_temp["ventaGravada"] = ventaGravada

            # Calcular tributos
            for line_tributo in line.tax_ids.filtered(lambda x: x.tributos_hacienda):
                codigo_tributo = line_tributo.tributos_hacienda  # ← Se asigna el objeto, no solo el código
                codigo_tributo_codigo = line_tributo.tributos_hacienda.codigo
                lines_tributes.append(codigo_tributo_codigo)

            # Cálculo de IVA
            vat_taxes_amounts = line.tax_ids.compute_all(
                line.precio_unitario,
                self.currency_id,
                line.quantity,
                product=line.product_id,
                partner=self.partner_id,
            )
            vat_taxes_amount = 0.0
            sit_amount_base = 0.0
            if vat_taxes_amounts and vat_taxes_amounts.get('taxes') and len(vat_taxes_amounts['taxes']) > 0:
                vat_taxes = vat_taxes_amounts.get('taxes', [])
                vat_taxes_amount = vat_taxes[0].get('amount', 0.0) if vat_taxes else self.valor_iva_config()
                sit_amount_base = round(vat_taxes[0].get('base', 0.0), 2) if vat_taxes else self.valor_iva_config()

            line_temp['psv'] = line.product_id.sit_psv
            line_temp["noGravado"] = 0.0

            price_unit = 0.0
            _logger.info("SIT sit_amount_base= %s", sit_amount_base)
            if line_temp["cantidad"] > 0:
                price_unit = round(sit_amount_base / line_temp["cantidad"], 4)
            else:
                price_unit = 0.00
            line_temp["precioUni"] = round(line.precio_unitario, 2)

            ventaGravada = round(line.precio_gravado,
                                 2)  # round((sit_amount_base - (line.price_unit * (line.discount / 100))), 2)
            total_Gravada += ventaGravada
            line_temp["ventaGravada"] = ventaGravada

            if line.product_id and line.product_id.tipo_venta:
                if line.product_id.tipo_venta == constants.TIPO_VENTA_PROD_GRAV:
                    line_temp["ventaNoSuj"] = 0.0
                    line_temp["ventaExenta"] = 0.0
                elif line.product_id.tipo_venta == constants.TIPO_VENTA_PROD_EXENTO:
                    line_temp["ventaNoSuj"] = 0.0
                    line_temp["ventaGravada"] = 0.0
                elif line.product_id.tipo_venta ==TIPO_VENTA_PROD_GRAV:
                    line_temp["ventaExenta"] = 0.0
                    line_temp["ventaGravada"] = 0.0

            # Tributos según tipo de item
            if ventaGravada == 0.0:
                line_temp["tributos"] = None
            elif tipoItem == 4:
                line_temp["uniMedida"] = 99
                line_temp["codTributo"] = codTributo
                line_temp["tributos"] = [20]
            else:
                line_temp["codTributo"] = None
                line_temp["tributos"] = lines_tributes

            totalIva += round(
                vat_taxes_amount - ((((line.precio_unitario * line.quantity) * (
                            line.discount / 100)) / self.get_valor_iva_divisor_config()) * self.valor_iva_config()),
                2)

            lines.append(line_temp)
            self.check_parametros_linea_firmado(line_temp)

        return lines, codigo_tributo, total_Gravada, line.tax_ids, totalIva

    def sit_ccf_base_map_invoice_info_resumen(self, total_Gravada, total_tributos, totalIva, identificacion):
        _logger.info("SIT sit_base_map_invoice_info_resumen self = %s", self)
        total_des = 0
        por_des = 0
        for line in self.invoice_line_ids.filtered(lambda x: x.price_unit < 0):
            total_des += (line.precio_unitario * -1 / self.get_valor_iva_divisor_config())
        if total_des:
            total_gral = self.amount_total + (total_des)
            por_des = 100 - round(((total_gral - (total_des * self.get_valor_iva_divisor_config())) / total_gral) * 100)
        else:
            total_des = self.descuento_gravado
        invoice_info = {}
        tributos = {}
        pagos = {}
        invoice_info["totalNoSuj"] = round(self.total_no_sujeto, 2)  # 0
        invoice_info["totalExenta"] = round(self.total_exento, 2)  # 0
        invoice_info["totalGravada"] = round(total_Gravada, 2)
        invoice_info["subTotalVentas"] = round(self.sub_total_ventas, 2)
        invoice_info["descuNoSuj"] = round(self.descuento_no_sujeto, 2)  # 0
        invoice_info["descuExenta"] = round(self.descuento_exento, 2)  # 0
        invoice_info["descuGravada"] = round(total_des, 2)
        invoice_info["porcentajeDescuento"] = por_des
        invoice_info["totalDescu"] = round(self.total_descuento, 2)  # 0
        _logger.info("SIT  identificacion[tipoDte] = %s", identificacion['tipoDte'])
        _logger.info("SIT  identificacion[tipoDte] = %s", identificacion)
        _logger.info("SIT resumen totalIVA ========================== %s", totalIva)
        tributos["codigo"] = total_tributos.tributos_hacienda.codigo
        tributos["descripcion"] = total_tributos.tributos_hacienda.valores
        tributos["valor"] = round(self.amount_tax, 2)  # round(totalIva -(total_des*0.13),2)
        invoice_info["tributos"] = [tributos]
        invoice_info["subTotal"] = round(self.sub_total, 2)  # round(total_Gravada - total_des, 2 )
        invoice_info["ivaPerci1"] = round(self.iva_percibido_amount, 2)

        monto_descu = 0.0
        rete_iva = round(self.retencion_iva_amount or 0.0, 2)
        rete_renta = round(self.retencion_renta_amount or 0.0, 2)
        _logger.warning("SIT  RENTA = %s", rete_renta)

        _logger.warning("SIT  TIENE RENTA = %s", self.apply_retencion_renta)
        retencion = rete_iva + rete_renta

        for line in self.invoice_line_ids:
            taxes = line.tax_ids.compute_all(
                line.price_unit,
                self.currency_id,
                line.quantity,
                product=line.product_id,
                partner=self.partner_id,
            )

            monto_descu += round(line.quantity * (line.price_unit * (line.discount / 100)), 2)

        invoice_info["ivaRete1"] = rete_iva
        invoice_info["reteRenta"] = rete_renta
        invoice_info["montoTotalOperacion"] = round(self.total_operacion, 2)
        invoice_info["totalNoGravado"] = 0
        invoice_info["totalPagar"] = round(self.total_pagar, 2)
        invoice_info["totalLetras"] = self.amount_text
        invoice_info["saldoFavor"] = 0
        invoice_info["condicionOperacion"] = int(self.condiciones_pago)
        pagos = {}
        pagos["codigo"] = self.forma_pago.codigo
        pagos["montoPago"] = round(self.total_pagar, 2)
        pagos["referencia"] = self.sit_referencia

        if int(self.condiciones_pago) in [2]:
            pagos["plazo"] = self.sit_plazo.codigo
            pagos["periodo"] = self.sit_periodo
            invoice_info["pagos"] = [pagos]
        else:
            pagos["plazo"] = None
            pagos["periodo"] = None
            invoice_info["pagos"] = [pagos]
            _logger.info("SIT Formas de pago = %s=, %s=", self.forma_pago, pagos)

        invoice_info["numPagoElectronico"] = None
        if invoice_info["totalGravada"] == 0.0:
            invoice_info["ivaPerci1"] = 0.0
            invoice_info["ivaRete1"] = 0.0
        if invoice_info["totalPagar"] == 0.0:
            invoice_info["condicionOperacion"] = 1
        return invoice_info

    def sit_ccf_base_map_invoice_info_extension(self):
        invoice_info = {}
        invoice_info["nombEntrega"] = self.invoice_user_id.name
        invoice_info["docuEntrega"] = self.company_id.vat
        if self.partner_id.nombreComercial:
            invoice_info["nombRecibe"] = self.partner_id.nombreComercial
        else:
            invoice_info["nombRecibe"] = None

        nit = None
        if self.partner_id:
            if self.partner_id.dui:
                nit = self.partner_id.dui or ''
            elif self.partner_id.vat:
                nit = self.partner_id.vat or ''
        if isinstance(nit, str):
            nit = nit.replace("-", "")
            invoice_info["docuRecibe"] = nit
        invoice_info["observaciones"] = self.sit_observaciones
        invoice_info["placaVehiculo"] = None
        invoice_info = None
        return invoice_info

    ###--------FE-FACTURA ELECTRONICA-----------##

    def sit_base_map_invoice_info(self):
        _logger.info("SIT sit_base_map_invoice_info self = %s", self)
        invoice_info = {}
        nit = None

        if self.company_id and self.company_id.vat:
            nit = self.company_id.vat.replace("-", "")

        invoice_info["nit"] = nit
        invoice_info["activo"] = True
        invoice_info["passwordPri"] = self.company_id.sit_passwordPri
        if not self.hacienda_selloRecibido and self.sit_factura_de_contingencia and not self.sit_json_respuesta:
            _logger.info("SIT sit_base_map_invoice_info contingencia")
            invoice_info["dteJson"] = self.sit_json_respuesta
        else:
            _logger.info("SIT sit_base_map_invoice_info dte")
            invoice_info["dteJson"] = self.sit_base_map_invoice_info_dtejson()
        return invoice_info

    def sit_base_map_invoice_info_dtejson(self):
        invoice_info = {}
        invoice_info["identificacion"] = self.sit_base_map_invoice_info_identificacion()
        invoice_info["documentoRelacionado"] = None
        invoice_info["emisor"] = self.sit_base_map_invoice_info_emisor()
        invoice_info["receptor"] = self.sit_base_map_invoice_info_receptor()
        invoice_info["otrosDocumentos"] = None
        invoice_info["ventaTercero"] = None
        cuerpoDocumento = self.sit_base_map_invoice_info_cuerpo_documento()
        invoice_info["cuerpoDocumento"] = cuerpoDocumento[0]
        if str(invoice_info["cuerpoDocumento"]) == 'None':
            raise UserError(_('La Factura no tiene linea de Productos Valida.'))
        invoice_info["resumen"] = self.sit_base_map_invoice_info_resumen(cuerpoDocumento[1], cuerpoDocumento[2],
                                                                         cuerpoDocumento[3],
                                                                         invoice_info["identificacion"],
                                                                         invoice_info["cuerpoDocumento"])
        invoice_info["extension"] = self.sit_base_map_invoice_info_extension()
        invoice_info["apendice"] = None
        return invoice_info

    def sit_base_map_invoice_info_identificacion(self):
        invoice_info = {}
        invoice_info["version"] = int(self.journal_id.sit_tipo_documento.version) #1

        ambiente = None
        if config_utils:
            ambiente = config_utils.compute_validation_type_2(self.env)

        invoice_info["ambiente"] = ambiente
        invoice_info["tipoDte"] = self.journal_id.sit_tipo_documento.codigo
        invoice_info["numeroControl"] = self.name
        invoice_info["codigoGeneracion"] = self.hacienda_codigoGeneracion_identificacion  # self.sit_generar_uuid()
        invoice_info["tipoModelo"] = int(self.journal_id.sit_modelo_facturacion)
        invoice_info["tipoOperacion"] = int(self.journal_id.sit_tipo_transmision)

        # Contingencia
        invoice_info["tipoContingencia"] = int(self.sit_tipo_contingencia or 0)
        invoice_info["motivoContin"] = str(self.sit_tipo_contingencia_otro or "")

        FechaEmi = None
        if self.invoice_date:
            FechaEmi = self.invoice_date
            _logger.info("SIT FechaEmi seleccionada = %s", FechaEmi)
        else:
            #os.environ['TZ'] = 'America/El_Salvador'  # Establecer la zona horaria
            #datetime.datetime.now()
            #salvador_timezone = pytz.timezone('America/El_Salvador')
            #FechaEmi = datetime.datetime.now(salvador_timezone)
            FechaEmi = config_utils.get_fecha_emi()
            _logger.info("SIT FechaEmi none = %s", FechaEmi)
        _logger.info("SIT FechaEmi = %s (%s): HoraEmi = %s", FechaEmi, type(FechaEmi), self.invoice_date)
        invoice_info["fecEmi"] = FechaEmi
        invoice_info["horEmi"] = self.invoice_time
        invoice_info["tipoMoneda"] = self.currency_id.name
        if invoice_info["tipoOperacion"] == constants.TRANSMISION_NORMAL:#1:
            invoice_info["tipoModelo"] = 1 #Transmision normal
            invoice_info["tipoContingencia"] = None
            invoice_info["motivoContin"] = None
        else:
            invoice_info["tipoModelo"] = 2 #Transmision por contingencia
        if invoice_info["tipoOperacion"] == constants.TRANSMISION_CONTINGENCIA:
            invoice_info["tipoContingencia"] = None
        return invoice_info

    def sit_base_map_invoice_info_emisor(self):
        invoice_info = {}
        direccion = {}
        nit = self.company_id.vat.replace("-", "") if self.company_id and self.company_id.vat else None
        invoice_info["nit"] = nit
        nrc = self.company_id.company_registry if self.company_id and self.company_id.company_registry else None
        if nrc:
            nrc = nrc.replace("-", "")
        invoice_info["nrc"] = nrc
        invoice_info["nombre"] = self.company_id.name
        invoice_info["codActividad"] = self.company_id.codActividad.codigo
        invoice_info["descActividad"] = self.company_id.codActividad.valores
        if self.company_id.nombre_comercial:
            invoice_info["nombreComercial"] = self.company_id.nombre_comercial
        else:
            invoice_info["nombreComercial"] = None
        invoice_info["tipoEstablecimiento"] = self.company_id.tipoEstablecimiento.codigo
        direccion["departamento"] = self.company_id.state_id.code
        direccion["municipio"] = self.company_id.munic_id.code
        direccion["complemento"] = self.company_id.street
        invoice_info["direccion"] = direccion
        if self.company_id.phone:
            invoice_info["telefono"] = self.company_id.phone
        else:
            invoice_info["telefono"] = None
        invoice_info["correo"] = self.company_id.email
        invoice_info["codEstableMH"] = self.journal_id.sit_codestable
        invoice_info["codEstable"] = self.journal_id.sit_codestable
        invoice_info["codPuntoVentaMH"] = self.journal_id.sit_codpuntoventa
        invoice_info["codPuntoVenta"] = self.journal_id.sit_codpuntoventa
        return invoice_info

    def sit_base_map_invoice_info_receptor(self):
        _logger.info("SIT sit_base_map_invoice_info_receptor self = %s", self)
        invoice_info = {}

        # 1) ¿qué DTE es?
        tipo_dte = self.journal_id.sit_tipo_documento.codigo

        # 2) campo base (NIT para 03, DUI para el resto)
        raw_doc = None
        if self.partner_id:
            if self.partner_id.dui:
                raw_doc = self.partner_id.dui or ''
            elif self.partner_id.vat:
                raw_doc = self.partner_id.vat or ''
            elif self.partner_id.fax:
                raw_doc = self.partner_id.fax or ''
        tipo_doc = getattr(self.partner_id.l10n_latam_identification_type_id, 'codigo', None)

        if not raw_doc:
            raise UserError(_(
                "Receptor sin documento de identidad (DUI o NIT) para DTE %s.\nCliente: %s"
            ) % (tipo_dte, self.partner_id.display_name))

        # 3) limpio sólo dígitos
        # cleaned = re.sub(r'\D', '', raw_doc)
        # if not cleaned or not tipo_doc:
        #     raise UserError(_(
        #         "Receptor sin documento válido para DTE %s:\nraw=%r, tipo=%r") %
        #                     (tipo_dte, raw_doc, tipo_doc)
        #                     )
        #
        # # 4) si es DTE 13, poner guión xxxxxxxx-x
        num_doc = raw_doc #None
        # if tipo_doc is not None and tipo_doc == constants.COD_TIPO_DOCU_DUI: #if tipo_dte == '13':
        #     if len(cleaned) != 9:
        #         raise UserError(_("Para DTE 01 el DUI debe ser 9 dígitos (8+1). Se dieron %d.") % len(cleaned))
        #     num_doc = f"{cleaned[:8]}-{cleaned[8]}"
        # else:
        #     num_doc = cleaned

        invoice_info['numDocumento'] = num_doc
        invoice_info['tipoDocumento'] = tipo_doc

        # 5) NRC
        raw_nrc = self.partner_id.nrc.replace("-", "") if self.partner_id and self.partner_id.nrc else ''
        invoice_info['nrc'] = re.sub(r'\D', '', raw_nrc) or None

        # 6) Nombre y actividad
        invoice_info['nombre'] = self.partner_id.name or ''
        invoice_info['codActividad'] = getattr(self.partner_id.codActividad, 'codigo', '')
        invoice_info['descActividad'] = getattr(self.partner_id.codActividad, 'valores', '')

        # 7) Dirección si está completa
        depto = getattr(self.partner_id.state_id, 'code', None)
        muni = getattr(self.partner_id.munic_id, 'code', None)
        compo = self.partner_id.street or ''
        invoice_info['direccion'] = (
            {'departamento': depto, 'municipio': muni, 'complemento': compo}
            if depto and muni and compo else None
        )

        # 8) Teléfono y correo
        invoice_info['telefono'] = self.partner_id.phone or ''
        invoice_info['correo'] = self.partner_id.email or ''

        return invoice_info

    def sit_base_map_invoice_info_cuerpo_documento(self):
        lines = []
        _logger.info("SIT sit_base_map_invoice_info_cuerpo_documento self = %s", self.invoice_line_ids)
        item_numItem = 0
        total_Gravada = 0.0
        totalIva = 0.0
        ventaGravada = 0.0
        ventaExenta = 0.0

        for line in self.invoice_line_ids.filtered(lambda x: x.precio_unitario > 0):
            item_numItem += 1
            line_temp = {}
            lines_tributes = []
            line_temp["numItem"] = item_numItem
            tipoItem = int(line.product_id.tipoItem.codigo or line.product_id.product_tmpl_id.tipoItem.codigo)
            line_temp["tipoItem"] = tipoItem
            line_temp["numeroDocumento"] = None
            line_temp["cantidad"] = line.quantity
            line_temp["codigo"] = line.product_id.default_code
            if not line.product_id:
                _logger.error("Producto no configurado en la línea de factura.")
                continue  # O puedes decidir manejar de otra manera
            product_name = line.product_id.name or "Desconocido"
            if not line.product_id.uom_hacienda:
                raise UserError(_("Unidad de medida del producto no configurada para: %s" % product_name))
            else:
                _logger.info("SIT uniMedida self = %s", line.product_id)
                _logger.info("SIT uniMedida self = %s", line.product_id.uom_hacienda)
                uniMedida = int(line.product_id.uom_hacienda.codigo)
            line_temp["uniMedida"] = int(uniMedida)

            line_temp["descripcion"] = line.name
            line_temp["precioUni"] = round(line.precio_unitario, 2)
            line_temp["montoDescu"] = (
                    line_temp["cantidad"] * (line.price_unit * (line.discount / 100))
                    or 0.0
            )
            line_temp["ventaNoSuj"] = round(line.precio_no_sujeto, 2)  # 0.0
            codigo_tributo = None
            codigo_tributo_codigo = 0
            for line_tributo in line.tax_ids:
                codigo_tributo_codigo = line_tributo.tributos_hacienda.codigo
                codigo_tributo = line_tributo.tributos_hacienda
            lines_tributes.append(codigo_tributo_codigo)
            line_temp["tributos"] = lines_tributes
            vat_taxes_amounts = line.tax_ids.compute_all(
                line.precio_unitario,
                self.currency_id,
                line.quantity,
                product=line.product_id,
                partner=self.partner_id,
            )

            vat_taxes_amount = 0.0
            if vat_taxes_amounts and vat_taxes_amounts.get('taxes') and len(vat_taxes_amounts['taxes']) > 0:
                vat_taxes_amount = round(vat_taxes_amounts['taxes'][0]['amount'], 2) if vat_taxes_amounts else 0.0
                _logger.info("SIT taxes= %s", vat_taxes_amount)

                sit_amount_base = round(vat_taxes_amounts['taxes'][0]['base'], 2) if vat_taxes_amounts else 0.0

            line_temp['psv'] = line.product_id.sit_psv
            line_temp["noGravado"] = 0.0

            ventaGravada = line.precio_gravado
            _logger.info("SIT Cantidad= %s, precio gravado= %s, descuento= %s, monto descu= %s, venta gravada= %s",
                         line_temp["cantidad"], line.precio_gravado, (line.discount / 100),
                         (line.precio_gravado * (line.discount / 100)), ventaGravada)

            line_temp["ivaItem"] = round(((ventaGravada / self.get_valor_iva_divisor_config()) * self.valor_iva_config()),
                                         2)  # round(vat_taxes_amount - ((((line.price_unit *line.quantity)* (line.discount / 100))/1.13)*0.13),2)
            _logger.info("SIT Iva item= %s", line_temp["ivaItem"])
            _logger.info("SIT  RENTA = %s", self.retencion_renta_amount)

            if line_temp["ivaItem"] == 0.0:
                ventaGravada = 0.0
                ventaExenta = round(line.precio_exento, 2)
            # else:
            # ventaGravada = line_temp["cantidad"] * (line.price_unit - (line.price_unit * (line.discount / 100)))
            # ventaExenta = 0.0  # O lo que corresponda en caso de que haya IVA
            ventaExenta = round(line.precio_exento, 2)
            total_Gravada += ventaGravada
            line_temp["ventaGravada"] = round(ventaGravada, 2)
            line_temp["ventaExenta"] = round(ventaExenta, 2)

            if line.product_id and line.product_id.tipo_venta:
                if line.product_id.tipo_venta == constants.TIPO_VENTA_PROD_GRAV:
                    line_temp["ventaNoSuj"] = 0.0
                    line_temp["ventaExenta"] = 0.0
                elif line.product_id.tipo_venta == constants.TIPO_VENTA_PROD_EXENTO:
                    line_temp["ventaNoSuj"] = 0.0
                    line_temp["ventaGravada"] = 0.0
                elif line.product_id.tipo_venta == constants.TIPO_VENTA_PROD_NO_SUJETO:
                    line_temp["ventaExenta"] = 0.0
                    line_temp["ventaGravada"] = 0.0

            if ventaGravada == 0.0:
                line_temp["tributos"] = None
            if tipoItem == 4:
                line_temp["uniMedida"] = 99
                line_temp["codTributo"] = codTributo
                line_temp["codTributo"] = None  # <------------- Temporal
                line_temp["tributos"] = None
            else:
                line_temp["codTributo"] = None
                line_temp["tributos"] = lines_tributes
                line_temp["tributos"] = None  # <-----   temporal
                line_temp["uniMedida"] = int(uniMedida)
            totalIva += line_temp["ivaItem"]
            lines.append(line_temp)
            self.check_parametros_linea_firmado(line_temp)
        return lines, codigo_tributo, total_Gravada, float(totalIva)

    def sit_base_map_invoice_info_resumen(self, tributo_hacienda, total_Gravada, totalIva, identificacion,
                                          cuerpo_documento):
        _logger.info("SIT sit_base_map_invoice_info_resumen self = %s", self)
        total_des = 0
        total_gral = self.amount_total + total_des
        por_des = 0
        for line in self.invoice_line_ids.filtered(lambda x: x.price_unit < 0):
            total_des += (line.precio_unitario * -1)

        total_gral = self.amount_total + total_des
        if total_des:
            total_gral = self.amount_total + total_des
            por_des = 100 - round(((total_gral - total_des) / total_gral) * 100)
        else:
            total_des = self.descuento_gravado
            por_des = self.descuento_global
        _logger.info("SIT total des = %s, total gravado %s", total_des, self.total_gravado)

        subtotal = sum(line.price_subtotal for line in self.invoice_line_ids)
        total = self.amount_total

        rete_iva = round(self.retencion_iva_amount or 0.0, 2)
        rete_renta = round(self.retencion_renta_amount or 0.0, 2)
        _logger.warning("SIT  RENTA = %s", rete_renta)
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

            por_des = 100 - round(((total_gral - total_des) / total_gral) * 100)

        subtotal = sum(line.price_subtotal for line in self.invoice_line_ids)
        total = self.amount_total

        invoice_info = {}
        tributos = {}
        pagos = {}
        invoice_info["totalNoSuj"] = round(self.total_no_sujeto, 2)  # 0
        invoice_info["totalExenta"] = round(self.total_exento, 2)  # 0
        invoice_info["subTotalVentas"] = round(self.sub_total_ventas, 2)  # round (self.amount_total + total_des , 2 )
        invoice_info["descuNoSuj"] = round(self.descuento_no_sujeto, 2)  # 0
        invoice_info["descuExenta"] = round(self.descuento_exento, 2)  # 0
        invoice_info["descuGravada"] = round(total_des, 2)
        invoice_info["porcentajeDescuento"] = round(por_des, 2)
        invoice_info["totalDescu"] = round(self.total_descuento, 2)  # 0
        if identificacion['tipoDte'] != constants.COD_DTE_FE:
            if tributo_hacienda:
                _logger.info("SIT tributo_haciendatributo_hacienda = %s", tributo_hacienda)
                tributos["codigo"] = tributo_hacienda.codigo
                tributos["descripcion"] = tributo_hacienda.valores
                tributos["valor"] = round(self.amount_tax, 2)
            else:
                tributos["codigo"] = None
                tributos["descripcion"] = None
                tributos["valor"] = None
            invoice_info["tributos"] = tributos
        else:
            invoice_info["tributos"] = None
        invoice_info["subTotal"] = round(self.sub_total, 2)  # round(self.amount_total, 2 )
        invoice_info["ivaRete1"] = rete_iva
        invoice_info["reteRenta"] = rete_renta

        # Tributos
        valor_tributo = 0
        if tributo_hacienda:
            valor_tributo = tributos.get("valor", 0) or 0  # Accede al valor del diccionario

        invoice_info["montoTotalOperacion"] = round(self.total_operacion, 2)  # round(self.amount_total, 2 )
        invoice_info["totalNoGravado"] = 0
        invoice_info["totalPagar"] = round(self.total_pagar, 2)
        invoice_info["totalLetras"] = self.amount_text
        _logger.info("SIT total descuentos = %s, iva= %s", total_des, totalIva)
        invoice_info["totalIva"] = round(totalIva, 2)  # round(totalIva - (total_des - (total_des / 1.13)), 2 )
        if invoice_info["totalIva"] == 0.0:
            invoice_info["totalGravada"] = 0.0
            invoice_info["totalExenta"] = round(self.total_exento, 2)
        else:
            invoice_info["totalGravada"] = round(self.total_gravado, 2)  # round(self.total_gravado + total_des, 2 )
            # invoice_info["totalExenta"] = 0.0
        invoice_info["saldoFavor"] = 0
        invoice_info["condicionOperacion"] = int(self.condiciones_pago)
        pagos["codigo"] = self.forma_pago.codigo
        pagos["montoPago"] = round(self.total_pagar, 2)
        pagos["referencia"] = self.sit_referencia
        if int(self.condiciones_pago) in [2, 3]:
            pagos["periodo"] = self.sit_periodo
            pagos["plazo"] = self.sit_plazo.codigo
            invoice_info["pagos"] = [pagos]
        else:
            pagos["periodo"] = None
            pagos["plazo"] = None
            invoice_info["pagos"] = None

        if invoice_info["totalGravada"] == 0.0:
            invoice_info["ivaRete1"] = 0.0
        invoice_info["numPagoElectronico"] = None
        return invoice_info

    def sit_base_map_invoice_info_extension(self):
        invoice_info = {}
        invoice_info["nombEntrega"] = self.invoice_user_id.name or None
        invoice_info["docuEntrega"] = self.company_id.vat or None
        invoice_info["nombRecibe"] = self.partner_id.nombreComercial if self.partner_id.nombreComercial else None
        # Asegurarse de que 'nit' sea una cadena antes de usar 'replace'

        nit = None
        if self.partner_id:
            if self.partner_id.dui:
                nit = self.partner_id.dui or ''
            elif self.partner_id.vat:
                nit = self.partner_id.vat or ''

        if isinstance(nit, str):
            nit = nit.replace("-", "")
            invoice_info["docuRecibe"] = nit
        invoice_info["observaciones"] = self.sit_observaciones
        invoice_info["placaVehiculo"] = None
        invoice_info["observaciones"] = self.sit_observaciones
        return invoice_info

    def sit_obtener_payload_dte_info(self, ambiente, doc_firmado):
        _logger.info("Generando payload FCF (cg):%s", self.hacienda_codigoGeneracion_identificacion)
        invoice_info = {}
        invoice_info["ambiente"] = ambiente
        invoice_info["idEnvio"] = "00001"
        invoice_info["tipoDte"] = self.journal_id.sit_tipo_documento.codigo
        invoice_info["version"] = int(self.journal_id.sit_tipo_documento.version)
        invoice_info["documento"] = doc_firmado
        invoice_info["codigoGeneracion"] = self.hacienda_codigoGeneracion_identificacion  # self.sit_generar_uuid()
        return invoice_info

    def sit_generar_uuid(self) -> Any:
        import uuid
        # Genera un UUID versión 4 (basado en números aleatorios)
        uuid_aleatorio = uuid.uuid4()
        uuid_cadena = str(uuid_aleatorio)
        return uuid_cadena.upper()

    ##################################### NOTA DE CREDITO

    def sit_base_map_invoice_info_ndc(self):
        _logger.info("SIT sit_base_map_invoice_info_ndc self = %s", self)
        invoice_info = {}
        nit = None
        if self.company_id and self.company_id.vat:
            nit = self.company_id.vat.replace("-", "")
        invoice_info["nit"] = nit
        invoice_info["activo"] = True
        invoice_info["passwordPri"] = self.company_id.sit_passwordPri
        invoice_info["dteJson"] = self.sit_base_map_invoice_info_ndc_dtejson()
        return invoice_info

    def sit_base_map_invoice_info_ndc_dtejson(self):
        _logger.info("SIT sit_base_map_invoice_info_dtejson self = %s", self)
        invoice_info = {}
        invoice_info["identificacion"] = self.sit_ndc_base_map_invoice_info_identificacion()
        invoice_info["documentoRelacionado"] = self.sit__ndc_relacionado()
        invoice_info["emisor"] = self.sit__ndc_base_map_invoice_info_emisor()
        invoice_info["receptor"] = self.sit__ccf_base_map_invoice_info_receptor()
        invoice_info["ventaTercero"] = None
        cuerpoDocumento = self.sit_base_map_invoice_info_cuerpo_documento_ndc()
        invoice_info["cuerpoDocumento"] = cuerpoDocumento[0]
        if str(invoice_info["cuerpoDocumento"]) == 'None':
            raise UserError(_('La Factura no tiene linea de Productos Valida.'))

        _logger.info("SIT resumen NC = c1=%s, c2=%s, c3=%s, c4=%s", cuerpoDocumento[1], cuerpoDocumento[2],
                     cuerpoDocumento[3], invoice_info["identificacion"])
        invoice_info["resumen"] = self.sit_ndc_base_map_invoice_info_resumen(cuerpoDocumento[1], cuerpoDocumento[2],
                                                                             cuerpoDocumento[3],
                                                                             invoice_info["identificacion"])
        invoice_info["extension"] = self.sit_base_map_invoice_info_extension_ndc()
        invoice_info["apendice"] = None
        return invoice_info

    def sit_ndc_base_map_invoice_info_identificacion(self):
        invoice_info = {}
        invoice_info["version"] = int(self.journal_id.sit_tipo_documento.version)  # 3

        # Ambiente y validación
        ambiente = None
        if config_utils:
            ambiente = config_utils.compute_validation_type_2(self.env)
        invoice_info["ambiente"] = ambiente
        invoice_info["tipoDte"] = self.journal_id.sit_tipo_documento.codigo
        invoice_info["numeroControl"] = self.name
        invoice_info[
            "codigoGeneracion"] = self.hacienda_codigoGeneracion_identificacion  # self.sit_generar_uuid()          #  company_id.sit_uuid.upper()
        invoice_info["tipoModelo"] = int(self.journal_id.sit_modelo_facturacion)
        invoice_info["tipoOperacion"] = int(self.journal_id.sit_tipo_transmision)

        # Contingencia

        tipoContingencia = int(self.sit_tipo_contingencia) or 0
        invoice_info["tipoContingencia"] = tipoContingencia
        motivoContin = str(self.sit_tipo_contingencia_otro) or ""
        invoice_info["motivoContin"] = motivoContin

        # Fecha y hora de emisión
        FechaEmi = None
        if self.invoice_date:
            FechaEmi = self.invoice_date
        else:
            FechaEmi = config_utils.get_fecha_emi()
        _logger.info("SIT FechaEmi = %s (%s)", FechaEmi, type(FechaEmi))
        invoice_info["fecEmi"] = FechaEmi
        invoice_info["horEmi"] = self.invoice_time
        invoice_info["tipoMoneda"] = self.currency_id.name
        if invoice_info["tipoOperacion"] == constants.TRANSMISION_NORMAL:
            invoice_info["tipoModelo"] = 1
            invoice_info["tipoContingencia"] = None
            invoice_info["motivoContin"] = None
        else:
            invoice_info["tipoModelo"] = 2
        if invoice_info["tipoOperacion"] != constants.TRANSMISION_NORMAL:
            invoice_info["tipoContingencia"] = tipoContingencia
        if invoice_info["tipoContingencia"] == constants.TIPO_CONTIN_OTRO:
            invoice_info["motivoContin"] = motivoContin
        return invoice_info

    def sit_base_map_invoice_info_cuerpo_documento_ndc(self):
        lines = []
        item_numItem = 0
        total_Gravada = 0.0
        totalIva = 0.0
        codigo_tributo = None  # Inicializamos la variable para asegurarnos de que tiene un valor predeterminado.
        tax_ids_list = []  # Creamos una lista para almacenar los tax_ids.

        _logger.info("Iniciando el mapeo de la información del documento NDC = %s", self.invoice_line_ids)

        for line in self.invoice_line_ids.filtered(lambda x: x.precio_unitario > 0):
            if not line.custom_discount_line:
                item_numItem += 1
                line_temp = {}
                lines_tributes = []
                line_temp["numItem"] = item_numItem
                tipoItem = int(line.product_id.tipoItem.codigo or line.product_id.product_tmpl_id.tipoItem.codigo)
                line_temp["tipoItem"] = tipoItem
                _logger.info(
                    f"Procesando línea de factura: {line.product_id.name}, tipoItem: {tipoItem}.")  # Log en cada línea.

                if self.inv_refund_id:
                    line_temp["numeroDocumento"] = self.inv_refund_id.hacienda_codigoGeneracion_identificacion
                else:
                    line_temp["numeroDocumento"] = None

                line_temp["codigo"] = line.product_id.default_code
                codTributo = line.product_id.tributos_hacienda_cuerpo.codigo
                if codTributo == False:
                    line_temp["codTributo"] = None
                else:
                    line_temp["codTributo"] = codTributo

                line_temp["descripcion"] = line.name
                line_temp["cantidad"] = line.quantity
                if line.product_id and not line.product_id.uom_hacienda:
                    uniMedida = 7
                    _logger.error(f"UOM no configurado para el producto: {line.product_id.name}.")  # Log de error
                    raise UserError(_("UOM de producto no configurado para:  %s" % (line.product_id.name)))
                else:
                    uniMedida = int(line.product_id.uom_hacienda.codigo)

                line_temp["uniMedida"] = int(uniMedida)
                # line_temp["precioUni"] = round(line.price_unit, 4)
                line_temp["montoDescu"] = (
                        round(line_temp["cantidad"] * (line.price_unit * (line.discount / 100)), 2) or 0.0)
                line_temp["ventaNoSuj"] = round(line.precio_no_sujeto, 2)  # 0.0
                line_temp["ventaExenta"] = round(line.precio_exento, 2)  # 0.0
                ventaGravada = round(line.precio_gravado,
                                     2)  # line_temp["cantidad"] * (line.price_unit * (line.discount / 100))
                line_temp["ventaGravada"] = round(ventaGravada, 2)

                _logger.debug(
                    f"Venta gravada: {ventaGravada}, cantidad: {line_temp['cantidad']}, precio unitario: {line.price_unit}.")  # Log sobre cálculos.

                for line_tributo in line.tax_ids:
                    codigo_tributo_codigo = line_tributo.tributos_hacienda.codigo
                    codigo_tributo = line_tributo.tributos_hacienda  # Asignamos el valor de `codigo_tributo`
                    lines_tributes.append(codigo_tributo_codigo)

                line_temp["tributos"] = lines_tributes
                vat_taxes_amounts = line.tax_ids.compute_all(
                    line.price_unit,
                    self.currency_id,
                    line.quantity,
                    product=line.product_id,
                    partner=self.partner_id,
                )

                vat_taxes_amount = 0.0
                sit_amount_base = 0.0
                _logger.info(f"Impuestos: {vat_taxes_amounts}")  # Log en cada línea.
                if vat_taxes_amounts and vat_taxes_amounts.get('taxes') and len(vat_taxes_amounts['taxes']) > 0:
                    vat_taxes_amount = vat_taxes_amounts['taxes'][0]['amount'] if vat_taxes_amounts['taxes'] and \
                                                                                  vat_taxes_amounts[
                                                                                      'taxes'] != "" else 0
                    sit_amount_base = round(vat_taxes_amounts['taxes'][0]['base'], 2) if vat_taxes_amounts['taxes'] and \
                                                                                         vat_taxes_amounts[
                                                                                             'taxes'] != "" else 0
                price_unit_mas_iva = round(line.price_unit, 4)

                price_unit = 0.0
                if line_temp["cantidad"] > 0:
                    price_unit = round(sit_amount_base / line_temp["cantidad"], 4)
                else:
                    price_unit = round(0.00, 4)

                line_temp["precioUni"] = round(line.precio_unitario, 2)
                # ventaGravada = line_temp["cantidad"] * line_temp["precioUni"] - line_temp["montoDescu"]
                total_Gravada += round(ventaGravada, 4)
                # line_temp["ventaGravada"] = round(ventaGravada, 4)

                _logger.debug(f"Total gravada acumulado: {total_Gravada}.")  # Log del total gravado.
                if line.product_id and line.product_id.tipo_venta:
                    if line.product_id.tipo_venta == constants.TIPO_VENTA_PROD_GRAV:
                        line_temp["ventaNoSuj"] = 0.0
                        line_temp["ventaExenta"] = 0.0
                    elif line.product_id.tipo_venta == constants.TIPO_VENTA_PROD_EXENTO:
                        line_temp["ventaNoSuj"] = 0.0
                        line_temp["ventaGravada"] = 0.0
                    elif line.product_id.tipo_venta == constants.TIPO_VENTA_PROD_NO_SUJETO:
                        line_temp["ventaExenta"] = 0.0
                        line_temp["ventaGravada"] = 0.0

                if ventaGravada == 0.0:
                    line_temp["tributos"] = None
                else:
                    line_temp["tributos"] = lines_tributes

                if tipoItem == constants.COD_TIPO_ITEM:
                    line_temp["uniMedida"] = 99
                    line_temp["codTributo"] = codTributo
                    line_temp["tributos"] = [20]
                else:
                    line_temp["codTributo"] = None
                    line_temp["tributos"] = lines_tributes

                totalIva += vat_taxes_amount
                lines.append(line_temp)
                tax_ids_list.append(line.tax_ids)  # Almacenamos los tax_ids de la línea

        _logger.info(
            f"Proceso de mapeo finalizado. Total Gravada: {total_Gravada}, Total IVA: {totalIva}.")  # Log al finalizar la función.

        return lines, codigo_tributo, total_Gravada, tax_ids_list, totalIva

    def sit_ndc_base_map_invoice_info_resumen(self, tributo_hacienda, total_Gravada, totalIva, identificacion):
        invoice_info = {}
        tributos = {}
        pagos = {}

        _logger.info("SIT total gravado NC = %s", total_Gravada)

        invoice_info["totalNoSuj"] = round(self.total_no_sujeto, 2)  # 0
        invoice_info["totalExenta"] = round(self.total_exento, 2)  # 0
        invoice_info["totalGravada"] = round(total_Gravada, 2)
        invoice_info["subTotalVentas"] = round(self.sub_total_ventas, 2)
        invoice_info["descuNoSuj"] = round(self.descuento_no_sujeto, 2)  # 0
        invoice_info["descuExenta"] = round(self.descuento_exento, 2)  # 0
        invoice_info["descuGravada"] = round(self.descuento_gravado, 2)
        invoice_info["totalDescu"] = round(self.total_descuento, 2)  # 0
        if identificacion['tipoDte'] != constants.COD_DTE_FE:
            if tributo_hacienda:
                tributos["codigo"] = tributo_hacienda.codigo
                tributos["descripcion"] = tributo_hacienda.valores
                tributos["valor"] = round(self.amount_tax, 2)
            else:
                tributos["codigo"] = None
                tributos["descripcion"] = None
                tributos["valor"] = None
            _logger.info("========================AÑADIENDO TRIBUTO======================")
            invoice_info["tributos"] = [tributos]
        else:
            invoice_info["tributos"] = None
        invoice_info["subTotal"] = round(self.sub_total, 2)  # self.             amount_untaxed
        invoice_info["ivaPerci1"] = round(self.inv_refund_id.iva_percibido_amount, 2)
        invoice_info["ivaRete1"] = round(self.retencion_iva_amount or 0.0, 2)
        invoice_info["reteRenta"] = round(self.retencion_renta_amount or 0.0, 2)
        invoice_info["montoTotalOperacion"] = round(self.amount_total, 2)
        invoice_info["totalLetras"] = self.amount_text
        invoice_info["condicionOperacion"] = int(self.condiciones_pago)
        pagos["codigo"] = self.forma_pago.codigo  # '01'   # CAT-017 Forma de Pago    01 = bienes
        pagos["montoPago"] = round(self.total_pagar, 2)
        pagos["referencia"] = self.sit_referencia  # Un campo de texto llamado Referencia de pago
        if invoice_info["totalGravada"] == 0.0:
            invoice_info["ivaPerci1"] = 0.0
            invoice_info["ivaRete1"] = 0.0
        return invoice_info

    def sit__ndc_base_map_invoice_info_emisor(self):
        invoice_info = {}
        direccion = {}
        nit = self.company_id.vat.replace("-", "") if self.company_id and self.company_id.vat else None
        invoice_info["nit"] = nit

        nrc = self.company_id.company_registry if self.company_id and self.company_id.company_registry else None
        if nrc:
            nrc = nrc.replace("-", "")
        invoice_info["nrc"] = nrc
        invoice_info["nombre"] = self.company_id.name
        invoice_info["codActividad"] = self.company_id.codActividad.codigo
        invoice_info["descActividad"] = self.company_id.codActividad.valores
        if self.company_id.nombre_comercial:
            invoice_info["nombreComercial"] = self.company_id.nombre_comercial
        else:
            invoice_info["nombreComercial"] = None
        invoice_info["tipoEstablecimiento"] = self.company_id.tipoEstablecimiento.codigo
        direccion["departamento"] = self.company_id.state_id.code
        direccion["municipio"] = self.company_id.munic_id.code
        direccion["complemento"] = self.company_id.street
        invoice_info["direccion"] = direccion
        if self.company_id.phone:
            invoice_info["telefono"] = self.company_id.phone
        else:
            invoice_info["telefono"] = None
        invoice_info["correo"] = self.company_id.email
        return invoice_info

    def sit_base_map_invoice_info_extension_ndc(self):
        invoice_info = {}
        invoice_info["nombEntrega"] = self.invoice_user_id.name
        invoice_info["docuEntrega"] = self.company_id.vat
        invoice_info["nombRecibe"] = self.partner_id.nombreComercial if self.partner_id.nombreComercial else None
        # Asegurarse de que 'nit' sea una cadena antes de usar 'replace'
        nit = None
        if self.partner_id:
            if self.partner_id.dui:
                nit = self.partner_id.dui or ''
            elif self.partner_id.vat:
                nit = self.partner_id.vat or ''

        if isinstance(nit, str):
            nit = nit.replace("-", "")
        invoice_info["docuRecibe"] = nit
        invoice_info["observaciones"] = self.sit_observaciones
        return invoice_info

    def sit__ndc_relacionado(self):
        lines = []
        lines_temp = {}
        lines_temp['tipoDocumento'] = self.reversed_entry_id.journal_id.sit_tipo_documento.codigo  # '03'
        lines_temp['tipoGeneracion'] = int(constants.COD_TIPO_DOC_GENERACION_DTE) #Cat-007 Tipo de generacion del documento
        lines_temp['numeroDocumento'] = self.inv_refund_id.hacienda_codigoGeneracion_identificacion
        #invoice_date = self.inv_refund_id.invoice_date
        #if invoice_date:
            #new_date = invoice_date + timedelta(hours=20)
        lines_temp['fechaEmision'] = self.inv_refund_id.invoice_date.strftime(
            '%Y-%m-%d') if self.inv_refund_id.invoice_date else None  # self.inv_refund_id.invoice_date
        lines.append(lines_temp)
        return lines

    ##################################### NOTA DE DEBITO

    def sit_base_map_invoice_info_ndd(self):
        """Envoltorio principal para Nota de Débito (DTE tipo 05)."""
        _logger.info("SIT sit_base_map_invoice_info_ndd self = %s", self)
        nit = None
        if self.company_id and self.company_id.vat:
            nit = self.company_id.vat.replace("-", "")
        invoice_info = {
            'nit': nit,
            'activo': True,
            'passwordPri': self.company_id.sit_passwordPri,
            'dteJson': self.sit_base_map_invoice_info_ndd_dtejson(),
        }
        return invoice_info

    def sit_base_map_invoice_info_ndd_dtejson(self):
        """Construye el JSON interno para la Nota de Débito."""
        _logger.info("SIT sit_base_map_invoice_info_ndd_dtejson self = %s", self)
        invoice_info = {}
        # 1) Identificación
        invoice_info['identificacion'] = self.sit_ndd_base_map_invoice_info_identificacion()
        # 2) Documento relacionado
        invoice_info['documentoRelacionado'] = self.sit__ndd_relacionado()
        # 3) Emisor (reutiliza tu método de NDC)
        invoice_info['emisor'] = self.sit__ndc_base_map_invoice_info_emisor()
        # 4) Receptor (misma lógica que CCF)
        invoice_info['receptor'] = self.sit__ccf_base_map_invoice_info_receptor()
        invoice_info['ventaTercero'] = None
        # 5) Cuerpo del documento: reusa tu método de NDC
        cuerpo, tributo, totalGravada, tax_ids, totalIva = self.sit_base_map_invoice_info_cuerpo_documento_ndd()
        invoice_info['cuerpoDocumento'] = cuerpo
        if cuerpo is None:
            raise UserError(_("La Nota de Débito no tiene líneas de productos válidas."))
        # 6) Resumen: reusa tu método de NDC
        invoice_info['resumen'] = self.sit_ndd_base_map_invoice_info_resumen(
            tributo, totalGravada, totalIva,
            invoice_info['identificacion']
        )
        # 7) Extensión: reusa tu método de NDC
        invoice_info['extension'] = self.sit_base_map_invoice_info_extension_ndc()
        invoice_info['apendice'] = None
        return invoice_info

    def sit_base_map_invoice_info_cuerpo_documento_ndd(self):
        lines = []
        item_numItem = 0
        total_Gravada = 0.0
        totalIva = 0.0
        codigo_tributo = None  # Inicializamos la variable para asegurarnos de que tiene un valor predeterminado.
        tax_ids_list = []  # Creamos una lista para almacenar los tax_ids.

        _logger.info("Iniciando el mapeo de la información del documento NDD = %s", self.invoice_line_ids)

        for line in self.invoice_line_ids.filtered(lambda x: x.price_unit > 0):
            if not line.custom_discount_line:
                item_numItem += 1
                line_temp = {}
                lines_tributes = []
                line_temp["numItem"] = item_numItem
                tipoItem = int(line.product_id.tipoItem.codigo or line.product_id.product_tmpl_id.tipoItem.codigo)
                line_temp["tipoItem"] = tipoItem
                _logger.debug(
                    f"Procesando línea de factura: {line.product_id.name}, tipoItem: {tipoItem}.")  # Log en cada línea.

                _logger.info("Numero de documento:=%s ", self.debit_origin_id)
                if self.debit_origin_id:
                    line_temp["numeroDocumento"] = self.debit_origin_id.hacienda_codigoGeneracion_identificacion
                else:
                    line_temp["numeroDocumento"] = None

                line_temp["codigo"] = line.product_id.default_code
                codTributo = line.product_id.tributos_hacienda_cuerpo.codigo
                if codTributo == False:
                    line_temp["codTributo"] = None
                else:
                    line_temp["codTributo"] = codTributo

                line_temp["descripcion"] = line.name
                line_temp["cantidad"] = line.quantity
                if not line.product_id.uom_hacienda:
                    uniMedida = 7
                    _logger.error(f"UOM no configurado para el producto: {line.product_id.name}.")  # Log de error
                    raise UserError(_("UOM de producto no configurado para:  %s" % (line.product_id.name)))
                else:
                    uniMedida = int(line.product_id.uom_hacienda.codigo)

                line_temp["uniMedida"] = int(uniMedida)
                # line_temp["precioUni"] = round(line.price_unit, 4)
                line_temp["montoDescu"] = (
                        round(line_temp["cantidad"] * (line.price_unit * (line.discount / 100)), 2) or 0.0)
                line_temp["ventaNoSuj"] = round(line.precio_no_sujeto, 2)  # 0.0
                line_temp["ventaExenta"] = round(line.precio_exento, 2)  # 0.0
                ventaGravada = round(line.precio_gravado,
                                     2)  # line_temp["cantidad"] * (line.price_unit * (line.discount / 100))
                line_temp["ventaGravada"] = ventaGravada

                _logger.debug(
                    f"Venta gravada: {ventaGravada}, cantidad: {line_temp['cantidad']}, precio unitario: {line.price_unit}.")  # Log sobre cálculos.

                for line_tributo in line.tax_ids:
                    codigo_tributo_codigo = line_tributo.tributos_hacienda.codigo
                    codigo_tributo = line_tributo.tributos_hacienda  # Asignamos el valor de `codigo_tributo`
                    lines_tributes.append(codigo_tributo_codigo)

                line_temp["tributos"] = lines_tributes
                vat_taxes_amounts = line.tax_ids.compute_all(
                    line.precio_unitario,
                    self.currency_id,
                    line.quantity,
                    product=line.product_id,
                    partner=self.partner_id,
                )

                vat_taxes_amount = 0.0
                sit_amount_base = 0.0
                if vat_taxes_amounts and vat_taxes_amounts.get('taxes') and len(vat_taxes_amounts['taxes']) > 0:
                    vat_taxes_amount = vat_taxes_amounts['taxes'][0]['amount']
                    sit_amount_base = round(vat_taxes_amounts['taxes'][0]['base'], 2)
                price_unit_mas_iva = round(line.price_unit, 4)

                if line_temp["cantidad"] > 0:
                    price_unit = round(sit_amount_base / line_temp["cantidad"], 4)
                else:
                    price_unit = round(0.00, 4)

                line_temp["precioUni"] = round(line.precio_unitario, 2)
                # ventaGravada = line_temp["cantidad"] * line_temp["precioUni"] - line_temp["montoDescu"]
                total_Gravada += round(ventaGravada, 4)
                # line_temp["ventaGravada"] = round(ventaGravada, 4)

                _logger.debug(f"Total gravada acumulado: {total_Gravada}.")  # Log del total gravado.
                if line.product_id and line.product_id.tipo_venta:
                    if line.product_id.tipo_venta == constants.TIPO_VENTA_PROD_GRAV:
                        line_temp["ventaNoSuj"] = 0.0
                        line_temp["ventaExenta"] = 0.0
                    elif line.product_id.tipo_venta == constants.TIPO_VENTA_PROD_EXENTO:
                        line_temp["ventaNoSuj"] = 0.0
                        line_temp["ventaGravada"] = 0.0
                    elif line.product_id.tipo_venta == constants.TIPO_VENTA_PROD_NO_SUJETO:
                        line_temp["ventaExenta"] = 0.0
                        line_temp["ventaGravada"] = 0.0

                if ventaGravada == 0.0:
                    line_temp["tributos"] = None
                else:
                    line_temp["tributos"] = lines_tributes

                if tipoItem == constants.COD_TIPO_ITEM:
                    line_temp["uniMedida"] = 99
                    line_temp["codTributo"] = codTributo
                    line_temp["tributos"] = [20]
                else:
                    line_temp["codTributo"] = None
                    line_temp["tributos"] = lines_tributes

                totalIva += vat_taxes_amount
                lines.append(line_temp)
                tax_ids_list.append(line.tax_ids)  # Almacenamos los tax_ids de la línea

        _logger.info(
            f"Proceso de mapeo finalizado. Total Gravada: {total_Gravada}, Total IVA: {totalIva}.")  # Log al finalizar la función.

        return lines, codigo_tributo, total_Gravada, tax_ids_list, totalIva

    def sit_ndd_base_map_invoice_info_resumen(self, tributo_hacienda, total_Gravada, totalIva, identificacion):
        invoice_info = {}
        tributos = {}
        pagos = {}
        retencion = 0.0

        _logger.info("SIT total gravado NC = %s", total_Gravada)

        invoice_info["totalNoSuj"] = round(self.total_no_sujeto, 2)  # 0
        invoice_info["totalExenta"] = round(self.total_exento, 2)  # 0
        invoice_info["totalGravada"] = round(total_Gravada, 2)
        invoice_info["subTotalVentas"] = round(self.sub_total_ventas, 2)
        invoice_info["descuNoSuj"] = round(self.descuento_no_sujeto, 2)  # 0
        invoice_info["descuExenta"] = round(self.descuento_exento, 2)  # 0
        invoice_info["descuGravada"] = round(self.descuento_gravado, 2)
        invoice_info["totalDescu"] = round(self.total_descuento, 2)  # 0
        invoice_info["numPagoElectronico"] = None
        if identificacion['tipoDte'] != constants.COD_DTE_FE:
            if tributo_hacienda:
                tributos["codigo"] = tributo_hacienda.codigo
                tributos["descripcion"] = tributo_hacienda.valores
                tributos["valor"] = round(self.amount_tax, 2)
            else:
                tributos["codigo"] = None
                tributos["descripcion"] = None
                tributos["valor"] = None
            _logger.info("========================AÑADIENDO TRIBUTO======================")
            invoice_info["tributos"] = [tributos]
        else:
            invoice_info["tributos"] = None
        invoice_info["subTotal"] = round(self.sub_total, 2)  # self.             amount_untaxed
        invoice_info["ivaPerci1"] = self.iva_percibido_amount
        invoice_info["ivaRete1"] = self.retencion_iva_amount
        invoice_info["reteRenta"] = self.retencion_renta_amount
        # invoice_info["montoTotalOperacion"] = round(self.total_operacion + retencion, 2)
        invoice_info["montoTotalOperacion"] = round(self.total_pagar, 2)

        # invoice_info["totalNoGravado"] = 0
        # invoice_info["totalPagar"] = round(self.amount_total, 2)
        invoice_info["totalLetras"] = self.amount_text
        invoice_info["condicionOperacion"] = int(self.condiciones_pago)
        pagos["codigo"] = self.forma_pago.codigo  # '01'   # CAT-017 Forma de Pago    01 = bienes
        pagos["montoPago"] = round(self.total_pagar,

                                   2)
        pagos["referencia"] = self.sit_referencia  # Un campo de texto llamado Referencia de pago
        if invoice_info["totalGravada"] == 0.0:
            invoice_info["ivaPerci1"] = 0.0
            invoice_info["ivaRete1"] = 0.0
        return invoice_info

    def sit_ndd_base_map_invoice_info_identificacion(self):
        """Cabecera de identificación para Nota de Débito (tipoDte = '05')."""
        _logger.info("SIT sit_ndd_base_map_invoice_info_identificacion self = %s", self)

        # ambiente
        ambiente = None
        if config_utils:
            ambiente = config_utils.compute_validation_type_2(self.env)

        invoice_info = {
            'version': int(self.journal_id.sit_tipo_documento.version),  # 3,
            'ambiente': ambiente,
            'tipoDte': self.journal_id.sit_tipo_documento.codigo,
        }

        # númeroControl
        invoice_info['numeroControl'] = self.name

        # resto
        invoice_info.update({
            'codigoGeneracion': self.hacienda_codigoGeneracion_identificacion,
            'tipoModelo': int(self.journal_id.sit_modelo_facturacion),
            'tipoOperacion': int(self.journal_id.sit_tipo_transmision),
            'tipoContingencia': int(self.sit_tipo_contingencia) if self.sit_tipo_contingencia else None,
            'motivoContin': self.sit_tipo_contingencia_otro or None,
        })

        # fecha/hora
        FechaEmi = None
        if self.invoice_date:
            FechaEmi = self.invoice_date
            _logger.info("SIT FechaEmi seleccionada = %s", FechaEmi)
        else:
            FechaEmi = config_utils.get_fecha_emi()
            _logger.info("Fecha en sesion: %s", FechaEmi)
        _logger.info("SIT FechaEmi = %s (%s)", FechaEmi, type(FechaEmi))
        invoice_info['fecEmi'] = FechaEmi
        invoice_info['horEmi'] = self.invoice_time
        invoice_info['tipoMoneda'] = self.currency_id.name
        # ajustes según operación
        if invoice_info['tipoOperacion'] == constants.TRANSMISION_NORMAL:  # 1:
            invoice_info['tipoModelo'] = 1
            invoice_info['tipoContingencia'] = None
            invoice_info['motivoContin'] = None
        elif invoice_info['tipoOperacion'] != constants.TRANSMISION_NORMAL:
            invoice_info['tipoModelo'] = 2
        if invoice_info['tipoContingencia'] == constants.TIPO_CONTIN_OTRO:
            invoice_info['motivoContin'] = invoice_info['motivoContin']
        return invoice_info

    def sit__ndd_relacionado(self):
        """Referenciar la factura de origen para Nota de Débito."""
        self.ensure_one()
        if not self.debit_origin_id:
            raise UserError(_("La Nota de Débito debe referenciar una factura existente."))
        origin = self.debit_origin_id
        _logger.info("SIT Debito: %s", origin)
        return [{
            'tipoDocumento': origin.journal_id.sit_tipo_documento.codigo,
            'tipoGeneracion': constants.COD_TIPO_DOC_GENERACION_DTE,
            'numeroDocumento': origin.hacienda_codigoGeneracion_identificacion,
            'fechaEmision': origin.invoice_date.strftime('%Y-%m-%d'),
        }]
