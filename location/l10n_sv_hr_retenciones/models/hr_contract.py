import logging
from odoo import models, fields

_logger = logging.getLogger(__name__)

try:
    from odoo.addons.common_utils.utils import constants
    _logger.info("SIT Modulo config_utils l10n_sv_haciendaws_fe")
except ImportError as e:
    _logger.error(f"Error al importar 'config_utils': {e}")
    constants = None

class HrContract(models.Model):
    _inherit = 'hr.contract'

    #Opcion de servicios profesionales en campo tipo de salario del contrato
    wage_type = fields.Selection(
        selection_add=[('professional_services', 'Salario por servicios profesionales')],
        string='Tipo de salario'
    )

    hourly_wage = fields.Float(
        string="Salario por hora",
        digits=(16, 4),  # ✅ Ahora permite 4 decimales
    )

    def get_salario_bruto_total(self):
        """
        Retorna el salario base + total de asignaciones sujetas a retención,
        incluyendo horas extra, comisiones y bonos.
        """
        self.ensure_one()

        bruto = self.wage or 0.0  # Define salario base
        _logger.info("📌 Salario base del contrato ID %s = %.2f", self.id, bruto)

        if not self.employee_id:
            _logger.warning("Contrato %s no tiene empleado asignado. Retornando solo salario base.", self.id)
            return bruto  # ✅ Ya está definido

        tipos_incluidos = [
            constants.ASIGNACION_HORAS_EXTRA.upper(),
            constants.ASIGNACION_BONOS.upper(),
            constants.ASIGNACION_COMISIONES.upper(),
        ]
        _logger.info("Buscando asignaciones (%s) para empleado ID %s", tipos_incluidos, self.employee_id.id)

        try:
            asignaciones = self.env['hr.salary.assignment'].search([
                ('employee_id', '=', self.employee_id.id),
                ('tipo', 'in', tipos_incluidos),
            ])
            _logger.info("✅ Se encontraron %d asignaciones para contrato ID %s", len(asignaciones), self.id)
        except Exception as e:
            _logger.error("Error al buscar asignaciones para contrato %s: %s", self.id, e)
            asignaciones = []

        monto_extra = sum(asignacion.monto for asignacion in asignaciones)
        bruto_total = bruto + monto_extra

        _logger.info(
            "Bruto total para contrato ID %s: salario base %.2f + asignaciones %.2f = %.2f",
            self.id, bruto, monto_extra, bruto_total
        )

        _logger.info(
            "Bruto total %.2f",bruto_total
        )
        return bruto_total

    # Método para calcular la deducción AFP (Administradora de Fondos de Pensiones)
    def calcular_afp(self, bruto=None):
        self.ensure_one()  # Garantiza que el cálculo se realice solo en un solo registro
        if self.wage_type == constants.SERVICIOS_PROFESIONALES:
            _logger.info("Contrato con servicios profesionales, no se aplica AFP.")
            return 0.0

        salario = bruto if bruto is not None else self.get_salario_bruto_total()
        _logger.info("📌 AFP: salario bruto =%s", bruto)
        _logger.info("📌 AFP: salario base para contrato ID %s = %.2f", self.id, salario)

        # Buscar el porcentaje y techo configurado para el empleado
        afp_empleado = self.env['hr.retencion.afp'].search([('tipo', '=', constants.DEDUCCION_EMPLEADO)], limit=1)
        if not afp_empleado:
            # Si no se encuentra configuración para AFP, se registra una advertencia y se retorna 0.0
            _logger.warning("No se encontró configuración AFP para empleado.")
            return 0.0

        _logger.info("Config AFP encontrada: techo=%.2f, porcentaje=%.2f%%", afp_empleado.techo,
                     afp_empleado.porcentaje)

        porcentaje_afp = afp_empleado.porcentaje or 0.0  # Porcentaje de deducción AFP
        techo = afp_empleado.techo or 0.0  # Techo máximo de deducción AFP

        _logger.info(
            "salario %.2f", salario
        )
        # Si hay techo definido (> 0), se aplica como límite para la base de cálculo
        base = min(salario, techo) if techo > 0 else salario
        deduccion = base * (porcentaje_afp / 100.0)  # Cálculo de la deducción AFP
        _logger.info("AFP base calculada = %.2f", base)

        _logger.info(
            "base %.2f", base
        )
        _logger.info(
            "deduccion %.2f", deduccion
        )

        _logger.info("AFP para contrato ID %d: base %.2f * %.2f%% = %.2f", self.id, base, porcentaje_afp, deduccion)
        return deduccion

    # Método para calcular la deducción ISSS (Instituto Salvadoreño del Seguro Social)
    def calcular_isss(self, bruto=None):
        self.ensure_one()  # Garantiza que el cálculo se realice solo en un solo registro
        if self.wage_type == constants.SERVICIOS_PROFESIONALES:
            _logger.info("Contrato con servicios profesionales, no se aplica ISSS.")
            return 0.0

        salario = bruto if bruto is not None else self.get_salario_bruto_total()
        _logger.info("📌 ISSS: salario bruto =%s", bruto)
        _logger.info("📌 ISSS: salario base para contrato ID %s = %.2f", self.id, salario)

        # Buscar la configuración de ISSS para el empleado
        isss_empleado = self.env['hr.retencion.isss'].search([('tipo', '=', constants.DEDUCCION_EMPLEADO)], limit=1)
        if not isss_empleado:
            # Si no se encuentra configuración para ISSS, se registra una advertencia y se retorna 0.0
            _logger.warning("No se encontró configuración ISSS para empleado.")
            return 0.0

        _logger.info("Config ISSS encontrada: techo=%.2f, porcentaje=%.2f%%", isss_empleado.techo,
                     isss_empleado.porcentaje)

        porcentaje = isss_empleado.porcentaje or 0.0  # Porcentaje de deducción ISSS
        techo = isss_empleado.techo or 0.0  # Techo máximo de deducción ISSS

        # Se aplica el techo si está definido
        base = min(salario, techo) if techo > 0 else salario
        deduccion = base * (porcentaje / 100.0)  # Cálculo de la deducción ISSS
        _logger.info("ISSS base calculada = %.2f", base)

        # Registro de la información de la deducción para referencia
        _logger.info("ISSS empleado para contrato ID %d: base %.2f * %.2f%% = %.2f", self.id, base, porcentaje,
                     deduccion)
        return deduccion

    # Método para calcular la deducción de renta del empleado
    def calcular_deduccion_renta(self, bruto=None):
        self.ensure_one()  # Garantiza que el cálculo se realice solo en un solo registro
        _logger.info("Cálculo de deducción de renta iniciado para contrato ID %s", self.id)

        # Si el valor 'bruto' no es proporcionado, se usa el salario del contrato
        salario = bruto if bruto is not None else self.get_salario_bruto_total()
        _logger.info("📌 RENTA: salario bruto =%s", bruto)

        # Si es servicios profesionales: 10% directo
        if self.wage_type == constants.SERVICIOS_PROFESIONALES:
            resultado = salario * 0.10
            _logger.info("Contrato de servicios profesionales: renta fija 10%% sobre %.2f = %.2f", bruto, resultado)
            return resultado

        # Verifica si el contrato tiene definida la frecuencia de pago
        if not self.schedule_pay:
            # Si no tiene definida la frecuencia de pago, se registra una advertencia y se retorna 0.0
            _logger.warning("El contrato no tiene definida la frecuencia de pago.")
            return 0.0

        # Mapeo de las frecuencias de pago a códigos para la tabla de retención de renta
        codigo_mapeo = {
            'monthly': constants.RET_MENSUAL,  # Mensual
            'semi-monthly': constants.RET_QUINCENAL,  # Quincenal(medio mes)
            'weekly': constants.RET_SEMANAL,  # Semanal
        }

        # Se obtiene el código de tabla correspondiente a la frecuencia de pago
        codigo = codigo_mapeo.get(self.schedule_pay)
        _logger.info("Frecuencia de pago: %s → Código tabla: %s", self.schedule_pay, codigo)

        if not codigo:
            # Si no se encuentra un código para la frecuencia de pago, se registra una advertencia y se retorna 0.0
            _logger.warning("No se encontró código de tabla para la frecuencia de pago '%s'", self.schedule_pay)
            return 0.0

        # Buscar la tabla de remuneración gravada según el código
        tabla = self.env['hr.retencion.renta'].search([('codigo', '=', codigo)], limit=1)
        if not tabla:
            # Si no se encuentra la tabla correspondiente, se registra una advertencia y se retorna 0.0
            _logger.warning("No se encontró tabla de remuneración gravada con código '%s'", codigo)
            return 0.0

        # Calcular base imponible restando AFP e ISSS
        afp = self.calcular_afp(bruto=salario)
        isss = self.calcular_isss(bruto=salario)
        # incaf = self.calcular_incaf()
        base_imponible = salario - afp - isss  # - incaf
        _logger.info("Base imponible renta = %.2f - %.2f - %.2f = %.2f", salario, afp, isss, base_imponible)

        # Se itera sobre los tramos de la tabla para determinar el tramo aplicable
        tramos = tabla.tramo_ids.sorted(key=lambda t: t.desde)
        for tramo in tramos:
            # Verificar si la base imponible cae dentro del tramo
            if (not tramo.hasta or base_imponible <= tramo.hasta) and base_imponible >= tramo.desde:
                # Si es así, calcular la deducción de renta basada en el tramo
                exceso = base_imponible - tramo.exceso_sobre
                resultado = tramo.cuota_fija + (exceso * tramo.porcentaje_excedente / 100)
                _logger.info("Deducción de renta calculada: %.2f (tramo aplicado)", resultado)
                return resultado

        # Si no se encuentra un tramo aplicable, se registra un mensaje de información y se retorna 0.0
        _logger.info("No se encontró tramo aplicable para la base imponible.")
        return 0.0

    # Método para calcular el aporte patronal ISSS (empleador)
    def calcular_aporte_patronal(self, tipo, bruto=None):
        """
        Calcula el aporte patronal (ISSS o AFP) según el salario y los techos definidos.
        - tipo: constants.TIPO_DED_ISSS o constants.TIPO_DED_AFP
        - bruto: base opcional. Si no se pasa, usa el salario bruto total del contrato.
        """
        self.ensure_one()
        if self.wage_type == constants.SERVICIOS_PROFESIONALES:
            _logger.info("Contrato con servicios profesionales, no se aplica INCAF.")
            return 0.0

        # ✅ Si me pasaron bruto, usarlo. Si no, calcular salario bruto total del contrato
        salario = bruto if bruto is not None else self.get_salario_bruto_total()
        _logger.info("📌 Aporte patronal: salario bruto =%s", bruto)

        _logger.info("Cálculo de aporte patronal para contrato ID %s. Tipo: %s. Salario base: %.2f", self.id, tipo,
                     salario)

        if tipo == constants.TIPO_DED_ISSS:
            tipo_isss = self.env['hr.retencion.isss'].search([('tipo', '=', constants.DEDUCCION_EMPLEADOR)], limit=1)
            if tipo_isss:
                base = salario if tipo_isss.techo == 0.0 else min(salario, tipo_isss.techo)
                resultado = base * (tipo_isss.porcentaje / 100)
                _logger.info("ISSS Patronal: base=%.2f, porcentaje=%.2f%%, resultado=%.2f", base,
                             tipo_isss.porcentaje * 100, resultado)
                return resultado
            _logger.warning("No se encontró configuración ISSS para empleador.")
            return 0.0
        elif tipo != constants.TIPO_DED_ISSS:  # afp
            tipo_afp = self.env['hr.retencion.afp'].search([('tipo', '=', constants.DEDUCCION_EMPLEADOR)], limit=1)
            if tipo_afp:
                base = salario if tipo_afp.techo == 0.0 else min(salario, tipo_afp.techo)
                resultado = base * (tipo_afp.porcentaje / 100)
                _logger.info("AFP Patronal: base=%.2f, porcentaje=%.2f%%, resultado=%.2f", base,
                             tipo_afp.porcentaje * 100, resultado)
                return resultado
            _logger.warning("No se encontró configuración AFP para empleador.")
            return 0.0

        _logger.warning("Tipo de aporte patronal desconocido o sin configuración.")
        return 0.0

    def calcular_incaf(self, bruto=None):
        """
        Calcula la deducción del INCAF (1% del salario bruto total del empleado),
        solo si la empresa tiene activado el campo 'pago_incaf'.
        Retorna 0.0 si no aplica o si ocurre un error.
        """
        self.ensure_one()
        if self.wage_type == constants.SERVICIOS_PROFESIONALES:
            _logger.info("Contrato con servicios profesionales, no se aplica INCAF.")
            return 0.0

        try:
            empresa = self.company_id or self.employee_id.company_id
            if not empresa or not empresa.pago_incaf:
                _logger.info("Empresa no paga INCAF, se omite deducción para contrato ID %s.", self.id)
                return 0.0

            salario = bruto if bruto is not None else self.get_salario_bruto_total()
            _logger.info("📌 INCAF: salario bruto =%s", bruto)
            _logger.info("📌 INCAF: salario base para contrato ID %s = %.2f", self.id, salario)

            # Buscar la configuración de ISSS para el incaf
            isss_incaf = self.env['hr.retencion.isss'].search([('tipo', '=', constants.DEDUCCION_INCAF)], limit=1)
            if not isss_incaf:
                # Si no se encuentra configuración para INCAF, se registra una advertencia y se retorna 0.0
                _logger.warning("No se encontró configuración INCAF para empleado.")
                return 0.0

            _logger.info("Config INCAF encontrada: porcentaje=%.2f%%", isss_incaf.porcentaje)

            porcentaje = isss_incaf.porcentaje or 0.0  # Porcentaje de deducción INCAF
            resultado = salario * (porcentaje / 100.0)

            _logger.info("INCAF para contrato ID %s: %.2f * 1%% = %.2f", self.id, salario, resultado)
            return resultado

        except Exception as e:
            _logger.error("Error general al calcular INCAF para contrato ID %s: %s", self.id, e)
            return 0.0
