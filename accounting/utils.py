#!/user/bin/env python2.7

from datetime import date, datetime
from dateutil.relativedelta import relativedelta

from accounting import db
from models import Contact, Invoice, Payment, Policy

import logging
logging.basicConfig(level=logging.DEBUG)


logger = logging.getLogger(__name__)

handler = logging.FileHandler('accounting.log')
format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(format)
logger.addHandler(handler)

"""
#######################################################
This is the base code for the engineer project.
#######################################################
"""

class PolicyAccounting(object):
    """
     Each policy has its own instance of accounting.
    """
    def __init__(self, policy_id):
        self.policy = Policy.query.filter_by(id=policy_id).one()
        self.billing_schedules = {'Annual': 1, 'Two-Pay': 2, 'Quarterly': 4, 'Monthly': 12}
        self.scheduling_interval = {'Annual': 1,'Two-Pay': 6, 'Quarterly': 3, 'Monthly': 1}

        if not self.policy.invoices:
            self.make_invoices()

    def return_account_balance(self, date_cursor=None):
        if not date_cursor:
            date_cursor = datetime.now().date()

        # get the list of invoices for this policy up to the date passed in
        invoices = Invoice.query.filter_by(policy_id=self.policy.id)\
                                .filter(Invoice.bill_date <= date_cursor)\
                                .order_by(Invoice.bill_date)\
                                .all()

        # calculate the amount due for this policy up to the date passed in
        due_now = 0
        for invoice in invoices:
            due_now += invoice.amount_due

        logger.debug("Invoices up to date %s: %d",date_cursor, len(invoices))
        logger.debug("Amount due: %d", due_now)
        # get the list of payments made on this policy up to the date passed in
        payments = Payment.query.filter_by(policy_id=self.policy.id)\
                                .filter(Payment.transaction_date <= date_cursor)\
                                .all()

        # remove the amount already paid from the amount due
        for payment in payments:
            logger.debug("Found payment of: %d", payment.amount_paid)
            due_now -= payment.amount_paid

        logger.debug("Amount due: %d", due_now)
        # return the amount due for this policy
        return due_now

    def make_payment(self, contact_id=None, date_cursor=None, amount=0):
        if not date_cursor:
            date_cursor = datetime.now().date()

        if not contact_id:
            try:
                contact_id = self.policy.named_insured
            except:
                db.session.rollback()

        # create payment for this policy
        payment = Payment(self.policy.id,
                          contact_id,
                          amount,
                          date_cursor)
        db.session.add(payment)
        db.session.commit()

        logger.debug("Created payment => policy: %s / contact_id: %s / amount %d / date: %s", self.policy.id, contact_id, amount, date_cursor)
        return payment

    def evaluate_cancellation_pending_due_to_non_pay(self, date_cursor=None):
        """
         If this function returns true, an invoice
         on a policy has passed the due date without
         being paid in full. However, it has not necessarily
         made it to the cancel_date yet.
        """
        if not date_cursor:
            date_cursor = datetime.now().date()

        if self.evaluate_cancel(date_cursor):
            return True

        return False

    def evaluate_cancel(self, date_cursor=None):
        if not date_cursor:
            date_cursor = datetime.now().date()

        # gets all the invoices with the cancel date up to the date passed in
        invoices = Invoice.query.filter_by(policy_id=self.policy.id)\
                                .filter(Invoice.cancel_date <= date_cursor)\
                                .order_by(Invoice.bill_date)\
                                .all()

        # if there is any amount left to pay, tell that the policy should be canceled
        for invoice in invoices:
            if not self.return_account_balance(invoice.cancel_date):
                continue
            else:
                print "THIS POLICY SHOULD HAVE CANCELED"
                return True
        else:
            print "THIS POLICY SHOULD NOT CANCEL"
            return False


    def make_invoices(self):
        for invoice in self.policy.invoices:
            invoice.delete()

        invoices = []

        if self.policy.billing_schedule in self.scheduling_interval:
            for i in range(0, self.billing_schedules.get(self.policy.billing_schedule)):
                months_after_eff_date = i * self.scheduling_interval[self.policy.billing_schedule]
                bill_date = self.policy.effective_date + relativedelta(months=months_after_eff_date)

                logger.debug(
                    "Creating [%s] Invoice => policy_id: %s / bill_date: %s / due_date: %s / cancel_date: %s / amount_due: %s",
                    self.policy.billing_schedule,
                    self.policy.id,
                    bill_date,
                    bill_date + relativedelta(months=1),
                    bill_date + relativedelta(months=1, days=14),
                    self.policy.annual_premium / self.billing_schedules.get(self.policy.billing_schedule))

                invoice = Invoice(self.policy.id,
                                  bill_date,
                                  bill_date + relativedelta(months=1),
                                  bill_date + relativedelta(months=1, days=14),
                                  self.policy.annual_premium / self.billing_schedules.get(self.policy.billing_schedule))
                invoices.append(invoice)
        elif self.policy.billing_schedule == "Annual":
            pass
        else:
            print "You have chosen a bad billing schedule."

        for invoice in invoices:
            db.session.add(invoice)
        db.session.commit()

################################
# The functions below are for the db and 
# shouldn't need to be edited.
################################
def build_or_refresh_db():
    db.drop_all()
    db.create_all()
    insert_data()
    print "DB Ready!"

def insert_data():
    #Contacts
    contacts = []
    john_doe_agent = Contact('John Doe', 'Agent')
    contacts.append(john_doe_agent)
    john_doe_insured = Contact('John Doe', 'Named Insured')
    contacts.append(john_doe_insured)
    bob_smith = Contact('Bob Smith', 'Agent')
    contacts.append(bob_smith)
    anna_white = Contact('Anna White', 'Named Insured')
    contacts.append(anna_white)
    joe_lee = Contact('Joe Lee', 'Agent')
    contacts.append(joe_lee)
    ryan_bucket = Contact('Ryan Bucket', 'Named Insured')
    contacts.append(ryan_bucket)

    for contact in contacts:
        db.session.add(contact)
    db.session.commit()

    policies = []
    p1 = Policy('Policy One', date(2015, 1, 1), 365)
    p1.billing_schedule = 'Annual'
    p1.agent = bob_smith.id
    policies.append(p1)

    p2 = Policy('Policy Two', date(2015, 2, 1), 1600)
    p2.billing_schedule = 'Quarterly'
    p2.named_insured = anna_white.id
    p2.agent = joe_lee.id
    policies.append(p2)

    p3 = Policy('Policy Three', date(2015, 1, 1), 1200)
    p3.billing_schedule = 'Monthly'
    p3.named_insured = ryan_bucket.id
    p3.agent = john_doe_agent.id
    policies.append(p3)

    for policy in policies:
        db.session.add(policy)
    db.session.commit()

    for policy in policies:
        PolicyAccounting(policy.id)

    payment_for_p2 = Payment(p2.id, anna_white.id, 400, date(2015, 2, 1))
    db.session.add(payment_for_p2)
    db.session.commit()

