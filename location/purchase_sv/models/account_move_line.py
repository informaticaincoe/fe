from odoo import api, fields, models, _
from odoo.tools.float_utils import float_round

import logging
_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import constants
    from odoo.addons.common_utils.utils import config_utils
    _logger.info("SIT Modulo constants [purchase-account_move_line]")
except ImportError as e:
    _logger.error(f"Error al importar 'constants': {e}")
    constants = None
    config_utils = None

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    apply_percepcion = fields.Boolean(
        string="Percepción 1%",
        default=False,
    )

    percepcion_amount = fields.Monetary(
        string="Monto percepción",
        currency_field='currency_id',
        readonly=True,
        store=True,
        compute='_compute_percepcion_retencion_amount'
    )

    apply_retencion = fields.Boolean(
        string="Retencion IVA",
        default=False,
    )

    retencion_amount = fields.Monetary(
        string="Monto retención IVA",
        currency_field='currency_id',
        readonly=True,
        store=True,
        compute='_compute_percepcion_retencion_amount'
    )

    renta_percentage = fields.Float(
        string="% Renta",
        digits=(5, 2),
        default=0.0,
        help="Porcentaje de renta que se aplicará al subtotal de la línea"
    )

    renta_amount = fields.Monetary(
        string="Renta",
        currency_field='currency_id',
        store=True,
    )

    @api.depends('apply_percepcion', 'apply_retencion', 'renta_percentage', 'price_subtotal')
    def _compute_percepcion_retencion_amount(self):
        """
        Calcula los montos de percepción, retención de IVA y renta sobre el subtotal de la línea.

        Lógica:
        - Aplica solo a facturas de proveedor (IN_INVOICE, IN_REFUND) que no sean FSE.
        - Los porcentajes se obtienen desde la configuración global.
        - Si el campo correspondiente (apply_*) no está activo, reinicia el monto a 0.
        - Tras calcular los montos de línea, actualiza los totales en la factura.
        Campos afectados:
            - percepcion_amount
            - retencion_amount
            - renta_amount
        """
        for line in self:
            tipo_doc = line.move_id.journal_id.sit_tipo_documento if line.move_id.journal_id else None

            # Solo aplica a facturas de compra que no sean FSE
            if line.move_id.move_type in (constants.IN_INVOICE, constants.IN_REFUND) and (
                    not tipo_doc or tipo_doc.codigo != constants.COD_DTE_FSE
            ):
                # === PERCEPCIÓN ===
                if line.apply_percepcion:
                    porc_percepcion = config_utils.get_config_value(self.env, constants.config_percepcion, line.company_id.id)
                    try:
                        porc_percepcion = float(porc_percepcion) / 100.0
                    except (TypeError, ValueError):
                        porc_percepcion = 0.0

                    line.percepcion_amount = float_round(
                        line.price_subtotal * porc_percepcion,
                        precision_rounding=line.move_id.currency_id.rounding
                    )
                    _logger.info(
                        "SIT | Línea '%s': percepción aplicada (%s%%) subtotal=%s → percepcion_amount=%s",
                        line.name, porc_percepcion * 100, line.price_subtotal, line.percepcion_amount
                    )
                else:
                    line.percepcion_amount = 0.0
                    _logger.info("SIT | Línea '%s': sin percepción, monto=0", line.name)

                # === RETENCIÓN IVA ===
                if line.apply_retencion:
                    porc_retencion = config_utils.get_config_value(
                        self.env, constants.config_retencion_iva, line.company_id.id
                    )
                    try:
                        porc_retencion = float(porc_retencion) / 100.0
                    except (TypeError, ValueError):
                        porc_retencion = 0.0

                    line.retencion_amount = float_round(
                        line.price_subtotal * porc_retencion,
                        precision_rounding=line.move_id.currency_id.rounding
                    )
                    _logger.info(
                        "SIT | Línea '%s': retención IVA aplicada (%s%%) subtotal=%s → retencion_amount=%s",
                        line.name, porc_retencion * 100, line.price_subtotal, line.retencion_amount
                    )
                else:
                    line.retencion_amount = 0.0
                    _logger.info("SIT | Línea '%s': sin retención IVA, monto=0", line.name)

                # === RENTA ===
                if line.renta_percentage > 0:
                    line.renta_amount = float_round(
                        line.price_subtotal * (line.renta_percentage / 100),
                        precision_rounding=line.move_id.currency_id.rounding
                    )
                    _logger.info(
                        "SIT | Línea '%s': renta aplicada (%s%%) subtotal=%s → renta_amount=%s",
                        line.name, line.renta_percentage, line.price_subtotal, line.renta_amount
                    )
                else:
                    line.renta_amount = 0.0
                    _logger.info("SIT | Línea '%s': sin renta, monto=0", line.name)

                # === ACTUALIZA TOTALES EN LA FACTURA ===
                if line.move_id:
                    line.move_id._compute_retencion()
