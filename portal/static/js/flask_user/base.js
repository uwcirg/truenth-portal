$(document).on("ready", function() {
    if ($("#email").length && getUrlParameter("email")) { /*global getUrlParameter */
        $("#email").val(getUrlParameter("email"));
    }
    $("input[type='text']").on("blur paste", function() {
        $(this).val($.trim($(this).val()));
    });
});
