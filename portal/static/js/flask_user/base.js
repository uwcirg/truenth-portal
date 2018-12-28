$(document).on("ready", function() {
    var requestEmail =  Utility.getUrlParameter("email");
    if ($("#email").length && requestEmail) { /*global Utility getUrlParameter */
        $("#email").val(requestEmail);
    }
    $("input[type='text']").on("blur paste", function() {
        $(this).val($.trim($(this).val()));
    });
});

