# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from datetime import datetime
from odoo.tools import float_round
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError

from odoo.addons.common_utils.utils import constants

import logging

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import constants

    _logger.info("SIT Modulo constants [purchase-account_move]")
except ImportError as e:
    _logger.error(f"Error al importar 'constants': {e}")
    constants = None


class AccountMove(models.Model):
    _inherit = 'account.move'

    exp_duca_id = fields.One2many('exp_duca', 'move_id', string='DUCAs')

    document_number = fields.Char("Número de documento de proveedor")

    # Campo real: Many2one que se guarda en la BD
    sit_tipo_documento_id = fields.Many2one(
        'account.journal.tipo_documento.field',
        string='Tipo de Documento',
        # related='journal_id.sit_tipo_documento',
        store=True,
        default=lambda self: self._get_default_tipo_documento(),
    )

    codigo_tipo_documento_id = fields.Char(
        string="Código tipo documento",
        related='sit_tipo_documento_id.codigo',
        store=False,  # pon True si quieres poder buscar/filtrar por este campo
        readonly=True,
    )

    # fecha_aplicacion = fields.Date(string="Fecha de Aplicación")
    #
    # fecha_iva = fields.Date(string="Fecha IVA")

    is_dte_doc = fields.Boolean(
        string="Es documento DTE",
        compute="_compute_is_dte_doc",
        store=False,  # explícito para dejar claro que NO se guarda
    )

    sit_condicion_plazo = fields.Selection(
        [
            ('desde_fecha_doc', "Plazo Crédito desde Fecha Documento"),
            ('no_genera_cxp', "No genera Cuenta por Pagar"),
            ('no_genera_asiento', "No genera Partida Contable"),
            ('ya_provisionada', "Ya provisionada en Contabilidad"),
            ('contabilizar_indep', "Contabilizar en Partida independiente"),
        ],
        string="Condición del Plazo Crédito",
        help="Selecciona la opción que aplica para este documento",
    )

    # Campo name editable
    name = fields.Char(
        string='Number',
        readonly=False,  # editable siempre
        copy=False,
        default='/',
        help="Editable siempre por el usuario",
        # compute="_compute_unique_name"
    )


    # Verificar que el name (o numero de control) sea unico
    @api.constrains('name', 'company_id')
    def _check_unique_name(self):
        for move in self:
            name = (move.name or '').strip()
            # Permitir '/' y vacío (borradores) y saltar si no hay nombre
            if not name or name == '/':
                continue

            # Busca duplicado en la misma compañía, excluyendo el propio registro
            dup = self.search([
                ('id', '!=', move.id),
                ('company_id', '=', move.company_id.id),
                ('name', '=', name),
            ], limit=1)

            if dup:
                # Mensaje claro al usuario
                raise ValidationError(_(
                    "El número de documento '%(name)s' ya existe",
                ) % {
                      'name': name,
                      'doc': dup.display_name or dup.name,
                })

    # Verificar que el sello sea unico
    @api.constrains('hacienda_selloRecibido', 'company_id', 'move_type')
    def _check_unique_sello(self):
        for move in self:
            # Solo aplica a compras
            if move.move_type not in ('in_invoice', 'in_refund'):
                continue

            sello = self._norm_sello(move.hacienda_selloRecibido)
            if not sello:
                continue

            dup = self.search([
                ('id', '!=', move.id),
                ('company_id', '=', move.company_id.id),
                ('move_type', 'in', ['in_invoice', 'in_refund']),
                ('hacienda_selloRecibido', '=', sello),
            ], limit=1)

            if dup:
                raise ValidationError(_("El Sello de recepción '%(sello)s' ya existe en el documento %(doc)s.") % {
                    'sello': sello,
                    'doc': dup.name or dup.display_name,
                })

    # Verificar que el sello sea unico
    @api.constrains('hacienda_codigoGeneracion_identificacion', 'company_id', 'move_type')
    def _check_unique_cod_generacion(self):
        for move in self:
            if move.move_type not in ('in_invoice', 'in_refund'):
                continue

            codigo_generacion = self._norm_sello(move.hacienda_codigoGeneracion_identificacion)
            if not codigo_generacion:
                continue

            dup = self.search([
                ('id', '!=', move.id),
                ('company_id', '=', move.company_id.id),
                ('move_type', 'in', ['in_invoice', 'in_refund']),
                ('hacienda_codigoGeneracion_identificacion', '=', codigo_generacion),
            ], limit=1)

            if dup:
                raise ValidationError(_("El codigo de generacion '%(codigo_generacion)s' ya existe en el documento %(doc)s.") % {
                    'codigo_generacion': codigo_generacion,
                    'doc': dup.name or dup.display_name,
                })

    _original_name = fields.Char(compute='_compute_original_name', store=False)

    @staticmethod
    def _norm_sello(v):
        v = (v or '')
        return v.replace('-', '').replace(' ', '').upper().strip()


    sit_amount_tax_system = fields.Monetary(
        string="SIT Amount Tax System",
        compute="_compute_sit_amount_tax_system",
        store=True,
    )

    invoice_line_ids_view_id = fields.Many2one(
        'ir.ui.view',
        string="Vista de líneas",
        compute='_compute_invoice_line_view',
        store=False
    )

    percepcion_amount = fields.Monetary(
        string="Percepción",
        currency_field='currency_id',
        readonly=True,
        store=True,
        default=0.0)

    def _get_default_tipo_documento(self):
        """Busca en 'account.journal.tipo_documento.field' el registro con código '01'
        y lo usa como valor por defecto.
        """
        # Lógica para obtener el valor predeterminado según el contexto o condiciones
        return self.env['account.journal.tipo_documento.field'].search([('codigo', '=', '01')], limit=1)

    @api.depends('clase_documento_id', 'move_type', 'journal_id', 'journal_id.sit_tipo_documento', 'journal_id.sit_tipo_documento.codigo')
    def _compute_is_dte_doc(self):
        """
        Calcula si el movimiento es un documento DTE.
        Aplica solo a facturas de proveedor IN_INVOICE o IN_REFUND que no sean FSE.
        """
        for rec in self:
            valor = False  # valor por defecto
            if (rec.move_type in (constants.IN_INVOICE, constants.IN_REFUND) and rec.journal_id
                    and (
                            not rec.journal_id.sit_tipo_documento or rec.journal_id.sit_tipo_documento.codigo != constants.COD_DTE_FSE)):
                codigo = rec.clase_documento_id.codigo if rec.clase_documento_id else None
                valor = bool(codigo == constants.DTE_COD)

            _logger.info(
                "SIT | _compute_is_dte_doc | move_id=%s | clase_documento_id=%s | codigo=%s | is_dte_doc=%s",
                rec.id,
                rec.clase_documento_id.id if rec.clase_documento_id else None,
                rec.clase_documento_id.codigo if rec.clase_documento_id else None,
                valor
            )
            rec.is_dte_doc = valor

    @api.onchange('name', 'hacienda_codigoGeneracion_identificacion', 'hacienda_selloRecibido')
    def _onchange_remove_hyphen_and_spaces(self):
        """
        Limpia guiones y espacios de campos relevantes al cambiar alguno de ellos.
        - Se aplica solo a facturas de proveedor (IN_INVOICE, IN_REFUND) que no sean FSE.
        - Campos afectados: 'name', 'hacienda_codigoGeneracion_identificacion', 'hacienda_selloRecibido'.
        """
        if (self.move_type not in(constants.IN_INVOICE, constants.IN_REFUND) or
                (self.move_type == constants.IN_INVOICE and self.journal_id.sit_tipo_documento and self.journal_id.sit_tipo_documento.codigo == constants.COD_DTE_FSE)):
            return

        # name
        if self.name:
            old_name = self.name
            self.name = self.name.replace('-', '').replace(' ', '')
            if old_name != self.name:
                _logger.info("[ONCHANGE] move_id=%s: 'name' changed from '%s' to '%s'", self.id, old_name, self.name)

        # hacienda_codigoGeneracion_identificacion
        if self.hacienda_codigoGeneracion_identificacion:
            old_val = self.hacienda_codigoGeneracion_identificacion
            self.hacienda_codigoGeneracion_identificacion = old_val.replace('-', '').replace(' ', '')
            if old_val != self.hacienda_codigoGeneracion_identificacion:
                _logger.info("[ONCHANGE] move_id=%s: 'hacienda_codigoGeneracion_identificacion' changed from '%s' to '%s'",
                             self.id, old_val, self.hacienda_codigoGeneracion_identificacion)

        # hacienda_selloRecibido
        if self.hacienda_selloRecibido:
            old_val = self.hacienda_selloRecibido
            self.hacienda_selloRecibido = old_val.replace('-', '').replace(' ', '')
            if old_val != self.hacienda_selloRecibido:
                _logger.info("[ONCHANGE] move_id=%s: 'hacienda_selloRecibido' changed from '%s' to '%s'",
                             self.id, old_val, self.hacienda_selloRecibido)

    @api.depends('invoice_line_ids.price_unit', 'invoice_line_ids.quantity', 'invoice_line_ids.discount', 'invoice_line_ids.tax_ids', 'currency_id', 'move_type', 'partner_id',)
    def _compute_sit_amount_tax_system(self):
        """
        Calcula el total de impuestos de la factura según las líneas y el sistema de impuestos.

        - Aplica solo a facturas de proveedor (IN_INVOICE, IN_REFUND) que no sean FSE.
        - Calcula impuestos por línea considerando precio unitario, cantidad, descuento y taxes.
        - Ajusta el total para notas de crédito (negativo).
        - Guarda el resultado en 'sit_amount_tax_system'.
        """
        for move in self:
            if (move.move_type in (constants.IN_INVOICE, constants.IN_REFUND) and move.journal_id and
                    (not move.journal_id.sit_tipo_documento or move.journal_id.sit_tipo_documento.codigo != constants.COD_DTE_FSE)):
                total_tax = 0.0
                _logger.info("SIT | Calculando impuestos para move: %s", move.name)

                for line in move.invoice_line_ids:
                    if not line.tax_ids:
                        _logger.info("SIT | Línea %s sin impuestos", line.name)
                        continue

                    price_after_discount = line.price_unit * (1 - (line.discount or 0.0) / 100)
                    _logger.info("SIT | Línea %s precio unitario: %s, cantidad: %s, precio tras descuento: %s",
                                 line.name, line.price_unit, line.quantity, price_after_discount)

                    tax_res = line.tax_ids.compute_all(
                        price_after_discount,
                        quantity=line.quantity,
                        product=line.product_id,
                        partner=move.partner_id,
                    )

                    total_tax_line = tax_res['total_included'] - tax_res['total_excluded']
                    _logger.info("SIT | Línea %s total_tax calculado: %s", line.name, total_tax_line)
                    total_tax += total_tax_line

                if move.move_type in (constants.IN_REFUND):
                    total_tax *= -1
                    _logger.info("SIT | Ajuste por nota de crédito: total_tax=%s", total_tax)

                move.sit_amount_tax_system = move.currency_id.round(total_tax)
                _logger.info("SIT | move %s sit_amount_tax_system final: %s", move.name, move.sit_amount_tax_system)

    # def _compute_totales_retencion_percepcion(self):
    #     """Suma automática de percepción, retención IVA y renta desde las líneas."""
    #     for move in self:
    #         if (move.move_type in (constants.IN_INVOICE, constants.IN_REFUND) and move.journal_id and
    #                 (not move.journal_id.sit_tipo_documento or move.journal_id.sit_tipo_documento.codigo != constants.COD_DTE_FSE)):
    #             percepcion_total = sum(move.line_ids.mapped('percepcion_amount'))
    #             retencion_iva_total = sum(move.line_ids.mapped('retencion_amount'))
    #             retencion_renta_total = sum(move.line_ids.mapped('renta_amount'))
    #
    #             # Asigna los totales a los campos existentes
    #             # Evitar recursión al escribir valores
    #             if not self.env.context.get('skip_compute'):
    #                 move.with_context(skip_compute=True).write({
    #                     'percepcion_amount': percepcion_total,
    #                     'retencion_iva_amount': retencion_iva_total,
    #                     'retencion_renta_amount': retencion_renta_total,
    #                 })
    #             else:
    #                 # Solo asignar en memoria si el flag está activo
    #                 move.percepcion_amount = percepcion_total
    #                 move.retencion_iva_amount = retencion_iva_total
    #                 move.retencion_renta_amount = retencion_renta_total
    #
    #             _logger.info("SIT | Totales move_id=%s => Percepción=%.2f | Retención IVA=%.2f | Retención Renta=%.2f",
    #                          move.id, percepcion_total, retencion_iva_total, retencion_renta_total)

    # def _update_totales_move(self):
    #     """
    #     Actualiza los totales de retención y percepción desde las líneas.
    #     No se usa @api.depends para evitar conflictos con otros computes existentes.
    #     """
    #     for move in self:
    #         if (move.move_type in (constants.IN_INVOICE, constants.IN_REFUND) and move.journal_id and
    #                 (not move.journal_id.sit_tipo_documento or move.journal_id.sit_tipo_documento.codigo != constants.COD_DTE_FSE)):
    #             total_percepcion = sum(move.line_ids.mapped('percepcion_amount'))
    #             total_ret_iva = sum(move.line_ids.mapped('retencion_amount'))
    #             total_ret_renta = sum(move.line_ids.mapped('renta_amount'))
    #
    #             move.percepcion_amount = total_percepcion
    #             move.retencion_iva_amount = total_ret_iva
    #             move.retencion_renta_amount = total_ret_renta
    #
    #             _logger.info(
    #                 "SIT | Totales actualizados move_id=%s => Percepción=%.2f | Ret. IVA=%.2f | Ret. Renta=%.2f",
    #                 move.id, total_percepcion, total_ret_iva, total_ret_renta
    #             )

    def action_post(self):
        """
        - Aplica solo a facturas de proveedor (IN_INVOICE, IN_REFUND) que no sean FSE.
        - Valida campos obligatorios: tipo de documento, clase de documento, sello y código de generación.
        - Evita duplicados en 'hacienda_codigoGeneracion_identificacion'.
        - Genera líneas de percepción, retención y renta antes de postear.
        - Luego llama al método estándar 'action_post' de Odoo.
        """
        _logger.info("SIT Action post purchase: %s", self)
        # Si FE está desactivada → comportamiento estándar de Odoo
        invoices = self.filtered(lambda inv: inv.move_type in (constants.OUT_INVOICE, constants.OUT_REFUND, constants.IN_INVOICE, constants.IN_REFUND))
        if not invoices:
            # Si no hay facturas, llamar al método original sin hacer validaciones DTE
            return super().action_post()

        # Obtener el registro de Pago Inmediato
        IMMEDIATE_PAYMENT = self.env.ref('account.account_payment_term_immediate').id

        for move in self:
            _logger.info("SIT-Compra move type: %s, tipo documento %s: ", move.move_type, move.codigo_tipo_documento)
            if move.move_type not in (constants.IN_INVOICE, constants.IN_REFUND):
                _logger.info("SIT Action post no aplica a modulos distintos a compra.")
                continue
            if move.move_type == constants.IN_INVOICE and move.journal_id and move.journal_id.sit_tipo_documento and move.journal_id.sit_tipo_documento.codigo == constants.COD_DTE_FSE:
                _logger.info("SIT Action post no aplica para compras electronicas(como suejto excluido).")
                continue

            if move.move_type == constants.IN_INVOICE and move.journal_id.sit_tipo_documento and move.hacienda_codigoGeneracion_identificacion:
                existing = self.search([
                    ('id', '!=', move.id),
                    ('hacienda_codigoGeneracion_identificacion', '=', move.hacienda_codigoGeneracion_identificacion)
                ], limit=1)
                if existing:
                    raise ValidationError(_(
                        "El Número de Resolución '%s' ya existe en otro documento (%s)."
                    ) % (move.hacienda_codigoGeneracion_identificacion, existing.name))

            # if not move.fecha_aplicacion:
            #     _logger.info("SIT | Fecha de aplicacion no seleccionada.")
            #     raise ValidationError("Debe seleccionar la Fecha de Aplicación.")

            # if not move.fecha_iva:
            #     _logger.info("SIT | Fecha IVA no seleccionada.")
            #     raise ValidationError("Debe seleccionar la Fecha de IVA.")

            # fecha_iva = move.fecha_iva
            # date_invoice = move.invoice_date

            # _logger.info("SIT | Fecha factura: %s, Fecha IVA: %s.", date_invoice, fecha_iva)
            # if fecha_iva and date_invoice:
            #     # Ambas son fechas, se comparan directamente
            #     if fecha_iva < date_invoice:
            #         _logger.info(
            #             "SIT | Fecha IVA (%s) no debe ser menor a la fecha de la factura (%s).",
            #             fecha_iva,
            #             date_invoice
            #         )
            #         raise ValidationError(
            #             "Fecha IVA (%s) no debe ser menor a la fecha de la factura (%s)." % (
            #                 fecha_iva,
            #                 date_invoice
            #             )
            #         )

            if not move.sit_tipo_documento_id:
                _logger.info("SIT | Tipo de documento no seleccionado.")
                raise ValidationError("Debe seleccionar el Tipo de documento de compra.")

            if not move.clase_documento_id:
                _logger.info("SIT | Clase de documento no seleccionada.")
                raise ValidationError("Debe seleccionar la Clase de documento.")

            if not move.hacienda_selloRecibido:
                _logger.info("SIT | Sello Recepcion no agregado.")
                raise ValidationError("Debe agregar el Sello de recepción.")

            if not move.hacienda_codigoGeneracion_identificacion:
                _logger.info("SIT | Codigo de generacion no agregado.")
                raise ValidationError("Debe agregar el Codigo de generación.")

            if not move.sit_obervaciones:
                _logger.info("SIT | Descripcion no agregada.")
                raise ValidationError("Se requiere una descripción.")

            # Validación de Condición/Plazo solo para ventas
            payment_term_id = move.invoice_payment_term_id.id if move.invoice_payment_term_id else None
            _logger.info("Termino de pago seleccionado: %s", move.invoice_payment_term_id.name if move.invoice_payment_term_id else None)

            # if payment_term_id and payment_term_id != IMMEDIATE_PAYMENT and not move.sit_condicion_plazo:
            #     _logger.info("Debe seleccionar el campo 'Condición del Plazo Crédito' si el término de pago no es 'Pago inmediato'.")
            #     raise ValidationError(_("Debe seleccionar el campo 'Condición del Plazo Crédito' si el término de pago no es 'Pago inmediato'."))

            # Generar las líneas de percepción/retención/renta antes de postear
            move.generar_asientos_retencion_compras()

        # Finalmente llamar al método estándar de Odoo
        return super(AccountMove, self).action_post()

    def _post(self, soft=True):
        """Extiende el método de posteo de facturas de compra para manejo de anulaciones DTE.

        - Aplica solo a facturas de proveedor (IN_INVOICE, IN_REFUND) que no sean FSE.
        - Si la factura está marcada como 'sit_invalidar', crea la invalidación correspondiente si aún no existe.
        - Registra logs de auditoría durante todo el proceso.
        - Devuelve el resultado original para mantener el flujo estándar de Odoo.
        """
        _logger.info("SIT Purchase.")

        result = super(AccountMove, self)._post(soft=soft)

        for move in self:
            if move.move_type not in (constants.IN_INVOICE, constants.IN_REFUND):
                _logger.info("SIT Post no aplica a modulos distintos a compra.")
                continue

            if (move.move_type == constants.IN_INVOICE and move.journal_id
                    and move.journal_id.sit_tipo_documento and move.journal_id.sit_tipo_documento.codigo == constants.COD_DTE_FSE):
                _logger.info("SIT Post no aplica para compras electronicas(como suejto excluido).")
                continue

            _logger.info("SIT-Purchase Move id: %s", move.id)

            _logger.info("SIT-Purchase Compra anulada: %s", move.sit_invalidar)
            AccountInvalidacion = self.env['account.move.invalidation']
            if move.sit_invalidar:
                invalidacion = AccountInvalidacion.search([
                    ('sit_factura_a_reemplazar', '=', move.id)
                ])
                _logger.info("SIT-Purchase Invaldiacion: %s", invalidacion)

                if invalidacion:
                    _logger.info("SIT-Purchase Invaldiacion existe: %s", invalidacion)
                    continue  # Ya existe la invalidación, no hacer nada más, pero seguir con el resto del flujo
                else:
                    _logger.info("SIT-Purchase Invaldiacion no existe, creando anulacion: %s", invalidacion)
                    move.sit_factura_a_reemplazar = move.id
                    move.action_button_anulacion()

        # Devuelve el resultado original para que Odoo siga funcionando
        return result

    exp_duca_id = fields.One2many('exp_duca', 'move_id', string='DUCAs')
    def generar_asientos_retencion_compras(self):
        """
        Genera automáticamente las líneas contables de **percepción**, **retención** y **renta**
        para facturas de compra (`in_invoice`) y notas de crédito de compra (`in_refund`), acumulando
        los valores de cada línea (`account.move.line`) y creando líneas contables en el asiento.

        Solo se aplica si el asiento está en borrador.
        No reemplaza otras líneas del asiento que no sean de percepción/retención/renta.
        Las cuentas deben estar configuradas en la compañía:
        - `iva_percibido_account_id`
        - `retencion_iva_account_id`
        - `retencion_renta_account_id`
        """
        for move in self:
            _logger.info(f"SIT | [Move {move.id}] Inicio de generación de asientos ret./perc./renta")

            if (move.move_type not in (constants.IN_INVOICE, constants.IN_REFUND) or
                    (move.move_type == constants.IN_INVOICE and move.journal_id and move.journal_id.sit_tipo_documento and move.journal_id.sit_tipo_documento.codigo == constants.COD_DTE_FSE)):
                _logger.info(f"SIT | [Move {move.id}] No aplica: solo compras o notas de crédito de compra.")
                continue

            if move.state != 'draft':
                _logger.warning(
                    f"SIT | [Move {move.id}] No se puede modificar, no está en borrador (estado={move.state}).")
                continue

            company = move.company_id
            currency = move.currency_id
            precision = currency.rounding or 0.01

            # --- Detalle de líneas
            _logger.info(f"SIT | [Move {move.id}] Revisando {len(move.invoice_line_ids)} líneas de factura")
            for line in move.invoice_line_ids:
                _logger.info(
                    f"SIT | [Move {move.id}] Línea {line.id}: subtotal={line.price_subtotal}, "
                    f"apply_percepcion={line.apply_percepcion}, percepcion_amount={line.percepcion_amount}, "
                    f"apply_retencion={line.apply_retencion}, retencion_amount={line.retencion_amount}, "
                    f"renta_percentage={line.renta_percentage}"
                )

            # Acumular montos
            total_percepcion = sum(line.percepcion_amount for line in move.invoice_line_ids)
            total_retencion = sum(line.retencion_amount for line in move.invoice_line_ids)
            total_renta = sum(line.renta_amount for line in move.invoice_line_ids)

            _logger.info(
                f"SIT | [Move {move.id}] Totales calculados -> Percepción: {total_percepcion}, "
                f"Retención IVA: {total_retencion}, Renta: {total_renta}"
            )

            # Eliminar líneas previas de este tipo
            previas = move.line_ids.filtered(lambda l: l.name in ["Percepción", "Retención IVA", "Renta"])
            if previas:
                _logger.info(
                    f"SIT | [Move {move.id}] Eliminando {len(previas)} líneas previas de retención/percepción/renta")
                previas.unlink()

            lineas = []

            def redondear(monto):
                return float_round(monto or 0.0, precision_rounding=precision)

            # --- Percepción
            if total_percepcion > 0 and company.iva_percibido_account_id:
                lineas.append({
                    'name': 'Percepción',
                    'account_id': company.iva_percibido_account_id.id,
                    'debit': redondear(total_percepcion),
                    'credit': 0.0,
                    'move_id': move.id,
                })
                _logger.info(f"SIT | [Move {move.id}] Línea de Percepción lista: {redondear(total_percepcion)}")

            # --- Retención IVA
            if total_retencion > 0 and company.retencion_iva_account_id:
                lineas.append({
                    'name': 'Retención IVA',
                    'account_id': company.retencion_iva_account_id.id,
                    'debit': 0.0,
                    'credit': redondear(total_retencion),
                    'move_id': move.id,
                })
                _logger.info(f"SIT | [Move {move.id}] Línea de Retención IVA lista: {redondear(total_retencion)}")

            # --- Renta
            if total_renta > 0 and company.retencion_renta_account_id:
                lineas.append({
                    'name': 'Renta',
                    'account_id': company.retencion_renta_account_id.id,
                    'debit': 0.0,
                    'credit': redondear(total_renta),
                    'move_id': move.id,
                })
                _logger.info(f"SIT | [Move {move.id}] Línea de Renta lista: {redondear(total_renta)}")

            if lineas:
                move.write({'line_ids': [(0, 0, vals) for vals in lineas]})
                _logger.info(f"SIT | [Move {move.id}] Se agregaron {len(lineas)} líneas contables de ret./perc./renta")
            else:
                _logger.info(f"SIT | [Move {move.id}] No hay montos para agregar (percepción/retención/renta)")

    # --- campo O2M en plural ---
    exp_duca_ids = fields.One2many('exp_duca', 'move_id', string='DUCAs')

    # --- Helpers DUCA ---
    def _get_duca(self):
        self.ensure_one()
        return self.exp_duca_ids[:1]  # por unique(move_id) habrá 0 o 1

    def _get_or_create_duca(self):
        duca = self._get_duca()
        if not duca:
            duca = self.env['exp_duca'].create({
                'move_id': self.id,
                'company_id': self.company_id.id,
            })
        return duca

    # --- Proxies (compute + inverse) ---
    duca_number = fields.Char(string="N° DUCA", compute="_compute_duca_fields",
                              inverse="_inverse_duca_number", store=False)
    duca_acceptance_date = fields.Date(string="Fecha aceptación", compute="_compute_duca_fields",
                                       inverse="_inverse_duca_acceptance_date", store=False)
    duca_regimen = fields.Char(string="Régimen", compute="_compute_duca_fields",
                               inverse="_inverse_duca_regimen", store=False)
    duca_aduana = fields.Char(string="Aduana", compute="_compute_duca_fields",
                              inverse="_inverse_duca_aduana", store=False)

    duca_currency_id = fields.Many2one("res.currency", string="Moneda DUCA",
                                       compute="_compute_duca_fields",
                                       inverse="_inverse_duca_currency", store=False)

    duca_valor_transaccion = fields.Monetary(
        string="Valor transacción",
        currency_field="duca_currency_id",
        compute="_compute_duca_fields",
        inverse="_inverse_duca_valor_transaccion",
        store=False,
    )

    duca_otros_gastos = fields.Monetary(
        string="Otros gastos",
        currency_field="duca_currency_id",
        compute="_compute_duca_fields",
        inverse="_inverse_duca_otros_gastos",
        store=False,
    )

    duca_valor_en_aduana = fields.Monetary(
        string="Valor en Aduana",
        currency_field="duca_currency_id",
        compute="_compute_duca_fields",
        inverse="_inverse_duca_valor",
        store=False,
    )
    duca_dai_amount = fields.Monetary(
        string="DAI",
        currency_field="duca_currency_id",
        compute="_compute_duca_fields",
        inverse="_inverse_duca_dai",
        store=False,
    )
    duca_iva_importacion = fields.Monetary(
        string="IVA importación (ref.)",
        currency_field="duca_currency_id",
        compute="_compute_duca_fields",
        inverse="_inverse_duca_iva",
        store=False,
    )

    duca_file = fields.Binary(string="Archivo DUCA",
                              compute="_compute_duca_fields",
                              inverse="_inverse_duca_file", store=False)
    duca_filename = fields.Char(string="Nombre archivo DUCA",
                                compute="_compute_duca_fields",
                                inverse="_inverse_duca_filename", store=False)

    def _compute_duca_fields(self):
        for move in self:
            duca = move._get_duca()
            move.duca_number = duca.number if duca else False
            move.duca_acceptance_date = duca.acceptance_date if duca else False
            move.duca_regimen = duca.regimen if duca else False
            move.duca_aduana = duca.aduana if duca else False
            move.duca_currency_id = duca.currency_id.id if duca else move.company_id.currency_id.id

            move.duca_valor_transaccion = duca.valor_transaccion if duca else 0.0
            move.duca_otros_gastos = duca.otros_gastos if duca else 0.0
            move.duca_valor_en_aduana = duca.valor_en_aduana if duca else 0.0
            move.duca_dai_amount = duca.dai_amount if duca else 0.0
            move.duca_iva_importacion = duca.iva_importacion if duca else 0.0

            move.duca_file = duca.duca_file if duca else False
            move.duca_filename = duca.duca_filename if duca else False

    def _inverse_duca_number(self):
        for move in self:
            move._get_or_create_duca().number = move.duca_number

    def _inverse_duca_acceptance_date(self):
        for move in self:
            move._get_or_create_duca().acceptance_date = move.duca_acceptance_date

    def _inverse_duca_regimen(self):
        for move in self:
            move._get_or_create_duca().regimen = move.duca_regimen

    def _inverse_duca_aduana(self):
        for move in self:
            move._get_or_create_duca().aduana = move.duca_aduana

    def _inverse_duca_currency(self):
        for move in self:
            move._get_or_create_duca().currency_id = move.duca_currency_id.id

    def _inverse_duca_valor_transaccion(self):
        for move in self:
            move._get_or_create_duca().valor_transaccion = move.duca_valor_transaccion

    def _inverse_duca_otros_gastos(self):
        for move in self:
            move._get_or_create_duca().otros_gastos = move.duca_otros_gastos

    def _inverse_duca_valor(self):
        for move in self:
            move._get_or_create_duca().valor_en_aduana = move.duca_valor_en_aduana

    def _inverse_duca_dai(self):
        for move in self:
            move._get_or_create_duca().dai_amount = move.duca_dai_amount

    def _inverse_duca_iva(self):
        for move in self:
            move._get_or_create_duca().iva_importacion = move.duca_iva_importacion

    def _inverse_duca_file(self):
        for move in self:
            duca = move._get_or_create_duca()
            duca.duca_file = move.duca_file
            if move.duca_file and not move.duca_filename:
                duca.duca_filename = (move.duca_number and f"DUCA_{move.duca_number}.pdf") or "DUCA.pdf"

    def _inverse_duca_filename(self):
        for move in self:
            move._get_or_create_duca().duca_filename = move.duca_filename

    def action_open_duca(self):
        self.ensure_one()
        duca = self._get_or_create_duca()
        return {
            'type': 'ir.actions.act_window',
            'name': 'DUCA',
            'res_model': 'exp_duca',
            'view_mode': 'form',
            'res_id': duca.id,
            'target': 'current',
        }
