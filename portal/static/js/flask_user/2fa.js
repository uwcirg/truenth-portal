$(document).ready(function() {
    var VALIDATE_CODE_BUTTON_ID = "submitValidationCode";
    var RESENT_CODE_BUTTON_ID = "resendValidationCode";
    var submitForm = function(target) {
        //when submitting code, the code cannot be empty
        if ($(target).attr("id") == VALIDATE_CODE_BUTTON_ID && !$("#faInput").val()) return;
        //set field value if this is a resend
        if ($(target).attr("id") == RESENT_CODE_BUTTON_ID) {
            $("#resend_code").val("true");
        } else {
            $("#resend_code").val("false");
        }
        $(".buttons-container").addClass("loading");
        setTimeout(function() {
            $("#TwoFAForm").submit();
        }, 50);
    };
    $("#"+RESENT_CODE_BUTTON_ID).on("click", function(e) {
        e.stopPropagation();
        submitForm(e.target);
    });
    $("#"+VALIDATE_CODE_BUTTON_ID).on("click", function(e) {
        e.stopPropagation();
        submitForm(e.target);
    });
    $(document).keypress(function(event) {
        if (event.which === 13) {
           submitForm(event.target);
           return false;
        }
        return true;
    });
});
