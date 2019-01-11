$(document).on("ready", function() {
    $("input[type='text']").on("blur paste", function() {
        $(this).val($.trim($(this).val()));
    });
});

