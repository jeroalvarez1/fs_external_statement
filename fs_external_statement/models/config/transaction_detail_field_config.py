from email.policy import default

from odoo import api, fields, models

class TransactionDetailFieldConfig(models.Model):
    _name = "transaction.detail.field.config"

    name = fields.Char(compute='_compute_name', string='Nombre')
    transaction_detail_config_id = fields.Many2one(
        'transaction.detail.config',
        string='Configuración del Detalle de Transacción',
        required=True,
        ondelete='cascade'
    )
    destination_field_id = fields.Many2one(
        'ir.model.fields',
        domain=[('model_id.model', '=', 'transaction.detail')],
        string='Campo de destino',
        required=True
    )

    search_type = fields.Selection(
        related='transaction_detail_config_id.search_type', string='Tipo de búsqueda', store=True
    )

    # Sirve para excel y txt
    start_with = fields.Char(string='Caracter de comienzo de linea')
    starting_position = fields.Integer(string='Posición inicial en extracto (.txt)')
    end_position = fields.Integer(string='Posición final en el extracto (.txt)')

    # Campos para .csv, xsl y xlsx
    row = fields.Integer(string='Fila')  # TODO: SOLO SI ES LIQUIDATION NUMBER Y fixed
    col = fields.Integer(string='Columna')

    is_liquidation_number = fields.Boolean(string='Es el numero de liquidación', default=False)
    liquidation_type = fields.Selection([('row', 'En filas'), ('fixed', 'Fijo')])

    origin_date_format = fields.Char(string='Formato de Origen')
    dest_date_format = fields.Char(string='Formato de Destino')

    @api.depends('destination_field_id')
    def _compute_name(self):
        for record in self:
            record.name = record.destination_field_id.name if record.destination_field_id else False

    @api.onchange('search_type')
    def _onchange_search_type(self):
        for record in self:
            # Limpiar campos que no aplican
            record.start_with = False
            record.starting_position = False
            record.end_position = False
            record.col = False
            record.is_liquidation_number = False
            record.group_by = False
            record.origin_date_format = False
            record.dest_date_format = False

            if record.search_type == 'excel_init_with_date':
                record.origin_date_format = '%Y-%m-%dT%H:%M:%S.%f%z'
                record.dest_date_format = '%Y-%m-%d'
