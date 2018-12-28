$(document).ready(function() { /*global $ */
    var fmBirthDate = $("#birthdate").val();
    if (fmBirthDate) {
        var arrDate = String(fmBirthDate).split("-");
        $("#month").val(arrDate[0]);
        $("#date").val(arrDate[1]);
        $("#year").val(arrDate[2]);
    }
    $("#month, #date, #year").on("change", function() {
        if (!$("#year").val() || !$("#month").val() || !$("#date").val()) {
            return;
        }
        $("#birthdate").val([$("#month").val(), $("#date").val(),$("#year").val()].join("-"));
    });
    $("input[type='text']").on("blur", function() {
        $(this).val($.trim($(this).val()));
    });
    //display keyboard for numeric fields on mobile devices
    if (Utility.isTouchDevice()) {
        Utility.convertToNumericField($("#date, #year")); /*global convertToNumericField */
    }

    $("#challengeForm").validator().on("submit", function (e) {
        if (e.isDefaultPrevented()) {
            return;
        }
    });
});
