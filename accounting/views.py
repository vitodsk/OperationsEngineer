# You will probably need more methods from flask but this one is a good start.
from flask import render_template
from utils import PolicyAccounting, db
from accounting import app
from sqlalchemy import orm
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

handler = logging.FileHandler('accounting.log')
format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(format)
logger.addHandler(handler)


# Routing for the server.
@app.route("/", methods=['GET', 'POST'])
def index():
    # You will need to serve something up here.
    return render_template('index.html', context={})


@app.route("/<policy>/<supplied_date>")
def get_result(policy, supplied_date):

    errors = {}
    try:
        pa = PolicyAccounting(policy)
    except orm.exc.NoResultFound:
        error_text = "No Policy found with Policy id: " + policy
        errors['error'] = error_text
        logger.error(error_text)
        return render_template("error.html", context=errors )

    invoices = pa.get_invoices(supplied_date)
    balance = pa.return_account_balance(supplied_date)
    main_dic = {}
    invoices_list = []
    for invoice in invoices:
        logger.debug("invoice:  bill_date: %s - due_date: %s - cancel_date: %s - amount_due: %s",
                     invoice.bill_date, invoice.due_date, invoice.cancel_date, invoice.amount_due)
        invoices_list.append({
            'bill_date': invoice.bill_date.strftime('%Y-%m-%d'),
            'due_date': invoice.due_date.strftime('%Y-%m-%d'),
            'cancel_date': invoice.cancel_date.strftime('%Y-%m-%d'),
            'amount_due': invoice.amount_due
        })
    main_dic['invoices'] = invoices_list
    main_dic['balance'] = balance
    main_dic['policy_id'] = policy
    return render_template('table.html', context=main_dic)
