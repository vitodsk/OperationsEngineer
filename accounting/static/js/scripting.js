
var number = {}

IndexViewModel = function() {
  var self = this;
  self.ok = ko.observable(false)
  self.policy = ko.observable('').extend({
    validation: {
      validator: function(val) {
        return (!ko.validation.utils.isEmptyVal(val) &&  /^[0-9]*$/.test(val));
      },
      message: 'must be numeric existing policy id!',
      ok: false
    }
  });

  self.dateTo = ko.observable(moment().format('YYYY-MM-DD')).extend({
    validation: {
      validator: function(val) {
        return moment(val, 'YYYY-MM-DD').isValid()
      },
      message: 'must be date like YYYY-MM-DD !',
      ok: false
    }
  });

  self.control_data = ko.dependentObservable(function(formElement) {
             self.ok(self.policy !== '' && self.policy.isValid() === true && self.dateTo.isValid() === true)

        })
};

ko.validation.init({
  registerExtenders: true,
  messagesOnModified: true,
  insertMessages: true,
  parseInputAttributes: true,
  messageTemplate: null,
  decorateInputElement: true,
  errorElementClass: 'form-error',
  errorsAsTitle: false
}, true);

var indexViewModel = new IndexViewModel();
ko.applyBindings(indexViewModel,document.body);

function find_data(policy,dateTo) {

    const Http = new XMLHttpRequest();
    url='http://localhost:5000/' + policy  +'/'+ dateTo

    $.get(url, function(data) {
    $("#showresults").html(data);
    });
}

