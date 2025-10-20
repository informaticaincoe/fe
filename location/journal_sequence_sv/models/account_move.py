# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError, AccessError

import logging
_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo constants [journal_sequence account_move]")
except ImportError as e:
    _logger.error(f"Error al importar 'constants': {e}")
    constants = None

class AccountMove(models.Model):
    _inherit = "account.move"

    name = fields.Char(string='Number', required=True, readonly=False, copy=False, default='/')


    def _get_sequence(self):
        """Resuelve la secuencia a usar respetando el core si FE está OFF."""
        self.ensure_one()
        if (not self.env.company.sit_facturacion
                or (self.move_type in (constants.IN_INVOICE, constants.IN_REFUND)
                    and (not self.journal_id.sit_tipo_documento or self.journal_id.sit_tipo_documento.codigo != constants.COD_DTE_FSE))
        ):
            return super()._get_sequence()

        journal = self.journal_id
        # Si es normal o no hay refund_sequence -> principal
        if self.move_type in ('entry', 'out_invoice', 'in_invoice', 'out_receipt', 'in_receipt') or not journal.refund_sequence:
            return journal.sequence_id
        # Si es NC y existe refund_sequence -> refund
        if journal.refund_sequence_id:
            return journal.refund_sequence_id
        return journal.sequence_id  # fallback seguro


    @api.model
    def _get_standard_sequence(self):
        """Devuelve la secuencia estándar (no-DTE) para el diario."""
        self.ensure_one()
        if (not self.env.company.sit_facturacion
                or (self.move_type in (constants.IN_INVOICE, constants.IN_REFUND)
                    and (not self.journal_id.sit_tipo_documento or self.journal_id.sit_tipo_documento.codigo != constants.COD_DTE_FSE)) ):
            # respetar core; si no existe en tu versión, puedes retornar self.journal_id.sequence_id
            try:
                return super()._get_standard_sequence()
            except AttributeError:
                pass
        journal = self.journal_id
        if self.move_type in ('entry', 'out_invoice', 'in_invoice', 'out_receipt',
                              'in_receipt') or not journal.refund_sequence:
            return journal.sequence_id
        return journal.refund_sequence_id or journal.sequence_id


    def _post(self, soft=True):

        if (not self.env.company.sit_facturacion
                or (self.move_type in (constants.IN_INVOICE, constants.IN_REFUND)
                    and (
                            not self.journal_id.sit_tipo_documento or self.journal_id.sit_tipo_documento.codigo != constants.COD_DTE_FSE))):
            return super()._post(soft=soft)

        # 1) Solo asigno la secuencia estándar para diarios NO sale
        non_sales = self.filtered(lambda m: m.journal_id.type != 'sale')
        for move in non_sales:
            _logger.info("Revisando move %s con diario %s (%s)", move.id, move.journal_id.name, move.journal_id.type)

            if not (move.company_id and move.company_id.sit_facturacion) or not move.journal_id.sit_tipo_documento:
                _logger.warning("Move %s omitido: sin company_id.sit_facturacion y sin tipo de documento en el diario %s", move.id, move.journal_id.id)
                continue

            _logger.info("Move %s pasa validaciones, continúa con el flujo", move.id)
            if move.name == '/':
                journal = move.journal_id
                if not journal:
                    raise UserError(_('Debe seleccionar un Diario antes de confirmar el documento.'))
                sequence = move._get_standard_sequence()
                if not sequence:
                    raise UserError(
                        _('Por favor defina una secuencia para el Diario "%s".') %
                        journal.display_name
                    )
                # Asigno el siguiente número de la secuencia normal
                move.name = sequence.with_context(
                    ir_sequence_date=move.date
                ).next_by_id()

        # 2) Delego al super(), de modo que:
        #    - los diarios sale pasen a tu flujo DTE (con “DTE-…”)
        #    - todo lo demás continúe con la lógica de Odoo
        return super(AccountMove, self)._post(soft=soft)

    @api.onchange('journal_id')
    def onchange_journal_id(self):
        """Resetea nombre y deja que el core compute lo demás; si FE OFF, no toques nada extra."""
        _logger.info("SIT-ONCHANGE: Iniciando onchange_journal_id para move_id=%s, journal_id=%s", self.id, self.journal_id.id if self.journal_id else None)

        # Llama primero al core por si tiene lógica propia
        try:
            super(AccountMove, self).onchange_journal_id()
            _logger.info("SIT-ONCHANGE: super().onchange_journal_id ejecutado, name=%s", self.name)
        except AttributeError:
            _logger.warning("SIT-ONCHANGE: super().onchange_journal_id no existe en esta versión")

        if self.name != '/' and self.env.company.sit_facturacion and (
                self.move_type not in (constants.IN_INVOICE, constants.IN_REFUND) or
                (self.move_type == constants.IN_INVOICE and self.journal_id.sit_tipo_documento and self.journal_id.sit_tipo_documento.codigo == constants.COD_DTE_FSE)
        ):
            raise UserError(_(
                "No puede cambiar el diario porque este documento ya tiene un número asignado: %s."
            ) % self.name)

        # Si quieres forzar reset del nombre cuando FE ON:
        if self.env.company.sit_facturacion and self.name == '/' and (
                self.move_type not in (constants.IN_INVOICE, constants.IN_REFUND) or
                (self.move_type == constants.IN_INVOICE and self.journal_id.sit_tipo_documento and self.journal_id.sit_tipo_documento.codigo == constantsCOD_DTE_FSE)
        ):
            _logger.info("SIT-ONCHANGE: FE activado, reseteando name a '/' (antes name=%s)", self.name)
            # self.name = '/'
            try:
                nuevo_name = self.with_context(_dte_auto_generated=True,_dte_manual_update=True)._generate_dte_name(
                    journal=self.journal_id,
                    actualizar_secuencia=False  # solo preview
                )
                if nuevo_name:
                    _logger.info("SIT-ONCHANGE: previsualizando name=%s", nuevo_name)
                    self.name = nuevo_name  # ← Se muestra en pantalla
                # self._compute_name()
                _logger.info("SIT-ONCHANGE: _compute_name() ejecutado, name=%s", self.name)
            except Exception as e:
                _logger.error("SIT-ONCHANGE: Error ejecutando _compute_name(): %s", e)

    def _constrains_date_sequence(self):
        return

    def write(self, vals):
        # Si la empresa no tiene habilitada la facturación electrónica, se usa el comportamiento estándar
        if not all(inv.company_id.sit_facturacion for inv in self):
            _logger.info("SIT-journal_sequence_sv: Facturación no activa, se usa write estándar.")
            return super().write(vals)

        # Verificamos si son facturas de compra (in_invoice o in_refund). Si lo son, no ejecutamos la lógica personalizada.
        if all(inv.move_type in (constants.IN_INVOICE, constants.IN_REFUND)
               and (not inv.journal_id.sit_tipo_documento or inv.journal_id.sit_tipo_documento.codigo != constants.COD_DTE_FSE) for inv in self):
            _logger.info("SIT-journal_sequence_sv: Factura de compra detectada, se salta la lógica personalizada para 'name'.")

            # Verificamos si ya se ha procesado un reembolso antes de ejecutar cualquier lógica adicional
            if 'is_refund_processed' in vals and vals['is_refund_processed']:
                _logger.info("SIT-journal_sequence_sv: Reembolso ya procesado, evitando cambios adicionales.")
                return super().write(vals)

            return super().write(vals)

        _logger.info("SIT-Write(journal_sequence_sv): Asigna / en name si es false: %s", vals)

        # para evitar que pongan name = False
        if 'name' in vals and vals['name'] is False:
            _logger.info("SIT-Write(journal_sequence_sv): Name sin modificacion: %s", vals['name'])
            vals['name'] = '/'
            _logger.info("SIT-Write(journal_sequence_sv): Name modificado: %s", vals['name'])
        return super().write(vals)
