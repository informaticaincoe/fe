from odoo import api, fields, models, _
import logging
_logger = logging.getLogger(__name__)

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    precio_unitario = fields.Float(string='Precio Unitario', compute='_compute_precios_tipo_venta', store=True)
    precio_gravado = fields.Float(string='Gravado', compute='_compute_precios_tipo_venta', store=True)
    precio_exento = fields.Float(string='Exento', compute='_compute_precios_tipo_venta', store=True)
    precio_no_sujeto = fields.Float(string='No Sujeto', compute='_compute_precios_tipo_venta', store=True)
    custom_discount_line = fields.Boolean(string='Es línea de descuento', default=False)

    @api.depends('product_id', 'quantity', 'price_unit', 'discount', 'tax_ids', 'move_id.journal_id')
    #@api.onchange('product_id', 'quantity', 'price_unit', 'discount')
    def _compute_precios_tipo_venta(self): #def _onchange_precio_tipo_venta(self):
        for line in self:
            _logger.info("SIT Onchange activado para la línea ID: %s", line.id)
            if not line.product_id:
                continue

            tipo_venta = line.product_id.tipo_venta
            if not tipo_venta:
                continue
            _logger.info("SIT tipo_venta del producto [%s]: %s", line.product_id.display_name, tipo_venta)

            # Reinicia los campos
            line.precio_gravado = 0.0
            line.precio_exento = 0.0
            line.precio_no_sujeto = 0.0
            precio_total = 0.0

            # Calcular precio total con descuento
            # Se verifica el tipo de documento a generar, si es factura el precio debe contener impuesto(IVA), si es CCF no debe tener impuestos(IVA)
            if line.move_id.journal_id.sit_tipo_documento.codigo == "01":
                if not line.tax_ids:
                    precio_total = (line.price_unit * line.quantity * (1 - (line.discount or 0.0) / 100.0) * 1.13)
                    line.precio_unitario = line.price_unit * 1.13
                elif line.tax_ids:
                    precio_total = (line.price_unit * line.quantity * (1 - (line.discount or 0.0) / 100.0))
                    line.precio_unitario = line.price_unit

            elif line.move_id.journal_id.sit_tipo_documento.codigo != "01":
                if line.tax_ids:
                    precio_total = line.price_unit * line.quantity * (1 - (line.discount or 0.0) / 100.0) / 1.13
                    line.precio_unitario = line.price_unit / 1.13
                elif not line.tax_ids:
                    precio_total = (line.price_unit * line.quantity * (1 - (line.discount or 0.0) / 100.0))
                    line.precio_unitario = line.price_unit
            _logger.info("SIT Precio total con descuento: %s", precio_total)

            # Asignar según tipo_venta
            if tipo_venta == 'gravado':
                line.precio_gravado = precio_total
            elif tipo_venta == 'exento':
                line.precio_exento = precio_total
            elif tipo_venta == 'no_sujeto':
                line.precio_no_sujeto = precio_total
