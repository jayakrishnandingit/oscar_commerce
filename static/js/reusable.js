String.prototype.capitalize = function() {
    return this.charAt(0).toUpperCase() + this.slice(1);
}

function showFormErrors(jsonObj, formId) {
    $.each($('#' + formId + ' span.error'), function (index, element) {
        if (jsonObj[$(element).attr('name')]) {
            $(element).text(jsonObj[$(element).attr('name')][0]);
            $(element).show();
            if ($(element).hasClass('hidden')) {
                $(element).removeClass('hidden');
            }
        }
    });
}

function clearFormErrors(formId, exclude) {
    $.each($('#' + formId + ' span.error').not(exclude), function (index, element) {
        $(element).text('');
        $(element).hide();
    });
}
