# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from datetime import datetime
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError

import logging
_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    document_number = fields.Char("Número de documento de proveedor")

    # Campo real: Many2one que se guarda en la BD
    sit_tipo_documento_id = fields.Many2one(
        'account.journal.tipo_documento.field',
        string='Tipo de Documento',
        related='journal_id.sit_tipo_documento',
        store=True,
        default=lambda self: self._get_default_tipo_documento(),
        domain=lambda self: self._get_tipo_documento_domain(),
    )

    fecha_aplicacion = fields.Date(string="Fecha de Aplicación")

    fecha_iva = fields.Date(string="Fecha IVA")

    #CAMPOS NUMERICOS EN DETALLE DE COMPRAS
    # comp_exenta_nsuj = fields.Float(
    #     string="Compras Internas Exentas y/o No Sujetas",
    #     digits=(16, 2),  # 16 dígitos totales, 2 decimales
    #     help="Ingrese un valor decimal, por ejemplo 1234.56"
    # )
    #
    # inter_exenta_nsuj = fields.Float(
    #     string="Internaciones Exentas y/o No Sujetas",
    #     digits=(16, 2),  # 16 dígitos totales, 2 decimales
    #     help="Ingrese un valor decimal, por ejemplo 1234.56"
    # )
    #
    # importacion_exenta_nsuj = fields.Float(
    #     string="Importaciones Exentas y/o No Sujetas",
    #     digits=(16, 2),  # 16 dígitos totales, 2 decimales
    #     help="Ingrese un valor decimal, por ejemplo 1234.56"
    # )
    #
    # inter_gravada = fields.Float(
    #     string="Compras Internas Gravadas",
    #     digits=(16, 2),  # 16 dígitos totales, 2 decimales
    #     help="Ingrese un valor decimal, por ejemplo 1234.56"
    # )
    #
    # inter_gravada_bien = fields.Float(
    #     string="Internaciones Gravadas de Bienes",
    #     digits=(16, 2),  # 16 dígitos totales, 2 decimales
    #     help="Ingrese un valor decimal, por ejemplo 1234.56"
    # )
    #
    # impor_gravada_bien = fields.Float(
    #     string="Importaciones Gravadas de Bienes",
    #     digits=(16, 2),  # 16 dígitos totales, 2 decimales
    #     help="Ingrese un valor decimal, por ejemplo 1234.56"
    # )
    #
    # impor_gravada_servicio = fields.Float(
    #     string="Importaciones Gravadas de Servicios",
    #     digits=(16, 2),  # 16 dígitos totales, 2 decimales
    #     help="Ingrese un valor decimal, por ejemplo 1234.56"
    # )

    def _get_default_tipo_documento(self):
        # Lógica para obtener el valor predeterminado según el contexto o condiciones
        return self.env['account.journal.tipo_documento.field'].search([('codigo', '=', '01')], limit=1)

    def _get_tipo_documento_domain(self):
        # Lógica para establecer el dominio del campo para siempre mostrar los documentos con los códigos especificados
        _logger.info("Tipos de documento")
        # Mostrar los tipos de documentos con los códigos '03', '05', '06', '11' en todos los casos
        return [('codigo', 'in', ['03', '05', '06', '11'])]

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
            _logger.info("Compute show_sit_tipo_documento: move id=%s, move_type=%s, show=%s", move.id, move.move_type, move.show_sit_tipo_documento)

    @api.onchange('name', 'hacienda_codigoGeneracion_identificacion', 'hacienda_selloRecibido')
    def _onchange_remove_hyphen_and_spaces(self):
        if self.move_type != 'in_invoice':
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
                _logger.info(
                    "[ONCHANGE] move_id=%s: 'hacienda_codigoGeneracion_identificacion' changed from '%s' to '%s'",
                    self.id, old_val, self.hacienda_codigoGeneracion_identificacion)

        # hacienda_selloRecibido
        if self.hacienda_selloRecibido:
            old_val = self.hacienda_selloRecibido
            self.hacienda_selloRecibido = old_val.replace('-', '').replace(' ', '')
            if old_val != self.hacienda_selloRecibido:
                _logger.info(
                    "[ONCHANGE] move_id=%s: 'hacienda_selloRecibido' changed from '%s' to '%s'",
                    self.id, old_val, self.hacienda_selloRecibido)

    def write(self, vals):
        if 'name' in vals:
            for move in self:
                # if move.move_type not in ('out_invoice', 'out_refund'):
                #     continue

                _logger.info("Tipo de documento(dte): %s", move.codigo_tipo_documento)
                if not move.codigo_tipo_documento:
                    continue

                old_name = move.name or ''
                new_name = vals.get('name') or ''

                _logger.info(
                    "[WRITE-VALIDATION] move_id=%s, state=%s, old_name=%s, new_name=%s, "
                    "auto_generated=%s, manual_update=%s",
                    move.id, move.state, old_name, new_name,
                    self.env.context.get("_dte_auto_generated"),
                    self.env.context.get("_dte_manual_update")
                )

                # Si el valor no cambia, dejamos pasar
                if old_name == new_name:
                    _logger.info(
                        "Account_move_purchase [WRITE-VALIDATION] El valor de 'name' no cambió (se mantiene %s). Permitido.",
                        old_name
                    )
                    continue

                # Si no viene con el flag de generación automática → bloquear
                bloquear = True  # asumimos que siempre se bloquea

                # Permitir reset a '/'
                if old_name == '/' and new_name != '/':
                    bloquear = False
                # Permitir actualización desde onchange / auto-generada
                elif self.env.context.get("_dte_auto_generated"):
                    bloquear = False
                # Permitir actualización manual explícita
                elif self.env.context.get("_dte_manual_update"):
                    bloquear = False

                _logger.info(
                    "SIT Bloquear modificacion de name: %s, name anterior: %s, nuevo name. %s",
                    bloquear, old_name, new_name
                )

                _logger.info("SIT Bloquear modificacion de name: %s, name anterior: %s, nuevo name. %s", bloquear,
                             old_name, new_name)
                if bloquear:
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
                    "[WRITE-VALIDATION] Cambio de 'name' permitido. Valor anterior: %s → Nuevo valor: %s",
                    old_name, new_name
                )
        return super().write(vals)

    def action_post(self):
        _logger.info("SIT Action post purchase: %s", self)
        for move in self:

            _logger.info("SIT-Compra move type: %s, tipo documento %s: ", move.move_type, move.codigo_tipo_documento)
            if move.move_type != 'in_invoice':
                _logger.info("SIT Action post no aplica a modulos distintos a compra.")
                continue
            elif move.move_type == 'in_invoice' and move.codigo_tipo_documento:
                _logger.info("SIT Action post no aplica para compras electronicas(como suejto excluido).")
                continue

            if move.move_type == 'in_invoice' and move.codigo_tipo_documento and move.hacienda_codigoGeneracion_identificacion:
                existing = self.search([
                    ('id', '!=', move.id),
                    ('hacienda_codigoGeneracion_identificacion', '=', move.hacienda_codigoGeneracion_identificacion)
                ], limit=1)
                if existing:
                    raise ValidationError(_(
                        "El Número de Resolución '%s' ya existe en otro documento (%s)."
                    ) % (move.hacienda_codigoGeneracion_identificacion, existing.name))

            if not move.fecha_aplicacion:
                _logger.info("SIT | Fecha de aplicacion no seleccionada.")
                raise ValidationError("Debe seleccionar la Fecha de Aplicación.")

            if not move.fecha_iva:
                _logger.info("SIT | Fecha IVA no seleccionada.")
                raise ValidationError("Debe seleccionar la Fecha de IVA.")

            fecha_iva = move.fecha_iva
            date_invoice = move.invoice_date

            _logger.info("SIT | Fecha factura: %s, Fecha IVA: %s.", date_invoice, fecha_iva)
            if fecha_iva and date_invoice:
                # Ambas son fechas, se comparan directamente
                if fecha_iva < date_invoice:
                    _logger.info(
                        "SIT | Fecha IVA (%s) no debe ser menor a la fecha de la factura (%s).",
                        fecha_iva,
                        date_invoice
                    )
                    raise ValidationError(
                        "Fecha IVA (%s) no debe ser menor a la fecha de la factura (%s)." % (
                            fecha_iva,
                            date_invoice
                        )
                    )

        return super(AccountMove, self).action_post()

    def _post(self, soft=True):
        _logger.info("SIT Purchase.")

        result = super(AccountMove, self)._post(soft=soft)

        for move in self:
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
