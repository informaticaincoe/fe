from odoo import api, fields, models, _
import logging
from decimal import Decimal, ROUND_HALF_UP
_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import config_utils
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo config_utils [PURCHASE account_move_line]")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    config_utils = None

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    precio_unitario = fields.Float(string='Precio Unitario', compute='_compute_precios_tipo_venta', store=True)
    precio_gravado = fields.Float(string='Gravado', compute='_compute_precios_tipo_venta', store=True)
    precio_exento = fields.Float(string='Exento', compute='_compute_precios_tipo_venta', store=True)
    precio_no_sujeto = fields.Float(string='No Sujeto', compute='_compute_precios_tipo_venta', store=True)
    custom_discount_line = fields.Boolean(string='Es línea de descuento', default=False)

    # Puentes desde el move (no se almacenan)
    move_is_purchase = fields.Boolean(related='move_id.is_purchase', store=False)
    move_codigo_tipo_documento = fields.Char(related='move_id.codigo_tipo_documento', store=False)

    codigo_tipo_documento = fields.Char(
        related='journal_id.sit_tipo_documento.codigo',
        string='Código Tipo Documento',
        store=True,
        # compute='_compute_codigo_tipo_documento'
    )

    # x_line_vat_amount = fields.Monetary(
    #     string="IVA",
    #     currency_field='currency_id',
    #     # compute='_compute_total_iva',
    #     store=True  # no se guarda, solo se calcula al vuelo
    # )

    total_iva = fields.Monetary(
        string="IVA",
        currency_field='currency_id',
        compute='_compute_total_iva',
        store=True  # no se guarda, solo se calcula al vuelo
    )

    iva_unitario = fields.Monetary(
        string="IVA unitario",
        currency_field='currency_id',
        compute='_compute_iva_unitario',
        store=True  # no se guarda, solo se calcula al vuelo
    )

    @api.depends('product_id', 'quantity', 'price_unit', 'discount', 'tax_ids', 'move_id.journal_id')
    def _compute_total_iva(self):
        for line in self:
            vat_amount = 0.0
            line.total_iva = 0.0
            tipo_doc = line.move_id.journal_id.sit_tipo_documento if line.move_id.journal_id else None

            if line.move_id.move_type in (constants.TYPE_ENTRY, constants.OUT_RECEIPT, constants.IN_RECEIPT):
                _logger.info("[SIT] Se omite _compute_total_iva para movimiento tipo '%s' (ID: %s)", line.move_id.move_type, line.move_id.id)
                continue

            # Ventas → solo si hay facturación electrónica
            if line.move_id.move_type in (constants.OUT_INVOICE, constants.OUT_REFUND) and not line.move_id.company_id.sit_facturacion:
                _logger.info("SIT _compute_total_iva | Venta detectada sin facturación -> move_id: %s, se omite cálculo de IVA", line.move_id.id)
                continue

            # Verificamos si es una factura de compra
            if line.move_id.move_type in (constants.IN_INVOICE, constants.IN_REFUND):
                if not tipo_doc or tipo_doc.codigo != constants.COD_DTE_FSE or (
                        tipo_doc.codigo == constants.COD_DTE_FSE and not line.move_id.company_id.sit_facturacion):
                    _logger.info("SIT _compute_total_iva | Compra normal o sujeto excluido sin facturación -> move_id: %s, se omite cálculo de IVA", line.move_id.id)
                    continue

            # Si no es una compra, procedemos con el cálculo del IVA
            if line.tax_ids:
                # Solo considerar impuestos tipo IVA
                _logger.info("Tax_ids: %s", line.tax_ids.mapped('name'))
                for tax in line.tax_ids:
                    _logger.info("Revisando impuesto: %s, tipo: %s, amount: %s, price_include_override: %s", tax.name,
                                 tax.amount_type, tax.amount, tax.price_include_override)
                    if 'IVA' in tax.name and tax.amount_type == 'percent':
                        vat_amount += (line.price_subtotal * tax.amount) / 100.0
            line.total_iva = vat_amount
            _logger.info("Total IVA final para la línea: %s", line.total_iva)
            _logger.info("=====================================")

    @api.depends('product_id', 'quantity', 'price_unit', 'discount', 'tax_ids', 'move_id.journal_id')
    def _compute_iva_unitario(self):
        for line in self:
            vat_amount = 0.0
            line.iva_unitario = 0.0
            tipo_doc = line.move_id.journal_id.sit_tipo_documento if line.move_id.journal_id else None

            if line.move_id.move_type in (constants.TYPE_ENTRY, constants.OUT_RECEIPT, constants.IN_RECEIPT):
                _logger.info("[SIT] Se omite _compute_iva_unitario para movimiento tipo '%s' (ID: %s)", line.move_id.move_type, line.move_id.id)
                continue

            # Ventas → solo si hay facturación electrónica
            if line.move_id.move_type in (constants.OUT_INVOICE, constants.OUT_REFUND) and not line.move_id.company_id.sit_facturacion:
                _logger.info("SIT _compute_iva_unitario | Venta detectada sin facturación -> move_id: %s, no se calcula IVA unitario", line.move_id.id)
                continue

            # Compras → solo si es sujeto excluido con facturación o compras normales DTE tipo FSE
            if line.move_id.move_type in (constants.IN_INVOICE, constants.IN_REFUND):
                if not tipo_doc or tipo_doc.codigo != constants.COD_DTE_FSE or (
                        tipo_doc.codigo == constants.COD_DTE_FSE and not line.move_id.company_id.sit_facturacion):
                    _logger.info("SIT _compute_iva_unitario | Compra normal o sujeto excluido sin facturación -> move_id: %s, no se calcula IVA unitario", line.move_id.id)
                    line.iva_unitario = 0.0
                    continue

            if line.tax_ids:
                # Solo considerar impuestos tipo IVA
                _logger.info("Tax_ids: %s", line.tax_ids.mapped('name'))
                for tax in line.tax_ids:
                    _logger.info("Revisando impuesto: %s, tipo: %s, amount: %s", tax.name, tax.amount_type, tax.amount)
                    if 'IVA' in tax.name and tax.amount_type == 'percent':
                        vat_amount += ((line.price_subtotal * tax.amount) / 100.0) / line.quantity
            line.iva_unitario = vat_amount
            _logger.info("IVA unitario final para la línea: %s", line.iva_unitario)
            _logger.info("=====================================")

    @api.depends('move_id.journal_id.sit_tipo_documento.codigo')
    def _compute_codigo_tipo_documento(self):
        for line in self:
            line.codigo_tipo_documento = line.move_id.journal_id.sit_tipo_documento.codigo or False
            _logger.info("SIT Tipo de documento(dte): %s", line.codigo_tipo_documento)

    @api.depends('product_id', 'quantity', 'price_unit', 'discount', 'tax_ids', 'move_id.journal_id')
    def _compute_precios_tipo_venta(self):
        for line in self:
            line.precio_gravado = 0.0
            line.precio_exento = 0.0
            line.precio_no_sujeto = 0.0
            tipo_doc = line.move_id.journal_id.sit_tipo_documento if line.move_id.journal_id else None

            if line.move_id.move_type in (constants.TYPE_ENTRY, constants.OUT_RECEIPT, constants.IN_RECEIPT):
                _logger.info("[SIT] Se omite _compute_precios_tipo_venta para movimiento tipo '%s' (ID: %s)", line.move_id.move_type, line.move_id.id)
                continue

            # Ventas → solo si hay facturación electrónica
            if line.move_id.move_type in (constants.OUT_INVOICE, constants.OUT_REFUND) and not line.move_id.company_id.sit_facturacion:
                _logger.info("SIT _compute_precios_tipo_venta | Venta sin facturación -> move_id: %s, no se calcula precio por tipo de venta", line.move_id.id)
                continue

            # Compras → solo si es sujeto excluido con facturación o compras normales DTE tipo FSE
            if line.move_id.move_type in (constants.IN_INVOICE, constants.IN_REFUND):
                if not tipo_doc or tipo_doc.codigo != constants.COD_DTE_FSE or (
                        tipo_doc.codigo == constants.COD_DTE_FSE and not line.move_id.company_id.sit_facturacion):
                    _logger.info("SIT _compute_precios_tipo_venta | Compra normal o sujeto excluido sin facturación -> move_id: %s, no se calcula precio por tipo de venta", line.move_id.id)
                    continue

            _logger.info("==== INICIO LINEA ID: %s ====", line.id)
            _logger.info("Producto: %s (%s)", line.product_id.display_name, line.product_id.id)

            if not line.product_id:
                _logger.info("Sin producto asignado, se omite la línea")
                continue

            tipo_venta = line.product_id.tipo_venta
            if not tipo_venta:
                _logger.info("Sin tipo_venta definido para el producto [%s]", line.product_id.display_name)
                continue
            _logger.info("Tipo de venta del producto: %s", tipo_venta)

            currency = line.move_id.currency_id
            cantidad = line.quantity
            descuento = line.discount or 0.0
            base_price_unit = line.price_unit
            _logger.info("Valores base -> price_unit: %s, quantity: %s, discount: %s", base_price_unit, cantidad,
                         descuento)

            subtotal_linea_con_descuento = base_price_unit * cantidad * (1 - descuento / 100.0)
            precio_total = currency.round(subtotal_linea_con_descuento)
            _logger.info("Subtotal con descuento: %s, precio_total redondeado: %s", subtotal_linea_con_descuento,
                         precio_total)

            # Ajuste para ventas
            if line.move_id.move_type in (constants.OUT_INVOICE, constants.OUT_REFUND):
                _logger.info("Ventas detectadas -> move_type: %s, journal_code: %s", line.move_id.move_type,
                             line.journal_id.code)
                if line.journal_id.code == 'FCF' and line.tax_ids.price_include_override == 'tax_excluded':
                    line.precio_unitario = line.price_unit + line.iva_unitario
                    _logger.info("Precio unitario FCF con IVA incluido: %s", line.precio_unitario)
                else:
                    line.precio_unitario = line.price_unit
                    _logger.info("Precio unitario estándar: %s", line.precio_unitario)

                # Asignar según tipo_venta
                if tipo_venta == constants.TIPO_VENTA_PROD_GRAV:
                    if line.journal_id.code == 'FCF' and line.tax_ids.price_include_override == 'tax_excluded':
                        line.precio_gravado = precio_total + line.total_iva
                    else:
                        line.precio_gravado = precio_total
                    _logger.info("Precio gravado asignado: %s", line.precio_gravado)

            elif tipo_venta == constants.TIPO_VENTA_PROD_EXENTO:
                line.precio_exento = precio_total
                _logger.info("Precio exento asignado: %s", line.precio_exento)
            elif tipo_venta == constants.TIPO_VENTA_PROD_NO_SUJETO:
                line.precio_no_sujeto = precio_total
                _logger.info("Precio no sujeto asignado: %s", line.precio_no_sujeto)

            _logger.info("Precio final -> gravado: %s, exento: %s, no_sujeto: %s",
                         line.precio_gravado, line.precio_exento, line.precio_no_sujeto)
            _logger.info("==== FIN LINEA ID: %s ====", line.id)
