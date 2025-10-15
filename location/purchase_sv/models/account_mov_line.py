from odoo import api, fields, models, _

import logging
_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo constants [purchase-account_move_line]")
except ImportError as e:
    _logger.error(f"Error al importar 'constants': {e}")
    constants = None

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
        readonly=True,
        store=True,
    )

    @api.depends('apply_percepcion', 'apply_retencion', 'renta_percentage', 'price_subtotal')
    def _compute_percepcion_retencion_amount(self):
        """Calcula automáticamente el 1% del subtotal si apply_percepcion está activo."""
        for line in self:
            # Verificamos si es una factura de compra
            tipo_doc = line.move_id.journal_id.sit_tipo_documento if line.move_id.journal_id else None
            if line.move_id.move_type in (constants.IN_INVOICE, constants.IN_REFUND) and (not tipo_doc or tipo_doc.codigo != constants.COD_DTE_FSE):
                #---- PERCEPCION 1%
                if line.apply_percepcion:
                    line.percepcion_amount = round(line.price_subtotal * 0.01, 2)
                    _logger.info(
                        "SIT | Línea %s: apply_percepcion=TRUE, price_subtotal=%s, percepcion_amount calculado=%s",
                        line.name, line.price_subtotal, line.percepcion_amount
                    )
                else:
                    line.percepcion_amount = 0.0
                    _logger.info(
                        "SIT | Línea %s: apply_percepcion=FALSE, percepcion_amount reiniciado a 0",
                        line.name
                    )

                # ---- RETENCION 1%
                if line.apply_retencion:
                    line.retencion_amount = round(line.price_subtotal * 0.01, 2)
                    _logger.info(
                        "SIT | Línea %s: apply_retencion=TRUE, price_subtotal=%s, retencion_amount calculado=%s",
                        line.name, line.price_subtotal, line.percepcion_amount
                    )
                else:
                    line.retencion_amount = 0.0
                    _logger.info(
                        "SIT | Línea %s: apply_retencion=FALSE, retencion_amount reiniciado a 0",
                        line.name
                    )

                # --- RENTA ---
                if line.renta_percentage > 0:
                    line.renta_amount = round(line.price_subtotal * line.renta_percentage / 100, 2)
                    _logger.info(
                        "SIT | Línea %s: renta_percentage=%s%%, price_subtotal=%s, renta_amount calculado=%s",
                        line.name, line.renta_percentage, line.price_subtotal, line.renta_amount
                    )
                else:
                    line.renta_amount = 0.0
                    _logger.info(
                        "SIT | Línea %s: renta_percentage=0, renta_amount reiniciado a 0", line.name
                    )

