$(document).ready(function() {
    var submitForm = function() {
        if (!$("#faInput").val()) return;
        $(".buttons-container").addClass("loading");
        setTimeout(function() {
            $("#TwoFAForm").submit();
        }, 50);
    };
    $("#resendValidationCode").on("click", function(e) {
        e.stopPropagation();
        submitForm();
    });
    $("#submitValidationCode").on("click", function(e) {
        e.stopPropagation();
        submitForm();
    });
    $(document).keypress(function(event) {
        if (event.which === 13) {
           submitForm();
           return false;
        }
        return true;
    });
});
