from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class AccountDebitNote(models.TransientModel):
    _inherit = 'account.debit.note'

    def create_debit(self):
        _logger.info("SIT: Entrando al método create_debit personalizado: %s", self)
        self.ensure_one()

        if not (self.company_id and self.company_id.sit_facturacion):
            _logger.info("SIT: La empresa %s no aplica a facturación electrónica. Saltando validaciones DTE/Hacienda para ND.", self.company_id.name)
            return  # Si no aplica, no continuar con la lógica de ND electrónica

        if not self.journal_id:
            raise UserError(_("Debe seleccionar un diario antes de continuar."))

        if self.journal_id.type == 'sale' and not self.journal_id.sit_tipo_documento:
            raise UserError(_("No se encontró el tipo de documento (06) Nota de Débito."))

        # Obtener el código del tipo de documento desde el diario
        doc_code = (
                getattr(self.journal_id.sit_tipo_documento, "codigo", False)
                or getattr(self.journal_id.sit_tipo_documento, "code", False)
        )
        if not doc_code:
            raise UserError(_("El diario no tiene código de tipo de documento configurado."))

        DocType = self.env["l10n_latam.document.type"]
        doc_type = DocType.search([
            ("code", "=", doc_code),
        ], limit=1)

        if not doc_type:
            # Intento sin filtro de país como fallback
            doc_type = DocType.search([("code", "=", doc_code)], limit=1)

        if not doc_type:
            _logger.error("SIT: No se encontró l10n_latam.document.type con code=%s", doc_code)
            raise UserError(_("No se encontró el Tipo de Documento (LATAM) con código: %s") % doc_code)

        _logger.info(
            "SIT: Resuelto l10n_latam_document_type_id -> id=%s, code=%s, name=%s",
            doc_type.id, doc_type.code, doc_type.display_name
        )
        ctx = dict(self.env.context or {})
        ctx.update({
            'default_journal_id': self.journal_id.id,
            'dte_name_preassigned': True,
        })

        moves = self.move_ids
        default_values_list = []

        for move in moves:
            _logger.info("SIT: Procesando factura original ID=%s | name=%s", move.id, move.name)
            _logger.info("SIT: doc_type =%s", doc_type)

            default_vals = {
                'journal_id': self.journal_id.id,
                'move_type': 'out_invoice',
                'partner_id': move.partner_id.id,
                'l10n_latam_document_type_id':doc_type.id,
                'debit_origin_id': move.id,
                'ref': move.name,
                'invoice_origin': move.name,
                'currency_id': move.currency_id.id,
                'invoice_date': fields.Date.context_today(self),

                # Copiar descuentos desde el crédito fiscal
                'descuento_gravado_pct': move.descuento_gravado_pct,
                'descuento_exento_pct': move.descuento_exento_pct,
                'descuento_no_sujeto_pct': move.descuento_no_sujeto_pct,
                'descuento_global_monto': move.descuento_global_monto,
            }

            invoice_lines_vals = []

            for line in move.invoice_line_ids:
                if line.display_type in [False, 'product'] and not line.custom_discount_line:
                    line_vals = {
                        'product_id': line.product_id.id,
                        'name': line.name,
                        'quantity': line.quantity,
                        'price_unit': line.price_unit,
                        'account_id': line.account_id.id,
                        'tax_ids': [(6, 0, line.tax_ids.ids)],
                        'discount': line.discount,
                    }
                    invoice_lines_vals.append((0, 0, line_vals))

                    _logger.warning("SIT: line_vals: %s", line_vals)

            # Simula el asiento temporalmente
            temp_move = self.env['account.move'].new({
                **default_vals,
                'invoice_line_ids': invoice_lines_vals
            })

            # Total real simulado desde líneas temporales
            total_debit = sum(line.debit for line in temp_move.line_ids)
            total_credit = sum(line.credit for line in temp_move.line_ids)
            diferencia = round(total_credit - total_debit, 2)

            _logger.warning("SIT: total_debit: %s", total_debit)
            _logger.warning("SIT: total_credit: %s", total_credit)
            _logger.warning("SIT: diferencia: %s", diferencia)
            if abs(diferencia) > 0.01:
                _logger.warning("SIT: Agregando contrapartida por diferencia: %s", diferencia)

                if not self.journal_id.default_account_id:
                    raise UserError(_("El diario seleccionado no tiene una cuenta predeterminada configurada."))

                if diferencia > 0:
                    # Hace falta agregar al DEBIT
                    invoice_lines_vals.append((0, 0, {
                        'name': 'Contrapartida automática',
                        'account_id': self.journal_id.default_account_id.id,
                        'quantity': 1,
                        'price_unit': diferencia,
                        'debit': diferencia,
                        'credit': 0.0,
                    }))
                else:
                    # Hace falta agregar al CREDIT
                    diferencia = abs(diferencia)
                    invoice_lines_vals.append((0, 0, {
                        'name': 'Contrapartida automática',
                        'account_id': self.journal_id.default_account_id.id,
                        'quantity': 1,
                        'price_unit': diferencia,
                        'debit': 0.0,
                        'credit': diferencia,
                    }))

            default_vals['invoice_line_ids'] = invoice_lines_vals

            # Generar nombre anticipado
            temp_move_final = self.env['account.move'].new(default_vals)
            temp_move_final.journal_id = self.journal_id
            nombre_generado = temp_move_final._generate_dte_name()
            if not nombre_generado:
                raise UserError(_("No se pudo generar un número de control para el documento."))

            default_vals['name'] = nombre_generado
            _logger.info("SIT: Nombre generado para ND: %s", nombre_generado)

            default_values_list.append(default_vals)

        try:
            new_moves = self.env['account.move'].with_context(ctx).create(default_values_list)
        except Exception as e:
            _logger.error("Error al crear account.move: %s", e)
            raise UserError(_("Ocurrió un error al crear la nota de débito: %s") % e)

        return {
            'name': _('Debit Notes'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form' if len(new_moves) == 1 else 'list,form',
            'res_id': new_moves.id if len(new_moves) == 1 else False,
            'domain': [('id', 'in', new_moves.ids)],
            'context': {
                'default_move_type': new_moves[0].move_type if new_moves else 'out_invoice',
            },
        }
