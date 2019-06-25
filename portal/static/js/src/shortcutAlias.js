/* global $ */
$("document").ready(function() {
    $("#shortcut_alias").on("keyup", function() {
        if (!$(this).val()) {
            $("#nextLink").addClass("disabled").attr("disabled", true);
            return;
        }
        $("#nextLink").removeClass("disabled").attr("disabled", false);
    });
    $("#shortcut_alias").attr("placeholder", "").focus();
    if ($("#shortcut_alias").val() !== "")  {
        $("#nextLink").removeClass("disabled").attr("disabled", false);
    }
});

