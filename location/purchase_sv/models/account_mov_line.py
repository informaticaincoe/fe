from odoo import api, fields, models, _

import logging
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

    apply_percepcion = fields.Boolean(
        string="Aplicar percepción 1%", default=False,
        store=True,   # no se guarda en BD
        compute=False  # editable por el usuario
    )

    percepcion_amount = fields.Monetary(
        string="Monto percepcion",
        currency_field='currency_id',
        readonly=True,
        store=True,
        default=0.0
    )

    @api.depends(
        'product_id', 'quantity', 'price_unit', 'discount',
        'tax_ids', 'move_id.journal_id', 'move_id.sit_tipo_documento_id'
    )
    def _compute_precios_tipo_venta(self):
        """
        Hereda el compute de l10n_invoice_sv para reutilizar la lógica de ventas,
        pero ajusta los cálculos cuando el documento es una compra.
        """
        super(AccountMoveLine, self)._compute_precios_tipo_venta()

        for line in self:
            move = line.move_id

            # Solo aplicar si es factura o nota de crédito de compra
            if move.move_type not in ('in_invoice', 'in_refund'):
                continue

            # Tipo de documento en compras
            tipo_doc = move.sit_tipo_documento_id.codigo if move.sit_tipo_documento_id else None

            _logger.info("SIT [Compras] Tipo documento: %s", tipo_doc)

            # Ejemplo: aplicar el mismo criterio que ventas, pero según tipo_doc
            if tipo_doc == constants.COD_DTE_FE:
                if line.tax_ids and line.tax_ids.price_include_override == 'tax_excluded':
                    line.precio_unitario = line.price_unit + line.iva_unitario
                    _logger.info("SIT [Compras] FCF con IVA incluido: %s", line.precio_unitario)
                else:
                    line.precio_unitario = line.price_unit
                    _logger.info("SIT [Compras] FCF con precio sin IVA: %s", line.precio_unitario)
            else:
                # Para otros tipos de documento en compras
                line.precio_unitario = line.price_unit
                _logger.info("SIT [Compras] Tipo doc distinto, precio_unitario = price_unit (%s)", line.precio_unitario)

    @api.onchange('apply_percepcion', 'price_subtotal')
    def _onchange_apply_percepcion(self):
        """Si el usuario marca la casilla, calcular el 1% del subtotal."""
        for line in self:
            if line.apply_percepcion:
                line.percepcion_amount = round(line.price_subtotal * 0.01, 2)
            else:
                line.percepcion_amount = 0.0
