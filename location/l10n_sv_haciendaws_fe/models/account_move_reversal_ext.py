from odoo import fields, models, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import constants
    from odoo.addons.common_utils.utils import config_utils
    _logger.info("SIT Modulo config_utils [Reverse] Nota de credito")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    config_utils = None
    constants = None

class AccountMoveReversal(models.TransientModel):
    _inherit = "account.move.reversal"

    l10n_latam_document_type_id = fields.Many2one(
        'l10n_latam.document.type',
        string='Tipo de Documento',
        domain=[('code', '=', '05')],
    )

    inv_refund_id = fields.Many2one('account.move', string='Factura a Reversar')
    inv_debit_id = fields.Many2one('account.move', string='Factura a Debitar')

    def refund_moves_custom(self):
        self.ensure_one()
        _logger.info("SIT refund_moves_custom iniciado con move_ids=%s", self.move_ids)

        if not (self.company_id and self.company_id.sit_facturacion):
            _logger.info(
                "SIT: La empresa %s no aplica a facturación electrónica, saltando validaciones DTE/Hacienda para NC.",
                self.company_id.name)
            return

        if not self.journal_id:
            raise UserError(_("Debe seleccionar un diario antes de continuar."))

        if self.journal_id.type == 'sale' and not self.l10n_latam_document_type_id:
            raise UserError(_("Debe seleccionar un Tipo de Documento para la Nota de Crédito."))

        if self.journal_id.type == 'sale' and not self.l10n_latam_document_type_id:
            doc_type = self.env['l10n_latam.document.type'].search([('code', '=', constants.COD_DTE_NC)], limit=1)
            if not doc_type:
                raise UserError(_("No se encontró el tipo de documento (05) Nota de crédito."))
            self.l10n_latam_document_type_id = doc_type

        ctx = dict(self.env.context or {})
        ctx.update({
            'default_journal_id': self.journal_id.id,
            'default_l10n_latam_document_type_id': self.l10n_latam_document_type_id.id,
            'dte_name_preassigned': True,
        })
        _logger.info("SIT refund_moves_custom usando contexto: %s", ctx)

        moves = self.move_ids
        default_values_list = []
        default_vals = []

        for move in moves:
            default_vals = self._prepare_default_reversal(move)
            default_vals['journal_id'] = self.journal_id.id
            default_vals['move_type'] = 'out_refund'
            default_vals['partner_id'] = move.partner_id.id
            default_vals['l10n_latam_document_type_id'] = self.l10n_latam_document_type_id.id

            default_vals['inv_refund_id'] = move.id
            default_vals['reversed_entry_id'] = move.id

            _logger.info("SIT descuentos globales desc gravado=%s, desc exento=%s, desc no sujeto=%s, desc global=%s",
                         move.descuento_gravado_pct, move.descuento_exento_pct, move.descuento_no_sujeto_pct,
                         move.descuento_global_monto)
            # Copiar descuentos globales, si existen
            if hasattr(move, 'descuento_gravado_pct'):  # Si account.move tiene un campo descuento_gravado_pct
                default_vals['descuento_gravado_pct'] = move.descuento_gravado_pct

            if hasattr(move, 'descuento_exento_pct'):
                default_vals['descuento_exento_pct'] = move.descuento_exento_pct

            if hasattr(move, 'descuento_no_sujeto_pct'):
                default_vals['descuento_no_sujeto_pct'] = move.descuento_no_sujeto_pct

            if hasattr(move, 'descuento_global_monto'):
                default_vals['descuento_global_monto'] = move.descuento_global_monto

            _logger.info("SIT Preparing reversal for move_id=%s → reversed_entry_id=%s | inv_refund_id=%s",
                         move.id, default_vals['reversed_entry_id'], default_vals['inv_refund_id'])

            invoice_lines_vals = []
            _logger.info("SIT Invoice Lines: %s", move.invoice_line_ids)

            for line in move.invoice_line_ids:
                _logger.info("SIT display type: %s", line.display_type)
                if line.display_type not in [False, 'product'] or line.custom_discount_line:
                    continue

                invoice_lines_vals.append((0, 0, {
                    'product_id': line.product_id.id,
                    'name': line.name,
                    'quantity': line.quantity,
                    'price_unit': line.price_unit,
                    'account_id': line.account_id.id,
                    'tax_ids': [(6, 0, line.tax_ids.ids)],
                    'discount': line.discount,
                }))
                # 'analytic_account_id': line.analytic_account_id.id if line.analytic_account_id else False,
                # 'analytic_tag_ids': [(6, 0, line.analytic_tag_ids.ids)],
            default_vals['invoice_line_ids'] = invoice_lines_vals
            _logger.info("SIT listado de productos=%s", default_vals['invoice_line_ids'])

            prefix = (config_utils.get_config_value(self.env, 'dte_prefix', self.company_id.id) or "DTE-").lower()
            if not move.name or move.name == '/' or not move.name.startswith(prefix):
                move_temp = self.env['account.move'].new(default_vals)
                move_temp.journal_id = self.journal_id
                nombre_generado = move_temp._generate_dte_name()

                if not nombre_generado:
                    raise UserError(_("No se pudo generar un número de control para el documento."))

                default_vals['name'] = nombre_generado
                _logger.info("SIT Nombre generado para NC: %s", nombre_generado)
            else:
                _logger.info("SIT Usando nombre original: %s", move.name)

            default_values_list.append(default_vals)

        # Log antes de crear
        for i, val in enumerate(default_values_list):
            _logger.info("SIT Pre-creación NC #%s: reversed_entry_id=%s | inv_refund_id=%s | name=%s",
                         i, val.get('reversed_entry_id'), val.get('inv_refund_id'), val.get('name'))

        # Comprobar si ya existe un registro con el mismo nombre
        existing_move = self.env['account.move'].search([('name', '=', default_vals['name'])], limit=1)

        if existing_move:
            _logger.info("SIT: Ya existe un movimiento con el nombre %s. Usando el registro existente.",
                         default_vals['name'])
            return {
                'name': _('Reverse Moves'),
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'view_mode': 'form' if len(existing_move) == 1 else 'list,form',
                'res_id': existing_move.id if len(existing_move) == 1 else False,
                'domain': [('id', 'in', existing_move.ids)],
                'context': {
                    'default_move_type': existing_move.move_type if existing_move else 'out_refund',
                },
            }

        # Si no existe un movimiento, creamos los nuevos registros
        new_moves = self.env['account.move'].with_context(ctx).create(default_values_list)
        _logger.info("SIT nuevo account.move creado: %s ", new_moves)

        # Si no se crearon movimientos, lanzamos un error (esto es más como precaución)
        if not new_moves:
            raise UserError(_("No se han creado movimientos de reversión."))

        # El código para crear 'new_move' podría ser redundante si ya se están creando varios registros en 'new_moves'.
        # Solo asegúrate de que no estés creando un movimiento innecesario aquí.
        # if new_moves and isinstance(new_moves, list) and all(
        #         isinstance(move, self.env['account.move'].__class__) for move in new_moves):
        #     for move in new_moves:
        #         if move.codigo_tipo_documento == constants.COD_DTE_NC and move.reversed_entry_id:
        #             _logger.info("SIT NC creada: ID=%s | reversed_entry_id=%s | inv_refund_id=%s | name=%s",
        #                          move.id, move.reversed_entry_id.id, move.inv_refund_id.id, move.name)
        #             move._copiar_retenciones_desde_documento_relacionado()
        #
        #     # Devolvemos la respuesta correcta en función de si hay un solo movimiento o varios
        #     return {
        #         'name': _('Reverse Moves'),
        #         'type': 'ir.actions.act_window',
        #         'res_model': 'account.move',
        #         'view_mode': 'form' if len(new_moves) == 1 else 'list,form',
        #         'res_id': new_moves[0].id if len(new_moves) == 1 else False,
        #         # Accede a 'id' solo si hay un solo movimiento
        #         'domain': [('id', 'in', [move.id for move in new_moves])],  # Genera una lista de IDs
        #         'context': {
        #             'default_move_type': new_moves[0].move_type if new_moves else 'out_refund',
        #         },
        #     }
        # else:
        #     raise UserError(_("No se han creado movimientos de reversión válidos o hay un error en los datos."))

        # new_moves es un recordset (no lista)
        if new_moves:
            for move in new_moves:
                # Por si inv_refund_id es False, evita AttributeError en el log
                inv_refund = move.inv_refund_id.id if move.inv_refund_id else False
                rev_id = move.reversed_entry_id.id if move.reversed_entry_id else False

                if move.codigo_tipo_documento == constants.COD_DTE_NC and (move.reversed_entry_id or move.inv_refund_id):
                    _logger.info(
                        "SIT NC creada: ID=%s | reversed_entry_id=%s | inv_refund_id=%s | name=%s",
                        move.id, rev_id, inv_refund, move.name
                    )
                    move._copiar_retenciones_desde_documento_relacionado()

            # Arma la acción con ids del recordset
            return {
                'name': _('Reverse Moves'),
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'view_mode': 'form' if len(new_moves) == 1 else 'tree,form',
                'res_id': new_moves.id if len(new_moves) == 1 else False,
                'domain': [('id', 'in', new_moves.ids)],
                'context': {
                    'default_move_type': new_moves.move_type if len(new_moves) == 1 else 'out_refund',
                },
            }
        else:
            raise UserError(_("No se han creado movimientos de reversión válidos o hay un error en los datos."))

    import logging
    _logger = logging.getLogger(__name__)

    def refund_or_debit_custom(self):
        self.ensure_one()
        _logger.info("SIT refund_or_debit_custom iniciado para account.move.reversal con ID=%s", self.id)

        if not (self.company_id and self.company_id.sit_facturacion):
            _logger.info("SIT: La empresa %s no aplica a facturación electrónica, saltando lógica personalizada de refund/debit.", self.company_id.name)
            return super().refund_or_debit()

        doc_type = self.l10n_latam_document_type_id.code
        _logger.info("SIT Tipo de documento detectado: %s", doc_type)

        if doc_type == constants.COD_DTE_NC:
            _logger.info("SIT Ejecutando refund_moves() para Nota de Crédito")
            result = self.refund_moves_custom()
            _logger.info("SIT refund_moves() ejecutado con éxito")
            return result

        elif doc_type == constants.COD_DTE_ND:
            _logger.info("SIT Ejecutando creación de Nota de Débito con wizard")
            _logger.info("SIT move_ids para el wizard: %s", self.move_ids.ids)
            _logger.info("SIT journal_id: %s", self.journal_id.id)
            debit_wizard = self.env['account.debit.note'].create({
                'move_ids': [(6, 0, self.move_ids.ids)],
                'journal_id': self.journal_id.id,
            })
            _logger.info("SIT Wizard creado con ID: %s", debit_wizard.id)
            result = debit_wizard.create_debit()
            _logger.info("SIT create_debit() ejecutado con éxito")
            return result

        else:
            _logger.error("SIT Tipo de documento no soportado para reverso: %s", doc_type)
            raise UserError(_("Tipo de documento no soportado para reverso: %s") % doc_type)

