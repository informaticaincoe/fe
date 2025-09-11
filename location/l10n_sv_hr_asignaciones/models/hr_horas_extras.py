from odoo import models, fields, api, _
import logging
import traceback
_logger = logging.getLogger(__name__)

class HrHorasExtras(models.Model):
    _name = 'hr.horas.extras'
    _description = 'Horas extras'

    salary_assignment_id = fields.Many2one(
        'hr.salary.assignment',
        string='Asignación salarial',
        ondelete='cascade'
    )

    horas_diurnas = fields.Char("Horas extras diurnas",required=False)
    horas_nocturnas = fields.Char("Horas extras nocturnas", required=False)
    horas_diurnas_descanso = fields.Char("Horas extras diurnas en descanso", required=False)
    horas_nocturnas_descanso = fields.Char("Horas extras nocturnas en descanso", required=False)
    horas_diurnas_asueto = fields.Char("Horas extras diurnas asueto", required=False)
    horas_nocturnas_asueto = fields.Char("Horas extras nocturnas asueto", required=False)
    descripcion = fields.Char("Descripción", required=False)

    def _parse_horas(self, valor):
        """
        Convierte un valor de horas a decimal.
        Escenarios cubiertos:
            - None, False, "", "   " -> 0.0
            - Float o int -> se devuelve tal cual
            - String decimal con punto o coma -> se normaliza
            - String HH:MM -> se convierte a decimal
            - Valores con letras como '7h 10m' -> se intenta extraer HH y MM
            - Valores inválidos -> 0.0
        """
        if self.salary_assignment_id:
            return self.salary_assignment_id._parse_horas(valor)

        if valor in (None, False, "") or str(valor).strip() == "":
            return 0.0

        # Normalizar string
        valor_str = str(valor).strip().replace(',', '.')  # cambiar coma por punto

        # Si ya es float o int
        if isinstance(valor, (int, float)):
            return round(float(valor), 2)

        # Si contiene ":" -> formato HH:MM
        if ":" in valor_str:
            try:
                h, m = map(int, valor_str.split(":"))
                return round(h + m / 60, 2)
            except Exception:
                _logger.warning("Valor de horas inválido (HH:MM): %s", valor_str)
                return 0.0

        # Intentar detectar formato tipo '7h 10m'
        import re
        match = re.match(r"(?P<h>\d+)[hH]?\s*(?P<m>\d+)?[mM]?", valor_str)
        if match:
            h = int(match.group("h"))
            m = int(match.group("m") or 0)
            return round(h + m / 60, 2)

        # Intentar convertir a float directamente
        try:
            return round(float(valor_str), 2)
        except Exception:
            _logger.warning("Valor de horas no reconocido: %s", valor_str)
            return 0.0

    def write(self, vals):
        res = super().write(vals)
        self._notify_parent_recompute()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._notify_parent_recompute()
        return records

    def _notify_parent_recompute(self):
        try:
            for record in self:
                asignacion = record.salary_assignment_id
                if asignacion:
                    _logger.info("Recomputando asignación ID=%s para empleado: %s", asignacion.id,
                                 asignacion.employee_id.name)

                    horas_totales = {
                        'horas_diurnas': 0.0,
                        'horas_nocturnas': 0.0,
                        'horas_diurnas_descanso': 0.0,
                        'horas_nocturnas_descanso': 0.0,
                        'horas_diurnas_asueto': 0.0,
                        'horas_nocturnas_asueto': 0.0
                    }

                    for linea in asignacion.horas_extras_ids:
                        _logger.debug("Procesando línea ID=%s para asignación ID=%s", linea.id, asignacion.id)
                        horas_totales['horas_diurnas'] += linea._parse_horas(linea.horas_diurnas)
                        horas_totales['horas_nocturnas'] += linea._parse_horas(linea.horas_nocturnas)
                        horas_totales['horas_diurnas_descanso'] += linea._parse_horas(linea.horas_diurnas_descanso)
                        horas_totales['horas_nocturnas_descanso'] += linea._parse_horas(linea.horas_nocturnas_descanso)
                        horas_totales['horas_diurnas_asueto'] += linea._parse_horas(linea.horas_diurnas_asueto)
                        horas_totales['horas_nocturnas_asueto'] += linea._parse_horas(linea.horas_nocturnas_asueto)

                    _logger.info("Totales horas extra para asignación ID=%s: %s", asignacion.id, horas_totales)

                    nuevo_monto = asignacion._calcular_monto_horas_extras(asignacion.employee_id, horas_totales)
                    _logger.info("Nuevo monto calculado: %.2f (Asignación ID=%s)", nuevo_monto, asignacion.id)

                    asignacion.monto = nuevo_monto
        except Exception as e:
            _logger.error("Error procesando descripción: %s", traceback.format_exc())
            raise