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
        journal = self.journal_id
        # Si es normal o no hay refund_sequence -> principal
        if self.move_type in (constants.TYPE_ENTRY, constants.OUT_RECEIPT, constants.IN_RECEIPT) or not journal.refund_sequence:
            return journal.sequence_id

        if (self.move_type in (constants.IN_INVOICE, constants.IN_REFUND) and
             (not self.journal_id.sit_tipo_documento or self.journal_id.sit_tipo_documento.codigo != constants.COD_DTE_FSE) ):
            return super()._get_sequence()
        if not self.env.company.sit_facturacion:
            return super()._get_sequence()

        # Si es NC y existe refund_sequence -> refund
        if journal.refund_sequence_id:
            return journal.refund_sequence_id
        return journal.sequence_id  # fallback seguro

    @api.model
    def _get_standard_sequence(self):
        """Devuelve la secuencia estándar (no-DTE) para el diario."""
        self.ensure_one()
        if (self.move_type in (constants.IN_INVOICE, constants.IN_REFUND) and self.journal_id and
                (not self.journal_id.sit_tipo_documento or self.journal_id.sit_tipo_documento.codigo != constants.COD_DTE_FSE) ):
            # respetar core; si no existe en tu versión, puedes retornar self.journal_id.sequence_id
            try:
                return super()._get_standard_sequence()
            except AttributeError:
                pass

        journal = self.journal_id
        if self.move_type in (constants.TYPE_ENTRY, constants.OUT_RECEIPT, constants.IN_RECEIPT) or not journal.refund_sequence:
            return journal.sequence_id
        if (not self.env.company.sit_facturacion):
            # respetar core; si no existe en tu versión, puedes retornar self.journal_id.sequence_id
            try:
                return super()._get_standard_sequence()
            except AttributeError:
                pass

        return journal.refund_sequence_id or journal.sequence_id

    def _post(self, soft=True):
        # Siempre permitir que Odoo postee primero (puede ser masivo)
        result = super(AccountMove, self)._post(soft=soft)

        # Si la empresa no usa facturación electrónica, no hago nada
        if not self.env.company.sit_facturacion:
            return result

        # Procesar SIEMPRE por movimiento
        for move in self:
            # Movimientos que no deben tocarse
            if move.move_type in (constants.TYPE_ENTRY, constants.OUT_RECEIPT, constants.IN_RECEIPT):
                continue
            if (move.move_type in (constants.IN_INVOICE, constants.IN_REFUND) and move.journal_id
                    and (not move.journal_id.sit_tipo_documento or move.journal_id.sit_tipo_documento.codigo != constants.COD_DTE_FSE)):
                continue

            # Los diarios de venta siguen su propio flujo
            if move.journal_id.type == constants.TYPE_VENTA:
                continue

            # Validaciones mínimas
            if not move.journal_id or not move.journal_id.sit_tipo_documento:
                continue

            # Asignar secuencia estándar solo si aún no tiene número
            if move.name == '/':
                sequence = move._get_standard_sequence()
                if not sequence:
                    raise UserError(
                        _('Por favor defina una secuencia para el Diario "%s".')
                        % move.journal_id.display_name
                    )

                move.name = sequence.with_context(
                    ir_sequence_date=move.date
                ).next_by_id()

        # 2) Delego al super(), de modo que:
        #    - los diarios sale pasen a tu flujo DTE (con “DTE-…”)
        #    - todo lo demás continúe con la lógica de Odoo
        return result

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
                (self.move_type == constants.IN_INVOICE and self.journal_id.sit_tipo_documento and self.journal_id.sit_tipo_documento.codigo == constants.COD_DTE_FSE)
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
