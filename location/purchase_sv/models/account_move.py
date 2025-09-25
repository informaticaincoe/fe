# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError

import logging
_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    document_number = fields.Char("Número de documento de proveedor")

    # Campo real: Many2one que se guarda en la BD
    sit_tipo_documento_id = fields.Many2one(
        'account.journal.tipo_documento.field',
        string='Tipo de Documento',
        # compute='_compute_tipo_doc',
        related='journal_id.sit_tipo_documento',
        store=True,
        default=lambda self: self.env['account.journal.tipo_documento.field'].search([], limit=1)
    )

    show_sit_tipo_documento = fields.Boolean(
        compute='_compute_show_sit_tipo_documento',
        # store=True
    )

    # Campo name editable
    name = fields.Char(
        string='Number',
        readonly=False,  # editable siempre
        copy=False,
        default='/',
        help="Editable siempre por el usuario"
    )

    _original_name = fields.Char(compute='_compute_original_name', store=False)

    @api.depends('move_type')
    def _compute_show_sit_tipo_documento(self):
        for move in self:
            move.show_sit_tipo_documento = move.move_type in ('in_invoice', 'in_refund')
            _logger.info(
                "Compute show_sit_tipo_documento: move id=%s, move_type=%s, show=%s",
                move.id, move.move_type, move.show_sit_tipo_documento
            )

    # @api.constrains('name')
    # def _check_name_sales(self):
    #     """
    #     Restricción: evitar la modificación manual del campo `name` en facturas de venta.
    #
    #     Contexto:
    #     ----------
    #     - En facturas de venta (`move_type == 'out_invoice'`), el campo `name`
    #       representa el número oficial del DTE (documento tributario electrónico).
    #     - Este número debe asignarse únicamente de manera automática por el sistema
    #       usando la lógica de `_generate_dte_name`.
    #     - Si el usuario intenta cambiarlo manualmente, debe bloquearse para garantizar
    #       la integridad y trazabilidad contable/fiscal.
    #
    #     Mecanismo:
    #     ----------
    #     - Usamos un flag en el contexto (`_dte_auto_generated=True`) al momento de
    #       llamar a `super().create(vals_list)`. Esto indica que el `name` fue generado
    #       automáticamente por el flujo DTE.
    #     - Si el constraint detecta que el contexto NO contiene ese flag, significa que
    #       alguien (usuario u otro flujo externo) intentó modificar el campo manualmente.
    #       → En este caso se lanza un UserError.
    #     """
    #     for move in self:
    #         if move.move_type != 'out_invoice':
    #             _logger.info("No es factura de venta, no se valida el name: move_id=%s", move.id)
    #             continue
    #
    #         # Detectar si el name fue generado automáticamente vía contexto
    #         auto_generated = self.env.context.get('_dte_auto_generated', False)
    #         _logger.info("move_id=%s, auto_generated=%s", move.id, auto_generated)
    #
    #         if not auto_generated:
    #             _logger.warning("Intento de modificar manualmente el número de la factura de venta: move_id=%s, name=%s", move.id, move.name)
    #             raise UserError(_("No está permitido modificar manualmente el número de la factura de venta."))
    #         else:
    #             _logger.info("Nombre generado automáticamente permitido: move_id=%s, name=%s", move.id, move.name)

    def write(self, vals):
        if 'name' in vals:
            for move in self:
                if move.move_type == 'out_invoice' or move.move_type == 'out_refund':
                    # if 'name' in vals and vals['name'].startswith('05 '):
                    #     _logger.warning(
                    #         "[WRITE-CLEAN] Limpiando prefijo '05 ' de move_id=%s, old_name=%s, vals_name=%s",
                    #         move.id, move.name, vals['name']
                    #     )
                    #     # Limpiar el prefijo temporal
                    #     vals['name'] = vals['name'][3:]
                    # else:
                    old_name = move.name or ''
                    new_name = vals.get('name') or ''

                    _logger.info(
                        "[WRITE-VALIDATION] move_id=%s, state=%s, old_name=%s, new_name=%s, auto_generated=%s",
                        move.id, move.state, old_name, new_name,
                        self.env.context.get('_dte_auto_generated', False)
                    )

                    # Si el valor no cambia, dejamos pasar
                    if old_name == new_name:
                        _logger.info(
                            "[WRITE-VALIDATION] El valor de 'name' no cambió (se mantiene %s). Permitido.",
                            old_name
                        )
                        continue

                    # Si no viene con el flag de generación automática → bloquear
                    if not self.env.context.get('_dte_auto_generated', False):
                        _logger.warning(
                            "[WRITE-VALIDATION] Intento de modificar manualmente el 'name' en factura de venta "
                            "(move_id=%s). Valor anterior: %s → Nuevo valor: %s",
                            move.id, old_name, new_name
                        )
                        raise UserError(
                            _("No está permitido modificar manualmente el número de la factura de venta, "
                              "ni en borrador ni validada.")
                        )

                    _logger.info(
                        "[WRITE-VALIDATION] Cambio de 'name' permitido por flag auto-generado. "
                        "Valor anterior: %s → Nuevo valor: %s",
                        old_name, new_name
                    )
        return super().write(vals)

    # def write(self, vals):
    #     for move in self:
    #         if 'name' in vals and vals['name'].startswith('05 '):
    #             _logger.warning(
    #                 "[WRITE-CLEAN] Limpiando prefijo '05 ' de move_id=%s, old_name=%s, vals_name=%s",
    #                 move.id, move.name, vals['name']
    #             )
    #             # Limpiar el prefijo temporal
    #             vals['name'] = vals['name'][3:]
    #
    #     return super().write(vals)
