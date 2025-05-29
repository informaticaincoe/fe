# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from odoo.tools import float_repr
import pytz
import logging
_logger = logging.getLogger(__name__)

from pytz import timezone
from datetime import datetime
import pytz

def _default_fecha_hora_sv():
    tz = pytz.timezone('America/El_Salvador')
    return pytz.utc.localize(datetime.utcnow()).astimezone(tz)

class sit_account_contingencia(models.Model):
    
    _name = 'account.contingencia1'
    _description = "Entrada de contingencia"

    name = fields.Char(
        string='Number',
        compute='_compute_name', 
        required=True,

        # readonly=False, 
        store=True,
        # copy=False,
        # tracking=True,
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
    date = fields.Datetime(
        string='Date',
        index=True,
        compute='_compute_date', 
        store=True, 
        required=True, 
        # readonly=False, 
        precompute=True,
        # states={'posted': [('readonly', True)], 'cancel': [('readonly', True)]},
        # copy=False,
        # tracking=True,
    )
    invoice_user_id = fields.Many2one(
        string='Responsable',
        comodel_name='res.users',
        copy=False,
        tracking=True,
        default=lambda self: self.env.user,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        compute='_compute_company_id', store=True, readonly=False, precompute=True,
        index=True,
    )    
    journal_id = fields.Many2one(
        'account.journal',
        string='Diario',
        # compute='_compute_journal_id', store=True, readonly=False, precompute=True,
        required=True,
        # states={'draft': [('readonly', False)]},
        # check_company=True,
        # domain="[('id', 'in', suitable_journal_ids)]",
    )
    sit_fInicio_hInicio = fields.Datetime("Fecha de Inicio de Contingencia - Hacienda", required=True, help="Asignación de Fecha manual para registrarse en Hacienda", default=_default_fecha_hora_sv)
    fecha_hora_creacion = fields.Datetime(string="Fecha y hora (El Salvador)", readonly=True)

    sit_fFin_hFin = fields.Datetime("Fecha de Fin de Contingencia - Hacienda",  help="Asignación de Fecha manual para registrarse en Hacienda", )
    sit_tipo_contingencia = fields.Many2one('account.move.tipo_contingencia.field', string="Tipo de Contingencia")
    sit_tipo_contingencia_otro = fields.Text(string="Especifique el Otro Tipo de Contingencia")
    sit_tipo_contingencia_valores = fields.Char(related="sit_tipo_contingencia.valores", string="Tipo de contingiancia(nombre)")
    sit_facturas_relacionadas = fields.One2many(
        'account.move',
        'sit_factura_de_contingencia',
        string='Facturas relacionadas',
    #     copy=True,
    #     # readonly=True,
    #     states={'draft': [('readonly', False)]},
    )


    sit_estado = fields.Text(string="Estado - Hacienda", default="")
    sit_fechaHora = fields.Datetime("Fecha de Hacienda",  help="Asignación de Fecha manual para registrarse en Hacienda", )
    sit_mensaje = fields.Text(string="Mensaje - Hacienda", default="")
    sit_selloRecibido = fields.Text(string="sello Recibido - Hacienda", default="")
    sit_observaciones=fields.Text("observaciones - Hacienda", default="") 
    hacienda_estado=fields.Text("hacienda estado", default="") 
    sit_json_respuesta = fields.Text("Json de Respuesta", default="")
    hacienda_codigoGeneracion_identificacion = fields.Char(
        copy=False,
        string="Codigo de Generación de Identificación Contingencia",
        readonly=True,
        states={"draft": [("readonly", False)]},
    )
    sit_documento_firmado_contingencia = fields.Text(
        string="Documento Firmado Contingencia",
        copy=False,
        readonly=True,
    )

    lote_ids = fields.One2many(
        'account.lote',
        'sit_contingencia',
        string='Lotes asociados'
    )

    contingencia_recibida_mh = fields.Boolean(string="Lote recibido por MH", copy=False)
    contingencia_activa = fields.Boolean(string="Contingencia Activa", copy=False, default=True)

    boton_contingencia = fields.Boolean(
        string="Mostrar botón de lote",
        compute='_compute_mostrar_boton_contingencia',
        store=False
    )

    boton_lote = fields.Boolean(
        string="Mostrar botón de lote",
        compute='_compute_mostrar_boton_lote',
        store=False
    )

    ultima_actualizacion_task = fields.Datetime(string="Última actualización del cron")

    @api.depends('lote_ids.lote_recibido_mh')
    def _compute_mostrar_boton_lote(self):
        for rec in self:
            # Lógica de ejemplo: mostrar solo si está en 'posted' y aún no tiene lote
            rec.boton_lote = any(not lote.lote_recibido_mh for lote in rec.lote_ids)

    @api.depends('contingencia_recibida_mh')
    def _compute_mostrar_boton_contingencia(self):
        for rec in self:
            # Lógica de ejemplo: mostrar solo si está en 'posted' y aún no tiene lote
            rec.boton_contingencia = not rec.contingencia_recibida_mh

    def _compute_company_id(self):
        _logger.info("SIT calculando company_id")
        for move in self:
            company_id = self.env.company
            if company_id != move.company_id:
                move.company_id = company_id

    def _compute_date(self):
        _logger.info("SIT calculando date")
        for move in self:
            if not move.date:
                move.date = fields.Date.context_today(self)

    def _compute_name(self):
        _logger.info("SIT asignando name")
        for record in self:

            import datetime
            FechaEventoContingencia = datetime.datetime.now()
            _logger.info("SIT FechaEventoContingencia = %s (%s)", FechaEventoContingencia, type(FechaEventoContingencia))
            FECHA_EVENTO_CONTINGENCIA = FechaEventoContingencia.strftime('%Y-%m-%d_%H%M%S')
            _logger.info("SIT sit_ccf_ FECHA_EVENTO_CONTINGENCIA = %s", FECHA_EVENTO_CONTINGENCIA)

            NAME = "EVENTO_CONTINGENCIA_" + str(FECHA_EVENTO_CONTINGENCIA)
            record.name = NAME




# ---------------------------------------------------------------------------------------------
    # def action_post_contingencia(self):
    #     '''validamos que partner cumple los requisitos basados en el tipo
    # de documento de la sequencia del diario selecionado
    # FACTURA ELECTRONICAMENTE
    # '''
    #     _logger.info("SIT action_post_contingencia ")
    #     MENSAJE = "SIT Generando Factura de Contingencia = ..." 
    #     raise UserError(_(MENSAJE))        


    def _compute_validation_type_2(self):
        for rec in self:
            if  not rec.afip_auth_code:
                validation_type = self.env["res.company"]._get_environment_type()
                if validation_type == "homologation":
                    try:
                        rec.company_id.get_key_and_certificate(validation_type)
                    except Exception:
                        validation_type = False
                return validation_type
            else:
                return False

    @api.model
    def create(self, vals):
        # Crear el registro de contingencia
        record = super().create(vals)

        # Buscar todas las facturas que están en contingencia y no están asignadas a ninguna contingencia aún
        facturas_en_contingencia = self.env['account.move'].search([
            ('sit_es_configencia', '=', True),
            ('sit_factura_de_contingencia', '=', False),
            '|', ('hacienda_selloRecibido', '=', None), ('hacienda_selloRecibido', '=', '')
        ])

        # Asignar las facturas al registro actual
        if facturas_en_contingencia:
            facturas_en_contingencia_count = len(facturas_en_contingencia)

            # Verificar si las facturas no superan los 400 lotes de 100 facturas por lote
            max_lotes = 2#400
            facturas_por_lote = 2#100

            total_lotes = ((facturas_en_contingencia_count // facturas_por_lote) +
                           (1 if facturas_en_contingencia_count % facturas_por_lote != 0 else 0))

            if total_lotes > max_lotes:
                _logger.info(
                    "La cantidad de facturas excede el límite de lotes permitidos. Solo se asignarán los primeros 400 lotes.")
                facturas_a_incluir = facturas_en_contingencia[:max_lotes * facturas_por_lote]
                facturas_en_contingencia = facturas_a_incluir  # Solo trabajar con las primeras 40,000 facturas

            # Crear los lotes y asignar las facturas a cada lote
            lote_count = 0
            for i in range(0, facturas_en_contingencia_count, facturas_por_lote):
                facturas_lote = facturas_en_contingencia[i:i + facturas_por_lote]

                # Crear lote
                lote_vals = {
                    'sit_contingencia': record.id,  # Relaciona el lote con la contingencia
                    'state': 'draft',  # El lote puede empezar en estado borrador
                }
                lote_record = self.env['account.lote'].create(lote_vals)
                lote_count += 1
                _logger.info(f"Lote creado con {len(facturas_lote)} facturas en contingencia.")

                # Asignar cada lote a las facturas correspondientes
                facturas_lote.write({
                    'sit_lote_contingencia': lote_record.id
                })
            # Después de asignar todas las facturas a los lotes, las asociamos a la contingencia
            facturas_en_contingencia.write({
                'sit_factura_de_contingencia': record.id
            })
        return record

    #@api.model
    def actualizar_contingencias_expiradas(self):
        """Desactiva contingencias que han pasado 24 horas desde su inicio."""
        _logger.info("Desactivar contingencias que han pasado 24 horas desde su inicio=%s", self.id)
        tz = pytz.timezone('America/El_Salvador')
        hora_actual = pytz.utc.localize(datetime.utcnow()).astimezone(tz)

        # Buscar contingencias activas con fecha de inicio válida
        contingencias = self.search([
            ('contingencia_activa', '=', True),
            ('sit_fInicio_hInicio', '!=', False)
        ])

        for contingencia in contingencias:
            inicio = contingencia.sit_fInicio_hInicio
            if inicio:
                # Convertir a zona horaria de El Salvador si está en UTC
                if inicio.tzinfo is None:
                    inicio = pytz.utc.localize(inicio).astimezone(tz)

                if hora_actual - inicio >= timedelta(hours=24):
                    contingencia.contingencia_activa = False
                    _logger.info("Contingencia actualizada=%s", contingencia.id)
