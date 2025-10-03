from odoo import api, fields, models


class TradeHeaderFieldConfig(models.Model):
    _name = "trade.header.field.config"

    name = fields.Char(compute='_compute_name', string='Nombre')
    trade_header_config_id = fields.Many2one(
        'trade.header.config',
        string='Configuración de Detalle de Transacción',
    )
    destination_field_id = fields.Many2one(
        'ir.model.fields',
        domain=[('model_id.model', '=', 'trade.header')],
        string='Campo de destino',
        required=True
    )

    # Campos para .txt
    start_with = fields.Char(
        string='Caracter de comienzo de linea (.txt)'
    )
    line_number = fields.Integer(
        string='Numero de linea (.txt)'
    )
    starting_position = fields.Integer(string='Posición inicial en extracto (.txt)')
    end_position = fields.Integer(string='Posición final en el extracto (.txt)')

    # Campos para .csv, xsl y xlsx
    row = fields.Integer(string='Fila')
    col = fields.Integer(string='Columna')

    @api.depends('destination_field_id')
    def _compute_name(self):
        for record in self:
            record.name = record.destination_field_id.name