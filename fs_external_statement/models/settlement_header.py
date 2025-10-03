from odoo import api, fields, models
from odoo.exceptions import UserError


class SettlementHeader(models.Model):
    _name = "settlement.header"
    _description = "Cabecera de Liquidaciones"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'settlement_number, id'

    # Campos Base
    name = fields.Char(
        string='Referencia de Archivo',
        required=True,
        size=6,
        tracking=True
    )
    product = fields.Char(
        string='Código de Producto',
        size=1,
        tracking=True,
        help="Código de producto de la liquidación"
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Diario',
        required=True,
        domain="[('type', 'in', ['bank', 'cash'])]",
        tracking=True
    )
    settlement_number = fields.Char(
        string='Número de Liquidación',
        required=True,
        tracking=True,
        index=True,
        help="Número único de liquidación"
    )
    state = fields.Selection(
        [('draft', 'Borrador'), ('partial', 'En proceso'), ('processed', 'Realizado')],
        string='Estado', default='draft', tracking=True, index=True, compute='_compute_state', store=True
    )

    # Campos Relaciones
    trade_header_id = fields.Many2one(
        'trade.header',
        string='Cabecera de Comercio',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True
    )
    transaction_detail_ids = fields.One2many(
        'transaction.detail',
        'settlement_header_id',
        string='Detalles de Transacciones',
        ondelete='restrict',
        copy=False
    )
    settlement_trailer_tax_ids = fields.One2many(
        'settlement.trailer.tax',
        'settlement_header_id',
        string='Trailers de Liquidación',
        copy=False
    )

    # Campos Calculados
    total_amount = fields.Float(
        string='Monto Total',
        compute='_compute_totals',
        store=True,
        digits=(16, 2)
    )
    external_statement_payment_method_description = fields.Char(
        string='Metodo de Pago',
        compute='_compute_external_statement_payment_method_description',
        store=True
    )
    transactions_count = fields.Integer(
        string='Cantidad de Transacciones',
        compute='_compute_transactions_count',
        store=True
    )

    # Metodos Base
    def unlink(self):
        """
        Sobre escritura del metodo 'unlink', valida que no se pueda borrar el registro si el estado del mismo es
        distinto a 'Borrador'
        """
        for record in self:
            if record.state != 'draft':
                raise UserError(
                    'No se puede eliminar una "Cabecera de liquidación" que el estado sea distinto de "Borrador"'
                )
        return super().unlink()

    # Métodos Depends
    @api.depends('transaction_detail_ids', 'transaction_detail_ids.total')
    def _compute_totals(self):
        """Calcula el monto total de los 'Detalles de transacción'  relacionados"""
        for record in self:
            record.total_amount = sum(record.transaction_detail_ids.mapped('total'))

    @api.depends('transaction_detail_ids')
    def _compute_transactions_count(self):
        """Calcula el número de transacciones"""
        for record in self:
            record.transactions_count = len(record.transaction_detail_ids)

    @api.depends('transaction_detail_ids', 'transaction_detail_ids.processed')
    def _compute_state(self):
        """Calcula el estado basado en las transacciones"""
        for record in self:
            if not record.transaction_detail_ids:
                record.state = 'draft'
            elif all(tx.processed for tx in record.transaction_detail_ids):
                record.state = 'processed'
            elif any(tx.processed for tx in record.transaction_detail_ids):
                record.state = 'partial'
            else:
                record.state = 'draft'

    @api.depends('product')
    def _compute_external_statement_payment_method_description(self):
        """Obtiene la descripción del metodo de pago de extractos bancarios externos"""
        for record in self:
            if record.product:
                method = self.env['external.statement.payment.methods'].search([
                    ('name', '=', record.product)
                ], limit=1)
                record.external_statement_payment_method_description = method.description if method else ''
            else:
                record.external_statement_payment_method_description = ''

    # Metodos Acciones
    def action_view_transaction_detail(self):
        """Acción para ver las transacciones relacionadas"""
        self.ensure_one()
        return {
            'name': 'Detalles de Transacciones',
            'view_mode': 'tree,form',
            'res_model': 'transaction.detail',
            'type': 'ir.actions.act_window',
            'domain': [('settlement_header_id', '=', self.id)],
            'context': {'default_settlement_header_id': self.id, 'group_by': 'journal_id'}
        }
