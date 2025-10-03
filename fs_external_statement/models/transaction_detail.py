from odoo import api, fields, models
from odoo.exceptions import UserError


class TransactionDetail(models.Model):
    _name = "transaction.detail"
    _description = "Detalles de Transacciones"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'operation_date desc, id desc'

    # Campos Base
    name = fields.Char(
        string='Referencia',
        related='settlement_header_id.name',
        help="Referencia de la transacción"
    )
    product = fields.Char(
        related='settlement_header_id.product',
        string='Código del Producto',
        store=True,
        help="Código de producto de la transacción"
    )
    journal_id = fields.Many2one(
        'account.journal',
        related='settlement_header_id.journal_id',
        string='Diario',
        store=True,
        help="Diario contable asociado a la transacción"
    )
    settlement_number = fields.Char(
        string='Número de Liquidación',
        related='settlement_header_id.settlement_number',
        index=True,
        store=True,
        help="Número de liquidación al que pertenece la transacción"
    )
    operation_date = fields.Date(
        string='Fecha de la operación',
        required=True,
        tracking=True,
        help="Fecha de la operación"
    )
    cover_terminal_posnet = fields.Integer(
        string='Número de terminal POS',
        size=9,
        tracking=True,
        help="Número de terminal POS"
    )
    summary_lot_posnet = fields.Integer(
        string='Número de lote',
        size=3,
        tracking=True,
        help="Número de lote del resumen"
    )
    coupon_posnet = fields.Integer(
        string='Número de cupón',
        size=5,
        tracking=True,
        help="Número de cupón"
    )
    total = fields.Float(
        string='Monto total',
        digits=(16, 2),
        tracking=True,
        help="Monto total de la transacción"
    )
    card_number = fields.Char(
        string='Numero de tarjeta',
        size=19,
        tracking=True,
        help="Número de tarjeta"
    )
    processed = fields.Boolean(
        string='Processed',
        default=False,
        tracking=True,
        help="Indica si la transacción ha sido procesada"
    )

    # -------------------------------------- Relaciones --------------------------------------
    settlement_header_id = fields.Many2one(
        'settlement.header',
        string='Cabecera de Liquidación',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True
    )

    # -------------------------------------- Campos calculados y relacionados --------------------------------------
    external_statement_payment_method_description = fields.Char(
        string='Método de Pago',
        related='settlement_header_id.external_statement_payment_method_description',
        store=True,
        help="Descripción del método de pago del Extracto Bancario Externo"
    )

