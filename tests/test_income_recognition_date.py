# -*- coding: utf-8 -*-

from odoo.tests.common import TransactionCase, tagged
from odoo import fields
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "income_recognition")
class TestIncomeRecognitionDate(TransactionCase):
    """Test cases for income_recognition_date computation logic"""

    @classmethod
    def setUpClass(cls):
        super(TestIncomeRecognitionDate, cls).setUpClass()

    def setUp(self):
        super(TestIncomeRecognitionDate, self).setUp()

        # Create test customer
        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Customer",
                "country_id": self.env.ref("base.cl").id,
            }
        )

        # Create test product
        self.product = self.env["product.product"].create(
            {
                "name": "Test Product",
                "type": "service",
                "list_price": 1000.0,
                "invoice_policy": "order",
            }
        )

        # Get stages
        self.planning_stage = self.env.ref(
            "kvz_backlog.block_stage_002", raise_if_not_found=False
        )
        self.provisioned_stage = self.env.ref(
            "kvz_backlog.block_stage_005", raise_if_not_found=False
        )
        self.invoiced_stage = self.env.ref(
            "kvz_backlog.block_stage_006", raise_if_not_found=False
        )

        # Create dates for testing
        self.today = fields.Date.today()
        self.yesterday = self.today - timedelta(days=1)
        self.two_days_ago = self.today - timedelta(days=2)
        self.three_days_ago = self.today - timedelta(days=3)

    def _create_sale_order_with_line(self, date_deadline=None):
        """Helper to create a sale order with one line"""
        sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
            }
        )

        order_line = self.env["sale.order.line"].create(
            {
                "order_id": sale_order.id,
                "product_id": self.product.id,
                "product_uom_qty": 1.0,
                "price_unit": 1000.0,
            }
        )

        sale_order.action_confirm()

        # Set date_deadline via write() to simulate how project_milestone sets it
        # This ensures the @api.depends decorator triggers properly
        if date_deadline is not False:
            order_line.write({"date_deadline": date_deadline or self.today})

        return sale_order, order_line

    def _invoice_sale_order(self, sale_order, invoice_date=None):
        """Helper to create and post an invoice for a sale order"""
        # Create invoice
        invoice = sale_order._create_invoices()

        # Set invoice date if provided
        if invoice_date:
            invoice.invoice_date = invoice_date

        # Set Chilean DTE status
        invoice.l10n_cl_dte_status = "accepted"

        # Post the invoice
        invoice.action_post()

        return invoice

    def test_01_initial_date_from_deadline(self):
        """Test that income_recognition_date initially equals date_deadline"""
        _logger.info("TEST 1: Initial date from deadline")

        # Create sale order line with specific deadline
        deadline = self.three_days_ago
        sale_order, order_line = self._create_sale_order_with_line(
            date_deadline=deadline
        )

        # Check that income_recognition_date equals date_deadline
        self.assertEqual(
            order_line.income_recognition_date,
            deadline,
            "Income recognition date should initially equal date_deadline",
        )

        _logger.info(
            f"✓ Initial income_recognition_date correctly set to date_deadline: {deadline}"
        )

    def test_02_no_dates_keeps_deadline(self):
        """Test that without invoice or provision dates, deadline is kept"""
        _logger.info("TEST 2: No dates keeps deadline")

        deadline = self.two_days_ago
        sale_order, order_line = self._create_sale_order_with_line(
            date_deadline=deadline
        )

        # Move to planning stage (no provision date set)
        if self.planning_stage:
            order_line.backlog_state_id = self.planning_stage.id
            order_line.bklg_state = "planning"

        # Force recomputation
        order_line._compute_income_recognition_date()

        # Should still be date_deadline
        self.assertEqual(
            order_line.income_recognition_date,
            deadline,
            "Without invoice or provision dates, should keep date_deadline",
        )

        _logger.info(
            f"✓ Income recognition date correctly kept as deadline: {deadline}"
        )

    def test_03_only_invoice_date(self):
        """Test using only invoice date when provision date doesn't exist"""
        _logger.info("TEST 3: Only invoice date")

        deadline = self.three_days_ago
        invoice_date = self.yesterday
        sale_order, order_line = self._create_sale_order_with_line(
            date_deadline=deadline
        )

        # Create and post invoice with specific date
        invoice = self._invoice_sale_order(sale_order, invoice_date=invoice_date)

        # Force recomputation
        order_line._compute_income_recognition_date()

        # Should use invoice date
        self.assertEqual(
            order_line.income_recognition_date,
            invoice_date,
            "Should use invoice_date when it's the only available date",
        )

        _logger.info(
            f"✓ Income recognition date correctly set to invoice_date: {invoice_date}"
        )

    def test_04_only_provision_date(self):
        """Test using only provision date when invoice doesn't exist"""
        _logger.info("TEST 4: Only provision date")

        deadline = self.three_days_ago
        sale_order, order_line = self._create_sale_order_with_line(
            date_deadline=deadline
        )

        # Set provision date manually
        provision_datetime = datetime.combine(self.yesterday, datetime.min.time())
        order_line.write(
            {
                "backlog_state_id": self.provisioned_stage.id,
                "bklg_state": "provisioned",
                "initial_provisioned_amount": 1000.0,
                "initial_provisioned_amount_datetime": provision_datetime,
            }
        )

        # Force recomputation
        order_line._compute_income_recognition_date()

        # Should use provision date (date part only)
        expected_date = provision_datetime.date()
        self.assertEqual(
            order_line.income_recognition_date,
            expected_date,
            "Should use provision date when it's the only available date",
        )

        _logger.info(
            f"✓ Income recognition date correctly set to provision date: {expected_date}"
        )

    def test_05_earliest_of_both_dates_invoice_earlier(self):
        """Test using earliest date when both exist - invoice earlier"""
        _logger.info("TEST 5: Earliest of both dates (invoice earlier)")

        deadline = self.three_days_ago
        invoice_date = self.two_days_ago  # Earlier
        provision_date = self.yesterday  # Later
        sale_order, order_line = self._create_sale_order_with_line(
            date_deadline=deadline
        )

        # Set provision date
        provision_datetime = datetime.combine(provision_date, datetime.min.time())
        order_line.write(
            {
                "backlog_state_id": self.provisioned_stage.id,
                "bklg_state": "provisioned",
                "initial_provisioned_amount": 1000.0,
                "initial_provisioned_amount_datetime": provision_datetime,
            }
        )

        # Create and post invoice with earlier date
        invoice = self._invoice_sale_order(sale_order, invoice_date=invoice_date)

        # Force recomputation
        order_line._compute_income_recognition_date()

        # Should use the earlier invoice date
        self.assertEqual(
            order_line.income_recognition_date,
            invoice_date,
            "Should use earliest date (invoice_date) when both exist",
        )

        _logger.info(
            f"✓ Income recognition date correctly set to earliest date (invoice): {invoice_date}"
        )

    def test_06_earliest_of_both_dates_provision_earlier(self):
        """Test using earliest date when both exist - provision earlier"""
        _logger.info("TEST 6: Earliest of both dates (provision earlier)")

        deadline = self.three_days_ago
        provision_date = self.two_days_ago  # Earlier
        invoice_date = self.yesterday  # Later
        sale_order, order_line = self._create_sale_order_with_line(
            date_deadline=deadline
        )

        # Set provision date (earlier)
        provision_datetime = datetime.combine(provision_date, datetime.min.time())
        order_line.write(
            {
                "backlog_state_id": self.provisioned_stage.id,
                "bklg_state": "provisioned",
                "initial_provisioned_amount": 1000.0,
                "initial_provisioned_amount_datetime": provision_datetime,
            }
        )

        # Create and post invoice with later date
        invoice = self._invoice_sale_order(sale_order, invoice_date=invoice_date)

        # Force recomputation
        order_line._compute_income_recognition_date()

        # Should use the earlier provision date
        self.assertEqual(
            order_line.income_recognition_date,
            provision_date,
            "Should use earliest date (provision_date) when both exist",
        )

        _logger.info(
            f"✓ Income recognition date correctly set to earliest date (provision): {provision_date}"
        )

    def test_07_same_dates(self):
        """Test when invoice date and provision date are the same"""
        _logger.info("TEST 7: Same invoice and provision dates")

        deadline = self.three_days_ago
        same_date = self.yesterday
        sale_order, order_line = self._create_sale_order_with_line(
            date_deadline=deadline
        )

        # Set provision date
        provision_datetime = datetime.combine(same_date, datetime.min.time())
        order_line.write(
            {
                "backlog_state_id": self.provisioned_stage.id,
                "bklg_state": "provisioned",
                "initial_provisioned_amount": 1000.0,
                "initial_provisioned_amount_datetime": provision_datetime,
            }
        )

        # Create invoice with same date
        invoice = self._invoice_sale_order(sale_order, invoice_date=same_date)

        # Force recomputation
        order_line._compute_income_recognition_date()

        # Should use the same date
        self.assertEqual(
            order_line.income_recognition_date,
            same_date,
            "Should correctly handle when both dates are the same",
        )

        _logger.info(
            f"✓ Income recognition date correctly set when dates are equal: {same_date}"
        )

    def test_08_automatic_recomputation_on_invoice(self):
        """Test that field recomputes automatically when invoice is created"""
        _logger.info("TEST 8: Automatic recomputation on invoice")

        deadline = self.three_days_ago
        invoice_date = self.yesterday
        sale_order, order_line = self._create_sale_order_with_line(
            date_deadline=deadline
        )

        # Initially should be deadline
        self.assertEqual(order_line.income_recognition_date, deadline)

        # Create invoice (should trigger automatic recomputation)
        invoice = self._invoice_sale_order(sale_order, invoice_date=invoice_date)

        # Should automatically update to invoice date
        self.assertEqual(
            order_line.income_recognition_date,
            invoice_date,
            "Field should recompute automatically when invoice is posted",
        )

        _logger.info(
            f"✓ Field automatically recomputed on invoice posting: {invoice_date}"
        )

    def test_09_automatic_recomputation_on_provision(self):
        """Test that field recomputes automatically when provision date is set"""
        _logger.info("TEST 9: Automatic recomputation on provision")

        deadline = self.three_days_ago
        provision_date = self.yesterday
        sale_order, order_line = self._create_sale_order_with_line(
            date_deadline=deadline
        )

        # Initially should be deadline
        self.assertEqual(order_line.income_recognition_date, deadline)

        # Set provision date (should trigger automatic recomputation)
        provision_datetime = datetime.combine(provision_date, datetime.min.time())
        order_line.write(
            {
                "backlog_state_id": self.provisioned_stage.id,
                "bklg_state": "provisioned",
                "initial_provisioned_amount": 1000.0,
                "initial_provisioned_amount_datetime": provision_datetime,
            }
        )

        # Should automatically update to provision date
        self.assertEqual(
            order_line.income_recognition_date,
            provision_date,
            "Field should recompute automatically when provision date is set",
        )

        _logger.info(
            f"✓ Field automatically recomputed on provision: {provision_date}"
        )

    def test_10_deadline_none_handles_gracefully(self):
        """Test that None deadline is handled gracefully"""
        _logger.info("TEST 10: Handle None deadline gracefully")

        # Create order line without deadline
        sale_order, order_line = self._create_sale_order_with_line(date_deadline=False)

        # Should handle None gracefully
        self.assertFalse(
            order_line.income_recognition_date,
            "Should handle None deadline gracefully",
        )

        # Add invoice date
        invoice_date = self.yesterday
        invoice = self._invoice_sale_order(sale_order, invoice_date=invoice_date)

        # Should now use invoice date
        self.assertEqual(
            order_line.income_recognition_date,
            invoice_date,
            "Should use invoice_date when deadline is None",
        )

        _logger.info(f"✓ Correctly handled None deadline, used invoice_date")
