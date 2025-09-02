from odoo import api, fields, models, _
import logging
from decimal import Decimal, ROUND_HALF_UP
_logger = logging.getLogger(__name__)

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    precio_unitario = fields.Float(string='Precio Unitario', compute='_compute_precios_tipo_venta', store=True)
    precio_gravado = fields.Float(string='Gravado', compute='_compute_precios_tipo_venta', store=True)
    precio_exento = fields.Float(string='Exento', compute='_compute_precios_tipo_venta', store=True)
    precio_no_sujeto = fields.Float(string='No Sujeto', compute='_compute_precios_tipo_venta', store=True)
    custom_discount_line = fields.Boolean(string='Es línea de descuento', default=False)

    codigo_tipo_documento = fields.Char(string='Código Tipo Documento', store=True,
                                        compute='_compute_codigo_tipo_documento')


    x_line_vat_amount = fields.Monetary(
        string="IVA",
        currency_field='currency_id',
        compute='_compute_x_line_vat_amount',
        store=False  # no se guarda, solo se calcula al vuelo
    )

    def _compute_x_line_vat_amount(self):
        for line in self:
            vat_amount = 0.0
            if line.tax_ids:
                # Solo considerar impuestos tipo IVA
                for tax in line.tax_ids:
                    if 'IVA' in tax.name and tax.amount_type == 'percent':
                        vat_amount += (line.price_subtotal * tax.amount) / 100.0
            line.x_line_vat_amount = vat_amount

    @api.depends('move_id.journal_id.sit_tipo_documento.codigo')
    def _compute_codigo_tipo_documento(self):
        for line in self:
            line.codigo_tipo_documento = line.move_id.journal_id.sit_tipo_documento.codigo or False
            _logger.info("SIT Tipo de documento(dte): %s", line.codigo_tipo_documento)

    @api.depends('product_id', 'quantity', 'price_unit', 'discount', 'tax_ids', 'move_id.journal_id')
    def _compute_precios_tipo_venta(self):
        for line in self:
            _logger.info("==== SIT Onchange activado para la línea ID: %s ====", line.id)
            if not line.product_id:
                _logger.info("SIT Sin producto asignado, se omite la línea")
                continue

            tipo_venta = line.product_id.tipo_venta
            if not tipo_venta:
                _logger.info("SIT Sin tipo_venta definido para el producto [%s]", line.product_id.display_name)
                continue
            _logger.info("SIT Tipo de venta del producto [%s]: %s", line.product_id.display_name, tipo_venta)

            currency = line.move_id.currency_id
            cantidad = line.quantity
            descuento = line.discount or 0.0
            base_price_unit = line.price_unit  # Ahora ya tiene el ajuste correcto

            # Reset precios
            line.precio_gravado = 0.0
            line.precio_exento = 0.0
            line.precio_no_sujeto = 0.0

            # Subtotal línea aplicando descuento
            subtotal_linea_con_descuento = base_price_unit * cantidad * (1 - descuento / 100.0)
            precio_total = currency.round(subtotal_linea_con_descuento)
            line.precio_unitario = line.price_unit

            # Asignar según tipo_venta
            if tipo_venta == 'gravado':
                line.precio_gravado = precio_total
            elif tipo_venta == 'exento':
                line.precio_exento = precio_total
            elif tipo_venta == 'no_sujeto':
                line.precio_no_sujeto = precio_total
            _logger.info("SIT Precio total gravado= %s, total exento= %s, total no sujeto= %s", line.precio_gravado, line.precio_exento, line.precio_no_sujeto)
            _logger.info("==== FIN LINEA ID: %s ====", line.id)

    @api.onchange('product_id', 'tax_ids', 'move_id.journal_id')
    def _onchange_price_unit_tipo_venta(self):
        for line in self:
            if not line.product_id:
                continue

            doc_code = line.move_id.journal_id.sit_tipo_documento.codigo
            impuestos_incluidos = line.tax_ids.filtered(lambda t: t.price_include_override == 'tax_included')
            impuestos_no_incluidos = line.tax_ids.filtered(lambda t: t.price_include_override == 'tax_excluded')

            base_price_unit = line.product_id.lst_price  # Precio de lista
            currency = line.move_id.currency_id

            # ------------------ FE (01) ------------------
            if doc_code == "01":
                if impuestos_no_incluidos:
                    # Agregar impuesto al price_unit
                    tasa_total = sum(t.amount / 100.0 for t in impuestos_no_incluidos)
                    line.price_unit = currency.round(base_price_unit * (1 + tasa_total))
                else:
                    # Precio normal si el impuesto ya está incluido
                    line.price_unit = currency.round(base_price_unit)

            # ------------------ FEX (11) ------------------
            elif doc_code == "11":
                line.price_unit = currency.round(base_price_unit)

            # ------------------ Otros documentos ------------------
            else:
                if impuestos_incluidos:
                    # Quitar impuestos del price_unit
                    tasa_total = sum(t.amount / 100.0 for t in impuestos_incluidos)
                    line.price_unit = currency.round(base_price_unit / (1 + tasa_total))
                else:
                    # Usar price_unit normal
                    line.price_unit = currency.round(base_price_unit)
