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

# Definir la zona horaria de El Salvador
tz_el_salvador = pytz.timezone('America/El_Salvador')


import logging

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import config_utils
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo config_utils hacienda fex")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    config_utils = None
    constants = None

class AccountMove(models.Model):
    _inherit = "account.move"



######################################### FCE-EXPORTACION

    def sit_base_map_invoice_info_fex(self):
        if not self.env.company.sit_facturacion:
            _logger.info("FE OFF: omitiendo sit_base_map_invoice_info_fex en %s", self._name)
            return None

        _logger.info("SIT sit_base_map_invoice_info self = %s", self)
        invoice_info = {}
        nit = (self.company_id.vat or "").replace("-", "")
        invoice_info["nit"] = nit
        invoice_info["activo"] = True
        invoice_info["passwordPri"] = self.company_id.sit_passwordPri
        _logger.info("SIT sit_base_map_invoice_info = %s", invoice_info)

        if not self.hacienda_selloRecibido and self.sit_factura_de_contingencia and self.sit_json_respuesta:
            _logger.info("SIT sit_base_map_invoice_info contingencia")
            invoice_info["dteJson"] = self.sit_json_respuesta
        else:
            _logger.info("SIT sit_base_map_invoice_info dte")
            invoice_info["dteJson"] = self.sit__fex_base_map_invoice_info_dtejson()
        return invoice_info

    def sit__fex_base_map_invoice_info_dtejson(self):
        if not self.env.company.sit_facturacion:
            _logger.info("FE OFF: omitiendo sit__fex_base_map_invoice_info_dtejson")
            return None

        _logger.info("SIT sit_base_map_invoice_info_dtejson self = %s", self)
        invoice_info = {}
        invoice_info["identificacion"] = self.sit__fex_base_map_invoice_info_identificacion()
        _logger.info("SIT sit_base_map_invoice_info_dtejson = %s", invoice_info)
        invoice_info["emisor"] = self.sit__fex_base_map_invoice_info_emisor()
        invoice_info["receptor"] = self.sit__fex_base_map_invoice_info_receptor()
        invoice_info["otrosDocumentos"] = None
        invoice_info["ventaTercero"] = None

        cuerpoDocumento = self.sit_fex_base_map_invoice_info_cuerpo_documento()
        _logger.info("SIT Cuerpo documento =%s", cuerpoDocumento)
        invoice_info["cuerpoDocumento"] = cuerpoDocumento[0] if cuerpoDocumento else None
        _logger.info("SIT CUERPO_DOCUMENTO = %s", invoice_info["cuerpoDocumento"])
        if invoice_info["cuerpoDocumento"] is None:
            raise UserError(_('La Factura no tiene línea de Productos válida.'))

        invoice_info["resumen"] = self.sit_fex_base_map_invoice_info_resumen()
        invoice_info["apendice"] = None
        return invoice_info

    def sit__fex_base_map_invoice_info_identificacion(self):
        if not self.env.company.sit_facturacion:
            _logger.info("FE OFF: omitiendo sit__fex_base_map_invoice_info_identificacion")
            return None

        _logger.info("SIT sit_base_map_invoice_info_identificacion self = %s", self)
        invoice_info = {}
        invoice_info["version"] = int(self.journal_id.sit_tipo_documento.version)

        ambiente = None
        if config_utils:
            ambiente = config_utils.compute_validation_type_2(self.env)
        invoice_info["ambiente"] = ambiente

        invoice_info["tipoDte"] = self.journal_id.sit_tipo_documento.codigo
        invoice_info["numeroControl"] = self.name
        invoice_info["codigoGeneracion"] = self.hacienda_codigoGeneracion_identificacion
        invoice_info["tipoModelo"] = int(self.journal_id.sit_modelo_facturacion)
        invoice_info["tipoOperacion"] = int(self.journal_id.sit_tipo_transmision)
        invoice_info["tipoContingencia"] = None
        invoice_info["motivoContigencia"] = None

        # Fecha/hora emisión (zona América/El_Salvador)
        FechaEmi = self.invoice_date or (config_utils.get_fecha_emi() if config_utils else None)
        if isinstance(FechaEmi, str):
            FechaEmi = datetime.strptime(FechaEmi, '%Y-%m-%d').date()
        if not FechaEmi:
            FechaEmi = fields.Date.context_today(self)
        _logger.info("SIT FechaEmi = %s (%s)", FechaEmi, type(FechaEmi))
        invoice_info["fecEmi"] = FechaEmi.strftime('%Y-%m-%d')
        invoice_info["horEmi"] = self.invoice_time
        invoice_info["tipoMoneda"] = self.currency_id.name
        _logger.info("SIT sit_fex_ base_map_invoice_info_identificacion1 = %s", invoice_info)
        return invoice_info

    def sit__fex_base_map_invoice_info_emisor(self):
        if not self.env.company.sit_facturacion:
            _logger.info("FE OFF: omitiendo sit__fex_base_map_invoice_info_emisor")
            return None

        _logger.info("SIT sit__fex_base_map_invoice_info_emisor self = %s", self)
        invoice_info, direccion = {}, {}
        nit = (self.company_id.vat or '').replace("-", '') if self.company_id else None
        nrc = (self.company_id.company_registry or '').replace("-", '') if self.company_id else None

        invoice_info["nit"] = nit or None
        invoice_info["nrc"] = nrc or None
        invoice_info["nombre"] = self.company_id.name
        invoice_info["codActividad"] = getattr(self.company_id.codActividad, 'codigo', None)
        invoice_info["descActividad"] = getattr(self.company_id.codActividad, 'valores', None)
        invoice_info["nombreComercial"] = self.company_id.nombreComercial or None
        invoice_info["tipoEstablecimiento"] = getattr(self.company_id.tipoEstablecimiento, 'codigo', None)

        direccion["departamento"] = getattr(self.company_id.state_id, 'code', None)
        direccion["municipio"] = getattr(self.company_id.munic_id, 'code', None)
        direccion["complemento"] = self.company_id.street
        invoice_info["direccion"] = direccion
        invoice_info["telefono"] = self.company_id.phone or None
        invoice_info["correo"] = self.company_id.email
        invoice_info["codEstableMH"] = self.journal_id.sit_codestable
        invoice_info["codEstable"] = self.journal_id.sit_codestable
        invoice_info["codPuntoVentaMH"] = self.journal_id.sit_codpuntoventa
        invoice_info["codPuntoVenta"] = self.journal_id.sit_codpuntoventa

        # Tipo de item exportación (derivado de líneas)
        tipo_bien = tipo_servicio = False
        for line in self.invoice_line_ids:
            if not getattr(line, 'custom_discount_line', False):
                try:
                    tipo = int(getattr(line.product_id.tipoItem, 'codigo', 0))
                except Exception:
                    tipo = 0
                if tipo == 1:
                    tipo_bien = True
                elif tipo == 2:
                    tipo_servicio = True
                if tipo_bien and tipo_servicio:
                    break

        if tipo_bien and tipo_servicio:
            tipo_item_exportacion = 3
        elif tipo_bien:
            tipo_item_exportacion = 1
        elif tipo_servicio:
            tipo_item_exportacion = 2
        else:
            tipo_item_exportacion = 0

        # Si tienes campo en factura, úsalo; si no, deriva:
        invoice_info["tipoItemExpor"] = int(getattr(self.tipoItemEmisor, 'codigo', tipo_item_exportacion) or 0)

        recinto_fiscal = None
        if self.sale_order_id and self.sale_order_id.recintoFiscal:
            recinto_fiscal = str(self.sale_order_id.recintoFiscal.codigo)
        _logger.info("SIT Recinto fiscal: %s (tipo: %s)", recinto_fiscal,
                     type(recinto_fiscal).__name__ if recinto_fiscal is not None else None)
        invoice_info["recintoFiscal"] = recinto_fiscal if recinto_fiscal else None
        _logger.info("SIT regimen de exportacion = %s", self.sit_regimen)
        invoice_info["regimen"] = getattr(self.sit_regimen, 'codigo', None)
        return invoice_info

    def sit__fex_base_map_invoice_info_receptor(self):
        if not self.env.company.sit_facturacion:
            _logger.info("FE OFF: omitiendo sit__fex_base_map_invoice_info_receptor")
            return None

        _logger.info("SIT sit_base_map_invoice_info_receptor self = %s", self)
        invoice_info = {}

        raw_doc = None
        if self.partner_id:
            if self.partner_id.vat:
                raw_doc = self.partner_id.vat.replace("-", "")
            elif self.partner_id.dui:
                raw_doc = self.partner_id.dui.replace("-", "")

        _logger.info("SIT Documento receptor = %s", raw_doc)
        if isinstance(raw_doc, str):
            invoice_info["numDocumento"] = raw_doc

        tipoDocumento = (self.partner_id.l10n_latam_identification_type_id.codigo
                         if self.partner_id.l10n_latam_identification_type_id and raw_doc else None)
        invoice_info["tipoDocumento"] = tipoDocumento
        invoice_info["nombre"] = self.partner_id.name

        if self.partner_id.country_id:
            invoice_info["codPais"] = self.partner_id.country_id.code
            invoice_info["nombrePais"] = self.partner_id.country_id.name
        else:
            invoice_info["codPais"] = None
            invoice_info["nombrePais"] = None

        tipoPersona = 1 if self.partner_id.company_type == 'person' else (
            2 if self.partner_id.company_type == 'company' else 0)
        invoice_info["tipoPersona"] = tipoPersona
        invoice_info["nombreComercial"] = self.partner_id.nombreComercial or None
        invoice_info["descActividad"] = getattr(self.partner_id.codActividad, 'valores', None)
        invoice_info["complemento"] = self.partner_id.street
        invoice_info["telefono"] = self.partner_id.phone or None
        invoice_info["correo"] = self.partner_id.email or None
        return invoice_info

    def sit_fex_base_map_invoice_info_cuerpo_documento(self):
        if not self.env.company.sit_facturacion:
            _logger.info("FE OFF: omitiendo sit_fex_base_map_invoice_info_cuerpo_documento")
            return None

        _logger.info("SIT sit_base_map_invoice_info_cuerpo_documento self = %s", self)
        lines = []
        item_numItem = 0
        total_Gravada = 0.0
        totalIva = 0.0
        codigo_tributo = None

        for line in self.invoice_line_ids:
            if getattr(line, 'custom_discount_line', False):
                continue

            item_numItem += 1
            line_temp, lines_tributes = {}, []

            line_temp["numItem"] = item_numItem
            line_temp["codigo"] = line.product_id.default_code
            line_temp["descripcion"] = line.name
            line_temp["cantidad"] = line.quantity

            if not line.product_id.uom_hacienda:
                raise UserError(_("UOM de producto no configurado para:  %s") % (line.product_id.name))
            # Si el tipo seleccionado en la factura es 'servicio' (usa constants si existe)
            is_serv = bool(self.tipoItemEmisor and hasattr(self.tipoItemEmisor, 'codigo')
                           and constants and hasattr(constants, 'ITEM_SERVICIOS')
                           and self.tipoItemEmisor.codigo == constants.ITEM_SERVICIOS)
            uniMedida = 99 if is_serv else int(getattr(line.product_id.uom_hacienda, 'codigo', 7) or 7)
            line_temp["uniMedida"] = int(uniMedida)

            line_temp["montoDescu"] = round(line.quantity * (line.price_unit * (line.discount / 100.0)), 2) or 0.0
            ventaGravada = round(getattr(line, 'precio_gravado', 0.0), 2)
            line_temp["ventaGravada"] = ventaGravada

            codigo_tributo_codigo = None
            for t in line.tax_ids:
                codigo_tributo_codigo = getattr(getattr(t, 'tributos_hacienda', None), 'codigo', None)
                codigo_tributo = getattr(t, 'tributos_hacienda', None)
            if codigo_tributo_codigo:
                lines_tributes.append(codigo_tributo_codigo)

            # Si no hay impuestos, base = qty * price_unit
            vat_taxes_amounts = line.tax_ids.compute_all(
                line.price_unit, self.currency_id, line.quantity,
                product=line.product_id, partner=self.partner_id,
            )
            if vat_taxes_amounts.get('taxes'):
                vat_taxes_amount = vat_taxes_amounts['taxes'][0]['amount']
                sit_amount_base = round(vat_taxes_amounts['taxes'][0]['base'], 2)
            else:
                vat_taxes_amount = 0.0
                sit_amount_base = round(line.quantity * line.price_unit, 2)

            line_temp["noGravado"] = 0.0

            # Precio unitario final a reportar (tu campo personalizado)
            line_temp["precioUni"] = round(getattr(line, 'precio_unitario', line.price_unit), 2)

            # Recalcular venta gravada con descuentos
            ventaGravada = line.quantity * (getattr(line, 'precio_unitario', line.price_unit) - (
                        getattr(line, 'precio_unitario', line.price_unit) * (line.discount / 100.0)))
            total_Gravada += ventaGravada
            line_temp["ventaGravada"] = round(ventaGravada, 2)

            totalIva += round(
                vat_taxes_amount - ((((line.price_unit * line.quantity) * (line.discount / 100.0)) / 1.13) * 0.13), 2)

            lines.append(line_temp)
            # 🔧 Aquí el método correcto es con sufijo _fex
            self.check_parametros_linea_firmado_fex(line_temp)

        _logger.info("SIT totalIVA ______1 =%s", totalIva)
        # Devuelve la misma estructura que esperas más arriba
        # (lines, codigo_tributo, total_Gravada, line.tax_ids, totalIva)
        last_line_taxes = self.invoice_line_ids[-1].tax_ids if self.invoice_line_ids else self.env['account.tax']
        return lines, codigo_tributo, total_Gravada, last_line_taxes, totalIva

    def sit_fex_base_map_invoice_info_resumen(self):
        if not self.env.company.sit_facturacion:
            _logger.info("FE OFF: omitiendo sit_fex_base_map_invoice_info_resumen")
            return None

        _logger.info("SIT sit_base_map_invoice_info_resumen self = %s", self)
        invoice_info = {}
        invoice_info["totalGravada"] = round(getattr(self, 'total_gravado', 0.0), 2)
        invoice_info["totalNoGravado"] = 0
        invoice_info["descuento"] = round(getattr(self, 'descuento_gravado', 0.0), 2)
        invoice_info["porcentajeDescuento"] = round(getattr(self, 'descuento_global', 0.0), 2)
        invoice_info["totalDescu"] = round(getattr(self, 'total_descuento', 0.0), 2)
        invoice_info["montoTotalOperacion"] = round(getattr(self, 'total_operacion', 0.0), 2)
        invoice_info["totalPagar"] = round(getattr(self, 'total_pagar', 0.0), 2)
        invoice_info["totalLetras"] = self.amount_text
        invoice_info["condicionOperacion"] = int(self.condiciones_pago)

        pagos = {
            "codigo": getattr(self.forma_pago, 'codigo', None),
            "montoPago": round(getattr(self, 'total_pagar', 0.0), 2),
            "referencia": getattr(self, 'sit_referencia', None),
        }
        invoice_info["codIncoterms"] = getattr(self.invoice_incoterm_id, 'codigo_mh', None)
        invoice_info["descIncoterms"] = getattr(self.invoice_incoterm_id, 'name', None)
        invoice_info["observaciones"] = None
        invoice_info["flete"] = getattr(self, 'flete', 0.0)
        invoice_info["numPagoElectronico"] = None
        invoice_info["seguro"] = getattr(self, 'seguro', 0.0)

        if int(self.condiciones_pago) in [2]:
            pagos["plazo"] = getattr(self.sit_plazo, 'codigo', None)
            pagos["periodo"] = getattr(self, 'sit_periodo', None)
            invoice_info["pagos"] = [pagos]
            pagos["montoPago"] = 0.0
        else:
            pagos["plazo"] = None
            pagos["periodo"] = None
            invoice_info["pagos"] = [pagos]
        return invoice_info

    def sit_obtener_payload_fex_dte_info(self, ambiente, doc_firmado):
        if not self.env.company.sit_facturacion:
            _logger.info("FE OFF: omitiendo sit_obtener_payload_fex_dte_info")
            return None

        _logger.info("SIT sit_obtener_payload_exp_dte_info self = %s", self)
        invoice_info = {}
        nit = (self.company_id.vat or "").replace("-", "")
        invoice_info["ambiente"] = ambiente
        invoice_info["idEnvio"] = 1
        invoice_info["version"] = 1
        invoice_info["documento"] = doc_firmado
        invoice_info["codigoGeneracion"] = self.sit_generar_uuid()
        return invoice_info

    def sit_generar_uuid(self):
        if not self.env.company.sit_facturacion:
            _logger.info("FE OFF: omitiendo sit_generar_uuid")
            return None
        import uuid
        return str(uuid.uuid4()).upper()
