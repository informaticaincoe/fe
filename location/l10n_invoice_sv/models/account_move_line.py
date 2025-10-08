from odoo import api, fields, models, _
import logging
from decimal import Decimal, ROUND_HALF_UP
_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import config_utils
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo config_utils [hacienda ws-account_move]")
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

    @api.depends('product_id','quantity', 'price_unit', 'discount', 'tax_ids', 'move_id.journal_id')
    def _compute_total_iva(self):
        for line in self:
            vat_amount = 0.0
            if line.tax_ids:
                # Solo considerar impuestos tipo IVA
                _logger.info("Tax_ids: %s", line.tax_ids.mapped('name'))
                for tax in line.tax_ids:
                    _logger.info("Revisando impuesto: %s, tipo: %s, amount: %s, price_include_override: %s", tax.name, tax.amount_type, tax.amount, tax.price_include_override)
                    if 'IVA' in tax.name and tax.amount_type == 'percent':
                        vat_amount += (line.price_subtotal * tax.amount) / 100.0
            line.total_iva = vat_amount
            _logger.info("Total IVA final para la línea: %s", line.total_iva)
            _logger.info("=====================================")

    @api.depends('product_id', 'quantity', 'price_unit', 'discount', 'tax_ids', 'move_id.journal_id')
    def _compute_iva_unitario(self):
        for line in self:
            vat_amount = 0.0
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

            _logger.info("SIT Producto: %s", line.product_id)
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

            if line.move_id.move_type in ('out_invoice', 'out_refund'):
                if line.journal_id.code == 'FCF':
                    if line.tax_ids.price_include_override == 'tax_excluded':
                        line.precio_unitario = line.price_unit + (line.iva_unitario)
                        _logger.info("line.precio_unitario  FCF con iva incluido %s", line.precio_unitario)
                    else:
                        line.precio_unitario = line.price_unit
                else:
                    line.precio_unitario = line.price_unit
                    _logger.info("line.precio_unitario sin incluir iva %s", line.precio_unitario)

                # Asignar según tipo_venta
                if tipo_venta == 'gravado':
                    if line.journal_id.code == 'FCF':
                        if line.tax_ids.price_include_override == 'tax_excluded':
                            line.precio_gravado = precio_total + line.total_iva
                        else:
                            line.precio_gravado = precio_total
                    else:
                        line.precio_gravado = precio_total

            elif tipo_venta == 'exento':
                line.precio_exento = precio_total
            elif tipo_venta == 'no_sujeto':
                line.precio_no_sujeto = precio_total
            _logger.info("SIT Precio total gravado= %s, total exento= %s, total no sujeto= %s", line.precio_gravado, line.precio_exento, line.precio_no_sujeto)
            _logger.info("==== FIN LINEA ID: %s ====", line.id)
