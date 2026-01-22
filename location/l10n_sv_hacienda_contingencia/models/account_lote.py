##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from odoo.tools import float_repr
from odoo.addons.l10n_sv_haciendaws_fe.afip_utils import get_invoice_number_from_response
import base64
import pyqrcode
import qrcode
import os
from PIL import Image
import io

import logging
import sys
import traceback

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import config_utils
    _logger.info("SIT Modulo config_utils [hacienda ws-account_lote]")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    config_utils = None

class sit_account_lote(models.Model):
    _name = 'account.lote'
    _description = 'Lote de Facturas'

    fechaHoraTransmision = fields.Datetime(
        copy=False,
        string="Fecha/Hora de Transmisión",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )

    # --------CAMPOS LOTE --------------------

    hacienda_estado_lote = fields.Char(
        copy=False,
        string="Estado Lote",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    hacienda_idEnvio_lote = fields.Char(
        copy=False,
        string="Id de Envio Lote",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    hacienda_fhProcesamiento_lote = fields.Datetime(
        copy=False,
        string="Fecha de Procesamiento de Lote",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    hacienda_codigoLote_lote = fields.Char(
        copy=False,
        string="Codigo de Lote",
        readonly=True,
    )
    hacienda_codigoMsg_lote = fields.Char(
        copy=False,
        string="Codigo de Mensaje",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    hacienda_descripcionMsg_lote = fields.Char(
        copy=False,
        string="Descripción de Lote",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )

    state = fields.Selection(
        selection=[
            ('draft', 'Nuevo'),
            ('posted', 'Validado'),
            ('posted_lote', 'Lote Validado'),
            ('cancel', 'Cancelado'),
        ],
        string='Estado',
        required=True,
        readonly=True,
        # copy=False,
        tracking=True,
        default='draft',
    )

    error_log = fields.Text(string="Error técnico Contingencia", readonly=True)

    sit_contingencia = fields.Many2one('account.contingencia1', string="Contingencia asociada al lote")

    move_ids = fields.One2many(
        comodel_name='account.move',
        inverse_name='sit_lote_contingencia',
        string='Facturas Relacionadas'
    )

    lote_recibido_mh = fields.Boolean(string="Lote recibido por MH", copy=False)
    lote_activo = fields.Boolean(string="Lote Activo", copy=False, default=True)

    sit_json_respuesta = fields.Text("Json de Respuesta", default="")

    name = fields.Char(
        readonly=True,  # Solo lectura
        copy=False,
        string="Identificacion del lote",
        required=True
    )

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'El nombre del lote debe ser único.'),
    ]

    journal_id = fields.Many2one('account.journal', string='Diario', required=False)
    company_id = fields.Many2one('res.company', string="Compañía")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                _logger.error("Creando lote sin nombre: %s", vals)
        return super().create(vals_list)

    def action_ver_facturas(self):
        return {
            'name': 'Documentos Electrónicos del Lote',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('sit_lote_contingencia', '=', self.id)],
            'context': dict(self.env.context),
            'views': [(self.env.ref('l10n_sv_hacienda_contingencia.view_account_move_lote_list').id, 'list'),
                      (self.env.ref('account.view_move_form').id, 'form')],
        }

    # Generar secuencia para lotes
    @api.model
    def generar_nombre_lote(self, journal=None, actualizar_secuencia=False, empresa=False):
        journal = journal # or self.journal_id

        # Validaciones
        version_lote = config_utils.get_config_value(
            self.env, 'version_lote', journal.company_id.id
        )
        _logger.info("Versión lote: %s | Compañía: %s", version_lote, journal.company_id)

        if version_lote is None:
            raise UserError(_("Debe definir la versión del lote."))
        _logger.info("SIT diario: %s, tipo: %s, compañía: %s", journal, journal.type, journal.company_id)

        if not journal.sit_codestable:
            raise UserError(_("Configure Código de Establecimiento en diario '%s'.") % journal.name)

        if not journal.sit_codpuntoventa:
            raise UserError(_("Configure el Punto de Venta en el diario '%s'.") % journal.name)

        # if not journal.sequence_id:
        #     raise UserError(_("Configure una secuencia de lote en el diario '%s'.") % journal.name)

        # Obtener secuencia configurada para actualizar el número, no para generar el nombre
        # sequence = journal.sequence_id
        sequence = self.env['ir.sequence'].search([
            ('code', '=', 'LOT'),
            ('company_id', '=', empresa.id),
        ], limit=1)
        _logger.info("Secuencia lote: %s | Empresa: %s", sequence, empresa.id)
        if not sequence or not sequence.exists():
            raise UserError(_("Secuencia no configurada para lotes."))

        prefix = sequence.prefix or ''  # prefijo dinámico de la secuencia
        _logger.info("Prefix lote: %s", prefix)

        version_str = str(version_lote).zfill(2)
        if not version_str.strip():
            raise UserError("La versión de lote no puede estar vacía.")
        estable = journal.sit_codestable
        punto_venta = journal.sit_codpuntoventa

        # Armar patrón dinámico basado en prefix de la secuencia
        # Ejemplo: prefix="LOT-%(version)s-0000%(estable)s-" → se sustituye aquí
        # Diccionario para reemplazar placeholders con valores dinámicos
        replacements = {
            'lote': version_str,
            'estable': estable,
            'punto_venta': punto_venta,
        }
        # Reemplazar todos los placeholders en el prefijo de la secuencia
        pattern_prefix = prefix
        for key, value in replacements.items():
            pattern_prefix = pattern_prefix.replace(f'%({key})s', value)

        _logger.info("Prefijo dinámico final lote: %s", pattern_prefix)

        # Buscar último nombre generado con formato LOT-version-0000estable-
        ultimo = self.search([('company_id', '=', empresa.id), ('name', 'like', f'{pattern_prefix}%')], order='name desc', limit=1)
        if ultimo:
            try:
                ultima_parte = int(ultimo.name.split('-')[-1])
            except ValueError:
                raise UserError(_("No se pudo interpretar el número del último lote: %s") % ultimo.name)
            nuevo_numero = ultima_parte + 1
        else:
            nuevo_numero = 1

        # Generar el nuevo nombre con el prefix de la secuencia
        nuevo_name = f"{pattern_prefix}{str(nuevo_numero).zfill(15)}"

        # Verificar duplicado
        if self.search_count([('name', '=', nuevo_name), ('company_id', '=', empresa.id)]):
            raise UserError(_("El número de lote generado ya existe: %s") % nuevo_name)

        _logger.info("Nombre de lote generado dinámicamente con prefix: %s", nuevo_name)

        # Actualizar secuencia si es necesario
        if actualizar_secuencia:
            next_num = nuevo_numero + 1
            if sequence.use_date_range:
                today = fields.Date.context_today(self)
                date_range = self.env['ir.sequence.date_range'].search([
                    ('sequence_id', '=', sequence.id),
                    ('date_from', '<=', today),
                    ('date_to', '>=', today)
                ], limit=1)
                if date_range and date_range.number_next_actual < next_num:
                    date_range.number_next_actual = next_num
                    _logger.info("Secuencia con date_range '%s' actualizada a %s", sequence.code, next_num)
            else:
                if sequence.number_next_actual < next_num:
                    sequence.number_next_actual = next_num
                    _logger.info("Secuencia '%s' actualizada a %s", sequence.code, next_num)

        return nuevo_name
