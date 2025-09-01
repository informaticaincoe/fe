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

    codigo_tipo_documento = fields.Char(string='Código Tipo Documento', store=True,
                                        compute='_compute_codigo_tipo_documento')

    @api.depends('move_id.journal_id.sit_tipo_documento.codigo')
    def _compute_codigo_tipo_documento(self):
        for line in self:
            line.codigo_tipo_documento = line.move_id.journal_id.sit_tipo_documento.codigo or False
            _logger.info("SIT Tipo de documento(dte): %s", line.codigo_tipo_documento)

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
            # if config_utils:
            #     iva = config_utils.get_config_value(self.env, 'valor_iva', self.company_id.id)
            # else:
            #     _logger.error("config_utils no disponible. Valor IVA por defecto 0.0.")
            # _logger.info("SIT Configuracion IVA: %s", iva)

            # Calcular precio total con descuento
            # Se verifica el tipo de documento a generar, si es factura el precio debe contener impuesto(IVA), si es CCF no debe tener impuestos(IVA)
            if line.move_id.journal_id.sit_tipo_documento.codigo == "01":
                # Calcular precio unitario con descuento aplicado
                price_after_discount = round(line.price_unit * (1 - (line.discount or 0.0) / 100.0), 6)

                # Usamos compute_all para sumar impuestos
                taxes = line.tax_ids.compute_all(
                    price_after_discount,
                    quantity=line.quantity,
                    product=line.product_id,
                    partner=line.move_id.partner_id
                )

                #precio_total = round( (line.price_subtotal * line.quantity * (1 - (line.discount or 0.0) / 100.0)), 6)
                precio_total = round(taxes['total_included'], 6)  # Incluye impuestos
                line.precio_unitario = round(line.price_unit, 6)
                # line.precio_unitario = round(price_after_discount, 6)

            elif line.move_id.journal_id.sit_tipo_documento.codigo != "01" and line.move_id.journal_id.sit_tipo_documento.codigo != "11":
                precio_total = round( (line.price_subtotal * line.quantity * (1 - (line.discount or 0.0) / 100.0)), 6)
                line.precio_unitario = round(line.price_unit, 6)
            elif line.move_id.journal_id.sit_tipo_documento.codigo == "11":
                precio_total = round((line.price_subtotal * line.quantity * (1 - (line.discount or 0.0) / 100.0)), 6)
                line.precio_unitario = round(line.price_unit, 6)
            _logger.info("SIT Precio total con descuento: %s", precio_total)

            # Asignar según tipo_venta
            if tipo_venta == 'gravado':
                line.precio_gravado = precio_total
            elif tipo_venta == 'exento':
                line.precio_exento = precio_total
            elif tipo_venta == 'no_sujeto':
                line.precio_no_sujeto = precio_total
            _logger.info("SIT Precio total gravado= %s, total exento= %s, total no sujeto= %s", line.precio_gravado, line.precio_exento, line.precio_no_sujeto)
