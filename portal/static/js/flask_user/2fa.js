$(document).ready(function() {
    $("#submitValidationCode").on("click", function(e) {
        e.stopPropagation();
        if (!$("#faInput").val()) return;
        $(".buttons-container").addClass("loading");
        setTimeout(function() {
            $("#TwoFAForm").submit();
        }, 50);

    });
});
