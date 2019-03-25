#!/user/bin/env python2.7

import unittest
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from mock import MagicMock
from accounting import db
from models import Contact, Invoice, Payment, Policy
from utils import PolicyAccounting

"""
#######################################################
Test Suite for Accounting
#######################################################
"""


class TestBillingSchedules(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_agent = Contact('Test Agent', 'Agent')
        cls.test_insured = Contact('Test Insured', 'Named Insured')
        db.session.add(cls.test_agent)
        db.session.add(cls.test_insured)
        db.session.commit()

        cls.policy = Policy('Test Policy', date(2015, 1, 1), 1200)
        db.session.add(cls.policy)
        cls.policy.named_insured = cls.test_insured.id
        cls.policy.agent = cls.test_agent.id
        db.session.commit()

    @classmethod
    def tearDownClass(cls):
        db.session.delete(cls.test_insured)
        db.session.delete(cls.test_agent)
        db.session.delete(cls.policy)
        db.session.commit()

    def setUp(self):
        pass

    def tearDown(self):
        for invoice in self.policy.invoices:
            db.session.delete(invoice)
        db.session.commit()

    def test_annual_billing_schedule(self):
        self.policy.billing_schedule = "Annual"
        # No invoices currently exist
        self.assertFalse(self.policy.invoices)
        # Invoices should be made when the class is initiated
        pa = PolicyAccounting(self.policy.id)
        self.assertEquals(len(self.policy.invoices), 1)
        self.assertEquals(self.policy.invoices[0].amount_due, self.policy.annual_premium)

    def test_monthly_billing_schedule(self):
        self.policy.billing_schedule = "Monthly"
        self.assertFalse(self.policy.invoices)
        pa = PolicyAccounting(self.policy.id)
        self.assertEquals(len(self.policy.invoices), 12)
        self.assertEquals(self.policy.invoices[0].amount_due, self.policy.annual_premium / 12)


class TestReturnAccountBalance(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_agent = Contact('Test Agent', 'Agent')
        cls.test_insured = Contact('Test Insured', 'Named Insured')
        db.session.add(cls.test_agent)
        db.session.add(cls.test_insured)
        db.session.commit()

        cls.policy = Policy('Test Policy', date(2015, 1, 1), 1200)
        cls.policy.named_insured = cls.test_insured.id
        cls.policy.agent = cls.test_agent.id
        db.session.add(cls.policy)
        db.session.commit()

    @classmethod
    def tearDownClass(cls):
        db.session.delete(cls.test_insured)
        db.session.delete(cls.test_agent)
        db.session.delete(cls.policy)
        db.session.commit()

    def setUp(self):
        self.payments = []

    def tearDown(self):
        for invoice in self.policy.invoices:
            db.session.delete(invoice)
        for payment in self.payments:
            db.session.delete(payment)
        db.session.commit()

    def test_annual_on_eff_date(self):
        self.policy.billing_schedule = "Annual"
        pa = PolicyAccounting(self.policy.id)
        self.assertEquals(pa.return_account_balance(date_cursor=self.policy.effective_date), 1200)

    def test_quarterly_on_eff_date(self):
        self.policy.billing_schedule = "Quarterly"
        pa = PolicyAccounting(self.policy.id)
        self.assertEquals(pa.return_account_balance(date_cursor=self.policy.effective_date), 300)

    def test_quarterly_on_last_installment_bill_date(self):
        self.policy.billing_schedule = "Quarterly"
        pa = PolicyAccounting(self.policy.id)
        invoices = Invoice.query.filter_by(policy_id=self.policy.id) \
            .order_by(Invoice.bill_date).all()
        self.assertEquals(pa.return_account_balance(date_cursor=invoices[3].bill_date), 1200)

    def test_quarterly_on_second_installment_bill_date_with_full_payment(self):
        self.policy.billing_schedule = "Quarterly"
        pa = PolicyAccounting(self.policy.id)
        invoices = Invoice.query.filter_by(policy_id=self.policy.id) \
            .order_by(Invoice.bill_date).all()
        self.payments.append(pa.make_payment(contact_id=self.policy.named_insured,
                                             date_cursor=invoices[1].bill_date, amount=600))
        self.assertEquals(pa.return_account_balance(date_cursor=invoices[1].bill_date), 0)


class TestCancellationPolicies(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_agent = Contact('Test Agent', 'Agent')
        cls.test_insured = Contact('Test Insured', 'Named Insured')
        db.session.add(cls.test_agent)
        db.session.add(cls.test_insured)
        db.session.commit()

        cls.policy = Policy('Test Policy', date(2015, 1, 1), 1600)
        cls.policy.named_insured = cls.test_insured.id
        cls.policy.agent = cls.test_agent.id
        cls.policy.billing_schedule = "Quarterly"
        db.session.add(cls.policy)
        db.session.commit()

    @classmethod
    def tearDownClass(cls):
        db.session.delete(cls.test_insured)
        db.session.delete(cls.test_agent)
        db.session.delete(cls.policy)
        db.session.commit()

    def setUp(self):
        self.payments = []

    def tearDown(self):
        for invoice in self.policy.invoices:
            db.session.delete(invoice)
        for payment in self.payments:
            db.session.delete(payment)
        db.session.commit()

    def test_Given_unpaid_policy_When_cancellation_pending_before_cancel_date_Then_not_due_to_cancel(self):
        pa = PolicyAccounting(self.policy.id)
        invoices = Invoice.query.filter_by(policy_id=self.policy.id).order_by(Invoice.bill_date).all()
        self.payments.append(pa.make_payment(contact_id=self.policy.named_insured,
                                             date_cursor=invoices[0].bill_date,
                                             amount=400))

        # evaluation date it's 10 days after due_date
        evaluation_date = invoices[1].due_date + relativedelta(days=10)
        pa.evaluate_cancel = MagicMock(side_effect=pa.evaluate_cancel)
        result = pa.evaluate_cancellation_pending_due_to_non_pay(date_cursor=evaluation_date)
        pa.evaluate_cancel.assert_called_with(evaluation_date)
        self.assertIsNotNone(result)
        self.assertFalse(result)

    def test_Given_unpaid_policy_When_cancellation_pending_past_cancel_date_Then_due_to_cancel(self):
        pa = PolicyAccounting(self.policy.id)
        invoices = Invoice.query.filter_by(policy_id=self.policy.id) \
            .order_by(Invoice.bill_date).all()
        self.payments.append(pa.make_payment(contact_id=self.policy.named_insured,
                                             date_cursor=invoices[0].bill_date, amount=400))

        # evaluation date it's 20 days after due_date
        pa.evaluate_cancel = MagicMock(side_effect=pa.evaluate_cancel)
        evaluation_date = invoices[1].due_date + relativedelta(days=20)
        result = pa.evaluate_cancellation_pending_due_to_non_pay(date_cursor=evaluation_date)
        pa.evaluate_cancel.assert_called_with(evaluation_date)
        self.assertIsNotNone(result)
        self.assertTrue(result)

    def test_Given_paid_policy_after_bill_date_When_paid_before_cancel_date_Then_not_due_to_cancel(self):
        pa = PolicyAccounting(self.policy.id)
        invoices = Invoice.query.filter_by(policy_id=self.policy.id) \
            .order_by(Invoice.bill_date).all()
        self.payments.append(pa.make_payment(contact_id=self.policy.named_insured,
                                             date_cursor=invoices[0].bill_date, amount=400))

        # the policy has been paid 8 days after due date
        self.payments.append(pa.make_payment(contact_id=self.policy.named_insured,
                                             date_cursor=invoices[1].due_date + relativedelta(days=8), amount=400))

        pa.evaluate_cancel = MagicMock(side_effect=pa.evaluate_cancel)
        evaluation_date = invoices[1].due_date + relativedelta(days=20)
        result = pa.evaluate_cancellation_pending_due_to_non_pay(date_cursor=evaluation_date)
        pa.evaluate_cancel.assert_called_with(evaluation_date)
        self.assertIsNotNone(result)
        self.assertFalse(result)

    def test_Given_policy_to_cancel_When_policy_canceled_Then_policy_data_updated(self):
        pa = PolicyAccounting(self.policy.id)
        pa.cancel_policy("underwriting")
        self.assertEqual(pa.policy.status, 'Canceled')
        self.assertEqual(pa.policy.reason,"underwriting")
        self.assertEqual(pa.policy.date_changed, datetime.now().date())



class TestChangingPolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_agent = Contact('Test Agent', 'Agent')
        cls.test_insured = Contact('Test Insured', 'Named Insured')
        db.session.add(cls.test_agent)
        db.session.add(cls.test_insured)
        db.session.commit()

        cls.policy = Policy('Test Policy', date(2015, 1, 1), 1600)
        cls.policy.named_insured = cls.test_insured.id
        cls.policy.agent = cls.test_agent.id
        db.session.add(cls.policy)
        db.session.commit()

    @classmethod
    def tearDownClass(cls):
        db.session.rollback()
        db.session.delete(cls.test_insured)
        db.session.delete(cls.test_agent)
        db.session.delete(cls.policy)
        db.session.commit()
        pass

    def setUp(self):
        self.payments = []

    def tearDown(self):
        for invoice in self.policy.invoices:
            db.session.delete(invoice)
        for payment in self.payments:
            db.session.delete(payment)
        db.session.commit()

    def test_Given_policy_When_policy_is_changed_Then_old_policy_marked_deleted(self):
        self.policy.billing_schedule = 'Quarterly'
        pa = PolicyAccounting(self.policy.id)
        result = pa.change_policy(schedule='Monthly', date_cursor=date(2015, 3, 1))
        invoices = Invoice.query.filter_by(policy_id=self.policy.id) \
            .filter(Invoice.bill_date < date(2015, 3, 1)) \
            .order_by(Invoice.bill_date).all()
        for invoice in invoices:
            self.assertTrue(invoice.deleted)

    def test_Given_policy_When_policy_is_changed_Then_invoices_are_added(self):
        self.policy.billing_schedule = 'Quarterly'
        pa = PolicyAccounting(self.policy.id)
        already_paid_amount = 400
        self.payments.append(pa.make_payment(contact_id=self.policy.named_insured,
                                             date_cursor=date(2015, 1, 1), amount=already_paid_amount))
        expected_amount_due = (self.policy.annual_premium - already_paid_amount) / 9

        result = pa.change_policy(schedule='Monthly', date_cursor=date(2015, 3, 1))

        invoices = Invoice.query.filter_by(policy_id=self.policy.id) \
            .filter(Invoice.deleted != True) \
            .order_by(Invoice.bill_date).all()

        total_invoices_for_the_policy = 9
        self.assertEqual(total_invoices_for_the_policy, len(invoices))

        invoice_count = 0
        for invoice in filter(lambda x: x.bill_date >= date(2015, 3, 1) or x.deleted == True, invoices):
            invoice_count += 1
            self.assertEqual(expected_amount_due, invoice.amount_due)

        number_of_invoices_with_new_price = 9
        self.assertEqual(number_of_invoices_with_new_price, invoice_count)

    def test_Given_policy_When_policy_is_changed_Then_data_is_consistent(self):
        self.policy.billing_schedule = 'Quarterly'
        pa = PolicyAccounting(self.policy.id)

        result = pa.change_policy(schedule='Monthly', date_cursor=date(2015, 3, 1))

        self.assertEqual(self.test_insured.id, result.named_insured)
        self.assertEqual(self.test_agent.id, result.agent)
        self.assertEqual('Monthly', self.policy.billing_schedule)