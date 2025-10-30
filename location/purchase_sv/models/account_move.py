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

    sv_need_tax_override = fields.Boolean(
        compute= '_compute_sv_need_tax_override',
        store=False,
        string='Necesita ajuste de impuestos'
    )

    exp_duca_id = fields.One2many('exp_duca', 'move_id', string='DUCAs')

    document_number = fields.Char("Número de documento de proveedor")

    # Campo real: Many2one que se guarda en la BD
    sit_tipo_documento_id = fields.Many2one(
        'account.journal.tipo_documento.field',
        string='Tipo de Documento',
        store=True,
        default=lambda self: self._get_default_tipo_documento(),
    )

    codigo_tipo_documento_id = fields.Char(
        string="Código tipo documento",
        related='sit_tipo_documento_id.codigo',
        store=False,  # pon True si quieres poder buscar/filtrar por este campo
        readonly=True,
    )

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
    )

    # METODOS PARA VERIFICAR SI ES NECESARIO CAMBIAR CUENTA CONTABLE DE IMPUESTO
    def _compute_sv_need_tax_override(self):
        """Determina si el asiento necesita ajuste de cuentas de impuesto
        según las cuentas alternativas configuradas en los impuestos de las líneas.
        """
        for m in self:
            need = False
            if m.is_purchase_document(include_receipts=False):
                if m.invoice_date and m.invoice_date_due and m.invoice_date_duce > m.invoice_date:
                    need = True
                m.sv.need_tax_override = need
    
    def _sv_get_blocking_tax_lines(self):
        """Líneas de impuesto cuyo account_id sigue igual a la cuenta por defecto del
        tax_repartition_line (o sea, aún no fue sustituida)."""
        self.ensure_one()
        tax_lines = self.line_ids.filtered(lambda l: l.tax_line_id)
        return tax_lines.filtered(lambda l: l.account_id == l.tax_repartition_line_id.account_id)


    # Verificar que el name (o numero de control) sea unico
    @api.constrains('name', 'company_id')
    def _check_unique_name(self):
        for move in self:
            if (move.move_type in (constants.OUT_INVOICE, constants.OUT_REFUND) or
                (move.move_type == constants.IN_INVOICE and move.journal_id and move.journal_id.sit_tipo_documento and move.journal_id.sit_tipo_documento.codigo == constants.COD_DTE_FSE)):
                name = (move.name or '').strip()
                _logger.info("Validando número de documento '%s' (ID %s) para la compañía ID %s tipo de movimiento %s", name, move.id, move.company_id.id, move.move_type)

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
            if move.move_type not in (constants.IN_INVOICE, constants.IN_REFUND):
                continue

            sello = self._norm_sello(move.hacienda_selloRecibido)
            if not sello:
                continue

            dup = self.search([
                ('id', '!=', move.id),
                ('company_id', '=', move.company_id.id),
                ('move_type', 'in', [constants.IN_INVOICE, constants.IN_REFUND]),
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
            if move.move_type not in (constants.IN_INVOICE, constants.IN_REFUND):
                continue

            codigo_generacion = self._norm_sello(move.hacienda_codigoGeneracion_identificacion)
            if not codigo_generacion:
                continue

            dup = self.search([
                ('id', '!=', move.id),
                ('company_id', '=', move.company_id.id),
                ('move_type', 'in', [constants.IN_INVOICE, constants.IN_REFUND]),
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
        compute='_compute_retencion',
        readonly=True,
        store=True,
        default=0.0
    )

    amount_exento = fields.Monetary(
        string="Exento",
        compute='_compute_amount_exento',
        store=True,
        currency_field='currency_id'
    )

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
                    and (not rec.journal_id.sit_tipo_documento or rec.journal_id.sit_tipo_documento.codigo != constants.COD_DTE_FSE)):
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

    @api.depends('line_ids.price_subtotal', 'line_ids.tax_ids')
    def _compute_amount_exento(self):
        for move in self:
            total_exento = 0.0
            _logger.info("SIT | Calculando amount_exento para move_id=%s", move.id)
            for line in move.line_ids:

                if line.move_id.move_type in (constants.TYPE_ENTRY, constants.OUT_RECEIPT, constants.IN_RECEIPT):
                    _logger.info("[SIT] Se omite _compute_amount_exento para movimiento tipo '%s' (ID: %s)", line.move_id.move_type, line.move_id.id)
                    continue

                if (line.move_id and
                        (line.move_id.move_type not in(constants.IN_INVOICE, constants.IN_REFUND) or
                        (line.move_id.move_type == constants.IN_INVOICE and line.move_id.journal_id
                         and line.move_id.journal_id.sit_tipo_documento and line.move_id.journal_id.sit_tipo_documento.codigo == constants.COD_DTE_FSE)) ):
                    _logger.info("[SIT] Se omite movimientos distintos a compras '%s' (ID: %s)", line.move_id.move_type, line.move_id.id)
                    continue

                impuestos = line.tax_ids
                if not impuestos:
                    _logger.info("SIT | Línea sin impuestos: line_id=%s, subtotal=%.2f", line.id, line.price_subtotal)
                    total_exento += line.price_subtotal
                elif all(t.amount == 0 for t in impuestos):
                    _logger.info("SIT | Línea con impuestos 0%%: line_id=%s, subtotal=%.2f", line.id, line.price_subtotal)
                    total_exento += line.price_subtotal
                else:
                    _logger.debug("SIT | Línea con impuestos >0%%: line_id=%s", line.id)

            move.amount_exento = total_exento
            _logger.info("SIT | Total exento para move_id=%s = %.2f", move.id, total_exento)

    def _sv_requires_tax_override(self):
        """True si es compra y el vencimiento es mayor que la fecha contable."""
        self.ensure_one()
        return (
            self.move_type in ('in_invoice', 'in_refund')
            and self.invoice_date and self.invoice_date_due
            and self.invoice_date_due > self.invoice_date
        )

    def _sv_get_move_taxes(self):
        """Impuestos usados en líneas de la factura."""
        self.ensure_one()
        return self.invoice_line_ids.mapped('tax_ids')
    
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
        # IMMEDIATE_PAYMENT = self.env.ref('account.account_payment_term_immediate').id

        for move in self:
            _logger.info("SIT-Compra move type: %s, tipo documento %s: ", move.move_type, move.codigo_tipo_documento)
            if move.move_type in(constants.OUT_INVOICE, constants.OUT_REFUND):
                _logger.info("SIT Action post no aplica para ventas.")
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

            if not move.sit_tipo_documento_id:
                _logger.info("SIT | Tipo de documento no seleccionado.")
                raise ValidationError("Debe seleccionar el Tipo de documento de compra.")

            if not move.clase_documento_id:
                _logger.info("SIT | Clase de documento no seleccionada.")
                raise ValidationError("Debe seleccionar la Clase de documento.")

            if move.sit_tipo_documento_id and move.sit_tipo_documento_id.codigo != constants.COD_DTE_FEX and not move.hacienda_selloRecibido:
                _logger.info("SIT | Sello Recepcion no agregado.")
                if move.clase_documento_id and move.clase_documento_id.codigo == DTE_COD:
                    raise ValidationError("Debe agregar el Sello de recepción.")
                else:
                    raise ValidationError("Debe agregar el Número de serie.")

            if move.sit_tipo_documento_id and move.sit_tipo_documento_id.codigo != constants.COD_DTE_FEX and not move.hacienda_codigoGeneracion_identificacion:
                _logger.info("SIT | Codigo de generacion no agregado.")
                if move.clase_documento_id and move.clase_documento_id.codigo == DTE_COD:
                    raise ValidationError("Debe agregar el Codigo de generación.")
                else:
                    raise ValidationError("Debe agregar el Correlativo.")

            if not move.sit_observaciones:
                _logger.info("SIT | Descripcion no agregada.")
                raise ValidationError("Se requiere una descripción.")

            # Validación de Condición/Plazo solo para ventas
            # payment_term_id = move.invoice_payment_term_id.id if move.invoice_payment_term_id else None
            # _logger.info("Termino de pago seleccionado: %s", move.invoice_payment_term_id.name if move.invoice_payment_term_id else None)

            # if payment_term_id and payment_term_id != IMMEDIATE_PAYMENT and not move.sit_condicion_plazo:
            #     _logger.info("Debe seleccionar el campo 'Condición del Plazo Crédito' si el término de pago no es 'Pago inmediato'.")
            #     raise ValidationError(_("Debe seleccionar el campo 'Condición del Plazo Crédito' si el término de pago no es 'Pago inmediato'."))

            # Verificar si se necesita ajuste de cuentas de impuesto
            # --- REGLA: vencimiento > contable en compras -> pedir cuentas alternativas por impuesto ---
            # Usa el mapeo persistente sv.move.tax.account.override que ya agregamos.
            if not self.env.context.get('sv_skip_tax_override') and move._sv_requires_tax_override():
                taxes = move._sv_get_move_taxes()
                # ¿Qué impuestos aún no tienen mapeo de cuenta alternativa en ESTA factura?
                missing = taxes.filtered(lambda t: not move.sv_override_ids.filtered(lambda r: r.tax_id == t))
                if missing:
                    _logger.info("SIT | Falta asignar cuentas alternativas para impuestos: %s",
                                 ', '.join(missing.mapped('name')))
                    # Abre el wizard para que el usuario elija cuentas (solo esta factura)
                    action = self.env.ref('purchase_sv.action_sv_tax_override_wizard').read()[0]
                    action['context'] = dict(
                        self.env.context,
                        active_model='account.move',
                        active_id=move.id,
                        active_ids=[move.id],
                        default_move_id=move.id,
                    )
                    return action   
                
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
        - `percepcion_purchase_id`
        - `retencion_iva_purchase_id`
        - `renta_purchase_id`
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

            # Acumular montos
            total_percepcion = sum(line.percepcion_amount for line in move.invoice_line_ids)
            total_retencion = sum(line.retencion_amount for line in move.invoice_line_ids)
            total_renta = sum(line.renta_amount for line in move.invoice_line_ids)

            _logger.info(
                f"SIT | [Move {move.id}] Totales calculados -> Percepción: {total_percepcion}, "
                f"Retención IVA: {total_retencion}, Renta: {total_renta}"
            )

            # --- Si todos los montos son 0, no hacer nada ---
            if not any([total_percepcion > 0, total_retencion > 0, total_renta > 0]):
                _logger.info(f"SIT | [Move {move.id}] No aplica generación de asientos (todos los montos = 0).")
                continue

            # --- Validar configuración de cuentas en compañía
            missing_accounts = []
            if total_percepcion > 0 and not company.percepcion_purchase_id:
                missing_accounts.append("Cuenta de Percepción 1%")
            if total_retencion > 0 and not company.retencion_iva_purchase_id:
                missing_accounts.append("Cuenta de Retención IVA")
            if total_renta > 0 and not company.renta_purchase_id:
                missing_accounts.append("Cuenta de Renta")

            if missing_accounts:
                raise UserError(
                    "No se pueden generar los asientos de retención/percepción/renta porque faltan cuentas en la compañía "
                    f"{company.name}:\n- " + "\n- ".join(missing_accounts)
                    )

            # --- Si no hay ninguna cuenta configurada, salir sin error ---
            if not any([
                company.percepcion_purchase_id,
                company.retencion_iva_purchase_id,
                company.renta_purchase_id
            ]):
                _logger.info(
                    f"SIT | [Move {move.id}] No se configuraron cuentas de retención/percepción/renta en {company.name}, se omite.")
                continue

            # --- Eliminar líneas previas seguras ---
            target_names = {
                c.name for c in [
                    company.percepcion_purchase_id,
                    company.retencion_iva_purchase_id,
                    company.renta_purchase_id
                ] if c
            }

            # Eliminar líneas previas de este tipo
            # previas = move.line_ids.filtered(lambda l: l.name in [company.percepcion_purchase_id.name, company.retencion_iva_purchase_id.name, company.renta_purchase_id.name])
            # if previas:
            #     _logger.info(f"SIT | [Move {move.id}] Eliminando {len(previas)} líneas previas de retención/percepción/renta")
            #     previas.unlink()

            # Solo considerar líneas con esos nombres pero EXCLUIR líneas tipo receivable/payable
            previas = move.line_ids.filtered(
                lambda l: (
                        l.account_id
                        and l.account_id.account_type not in ('asset_receivable', 'liability_payable')
                        and l.name in target_names
                        and not l.reconciled
                )
            )

            if previas:
                _logger.info(
                    f"SIT | [Move {move.id}] Eliminando {len(previas)} líneas previas de retención/percepción/renta.")
                try:
                    previas.unlink()
                except Exception as e:
                    _logger.exception(f"SIT | [Move {move.id}] Error al eliminar previas: {e}")
                    # fallback: marcar para sobrescribir en lugar de eliminar

            lineas = []

            def redondear(monto):
                return float_round(monto or 0.0, precision_rounding=precision)

            # --- Percepción
            if total_percepcion > 0 and company.percepcion_purchase_id:
                lineas.append({
                    'name': company.percepcion_purchase_id.name,
                    'account_id': company.percepcion_purchase_id.id,
                    'debit': redondear(total_percepcion),
                    'credit': 0.0,
                    'move_id': move.id,
                })
                _logger.info(f"SIT | [Move {move.id}] Línea de Percepción lista: {redondear(total_percepcion)}")

            # --- Retención IVA
            if total_retencion > 0 and company.retencion_iva_purchase_id:
                lineas.append({
                    'name': company.retencion_iva_purchase_id.name,
                    'account_id': company.retencion_iva_purchase_id.id,
                    'debit': 0.0,
                    'credit': redondear(total_retencion),
                    'move_id': move.id,
                })
                _logger.info(f"SIT | [Move {move.id}] Línea de Retención IVA lista: {redondear(total_retencion)}")

            # --- Renta
            if total_renta > 0 and company.renta_purchase_id:
                lineas.append({
                    'name': company.renta_purchase_id.name,
                    'account_id': company.renta_purchase_id.id,
                    'debit': 0.0,
                    'credit': redondear(total_renta),
                    'move_id': move.id,
                })
                _logger.info(f"SIT | [Move {move.id}] Línea de Renta lista: {redondear(total_renta)}")

            # --- Crear líneas en el asiento ---
            if lineas:
                move.write({'line_ids': [(0, 0, vals) for vals in lineas]})
                _logger.info(f"SIT | [Move {move.id}] Se agregaron {len(lineas)} líneas contables de ret./perc./renta.")
            else:
                _logger.info(
                    f"SIT | [Move {move.id}] No hay líneas para agregar (montos = 0 o sin cuentas configuradas).")

    @api.depends(
        'invoice_line_ids.apply_percepcion',
        'invoice_line_ids.apply_retencion',
        'invoice_line_ids.renta_percentage',
        'invoice_line_ids.price_subtotal'
    )
    def _compute_retencion(self):
        """
        Extiende el cálculo de retenciones del módulo 'invoice_sv' para incluir:
          - Percepción (1%)
          - Retención de IVA (personalizada)
          - Retención de renta (porcentaje variable)

        Funcionamiento:
          1. Ejecuta primero el cálculo base del módulo original (super()).
          2. Aplica la extensión solo a facturas de compra (IN_INVOICE, IN_REFUND)
             que no sean del tipo FSE.
          3. Suma los montos línea por línea y actualiza los totales del movimiento.
          4. Si los valores cambian a 0, también se reflejan (no se acumulan).

        Campos afectados:
          - percepcion_amount
          - retencion_iva_amount
          - retencion_renta_amount
        """
        # Ejecutar el cómputo original del módulo base
        super(AccountMove, self)._compute_retencion()

        for move in self:
            # --- FILTRO: solo aplica a facturas de proveedor (no FSE) ---
            if (move.move_type not in (constants.IN_INVOICE, constants.IN_REFUND) or
                    (move.move_type == constants.IN_INVOICE and move.journal_id
                    and move.journal_id.sit_tipo_documento and move.journal_id.sit_tipo_documento.codigo == constants.COD_DTE_FSE)):
                _logger.info(
                    "SIT | _compute_retencion extendido omitido para move_id=%s (tipo=%s)",
                    move.id, move.move_type
                )
                continue

            # --- SUMATORIAS DE LÍNEAS ---
            total_percepcion = sum(line.percepcion_amount for line in move.invoice_line_ids)
            total_retencion = sum(line.retencion_amount for line in move.invoice_line_ids)
            total_renta = sum(line.renta_amount for line in move.invoice_line_ids)

            # --- LOG DETALLADO DE CADA LÍNEA ---
            for line in move.invoice_line_ids:
                _logger.info(
                    "SIT | [Línea %s] percepcion=%s, retencion=%s, renta=%s (subtotal=%s)",
                    line.id, line.percepcion_amount, line.retencion_amount,
                    line.renta_amount, line.price_subtotal
                )

            # --- ASIGNACIÓN DIRECTA (sin acumulación) ---
            move.percepcion_amount = total_percepcion or 0.0
            move.retencion_iva_amount = total_retencion or 0.0
            move.retencion_renta_amount = total_renta or 0.0

            _logger.info(
                "SIT | [Move %s] Totales recalculados -> Percepción=%s, Retención IVA=%s, Renta=%s",
                move.id, total_percepcion, total_retencion, total_renta
            )

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
