import logging

_logger = logging.getLogger(__name__)
# migrations/18.0.1.1/post-migration.py
def migrate(cr, version):
    # FALSE → NULL (solo cambia los False actuales)
    _logger.info("SIT version = %s", version)
    cr.execute("""
        UPDATE res_company
           SET sit_facturacion = FALSE
         WHERE sit_facturacion IS NULL
    """)
